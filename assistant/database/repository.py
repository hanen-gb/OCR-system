"""
Opérations CRUD PostgreSQL — documents, factures, traites.

Fonction principale : save_document()
  Appelée après Agent 1 + Agent 2 avec les résultats complets.
  Insère dans documents + factures OU traites selon le type.

notes_agent stocke le JSON complet des agents (entités + rapport d'audit).
"""

import json
from datetime import datetime
from psycopg2.extras import RealDictCursor

from .connection import get_conn


def _safe_date(val: str | None):
    """Tente de parser une date chaîne vers un objet date Python, ou None."""
    if not val:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        if isinstance(val, str):
            val = val.replace(" ", "").replace(" ", "").replace(",", ".")
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
    Sauvegarde un document traité dans PostgreSQL.

    1. Insère dans `documents`  → retourne doc_id
    2. Si FACTURE               → insère dans `factures`
    3. Si TRAITE                → insère dans `traites`

    Retourne doc_id (int) ou None si PostgreSQL non disponible.
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

                # 1 — Insérer dans documents
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

                # 2b — Traite (lettre de change)
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
        print(f"[DB] Échec sauvegarde PostgreSQL : {e}")
        return None


def get_documents_pg(limit: int = 50) -> list[dict]:
    """Retourne les derniers documents avec leurs données principales."""
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
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] get_documents_pg erreur : {e}")
        return []


def get_facture(doc_id: int) -> dict | None:
    """Retourne la facture complète (avec notes_agent JSON parsé)."""
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM factures WHERE doc_id = %s", (doc_id,))
                row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        try:
            result["notes_agent"] = json.loads(result["notes_agent"])
        except (TypeError, ValueError):
            pass
        return result
    except Exception as e:
        print(f"[DB] get_facture erreur : {e}")
        return None


def get_traite(doc_id: int) -> dict | None:
    """Retourne la traite complète (avec notes_agent JSON parsé)."""
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM traites WHERE doc_id = %s", (doc_id,))
                row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        try:
            result["notes_agent"] = json.loads(result["notes_agent"])
        except (TypeError, ValueError):
            pass
        return result
    except Exception as e:
        print(f"[DB] get_traite erreur : {e}")
        return None
