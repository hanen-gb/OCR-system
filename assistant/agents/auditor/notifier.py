"""
Outil de notification email — Agent 2 : L'Auditeur.

Déclenche un email d'alerte si au moins une condition est remplie :
  1. Montant TTC > ALERT_THRESHOLD_DT  (défaut : 5 000 DT)
  2. Échéance dans ≤ ALERT_DEADLINE_DAYS jours (défaut : 7)
     ou échéance déjà dépassée

Variables à ajouter dans assistant/.env :
  GMAIL_SENDER        adresse Gmail expéditrice (ex: toncompte@gmail.com)
  GMAIL_APP_PASSWORD  mot de passe d'application Google (16 caractères, PAS le mot de passe principal)
  ALERT_EMAIL_TO      destinataire (ex: destinataire@example.com)
  ALERT_THRESHOLD_DT  seuil financier en DT (défaut : 5000)
  ALERT_DEADLINE_DAYS jours avant échéance (défaut : 7)

Comment générer GMAIL_APP_PASSWORD :
  1. myaccount.google.com → Sécurité → Validation en 2 étapes (activer)
  2. myaccount.google.com → Sécurité → Mots de passe des applications
  3. Créer → Autre → "OCR System" → Copier les 16 caractères
"""

import os
import smtplib
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ALERT_THRESHOLD_DT  = float(os.getenv("ALERT_THRESHOLD_DT",  "5000"))
ALERT_DEADLINE_DAYS = int(os.getenv("ALERT_DEADLINE_DAYS",   "7"))
ALERT_EMAIL_TO      = os.getenv("ALERT_EMAIL_TO",            "expediteur@gmail.com")
GMAIL_SENDER        = os.getenv("GMAIL_SENDER",              "")
GMAIL_APP_PASSWORD  = os.getenv("GMAIL_APP_PASSWORD",        "")

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


def check_alert_conditions(
    montant_ttc: float | None,
    date_echeance: str | None,
) -> list[str]:
    """
    Retourne la liste des raisons d'alerte (liste vide = pas d'alerte).

    Conditions :
      1. montant_ttc > ALERT_THRESHOLD_DT
      2. date_echeance dans ≤ ALERT_DEADLINE_DAYS jours ou déjà dépassée
    """
    alerts = []

    if montant_ttc is not None and montant_ttc > ALERT_THRESHOLD_DT:
        alerts.append(
            f"Montant TTC ({montant_ttc:,.3f} DT) dépasse le seuil de {ALERT_THRESHOLD_DT:,.0f} DT"
        )

    echeance = _parse_date(date_echeance)
    if echeance is not None:
        delta = (echeance - date.today()).days
        if delta < 0:
            alerts.append(
                f"Échéance dépassée depuis {-delta} jour(s) — {echeance.strftime('%d/%m/%Y')}"
            )
        elif delta <= ALERT_DEADLINE_DAYS:
            alerts.append(
                f"Échéance dans {delta} jour(s) — {echeance.strftime('%d/%m/%Y')}"
            )

    return alerts


def send_alert_email(
    alerts: list[str],
    doc_type: str | None,
    doc_number: str | None,
    fournisseur: str | None,
    montant_ttc: float | None,
    date_echeance: str | None,
    status_validite: str | None,
) -> bool:
    """
    Envoie l'email d'alerte via Gmail SMTP (port 587, STARTTLS).
    Retourne True si l'envoi réussit, False sinon.
    """
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        print("[NOTIFIER] GMAIL_SENDER ou GMAIL_APP_PASSWORD absent dans .env → email désactivé")
        return False

    doc_type_label = "Lettre de change" if "lettre" in (doc_type or "") else "Facture"
    montant_str    = f"{montant_ttc:,.3f} DT" if montant_ttc is not None else "Non disponible"
    now_str        = datetime.now().strftime("%d/%m/%Y à %H:%M")

    statut_map = {
        "VALIDÉ"                 : "Validé — aucune erreur détectée",
        "ERREUR_CALCUL"          : "Erreur de calcul sur les lignes d'articles",
        "ERREUR_TVA"             : "Incohérence dans le montant de la TVA",
        "ERREUR_NET_A_PAYER"     : "Incohérence dans le montant net à payer",
        "ERREUR_MONTANT_LETTRES" : "Incohérence lettres/chiffres",
        "DOUBLON"                : "Document déjà enregistré (doublon)",
        "SIGNATURE_MANQUANTE"    : "Signature ou tampon manquant",
    }
    statut_texte  = statut_map.get(status_validite or "", status_validite or "Non disponible")
    alertes_texte = "\n".join(f"  - {a}" for a in alerts)

    corps = f"""\
Bonjour,

Un document a été traité par le système OCR et nécessite votre attention.

------------------------------------------------------------
INFORMATIONS DU DOCUMENT
------------------------------------------------------------
Type              : {doc_type_label}
Numéro            : {doc_number or "Non disponible"}
Fournisseur       : {fournisseur or "Non disponible"}
Montant TTC       : {montant_str}
Date d'échéance   : {date_echeance or "Non disponible"}
Résultat de l'audit : {statut_texte}

------------------------------------------------------------
POINT(S) NÉCESSITANT VOTRE ATTENTION
------------------------------------------------------------
{alertes_texte}

------------------------------------------------------------

Merci de vérifier ce document dans les meilleurs délais.

Cordialement,
Le Système de Gestion Documentaire — OCR PFE
(Message généré automatiquement le {now_str})
"""

    subject = f"[Action requise] {doc_type_label} N° {doc_number or '?'} — {alerts[0]}"

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
        print(f"[NOTIFIER] Email envoyé à {ALERT_EMAIL_TO} ({len(alerts)} alerte(s))")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[NOTIFIER] Authentification Gmail échouée — vérifier GMAIL_APP_PASSWORD dans .env")
        return False
    except Exception as exc:
        print(f"[NOTIFIER] Échec envoi email : {exc}")
        return False
