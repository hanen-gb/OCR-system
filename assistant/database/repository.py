"""
PostgreSQL CRUD operations — documents, invoices, bills of exchange.

Fonction principale : save_document()
  Called after Agent 1 + Agent 2 with the complete results.
  Inserts into documents + invoices OR bills depending on the type.

notes_agent stores the full JSON of the agents (entities + audit report).
"""

import json
import re
from datetime import datetime
from psycopg2.extras import RealDictCursor

from .connection import get_conn


def _safe_date(val: str | None):
    """Tries to parse a date string into a Python date object, or None."""
    if not val:
        return None
    # %d-%m-%y covers dates such as "12-11-22"
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _safe_float(val) -> float | None:
    """
    Converts an amount string to a float, handling both conventions:
      - "4 488,00"   (espace milliers, virgule decimale - convention FR/EU)
      - "4,498.800"  (virgule milliers, point decimale - convention US/mixte
                       vue sur certaines factures, ex: NETLINK)
    Rule: the RIGHT-most separator is the decimal one; the other one (if any)
    is a thousands separator to remove.
    """
    if val is None:
        return None
    try:
        if isinstance(val, str):
            v = re.sub(r"\s", "", val.strip())
            last_comma = v.rfind(",")
            last_dot   = v.rfind(".")
            if last_comma != -1 and last_dot != -1:
                if last_comma > last_dot:
                    v = v.replace(".", "").replace(",", ".")
                else:
                    v = v.replace(",", "")
            elif last_comma != -1:
                v = v.replace(",", ".")
            val = v
        return float(val)
    except (TypeError, ValueError):
        return None


def save_document(
    filename: str,
    entities: dict,
    audit_report: dict,
    owner_username: str = "anonymous",
    processing_time_s: float | None = None,
) -> int | None:
    """
    Saves a processed document to PostgreSQL.

    1. Inserts into `documents`  → returns doc_id
    2. If INVOICE                → inserts into `factures`
    3. If BILL OF EXCHANGE       → inserts into `traites`

    Returns doc_id (int), or None if PostgreSQL is unavailable.
    """
    doc_type_raw = (entities.get("_document_type") or "facture").lower()
    is_traite    = "lettre" in doc_type_raw or "change" in doc_type_raw or "traite" in doc_type_raw
    doc_type_pg  = "TRAITE" if is_traite else "FACTURE"

    audit_status = (audit_report.get("status_validite") or "PENDING").upper()

    # Mapping statut audit → statut workflow
    status_map = {
        "VALIDÉ"                 : "VALIDATED",
        "DOUBLON"                : "PENDING",
        "ERREUR_CALCUL"          : "PENDING",
        "ERREUR_TVA"             : "PENDING",
        "ERREUR_NET_A_PAYER"     : "PENDING",
        "ERREUR_MONTANT_LETTRES" : "PENDING",
        "SIGNATURE_MANQUANTE"    : "PENDING",
    }
    workflow_status = status_map.get(audit_status, "PENDING")

    notes = json.dumps({
        "entities"    : entities,
        "audit_report": audit_report,
    }, ensure_ascii=False)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                # 1 — Insert into documents
                cur.execute(
                    """
                    INSERT INTO documents
                      (filename, doc_type, status, audit_status, owner_username, processing_time_s)
                    VALUES (%s, %s::doc_type_enum, %s::doc_status_enum, %s, %s, %s)
                    RETURNING id
                    """,
                    (filename, doc_type_pg, workflow_status, audit_status, owner_username, processing_time_s),
                )
                doc_id = cur.fetchone()[0]

                # 2a — Facture
                if not is_traite:
                    numero      = entities.get("numero_facture") or entities.get("num_facture")
                    date_val    = _safe_date(entities.get("date_facture"))
                    fournisseur = entities.get("fournisseur")
                    if isinstance(fournisseur, dict):
                        fournisseur = fournisseur.get("nom")
                    client      = entities.get("client")
                    if isinstance(client, dict):
                        client = client.get("nom")
                    montant_ttc = _safe_float(entities.get("net_a_payer"))

                    cur.execute(
                        """
                        INSERT INTO factures
                          (doc_id, numero, date, fournisseur, client, montant_ttc, notes_agent)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (doc_id, numero, date_val, fournisseur, client, montant_ttc, notes),
                    )

                # 2b — Bill of exchange
                else:
                    numero        = entities.get("num_lettre") or entities.get("numero_lettre")
                    date_echeance = _safe_date(entities.get("date_echeance"))
                    tireur        = entities.get("tireur")
                    tire          = entities.get("tire")
                    rib           = entities.get("rib") or entities.get("iban")
                    domiciliation = entities.get("domiciliation") or entities.get("banque")
                    montant       = _safe_float(entities.get("montant") or entities.get("net_a_payer"))

                    cur.execute(
                        """
                        INSERT INTO traites
                          (doc_id, numero, date_echeance, tireur, tire, rib, domiciliation, montant, notes_agent)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (doc_id, numero, date_echeance, tireur, tire, rib, domiciliation, montant, notes),
                    )

        print(f"[DB] Sauvegarde OK  doc_id={doc_id} | type={doc_type_pg} | audit={audit_status}")
        return doc_id

    except Exception as e:
        print(f"[DB] PostgreSQL save failed: {e}")
        return None


def get_documents_pg(limit: int = 50) -> list[dict]:
    """Returns the latest documents with their main data."""
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        d.id,
                        d.filename,
                        d.doc_type,
                        d.status,
                        d.audit_status,
                        d.owner_username,
                        d.created_at,
                        d.processing_time_s,
                        COALESCE(f.numero, t.numero)           AS numero,
                        COALESCE(f.fournisseur, t.tireur)      AS fournisseur,
                        COALESCE(f.montant_ttc, t.montant)     AS montant,
                        f.client,
                        t.date_echeance
                    FROM documents d
                    LEFT JOIN factures f ON f.doc_id = d.id
                    LEFT JOIN traites  t ON t.doc_id = d.id
                    ORDER BY d.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        # psycopg2 returns DECIMAL columns as decimal.Decimal — converted to
        # float so that the downstream comparisons/computations (Agent 2, Agent 3) work.
        docs = []
        for r in rows:
            d = dict(r)
            if d.get("montant") is not None:
                d["montant"] = float(d["montant"])
            docs.append(d)
        return docs
    except Exception as e:
        print(f"[DB] get_documents_pg error: {e}")
        return []


def get_facture(doc_id: int) -> dict | None:
    """Returns the full invoice (with the parsed notes_agent JSON)."""
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM factures WHERE doc_id = %s", (doc_id,))
                row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        if result.get("montant_ttc") is not None:
            result["montant_ttc"] = float(result["montant_ttc"])
        try:
            result["notes_agent"] = json.loads(result["notes_agent"])
        except (TypeError, ValueError):
            pass
        return result
    except Exception as e:
        print(f"[DB] get_facture error: {e}")
        return None


def _is_traite_doc_type(doc_type: str | None) -> bool:
    d = (doc_type or "").lower()
    return "lettre" in d or "change" in d or "traite" in d


def check_doublon_pg(doc_type: str | None, doc_number: str | None) -> dict:
    """
    Checks whether a document with this number already exists in PostgreSQL
    (replaces the former SQLite duplicate detection).

    Retourne :
      {"status": "NOUVEAU",  "doc_number": ...}
      {"status": "DOUBLON",  "doc_number": ..., "first_seen": ..., "fournisseur": ..., "montant": ..., "detail": ...}
      {"status": "INCONNU",  "detail": "..."}
    """
    if not doc_number:
        return {"status": "INCONNU", "detail": "Document number missing"}

    is_traite = _is_traite_doc_type(doc_type)
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if is_traite:
                    cur.execute(
                        """
                        SELECT d.created_at, t.tireur AS fournisseur, t.montant AS montant
                        FROM traites t
                        JOIN documents d ON d.id = t.doc_id
                        WHERE t.numero = %s
                        ORDER BY d.created_at ASC
                        LIMIT 1
                        """,
                        (str(doc_number),),
                    )
                else:
                    cur.execute(
                        """
                        SELECT d.created_at, f.fournisseur AS fournisseur, f.montant_ttc AS montant
                        FROM factures f
                        JOIN documents d ON d.id = f.doc_id
                        WHERE f.numero = %s
                        ORDER BY d.created_at ASC
                        LIMIT 1
                        """,
                        (str(doc_number),),
                    )
                row = cur.fetchone()
    except Exception as e:
        print(f"[DB] check_doublon_pg error: {e}")
        return {"status": "INCONNU", "detail": str(e)}

    if row:
        created = row.get("created_at")
        return {
            "status"     : "DOUBLON",
            "doc_number" : doc_number,
            "first_seen" : created.isoformat() if created else None,
            "fournisseur": row.get("fournisseur"),
            "montant"    : float(row["montant"]) if row.get("montant") is not None else None,
            "detail"     : f"Already processed on {created.strftime('%d/%m/%Y') if created else '?'}",
        }
    return {"status": "NOUVEAU", "doc_number": doc_number}


def delete_document_pg(doc_type: str | None, doc_number: str) -> bool:
    """Deletes a document from PostgreSQL (cascade to factures/traites)."""
    is_traite = _is_traite_doc_type(doc_type)
    table     = "traites" if is_traite else "factures"
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM documents WHERE id IN (SELECT doc_id FROM {table} WHERE numero = %s)",
                    (str(doc_number),),
                )
                deleted = cur.rowcount > 0
        return deleted
    except Exception as e:
        print(f"[DB] delete_document_pg error: {e}")
        return False


def clear_documents_pg() -> int:
    """Empties documents/invoices/bills (cascade). Returns the number of deleted documents."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents")
                count = cur.rowcount
        return count
    except Exception as e:
        print(f"[DB] clear_documents_pg error: {e}")
        return 0


def get_traite(doc_id: int) -> dict | None:
    """Returns the full bill of exchange (with the parsed notes_agent JSON)."""
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM traites WHERE doc_id = %s", (doc_id,))
                row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        if result.get("montant") is not None:
            result["montant"] = float(result["montant"])
        try:
            result["notes_agent"] = json.loads(result["notes_agent"])
        except (TypeError, ValueError):
            pass
        return result
    except Exception as e:
        print(f"[DB] get_traite error: {e}")
        return None
