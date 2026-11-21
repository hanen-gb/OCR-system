"""
Outil de notification email — Agent 2 : L'Auditeur.

Sends an alert e-mail when at least one condition is met:
  1. Due date passed or within ≤ ALERT_DEADLINE_DAYS days (default: 2)
  2. Total amount incl. VAT > ALERT_MONTANT_RATIO × average of the documents of the same type in the database
     (fallback : montant_ttc > ALERT_THRESHOLD_DT si historique insuffisant)
  3. New document (never seen in the database) AND total amount incl. VAT > ALERT_NOUVEAU_MONTANT_DT (default: 4000 TND)

Variables to add to assistant/.env:
  GMAIL_SENDER             sender Gmail address (e.g. expediteur@gmail.com)
  GMAIL_APP_PASSWORD       Google application password (16 characters)
  ALERT_EMAIL_TO           destinataire (ex: destinataire@example.com)
  ALERT_DEADLINE_DAYS      days before the due date to send an alert (default: 2)
  ALERT_THRESHOLD_DT       fixed fallback threshold in TND when there is no history (default: 5000)
  ALERT_MONTANT_RATIO      ratio vs database average that triggers the alert (default: 3.0)
  ALERT_NOUVEAU_MONTANT_DT threshold in TND for a NEW document (default: 4000)
"""

import os
import smtplib
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ALERT_THRESHOLD_DT       = float(os.getenv("ALERT_THRESHOLD_DT",       "5000"))
ALERT_DEADLINE_DAYS      = int(os.getenv("ALERT_DEADLINE_DAYS",        "2"))
ALERT_MONTANT_RATIO      = float(os.getenv("ALERT_MONTANT_RATIO",      "3.0"))
ALERT_NOUVEAU_MONTANT_DT = float(os.getenv("ALERT_NOUVEAU_MONTANT_DT", "4000"))
ALERT_EMAIL_TO           = os.getenv("ALERT_EMAIL_TO",                 "")
GMAIL_SENDER             = os.getenv("GMAIL_SENDER",                   "")
# Google shows the application password with spaces ("xxxx xxxx xxxx xxxx") —
# they are removed because Gmail SMTP rejects the login when the password contains them.
GMAIL_APP_PASSWORD       = os.getenv("GMAIL_APP_PASSWORD",             "").replace(" ", "")

_DATE_FORMATS = [
    "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y",
    "%d/%m/%y", "%Y/%m/%d", "%d.%m.%Y",
]


def _parse_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _is_traite_type(doc_type: str | None) -> bool:
    return bool(doc_type and any(k in (doc_type or "").lower()
                                 for k in ("lettre", "change", "traite", "billet")))


def check_montant_vs_historique(
    montant_ttc: float | None,
    doc_type: str | None,
    historique: list,
) -> str | None:
    """
    Compares the amount of the current document with the average amount of the
    documents of the same type (invoice or bill) stored in PostgreSQL.

    Returns an alert reason string, or None when there is no alert.
    Requires at least 3 documents of the same type to be reliable.
    """
    if montant_ttc is None or montant_ttc <= 0:
        return None

    is_t = _is_traite_type(doc_type)
    docs_meme_type = [
        d for d in (historique or [])
        if _is_traite_type(d.get("doc_type")) == is_t
        and d.get("montant") is not None
        and float(d["montant"]) > 0
    ]

    if len(docs_meme_type) < 3:
        # Not enough history → fixed threshold fallback
        if montant_ttc > ALERT_THRESHOLD_DT:
            type_label = "traite" if is_t else "facture"
            return (f"Total amount incl. VAT ({montant_ttc:,.3f} TND) exceeds the threshold of "
                    f"{ALERT_THRESHOLD_DT:,.0f} DT (historique insuffisant pour comparaison)")
        return None

    montants  = [float(d["montant"]) for d in docs_meme_type]
    moyenne   = sum(montants) / len(montants)
    type_label = "traites" if is_t else "factures"

    if montant_ttc > moyenne * ALERT_MONTANT_RATIO:
        ratio = montant_ttc / moyenne
        return (f"Montant TTC ({montant_ttc:,.3f} DT) est {ratio:.1f}× la moyenne des "
                f"{type_label} en base ({moyenne:,.3f} DT sur {len(docs_meme_type)} doc(s))")

    return None


def check_nouveau_montant_eleve(
    montant_ttc: float | None,
    is_nouveau : bool,
) -> str | None:
    """
    Alerts when the document is NEW (never seen in the database) and its total amount
    incl. VAT exceeds ALERT_NOUVEAU_MONTANT_DT (default: 4000 TND).

    Returns an alert reason string, or None when there is no alert.
    """
    if not is_nouveau or montant_ttc is None or montant_ttc <= 0:
        return None
    if montant_ttc > ALERT_NOUVEAU_MONTANT_DT:
        return (f"New document detected with a high total amount incl. VAT "
                f"({montant_ttc:,.3f} DT > seuil de {ALERT_NOUVEAU_MONTANT_DT:,.0f} DT)")
    return None


def check_alert_conditions(
    montant_ttc   : float | None,
    date_echeance : str | None,
    doc_type      : str | None = None,
    historique    : list | None = None,
    is_nouveau    : bool = False,
) -> list[str]:
    """
    Returns the list of alert reasons (empty list = no alert).

    Conditions :
      1. Due date passed or within ≤ ALERT_DEADLINE_DAYS days
      2. Abnormal total amount compared with the history of the same type (or > fixed threshold without history)
      3. New document AND total amount incl. VAT > ALERT_NOUVEAU_MONTANT_DT
    """
    alerts = []

    # ── Condition 1: due date ─────────────────────────────────────────────────
    echeance = _parse_date(date_echeance)
    if echeance is not None:
        delta = (echeance - date.today()).days
        if delta < 0:
            alerts.append(
                f"Due date passed {-delta} day(s) ago — {echeance.strftime('%d/%m/%Y')}"
            )
        elif delta <= ALERT_DEADLINE_DAYS:
            alerts.append(
                f"Due in {delta} day(s) — {echeance.strftime('%d/%m/%Y')} "
                f"(seuil d'alerte : {ALERT_DEADLINE_DAYS} jour(s))"
            )

    # ── Condition 2: abnormal amount vs history ──────────────────────────────
    raison_montant = check_montant_vs_historique(montant_ttc, doc_type, historique or [])
    if raison_montant:
        alerts.append(raison_montant)

    # ── Condition 3: new document + high amount ───────────────────────────────
    raison_nouveau = check_nouveau_montant_eleve(montant_ttc, is_nouveau)
    if raison_nouveau:
        alerts.append(raison_nouveau)

    return alerts


def send_alert_email(
    alerts         : list[str],
    doc_type       : str | None,
    doc_number     : str | None,
    fournisseur    : str | None,
    montant_ttc    : float | None,
    date_echeance  : str | None,
    status_validite: str | None,
) -> bool:
    """
    Envoie l'email d'alerte via Gmail SMTP (port 587, STARTTLS).
    Returns True if the e-mail was sent, False otherwise.
    """
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        print("[NOTIFIER] GMAIL_SENDER or GMAIL_APP_PASSWORD missing in .env → e-mail disabled")
        return False

    doc_type_label = "Lettre de change" if _is_traite_type(doc_type) else "Facture"
    montant_str    = f"{montant_ttc:,.3f} DT" if montant_ttc is not None else "Non disponible"
    now_str        = datetime.now().strftime("%d/%m/%Y at %H:%M")

    statut_map = {
        "VALIDÉ"                 : "Validated — no error detected",
        "ERREUR_CALCUL"          : "Calculation error on the item lines",
        "ERREUR_MONTANT_LETTRES" : "Amount in words and figures do not match",
        "DOUBLON"                : "Document already stored (duplicate)",
        "SIGNATURE_MANQUANTE"    : "Signature ou tampon manquant",
        "ECHEANCE_DEPASSEE"      : "Due date passed",
    }
    statut_texte  = statut_map.get(status_validite or "", status_validite or "Non disponible")
    alertes_texte = "\n".join(f"  ⚠ {a}" for a in alerts)

    corps = f"""\
Bonjour,

Un document traité par le système OCR nécessite votre attention.

────────────────────────────────────────────
INFORMATIONS DU DOCUMENT
────────────────────────────────────────────
Type              : {doc_type_label}
Numéro            : {doc_number or "Non disponible"}
Fournisseur       : {fournisseur or "Non disponible"}
Montant TTC       : {montant_str}
Date d'échéance   : {date_echeance or "Non applicable"}
Résultat audit    : {statut_texte}

────────────────────────────────────────────
POINT(S) NÉCESSITANT VOTRE ATTENTION
────────────────────────────────────────────
{alertes_texte}

────────────────────────────────────────────

Merci de vérifier ce document dans les meilleurs délais.

Cordialement,
Système de Gestion Documentaire — OCR PFE GLM
(Message généré automatiquement le {now_str})
"""

    subject = f"[Alerte OCR] {doc_type_label} N° {doc_number or '?'} — {alerts[0][:80]}"

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
        print(f"[NOTIFIER] E-mail sent to {ALERT_EMAIL_TO} ({len(alerts)} alert(s))")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[NOTIFIER] Gmail authentication failed — check GMAIL_APP_PASSWORD in .env")
        return False
    except Exception as exc:
        print(f"[NOTIFIER] E-mail sending failed: {exc}")
        return False
