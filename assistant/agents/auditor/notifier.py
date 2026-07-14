"""
Outil de notification email — Agent 2 : L'Auditeur.

Déclenche un email d'alerte si au moins une condition est remplie :
  1. Échéance dépassée ou dans ≤ ALERT_DEADLINE_DAYS jours (défaut : 2)
  2. Montant TTC > ALERT_MONTANT_RATIO × moyenne des documents du même type en DB
     (fallback : montant_ttc > ALERT_THRESHOLD_DT si historique insuffisant)
  3. Nouveau document (jamais vu en base) ET montant TTC > ALERT_NOUVEAU_MONTANT_DT (défaut : 4000 DT)

Variables à ajouter dans assistant/.env :
  GMAIL_SENDER             adresse Gmail expéditrice (ex: toncompte@gmail.com)
  GMAIL_APP_PASSWORD       mot de passe d'application Google (16 caractères)
  ALERT_EMAIL_TO           destinataire (ex: destinataire@example.com)
  ALERT_DEADLINE_DAYS      jours avant échéance pour alerter (défaut : 2)
  ALERT_THRESHOLD_DT       seuil fixe de repli en DT si pas d'historique (défaut : 5000)
  ALERT_MONTANT_RATIO      ratio vs moyenne DB pour déclencher l'alerte (défaut : 3.0)
  ALERT_NOUVEAU_MONTANT_DT seuil en DT pour un NOUVEAU document (défaut : 4000)
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
# Google affiche le mot de passe d'application avec des espaces ("xxxx xxxx xxxx xxxx") —
# on les retire car Gmail SMTP refuse l'authentification si le mot de passe les contient.
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
    Compare le montant du document courant contre la moyenne des documents
    du même type (facture ou traite) présents en base PostgreSQL.

    Retourne une chaîne de raison d'alerte, ou None si pas d'alerte.
    Nécessite au moins 3 documents du même type pour être fiable.
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
        # Pas assez d'historique → fallback seuil fixe
        if montant_ttc > ALERT_THRESHOLD_DT:
            type_label = "traite" if is_t else "facture"
            return (f"Montant TTC ({montant_ttc:,.3f} DT) dépasse le seuil de "
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
    Alerte si le document est NOUVEAU (jamais vu en base) et que son montant TTC
    dépasse ALERT_NOUVEAU_MONTANT_DT (défaut : 4000 DT).

    Retourne une chaîne de raison d'alerte, ou None si pas d'alerte.
    """
    if not is_nouveau or montant_ttc is None or montant_ttc <= 0:
        return None
    if montant_ttc > ALERT_NOUVEAU_MONTANT_DT:
        return (f"Nouveau document détecté avec un montant TTC élevé "
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
    Retourne la liste des raisons d'alerte (liste vide = pas d'alerte).

    Conditions :
      1. Échéance dépassée ou dans ≤ ALERT_DEADLINE_DAYS jours
      2. Montant TTC anormal vs historique du même type (ou > seuil fixe si pas d'historique)
      3. Nouveau document ET montant TTC > ALERT_NOUVEAU_MONTANT_DT
    """
    alerts = []

    # ── Condition 1 : Échéance ────────────────────────────────────────────────
    echeance = _parse_date(date_echeance)
    if echeance is not None:
        delta = (echeance - date.today()).days
        if delta < 0:
            alerts.append(
                f"Échéance dépassée depuis {-delta} jour(s) — {echeance.strftime('%d/%m/%Y')}"
            )
        elif delta <= ALERT_DEADLINE_DAYS:
            alerts.append(
                f"Échéance dans {delta} jour(s) — {echeance.strftime('%d/%m/%Y')} "
                f"(seuil d'alerte : {ALERT_DEADLINE_DAYS} jour(s))"
            )

    # ── Condition 2 : Montant anormal vs historique ───────────────────────────
    raison_montant = check_montant_vs_historique(montant_ttc, doc_type, historique or [])
    if raison_montant:
        alerts.append(raison_montant)

    # ── Condition 3 : Nouveau document + montant élevé ────────────────────────
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
    Retourne True si l'envoi réussit, False sinon.
    """
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        print("[NOTIFIER] GMAIL_SENDER ou GMAIL_APP_PASSWORD absent dans .env → email désactivé")
        return False

    doc_type_label = "Lettre de change" if _is_traite_type(doc_type) else "Facture"
    montant_str    = f"{montant_ttc:,.3f} DT" if montant_ttc is not None else "Non disponible"
    now_str        = datetime.now().strftime("%d/%m/%Y à %H:%M")

    statut_map = {
        "VALIDÉ"                 : "Validé — aucune erreur détectée",
        "ERREUR_CALCUL"          : "Erreur de calcul sur les lignes d'articles",
        "ERREUR_MONTANT_LETTRES" : "Incohérence lettres/chiffres",
        "DOUBLON"                : "Document déjà enregistré (doublon)",
        "SIGNATURE_MANQUANTE"    : "Signature ou tampon manquant",
        "ECHEANCE_DEPASSEE"      : "Échéance dépassée",
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
        print(f"[NOTIFIER] Email envoyé à {ALERT_EMAIL_TO} ({len(alerts)} alerte(s))")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[NOTIFIER] Authentification Gmail échouée — vérifier GMAIL_APP_PASSWORD dans .env")
        return False
    except Exception as exc:
        print(f"[NOTIFIER] Échec envoi email : {exc}")
        return False
