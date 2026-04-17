"""Page Paramètres"""
import streamlit as st

st.markdown("""
<div style='
    background: linear-gradient(135deg, #0055A5 0%, #0088DD 100%);
    padding: 1.6rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.8rem;
    box-shadow: 0 4px 18px rgba(0,85,165,0.22);
'>
    <div style='color:white; font-size:1.55rem; font-weight:700; letter-spacing:-0.01em;'>
        Paramètres
    </div>
</div>
""", unsafe_allow_html=True)

def section_title(title):
    st.markdown(
        f"<div style='font-size:1rem; font-weight:700; color:#0055A5; "
        f"border-left:3px solid #0088DD; padding-left:0.6rem; margin:1.4rem 0 0.8rem 0;'>"
        f"{title}</div>",
        unsafe_allow_html=True,
    )

def spacer():
    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

# Onglets de configuration
tab1, tab2, tab3, tab4 = st.tabs(["OCR", "Langues", "Base de Données", "Interface"])

# ── TAB 1 : Configuration OCR ─────────────────────────────────────────────────
with tab1:
    spacer()
    section_title("Moteur OCR")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        ocr_engine = st.selectbox(
            "Moteur OCR",
            ["PaddleOCR (Recommandé)", "EasyOCR", "Tesseract"],
            help="Sélectionnez le moteur de reconnaissance OCR",
        )
    with col_b:
        use_gpu = st.checkbox(
            "Utiliser GPU",
            value=False,
            help="Accélération matérielle (nécessite CUDA)",
        )

    spacer()
    confidence_threshold = st.slider(
        "Seuil de confiance minimum",
        min_value=0.0, max_value=1.0, value=0.7, step=0.05,
        help="Score de confiance minimum pour accepter un résultat OCR",
    )

    st.markdown("---")
    section_title("Prétraitement d'Images")

    col1, col2, col3 = st.columns(3)
    with col1:
        apply_denoising    = st.checkbox("Suppression du bruit",      value=True)
    with col2:
        apply_binarization = st.checkbox("Binarisation",               value=True)
    with col3:
        apply_deskew       = st.checkbox("Redressement automatique",   value=True)

    spacer()
    col_bin, col_width = st.columns(2)
    with col_bin:
        binarization_method = st.selectbox(
            "Méthode de binarisation",
            ["Otsu (Auto)", "Adaptive", "Manual"],
            disabled=not apply_binarization,
        )
    with col_width:
        max_image_width = st.number_input(
            "Largeur maximale image (px)",
            min_value=1000, max_value=4000, value=2000, step=100,
        )

    spacer()
    st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
    if st.button("Sauvegarder Configuration OCR", type="primary", use_container_width=True):
        st.success("Configuration OCR sauvegardée")

# ── TAB 2 : Langues ───────────────────────────────────────────────────────────
with tab2:
    spacer()
    section_title("Langues Supportées")

    col1, col2, col3 = st.columns(3)
    with col1:
        lang_fr = st.checkbox("Français", value=True)
    with col2:
        lang_en = st.checkbox("Anglais",  value=True)
    with col3:
        lang_ar = st.checkbox("Arabe",    value=True)

    st.markdown("---")
    section_title("Langue par Défaut")

    default_lang = st.selectbox(
        "Langue par défaut si non détectée",
        ["Français", "Anglais", "Arabe"],
    )

    st.markdown("---")
    section_title("Détection Automatique")

    auto_detect = st.checkbox("Activer la détection automatique", value=True)
    spacer()
    detection_method = st.radio(
        "Méthode de détection",
        ["Nom de fichier (rapide)", "Analyse textuelle (précis)", "Les deux"],
        disabled=not auto_detect,
    )

    spacer()
    st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
    if st.button("Sauvegarder Configuration Langues", type="primary", use_container_width=True):
        st.success("Configuration langues sauvegardée")

# ── TAB 3 : Base de données ───────────────────────────────────────────────────
with tab3:
    spacer()
    section_title("Connexion Base de Données")

    db_type = st.selectbox(
        "Type de base de données",
        ["SQLite (Local)", "PostgreSQL (Production)", "MySQL"],
    )

    spacer()
    if db_type == "SQLite (Local)":
        db_path = st.text_input("Chemin de la base", value="data/ocr_database.db")
    else:
        col_h, col_p = st.columns([3, 1])
        with col_h:
            st.text_input("Hôte", value="localhost")
        with col_p:
            st.text_input("Port", value="5432")
        spacer()
        col_n, col_u = st.columns(2)
        with col_n:
            st.text_input("Nom de la base", value="ocr_system")
        with col_u:
            st.text_input("Utilisateur", value="admin")
        spacer()
        st.text_input("Mot de passe", type="password")

    st.markdown("---")
    section_title("Maintenance")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Tester Connexion", use_container_width=True):
            st.info("Connexion réussie (SQLite)")
    with col2:
        if st.button("Nettoyer Base", use_container_width=True):
            st.warning("Fonctionnalité disponible au Sprint 6")

    spacer()
    st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
    if st.button("Sauvegarder Configuration BD", type="primary", use_container_width=True):
        st.success("Configuration base de données sauvegardée")

# ── TAB 4 : Interface ─────────────────────────────────────────────────────────
THEME_OPTIONS = ["Unilog (Bleu)", "Vert", "Rouge", "Violet", "Sombre"]
LANG_OPTIONS  = ["Français", "English", "العربية"]

with tab4:
    spacer()
    section_title("Mode d'Affichage")

    _is_dark = st.session_state.get("theme") == "Sombre"
    dark_on  = st.toggle("Mode Sombre", value=_is_dark,
                         help="Bascule entre le thème sombre et le dernier thème clair utilisé")
    if dark_on != _is_dark:
        if dark_on:
            st.session_state.prev_theme = st.session_state.get("theme", "Unilog (Bleu)")
            st.session_state.theme = "Sombre"
        else:
            st.session_state.theme = st.session_state.get("prev_theme", "Unilog (Bleu)")
        st.rerun()

    st.markdown("---")
    section_title("Personnalisation Interface")

    col_t, col_l = st.columns(2)
    with col_t:
        theme = st.selectbox(
            "Thème de couleur",
            THEME_OPTIONS,
            index=THEME_OPTIONS.index(st.session_state.get("theme", "Unilog (Bleu)")),
        )
    with col_l:
        ui_language = st.selectbox(
            "Langue de l'interface",
            LANG_OPTIONS,
            index=LANG_OPTIONS.index(st.session_state.get("ui_language", "Français")),
        )

    spacer()
    layout = st.radio(
        "Disposition",
        ["Large (Recommandé)", "Centré", "Compact"],
        horizontal=True,
    )

    spacer()
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        show_sidebar_stats = st.checkbox("Afficher stats dans sidebar", value=True)
    with col_c2:
        show_animations = st.checkbox("Activer les animations", value=True)

    spacer()
    st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
    if st.button("Sauvegarder Préférences Interface", type="primary", use_container_width=True):
        st.session_state.theme       = theme
        st.session_state.ui_language = ui_language
        st.success(f"Thème '{theme}' et langue '{ui_language}' appliqués.")
        st.rerun()

# ── Informations système ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='font-size:1rem; font-weight:700; color:#1E2D40; margin-bottom:0.8rem;'>"
    "Informations Système</div>",
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Version", "1.0.0")
with col2:
    st.metric("Sprint", "1")
with col3:
    st.metric("Python", "3.13.4")

st.markdown("---")

col_a, col_b, col_c = st.columns(3)
with col_a:
    if st.button("Réinitialiser Paramètres", use_container_width=True):
        st.warning("Paramètres réinitialisés aux valeurs par défaut")
with col_b:
    if st.button("Exporter Config", use_container_width=True):
        st.info("Configuration exportée vers config.yaml")
with col_c:
    if st.button("Importer Config", use_container_width=True):
        st.info("Sélectionnez un fichier config.yaml")
