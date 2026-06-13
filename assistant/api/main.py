"""
assistant/api/main.py — Serveur FastAPI local (Agents 1, 2, 3 & 4)

Lance avec :
    cd assistant
    uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload

Endpoints :
    POST /analyse        — Agent 1 + Agent 2 + Agent 3 enchaînés
    POST /audit          — Agent 2 seul (JSON body : complete_entities + base_entities)
    POST /chat           — Agent 4 Chatbot
    GET  /documents      — Liste des documents enregistrés en base (déduplication)
    DELETE /documents/{type}/{number} — Supprime un document de la base
    GET  /health         — Vérifie que le serveur tourne
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Optional

# Permet d'importer state.py et agents/ depuis le dossier assistant/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, Form, UploadFile, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from jose import jwt, JWTError

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_SECRET    = os.getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM = "HS256"

from langchain_core.messages import HumanMessage, AIMessage as LCAIMessage

from agents.extractor import extractor_graph
from agents.auditor   import auditor_graph
from agents.analyst   import analyst_graph
from agents.chatbot   import chatbot_graph
from agents.auditor.db import list_documents, delete_document
from database import init_db, save_document, get_documents_pg, get_facture, get_traite

app = FastAPI(
    title="Agents OCR — Pipeline Multi-Agent",
    description="Pipeline multi-agent : extraction · audit · analyse · chatbot",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["*"],
)

# Initialise les tables PostgreSQL au démarrage (silencieux si DATABASE_URL absent)
init_db()


# ── Auth JWT ──────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    username: str
    role: str


def verify_token(authorization: str = Header(None)) -> dict:
    """Dépendance FastAPI — valide le Bearer JWT et retourne le payload."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token JWT manquant (Authorization: Bearer <token>)")
    try:
        payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token JWT invalide ou expiré")


def _owner_from_token(authorization: Optional[str]) -> str:
    """Extrait le username depuis un token optionnel — retourne 'anonymous' si absent/invalide."""
    if not authorization or not authorization.startswith("Bearer "):
        return "anonymous"
    try:
        payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub", "anonymous")
    except JWTError:
        return "anonymous"


@app.post("/token")
async def create_token(req: TokenRequest):
    """
    Retourne un JWT signé pour le frontend.
    Appelé une fois après login localStorage — stocké côté client.
    """
    payload = {"sub": req.username, "role": req.role}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/health")
async def health():
    return {"status": "ok", "agents": ["extracteur", "auditeur", "analyste", "chatbot"], "version": "3.0"}


# ── Agent 1 + Agent 2 (pipeline complet) ─────────────────────────────────────

@app.post("/analyse")
async def analyse_document(
    file          : UploadFile = File(...),
    document_type : str        = Form(default="auto"),
    base_entities : str        = Form(default="{}"),   # JSON string du GLM (optionnel)
    authorization : Optional[str] = Header(default=None),  # JWT optionnel pour owner_username
):
    """
    Pipeline complet : Agent 1 (Extraction) → Agent 2 (Audit).

    Paramètres :
      file          : image (JPG, PNG, BMP, TIFF) ou PDF
      document_type : "facture" | "lettre_de_change" | "auto"
      base_entities : JSON string des entités déjà extraites par le modèle GLM

    Retourne :
    {
      "analyse_contextuelle": { ... },  ← Agent 1 : entités extraites
      "audit"               : { ... },  ← Agent 2 : rapport d'audit
      "file_type"           : "image|pdf_native|pdf_scanned",
      "status"              : "ok" | "error"
    }
    """
    import json as _json

    allowed = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf"}
    suffix  = Path(file.filename or "doc.jpg").suffix.lower()
    if suffix not in allowed:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": f"Format non supporté : {suffix}"},
        )

    try:
        base = _json.loads(base_entities) if base_entities else {}
    except Exception:
        base = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        # ── Agent 1 : Extraction ──────────────────────────────────────────────
        result = extractor_graph.invoke(
            {
                "file_path"    : tmp_path,
                "document_type": document_type,
                "base_entities": base,
                "messages"     : [],
            },
            config={
                "run_name": f"Extracteur — {file.filename}",
                "tags"    : ["agent1", "extracteur", document_type],
                "metadata": {"filename": file.filename, "document_type": document_type},
            },
        )

        analyse = result.get("complete_entities") or result.get("augmented_entities") or {}

        print(f"\n[API] file_type : {result.get('file_type')}")
        print(f"[API] Agent1 entities : {len(analyse)} champs")

        # ── Agent 2 : Audit ───────────────────────────────────────────────────
        try:
            audit_state = auditor_graph.invoke(
                {
                    "complete_entities": analyse,
                    "base_entities"    : base,
                },
                config={
                    "run_name": f"Auditeur — {file.filename}",
                    "tags"    : ["agent2", "auditeur"],
                    "metadata": {"filename": file.filename},
                },
            )
            rapport_audit = audit_state.get("audit_report") or {}
            print(f"[API] Agent2 status : {audit_state.get('status_validite')}")
        except Exception as e_audit:
            traceback.print_exc()
            rapport_audit = {"status_validite": "ERREUR_AUDIT", "detail": str(e_audit)}

        # ── PostgreSQL : sauvegarde résultats Agents 1 + 2 ──────────────────
        try:
            save_document(
                filename       = file.filename or "unknown",
                entities       = analyse,
                audit_report   = rapport_audit,
                owner_username = _owner_from_token(authorization),
            )
        except Exception as e_db:
            print(f"[API] PostgreSQL save ignoré : {e_db}")

        # ── Agent 3 : Analyse comportementale ────────────────────────────────
        try:
            analyst_state = analyst_graph.invoke(
                {
                    "complete_entities": analyse,
                    "audit_report"     : rapport_audit,
                },
                config={
                    "run_name": f"Analyste — {file.filename}",
                    "tags"    : ["agent3", "analyste"],
                    "metadata": {"filename": file.filename},
                },
            )
            rapport_analyse = analyst_state.get("analyst_report") or {}
            print(f"[API] Agent3 alert_level : {analyst_state.get('alert_level')}")
        except Exception as e_analyst:
            traceback.print_exc()
            rapport_analyse = {"alert_level": "ERREUR", "detail": str(e_analyst)}

        return {
            "analyse_contextuelle": analyse,
            "audit"               : rapport_audit,
            "analyse"             : rapport_analyse,
            "file_type"           : result.get("file_type"),
            "status"              : "ok",
            "error"               : None,
        }

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "analyse_contextuelle": {},
                "audit"               : None,
                "analyse"             : None,
                "file_type"           : None,
                "status"              : "error",
                "error"               : str(e),
            },
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── Agent 2 seul (audit d'un JSON existant) ───────────────────────────────────

class AuditRequest(BaseModel):
    complete_entities: dict
    base_entities    : dict = {}


@app.post("/audit")
async def audit_only(req: AuditRequest):
    """
    Audite directement un JSON d'entités (sans ré-extraction).
    Utile pour re-auditer après correction manuelle.
    """
    try:
        audit_state = auditor_graph.invoke({
            "complete_entities": req.complete_entities,
            "base_entities"    : req.base_entities,
        })
        rapport = audit_state.get("audit_report") or {}
        return {"audit": rapport, "status": "ok"}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"audit": None, "status": "error", "error": str(e)},
        )


# ── Agent 4 : Chatbot ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message          : str
    context_entities : dict = {}
    context_audit    : dict = {}
    context_analyst  : dict = {}
    history          : list = []   # [{role: "user"|"assistant", content: str}]


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Échange avec l'Agent Chatbot (Agent 4).

    Le contexte du document courant (entités, audit, analyse) est injecté
    automatiquement dans le system prompt du LLM.
    """
    try:
        lc_messages = []
        for msg in req.history:
            role    = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(LCAIMessage(content=content))

        lc_messages.append(HumanMessage(content=req.message))

        chat_state = chatbot_graph.invoke(
            {
                "messages"        : lc_messages,
                "context_entities": req.context_entities,
                "context_audit"   : req.context_audit,
                "context_analyst" : req.context_analyst,
            },
            config={
                "run_name": "Chatbot",
                "tags"    : ["agent4", "chatbot"],
            },
        )

        response = chat_state.get("response") or (
            "Je suis désolé, je ne peux pas répondre pour le moment."
        )
        print(f"[API/chat] Réponse : {response[:80]}…")
        return {"response": response, "status": "ok"}

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"response": None, "status": "error", "error": str(e)},
        )


# ── Admin : liste et suppression des documents enregistrés ────────────────────

@app.get("/documents")
async def get_documents(limit: int = 50):
    """Retourne les derniers documents enregistrés en base (déduplication)."""
    return {"documents": list_documents(limit), "status": "ok"}


@app.delete("/documents/{doc_type}/{doc_number}")
async def remove_document(
    doc_type  : str,
    doc_number: str,
    token_data: dict = Depends(verify_token),
):
    """Supprime un document de la base SQLite — réservé aux administrateurs (role: admin)."""
    if token_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé — rôle admin requis")
    deleted = delete_document(doc_type, doc_number)
    return {"deleted": deleted, "doc_type": doc_type, "doc_number": doc_number}


# ── PostgreSQL : historique complet ──────────────────────────────────────────

@app.get("/pg/documents")
async def pg_documents(limit: int = 50):
    """Retourne l'historique complet depuis PostgreSQL (factures + traites)."""
    rows = get_documents_pg(limit)
    return {"documents": rows, "count": len(rows), "status": "ok"}


class SaveRequest(BaseModel):
    filename:     str
    entities:     dict
    doc_type:     str = "auto"
    audit_report: dict = {}


@app.post("/save")
async def save_entities(
    req: SaveRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Sauvegarde manuelle des entités (éventuellement corrigées) en PostgreSQL."""
    try:
        # Normalize keys to lowercase so save_document can match field names
        entities_norm = {k.lower(): v for k, v in req.entities.items()}

        # Set _document_type so save_document selects the right table
        is_traite = req.doc_type in ("lettre_de_change", "traite") or \
                    "lettre" in req.doc_type or "traite" in req.doc_type
        entities_norm["_document_type"] = "lettre_de_change" if is_traite else "facture"

        # Bridge GLM uppercase keys → expected lowercase field names
        if is_traite:
            if "num_lettre" not in entities_norm:
                entities_norm["num_lettre"] = entities_norm.get("numero_traite", "")
            if "montant" not in entities_norm:
                entities_norm["montant"] = entities_norm.get("montant_ttc") or entities_norm.get("montant", "")
        else:
            if "num_facture" not in entities_norm:
                entities_norm["num_facture"] = entities_norm.get("numero_facture", "")
            if "net_a_payer" not in entities_norm:
                entities_norm["net_a_payer"] = entities_norm.get("montant_ttc", "")

        doc_id = save_document(
            filename       = req.filename,
            entities       = entities_norm,
            audit_report   = req.audit_report,
            owner_username = _owner_from_token(authorization),
        )
        if doc_id is None:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "error": "PostgreSQL non disponible"},
            )
        return {"status": "ok", "doc_id": doc_id}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)},
        )


@app.get("/pg/documents/{doc_id}")
async def pg_document_detail(doc_id: int):
    """Retourne le détail complet d'un document (entités + audit JSON)."""
    facture = get_facture(doc_id)
    traite  = get_traite(doc_id)
    if not facture and not traite:
        return JSONResponse(status_code=404, content={"error": f"Document {doc_id} introuvable"})
    return {"doc_id": doc_id, "data": facture or traite, "status": "ok"}
