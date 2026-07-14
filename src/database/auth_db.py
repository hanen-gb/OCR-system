"""
auth_db.py — Gestionnaire d'authentification SQLite.

Tables :
  users    — comptes utilisateurs avec hash pbkdf2_hmac SHA-256
  sessions — tokens "remember me" (UUID4, expirables)

Compte admin par défaut créé au premier lancement :
  username : admin
  password : admin123
"""

import hashlib
import hmac
import os
import sqlite3
import uuid
from base64 import b64encode, b64decode
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path(__file__).parent.parent.parent / "data" / "ocr_database.db"


class AuthManager:
    """Gestion des utilisateurs et des sessions persistantes."""

    COOKIE_NAME = "ocr_unilog_token"
    SESSION_DAYS = 30

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    # ─────────────────────────────────────────────────────────────────────────
    # Connexion
    # ─────────────────────────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ─────────────────────────────────────────────────────────────────────────
    # Initialisation des tables
    # ─────────────────────────────────────────────────────────────────────────

    def _init_tables(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    username       TEXT    UNIQUE NOT NULL,
                    display_name   TEXT    NOT NULL,
                    email          TEXT    DEFAULT '',
                    password_hash  TEXT    NOT NULL,
                    role           TEXT    DEFAULT 'user',
                    is_active      INTEGER DEFAULT 1,
                    email_verified INTEGER DEFAULT 1,
                    created_at     TEXT    NOT NULL,
                    last_login     TEXT
                )
            """)
            # Migration : ajoute email_verified aux BDD existantes
            try:
                conn.execute(
                    "ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 1"
                )
            except Exception:
                pass  # Colonne déjà présente

            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token      TEXT PRIMARY KEY,
                    username   TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS email_verifications (
                    token      TEXT PRIMARY KEY,
                    username   TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

        # Créer les comptes par défaut s'ils n'existent pas encore
        existing = {u["username"] for u in self.list_users()}

        if "admin" not in existing:
            self.create_user(
                username="admin",
                display_name="Administrateur",
                email="admin@example.com",
                password=os.getenv("ADMIN_PASSWORD", "changeme"),
                role="admin",
                email_verified=True,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Hachage de mot de passe (pbkdf2_hmac SHA-256 + salt aléatoire)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Retourne 'salt_b64:hash_b64' — le salt est inclus dans la chaîne."""
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations=260_000,
        )
        return b64encode(salt).decode() + ":" + b64encode(key).decode()

    @staticmethod
    def verify_password(password: str, stored: str) -> bool:
        """Vérifie le mot de passe contre le hash stocké."""
        try:
            salt_b64, key_b64 = stored.split(":", 1)
            salt = b64decode(salt_b64)
            expected = b64decode(key_b64)
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                iterations=260_000,
            )
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # CRUD Utilisateurs
    # ─────────────────────────────────────────────────────────────────────────

    def create_user(
        self,
        username: str,
        display_name: str,
        email: str,
        password: str,
        role: str = "user",
        email_verified: bool = True,
    ) -> int:
        """Crée un utilisateur. Retourne l'ID ou lève ValueError si username déjà pris."""
        pwd_hash = self.hash_password(password)
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            try:
                cur = conn.execute(
                    """INSERT INTO users
                       (username, display_name, email, password_hash, role,
                        email_verified, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (username.strip().lower(), display_name.strip(), email.strip(),
                     pwd_hash, role, 1 if email_verified else 0, now),
                )
                conn.commit()
                return cur.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError(f"Le nom d'utilisateur « {username} » est déjà utilisé.")

    def verify_user(self, username: str, password: str) -> Optional[Dict]:
        """
        Vérifie les identifiants.
        Retourne le dict utilisateur si valide et actif, sinon None.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username.strip().lower(),),
            ).fetchone()
        if row is None:
            return None
        if not row["is_active"]:
            return None
        if not self.verify_password(password, row["password_hash"]):
            return None
        return dict(row)

    def get_user(self, username: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username.strip().lower(),),
            ).fetchone()
        return dict(row) if row else None

    def list_users(self) -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY role DESC, username ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def update_last_login(self, username: str):
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE username = ?",
                (now, username.strip().lower()),
            )
            conn.commit()

    def toggle_active(self, user_id: int, active: bool):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET is_active = ? WHERE id = ?",
                (1 if active else 0, user_id),
            )
            conn.commit()

    def delete_user(self, user_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.execute(
                "DELETE FROM sessions WHERE username = ("
                "  SELECT username FROM users WHERE id = ?)",
                (user_id,),
            )
            conn.commit()

    def change_password(self, username: str, new_password: str):
        pwd_hash = self.hash_password(new_password)
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (pwd_hash, username.strip().lower()),
            )
            conn.commit()

    def count_admins(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as n FROM users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()
        return row["n"] if row else 0

    # ─────────────────────────────────────────────────────────────────────────
    # Gestion des sessions persistantes (remember me)
    # ─────────────────────────────────────────────────────────────────────────

    def create_session(self, username: str, days: int = SESSION_DAYS) -> str:
        """Crée un token UUID4 valable `days` jours. Retourne le token."""
        token = str(uuid.uuid4())
        now     = datetime.utcnow()
        expires = (now + timedelta(days=days)).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO sessions (token, username, expires_at, created_at)
                   VALUES (?, ?, ?, ?)""",
                (token, username.strip().lower(), expires, now.isoformat()),
            )
            conn.commit()
        return token

    def validate_session(self, token: str) -> Optional[str]:
        """
        Vérifie si le token est valide et non expiré.
        Retourne le username ou None.
        """
        if not token:
            return None
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT username, expires_at FROM sessions WHERE token = ?",
                (token,),
            ).fetchone()
        if row is None:
            return None
        expires = datetime.fromisoformat(row["expires_at"])
        if datetime.utcnow() > expires:
            self.delete_session(token)
            return None
        return row["username"]

    def delete_session(self, token: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()

    def delete_user_sessions(self, username: str):
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM sessions WHERE username = ?",
                (username.strip().lower(),),
            )
            conn.commit()

    def cleanup_expired_sessions(self):
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            conn.commit()

    # ─────────────────────────────────────────────────────────────────────────
    # Vérification d'adresse email
    # ─────────────────────────────────────────────────────────────────────────

    def create_verification_token(self, username: str, hours: int = 24) -> str:
        """Génère un token de vérification email valable `hours` heures."""
        uname = username.strip().lower()
        # Supprimer les anciens tokens pour cet utilisateur
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM email_verifications WHERE username = ?", (uname,)
            )
            conn.commit()

        token = str(uuid.uuid4())
        now     = datetime.utcnow()
        expires = (now + timedelta(hours=hours)).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO email_verifications (token, username, expires_at, created_at)
                   VALUES (?, ?, ?, ?)""",
                (token, uname, expires, now.isoformat()),
            )
            conn.commit()
        return token

    def verify_email_token(self, token: str) -> Optional[str]:
        """
        Valide un token de vérification email.
        Si valide : marque l'email comme vérifié, supprime le token, retourne username.
        Sinon retourne None.
        """
        if not token:
            return None
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT username, expires_at FROM email_verifications WHERE token = ?",
                (token,),
            ).fetchone()
        if row is None:
            return None
        if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
            with self._get_conn() as conn:
                conn.execute(
                    "DELETE FROM email_verifications WHERE token = ?", (token,)
                )
                conn.commit()
            return None
        username = row["username"]
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET email_verified = 1 WHERE username = ?", (username,)
            )
            conn.execute(
                "DELETE FROM email_verifications WHERE token = ?", (token,)
            )
            conn.commit()
        return username

    def is_email_verified(self, username: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT email_verified FROM users WHERE username = ?",
                (username.strip().lower(),),
            ).fetchone()
        return bool(row["email_verified"]) if row else False
