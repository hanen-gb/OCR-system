"""Page de connexion — Système OCR Unilog."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

import streamlit as st
from database.auth_db import AuthManager

_auth = AuthManager()
_LOGO = Path(__file__).parent.parent.parent / "diagrams" / "uniloglogo-removebg-preview.png"

# ── CSS pleine page ────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Fond page */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #EEF2F7 0%, #D8E6F3 100%) !important;
}
[data-testid="stSidebar"]        { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
header[data-testid="stHeader"]   { display: none !important; }
[data-testid="stAppViewContainer"] > .main > .block-container {
    padding-top: 4rem !important;
    padding-bottom: 2rem !important;
}

/* ── Carte : colonne centrale ── */
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
/* Supprimer le gap entre les blocs markdown du header */
[data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2)
    [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}

/* ── Inputs ── */
[data-testid="stTextInput"] input {
    border: 1.5px solid #CBD8E8 !important;
    border-radius: 8px !important;
    padding: 0.55rem 0.85rem !important;
    font-size: 0.9rem !important;
    background: #F7FAFD !important;
    transition: border-color 0.2s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #0088DD !important;
    box-shadow: 0 0 0 3px rgba(0,136,221,0.12) !important;
    background: #ffffff !important;
}

/* ── Bouton connexion ── */
.stButton > button {
    background: linear-gradient(135deg, #0055A5, #003A6E) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.65rem 1rem !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    width: 100% !important;
    margin-top: 0.4rem !important;
    cursor: pointer !important;
    transition: opacity 0.2s !important;
    letter-spacing: 0.01em !important;
}
.stButton > button:hover { opacity: 0.88 !important; }

/* ── Bouton secondaire (inscription) ── */
.stButton > button[kind="secondary"] {
    background: transparent !important;
    color: #0055A5 !important;
    border: 1.5px solid #CBD8E8 !important;
    border-radius: 10px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    width: 100% !important;
    margin-top: 0 !important;
    transition: all 0.18s !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #EEF5FC !important;
    border-color: #0088DD !important;
    color: #003A6E !important;
}

/* ── Checkbox ── */
[data-testid="stCheckbox"] label {
    font-size: 0.83rem !important;
    color: #3A5270 !important;
}

/* ── Alertes ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    font-size: 0.84rem !important;
}

/* ── Footer ── */
.login-footer {
    text-align: center;
    color: #7A95B0;
    font-size: 0.75rem;
    margin-top: 1.4rem;
}
</style>
""", unsafe_allow_html=True)

# ── Logo (base64) ──────────────────────────────────────────────────────────────
logo_b64 = ""
if _LOGO.exists():
    import base64
    logo_b64 = base64.b64encode(_LOGO.read_bytes()).decode()

# ── Mise en page ───────────────────────────────────────────────────────────────
_, col_center, _ = st.columns([1, 2, 1])

with col_center:

    # ─────────────────────────────────────────────────────────────────────────
    # IMPORTANT : on sépare le logo (base64 long) du texte en DEUX appels
    # st.markdown() distincts.  Une chaîne base64 de plusieurs dizaines de
    # milliers de caractères dans un même bloc peut faire perdre le contexte
    # HTML au parseur de Streamlit, ce qui provoque l'affichage littéral des
    # balises suivantes (<h1>, <p>…) comme du texte brut.
    # ─────────────────────────────────────────────────────────────────────────

    # Bloc 1 — Logo seul (isole le base64 ici)
    if logo_b64:
        st.markdown(
            '<div style="'
            'background:linear-gradient(135deg,#005DA8 0%,#003A6E 100%);'
            'padding:1.8rem 2rem 0;text-align:center;">'
            f'<img src="data:image/png;base64,{logo_b64}"'
            ' style="height:62px;" alt="Unilog">'
            '</div>',
            unsafe_allow_html=True,
        )

    # Bloc 2 — Titre + sous-titre (aucun base64, balises <div> simples)
    _pad_top = "0.6rem" if logo_b64 else "2rem"
    st.markdown(
        f'<div style="'
        f'background:linear-gradient(135deg,#005DA8 0%,#003A6E 100%);'
        f'padding:{_pad_top} 2rem 1.6rem;text-align:center;margin-bottom:0.5rem;">'
        '<div style="color:#ffffff;font-size:1.35rem;font-weight:700;'
        'margin-bottom:0.35rem;letter-spacing:-0.02em;">Système OCR</div>'
        '<div style="color:rgba(255,255,255,0.7);font-size:0.82rem;">'
        'Connectez-vous pour accéder à la plateforme</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Champs du formulaire ────────────────────────────────────────────────
    st.markdown(
        '<div style="padding:0 1.8rem;">'
        '<span style="font-size:0.82rem;font-weight:600;color:#1E2D40;'
        'display:block;margin-bottom:0.25rem;">Nom d\'utilisateur</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    username_input = st.text_input(
        "username",
        placeholder="Entrez votre identifiant",
        label_visibility="collapsed",
        key="login_username",
    )

    st.markdown(
        '<div style="padding:0.4rem 1.8rem 0;">'
        '<span style="font-size:0.82rem;font-weight:600;color:#1E2D40;'
        'display:block;margin-bottom:0.25rem;">Mot de passe</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    password_input = st.text_input(
        "password",
        type="password",
        placeholder="••••••••",
        label_visibility="collapsed",
        key="login_password",
    )

    st.markdown('<div style="padding:0 1.8rem;">', unsafe_allow_html=True)
    remember_me = st.checkbox("Se souvenir de moi (30 jours)", key="login_remember")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)

    # Padding latéral du bouton via colonnes imbriquées
    _bl, _bm, _br = st.columns([0.12, 1, 0.12])
    with _bm:
        login_btn = st.button("Se connecter", use_container_width=True, type="primary")

    # ── Traitement du login ────────────────────────────────────────────────
    if login_btn:
        if not username_input or not password_input:
            st.error("Veuillez renseigner l'identifiant et le mot de passe.")
        else:
            user = _auth.verify_user(username_input, password_input)
            if user is None:
                st.error("Identifiant ou mot de passe incorrect.")
            elif not user.get("email_verified", 1):
                st.warning(
                    "Votre adresse email n'est pas encore vérifiée. "
                    "Consultez votre boîte mail et cliquez sur le lien de confirmation."
                )
                st.markdown(
                    '<div style="height:0.3rem"></div>', unsafe_allow_html=True
                )
                _bl_r, _bm_r, _br_r = st.columns([0.12, 1, 0.12])
                with _bm_r:
                    if st.button(
                        "Renvoyer l'email de vérification",
                        use_container_width=True,
                        key="resend_verif",
                    ):
                        _u = _auth.get_user(username_input)
                        if _u and _u.get("email"):
                            try:
                                from email_sender import send_verification_email
                                _tk = _auth.create_verification_token(_u["username"])
                                _ok = send_verification_email(
                                    _u["email"], _u["display_name"], _tk
                                )
                                if _ok:
                                    st.success(f"Email renvoyé à **{_u['email']}** !")
                                else:
                                    st.error(
                                        "Envoi impossible. Contactez l'administrateur."
                                    )
                            except Exception:
                                st.error(
                                    "Envoi impossible. Contactez l'administrateur."
                                )
                        else:
                            st.error(
                                "Aucune adresse email associée à ce compte. "
                                "Contactez l'administrateur."
                            )
            else:
                _auth.update_last_login(user["username"])
                st.session_state.authenticated = True
                st.session_state.username      = user["username"]
                st.session_state.display_name  = user["display_name"]
                st.session_state.user_role     = user["role"]

                if remember_me:
                    token = _auth.create_session(user["username"])
                    st.session_state.auth_token = token

                # L'admin atterrit sur son panneau dédié par défaut
                _default = "admin_dashboard" if user["role"] == "admin" else "dashboard"
                target_page = st.session_state.pop("requested_page", _default)
                st.session_state.page = target_page
                st.rerun()

    st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)

    # ── Lien vers l'inscription ────────────────────────────────────────────
    _bl2, _bm2, _br2 = st.columns([0.12, 1, 0.12])
    with _bm2:
        if st.button(
            "Pas encore de compte ? S'inscrire",
            use_container_width=True,
            key="login_to_register",
        ):
            st.session_state["_show_register"] = True
            st.rerun()

    st.markdown('<div style="height:1.2rem"></div>', unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="login-footer">'
    'Unilog OCR System &mdash; PFE 2025-2026 &nbsp;·&nbsp; Goubaa Hanen'
    '</div>',
    unsafe_allow_html=True,
)
