"""
assistant/api/main.py — Serveur FastAPI local (Agents 1, 2, 3 & 4)

Lance avec :
    cd assistant
    uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload

Endpoints :
    POST /analyse        — Agent 1 + Agent 2 + Agent 3 chained
    POST /audit          — Agent 2 seul (JSON body : complete_entities + base_entities)
    POST /chat           — Agent 4 Chatbot
    GET  /pg/documents   — List of the documents stored in PostgreSQL
    DELETE /documents/{type}/{number} — Supprime un document de PostgreSQL (admin)
    GET  /health         — Checks that the server is running
"""

import asyncio
import os
import sys
import tempfile
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Allows importing state.py and agents/ from the assistant/ folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, Form, UploadFile, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from jose import jwt, JWTError

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_SECRET    = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"

from langchain_core.messages import HumanMessage, AIMessage as LCAIMessage

from agents.extractor import extractor_graph
from agents.auditor   import auditor_graph
from agents.analyst   import analyst_graph
from agents.chatbot   import chatbot_graph
from agents.auditor.daily_reporter import send_daily_report
from database import (
    init_db, save_document, get_documents_pg, get_facture, get_traite,
    delete_document_pg, clear_documents_pg,
)


# ── Scheduler rapport quotidien 8h00 ─────────────────────────────────────────

async def _daily_report_scheduler():
    """asyncio task: sends the consolidated report every day at 8:00."""
    print("[DAILY] Scheduler started — next report at 08:00")
    while True:
        now    = datetime.now()
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_s = (target - now).total_seconds()
        print(f"[DAILY] Next report in {wait_s/3600:.1f}h ({target.strftime('%d/%m/%Y at 08:00')})")
        await asyncio.sleep(wait_s)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, send_daily_report)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(_daily_report_scheduler())
    yield


app = FastAPI(
    title="Agents OCR — Pipeline Multi-Agent",
    description="Pipeline multi-agent : extraction · audit · analyse · chatbot",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["*"],
)


# ── Auth JWT ──────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    username: str
    role: str


def verify_token(authorization: str = Header(None)) -> dict:
    """FastAPI dependency — validates the Bearer JWT and returns its payload."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token JWT manquant (Authorization: Bearer <token>)")
    try:
        payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired JWT")


def _owner_from_token(authorization: Optional[str]) -> str:
    """Extracts the username from an optional token — returns 'anonymous' if missing/invalid."""
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
    Returns a signed JWT for the frontend.
    Called once after the localStorage login — stored on the client side.
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
    base_entities : str        = Form(default="{}"),   # JSON string from GLM (optional)
    authorization : Optional[str] = Header(default=None),  # optional JWT for owner_username
):
    """
    Pipeline complet : Agent 1 (Extraction) → Agent 2 (Audit).

    Parameters:
      file          : image (JPG, PNG, BMP, TIFF) ou PDF
      document_type : "facture" | "lettre_de_change" | "auto"
      base_entities : JSON string of the entities already extracted by the GLM model

    Retourne :
    {
      "analyse_contextuelle": { ... },  ← Agent 1: extracted entities
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
            content={"status": "error", "error": f"Unsupported format: {suffix}"},
        )

    try:
        base = _json.loads(base_entities) if base_entities else {}
    except Exception:
        base = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        import time as _time
        _t_start = _time.perf_counter()

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
        print(f"[API] Agent1 entities: {len(analyse)} fields")

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

        # ── PostgreSQL: save the results of Agents 1 + 2 ────────────────────
        try:
            _processing_time = round(_time.perf_counter() - _t_start, 2)
            save_document(
                filename          = file.filename or "unknown",
                entities          = analyse,
                audit_report      = rapport_audit,
                owner_username    = _owner_from_token(authorization),
                processing_time_s = _processing_time,
            )
            print(f"[API] Temps traitement : {_processing_time}s")
        except Exception as e_db:
            print(f"[API] PostgreSQL save skipped: {e_db}")

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


# ── Agent 2 alone (audit of an existing JSON) ─────────────────────────────────

class AuditRequest(BaseModel):
    complete_entities: dict
    base_entities    : dict = {}


@app.post("/audit")
async def audit_only(req: AuditRequest):
    """
    Audits a JSON of entities directly (without re-extraction).
    Useful to re-audit after a manual correction.
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


# ── Agent 3 alone (behavioural analysis of an existing JSON) ──────────────────

class AnalystRequest(BaseModel):
    complete_entities: dict
    audit_report     : dict = {}


@app.post("/analyst")
async def analyst_only(req: AnalystRequest):
    """
    Re-analyses a JSON of entities directly (without re-extraction).
    Called after a manual correction of the contextual analysis (HITL),
    usually right after a call to /audit to propagate the corrections.
    """
    try:
        analyst_state = analyst_graph.invoke({
            "complete_entities": req.complete_entities,
            "audit_report"     : req.audit_report,
        })
        rapport = analyst_state.get("analyst_report") or {}
        return {"analyse": rapport, "status": "ok"}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"analyse": None, "status": "error", "error": str(e)},
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
    Conversation with the Chatbot Agent (Agent 4).

    The context of the current document (entities, audit, analysis) is injected
    automatically into the system prompt of the LLM.
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
            "Sorry, I cannot answer right now."
        )
        print(f"[API/chat] Answer: {response[:80]}…")
        return {"response": response, "status": "ok"}

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"response": None, "status": "error", "error": str(e)},
        )


# ── Admin: deletion of stored documents (PostgreSQL) ──────────────────────────

@app.delete("/documents/{doc_type}/{doc_number}")
async def remove_document(
    doc_type  : str,
    doc_number: str,
    token_data: dict = Depends(verify_token),
):
    """Deletes a document from PostgreSQL — administrators only (role: admin)."""
    if token_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied — admin role required")
    deleted = delete_document_pg(doc_type, doc_number)
    return {"deleted": deleted, "doc_type": doc_type, "doc_number": doc_number}


@app.delete("/admin/clear-documents")
async def clear_documents(token_data: dict = Depends(verify_token)):
    """Empties the PostgreSQL database entirely (documents + invoices + bills)."""
    if token_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied — admin role required")
    count = clear_documents_pg()
    return {"status": "ok", "deleted": count, "message": f"{count} document(s) deleted from PostgreSQL"}


@app.post("/admin/daily-report")
async def trigger_daily_report(token_data: dict = Depends(verify_token)):
    """Triggers the daily consolidated report manually (without waiting for 8:00)."""
    if token_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied — admin role required")
    loop = asyncio.get_event_loop()
    sent = await loop.run_in_executor(None, send_daily_report)
    return {"status": "ok" if sent else "error", "sent": sent}


# ── PostgreSQL : historique complet ──────────────────────────────────────────

@app.get("/pg/documents")
async def pg_documents(limit: int = 50):
    """Returns the full history from PostgreSQL (invoices + bills)."""
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
    """Manually saves the (possibly corrected) entities to PostgreSQL."""
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
    """Returns the full details of a document (entities + audit JSON)."""
    facture = get_facture(doc_id)
    traite  = get_traite(doc_id)
    if not facture and not traite:
        return JSONResponse(status_code=404, content={"error": f"Document {doc_id} introuvable"})
    return {"doc_id": doc_id, "data": facture or traite, "status": "ok"}
