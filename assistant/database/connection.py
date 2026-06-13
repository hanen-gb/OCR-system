"""
Connexion PostgreSQL — pool psycopg2.

Variable d'environnement requise (assistant/.env) :
  DATABASE_URL=postgresql://user:password@localhost:5432/ocr_pfe

Appeler init_db() au démarrage de l'API pour créer les tables si elles n'existent pas.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Connexion lazy — ouverte à la première utilisation
_connection = None


def _get_raw_conn():
    global _connection
    if _connection is None or _connection.closed:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL absent dans .env — "
                "ex: postgresql://postgres:motdepasse@localhost:5432/ocr_pfe"
            )
        _connection = psycopg2.connect(DATABASE_URL)
        _connection.autocommit = False
    return _connection


@contextmanager
def get_conn():
    """Context manager : yield une connexion, commit ou rollback automatique."""
    conn = _get_raw_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    """
    Crée les 3 tables PostgreSQL si elles n'existent pas encore.
    À appeler une fois au démarrage de l'API.
    """
    ddl = """
    -- ENUMs (ignorés si déjà créés)
    DO $$ BEGIN
        CREATE TYPE doc_type_enum AS ENUM ('FACTURE', 'TRAITE');
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;

    DO $$ BEGIN
        CREATE TYPE doc_status_enum AS ENUM ('PROCESSING', 'PENDING', 'VALIDATED');
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;

    -- Table principale : un enregistrement par fichier traité
    CREATE TABLE IF NOT EXISTS documents (
        id             SERIAL PRIMARY KEY,
        filename       VARCHAR(255),
        doc_type       doc_type_enum,
        status         doc_status_enum DEFAULT 'PENDING',
        audit_status   VARCHAR(50),
        owner_username VARCHAR(100) DEFAULT 'anonymous',
        created_at     TIMESTAMP DEFAULT NOW()
    );

    -- Migration pour les BDD existantes (ignoré si la colonne existe déjà)
    ALTER TABLE documents ADD COLUMN IF NOT EXISTS owner_username VARCHAR(100) DEFAULT 'anonymous';

    -- Table factures
    CREATE TABLE IF NOT EXISTS factures (
        id           SERIAL PRIMARY KEY,
        doc_id       INT REFERENCES documents(id) ON DELETE CASCADE,
        numero       VARCHAR(100),
        date         DATE,
        fournisseur  VARCHAR(255),
        client       VARCHAR(255),
        montant_ttc  DECIMAL(12,3),
        notes_agent  TEXT
    );

    -- Table traites (lettres de change)
    CREATE TABLE IF NOT EXISTS traites (
        id             SERIAL PRIMARY KEY,
        doc_id         INT REFERENCES documents(id) ON DELETE CASCADE,
        numero         VARCHAR(100),
        date_echeance  DATE,
        tireur         VARCHAR(255),
        tire           VARCHAR(255),
        rib            VARCHAR(100),
        domiciliation  VARCHAR(255),
        montant        DECIMAL(12,3),
        notes_agent    TEXT
    );
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
        print("[DB] Tables PostgreSQL initialisées")
    except Exception as e:
        print(f"[DB] PostgreSQL non disponible → désactivé ({e})")
