"""
Application principale Streamlit - Système OCR Multi-langue
Design Unilog — avec authentification multi-utilisateurs
"""

import streamlit as st
from pathlib import Path
import sys
from PIL import Image

sys.path.append(str(Path(__file__).parent.parent / "src"))

from database.database import DatabaseManager
from database.auth_db import AuthManager

# ── Chemin logo ───────────────────────────────────────────────────────────────
LOGO_PATH = Path(__file__).parent.parent / "diagrams" / "uniloglogo-removebg-preview.png"
_favicon  = Image.open(LOGO_PATH) if LOGO_PATH.exists() else "📄"

# ── Configuration page ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OCR Document System — Unilog",
    page_icon=_favicon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Defaults session state ────────────────────────────────────────────────────
if "page"          not in st.session_state: st.session_state.page          = "dashboard"
if "theme"         not in st.session_state: st.session_state.theme         = "Unilog (Bleu)"
if "ui_language"   not in st.session_state: st.session_state.ui_language   = "Français"
if "prev_theme"    not in st.session_state: st.session_state.prev_theme    = "Unilog (Bleu)"
# Auth
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username"      not in st.session_state: st.session_state.username      = None
if "display_name"  not in st.session_state: st.session_state.display_name  = None
if "user_role"     not in st.session_state: st.session_state.user_role     = None
if "auth_token"    not in st.session_state: st.session_state.auth_token    = None

# ── AuthManager (singleton via cache) ────────────────────────────────────────
@st.cache_resource
def _get_auth() -> AuthManager:
    return AuthManager()

_auth = _get_auth()

# ── Cookie Manager (remember me) ─────────────────────────────────────────────
# Instancié ici pour être disponible dans toute l'appli.
# Nécessite le paquet extra-streamlit-components.
_cookie_mgr = None
try:
    import extra_streamlit_components as stx
    _cookie_mgr = stx.CookieManager(key="__ocr_cookie_mgr__")
except Exception:
    pass   # Paquet absent → remember me désactivé silencieusement

# ── Vérification automatique du cookie "remember me" ─────────────────────────
if not st.session_state.authenticated and _cookie_mgr is not None:
    try:
        _saved_token = _cookie_mgr.get(AuthManager.COOKIE_NAME)
        if _saved_token:
            _username = _auth.validate_session(_saved_token)
            if _username:
                _user = _auth.get_user(_username)
                if _user and _user["is_active"]:
                    st.session_state.authenticated = True
                    st.session_state.username      = _username
                    st.session_state.display_name  = _user["display_name"]
                    st.session_state.user_role     = _user["role"]
                    st.session_state.auth_token    = _saved_token
    except Exception:
        pass

# ── Écriture du cookie après un login réussi ─────────────────────────────────
# (Le token est créé dans login.py et stocké temporairement en session_state)
if st.session_state.authenticated and st.session_state.auth_token and _cookie_mgr is not None:
    try:
        from datetime import datetime, timedelta
        _existing = _cookie_mgr.get(AuthManager.COOKIE_NAME)
        if _existing != st.session_state.auth_token:
            _exp = datetime.now() + timedelta(days=AuthManager.SESSION_DAYS)
            _cookie_mgr.set(AuthManager.COOKIE_NAME, st.session_state.auth_token,
                            expires_at=_exp)
    except Exception:
        pass

# ── Vérification d'email via lien (query param) ───────────────────────────────
_vfy_token = st.query_params.get("verify_token", "")
if _vfy_token:
    _pages_dir_vfy = Path(__file__).parent / "_pages"
    exec(open(_pages_dir_vfy / "verify_email.py", encoding="utf-8").read())
    st.stop()

# ── Porte d'authentification ──────────────────────────────────────────────────
if not st.session_state.authenticated:
    # Mémoriser la page demandée pour y revenir après connexion
    if "requested_page" not in st.session_state:
        st.session_state.requested_page = st.session_state.page
    pages_dir_login = Path(__file__).parent / "_pages"
    if st.session_state.get("_show_register"):
        exec(open(pages_dir_login / "register.py", encoding="utf-8").read())
    else:
        exec(open(pages_dir_login / "login.py", encoding="utf-8").read())
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# == UTILISATEUR AUTHENTIFIÉ : affichage de l'application ==
# ─────────────────────────────────────────────────────────────────────────────

# ── Définition des thèmes ─────────────────────────────────────────────────────
THEMES = {
    "Unilog (Bleu)": {
        "sidebar_bg":    "linear-gradient(175deg, #005DA8 0%, #003A6E 60%, #00274D 100%)",
        "accent1":       "#0055A5",
        "accent2":       "#0088DD",
        "active_grad":   "rgba(0,136,221,0.35), rgba(0,85,165,0.25)",
        "active_border": "rgba(0,136,221,0.55)",
        "collapsed_btn": "#0055A5",
        "main_bg":       "#EEF2F7",
        "card_bg":       "#ffffff",
        "tab_list_bg":   "#DDE5EF",
        "text_main":     "#1E2D40",
        "text_head":     "#0D1B2E",
    },
    "Vert": {
        "sidebar_bg":    "linear-gradient(175deg, #1A7A3A 0%, #0D5028 60%, #072D18 100%)",
        "accent1":       "#1A6B35",
        "accent2":       "#28A855",
        "active_grad":   "rgba(40,168,85,0.35), rgba(26,107,53,0.25)",
        "active_border": "rgba(40,168,85,0.55)",
        "collapsed_btn": "#1A6B35",
        "main_bg":       "#EEF5F0",
        "card_bg":       "#ffffff",
        "tab_list_bg":   "#D5E8DA",
        "text_main":     "#1A2D1E",
        "text_head":     "#0D2010",
    },
    "Rouge": {
        "sidebar_bg":    "linear-gradient(175deg, #A01530 0%, #6B0D1E 60%, #3D0810 100%)",
        "accent1":       "#9B1228",
        "accent2":       "#DD2244",
        "active_grad":   "rgba(221,34,68,0.35), rgba(155,18,40,0.25)",
        "active_border": "rgba(221,34,68,0.55)",
        "collapsed_btn": "#9B1228",
        "main_bg":       "#F7EEEE",
        "card_bg":       "#ffffff",
        "tab_list_bg":   "#EDD5D8",
        "text_main":     "#2D1A1A",
        "text_head":     "#2E0D0D",
    },
    "Violet": {
        "sidebar_bg":    "linear-gradient(175deg, #5B2D90 0%, #3A1A5E 60%, #22103A 100%)",
        "accent1":       "#5B2D90",
        "accent2":       "#8B55CC",
        "active_grad":   "rgba(139,85,204,0.35), rgba(91,45,144,0.25)",
        "active_border": "rgba(139,85,204,0.55)",
        "collapsed_btn": "#5B2D90",
        "main_bg":       "#F2EEF7",
        "card_bg":       "#ffffff",
        "tab_list_bg":   "#E0D5EE",
        "text_main":     "#1E1A2D",
        "text_head":     "#130D2E",
    },
    "Sombre": {
        "sidebar_bg":    "linear-gradient(175deg, #1A2A3E 0%, #101A28 60%, #080F1A 100%)",
        "accent1":       "#1E5FA0",
        "accent2":       "#4A9EE0",
        "active_grad":   "rgba(74,158,224,0.55), rgba(30,95,160,0.45)",
        "active_border": "rgba(74,158,224,0.75)",
        "collapsed_btn": "#1E5FA0",
        "main_bg":       "#0D1520",
        "card_bg":       "#162030",
        "tab_list_bg":   "#0D1520",
        "text_main":     "#DCE8F5",
        "text_head":     "#F0F8FF",
    },
}

# ── Traductions navigation ────────────────────────────────────────────────────
TRANSLATIONS = {
    "Français": {
        "nav":       ["Tableau de bord", "Documents", "Paramètres"],
        "nav_adm":   "Administration",
        "nav_hitl":    "Inférence IA + HITL",
        "nav_process": "Traiter un document",
        "logout":    "Se déconnecter",
        "docs":      "Documents",
        "success":   "Réussite",
        "role_admin": "Admin",
        "role_user":  "Utilisateur",
    },
    "English": {
        "nav":       ["Dashboard", "Documents", "Settings"],
        "nav_adm":   "Administration",
        "nav_hitl":    "AI Inference + HITL",
        "nav_process": "Process document",
        "logout":    "Log out",
        "docs":      "Documents",
        "success":   "Success rate",
        "role_admin": "Admin",
        "role_user":  "User",
    },
    "العربية": {
        "nav":       ["لوحة التحكم", "الوثائق", "الإعدادات"],
        "nav_adm":   "Administration",
        "nav_hitl":    "استنتاج ذكاء اصطناعي",
        "nav_process": "معالجة وثيقة",
        "logout":    "تسجيل الخروج",
        "docs":      "الوثائق",
        "success":   "نسبة النجاح",
        "role_admin": "Admin",
        "role_user":  "مستخدم",
    },
}

# ── CSS dynamique selon thème ─────────────────────────────────────────────────
t = THEMES.get(st.session_state.theme, THEMES["Unilog (Bleu)"])

st.markdown(f"""
<style>
/* ─── Police globale Arial (hors icônes) ─── */
body, p, div, h1, h2, h3, h4, h5, h6,
input, select, textarea, label, button,
[class*="css"]:not([class*="material"]) {{
    font-family: Arial, Helvetica, sans-serif !important;
}}
/* ─── Préserver la police Material Icons ─── */
span[class*="material"],
[class*="material-icons"],
[class*="material-symbols"],
[data-testid="stHeader"] button span,
[data-testid="stHeader"] span,
[data-testid="collapsedControl"] span,
[data-testid="stSidebarCollapseButton"] span {{
    font-family: "Material Symbols Rounded", "Material Symbols Outlined",
                 "Material Icons Sharp", "Material Icons" !important;
}}

/* ─── Cache menu & footer Streamlit ─── */
#MainMenu {{ visibility: hidden; }}
footer    {{ visibility: hidden; }}

/* ─── Header Streamlit natif ─── */
[data-testid="stHeader"] {{
    background-color: transparent !important;
    box-shadow: none !important;
}}

/* ─── Fond général ─── */
[data-testid="stAppViewContainer"] > .main {{
    background-color: {t['main_bg']};
}}
[data-testid="stMainBlockContainer"] {{
    padding-top: 2.5rem !important;
    background-color: {t['main_bg']};
}}

/* ─── Textes généraux ─── */
.main p, .main span, .main div, .main label,
.stMarkdown, .stMarkdown p {{
    color: {t['text_main']};
}}
.main h1, .main h2, .main h3, .main h4 {{
    color: {t['text_head']} !important;
}}

/* ─── Inputs & selects ─── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {{
    background-color: {t['card_bg']} !important;
    color: {t['text_main']} !important;
    border: 1px solid #C8D5E3 !important;
    border-radius: 8px !important;
}}
[data-testid="stTextInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stSelectbox"] label,
[data-testid="stSlider"] label,
[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label {{
    color: {t['text_main']} !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
}}
[data-testid="stSelectbox"] > div > div {{
    background-color: {t['card_bg']} !important;
    color: {t['text_main']} !important;
    border: 1px solid #C8D5E3 !important;
    border-radius: 8px !important;
}}
[data-testid="stCheckbox"] span,
[data-testid="stRadio"] span {{
    color: {t['text_main']} !important;
}}

/* ─── Boutons zone principale ─── */
.main .stButton > button {{
    background-color: {t['card_bg']} !important;
    color: {t['text_main']} !important;
    border: 1px solid #C8D5E3 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.18s ease;
}}
.main .stButton > button:hover {{
    background-color: {t['accent2']} !important;
    color: white !important;
    border-color: {t['accent2']} !important;
}}
.main .stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {t['accent1']}, {t['accent2']}) !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
}}
.main .stButton > button[kind="primary"]:hover {{
    opacity: 0.88 !important;
}}
.main [data-testid="stDownloadButton"] > button {{
    background-color: {t['card_bg']} !important;
    color: {t['text_main']} !important;
    border: 1px solid #C8D5E3 !important;
    border-radius: 8px !important;
}}
.main [data-testid="stDownloadButton"] > button:hover {{
    background-color: {t['accent2']} !important;
    color: white !important;
    border-color: {t['accent2']} !important;
}}

/* ─── Métriques ─── */
.main [data-testid="stMetric"] {{
    background: {t['card_bg']};
    border-radius: 10px;
    padding: 0.8rem 1rem;
    border: 1px solid #DDE5EF;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}}
.main [data-testid="stMetricValue"] {{ color: {t['text_head']} !important; font-weight: 700 !important; }}
.main [data-testid="stMetricLabel"] {{ color: {t['text_main']} !important; opacity: 0.75; }}
.main [data-testid="stMetricDelta"]  {{ color: #18A055 !important; }}

/* ─── Alertes ─── */
[data-testid="stAlert"] {{ border-radius: 10px !important; }}

/* ─── Tabs ─── */
[data-testid="stTabs"] [role="tablist"] {{
    background-color: {t['tab_list_bg']};
    border-radius: 10px;
    gap: 6px;
    padding: 6px 8px;
}}
[data-testid="stTabs"] [role="tab"] {{
    color: {t['text_main']} !important;
    border-radius: 7px !important;
    font-weight: 500 !important;
    font-family: Arial, Helvetica, sans-serif !important;
    font-size: 0.90rem !important;
    padding: 0.45rem 1.1rem !important;
    min-width: fit-content !important;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    background: linear-gradient(135deg, {t['accent1']}, {t['accent2']}) !important;
    color: white !important;
}}
[data-testid="stTabPanel"] {{
    background-color: {t['card_bg']};
    border-radius: 10px;
    padding: 1.2rem;
    border: 1px solid #DDE5EF;
    margin-top: 0.5rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}}

/* ─── DataFrame ─── */
[data-testid="stDataFrame"] {{
    border-radius: 10px !important;
    overflow: hidden;
    border: 1px solid #DDE5EF !important;
}}

/* ─── Séparateurs ─── */
.main hr {{ border-color: #DDE5EF !important; }}

/* ─── Sidebar fond dégradé thème ─── */
[data-testid="stSidebar"] {{
    background: {t['sidebar_bg']};
    border-right: none;
}}
[data-testid="stSidebarContent"] {{
    padding: 0 0.8rem 1rem 0.8rem !important;
    padding-top: 0 !important;
}}
[data-testid="stSidebarUserContent"] {{
    padding-top: 0 !important;
    margin-top: 0 !important;
}}

/* ─── Textes sidebar en blanc ─── */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] caption {{
    color: white !important;
}}

/* ─── Boutons nav inactifs ─── */
[data-testid="stSidebar"] .stButton > button {{
    width: 100%;
    margin: 0.18rem 0;
    padding: 0.55rem 1rem;
    background-color: rgba(255,255,255,0.08) !important;
    color: rgba(255,255,255,0.88) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 8px !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    transition: all 0.18s ease;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background-color: rgba(255,255,255,0.20) !important;
    border-color: rgba(255,255,255,0.45) !important;
    color: white !important;
    transform: translateX(3px);
}}
[data-testid="stSidebar"] .stButton > button:focus {{
    box-shadow: 0 0 0 2px rgba(255,255,255,0.35) !important;
    outline: none !important;
}}

/* ─── Bouton déconnexion sidebar ─── */
[data-testid="stSidebar"] .stButton > button[data-logout="true"],
[data-testid="stSidebar"] button.logout-btn {{
    background-color: rgba(200,40,40,0.20) !important;
    border-color: rgba(220,60,60,0.45) !important;
    color: #FFB3B3 !important;
}}
[data-testid="stSidebar"] .stButton > button[data-logout="true"]:hover,
[data-testid="stSidebar"] button.logout-btn:hover {{
    background-color: rgba(200,40,40,0.45) !important;
    color: #FFD6D6 !important;
}}

/* ─── Item nav actif ─── */
.nav-active {{
    width: 100%;
    margin: 0.18rem 0;
    padding: 0.55rem 1rem;
    background: linear-gradient(135deg, {t['active_grad']}) !important;
    color: #FFFFFF !important;
    border: 1px solid {t['active_border']} !important;
    border-radius: 8px;
    font-size: 0.92rem;
    font-weight: 700;
    cursor: default;
    box-shadow: 0 0 12px rgba(0,100,200,0.20);
}}

/* ─── Carte utilisateur sidebar ─── */
.user-card {{
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 10px;
    padding: 0.65rem 0.85rem;
    margin: 0.4rem 0 0.5rem 0;
    display: flex;
    align-items: center;
    gap: 0.65rem;
}}
.user-avatar {{
    width: 34px; height: 34px;
    border-radius: 50%;
    background: rgba(255,255,255,0.22);
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem;
    flex-shrink: 0;
    border: 1.5px solid rgba(255,255,255,0.35);
}}
.user-info {{ flex: 1; min-width: 0; }}
.user-name {{
    color: white !important;
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.user-badge-admin {{
    display: inline-block;
    background: rgba(255,255,255,0.25);
    color: white !important;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    padding: 0.05rem 0.45rem;
    border-radius: 20px;
    letter-spacing: 0.04em;
    border: 1px solid rgba(255,255,255,0.30);
    text-transform: uppercase;
}}
.user-badge-user {{
    display: inline-block;
    background: rgba(255,255,255,0.12);
    color: rgba(255,255,255,0.75) !important;
    font-size: 0.68rem !important;
    font-weight: 600 !important;
    padding: 0.05rem 0.45rem;
    border-radius: 20px;
    letter-spacing: 0.04em;
    border: 1px solid rgba(255,255,255,0.20);
}}

/* ─── Métriques sidebar ─── */
[data-testid="stSidebar"] [data-testid="stMetricValue"] {{
    color: white !important;
    font-size: 1.4rem !important;
    font-weight: 700 !important;
}}
[data-testid="stSidebar"] [data-testid="stMetricLabel"] {{
    color: rgba(255,255,255,0.7) !important;
    font-size: 0.78rem !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.15) !important;
    margin: 0.6rem 0 !important;
}}

/* ─── Bouton toggle sidebar ─── */
[data-testid="stSidebarCollapseButton"] button {{
    background-color: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.20) !important;
    border-radius: 6px !important;
    overflow: hidden !important;
}}
[data-testid="stSidebarCollapseButton"] button * {{ display: none !important; }}
[data-testid="stSidebarCollapseButton"] button svg {{
    display: block !important; fill: white !important; stroke: white !important;
}}
[data-testid="stSidebarCollapseButton"] button svg * {{ display: block !important; }}
[data-testid="collapsedControl"] button {{
    background-color: {t['collapsed_btn']} !important;
    border: 1px solid rgba(255,255,255,0.20) !important;
    border-radius: 6px !important;
    overflow: hidden !important;
}}
[data-testid="collapsedControl"] button * {{ display: none !important; }}
[data-testid="collapsedControl"] button svg {{
    display: block !important; fill: white !important;
}}
[data-testid="collapsedControl"] button svg * {{ display: block !important; }}

/* ─── Zone logo sidebar ─── */
.sidebar-logo-zone {{
    text-align: center;
    padding: 0.1rem 0.5rem 0.3rem 0.5rem;
    border-bottom: 1px solid rgba(255,255,255,0.12);
    margin-bottom: 0.4rem;
    margin-top: -2rem;
}}

/* ─── Images plafonnées ─── */
div[data-testid="stImage"] img {{
    max-height: 700px !important;
    width: 100% !important;
    object-fit: contain !important;
}}
/* ─── Boutons simulation compacts ─── */
div[data-testid="stVerticalBlock"] .stButton > button {{
    padding: 0.28rem 0.6rem !important;
    font-size: 0.82rem !important;
    min-height: 1.85rem !important;
    height: auto !important;
    line-height: 1.3 !important;
}}
/* ─── Tabs compacts ─── */
div[data-testid="stTabs"] [role="tab"] {{
    font-size: 0.82rem !important;
    padding: 0.35rem 0.8rem !important;
}}
</style>
""", unsafe_allow_html=True)

# ── CSS surcharges mode sombre ────────────────────────────────────────────────
if st.session_state.theme == "Sombre":
    st.markdown("""
<style>
/* ══ DARK MODE — surcharges complètes ══════════════════════════════════════ */
[data-testid="stTextArea"] textarea {
    background-color: #0D1520 !important;
    color: #F0F8FF !important;
    border: 1px solid #2A3D55 !important;
    border-radius: 8px !important;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
    background-color: #0D1520 !important;
    color: #F0F8FF !important;
    border-color: #2A3D55 !important;
}
[data-testid="stSelectbox"] > div > div {
    background-color: #0D1520 !important;
    color: #F0F8FF !important;
    border-color: #2A3D55 !important;
}
[data-testid="stFileUploaderDropzone"] {
    background-color: #162030 !important;
    border: 2px dashed #2A3D55 !important;
    border-radius: 10px !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] p,
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small {
    color: #DCE8F5 !important;
}
.main [data-testid="stMetric"] {
    background-color: #162030 !important;
    border: 1px solid #2A3D55 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.40) !important;
}
.main [data-testid="stMetricValue"] { color: #F0F8FF !important; }
.main [data-testid="stMetricLabel"] { color: #9AB8D0 !important; }
[data-testid="stTabPanel"] {
    background-color: #162030 !important;
    border: 1px solid #2A3D55 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.35) !important;
}
[data-testid="stDataFrame"] { border: 1px solid #2A3D55 !important; }
[data-testid="stDataFrame"] iframe { color-scheme: dark !important; }
.main .stButton > button {
    background-color: #162030 !important;
    color: #DCE8F5 !important;
    border: 1px solid #2A3D55 !important;
}
.main .stButton > button:hover {
    background-color: #1E3050 !important;
    border-color: #4A9EE0 !important;
    color: #F0F8FF !important;
}
.main [data-testid="stDownloadButton"] > button {
    background-color: #162030 !important;
    color: #DCE8F5 !important;
    border: 1px solid #2A3D55 !important;
}
.main [data-testid="stDownloadButton"] > button:hover {
    background-color: #1E3050 !important;
    color: #F0F8FF !important;
}
[data-testid="stAlert"] {
    background-color: #162030 !important;
    border-left-color: #4A9EE0 !important;
}
[data-testid="stAlert"] p,
[data-testid="stAlert"] span { color: #DCE8F5 !important; }
.main hr { border-color: #2A3D55 !important; }
.main [data-testid="stCaptionContainer"] p,
.main small { color: #8AAEC8 !important; }
[data-testid="stCheckbox"] > label > div:first-child,
[data-testid="stRadio"] > label > div:first-child {
    border-color: #2A3D55 !important;
    background-color: #0D1520 !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] [data-baseweb="slider-track"] {
    background-color: #2A3D55 !important;
}
[data-testid="stSpinner"] > div { border-top-color: #4A9EE0 !important; }
[data-testid="stToggle"] > label > div { background-color: #2A3D55 !important; }
[data-baseweb="popover"] [data-baseweb="menu"] {
    background-color: #162030 !important;
    border: 1px solid #2A3D55 !important;
}
[data-baseweb="popover"] [role="option"] {
    background-color: #162030 !important;
    color: #DCE8F5 !important;
}
[data-baseweb="popover"] [role="option"]:hover {
    background-color: #1E3050 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Traductions actives ───────────────────────────────────────────────────────
tr = TRANSLATIONS.get(st.session_state.ui_language, TRANSLATIONS["Français"])

if st.session_state.user_role == "admin":
    NAV_KEYS  = ["admin_dashboard", "dashboard", "documents", "inference_hitl", "process", "settings"]
    NAV_ITEMS = [
        ("admin_dashboard", tr["nav_adm"]),
        ("dashboard",       tr["nav"][0]),
        ("documents",       tr["nav"][1]),
        ("inference_hitl",  tr["nav_hitl"]),
        ("process",         tr["nav_process"]),
        ("settings",        tr["nav"][2]),
    ]
else:
    NAV_KEYS  = ["dashboard", "documents", "inference_hitl", "process", "settings"]
    NAV_ITEMS = [
        ("dashboard",      tr["nav"][0]),
        ("documents",      tr["nav"][1]),
        ("inference_hitl", tr["nav_hitl"]),
        ("process",        tr["nav_process"]),
        ("settings",       tr["nav"][2]),
    ]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:

    # Logo
    st.markdown('<div class="sidebar-logo-zone">', unsafe_allow_html=True)
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=52)
    st.markdown('</div>', unsafe_allow_html=True)

    # Carte utilisateur connecté
    _role    = st.session_state.user_role or "user"
    _badge   = "user-badge-admin" if _role == "admin" else "user-badge-user"
    _label   = tr["role_admin"] if _role == "admin" else tr["role_user"]
    _dname   = st.session_state.display_name or st.session_state.username or "?"
    _initial = _dname[0].upper() if _dname else "U"

    st.markdown(f"""
    <div class="user-card">
      <div class="user-avatar">{_initial}</div>
      <div class="user-info">
        <div class="user-name">{_dname}</div>
        <span class="{_badge}">{_label}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Navigation
    for key, label in NAV_ITEMS:
        is_active = (st.session_state.page == key)
        is_admin_btn = (key == "admin_dashboard")

        if is_active:
            st.markdown(f'<div class="nav-active">{label}</div>', unsafe_allow_html=True)
        elif is_admin_btn:
            # Bouton Admin : style spécial (fond doré discret) pour le distinguer
            st.markdown("""
            <style>
            [data-testid="stSidebar"] button[kind="secondary"][data-admin-btn="1"] {
                background-color: rgba(255,200,50,0.15) !important;
                border-color: rgba(255,200,50,0.40) !important;
                color: #FFE082 !important;
                font-weight: 700 !important;
            }
            [data-testid="stSidebar"] button[kind="secondary"][data-admin-btn="1"]:hover {
                background-color: rgba(255,200,50,0.30) !important;
                border-color: rgba(255,200,50,0.70) !important;
                color: #FFECB3 !important;
            }
            </style>
            """, unsafe_allow_html=True)
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()
        else:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()

    st.markdown("---")

    # Toggle mode sombre
    _is_dark = st.session_state.theme == "Sombre"
    _toggle_label = "☀️  Mode Clair" if _is_dark else "🌙  Mode Sombre"
    if st.button(_toggle_label, use_container_width=True, key="dark_toggle"):
        if _is_dark:
            st.session_state.theme = st.session_state.prev_theme
        else:
            st.session_state.prev_theme = st.session_state.theme
            st.session_state.theme = "Sombre"
        st.rerun()

    # Bouton déconnexion
    if st.button(f"  {tr['logout']}", use_container_width=True, key="btn_logout"):
        # Supprimer le token de session en DB
        if st.session_state.auth_token:
            _auth.delete_session(st.session_state.auth_token)
        # Supprimer le cookie
        if _cookie_mgr is not None:
            try:
                _cookie_mgr.delete(AuthManager.COOKIE_NAME)
            except Exception:
                pass
        # Réinitialiser l'état auth
        for _k in ("authenticated", "username", "display_name", "user_role", "auth_token",
                   "requested_page", "preprocessed_key", "preprocessed_img",
                   "original_img", "ocr_result"):
            st.session_state.pop(_k, None)
        st.session_state.authenticated = False
        st.rerun()

    st.markdown("---")

    # Statistiques rapides
    _stats = DatabaseManager().get_stats()
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.metric(tr["docs"],    _stats["total"])
    with col_s2:
        st.metric(tr["success"], f"{_stats['taux_reussite']}%")

# ── Routeur de pages ──────────────────────────────────────────────────────────
pages_dir = Path(__file__).parent / "_pages"

page_files = {
    "dashboard":       "dashboard.py",
    "admin_dashboard": "admin_dashboard.py",
    "documents":       "documents_list.py",
    "inference_hitl":  "inference_hitl.py",
    "process":         "process_document.py",
    "settings":        "settings.py",
    "user_management": "user_management.py",
}


# Sécurité : admin_dashboard et user_management réservés aux admins
if st.session_state.page in ("admin_dashboard", "user_management") and st.session_state.user_role != "admin":
    st.session_state.page = "dashboard"

# Rétrocompat : "user_management" redirige vers admin_dashboard pour les admins
if st.session_state.page == "user_management" and st.session_state.user_role == "admin":
    st.session_state.page = "admin_dashboard"

target = page_files.get(st.session_state.page, "dashboard.py")
exec(open(pages_dir / target, encoding="utf-8").read())
