"""
Rapport consolidé quotidien — envoyé chaque matin à 8h00.
Récapitule tous les documents présents en base SQLite.
"""

import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from agents.auditor.db import list_documents
from agents.auditor.notifier import (
    GMAIL_SENDER, GMAIL_APP_PASSWORD, ALERT_EMAIL_TO, _is_traite_type,
)


def _fmt_montant(val) -> str:
    try:
        return f"{float(val):,.3f} DT" if val is not None else "—"
    except (TypeError, ValueError):
        return "—"


def send_daily_report() -> bool:
    """Génère et envoie le rapport consolidé quotidien par email."""
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        print("[DAILY] Email désactivé (GMAIL_SENDER/GMAIL_APP_PASSWORD manquants dans .env)")
        return False

    docs = list_documents(limit=500)
    maintenant = datetime.now()
    hier = maintenant - timedelta(hours=24)

    docs_recent = []
    for d in docs:
        fs = d.get("first_seen") or ""
        try:
            dt = datetime.fromisoformat(fs.replace("Z", "+00:00").replace("+00:00", ""))
            if dt >= hier:
                docs_recent.append(d)
        except (ValueError, TypeError):
            pass

    nb_factures = sum(1 for d in docs if not _is_traite_type(d.get("doc_type")))
    nb_traites  = sum(1 for d in docs if _is_traite_type(d.get("doc_type")))

    montants      = [float(d["montant"]) for d in docs if d.get("montant") is not None]
    total_montant = sum(montants) if montants else 0.0
    moy_montant   = total_montant / len(montants) if montants else 0.0

    # Lignes des documents récents (max 25)
    lignes = ""
    for d in docs_recent[:25]:
        t   = ("TRAITE" if _is_traite_type(d.get("doc_type")) else "FACTURE")
        num = (d.get("doc_number") or "—")[:18]
        fou = (d.get("fournisseur") or "—")[:22]
        mnt = _fmt_montant(d.get("montant"))
        lignes += f"  • {t:7s} | N° {num:18s} | {fou:22s} | {mnt}\n"
    if not lignes:
        lignes = "  Aucun document traité dans les dernières 24h.\n"

    nb_recents = len(docs_recent)
    date_str   = maintenant.strftime("%d/%m/%Y")
    now_str    = maintenant.strftime("%d/%m/%Y à %H:%M")

    corps = f"""\
Bonjour,

Rapport consolidé quotidien — {date_str}

═══════════════════════════════════════════
STATISTIQUES GLOBALES (base complète)
═══════════════════════════════════════════
Total documents enregistrés : {len(docs)}
  dont Factures              : {nb_factures}
  dont Traites / LC          : {nb_traites}

Montant total TTC            : {_fmt_montant(total_montant)}
Montant moyen TTC            : {_fmt_montant(moy_montant)}

═══════════════════════════════════════════
DOCUMENTS TRAITÉS CES DERNIÈRES 24H ({nb_recents})
═══════════════════════════════════════════
{lignes}
═══════════════════════════════════════════

Pour consulter les détails complets, ouvrez la page Documents
de l'application de gestion documentaire.

Cordialement,
Système de Gestion Documentaire — OCR PFE GLM
(Rapport généré automatiquement le {now_str})
"""

    subject = (f"[Rapport Quotidien OCR] {date_str} — "
               f"{len(docs)} documents | {nb_recents} nouveaux")

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = ALERT_EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(corps, "plain", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, ALERT_EMAIL_TO, msg.as_string())
        print(f"[DAILY] Rapport quotidien envoyé à {ALERT_EMAIL_TO}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[DAILY] Authentification Gmail échouée — vérifier GMAIL_APP_PASSWORD")
        return False
    except Exception as exc:
        print(f"[DAILY] Échec envoi rapport quotidien : {exc}")
        return False
