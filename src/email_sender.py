"""
email_sender.py — Envoi d'emails transactionnels via Gmail SMTP.

Variables d'environnement requises (fichier .env à la racine du projet) :
  GMAIL_ADDRESS      — adresse Gmail expéditrice (ex: expediteur@gmail.com)
  GMAIL_APP_PASSWORD — mot de passe d'application Google (16 caractères, sans espaces)
  APP_BASE_URL       — URL publique de l'application (ex: http://localhost:8501)
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Charger le .env s'il existe
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

GMAIL_ADDRESS     = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
APP_BASE_URL      = os.getenv("APP_BASE_URL", "http://localhost:8501")


def send_verification_email(to_email: str, display_name: str, token: str) -> bool:
    """
    Envoie un email de vérification d'adresse via Gmail SMTP.
    Retourne True si l'envoi réussit, False sinon.
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return False

    link = f"{APP_BASE_URL}/?verify_token={token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Vérifiez votre adresse email — Unilog OCR"
    msg["From"]    = f"Unilog OCR System <{GMAIL_ADDRESS}>"
    msg["To"]      = to_email

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#EEF2F7;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 20px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,58,110,0.12);max-width:100%;">

        <!-- En-tête gradient Unilog -->
        <tr>
          <td style="background:linear-gradient(135deg,#005DA8 0%,#003A6E 100%);
                     padding:30px 40px;text-align:center;">
            <div style="color:#ffffff;font-size:20px;font-weight:700;
                        letter-spacing:-0.4px;margin-bottom:6px;">
              Unilog OCR System
            </div>
            <div style="color:rgba(255,255,255,0.72);font-size:13px;">
              Confirmation de votre adresse email
            </div>
          </td>
        </tr>

        <!-- Corps -->
        <tr>
          <td style="padding:36px 40px;">
            <p style="color:#1E2D40;font-size:15px;margin:0 0 14px;font-weight:600;">
              Bonjour {display_name},
            </p>
            <p style="color:#4A6080;font-size:14px;line-height:1.7;margin:0 0 28px;">
              Merci pour votre inscription sur la plateforme OCR Unilog.<br>
              Cliquez sur le bouton ci-dessous pour confirmer votre adresse
              et activer votre compte.
            </p>

            <!-- Bouton -->
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td align="center" style="padding-bottom:28px;">
                  <a href="{link}"
                     style="display:inline-block;
                            background:linear-gradient(135deg,#0055A5 0%,#003A6E 100%);
                            color:#ffffff;text-decoration:none;
                            font-size:15px;font-weight:600;
                            padding:14px 38px;border-radius:10px;
                            letter-spacing:0.01em;">
                    ✉ Vérifier mon adresse email
                  </a>
                </td>
              </tr>
            </table>

            <p style="color:#A0B4C8;font-size:12px;margin:0 0 6px;">
              Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :
            </p>
            <p style="margin:0 0 28px;">
              <a href="{link}"
                 style="color:#0055A5;font-size:12px;word-break:break-all;">
                {link}
              </a>
            </p>

            <hr style="border:none;border-top:1px solid #E8EEF5;margin:0 0 20px;">
            <p style="color:#B0C4D8;font-size:11px;margin:0;text-align:center;
                      line-height:1.6;">
              Ce lien expire dans <strong>24 heures</strong>.<br>
              Si vous n'avez pas créé ce compte, ignorez cet email.
            </p>
          </td>
        </tr>

        <!-- Pied de page -->
        <tr>
          <td style="background:#F7FAFD;padding:16px 40px;text-align:center;
                     border-top:1px solid #E8EEF5;">
            <span style="color:#A0B4C8;font-size:11px;">
              Unilog OCR System &mdash; PFE 2025-2026 &nbsp;&middot;&nbsp; Goubaa Hanen
            </span>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except Exception:
        return False
