"""
Gestionnaire de base de données SQLite
Stocke les métadonnées des documents OCR
Les fichiers bruts sont stockés sur disque (data/raw/)
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict


# Chemin de la BDD — à la racine du projet
DB_PATH = Path(__file__).parent.parent.parent / "data" / "ocr_database.db"


class DatabaseManager:
    """Gestionnaire SQLite pour les métadonnées des documents"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Crée les tables si elles n'existent pas"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_name   TEXT    NOT NULL,
                    stored_name     TEXT    NOT NULL,
                    file_path       TEXT    NOT NULL,
                    file_type       TEXT,
                    extension       TEXT,
                    size_bytes      INTEGER,
                    upload_date     TEXT    NOT NULL,
                    language        TEXT    DEFAULT 'inconnu',
                    doc_category    TEXT    DEFAULT 'autre',
                    status          TEXT    DEFAULT 'uploadé',
                    ocr_text        TEXT,
                    extracted_fields TEXT
                )
            """)
            conn.commit()

    # ── Insertion ────────────────────────────────────────────────────────────

    def insert_document(
        self,
        original_name: str,
        stored_name: str,
        file_path: str,
        file_type: str,
        extension: str,
        size_bytes: int,
        language: str = "inconnu",
        doc_category: str = "autre",
    ) -> int:
        """
        Insère un document dans la BDD.
        Retourne l'ID généré.
        """
        upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents
                    (original_name, stored_name, file_path, file_type,
                     extension, size_bytes, upload_date, language, doc_category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (original_name, stored_name, file_path, file_type,
                 extension, size_bytes, upload_date, language, doc_category),
            )
            conn.commit()
            return cursor.lastrowid

    # ── Lecture ──────────────────────────────────────────────────────────────

    def get_all_documents(self) -> List[Dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY upload_date DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_document_by_id(self, doc_id: int) -> Optional[Dict]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
        return dict(row) if row else None

    def search_documents(
        self,
        search: str = "",
        doc_category: str = "Tous",
        language: str = "Toutes",
        days: Optional[int] = None,
    ) -> List[Dict]:
        query = "SELECT * FROM documents WHERE 1=1"
        params = []

        if search:
            query += " AND (original_name LIKE ? OR ocr_text LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]

        if doc_category and doc_category != "Tous":
            query += " AND doc_category = ?"
            params.append(doc_category.lower())

        if language and language != "Toutes":
            query += " AND language = ?"
            params.append(language.lower())

        if days:
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            query += " AND upload_date >= ?"
            params.append(cutoff)

        query += " ORDER BY upload_date DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ── Statistiques ─────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            traites = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE status = 'traité'"
            ).fetchone()[0]
            en_attente = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE status = 'uploadé'"
            ).fetchone()[0]

            # Répartition par catégorie
            cat_rows = conn.execute(
                "SELECT doc_category, COUNT(*) as n FROM documents GROUP BY doc_category"
            ).fetchall()
            categories = {r["doc_category"]: r["n"] for r in cat_rows}

            # Documents du mois courant
            mois = datetime.now().strftime("%Y-%m")
            du_mois = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE upload_date LIKE ?",
                (f"{mois}%",),
            ).fetchone()[0]

            # Documents par mois (6 derniers mois)
            par_mois = conn.execute(
                """
                SELECT strftime('%Y-%m', upload_date) as mois, COUNT(*) as n
                FROM documents
                GROUP BY mois
                ORDER BY mois DESC
                LIMIT 6
                """
            ).fetchall()

        taux_reussite = round((traites / total * 100) if total > 0 else 0)

        return {
            "total": total,
            "traites": traites,
            "en_attente": en_attente,
            "taux_reussite": taux_reussite,
            "categories": categories,
            "du_mois": du_mois,
            "par_mois": [dict(r) for r in par_mois],
        }

    # ── Mise à jour ──────────────────────────────────────────────────────────

    def update_status(self, doc_id: int, status: str):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE documents SET status = ? WHERE id = ?", (status, doc_id)
            )
            conn.commit()

    def update_ocr_result(
        self,
        doc_id: int,
        ocr_text: str,
        extracted_fields: Optional[Dict] = None,
        language: str = "inconnu",
    ):
        fields_json = json.dumps(extracted_fields, ensure_ascii=False) if extracted_fields else None
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE documents
                SET ocr_text = ?, extracted_fields = ?, language = ?, status = 'traité'
                WHERE id = ?
                """,
                (ocr_text, fields_json, language, doc_id),
            )
            conn.commit()

    def update_category(self, doc_id: int, doc_category: str):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE documents SET doc_category = ? WHERE id = ?",
                (doc_category, doc_id),
            )
            conn.commit()

    # ── Suppression ──────────────────────────────────────────────────────────

    def delete_document(self, doc_id: int):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()
