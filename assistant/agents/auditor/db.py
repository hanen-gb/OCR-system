"""
Base SQLite locale — Détection de doublons pour l'Agent 2 : L'Auditeur.

Table : documents
  doc_type   : "facture" | "lettre_de_change"
  doc_number : N° facture ou N° traite (clé de déduplication)
  fournisseur: nom du fournisseur ou tireur
  montant    : montant TTC ou montant traite
  date_doc   : date de la facture / date d'échéance
  first_seen : timestamp d'insertion (ISO 8601)
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "documents.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type    TEXT    NOT NULL,
                doc_number  TEXT    NOT NULL,
                fournisseur TEXT,
                montant     REAL,
                date_doc    TEXT,
                first_seen  TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_key
            ON documents (doc_type, doc_number)
        """)


def check_doublon(doc_type: str, doc_number: str | None) -> dict:
    """
    Vérifie si (doc_type, doc_number) est déjà en base.

    Retourne :
      {"status": "NOUVEAU",  "doc_number": ...}
      {"status": "DOUBLON",  "doc_number": ..., "first_seen": ..., "detail": ...}
      {"status": "INCONNU",  "detail": "Numéro absent"}
    """
    if not doc_number:
        return {"status": "INCONNU", "detail": "Numéro de document absent"}

    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT first_seen, fournisseur, montant FROM documents "
            "WHERE doc_type = ? AND doc_number = ?",
            (doc_type, str(doc_number)),
        ).fetchone()

    if row:
        return {
            "status"     : "DOUBLON",
            "doc_number" : doc_number,
            "first_seen" : row["first_seen"],
            "fournisseur": row["fournisseur"],
            "montant"    : row["montant"],
            "detail"     : f"Déjà traité le {row['first_seen'][:10]}",
        }

    return {"status": "NOUVEAU", "doc_number": doc_number}


def register_document(
    doc_type   : str,
    doc_number : str,
    fournisseur: str | None = None,
    montant    : float | None = None,
    date_doc   : str | None = None,
) -> None:
    """Insère le document en base (ignoré s'il existe déjà)."""
    if not doc_number:
        return
    init_db()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO documents "
            "(doc_type, doc_number, fournisseur, montant, date_doc, first_seen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (doc_type, str(doc_number), fournisseur, montant, date_doc, now),
        )


def list_documents(limit: int = 50) -> list[dict]:
    """Retourne les derniers documents enregistrés (pour debug/admin)."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_document(doc_type: str, doc_number: str) -> bool:
    """Supprime un document de la base (pour corriger une fausse détection)."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM documents WHERE doc_type = ? AND doc_number = ?",
            (doc_type, str(doc_number)),
        )
    return cur.rowcount > 0


def clear_sqlite_db() -> int:
    """Vide complètement la table SQLite de détection de doublons. Retourne le nb de lignes supprimées."""
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM documents")
    return cur.rowcount
