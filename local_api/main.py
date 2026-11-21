"""
local_api/main.py
Serveur FastAPI local — pont entre React (port 3000) et PostgreSQL (port 5432)
Lancer avec : uvicorn main:app --reload --port 8001
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import psycopg
from psycopg.rows import dict_row

# ── Configuration BDD ────────────────────────────────────────────────────────
DB_CONFIG = {
    "dbname":   "postgres",
    "user":     "postgres",
    "password": "postgres",
    "host":     "localhost",
    "port":     5432,
}

def get_conn():
    return psycopg.connect(**DB_CONFIG)

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="ODSINET Local API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Allows all local origins (development)
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ──────────────────────────────────────────────────────────────────
class Timing(BaseModel):
    inference_ms: Optional[int] = None
    total_ms:     Optional[int] = None

class FacturePayload(BaseModel):
    filename:    str
    entities:    dict[str, str]
    corrections: Optional[dict[str, dict]] = None
    full_text:   Optional[str]             = None
    timing:      Optional[Timing]          = None

# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "odsinet-local-api"}


@app.post("/factures")
def save_facture(data: FacturePayload):
    """Inserts an extracted invoice (+ any corrections) into PostgreSQL."""
    e = data.entities
    corrected = bool(data.corrections and len(data.corrections) > 0)

    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO factures
                (filename, client, fournisseur, numero_facture,
                 date_facture, montant_ttc, corrected, full_text, inference_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (
                data.filename,
                e.get("CLIENT",         "N/A"),
                e.get("FOURNISSEUR",    "N/A"),
                e.get("NUMERO_FACTURE", "N/A"),
                e.get("DATE_FACTURE",   "N/A"),
                e.get("MONTANT_TTC",    "N/A"),
                corrected,
                data.full_text,
                data.timing.inference_ms if data.timing else None,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "id": row[0], "created_at": str(row[1])}

    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/factures")
def list_factures(limit: int = 50):
    """Returns the latest stored invoices."""
    try:
        conn = get_conn()
        cur  = conn.cursor(row_factory=dict_row)
        cur.execute(
            "SELECT * FROM factures ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"factures": rows, "total": len(rows)}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.delete("/factures/{facture_id}")
def delete_facture(facture_id: int):
    """Deletes an invoice by ID."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("DELETE FROM factures WHERE id = %s", (facture_id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))
