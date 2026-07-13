"""
Outils de l'Agent 1 — L'Extracteur

4 outils LangGraph :
  1. detect_file_type           — Détecte le type de fichier (pdf_native / pdf_scanned / image)
  2. extract_text_pdf_native    — Extrait le texte d'un PDF natif via pdfplumber
  3. extract_text_vision        — Extrait le texte via OCR.space (ou Gemini/Groq en fallback)
  4. extract_augmented_entities — Extrait les entités JSON via Mistral (ou Gemini/Groq en fallback)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
APIs gratuites — AUCUNE carte bancaire requise
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VISION (OCR) — OCR.space
  OCR_SPACE_API_KEY → ocr.space/OCRAPI → clé reçue par email
  Limites gratuites : 25 000 req/mois, 1 MB par fichier

EXTRACTION (LLM texte) — HuggingFace Inference API
  HF_API_KEY        → huggingface.co → Settings → Access Tokens → New token
  Modèle            → mistralai/Mistral-7B-Instruct-v0.3 (gratuit, endpoint cloud)
  Limites gratuites : généreuses, aucune installation locale

FALLBACK LLM : MISTRAL_API_KEY → GOOGLE_API_KEY → GROQ_API_KEY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import base64
import io
import json
import os
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

# ── Modèles ───────────────────────────────────────────────────────────────────
GROQ_BASE_URL          = "https://api.groq.com/openai/v1"
GROQ_TEXT_MODEL        = "qwen/qwen3-32b"                          # primary texte : Qwen3 32B
GROQ_FALLBACK_MODEL    = "llama-3.3-70b-versatile"                 # fallback 413 : 128k ctx
GROQ_GEMMA_MODEL       = "qwen/qwen3-32b"                          # alias conservé
GROQ_VISION_MODEL      = "meta-llama/llama-4-scout-17b-16e-instruct"  # vision multimodal Groq
HF_MODEL               = "Qwen/Qwen2.5-7B-Instruct"
HF_VISION_MODEL        = "Qwen/Qwen2-VL-7B-Instruct"             # vision HF (skip si 402)
MISTRAL_MODEL          = "mistral-small-latest"
GEMINI_MODEL           = "gemini-2.0-flash"
OCR_SPACE_URL          = "https://api.ocr.space/parse/image"

# Limite de tronquage pour les gros documents (chars → ~10k tokens)
_MAX_PROMPT_CHARS = 40_000


def _truncate_prompt(prompt: str, max_chars: int = _MAX_PROMPT_CHARS) -> str:
    """Garde le début (instructions) et la fin (schéma JSON) du prompt, coupe le milieu."""
    if len(prompt) <= max_chars:
        return prompt
    keep = max_chars // 2
    return (
        prompt[:keep]
        + "\n\n[... texte tronqué — document trop long ...]\n\n"
        + prompt[-keep:]
    )


def _call_llm(prompt: str) -> str:
    """
    Chaîne de fallback LLM texte :
      Groq llama-3.3-70b-versatile
        → Groq llama-3.1-8b-instant (si 413, avec prompt tronqué)
        → HuggingFace Qwen2.5-7B   (si disponible)
        → Gemini 2.0-flash / 1.5-flash / 1.5-pro
        → OpenAI gpt-4o-mini (tout dernier recours, si OPENAI_API_KEY défini)
    """
    errors = []

    # ── Groq (essai primary puis fallback si 413) ─────────────────────────────
    if os.getenv("GROQ_API_KEY"):
        p = _truncate_prompt(prompt)   # troncature préventive pour tous les modèles Groq
        groq_models = [
            (GROQ_TEXT_MODEL,     p),   # Qwen3-32b primary
            (GROQ_FALLBACK_MODEL, p),   # llama fallback si Qwen quota/413
        ]
        groq_quota_hit = False
        for groq_model, p in groq_models:
            if groq_quota_hit:
                break
            try:
                from langchain_openai import ChatOpenAI
                from langchain_core.messages import HumanMessage as HM
                llm = ChatOpenAI(
                    model=groq_model,
                    api_key=os.getenv("GROQ_API_KEY"),
                    base_url=GROQ_BASE_URL,
                    temperature=0,
                    max_tokens=8192,
                )
                result = llm.invoke([HM(content=p)]).content
                print(f"[LLM] Groq/{groq_model} ✓")
                return result
            except Exception as e:
                msg = str(e)
                if "413" in msg or "too large" in msg.lower() or "request_too_large" in msg.lower():
                    print(f"[LLM] Groq/{groq_model} 413 payload trop grand — modèle suivant")
                    errors.append(f"Groq/{groq_model} 413: {msg[:120]}")
                    # continue → essaie GROQ_FALLBACK_MODEL avec prompt tronqué
                elif "429" in msg or "rate_limit" in msg.lower() or "quota" in msg.lower():
                    print(f"[LLM] Groq/{groq_model} quota atteint — bascule sur HF/Gemini")
                    errors.append(f"Groq/{groq_model} 429: {msg[:120]}")
                    groq_quota_hit = True   # inutile d'essayer l'autre modèle Groq
                elif "403" in msg or "401" in msg or "forbidden" in msg.lower() or "unauthorized" in msg.lower() or "invalid api key" in msg.lower():
                    print(f"[LLM] Groq/{groq_model} clé invalide/refusée — bascule sur HF/Gemini")
                    errors.append(f"Groq/{groq_model} auth: {msg[:120]}")
                    groq_quota_hit = True   # clé invalide pour tous les modèles Groq, inutile de réessayer
                else:
                    raise  # erreur inattendue → propager

    # ── HuggingFace (rotation compte 1 → compte 2 si 402/429) ────────────────
    _hf_tokens = [t for t in [os.getenv("HF_API_KEY"), os.getenv("HF_API_KEY_2")] if t]
    for _idx, _hf_token in enumerate(_hf_tokens, 1):
        try:
            from huggingface_hub import InferenceClient
            client   = InferenceClient(token=_hf_token)
            response = client.chat_completion(
                model=HF_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8192,
                temperature=0.01,
            )
            print(f"[LLM] HuggingFace compte {_idx} ✓")
            return response.choices[0].message.content
        except Exception as e:
            msg = str(e)
            if ("429" in msg or "quota" in msg.lower() or "402" in msg or "payment" in msg.lower()
                    or "403" in msg or "forbidden" in msg.lower() or "401" in msg or "unauthorized" in msg.lower()):
                print(f"[LLM] HuggingFace compte {_idx} indisponible ({msg[:60]}) — compte suivant")
                errors.append(f"HF{_idx} skip: {msg[:120]}")
            else:
                raise

    # ── Google Gemini ──────────────────────────────────────────────────────────
    if os.getenv("GOOGLE_API_KEY"):
        for gemini_model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                from langchain_core.messages import HumanMessage as HM
                llm = ChatGoogleGenerativeAI(
                    model=gemini_model,
                    google_api_key=os.getenv("GOOGLE_API_KEY"),
                    temperature=0,
                )
                result = llm.invoke([HM(content=prompt)]).content
                print(f"[LLM] Gemini/{gemini_model} ✓")
                return result
            except Exception as e:
                msg = str(e)
                errors.append(f"Gemini/{gemini_model}: {msg[:120]}")
                print(f"[LLM] Gemini/{gemini_model} → {msg[:120]}")
                continue

    # ── OpenAI gpt-4o-mini (tout dernier recours — uniquement si Groq+HF+Gemini
    #    ont tous échoué ; évite de dépendre d'OpenAI en temps normal) ──────────
    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage as HM
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=os.getenv("OPENAI_API_KEY"),
                temperature=0,
            )
            result = llm.invoke([HM(content=prompt)]).content
            print("[LLM] OpenAI/gpt-4o-mini ✓ (dernier recours)")
            return result
        except Exception as e:
            msg = str(e)
            errors.append(f"OpenAI/gpt-4o-mini: {msg[:120]}")
            print(f"[LLM] OpenAI/gpt-4o-mini → {msg[:120]}")

    if errors:
        raise EnvironmentError(f"Tous les LLM ont échoué :\n" + "\n".join(errors))

    raise EnvironmentError(
        "\n❌ Aucune clé API LLM trouvée dans assistant/.env\n"
        "Ajouter au moins : GROQ_API_KEY=gsk_...  ou  GOOGLE_API_KEY=AIza...\n"
    )


def _sanitize_llm_json(raw: str) -> str:
    """
    Échappe les caractères de contrôle bruts insérés par le LLM à l'intérieur
    des valeurs de chaînes JSON (\\n \\r \\t littéraux qui cassent json.loads).

    Exemple : "notes_manuscrites": "cinq cent\\nquatre vingt..."
      → le \\n brut n'est pas une séquence d'échappement JSON → JSONDecodeError.
    Fix : remplace \\n/\\r/\\t par leurs équivalents JSON \\\\n/\\\\r/\\\\t,
          supprime les autres caractères de contrôle (<0x20, sauf dans les clés
          structurelles JSON qui sont déjà hors d'une chaîne).
    """
    result: list[str] = []
    in_string = False
    escape_next = False
    for ch in raw:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == "\\" and in_string:
            result.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string:
            if ch == "\n":
                result.append("\\n"); continue
            if ch == "\r":
                result.append("\\r"); continue
            if ch == "\t":
                result.append("\\t"); continue
            if ord(ch) < 0x20:          # autres ctrl chars → supprimer
                continue
        result.append(ch)
    return "".join(result)


def _repair_truncated_json(text: str) -> str:
    """
    Répare un JSON tronqué (réponse LLM coupée à max_tokens).
    Ferme les chaînes, listes et objets ouverts.
    """
    text = text.rstrip().rstrip(',')

    in_string = False
    escape_next = False
    stack = []  # '{' ou '['

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch in ('{', '['):
                stack.append(ch)
            elif ch == '}' and stack and stack[-1] == '{':
                stack.pop()
            elif ch == ']' and stack and stack[-1] == '[':
                stack.pop()

    # Ferme la chaîne ouverte si besoin
    if in_string:
        text += '"'

    # Ferme les structures dans l'ordre inverse
    for opener in reversed(stack):
        text += '}' if opener == '{' else ']'

    return text


# ── OCR Factory ───────────────────────────────────────────────────────────────

def _call_ocr_space(file_path: str) -> str:
    """
    Envoie un fichier image ou PDF à l'API OCR.space et retourne le texte extrait.
    Langue : français + anglais (les documents tunisiens mixent les deux).
    """
    api_key = os.getenv("OCR_SPACE_API_KEY", "helloworld")  # 'helloworld' = clé test limitée

    suffix = Path(file_path).suffix.lower()
    filetype_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".bmp": "image/bmp",
        ".tiff": "image/tiff", ".tif": "image/tiff",
        ".webp": "image/webp", ".pdf": "application/pdf",
    }
    mime = filetype_map.get(suffix, "image/png")

    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                OCR_SPACE_URL,
                files={"file": (Path(file_path).name, f, mime)},
                data={
                    "apikey": api_key,
                    "language": "fre",
                    "isOverlayRequired": False,
                    "OCREngine": 2,       # moteur plus précis
                    "scale": True,
                    "isTable": True,      # préserve la structure des tableaux
                    "detectOrientation": True,
                },
                timeout=60,
            )

        result = response.json()

        if result.get("IsErroredOnProcessing"):
            error_msg = result.get("ErrorMessage") or result.get("ErrorDetails", "Erreur inconnue")
            if isinstance(error_msg, list):
                error_msg = " | ".join(str(m) for m in error_msg)
            return f"Erreur OCR.space : {error_msg}"

        pages_text = [
            page.get("ParsedText", "")
            for page in result.get("ParsedResults", [])
            if page.get("ParsedText")
        ]
        return "\n\n".join(pages_text).strip()

    except requests.exceptions.Timeout:
        return "Erreur OCR.space : timeout (fichier trop lourd ou API lente)"
    except Exception as e:
        return f"Erreur OCR.space : {str(e)}"


def _call_vision_model_fallback(image_base64: str, mime: str, prompt: str) -> str:
    """
    Fallback OCR vision : Groq llama-4-scout → Gemini 2.0-flash / 1.5-flash / 1.5-pro.
    Utilisé seulement si OCR_SPACE_API_KEY est absent ou en erreur.
    """
    errors: list[str] = []

    # ── Groq vision (llama-4-scout multimodal) ────────────────────────────────
    if os.getenv("GROQ_API_KEY"):
        try:
            from openai import OpenAI
            client   = OpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url=GROQ_BASE_URL)
            response = client.chat.completions.create(
                model=GROQ_VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/{mime};base64,{image_base64}"}},
                    ],
                }],
                max_tokens=4096,
            )
            print(f"[OCR-FALLBACK] Groq/{GROQ_VISION_MODEL} ✓")
            return response.choices[0].message.content
        except Exception as e:
            msg = str(e)
            errors.append(f"Groq vision: {msg[:120]}")
            print(f"[OCR-FALLBACK] Groq/{GROQ_VISION_MODEL} → {msg[:120]}")

    # ── Google Gemini vision ──────────────────────────────────────────────────
    if os.getenv("GOOGLE_API_KEY"):
        for gemini_model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
            try:
                import google.generativeai as genai
                from PIL import Image as PILImage
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                gmodel      = genai.GenerativeModel(gemini_model)
                image_bytes = base64.b64decode(image_base64)
                image       = PILImage.open(io.BytesIO(image_bytes))
                result      = gmodel.generate_content([prompt, image]).text
                print(f"[OCR-FALLBACK] Gemini/{gemini_model} ✓")
                return result
            except Exception as e:
                msg = str(e)
                errors.append(f"Gemini/{gemini_model}: {msg[:120]}")
                print(f"[OCR-FALLBACK] Gemini/{gemini_model} → {msg[:120]}")
                continue

    raise EnvironmentError(
        "Aucun modèle vision disponible :\n" + "\n".join(errors)
        if errors else
        "Aucune clé API vision. Ajoutez GOOGLE_API_KEY dans assistant/.env"
    )


# ── Outil 1 : detect_file_type ────────────────────────────────────────────────

@tool
def detect_file_type(file_path: str) -> dict:
    """
    Détecte automatiquement le type du fichier reçu :
      - "pdf_native"  : PDF avec couche texte exploitable (pdfplumber)
      - "pdf_scanned" : PDF scanné (images uniquement, OCR requis)
      - "image"       : fichier image direct (JPG, PNG, TIFF, BMP, WEBP)

    Retourne :
    {
        "file_type": "pdf_native" | "pdf_scanned" | "image" | "unknown",
        "pages": int,
        "extension": str
    }
    """
    import pdfplumber

    path = Path(file_path)
    if not path.exists():
        return {"error": f"Fichier introuvable : {file_path}", "file_type": None}

    suffix = path.suffix.lower()
    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

    if suffix in image_exts:
        return {"file_type": "image", "pages": 1, "extension": suffix}

    if suffix == ".pdf":
        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                has_text = any(
                    len((page.extract_text() or "").strip()) > 50
                    for page in pdf.pages[:2]
                )
                file_type = "pdf_native" if has_text else "pdf_scanned"
                return {"file_type": file_type, "pages": total_pages, "extension": ".pdf"}
        except Exception as e:
            return {"error": str(e), "file_type": None}

    return {"file_type": "unknown", "extension": suffix}


# ── Outil 2 : extract_text_pdf_native ────────────────────────────────────────

@tool
def extract_text_pdf_native(file_path: str) -> str:
    """
    Extrait le texte complet d'un PDF natif (avec couche texte) via pdfplumber.
    Préserve la structure des tableaux (articles, montants, etc.).

    Retourne le texte brut de toutes les pages, formaté avec les tableaux.
    """
    import pdfplumber

    pages_text = []

    try:
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                section = f"\n--- PAGE {i + 1} ---\n"

                text = page.extract_text()
                if text:
                    section += text + "\n"

                tables = page.extract_tables()
                if tables:
                    section += "\n[TABLEAUX]\n"
                    for j, table in enumerate(tables):
                        section += f"\nTableau {j + 1} :\n"
                        for row in table:
                            if row:
                                section += " | ".join(str(cell or "").strip() for cell in row) + "\n"

                pages_text.append(section)

        return "\n".join(pages_text).strip()

    except Exception as e:
        return f"Erreur extraction PDF natif : {str(e)}"


# ── Outil 3 : extract_text_vision ─────────────────────────────────────────────

@tool
def extract_text_vision(image_path: str) -> str:
    """
    Extrait le texte d'une image ou d'un PDF scanné.
    Méthode principale : OCR.space (API REST, gratuite).
    Fallback : Gemini vision ou Groq vision.

    Gère : français, chiffres, tampons, signatures, mentions manuscrites.
    Retourne le texte brut extrait.
    """
    # ── Méthode principale : OCR.space ──
    if os.getenv("OCR_SPACE_API_KEY") or True:  # tente toujours OCR.space en premier
        result = _call_ocr_space(image_path)
        # Si OCR.space retourne du texte valide (pas une erreur), on le renvoie
        if result and not result.startswith("Erreur OCR.space"):
            return result
        # Si erreur OCR.space et pas de clé personnelle → fallback vision LLM
        if not os.getenv("OCR_SPACE_API_KEY"):
            return result  # retourne l'erreur si pas de clé du tout

    # ── Fallback : modèle vision LLM ──
    ocr_prompt = (
        "Tu es un expert OCR spécialisé dans les documents commerciaux tunisiens. "
        "Extrais TOUT le texte visible dans cette image, y compris : "
        "les en-têtes, les tableaux d'articles, les montants, les dates, "
        "les adresses, les emails, les numéros de téléphone, les tampons, "
        "les signatures, les mentions manuscrites, les avertissements et les "
        "mentions légales. Conserve la structure (tableaux en colonnes). "
        "Retourne uniquement le texte extrait, sans explication."
    )

    mime_map = {
        ".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png",
        ".tiff": "tiff", ".tif": "tiff", ".bmp": "bmp", ".webp": "webp",
    }

    suffix = Path(image_path).suffix.lower()

    if suffix == ".pdf":
        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(image_path, dpi=200)
            all_text = ""
            tmpdir = tempfile.gettempdir()

            for i, page_img in enumerate(pages):
                tmp_path = os.path.join(tmpdir, f"_ocr_page_{i + 1}.png")
                page_img.save(tmp_path, "PNG")
                with open(tmp_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                all_text += f"\n--- PAGE {i + 1} ---\n"
                all_text += _call_vision_model_fallback(b64, "png", ocr_prompt) + "\n"
                os.remove(tmp_path)

            return all_text.strip()
        except Exception as e:
            return f"Erreur conversion PDF scanné : {str(e)}"

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    mime = mime_map.get(suffix, "png")
    return _call_vision_model_fallback(b64, mime, ocr_prompt)


# ── Vision LLM direct ────────────────────────────────────────────────────────

def _call_vision_llm(image_path: str, prompt: str) -> str:
    """
    Chaîne vision : HuggingFace Qwen2-VL → Gemini 2.0-flash / 1.5-flash / 1.5-pro
    HF est skipé si 402 (payant) ou 429 (quota).
    """
    mime_map = {
        ".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png",
        ".bmp": "bmp", ".tiff": "tiff", ".tif": "tiff", ".webp": "webp",
    }
    ext  = Path(image_path).suffix.lower()
    mime = mime_map.get(ext, "png")

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    errors: list[str] = []

    # ── HuggingFace vision (rotation compte 1 → compte 2 si 402/429) ─────────
    _hf_tokens = [t for t in [os.getenv("HF_API_KEY"), os.getenv("HF_API_KEY_2")] if t]
    for _idx, _hf_token in enumerate(_hf_tokens, 1):
        try:
            from huggingface_hub import InferenceClient
            client   = InferenceClient(token=_hf_token)
            response = client.chat_completion(
                model=HF_VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/{mime};base64,{b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                max_tokens=4096,
            )
            print(f"[VISION] HuggingFace compte {_idx} ✓")
            return response.choices[0].message.content
        except Exception as e:
            msg = str(e)
            if "402" in msg or "payment" in msg.lower() or "429" in msg or "quota" in msg.lower():
                print(f"[VISION] HuggingFace compte {_idx} indisponible ({msg[:60]}) — compte suivant")
                errors.append(f"HF vision{_idx} skip: {msg[:120]}")
            else:
                raise

    # ── Google Gemini vision (dernier recours) ────────────────────────────────
    if os.getenv("GOOGLE_API_KEY"):
        for gemini_model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
            try:
                import google.generativeai as genai
                from PIL import Image as PILImage
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                gmodel = genai.GenerativeModel(gemini_model)
                image  = PILImage.open(io.BytesIO(base64.b64decode(b64)))
                result = gmodel.generate_content([prompt, image]).text
                print(f"[VISION] Gemini/{gemini_model} ✓")
                return result
            except Exception as e:
                msg = str(e)
                errors.append(f"Gemini vision/{gemini_model}: {msg[:120]}")
                print(f"[VISION] Gemini/{gemini_model} → {msg[:120]}")
                continue

    raise EnvironmentError(
        "Aucun modèle vision disponible :\n" + "\n".join(errors)
        if errors else
        "Aucune clé API vision trouvée. Ajoutez GOOGLE_API_KEY dans assistant/.env"
    )


def _build_extraction_prompt(document_type: str, base_entities: dict) -> str:
    """Construit le prompt d'extraction complet pour le modèle vision."""
    base_keys = list(base_entities.keys()) if base_entities else []
    mode_auto = document_type in ("auto", "") or not base_keys

    if base_keys:
        base_section = f"\nEntités déjà extraites (NE PAS répéter) : {base_keys}\n"
    else:
        base_section = ""

    return f"""Tu es un expert en extraction d'informations sur des documents commerciaux du Maghreb (Tunisie, Maroc, Algérie).
Analyse cette image de document commercial et extrais les données structurées.
{base_section}
━━━ RÈGLE 0 — LECTURE SEULE ━━━
Tu es un LECTEUR, pas un calculateur.
✅ Copie exactement ce qui est écrit dans l'image.
❌ Ne calcule jamais, ne déduis jamais, n'invente jamais.
→ Champ absent = null.

━━━ RÈGLE 0bis — DOCUMENTS BILINGUES FR/AR ━━━
Sur les documents bilingues français/arabe, les deux colonnes disent la MÊME chose.
→ Lis UNIQUEMENT la version FRANÇAISE pour toutes les valeurs numériques et les champs.
→ Ne mélange PAS le texte arabe avec le texte français dans un même champ.
→ Ne copie pas le code-barres, les numéros de série verticaux ou les textes marginaux dans les champs.

━━━ RÈGLE 0ter — NUMERO DE FACTURE ━━━
Le numéro de facture est TOUJOURS un code alphanumérique compact :
  Formats valides : "22FV0324", "A/155200", "FT-230600", "1729/900000", "FAC-2024-001"
  Cherche les libellés : "N° de facture", "Facture N°", "رقم الفاتورة", "Invoice No.", "No."
  La valeur est sur la MÊME LIGNE ou ligne SUIVANTE du libellé — pas dans le bloc d'adresse.
  ❌ JAMAIS copier le libellé lui-même ("Facture N°" est le LIBELLÉ, pas la valeur).
  ❌ JAMAIS une adresse, une ville, un nom de rue ou une entreprise dans ce champ.

━━━ RÈGLE 1 — FOURNISSEUR vs CLIENT ━━━
FOURNISSEUR = entité qui a créé ce document → logo/en-tête à GAUCHE, RC, IF, SIRET, RIB, pied de page.
CLIENT = entité destinataire → bloc encadré (rectangle) souvent à DROITE ou en dessous du header.
  Marqueurs client : "Facturé à", "Destinataire", "Client :", "Adressé à", "Livré à", "Ship to",
                     bloc entouré d'une bordure, position droite de l'en-tête.
  "N° client", "Code client", "N° abonné" = champs CLIENT uniquement.
⚠️ Sur les factures françaises : le fournisseur est en HAUT À GAUCHE, le client est dans un ENCADRÉ À DROITE.
⚠️ Si tu vois deux blocs d'adresse distincts → le bloc encadré/à droite = CLIENT.
⚠️ Un champ "N° client" ne va jamais dans le bloc fournisseur.

━━━ RÈGLE 2 — TABLEAU DES ARTICLES ━━━
Lis visuellement chaque colonne séparément :
  - "quantite"      → colonne QTE / Quantité (nombre simple : 3, 10, 300)
  - "prix_unitaire" → colonne Prix H.T. / P.U.H.T / Prix Uni HT
  - "total_ht"      → colonne Montant H.T. / Total H.T. par ligne
  - "unite"         → colonne U / Unité (M3, KG, U, pièce...)
⚠️ Le N° Série/Lot (ex: 200237-2-00-237) N'EST PAS la quantité.
⚠️ Ne recalcule pas total_ht = quantite × prix_unitaire.

━━━ RÈGLE 3 — SÉPARATEUR DÉCIMAL ━━━
QUATRE conventions coexistent dans les documents du Maghreb :
CAS A — millimes tunisiens simple : UN seul point + EXACTEMENT 3 chiffres → garder tel quel.
  33.529 → 33.529 ✅   2.347 → 2.347 ✅   0.600 → 0.600 ✅
  4.750  → 4.750  ✅  (4 DT 750 millimes — JAMAIS écrire 4750 dans le JSON)
  2.969  → 2.969  ✅  (2 DT 969 millimes — JAMAIS écrire 2969 dans le JSON)
  ❌ JAMAIS convertir 33.529 en 33529 ou 4.750 en 4750
CAS A-ter — ESPACE milliers + POINT millimes :
  1 109.244  → 1109.244  ✅  (1109 DT 244 millimes — JAMAIS 1109244)
  2 500.000  → 2500.000  ✅
  10 250.500 → 10250.500 ✅
  ❌ JAMAIS supprimer le point décimal quand il y a un espace avant
CAS A-quater — ESPACE milliers + VIRGULE décimale (IMPORTANT — F6 style) :
  3 700,000  → 3700.000  ✅  (3700 DT — JAMAIS 3.700 ni 3700000)
  20 754,000 → 20754.000 ✅  (20754 DT — JAMAIS 20.754)
  15 760,000 → 15760.000 ✅
  ⚠️ RÈGLE : espace = séparateur de milliers, virgule = décimal → supprimer espace, remplacer virgule par point
  ❌ ERREUR CRITIQUE : "20 754,000" ne signifie PAS 20.754 — c'est VINGT MILLE SEPT CENT CINQUANTE-QUATRE DINARS
CAS A-bis — DOUBLE POINT milliers+millimes (factures professionnelles tunisiennes) :
  X.XXX.XXX → premier point = séparateur de milliers (supprimer), deuxième = décimal millimes (garder)
  2.345.000 → 2345.000 ✅  (DEUX MILLE TROIS CENT QUARANTE CINQ — JAMAIS 2.345 !)
  1.116.000 → 1116.000 ✅   2.110.500 → 2110.500 ✅   3.780.000 → 3780.000 ✅
  ⚠️ Indice : si Total_HT d'une ligne est ~1000× plus grand que le PU extrait → erreur double point
CAS B — virgule décimale + point/espace milliers :
  82,775 → 82.775 ✅   1.200,50 → 1200.50 ✅   1 833,33 → 1833.33 ✅
Dans le JSON : utilise toujours le POINT comme séparateur décimal.
⚠️ COHÉRENCE : montant_tva doit toujours être < net_a_payer. Si non → erreur de lecture CAS A.

━━━ RÈGLE 4 — MONTANTS GLOBAUX ━━━
Identifie chaque ligne par son libellé :
  "montant_ht"   → "Total HT" / "Total Hors Taxes" / "Base HT" / "Montant HT Avant remises" /
                    "Montant HT" / "المجموع خالي من الأداءات" / "المبلغ بدون أداء قبل الخصم"
  "montant_ht_ar"→ "Montant HT Après remise" / "Total HT A.R." / "المبلغ بدون أداء بعد الخصم"
                    (si égal à montant_ht → les deux peuvent valoir la même chose)
  "montant_tva"  → ligne "TVA XX%" uniquement (pas droit de timbre, pas redevances)
  "tva_rate"     → le pourcentage associé à la ligne TVA (19, 20, 7...)
  "timbre_fiscal"→ "Droit de timbre" / "Droit de timbre sur facture" / "Timbre fiscal" /
                   "TIMBRE FISCAL LOI..." / "طابع جبائي"
                   ⚠️ En Tunisie : timbre_fiscal est TOUJOURS une petite valeur (0.600 à 30 DT max).
                   Si la valeur dépasse 50 DT → ce n'est PAS le timbre, c'est un autre champ → null.
                   ⚠️ "1.000" = 1 DT (CAS A millimes), JAMAIS 1000.
  "net_a_payer"  → "Net à payer" / "Total TTC" / "Total des charges" / "Montant de la facture (TTC)" / "المبلغ الجملي"

⚠️ TAXE FODEC (spécificité tunisienne) :
  Le FODEC (Fonds de Développement de la Compétitivité) est une TAXE de 1%, PAS une remise.
  Libellés : "FODEC", "Fodec", "Fonds de développement"
  → "fodec"          : montant de la ligne FODEC
  → "montant_ht_ar"  : "Total HT A.R." / "Total HT Après Remise" (après déduction de la remise)
  → "net_htva"       : "NET H.TVA" / "NET HT" (= montant_ht_ar + fodec, base de calcul de la TVA)
  ❌ Ne jamais mettre le FODEC dans "remise_globale" — c'est une taxe ajoutée, pas une déduction.
⚠️ Jamais de calcul : copie la valeur imprimée sur la ligne correspondante.

━━━ RÈGLE 5bis — FACTURES DE SERVICES (télécom, électricité, eau, internet) ━━━
Ces factures n'ont PAS de tableau d'articles ligne par ligne → articles = []
Elles ont un RÉCAPITULATIF de lignes nommées — extraire dans les champs globaux :
  "Total Hors Taxes" / "Montant HT Avant remises" / "Montant HT" / "المجموع (خالي من الأداءات)" → montant_ht
  "Montant HT Après remise" / "Total HT A.R."            → montant_ht_ar
  "TVA (X%)"                                              → montant_tva + tva_rate
  "Droit de timbre sur facture" / "Droit de timbre sur les services" → timbre_fiscal
  "Total des charges" / "Montant total de la facture (en DT TTC)"    → net_a_payer
⚠️ NE PAS créer d'articles avec ces lignes — ce sont des champs globaux, pas des produits.

━━━ RÈGLE 5ter — DOCUMENTS BILINGUES FR/AR ━━━
L'arabe est une TRADUCTION du français — les deux colonnes disent la même chose.
→ Lis UNIQUEMENT la version FRANÇAISE pour les valeurs numériques.
→ Ne pas mélanger ou dupliquer le texte arabe dans les champs du JSON.
→ Sur une facture bilingues FR/AR, le layout gauche=français et droite=arabe (ou inverse).

━━━ RÈGLE 6 — DÉTECTION TYPE ━━━
{"facture" if not mode_auto else ""}{"" if not mode_auto else '''Identifie le type :
  → "facture"          : vois "Facture", TVA, articles, montant TTC
  → "lettre_de_change" : vois "Lettre de change", "tiré", "tireur", "domiciliation"'''}

━━━ FORMAT DE SORTIE ━━━
Retourne UNIQUEMENT un objet JSON valide. Pas de markdown (```), pas d'explication.

Pour une FACTURE :
{{"_document_type":"facture","articles":[{{"designation":"...","quantite":...,"unite":"...","prix_unitaire":...,"total_ht":...}}],"montant_ht":...,"montant_tva":...,"tva_rate":...,"timbre_fiscal":...,"net_a_payer":...,"date_echeance":null,"mode_paiement":null,"reference_bancaire":null,"email_fournisseur":null,"email_client":null,"telephone_fournisseur":null,"telephone_client":null,"adresse_fournisseur":null,"adresse_client":null,"matricule_fiscal_fournisseur":null,"matricule_fiscal_client":null,"tampon_present":null,"signature_presente":null,"remarques_manuscrites":null,"mentions_legales":null,"reference_commande":null,"bon_livraison":null}}

Pour une LETTRE DE CHANGE :
{{"_document_type":"lettre_de_change","date_creation":null,"lieu_paiement":null,"lieu_creation":null,"banque_domiciliataire":null,"rib_tire":null,"endossements":[],"aval_bancaire":null,"aval_details":null,"date_acceptance":null,"date_presentation":null,"telephone_tire":null,"telephone_tireur":null,"email_tire":null,"email_tireur":null,"adresse_tire":null,"adresse_tireur":null,"tampon_present":null,"signature_presente":null,"remarques_manuscrites":null,"mentions_legales":null}}

JSON :"""


# ── Outil 5 : extract_entities_from_image ────────────────────────────────────

@tool
def extract_entities_from_image(
    image_path: str,
    document_type: str,
    base_entities_json: str,
) -> str:
    """
    Extrait directement les entités structurées depuis une image de document commercial.
    Utilise Qwen2-VL-7B qui VOIT visuellement les colonnes du tableau.
    → Résout la confusion de colonnes des tableaux à layouts variés.

    Paramètres :
      image_path         : chemin vers l'image (JPG, PNG, TIFF, WEBP)
      document_type      : "facture" | "lettre_de_change" | "auto"
      base_entities_json : JSON des entités déjà extraites (peut être "{}")

    Retourne un JSON string des entités extraites directement depuis l'image.
    """
    try:
        base = json.loads(base_entities_json) if base_entities_json else {}
    except Exception:
        base = {}

    prompt = _build_extraction_prompt(document_type, base)

    # PDF scanné : convertir chaque page en image
    suffix = Path(image_path).suffix.lower()
    if suffix == ".pdf":
        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(image_path, dpi=200)
            tmpdir = tempfile.gettempdir()
            all_results = []

            for i, page_img in enumerate(pages):
                tmp_path = os.path.join(tmpdir, f"_vision_page_{i + 1}.png")
                page_img.save(tmp_path, "PNG")
                try:
                    page_result = _call_vision_llm(tmp_path, prompt)
                    all_results.append(page_result)
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

            # Pour un PDF multi-pages : retourne la première page (page principale)
            content = all_results[0] if all_results else "{}"
        except Exception as e:
            return json.dumps({"error": f"Erreur conversion PDF : {str(e)}"}, ensure_ascii=False)
    else:
        content = _call_vision_llm(image_path, prompt)

    # Nettoyage et parsing JSON
    content = content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    content = _sanitize_llm_json(content)

    try:
        parsed = json.loads(content)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        repaired = _repair_truncated_json(content)
        try:
            parsed = json.loads(repaired)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            return json.dumps({"error": "JSON invalide", "raw": content[:300]}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ── Outil 4 : extract_visual_fields ──────────────────────────────────────────

@tool
def extract_visual_fields(image_path: str, document_type: str = "auto") -> str:
    """
    Analyse visuelle directe via Gemini Vision (Section II — Gouvernance).
    Détecte les éléments que l'OCR texte ne peut pas capturer :
      - Tampons / cachets humides (ronds, ovales, rectangulaires)
      - Signatures manuscrites (du tiré, du tireur, du fournisseur)
      - Annotations et notes manuscrites (texte griffonné à la main)
      - État du document (original, duplicata, copie, endommagé)
      - Présence et lisibilité du logo de l'entreprise
      - Aval bancaire (case cochée ou tampon dans la zone Aval)

    Retourne un JSON string avec uniquement les champs visuels.
    """
    is_traite = "lettre" in document_type.lower() or "change" in document_type.lower()

    if is_traite:
        champs_json = """{
  "cachet_present": true/false,
  "signature_tire": true/false,
  "signature_tireur": true/false,
  "aval_bancaire": true/false,
  "aval_details": "texte dans la case Aval si remplie, sinon null",
  "notes_manuscrites": "tout texte manuscrit visible (montant en lettres, annotations, etc.)",
  "etat_document": "original | duplicata | copie | endommagé",
  "banque_domiciliataire": "texte dans la zone Domiciliation (nom banque + agence), sinon null",
  "nom_adresse_tire": "texte dans la zone Nom et adresse du Tiré, sinon null"
}"""
        instructions_specifiques = """
- "signature_tire"       : la zone "Signature du tiré / إمضاء المسحوب عليه" (gauche) contient-elle une signature ou tampon ?
- "signature_tireur"     : la zone "Signature du tireur / توقيع الساحب" (droite bas) contient-elle une signature ou tampon ?
- "aval_bancaire"        : la case "Aval / الكفالة" est-elle remplie, tamponnée ou cochée ? (true même si c'est un tampon)
- "cachet_present"       : compte tous les tampons ronds/ovaux sur le document (true dès qu'il y en a 1)
- "banque_domiciliataire": lis le texte dans la zone "Domiciliation / اسم وعنوان الفرع"
- "nom_adresse_tire"     : lis le texte dans la zone "Nom et adresse du Tiré / اسم وعنوان المسحوب عليه"
- "notes_manuscrites"    : lis le "Montant en lettres" manuscrit et toute autre annotation à la main"""
        etape_articles = ""
        max_tok = 1024
    else:
        champs_json = """{
  "cachet_present": true/false,
  "signature_presente": true/false,
  "notes_manuscrites": "texte écrit à la main visible (hors champs imprimés), sinon null",
  "etat_document": "original | duplicata | copie | endommagé",
  "logo_detecte": true/false,
  "logo_nom": "nom lisible dans le logo ou null",
  "articles": [
    {
      "designation"     : "texte exact de la colonne Désignation/Description",
      "quantite"        : null,
      "unite"           : "M2 / KG / U / pièce / null",
      "prix_unitaire_ht": null,
      "remise_pct_ligne": null,
      "tva_rate_ligne"  : "19% / 7% / 13% / null",
      "total_ht_ligne"  : null
    }
  ]
}"""
        instructions_specifiques = """
- "signature_presente" : y a-t-il un paraphe, une signature manuscrite ou un tampon dans la zone signature ?
- "cachet_present"     : y a-t-il un tampon humide (rond, ovale, rectangulaire) visible sur le document ?
- "logo_nom"           : si un logo d'entreprise est visible en haut, quel est le nom lisible ?"""
        etape_articles = """
━━━ ÉTAPE 5 : TABLEAU DES ARTICLES ━━━
Cherche un tableau avec colonnes : N° | Désignation | QTE | Prix U.HT | TVA% | Montant HT
(les noms de colonnes varient, mais l'ordre est typiquement ce schéma)

RÈGLE FONDAMENTALE — LIS CHAQUE COLONNE INDÉPENDAMMENT :
  • Identifie d'abord la ligne d'en-tête (noms des colonnes)
  • Pour chaque ligne d'article, lis la valeur de CHAQUE colonne en restant dans sa bande verticale
  • "quantite"        → colonne QTE / Qté / Quantité — toujours un nombre ENTIER ou simple (3, 10, 300)
  • "prix_unitaire_ht"→ colonne P.U.H.T / Prix U.HT — UNIQUEMENT si la colonne est explicitement "HT"
  • "total_ht_ligne"  → colonne Montant HT / Total H.T. — UNIQUEMENT si la colonne est explicitement "HT"

⚠️ PIÈGE CRITIQUE — COLONNE "PU TTC" OU "PRIX TTC" :
  Certaines factures (revendeurs, distributeurs) affichent le PRIX TTC dans la colonne prix.
  Vérifie l'en-tête de la colonne : si elle dit "PU TTC", "Prix TTC", "P.U. TTC" :
  → prix_unitaire_ht = null   (prix TTC ≠ prix HT)
  → total_ht_ligne = null     (montant TTC ≠ montant HT)
  → montant_ht = extraire depuis le bas de la facture ("TOTAL HT" / "Base HT")
  ❌ JAMAIS mettre un prix TTC dans prix_unitaire_ht ou total_ht_ligne.

⚠️ AUTRES PIÈGES VISUELS :
  - La colonne QTE et la colonne P.U.H.T sont côte à côte → regarde l'en-tête pour identifier laquelle est QTE
  - Un N° série/lot (ex: 200237-2) dans une colonne ≠ quantité — la quantité est dans la colonne étiquetée QTE
  - Si le document est une facture de SERVICES (téléphone, internet, électricité, eau) sans tableau d'articles → articles = []

⚠️ PIÈGE CRITIQUE — NE JAMAIS DÉCALER LES LIGNES :
  Quand une désignation est longue ou tient sur 2 lignes, les valeurs QTE/P.U.H.T/%RM/TVA/Montant HT
  de CETTE MÊME ligne sont souvent imprimées plus bas, alignées avec le BAS du bloc texte, pas avec le haut.
  → Repère d'abord la ligne horizontale (ou l'espacement) qui sépare chaque article, puis associe à
    CHAQUE désignation les valeurs numériques comprises dans SA bande horizontale — jamais celles de
    l'article suivant ou précédent.
  → Avant de répondre, vérifie pour chaque ligne : quantite × prix_unitaire_ht × (1 - remise/100) ≈ total_ht_ligne.
    Si l'écart est grand, c'est probablement un décalage de ligne → relis le tableau ligne par ligne.

⚠️ COLONNE REMISE (%RM) — NE JAMAIS L'OMETTRE :
  Si une colonne "%RM", "Remise", "Rem." ou "%" existe entre P.U.H.T et TVA, lis sa valeur pour CHAQUE ligne
  et mets-la dans "remise_pct_ligne" (nombre, ex: 10 pour 10%, 0 si la cellule est vide ou affiche "0").
  Ne mets "remise_pct_ligne": null QUE si la colonne n'existe pas du tout dans le tableau.

NOTATION MILLIMES TUNISIENS :
  - Prix avec POINT + 3 chiffres = millimes (4.987 = 4 DT 987 millimes → garder 4.987, jamais 4987)
  - Quantité entière : 8 → 8, jamais 8.000"""
        max_tok = 4096

    prompt = f"""Tu es un expert en analyse visuelle de documents officiels.
Regarde ATTENTIVEMENT chaque zone de cette image — ne lis pas le texte imprimé, regarde les éléments graphiques.

━━━ ÉTAPE 1 : DÉTECTION DES TAMPONS (CACHETS) ━━━
Un tampon (cachet humide) se reconnaît à :
  • Une forme circulaire, ovale ou rectangulaire avec du texte à l'intérieur
  • De l'encre bleue, rouge ou noire déposée sur le papier (pas imprimée)
  • Un bord légèrement irrégulier ou flou (contrairement au texte imprimé net)
  • Il peut y en avoir plusieurs sur le même document
→ Regarde dans TOUS les coins et sur tout le document.
→ cachet_present = true dès qu'il y en a AU MOINS UN visible.

━━━ ÉTAPE 2 : DÉTECTION DES SIGNATURES ━━━
Une signature se reconnaît à :
  • Un tracé manuscrit cursif ou un paraphe (même illisible)
  • Un tampon dans une zone "Signature" vaut pour une signature
  • Une case "Signature du tiré" remplie = signature_tire true
  • Une case "Signature du tireur" remplie = signature_tireur true

━━━ ÉTAPE 3 : AVAL BANCAIRE ━━━
  • Cherche la zone étiquetée "Aval" ou "الكفالة"
  • aval_bancaire = true si cette zone contient un tampon, une signature ou tout texte manuscrit

━━━ ÉTAPE 4 : NOTES MANUSCRITES ━━━
  • Tout texte écrit à la main (pas imprimé) — montants en lettres, annotations, dates griffonnées
  • Copie le texte tel quel
{etape_articles}

━━━ FORMAT DE SORTIE ━━━
Retourne UNIQUEMENT ce JSON (sans markdown, sans explication) :
{champs_json}

JSON :"""

    # ── Appel Vision (Groq llama-4-scout en priorité, Gemini en fallback) ───────
    api_key = os.getenv("GOOGLE_API_KEY")  # Gemini (optionnel)

    if not os.getenv("GROQ_API_KEY") and not api_key:
        return json.dumps({"error": "Aucune clé API vision (GROQ_API_KEY ou GOOGLE_API_KEY)"}, ensure_ascii=False)

    content = ""
    last_error = ""
    _tmp_pdf_image: str | None = None

    try:
        import base64

        ext = Path(image_path).suffix.lower()

        # PDF (natif ou scanné) : extract_visual_fields n'a aucun lecteur PDF natif —
        # on convertit la 1ère page en PNG, comme extract_text_vision() le fait déjà.
        # Limite connue : pour un PDF multi-pages, seule la page 1 est analysée
        # visuellement (signatures/cachets/articles habituellement sur la 1ère page
        # pour les factures/lettres de change tunisiennes, qui sont en général
        # mono-page).
        if ext == ".pdf":
            from pdf2image import convert_from_path
            pages = convert_from_path(image_path, dpi=200)
            if pages:
                _tmp_pdf_image = os.path.join(
                    tempfile.gettempdir(), f"_visual_pdf_{os.getpid()}_{id(pages)}.png"
                )
                pages[0].save(_tmp_pdf_image, "PNG")
                image_path = _tmp_pdf_image
                ext = ".png"

        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png",  ".bmp": "image/bmp",
            ".tiff": "image/tiff", ".tif": "image/tiff",
            ".webp": "image/webp",
        }
        mime_type = mime_map.get(ext, "image/jpeg")

        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        image_url_data = f"data:{mime_type};base64,{image_b64}"

        # ── 1. Groq Vision (llama-4-scout — multimodal, clé déjà fonctionnelle) ──
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                from openai import OpenAI as GroqClient
                client = GroqClient(api_key=groq_key, base_url=GROQ_BASE_URL)
                resp = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url_data}},
                        ],
                    }],
                    max_tokens=max_tok,
                    temperature=0,
                )
                content = resp.choices[0].message.content.strip()
                print(f"[VISUAL] Modèle utilisé : llama-4-scout (Groq)")
            except Exception as e:
                last_error = str(e)
                print(f"[VISUAL] Groq vision → {last_error[:150]}")

        # ── 2. Fallback : Gemini via LangChain ───────────────────────────────────
        if not content:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage
            for model_name in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
                try:
                    llm = ChatGoogleGenerativeAI(
                        model=model_name, google_api_key=api_key,
                        temperature=0, max_tokens=max_tok,
                    )
                    msg = HumanMessage(content=[
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url_data}},
                    ])
                    content = llm.invoke([msg]).content.strip()
                    print(f"[VISUAL] Modèle utilisé : {model_name} (Gemini fallback)")
                    break
                except Exception as e:
                    last_error = str(e)
                    print(f"[VISUAL] {model_name} → {last_error[:120]}")
                    continue

        if not content:
            return json.dumps({"error": f"Aucun modèle vision disponible : {last_error[:200]}"}, ensure_ascii=False)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        content = _sanitize_llm_json(content)
        parsed = json.loads(content)
        print(f"[VISUAL] Champs visuels détectés : {parsed}")
        return json.dumps(parsed, ensure_ascii=False, indent=2)

    except json.JSONDecodeError as e:
        return json.dumps({"error": f"JSON invalide : {e}", "raw": content[:300]}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Erreur vision : {str(e)}"}, ensure_ascii=False)
    finally:
        if _tmp_pdf_image and os.path.exists(_tmp_pdf_image):
            os.remove(_tmp_pdf_image)


# ── Outil 5 : extract_augmented_entities ─────────────────────────────────────

@tool
def extract_augmented_entities(
    raw_text: str,
    base_entities_json: str,
    document_type: str,
) -> str:
    """
    Extrait les entités supplémentaires (augmentation) non capturées par le modèle fine-tuné.
    Utilise Mistral AI (gratuit) pour l'extraction intelligente.

    Paramètres :
      raw_text           : texte brut extrait par les outils 2 ou 3
      base_entities_json : JSON (string) des entités déjà extraites par le fine-tuné
      document_type      : "facture" | "lettre_de_change" | "auto"

    Retourne un JSON string des entités augmentées uniquement
    (ne répète pas ce qui est déjà dans base_entities_json).

    ── Pour une FACTURE, extrait :
       articles, montant_ht, tva_rate, montant_tva, timbre_fiscal,
       date_echeance, mode_paiement, reference_bancaire,
       email_fournisseur, email_client, telephone_fournisseur, telephone_client,
       adresse_fournisseur, adresse_client,
       matricule_fiscal_fournisseur, matricule_fiscal_client,
       tampon_present, signature_presente,
       remarques_manuscrites, mentions_legales,
       reference_commande, bon_livraison

    ── Pour une LETTRE DE CHANGE, extrait :
       date_creation, lieu_paiement, lieu_creation,
       banque_domiciliataire, rib_tire,
       endossements, aval_bancaire, aval_details,
       date_acceptance, date_presentation,
       telephone_tire, telephone_tireur, email_tire, email_tireur,
       adresse_tire, adresse_tireur,
       tampon_present, signature_presente,
       remarques_manuscrites, mentions_legales
    """
    try:
        base = json.loads(base_entities_json) if isinstance(base_entities_json, str) else base_entities_json
        base_keys = list(base.keys()) if base else []
    except Exception:
        base = {}
        base_keys = []

    doc_upper = (document_type or "auto").upper()
    mode_auto = doc_upper in ("AUTO", "") or not base_keys

    # ── Schémas JSON des deux types de documents ─────────────────────────────
    # Le GLM principal extrait déjà : fournisseur nom, client nom, date, numéro,
    # montant TTC (factures) ; tiré, tireur, montant, RIB, domiciliation (traites).
    # L'agent extrait TOUT LE RESTE — organisé en 3 sections.

    schema_facture = """{
  "_document_type": "facture",

  // ── I. ARTICLES & TAXES ───────────────────────────────────────────────────
  "articles": [
    {
      "designation"     : "texte exact de la colonne Désignation",
      "quantite"        : null,
      "unite"           : "M2 / KG / U / pièce / etc.",
      "prix_unitaire_ht": null,
      "remise_pct_ligne": null,
      "tva_rate_ligne"  : "19% / 7% / 13% / exonéré",
      "total_ht_ligne"  : null
    }
  ],
  "numero_facture"     : "cherche 'N° de facture', 'Facture N°', 'رقم الفاتورة', 'Invoice No.', 'No.' — copie la valeur ALPHANUMÉRIQUE compacte qui SUIT le libellé (ex: 22FV0324, A/155200, FT-230600, 1729/900000). ❌ JAMAIS copier le libellé lui-même ('Facture N°' n'est PAS un numéro). ❌ JAMAIS une adresse, un nom de ville ou de rue.",
  "montant_ht"         : null,
  "remise_globale"     : null,
  "montant_ht_ar"      : null,
  "fodec"              : null,
  "net_htva"           : null,
  "montant_tva"        : null,
  "tva_rate"           : "taux TVA global du pied de facture (ex: 19, 20, 7 — jamais de % ni de texte)",
  "timbre_fiscal"      : null,
  "net_a_payer"        : "valeur NUMÉRIQUE du montant total TTC (Net à payer / Total TTC / TOTAL A PAYER)",
  "net_a_payer_lettres": "COPIE MOT POUR MOT le texte 'en toutes lettres' tel qu'il est écrit dans le document — null si absent. RÈGLE ABSOLUE : garde la devise EXACTE du document (DINARS, DOLLARS, EUROS, DIRHAMS...) sans jamais la changer. NE PAS INVENTER, NE PAS CONVERTIR un nombre en lettres.",

  // ── II. VISUEL & SÉCURITÉ ─────────────────────────────────────────────────
  "cachet_present"     : true/false,
  "signature_presente" : true/false,
  "notes_manuscrites"  : "texte griffonné à la main (ex: Payé par chèque le...)",
  "logo_detecte"       : true/false,

  // ── III. PAIEMENT & LOGISTIQUE ────────────────────────────────────────────
  "mode_reglement"              : "UN SEUL mode explicitement indiqué (Virement, Chèque, Traite, Espèces, Comptant). Si le document liste plusieurs modes séparés par '/' ou des puces sans cocher l'un d'eux → null",
  "date_echeance"               : "DD/MM/YYYY",
  "email_fournisseur"           : null,
  "telephone_fournisseur"       : null,
  "adresse_fournisseur"         : null,
  "matricule_fiscal_fournisseur": null,
  "email_client"                : null,
  "telephone_client"            : null,
  "adresse_client"              : null,
  "matricule_fiscal_client"     : null,
  "reference_commande"          : null,
  "reference_bon_livraison"     : null
}"""

    schema_lettre = """{
  "_document_type": "lettre_de_change",

  // ── I. FINANCIER ──────────────────────────────────────────────────────────
  "montant_en_lettres" : "montant manuscrit en toutes lettres — vérifié contre le montant numérique (voir RÈGLE 6)",

  // ── II. VISUEL & SÉCURITÉ ─────────────────────────────────────────────────
  "signature_tire"     : true/false,
  "signature_tireur"   : true/false,
  "cachet_present"     : true/false,
  "aval_bancaire"      : true/false,
  "aval_details"       : "banque avaliste, date, conditions",
  "notes_manuscrites"  : "annotations manuscrites visibles",

  // ── III. LOGISTIQUE ───────────────────────────────────────────────────────
  "lieu_creation"         : "ville où la lettre a été créée",
  "lieu_paiement"         : "ville où elle doit être payée",
  "banque_domiciliataire" : null,
  "rib_tire"              : null,
  "date_acceptance"       : "DD/MM/YYYY",
  "date_presentation"     : "DD/MM/YYYY",
  "endossements"          : [{"endosseur": null, "date": null, "montant": null}],
  "telephone_tire"        : null,
  "telephone_tireur"      : null,
  "email_tire"            : null,
  "email_tireur"          : null,
  "adresse_tire"          : null,
  "adresse_tireur"        : null,
  "reference_commande"    : null,
  "mode_reglement"        : null
}"""

    # ── Construction du contexte ──────────────────────────────────────────────
    if mode_auto:
        type_instruction = """ÉTAPE 1 — TYPE DE DOCUMENT
Identifie le type en cherchant ces mots-clés exacts :
  → "facture", "FACTURE", "Facture"                    = "facture"
  → "lettre de change", "traite", "tiré", "tireur"    = "lettre_de_change"
"""
        schema_a_utiliser = f"FACTURE :\n{schema_facture}\n\nLETTRE DE CHANGE :\n{schema_lettre}"
    elif "FACTURE" in doc_upper:
        type_instruction = 'Type confirmé : "facture".\n'
        schema_a_utiliser = schema_facture
    else:
        type_instruction = 'Type confirmé : "lettre_de_change".\n'
        schema_a_utiliser = schema_lettre

    # Valeur numérique du montant déjà extraite par le modèle principal (pour cross-check
    # avec le montant manuscrit en lettres — voir RÈGLE 6 plus bas)
    montant_connu = (
        base.get("MONTANT") or base.get("montant")
        or base.get("MONTANT_TTC") or base.get("montant_ttc")
    )
    montant_connu_section = (
        f"\nMontant déjà lu par le modèle principal dans la case imprimée : {montant_connu}\n"
        if montant_connu else ""
    )

    # ── Prompt expert ────────────────────────────────────────────────────────
    prompt = f"""Tu es un expert en analyse contextuelle de documents commerciaux du Maghreb (Tunisie, Maroc, Algérie).
Tu reçois le texte brut produit par un OCR et tu extrais les données structurées détaillées.

CONTEXTE : Un modèle principal a déjà extrait les champs basiques (fournisseur nom, client nom, date, numéro, montant TTC pour les factures ; tiré, tireur, montant, RIB pour les traites).{montant_connu_section}
TON RÔLE : Extraire tout le reste — les détails des articles, les taxes, les éléments visuels, les coordonnées, les références logistiques.

═══════════════════════════════════════════
TEXTE BRUT EXTRAIT PAR OCR :
═══════════════════════════════════════════
{raw_text}
═══════════════════════════════════════════

{type_instruction}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLE 0 — LECTURE SEULE + ANTI-HALLUCINATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tu es un LECTEUR, pas un calculateur.
✅ Copie exactement ce qui est écrit dans le texte OCR.
❌ N'effectue AUCUN calcul (pas de somme, pas de produit, pas de déduction).
❌ N'invente AUCUNE valeur absente du texte.
❌ Ne complète pas un champ par logique ou estimation.
→ Si un champ n'est pas explicitement écrit dans le texte : retourne null.

⚠️ RÈGLE ANTI-HALLUCINATION ARTICLES :
   Si aucun vrai tableau Désignation/Quantité/Prix n'est visible → articles = []
   Les notes manuscrites, codes paiement, tampons ne sont JAMAIS des articles.
   Si la seule ligne "article" a un total = net_a_payer → c'est un résumé global, pas un article → articles = []

⚠️ RÈGLE ANTI-HALLUCINATION ABSOLUE pour les montants globaux :
   Les champs "net_a_payer", "montant_ht", "montant_tva" ne doivent être remplis
   QUE si un bloc "Total / Net à payer / Montant TTC" est EXPLICITEMENT présent dans le texte.
   Si ce bloc est absent (document coupé, page incomplète) → retourne null pour ces 3 champs.
   Si tu vois un nombre avec des chiffres répétitifs (333333, 111111, 999999...)
   → c'est une erreur OCR, retourne null.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLE 6bis — MATRICULE FISCAL (SPÉCIFICITÉ TUNISIENNE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Le matricule fiscal tunisien a ce format exact : XXXXXXXL/L/000
  Ex: 1234567A/M/000   7654321B/A/000   0123456B/P/000
Cherche les libellés : "MF:", "M.F:", "Matricule Fiscal:", "Mat. Fisc."
  → "matricule_fiscal_fournisseur" : MF dans le bloc fournisseur (en-tête/pied de page)
  → "matricule_fiscal_client"      : MF dans le bloc client
Pour les factures françaises/européennes : SIRET (14 chiffres), TVA intracommunautaire (FR + 11 chiffres)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLE 1 — IDENTIFIER FOURNISSEUR vs CLIENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Utilise la SÉMANTIQUE des champs, pas leur position dans la page.

FOURNISSEUR = l'entité qui a créé et signé ce document.
  Indices universels : logo en HAUT À GAUCHE, en-tête gauche, pied de page, RC/IF/ICE/SIRET, RIB.
  Si l'OCR a mal lu le logo : cherche le nom dans le pied de page ou les mentions légales.

CLIENT = l'entité à qui est adressé ce document.
  Indices universels : bloc "Facturé à" / "Client :" / "Destinataire" / "votre compte" /
  "Adressé à" / encadré (rectangle avec bordure) / position DROITE ou bas de l'en-tête.

RÈGLE LAYOUT FRANÇAIS (très fréquent) :
  Sur une facture française standard :
    → Bloc GAUCHE sans bordure = FOURNISSEUR (émetteur)
    → Bloc DROIT avec bordure/encadré = CLIENT (destinataire)
  Si tu vois deux adresses distinctes, la seconde (encadrée ou à droite) = CLIENT.

RÈGLE DE SÉPARATION DES CHAMPS :
  Les champs suivants appartiennent TOUJOURS au CLIENT :
    "N° client", "Code client", "N° compte client", "N° abonné", "votre N° de contrat"
  Les champs suivants appartiennent TOUJOURS au fournisseur :
    RC, IF, ICE, SIRET (identifiant fiscal), RIB fournisseur, email société, téléphone société

⚠️ adresse_client et adresse_fournisseur doivent contenir UNIQUEMENT des adresses postales.
   ❌ JAMAIS de données d'articles (désignations, codes barres, références produit) dans ces champs.
   ❌ JAMAIS de coordonnées GPS (ex: 35.794...,10.586...) dans ces champs.
⚠️ Ne jamais mettre l'adresse du CLIENT dans adresse_fournisseur et vice-versa.
⚠️ Si les deux adresses sont dans des villes différentes → c'est normal, elles sont distinctes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLE 2 — TABLEAU DES ARTICLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Le tableau a souvent ces colonnes dans cet ordre :
  Code/Ref | N° BL | Désignation | N° Série/Lot | Quantité | Prix Unitaire HT | %RM | TVA% | Montant HT

Pour chaque article extrais :
  "designation"      → colonne "Désignation" ou "Description" — le nom du produit uniquement
  "quantite"         → colonne "QTE", "Qté", "Quantité" — un nombre entier ou décimal simple
  "prix_unitaire_ht" → colonne "P.U.H.T", "Prix Uni HT", "P.U.V.HT" — prix sans taxes
  "remise_pct_ligne" → colonne "%RM", "Remise", "Rem." — nombre (10 pour 10%), 0 si vide/0, null UNIQUEMENT
                        si cette colonne n'existe pas du tout dans le tableau
  "tva_rate_ligne"   → colonne "TVA%", "Taux TVA"
  "total_ht_ligne"   → colonne "Montant HT", "Total HT" par ligne — copie tel quel

⚠️ PIÈGES FRÉQUENTS dans les tableaux :
  ❌ Le N° Série/Lot (ex: "200237-2-00-237") N'EST PAS la quantité → quantite = colonne QTE
  ❌ Le N° BL (ex: "CB216296") N'EST PAS la désignation → désignation = nom du produit
  ❌ Ne recalcule pas total_ht_ligne = quantite × prix_unitaire_ht → copie la colonne
  ❌ N'OMETS JAMAIS la colonne %RM — une remise ignorée fausse tout le calcul d'audit en aval
  ✅ Si une ligne ne contient que le N° série sur plusieurs sous-lignes, c'est une seule ligne d'article

⚠️ NE JAMAIS DÉCALER LES LIGNES : quand une désignation est longue ou coupée sur 2 lignes dans le texte OCR,
   les valeurs numériques (QTE/PU/%RM/TVA/Montant HT) qui suivent appartiennent à CETTE désignation, pas à
   la suivante. Avant de répondre, vérifie pour chaque ligne : quantite × prix_unitaire_ht × (1 - remise/100)
   ≈ total_ht_ligne — si l'écart est important, relis le tableau, une ligne est probablement décalée.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLE 3 — SÉPARATEUR DÉCIMAL (TRÈS IMPORTANT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dans les documents tunisiens, marocains et algériens, TROIS conventions coexistent :

CAS A — notation en millimes tunisiens (3 décimales avec point) :
  → Un SEUL point + EXACTEMENT 3 chiffres = décimales en millimes → garder tel quel
  33.529   → 33.529    ✅  (33 DT et 529 millimes)
  2.347    → 2.347     ✅
  0.600    → 0.600     ✅  (timbre fiscal)
  4.750    → 4.750     ✅  (4 DT 750 millimes — JAMAIS 4750)
  2.969    → 2.969     ✅  (2 DT 969 millimes — JAMAIS 2969)
  ❌ ERREUR CRITIQUE À ÉVITER : NE JAMAIS lire "4.750" comme "4 750" (quatre mille sept cent cinquante)
  ❌ ERREUR CRITIQUE À ÉVITER : NE JAMAIS supprimer le point et écrire 4750 ou 2969 dans le JSON
  → La règle est simple : si le nombre ne dépasse pas logiquement le contexte (TVA < TTC, Timbre < 50 DT), c'est CAS A.

CAS A-ter — ESPACE milliers + POINT millimes (format "1 109.244") :
  1 109.244  → 1109.244  ✅  (mille cent neuf DT et 244 millimes — JAMAIS 1109244)
  2 500.000  → 2500.000  ✅
  10 250.500 → 10250.500 ✅
  ❌ JAMAIS supprimer le point décimal : "1 109.244" → 1109244 est une ERREUR GRAVE

CAS A-quater — ESPACE milliers + VIRGULE décimale (format "3 700,000") :
  → Même logique que A-ter mais avec une VIRGULE au lieu d'un point
  3 700,000  → 3700.000  ✅  (trois mille sept cents DT — JAMAIS 3.700 ni 3700000)
  20 754,000 → 20754.000 ✅  (vingt mille sept cent cinquante-quatre DT — JAMAIS 20.754)
  15 760,000 → 15760.000 ✅
  ❌ ERREUR CRITIQUE : "20 754,000" → 20.754 est FAUX — c'est 20 754 DT, pas vingt dinars !
  → Règle : supprimer l'espace, remplacer la virgule par un point → écrire l'entier avec millimes

CAS A-bis — DOUBLE POINT : séparateur de milliers + millimes (fréquent sur factures tunisiennes professionnelles) :
  X.XXX.XXX → le PREMIER point est un séparateur de milliers → le supprimer
              le DEUXIÈME point + 3 chiffres = millimes → garder
  2.345.000  → 2345.000  ✅  (deux mille trois cent quarante-cinq DT — JAMAIS 2.345)
  1.116.000  → 1116.000  ✅  (mille cent seize DT — JAMAIS 1.116)
  2.110.500  → 2110.500  ✅
  3.780.000  → 3780.000  ✅
  ⚠️ RÈGLE CLEF : si tu vois X.XXX.XXX dans une colonne de prix → c'est X milliers, pas X dinars !
  ⚠️ Vérifie la cohérence : si QTE=1 et PU=2.345 mais Total=2110, alors PU=2345.000 (double point)

CAS B — virgule décimale (2 décimales) + point/espace milliers :
  → VIRGULE "," est le séparateur décimal → convertis en point dans le JSON
  → POINT "." avant une virgule = séparateur de milliers → supprime
  82,775   → 82.775    ✅
  1.200,50 → 1200.50   ✅  (point=milliers car suivi d'une virgule)
  1 200,50 → 1200.50   ✅  (espace=milliers)
  10 500,00→ 10500.00  ✅

⚠️ RÈGLE CLÉ : Un point suivi d'EXACTEMENT 3 chiffres en fin de nombre = millimes → GARDER.
⚠️ JAMAIS supprimer ou ignorer les décimales d'un montant.
⚠️ Dans le JSON final, utilise TOUJOURS le point comme séparateur décimal.
⚠️ VÉRIFICATION DE COHÉRENCE : montant_tva doit toujours être < net_a_payer. Si montant_tva > net_a_payer → tu as fait une erreur de lecture → relis CAS A.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLE 4 — MONTANTS GLOBAUX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Identifie chaque ligne par son LIBELLÉ exact — ne confonds pas les lignes :

  "montant_ht"    → libellé : "Total HT", "Total Hors Taxes", "Total Hors TVA",
                               "المجموع خالي من الأداءات", "Sous-total HT", "Base HT"
  "montant_tva"   → libellé : "TVA", "Montant TVA", "T.V.A", suivi du taux (ex: "TVA 19%")
                               ⚠️ PAS le droit de timbre, PAS les redevances
  "tva_rate"      → cherche "19%", "20%", "7%" associé à la ligne TVA uniquement
  "timbre_fiscal" → libellés reconnus : "Droit de timbre", "Droit de timbre sur facture",
                               "Timbre fiscal", "Timbre", "طابع جبائي",
                               "TIMBRE FISCAL LOI..." (texte légal long → prendre la valeur numérique associée)
                               ⚠️ PAS "Droit de timbre sur téléphonie/internet" (taxe séparée)
                               ⚠️ Valeur max attendue : 30 DT — si > 50 DT → null (confusion avec TTC)
                               ⚠️ Si la valeur est "1.000" → c'est 1.000 DT (CAS A millimes), JAMAIS 1000
  "net_a_payer"   → libellé : "Net à payer", "Total TTC", "Total des charges", "NET A PAYER",
                               "المبلغ الجملي", "Montant total"

⚠️ JAMAIS de calcul :
  ❌ montant_ht ≠ somme des total_ht des articles
  ❌ montant_tva ≠ montant_ht × tva_rate / 100
  ✅ Copie uniquement la valeur de la ligne identifiée par son libellé

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLE 5 — CHAMPS SPÉCIAUX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  "bon_livraison"     → cherche "N° BL", "BL N°", "Bon de Livraison" — prends la valeur
  "reference_commande"→ cherche "N° Commande", "BC", "Bon de commande" — pas le N° Facture
  "tampon_present"    → true si tu vois "cachet", "tampon", "sceau", ou du texte circulaire/illisible typique d'un tampon
  "signature_presente"→ true si tu vois "signé", "signature", paraphe, ou mention de validation manuscrite
  "mode_paiement"     → cherche "Comptant", "Virement", "Chèque", "Traite", "Espèces" — UN SEUL mode. Si liste de choix non cochés → null
  "date_echeance"     → c'est la date d'échéance de PAIEMENT, pas la date de facture (champ "Date")
  "matricule_fiscal_fournisseur" →
    Tunisie : MF format XXXXXXXL/L/L/000 (ex: 789012H/MA/000) — libellés : "MF:", "M.F:", "Mat. Fisc."
    France  : SIRET (14 chiffres, ex: 352 236 244 000 13) ou N° TVA intra (FR + 11 chiffres, ex: FR56352236244)
              libellés : "N° SIRET", "SIRET", "N° TVA intra", "TVA intracommunautaire"
    Maroc   : ICE (15 chiffres) — libellés : "ICE:"
    ⚠️ NE PAS confondre avec RC (Registre du Commerce, format "B XXXXXXXXX" ou "RC:") → RC ≠ MF/SIRET
  "matricule_fiscal_client"      → IF, ICE, SIRET appartenant au CLIENT (bloc client)

  "net_a_payer_lettres" → ⚠️ RÈGLE ABSOLUE : copie le texte EXACTEMENT tel qu'il est écrit dans le document.
    La devise dans ce champ (DINARS / DOLLARS / EUROS / DIRHAMS) doit être copiée sans aucun changement.
    Si le document écrit "DOLLARS", tu copies "DOLLARS" — même si tu penses que c'est une erreur.
    Si le document écrit "DINARS", tu copies "DINARS".
    ❌ NE JAMAIS remplacer la devise par une autre.
    ❌ NE JAMAIS inventer ce texte si tu ne le vois pas clairement.
    → null si ce champ est absent du document.

  "montant_en_lettres" (LETTRE DE CHANGE) → ⚠️ texte manuscrit cursif, lecture difficile :
    Lis chaque mot lentement, lettre par lettre — ne devine pas un mot à partir de sa forme générale.
    Confusions fréquentes en écriture cursive à vérifier explicitement avant de répondre :
      "cinq cent"      ≠ "cent cinquante"   (cinq-cent = 500 ; cent-cinquante = 150 — très différents !)
      "quatre-vingt"   ≠ "quatorze"
      "soixante"       ≠ "seize"
      "mille"          ≠ "mil"  (même nombre, orthographe variable, n'invente pas un autre nombre)
    Le "Montant déjà lu par le modèle principal" indiqué plus haut dans le CONTEXTE (ex: 1500,000) vient
    de la case imprimée encadrée par # et est BIEN PLUS FIABLE que ta lecture de l'écriture manuscrite.
    ⚠️ OBLIGATOIRE AVANT DE RÉPONDRE : convertis ce nombre en toutes lettres toi-même (ex: 1500,000 →
    "Mille cinq cents dinars") et UTILISE CETTE CONVERSION comme valeur de "montant_en_lettres", sauf si
    l'écriture manuscrite est sans ambiguïté possible un montant clairement différent (rare).
    Ne pars jamais uniquement de ta lecture visuelle de l'écriture manuscrite sans la confronter à ce
    montant numérique connu — c'est la cause la plus fréquente d'erreur sur ce champ.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLE 7 — ERREURS OCR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L'OCR peut faire des erreurs de lecture. Corrige si tu es certain :
  - "0" ↔ "O" dans les noms propres
  - "1" ↔ "l" dans les noms
  - Espaces manquants dans les mots composés
  - Ne corrige PAS les montants ou numéros (risque d'erreur)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMAT DE SORTIE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Retourne UNIQUEMENT un objet JSON valide correspondant au schéma ci-dessous.
  ❌ Pas de markdown (pas de ```json ni ```)
  ❌ Pas d'explication avant ou après
  ❌ Pas de commentaire dans le JSON (supprime les // ...)
  ✅ Valeurs absentes → null (jamais "" chaîne vide)
  ✅ Décimales exactes copiées depuis le document (2.252 reste 2.252)
  ✅ Booléens : true / false (pas de guillemets)

SCHÉMA À UTILISER :
{schema_a_utiliser}

JSON :"""

    content = ""
    try:
        content = _call_llm(prompt)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        content = _sanitize_llm_json(content)

        # Tente le parsing direct
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            # Réparation automatique si JSON tronqué (réponse trop longue)
            repaired = _repair_truncated_json(content)
            parsed = json.loads(repaired)
            return json.dumps(parsed, ensure_ascii=False, indent=2)

    except json.JSONDecodeError as e:
        return json.dumps(
            {"error": f"JSON invalide : {str(e)}", "raw_response": content[:500] + "…"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": f"Erreur LLM extraction : {str(e)}"}, ensure_ascii=False)
