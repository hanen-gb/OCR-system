"""
main.py — Backend FastAPI  |  GLM-OCR (vision-language model)
=============================================================

Route principale :
    POST /predict
        - Reçoit une image (multipart/form-data)
        - Pipeline : image → GLM-OCR → JSON structuré
        - Retourne les entités extraites de la facture

Routes utilitaires :
    GET  /health   → statut + modèle chargé
    GET  /labels   → liste des entités supportées

Modèle : zai-org/GLM-OCR fine-tuné sur factures tunisiennes (LoRA mergé)
Singleton : modèle chargé une seule fois au démarrage (lifespan FastAPI)
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

# ── Config modèle ─────────────────────────────────────────────────────────────
# HF_MODEL_REPO : repo HF Hub contenant le modèle GLM mergé
# LOCAL_MODEL   : chemin local optionnel (backend/model/glm_model/)
HF_MODEL_REPO = os.getenv("HF_MODEL_REPO", "Goubaa/glmocr-factures")
_local_model  = Path(__file__).parent / "model" / "glm_model"
MODEL_SOURCE  = str(_local_model) if _local_model.exists() else HF_MODEL_REPO

# Entités extraites par le modèle
ENTITIES = ["CLIENT", "FOURNISSEUR", "DATE_FACTURE", "MONTANT_TTC", "NUMERO_FACTURE"]

# Prompt d'extraction (identique à l'entraînement)
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
MAX_IMAGE_SIZE = 1024  # pixels (côté max)

# ── Singletons ────────────────────────────────────────────────────────────────
_processor:    Optional[AutoProcessor]                = None
_model:        Optional[AutoModelForImageTextToText]  = None
_models_ready: bool = False
_device:       str  = "cuda" if torch.cuda.is_available() else "cpu"


# ─────────────────────────────────────────────────────────────────────────────
# Chargement du modèle
# ─────────────────────────────────────────────────────────────────────────────

def _fix_filenames(model_dir: Path) -> None:
    """Renomme les fichiers 'name (N).ext' → 'name.ext' (artefact Windows)."""
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
    """Charge le processor et le modèle GLM-OCR mergé. Appelé une seule fois."""
    global _processor, _model, _models_ready

    logger.info("=== Chargement GLM-OCR depuis : %s (device=%s) ===", MODEL_SOURCE, _device)
    t0 = time.time()

    source = MODEL_SOURCE

    # Corriger les noms de fichiers si chargement local
    if Path(source).exists():
        _fix_filenames(Path(source))

    # ── Processor ─────────────────────────────────────────────────────────────
    logger.info("Chargement processor...")
    _processor = AutoProcessor.from_pretrained(
        source,
        use_fast=False,
        trust_remote_code=True,
    )

    # ── Modèle ────────────────────────────────────────────────────────────────
    logger.info("Chargement modèle GLM-OCR...")
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
    logger.info("=== Modèle GLM-OCR prêt en %.1f s ===", time.time() - t0)


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
    logger.info("Modèle libéré.")


# ─────────────────────────────────────────────────────────────────────────────
# Application FastAPI
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GLM-OCR Backend",
    description="Pipeline : image facture → GLM-OCR → JSON structuré",
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
# Pipeline d'inférence GLM-OCR
# ─────────────────────────────────────────────────────────────────────────────

def resize_image(image: Image.Image, max_size: int = MAX_IMAGE_SIZE) -> Image.Image:
    """Redimensionne l'image si elle dépasse max_size pixels (côté max)."""
    w, h = image.size
    if max(w, h) <= max_size:
        return image
    scale = max_size / max(w, h)
    return image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def parse_glm_output(raw_text: str) -> dict:
    """
    Extrait le JSON de la sortie brute du modèle.
    Gère les cas où le modèle ajoute du texte autour du JSON.
    """
    # Chercher un bloc JSON entre accolades
    match = re.search(r'\{[^{}]*\}', raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback : essayer de parser directement
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        pass

    # Dernier recours : retourner N/A pour tout
    logger.warning("Impossible de parser la sortie GLM : %s", raw_text[:200])
    return {e: "N/A" for e in ENTITIES}


def run_glm(pil_image: Image.Image) -> tuple[dict, str]:
    """
    Exécute GLM-OCR sur une image PIL.

    Returns:
        (parsed_dict, raw_text) :
            parsed_dict : {CLIENT: ..., FOURNISSEUR: ..., ...}
            raw_text    : sortie brute du modèle
    """
    image = pil_image.convert("RGB")
    image = resize_image(image)

    # Construire le message avec le template de chat GLM
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

    # Décoder seulement les tokens générés (pas le prompt)
    input_len = inputs["input_ids"].shape[1]
    raw_text = _processor.decode(
        output_ids[0][input_len:],
        skip_special_tokens=True,
    ).strip()

    parsed = parse_glm_output(raw_text)
    return parsed, raw_text


def build_entities(parsed: dict) -> list:
    """
    Convertit le dict parsé en liste d'entités compatible avec le frontend.
    Format : [{"label": str, "text": str, "box": null}]
    """
    entities = []
    for label in ENTITIES:
        value = parsed.get(label, "N/A")
        if value and value != "N/A":
            entities.append({
                "label": label,
                "text":  str(value),
                "box":   None,   # GLM ne fournit pas de coordonnées spatiales
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
    Pipeline GLM-OCR : image → JSON structuré.

    Retour :
    {
        "entities": [{"label": str, "text": str, "box": null, "words": []}],
        "full_text": str,    ← sortie brute du modèle
        "timing": {"inference_ms": int, "total_ms": int}
    }
    """
    if not _models_ready:
        raise HTTPException(503, "Modèle en cours de chargement, réessayez dans quelques secondes")

    ext = Path(file.filename or "img.jpg").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}:
        raise HTTPException(400, f"Format non supporté : {ext}")

    img_bytes = await file.read()
    t_start   = time.time()

    # ── Charger l'image ───────────────────────────────────────────────────────
    try:
        pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(422, f"Image invalide : {e}")

    # ── Inférence GLM-OCR ─────────────────────────────────────────────────────
    try:
        t0 = time.time()
        parsed, raw_text = run_glm(pil_image)
        ms_inference = int((time.time() - t0) * 1000)
    except Exception as e:
        logger.error("Erreur inférence GLM : %s", e)
        raise HTTPException(500, f"Erreur inférence : {e}")

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
# Point d'entrée local
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7860, reload=False)
