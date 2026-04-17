"""Page de vérification d'adresse email — Système OCR Unilog."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

import streamlit as st
from database.auth_db import AuthManager

_auth = AuthManager()
_LOGO = Path(__file__).parent.parent.parent / "diagrams" / "uniloglogo-removebg-preview.png"

# ── CSS (même charte que login / register) ────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #EEF2F7 0%, #D8E6F3 100%) !important;
}
[data-testid="stSidebar"]        { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
header[data-testid="stHeader"]   { display: none !important; }
[data-testid="stAppViewContainer"] > .main > .block-container {
    padding-top: 3.5rem !important;
    padding-bottom: 2rem !important;
}

/* ── Carte centrale ── */
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
}
.stButton > button[kind="primary"]:hover { opacity: 0.88 !important; }

/* ── Alertes ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    font-size: 0.85rem !important;
}

/* ── Footer ── */
.vfy-footer {
    text-align: center;
    color: #7A95B0;
    font-size: 0.75rem;
    margin-top: 1.2rem;
}
</style>
""", unsafe_allow_html=True)

# ── Logo base64 ───────────────────────────────────────────────────────────────
logo_b64 = ""
if _LOGO.exists():
    import base64
    logo_b64 = base64.b64encode(_LOGO.read_bytes()).decode()

# ── Token depuis l'URL ────────────────────────────────────────────────────────
_token = st.query_params.get("verify_token", "")

# ── Mise en page ─────────────────────────────────────────────────────────────
_, col_center, _ = st.columns([1, 2, 1])

with col_center:

    # Bloc 1 — Logo (base64 isolé)
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

    # Bloc 2 — Titre
    _pad_top = "0.5rem" if logo_b64 else "1.8rem"
    st.markdown(
        f'<div class="reg-header" style="'
        f'background:linear-gradient(135deg,#005DA8 0%,#003A6E 100%);'
        f'padding:{_pad_top} 2rem 1.4rem;text-align:center;margin-bottom:0.5rem;">'
        '<div style="color:#ffffff;font-size:1.20rem;font-weight:700;'
        'margin-bottom:0.25rem;letter-spacing:-0.02em;">Vérification d\'email</div>'
        '<div style="color:rgba(255,255,255,0.7);font-size:0.80rem;">'
        'Activation de votre compte Unilog</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div style="padding:1.5rem 1.8rem;">', unsafe_allow_html=True)

    # ── Traitement du token ───────────────────────────────────────────────────
    if not _token:
        st.error("Lien de vérification invalide ou manquant.")
    else:
        _username = _auth.verify_email_token(_token)
        if _username:
            _user = _auth.get_user(_username)
            _dname = _user["display_name"] if _user else _username
            st.success(
                f"Votre adresse email a été vérifiée avec succès ! "
                f"Bienvenue, **{_dname}**. "
                f"Vous pouvez maintenant vous connecter."
            )
            st.session_state.pop("_show_register", None)
        else:
            st.error(
                "Ce lien de vérification est invalide ou a expiré (durée : 24 h). "
                "Connectez-vous et demandez un nouvel email de vérification."
            )

    st.markdown('<div style="height:0.8rem"></div>', unsafe_allow_html=True)

    # Bouton retour connexion
    _bl, _bm, _br = st.columns([0.12, 1, 0.12])
    with _bm:
        if st.button("Se connecter", type="primary",
                     use_container_width=True, key="vfy_to_login"):
            # Nettoyer le query param et revenir au login
            st.query_params.clear()
            st.session_state.pop("_show_register", None)
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:1.2rem"></div>', unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="vfy-footer">'
    'Unilog OCR System &mdash; PFE 2025-2026 &nbsp;·&nbsp; Goubaa Hanen'
    '</div>',
    unsafe_allow_html=True,
)
