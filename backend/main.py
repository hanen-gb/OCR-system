"""
main.py — Backend FastAPI  |  GLM-OCR (vision-language model)
=============================================================

Route principale :
    POST /predict
        - Receives an image (multipart/form-data)
        - Pipeline: image → GLM-OCR → structured JSON
        - Returns the entities extracted from the invoice

Routes utilitaires :
    GET  /health   → status + loaded model
    GET  /labels   → list of supported entities

Model: zai-org/GLM-OCR fine-tuned on invoices (LoRA merged)
Singleton: the model is loaded once at start-up (FastAPI lifespan)
"""

import gc
import io
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import torch
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("backend")

# ── Model configuration ───────────────────────────────────────────────────────
# HF_MODEL_REPO: Hugging Face Hub repository holding the merged GLM model
# LOCAL_MODEL   : optional local path (backend/model/glm_model/)
HF_MODEL_REPO = os.getenv("HF_MODEL_REPO", "Goubaa/glmocr-factures")
_local_model  = Path(__file__).parent / "model" / "glm_model"
MODEL_SOURCE  = str(_local_model) if _local_model.exists() else HF_MODEL_REPO

# Entities extracted by the model
ENTITIES = ["CLIENT", "FOURNISSEUR", "DATE_FACTURE", "MONTANT_TTC", "NUMERO_FACTURE"]

# Extraction prompt (identical to the one used for training)
PROMPT = (
    "Extrais les informations suivantes de cette facture en JSON :\n"
    "- CLIENT : nom du client\n"
    "- FOURNISSEUR : nom du fournisseur\n"
    "- DATE_FACTURE : date de la facture (format JJ/MM/AAAA)\n"
    "- MONTANT_TTC : montant total TTC (ou N/A si absent)\n"
    "- NUMERO_FACTURE : numero de facture\n"
    "Reponds UNIQUEMENT avec un objet JSON valide.\n"
    "Si une information est absente, mettre N/A."
)

MAX_NEW_TOKENS = 256
MAX_IMAGE_SIZE = 1024  # pixels (longest side)

# ── Singletons ────────────────────────────────────────────────────────────────
_processor:    Optional[AutoProcessor]                = None
_model:        Optional[AutoModelForImageTextToText]  = None
_models_ready: bool = False
_device:       str  = "cuda" if torch.cuda.is_available() else "cpu"


# ─────────────────────────────────────────────────────────────────────────────
# Model loading
# ─────────────────────────────────────────────────────────────────────────────

def _fix_filenames(model_dir: Path) -> None:
    """Renames 'name (N).ext' files to 'name.ext' (Windows download artefact)."""
    pattern = re.compile(r'^(.+?) \(\d+\)(\..+)$')
    for f in model_dir.iterdir():
        m = pattern.match(f.name)
        if m:
            clean = m.group(1) + m.group(2)
            target = model_dir / clean
            if not target.exists():
                f.rename(target)
                logger.info("Renomme : %s → %s", f.name, clean)


def load_models() -> None:
    """Loads the processor and the merged GLM-OCR model. Called once."""
    global _processor, _model, _models_ready

    logger.info("=== Loading GLM-OCR from: %s (device=%s) ===", MODEL_SOURCE, _device)
    t0 = time.time()

    source = MODEL_SOURCE

    # Fix the file names when loading from a local folder
    if Path(source).exists():
        _fix_filenames(Path(source))

    # ── Processor ─────────────────────────────────────────────────────────────
    logger.info("Loading the processor...")
    _processor = AutoProcessor.from_pretrained(
        source,
        use_fast=False,
        trust_remote_code=True,
    )

    # ── Model ─────────────────────────────────────────────────────────────────
    logger.info("Loading the GLM-OCR model...")
    _model = AutoModelForImageTextToText.from_pretrained(
        source,
        torch_dtype=torch.float16 if _device == "cuda" else torch.float32,
        device_map="auto" if _device == "cuda" else None,
        trust_remote_code=True,
    )

    if _device == "cpu":
        _model = _model.to("cpu")

    _model.eval()

    _models_ready = True
    logger.info("=== GLM-OCR model ready in %.1f s ===", time.time() - t0)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan FastAPI
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_models()
    yield
    global _model, _processor
    _model     = None
    _processor = None
    gc.collect()
    if _device == "cuda":
        torch.cuda.empty_cache()
    logger.info("Model released.")


# ─────────────────────────────────────────────────────────────────────────────
# Application FastAPI
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GLM-OCR Backend",
    description="Pipeline: invoice image → GLM-OCR → structured JSON",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# GLM-OCR inference pipeline
# ─────────────────────────────────────────────────────────────────────────────

def resize_image(image: Image.Image, max_size: int = MAX_IMAGE_SIZE) -> Image.Image:
    """Resizes the image if it exceeds max_size pixels (longest side)."""
    w, h = image.size
    if max(w, h) <= max_size:
        return image
    scale = max_size / max(w, h)
    return image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def parse_glm_output(raw_text: str) -> dict:
    """
    Extracts the JSON from the raw model output.
    Handles cases where the model adds text around the JSON.
    """
    # Chercher un bloc JSON entre accolades
    match = re.search(r'\{[^{}]*\}', raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: try to parse directly
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        pass

    # Last resort: return N/A for every field
    logger.warning("Cannot parse the GLM output: %s", raw_text[:200])
    return {e: "N/A" for e in ENTITIES}


def run_glm(pil_image: Image.Image) -> tuple[dict, str]:
    """
    Runs GLM-OCR on a PIL image.

    Returns:
        (parsed_dict, raw_text) :
            parsed_dict : {CLIENT: ..., FOURNISSEUR: ..., ...}
            raw_text    : raw model output
    """
    image = pil_image.convert("RGB")
    image = resize_image(image)

    # Build the message with the GLM chat template
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text",  "text":  PROMPT},
            ],
        }
    ]

    text = _processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = _processor(
        text=[text],
        images=[image],
        return_tensors="pt",
    ).to(_device)

    with torch.inference_mode():
        output_ids = _model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )

    # Decode only the generated tokens (not the prompt)
    input_len = inputs["input_ids"].shape[1]
    raw_text = _processor.decode(
        output_ids[0][input_len:],
        skip_special_tokens=True,
    ).strip()

    parsed = parse_glm_output(raw_text)
    return parsed, raw_text


def build_entities(parsed: dict) -> list:
    """
    Converts the parsed dict into a list of entities compatible with the frontend.
    Format : [{"label": str, "text": str, "box": null}]
    """
    entities = []
    for label in ENTITIES:
        value = parsed.get(label, "N/A")
        if value and value != "N/A":
            entities.append({
                "label": label,
                "text":  str(value),
                "box":   None,   # GLM does not return spatial coordinates
                "words": [],
            })
    return entities


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status":       "ok" if _models_ready else "loading",
        "models_ready": _models_ready,
        "model":        "GLM-OCR" if _model is not None else "not_loaded",
        "device":       _device,
        "source":       MODEL_SOURCE,
    }


@app.get("/labels")
async def get_labels():
    return {"labels": ENTITIES, "count": len(ENTITIES)}


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    """
    GLM-OCR pipeline: image → structured JSON.

    Retour :
    {
        "entities": [{"label": str, "text": str, "box": null, "words": []}],
        "full_text": str,    ← raw model output
        "timing": {"inference_ms": int, "total_ms": int}
    }
    """
    if not _models_ready:
        raise HTTPException(503, "Model is loading, try again in a few seconds")

    ext = Path(file.filename or "img.jpg").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}:
        raise HTTPException(400, f"Unsupported format: {ext}")

    img_bytes = await file.read()
    t_start   = time.time()

    # ── Charger l'image ───────────────────────────────────────────────────────
    try:
        pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(422, f"Image invalide : {e}")

    # ── GLM-OCR inference ─────────────────────────────────────────────────────
    try:
        t0 = time.time()
        parsed, raw_text = run_glm(pil_image)
        ms_inference = int((time.time() - t0) * 1000)
    except Exception as e:
        logger.error("GLM inference error: %s", e)
        raise HTTPException(500, f"Inference error: {e}")

    entities = build_entities(parsed)
    ms_total = int((time.time() - t_start) * 1000)

    gc.collect()
    if _device == "cuda":
        torch.cuda.empty_cache()

    return JSONResponse({
        "entities":  entities,
        "full_text": raw_text,
        "timing": {
            "inference_ms": ms_inference,
            "total_ms":     ms_total,
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# Local entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7860, reload=False)
