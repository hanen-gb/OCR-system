"""
modal_app.py — Backend GLM-OCR deploye sur Modal (GPU T4)
==========================================================

Deploiement :
    modal deploy modal_app.py

URL produite :
    https://<workspace>--glmocr-backend-fastapi-app.modal.run
"""

import io
import modal

# ── Image Docker Modal ────────────────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .pip_install(
        # torch >= 2.4 requis par git transformers + CUDA 12.1
        "torch==2.4.1",
        "torchvision==0.19.1",     # requis par Glm46VVideoProcessor
        extra_index_url="https://download.pytorch.org/whl/cu121",
    )
    .pip_install(
        "fastapi==0.111.0",
        "uvicorn[standard]==0.29.0",
        "python-multipart==0.0.9",
        "accelerate>=0.30.0",
        "safetensors==0.4.3",
        "Pillow==10.3.0",
        "huggingface_hub==0.28.1",
        "sentencepiece",
        "tiktoken",       # requis par le code custom GLM-4V
        "einops",         # requis par le code custom GLM-4V (attention)
        "numpy<2",        # evite le conflit NumPy 1.x vs 2.x avec torch
    )
    .pip_install(
        # transformers version git (obligatoire pour zai-org/GLM-OCR)
        "git+https://github.com/huggingface/transformers.git"
    )
)

# ── App Modal ─────────────────────────────────────────────────────────────────
app = modal.App("glmocr-backend", image=image)

# ── Volume cache : modele telecharge une seule fois ───────────────────────────
model_cache = modal.Volume.from_name("glmocr-model-cache", create_if_missing=True)

HF_MODEL_REPO      = "Goubaa/glmocr-factures"
HF_TRAITE_REPO     = "Goubaa/glm-traite-tunis"
HF_CLASSIFIER_REPO = "Goubaa/mobilenet-classifier"
CACHE_PATH         = "/model_cache"

ENTITIES = ["CLIENT", "FOURNISSEUR", "DATE_FACTURE", "MONTANT_TTC", "NUMERO_FACTURE"]

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

ENTITIES_TRAITE = [
    "numero_traite", "date_echeance", "montant",
    "tireur", "tire", "rib", "domiciliation",
]

# Le modele a ete fine-tune pour repondre avec ces cles en minuscules (ENTITIES_TRAITE),
# mais le frontend (TRAITE_LABELS dans frontend/src/lib/api.ts) attend des labels en
# MAJUSCULES pour les entites retournees par /predict. Ce mapping fait le pont.
ENTITIES_TRAITE_LABEL_MAP = {
    "numero_traite":   "NUMERO_TRAITE",
    "date_echeance":   "DATE_ECHEANCE",
    "montant":         "MONTANT",
    "tireur":          "TIREUR",
    "tire":            "TIRE",
    "rib":             "RIB",
    "domiciliation":   "DOMICILIATION",
}

PROMPT_TRAITE = """Tu es un expert OCR spécialisé dans les lettres de change tunisiennes (كمبيالة).
Analyse l'image et extrais les 7 champs suivants en te guidant par leur POSITION sur le document :

1. numero_traite
   → Coin HAUT DROIT du document, après "Ordre de paiement L-CN" ou "أمر بدفع الكمبيالة عدد"
   → Suite de chiffres (10-12 chiffres), aussi visible dans le code-barres en BAS
   → Exemple : 012345678901

2. date_echeance
   → Zone HAUT GAUCHE, champ "Echéance / حلول الأجل"
   → C'est la date FUTURE (pas la date de création)
   → Format JJ/MM/AAAA
   → Exemple : 15/09/2026

3. montant
   → Zone HAUT DROIT, champ "Montant / البلغ"
   → Valeur numérique avec point ou virgule décimale
   → Ignorer "Montant en lettres"
   → Exemple : 2000.000

4. tireur
   → Zone MILIEU GAUCHE, champ "Tireur / الساحب"
   → Nom de la société ou personne qui émet la traite
   → Souvent en MAJUSCULES ou tampon
   → Exemple : SOCIETE EXEMPLE SARL

5. tire
   → Zone BAS CENTRE, champ "Nom et adresse du Tiré / اسم وعنوان المسحوب عليه"
   → Prendre UNIQUEMENT la première ligne (nom/société), ignorer l'adresse
   → Exemple : SOCIETE CLIENTE

6. rib
   → Zone MILIEU, champ "RIB ou RIP du Tiré / المعرف البنكي"
   → Code étab + Code Agence + N° Compte + Clé, sans espaces, chiffres uniquement
   → Exemple : 01234567890123456789

7. domiciliation
   → Zone BAS DROIT, champ "Domiciliation / اسم وعنوان الفرع المسحوب عليه"
   → Nom de la banque uniquement (BIAT, BNA, STB, Attijari, UIB, BTK...)
   → Exemple : BIAT

RÈGLES STRICTES :
- Répondre UNIQUEMENT avec un objet JSON valide, aucun texte avant ou après
- Si un champ est illisible → "illisible"
- Si un champ est absent → "N/A"
- Pour le RIB : chiffres uniquement, ignorer les lettres parasites

FORMAT :
{"numero_traite": "...", "date_echeance": "...", "montant": "...", "tireur": "...", "tire": "...", "rib": "...", "domiciliation": "..."}"""


# ── Classificateur (CPU — MobileNet léger) ───────────────────────────────────
@app.cls(
    cpu=2,
    scaledown_window=600,
    timeout=60,
    volumes={CACHE_PATH: model_cache},
)
class Classifier:

    @modal.enter()
    def load(self):
        import torch
        import torch.nn as nn
        import torchvision.models as models
        from huggingface_hub import hf_hub_download

        weights_path = hf_hub_download(
            repo_id=HF_CLASSIFIER_REPO,
            filename="best_model.pth",
            cache_dir=CACHE_PATH,
        )

        # Checkpoint dict sauvegardé avec torch.save({..., "model_state": ..., "classes": [...]})
        checkpoint = torch.load(weights_path, map_location="cpu")

        # ["factures", "traites"] → index 0 = factures, index 1 = traites
        classes = checkpoint.get("classes", ["factures", "traites"])
        self.idx_to_class = {i: c for i, c in enumerate(classes)}

        # Architecture identique au notebook Kaggle
        net = models.mobilenet_v2(weights=None)
        net.classifier = nn.Sequential(
            nn.Dropout(p=0.4),
            nn.Linear(1280, 256),
            nn.ReLU(),
            nn.Dropout(p=0.3),
            nn.Linear(256, 2),
        )
        net.load_state_dict(checkpoint["model_state"])
        net.eval()
        self.model = net
        print(f"Classifier OK — classes : {self.idx_to_class}")

    @modal.method()
    def classify(self, image_bytes: bytes) -> dict:
        import io, torch
        from PIL import Image
        import torchvision.transforms as T

        # Transform identique au test_transform du notebook Kaggle
        transform = T.Compose([
            T.Resize((224, 224)),
            T.Grayscale(num_output_channels=3),   # obligatoire : même pipeline qu'à l'entraînement
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        image  = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = transform(image).unsqueeze(0)   # (1, 3, 224, 224)

        with torch.no_grad():
            probs    = torch.softmax(self.model(tensor), dim=1)[0]
            pred_idx = probs.argmax().item()

        return {
            "doc_type":   self.idx_to_class[pred_idx],   # "factures" | "traites"
            "confidence": round(probs[pred_idx].item(), 4),
        }


# ── Classe principale (GPU T4) ────────────────────────────────────────────────
@app.cls(
    gpu="T4",
    scaledown_window=600,              # garde le modele 10 min en RAM (anti cold-start)
    timeout=300,                       # 5 min max par requete
    volumes={CACHE_PATH: model_cache}, # cache persistant du modele
)
class Model:

    @modal.enter()
    def load(self):
        """Charge le modele une seule fois au demarrage du container."""
        import os, torch, traceback
        from transformers import AutoProcessor, AutoModelForImageTextToText

        os.environ["TRANSFORMERS_CACHE"] = CACHE_PATH
        os.environ["HF_HOME"]            = CACHE_PATH

        print(f"=== DEBUT CHARGEMENT {HF_MODEL_REPO} ===")
        import time; t0 = time.time()

        try:
            print("Etape 1/2 : chargement du Processor...")
            self.processor = AutoProcessor.from_pretrained(
                HF_MODEL_REPO,
                use_fast=False,        # requis pour GLM-OCR (notebook)
                trust_remote_code=True,
                cache_dir=CACHE_PATH,
            )
            print("Processor OK")

            print("Etape 2/2 : chargement du Modele (float16)...")
            self.model = AutoModelForImageTextToText.from_pretrained(
                HF_MODEL_REPO,
                dtype=torch.float16,      # remplace torch_dtype (deprecated)
                device_map="auto",
                trust_remote_code=True,
                cache_dir=CACHE_PATH,
            )
            self.model.eval()
            print(f"=== MODELE PRET EN {time.time()-t0:.1f}s ===")

        except Exception as e:
            print(f"=== ERREUR CHARGEMENT : {type(e).__name__}: {e} ===")
            traceback.print_exc()
            raise

    @modal.method()
    def predict(self, image_bytes: bytes) -> dict:
        """Inference GLM-OCR sur une image (bytes)."""
        import gc, io, json, re, time, torch
        from PIL import Image

        t0 = time.time()

        # Charger et redimensionner l'image
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h  = image.size
        if max(w, h) > 1024:
            scale = 1024 / max(w, h)
            image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Construire le message — format exact du notebook de fine-tuning
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text",  "text":  PROMPT},
            ],
        }]

        # apply_chat_template avec tokenize=True (une seule étape, comme le notebook)
        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
            processor_kwargs={"return_mm_token_type_ids": True},
        )
        # Déplacer vers GPU et retirer token_type_ids (incompatible avec generate)
        inputs = {
            k: v.to("cuda") if isinstance(v, torch.Tensor) else v
            for k, v in inputs.items()
        }
        inputs.pop("token_type_ids", None)

        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                temperature=None,
                top_p=None,
            )

        input_len = inputs["input_ids"].shape[1]
        raw_text  = self.processor.decode(
            output_ids[0][input_len:], skip_special_tokens=True
        ).strip()

        print(f"GLM raw output: {raw_text[:200]}")

        # Parser le JSON
        parsed = {}
        match  = re.search(r'\{[^{}]*\}', raw_text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                parsed = {e: "N/A" for e in ENTITIES}
        else:
            parsed = {e: "N/A" for e in ENTITIES}

        entities = [
            {"label": label, "text": str(parsed.get(label, "N/A")), "box": None, "words": []}
            for label in ENTITIES
            if parsed.get(label) and parsed.get(label) != "N/A"
        ]

        ms = int((time.time() - t0) * 1000)
        gc.collect()
        torch.cuda.empty_cache()

        return {
            "entities":  entities,
            "full_text": raw_text,
            "timing":    {"inference_ms": ms, "total_ms": ms},
        }


# ── Classe GLM Lettre de change (GPU T4) ─────────────────────────────────────
@app.cls(
    gpu="T4",
    scaledown_window=600,
    timeout=300,
    volumes={CACHE_PATH: model_cache},
)
class ModelTraite:

    @modal.enter()
    def load(self):
        import os, torch, traceback
        from transformers import AutoProcessor, AutoModelForImageTextToText

        os.environ["TRANSFORMERS_CACHE"] = CACHE_PATH
        os.environ["HF_HOME"]            = CACHE_PATH

        print(f"=== DEBUT CHARGEMENT {HF_TRAITE_REPO} ===")
        import time; t0 = time.time()

        try:
            self.processor = AutoProcessor.from_pretrained(
                HF_TRAITE_REPO,
                use_fast=False,
                trust_remote_code=True,
                cache_dir=CACHE_PATH,
            )
            self.model = AutoModelForImageTextToText.from_pretrained(
                HF_TRAITE_REPO,
                dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True,
                cache_dir=CACHE_PATH,
            )
            self.model.eval()
            print(f"=== MODELE TRAITE PRET EN {time.time()-t0:.1f}s ===")
        except Exception as e:
            print(f"=== ERREUR CHARGEMENT TRAITE : {type(e).__name__}: {e} ===")
            traceback.print_exc()
            raise

    @modal.method()
    def predict(self, image_bytes: bytes) -> dict:
        import gc, io, json, re, time, torch
        from PIL import Image

        t0    = time.time()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h  = image.size
        if max(w, h) > 1024:
            scale = 1024 / max(w, h)
            image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text",  "text":  PROMPT_TRAITE},
            ],
        }]

        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
            processor_kwargs={"return_mm_token_type_ids": True},
        )
        inputs = {
            k: v.to("cuda") if isinstance(v, torch.Tensor) else v
            for k, v in inputs.items()
        }
        inputs.pop("token_type_ids", None)

        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                temperature=None,
                top_p=None,
            )

        input_len = inputs["input_ids"].shape[1]
        raw_text  = self.processor.decode(
            output_ids[0][input_len:], skip_special_tokens=True
        ).strip()

        print(f"GLM Traite raw output: {raw_text[:200]}")

        parsed = {}
        match  = re.search(r'\{[^{}]*\}', raw_text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                parsed = {e: "N/A" for e in ENTITIES_TRAITE}
        else:
            parsed = {e: "N/A" for e in ENTITIES_TRAITE}

        entities = [
            {"label": ENTITIES_TRAITE_LABEL_MAP[label], "text": str(parsed.get(label, "N/A")), "box": None, "words": []}
            for label in ENTITIES_TRAITE
            if parsed.get(label) and parsed.get(label) != "N/A"
        ]

        ms = int((time.time() - t0) * 1000)
        gc.collect()
        torch.cuda.empty_cache()

        return {
            "entities":  entities,
            "full_text": raw_text,
            "timing":    {"inference_ms": ms, "total_ms": ms},
        }


# ── FastAPI wrapper ───────────────────────────────────────────────────────────
@app.function()
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, File, Form, UploadFile, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pathlib import Path

    web_app = FastAPI(title="GLM-OCR Backend (Modal)")
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @web_app.get("/health")
    async def health():
        return {"status": "ok", "model": HF_MODEL_REPO, "gpu": "T4"}

    @web_app.get("/labels")
    async def labels():
        return {"labels": ENTITIES, "count": len(ENTITIES)}

    @web_app.post("/predict")
    async def predict(
        file          : UploadFile = File(...),
        document_type : str        = Form(default="auto"),  # "auto" | "factures" | "traites"
    ):
        ext = Path(file.filename or "img.jpg").suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}:
            raise HTTPException(400, f"Format non supporte : {ext}")

        image_bytes = await file.read()

        try:
            # ── Étape 1 : classification (sauf si override manuel) ────────────
            if document_type in ("factures", "traites"):
                # Override manuel : bypass le classifieur
                doc_type   = document_type
                confidence = 1.0
                print(f"[PREDICT] Override manuel : {doc_type}")
            else:
                classification = await Classifier().classify.remote.aio(image_bytes)
                doc_type       = classification["doc_type"]
                confidence     = classification["confidence"]
                print(f"[PREDICT] Classifieur : {doc_type} (conf={confidence:.2f})")

            # ── Étape 2 : routage vers le bon modèle ─────────────────────────
            if doc_type == "factures":
                result = await Model().predict.remote.aio(image_bytes)
            else:
                result = await ModelTraite().predict.remote.aio(image_bytes)

            result["doc_type"]                  = doc_type
            result["classification_confidence"] = confidence

        except Exception as e:
            raise HTTPException(500, f"Erreur inference : {e}")

        return JSONResponse(result)

    return web_app
