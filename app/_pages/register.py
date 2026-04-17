"""Page d'inscription — Système OCR Unilog."""
import sys
import re
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

import streamlit as st
from database.auth_db import AuthManager

_auth = AuthManager()
_LOGO = Path(__file__).parent.parent.parent / "diagrams" / "uniloglogo-removebg-preview.png"

# ── CSS (identique au thème login) ────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #EEF2F7 0%, #D8E6F3 100%) !important;
}
[data-testid="stSidebar"]        { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
header[data-testid="stHeader"]   { display: none !important; }
[data-testid="stAppViewContainer"] > .main > .block-container {
    padding-top: 3rem !important;
    padding-bottom: 2rem !important;
}

/* ── Carte (colonne centrale) ── */
[data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) {
    background: #ffffff;
    border-radius: 18px;
    box-shadow: 0 8px 40px rgba(0,58,110,0.18), 0 2px 8px rgba(0,0,0,0.06);
    overflow: hidden;
    padding: 0 !important;
}
[data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) > div {
    padding: 0 !important;
}
[data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2)
    [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}

/* ── Header gradient ── */
.reg-header {
    background: linear-gradient(135deg, #005DA8 0%, #003A6E 100%);
    padding: 1.6rem 2rem 1.4rem;
    text-align: center;
    margin-bottom: 0.5rem;
}

/* ── Inputs ── */
[data-testid="stTextInput"] input {
    border: 1.5px solid #CBD8E8 !important;
    border-radius: 8px !important;
    padding: 0.50rem 0.85rem !important;
    font-size: 0.88rem !important;
    background: #F7FAFD !important;
    transition: border-color 0.2s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #0088DD !important;
    box-shadow: 0 0 0 3px rgba(0,136,221,0.12) !important;
    background: #ffffff !important;
}
[data-testid="stTextInput"] label {
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    color: #1E2D40 !important;
}

/* ── Bouton principal ── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #0055A5, #003A6E) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.62rem 1rem !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    width: 100% !important;
    cursor: pointer !important;
    transition: opacity 0.2s !important;
    letter-spacing: 0.01em !important;
}
.stButton > button[kind="primary"]:hover { opacity: 0.88 !important; }

/* ── Bouton secondaire (retour login) ── */
.stButton > button[kind="secondary"] {
    background: transparent !important;
    color: #0055A5 !important;
    border: 1.5px solid #CBD8E8 !important;
    border-radius: 10px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    width: 100% !important;
    transition: all 0.18s !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #EEF5FC !important;
    border-color: #0088DD !important;
    color: #003A6E !important;
}

/* ── Alertes ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    font-size: 0.83rem !important;
}

/* ── Footer ── */
.reg-footer {
    text-align: center;
    color: #7A95B0;
    font-size: 0.75rem;
    margin-top: 1.2rem;
}

/* ── Séparateur de champs ── */
.field-sep { height: 0.3rem; }
</style>
""", unsafe_allow_html=True)

# ── Logo ───────────────────────────────────────────────────────────────────────
logo_b64 = ""
if _LOGO.exists():
    import base64
    logo_b64 = base64.b64encode(_LOGO.read_bytes()).decode()

# ── Mise en page ───────────────────────────────────────────────────────────────
_, col_center, _ = st.columns([1, 2, 1])

with col_center:

    # Bloc 1 — Logo seul (isole le base64)
    if logo_b64:
        st.markdown(
            '<div style="'
            'background:linear-gradient(135deg,#005DA8 0%,#003A6E 100%);'
            'padding:1.4rem 2rem 0;text-align:center;">'
            f'<img src="data:image/png;base64,{logo_b64}"'
            ' style="height:55px;" alt="Unilog">'
            '</div>',
            unsafe_allow_html=True,
        )

    # Bloc 2 — Titre (aucun base64, divs simples)
    _pad_top = "0.5rem" if logo_b64 else "1.8rem"
    st.markdown(
        f'<div class="reg-header" style="padding-top:{_pad_top};">'
        '<div style="color:#ffffff;font-size:1.25rem;font-weight:700;'
        'margin-bottom:0.25rem;letter-spacing:-0.02em;">Créer un compte</div>'
        '<div style="color:rgba(255,255,255,0.7);font-size:0.80rem;">'
        'Rejoignez la plateforme OCR Unilog</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Formulaire d'inscription ────────────────────────────────────────────
    st.markdown('<div style="padding:0 1.8rem;">', unsafe_allow_html=True)

    # Nom d'utilisateur
    username_input = st.text_input(
        "Nom d'utilisateur *",
        placeholder="ex : marie.dupont",
        key="reg_username",
    )

    # Nom complet
    display_name_input = st.text_input(
        "Nom complet *",
        placeholder="ex : Marie Dupont",
        key="reg_displayname",
    )

    # Email
    email_input = st.text_input(
        "Adresse e-mail *",
        placeholder="marie@unilog.com",
        key="reg_email",
    )

    # Mot de passe
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        password_input = st.text_input(
            "Mot de passe *",
            type="password",
            placeholder="Minimum 6 caractères",
            key="reg_password",
        )
    with col_p2:
        confirm_input = st.text_input(
            "Confirmer le mot de passe *",
            type="password",
            placeholder="Répéter",
            key="reg_confirm",
        )

    # Indicateur de force du mot de passe
    if password_input:
        _score = (
            len(password_input) >= 8
            + any(c.isupper() for c in password_input)
            + any(c.isdigit() for c in password_input)
            + any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password_input)
        )
        _strength_label, _strength_color = {
            0: ("Très faible", "#CC3333"),
            1: ("Faible",      "#E65100"),
            2: ("Moyen",       "#C07C00"),
            3: ("Fort",        "#18A055"),
            4: ("Très fort",   "#0D6B35"),
        }.get(_score, ("—", "#888"))
        _bar_pct = _score * 25
        st.markdown(
            f'<div style="margin-top:0.3rem;margin-bottom:0.1rem;">'
            f'<div style="height:4px;background:#E8EEF5;border-radius:2px;">'
            f'<div style="height:4px;width:{_bar_pct}%;background:{_strength_color};'
            f'border-radius:2px;transition:width 0.3s;"></div></div>'
            f'<span style="font-size:0.72rem;color:{_strength_color};font-weight:600;">'
            f'Force : {_strength_label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Bouton S'inscrire ───────────────────────────────────────────────────
    _bl, _bm, _br = st.columns([0.12, 1, 0.12])
    with _bm:
        register_btn = st.button("Créer mon compte", type="primary",
                                 use_container_width=True, key="reg_submit")

    # ── Traitement de l'inscription ─────────────────────────────────────────
    if register_btn:
        _EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
        errors = []

        if not username_input.strip():
            errors.append("Le nom d'utilisateur est obligatoire.")
        elif len(username_input.strip()) < 3:
            errors.append("Le nom d'utilisateur doit comporter au moins 3 caractères.")
        elif not re.match(r"^[a-zA-Z0-9._-]+$", username_input.strip()):
            errors.append("Le nom d'utilisateur ne peut contenir que des lettres, chiffres, points, tirets et underscores.")

        if not display_name_input.strip():
            errors.append("Le nom complet est obligatoire.")

        if not email_input.strip():
            errors.append("L'adresse e-mail est obligatoire.")
        elif not _EMAIL_RE.match(email_input.strip()):
            errors.append("L'adresse e-mail n'est pas valide.")

        if not password_input:
            errors.append("Le mot de passe est obligatoire.")
        elif len(password_input) < 6:
            errors.append("Le mot de passe doit comporter au moins 6 caractères.")
        elif password_input != confirm_input:
            errors.append("Les deux mots de passe ne correspondent pas.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            try:
                _new_id = _auth.create_user(
                    username=username_input.strip(),
                    display_name=display_name_input.strip(),
                    email=email_input.strip(),
                    password=password_input,
                    role="user",          # toujours "user" à l'inscription publique
                    email_verified=False, # nécessite confirmation par email
                )
                # Générer le token et envoyer l'email de confirmation
                try:
                    from email_sender import send_verification_email
                    _token = _auth.create_verification_token(username_input.strip())
                    _sent  = send_verification_email(
                        email_input.strip(),
                        display_name_input.strip(),
                        _token,
                    )
                    if _sent:
                        st.success(
                            f"Compte créé ! Un email de vérification a été envoyé à "
                            f"**{email_input.strip()}**. "
                            f"Cliquez sur le lien dans l'email pour activer votre compte."
                        )
                    else:
                        st.warning(
                            f"Compte **{display_name_input.strip()}** créé, mais "
                            f"l'envoi de l'email de vérification a échoué. "
                            f"Contactez l'administrateur pour activer votre compte."
                        )
                except Exception:
                    st.warning(
                        f"Compte **{display_name_input.strip()}** créé. "
                        f"Contactez l'administrateur pour activer votre compte."
                    )
                st.session_state["reg_success"] = True
            except ValueError as ve:
                st.error(str(ve))

    # ── Bouton retour + message succès ──────────────────────────────────────
    st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)

    _bl2, _bm2, _br2 = st.columns([0.12, 1, 0.12])
    with _bm2:
        if st.button(
            "Déjà un compte ? Se connecter",
            use_container_width=True,
            key="reg_to_login",
        ):
            st.session_state.pop("_show_register", None)
            st.session_state.pop("reg_success", None)
            st.rerun()

    st.markdown('<div style="height:1.2rem"></div>', unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="reg-footer">'
    'Unilog OCR System &mdash; PFE 2025-2026 &nbsp;·&nbsp; Goubaa Hanen'
    '</div>',
    unsafe_allow_html=True,
)
