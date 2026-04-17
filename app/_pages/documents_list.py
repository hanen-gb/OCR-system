"""Page Liste des documents"""
import streamlit as st
import pandas as pd
import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from database.database import DatabaseManager

db = DatabaseManager()

st.markdown("""
<div style='
    background: linear-gradient(135deg, #0055A5 0%, #0088DD 100%);
    padding: 1.6rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.8rem;
    box-shadow: 0 4px 18px rgba(0,85,165,0.22);
'>
    <div style='color:white; font-size:1.55rem; font-weight:700; letter-spacing:-0.01em;'>
        Documents
    </div>
</div>
""", unsafe_allow_html=True)

# ── Initialisation session state ──────────────────────────────────────────────
if "confirm_delete_id" not in st.session_state:
    st.session_state.confirm_delete_id = None
if "confirm_delete_name" not in st.session_state:
    st.session_state.confirm_delete_name = ""

# ── Boîte de confirmation ─────────────────────────────────────────────────────
if st.session_state.confirm_delete_id is not None:
    doc_id   = st.session_state.confirm_delete_id
    doc_name = st.session_state.confirm_delete_name

    st.warning(
        f"**Voulez-vous vraiment supprimer ce document ?**\n\n"
        f"`{doc_name}` (ID #{doc_id})\n\n"
        f"Cette action est **irréversible** : le fichier sera supprimé du disque et de la base de données."
    )

    col_oui, col_non, _ = st.columns([1, 1, 4])

    with col_oui:
        if st.button("Oui, supprimer", type="primary", use_container_width=True):
            doc = db.get_document_by_id(doc_id)
            if doc:
                file_path = Path(doc["file_path"])
                if file_path.exists():
                    os.remove(file_path)
            db.delete_document(doc_id)
            st.session_state.confirm_delete_id   = None
            st.session_state.confirm_delete_name = ""
            st.success("Document supprimé avec succès.")
            st.rerun()

    with col_non:
        if st.button("Annuler", use_container_width=True):
            st.session_state.confirm_delete_id   = None
            st.session_state.confirm_delete_name = ""
            st.rerun()

    st.markdown("---")

# ── Filtres ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    search = st.text_input("Rechercher", placeholder="Nom du fichier...")

with col2:
    doc_type = st.selectbox("Type", ["Tous", "facture", "devis", "bon_commande", "recu", "autre"])

with col3:
    language = st.selectbox("Langue", ["Toutes", "français", "anglais", "arabe", "inconnu"])

with col4:
    periode = st.selectbox("Période", ["Tous", "Aujourd'hui", "7 derniers jours", "30 derniers jours"])

days_map = {"Tous": None, "Aujourd'hui": 1, "7 derniers jours": 7, "30 derniers jours": 30}
days = days_map[periode]

# ── Requête BDD ───────────────────────────────────────────────────────────────
docs = db.search_documents(
    search=search,
    doc_category=doc_type,
    language=language,
    days=days,
)

st.markdown("---")
st.markdown(
    f"<div style='color:#1E2D40; font-size:0.95rem; font-weight:700; margin-bottom:0.6rem;'>"
    f"Liste des Documents &nbsp;·&nbsp; "
    f"<span style='color:#0066B2;'>{len(docs)} résultat{'s' if len(docs) != 1 else ''}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

if not docs:
    st.info(
        "Aucun document trouvé.\n\n"
        "Les documents sauvegardés apparaîtront ici. "
        "Commencez par traiter un document dans la section 'Traiter un document'."
    )
else:
    # ── En-têtes tableau ──────────────────────────────────────────────────────
    h1, h2, h3, h4, h5, h6, h7 = st.columns([0.4, 2.5, 1, 0.8, 0.7, 1.2, 0.6])
    _th = "color:#5A7A9A; font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;"
    h1.markdown(f"<span style='{_th}'>ID</span>",     unsafe_allow_html=True)
    h2.markdown(f"<span style='{_th}'>Nom</span>",    unsafe_allow_html=True)
    h3.markdown(f"<span style='{_th}'>Type</span>",   unsafe_allow_html=True)
    h4.markdown(f"<span style='{_th}'>Langue</span>", unsafe_allow_html=True)
    h5.markdown(f"<span style='{_th}'>Taille</span>", unsafe_allow_html=True)
    h6.markdown(f"<span style='{_th}'>Date</span>",   unsafe_allow_html=True)
    h7.markdown(f"<span style='{_th}'>Action</span>", unsafe_allow_html=True)

    st.markdown("<hr style='margin: 4px 0 8px 0;'>", unsafe_allow_html=True)

    # ── Lignes ────────────────────────────────────────────────────────────────
    for doc in docs:
        c1, c2, c3, c4, c5, c6, c7 = st.columns([0.4, 2.5, 1, 0.8, 0.7, 1.2, 0.6])
        c1.write(f"#{doc['id']}")
        c2.write(doc["original_name"])
        c3.write(doc["doc_category"].capitalize())
        c4.write(doc["language"].capitalize())
        c5.write(f"{doc['size_bytes'] / 1024 / 1024:.2f} MB")
        c6.write(doc["upload_date"][:16])

        if c7.button("Suppr.", key=f"del_{doc['id']}", help="Supprimer ce document"):
            st.session_state.confirm_delete_id   = doc["id"]
            st.session_state.confirm_delete_name = doc["original_name"]
            st.rerun()

    # ── Export CSV ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<div style='color:#1E2D40; font-size:0.95rem; font-weight:700; margin-bottom:0.6rem;'>"
        "Actions</div>",
        unsafe_allow_html=True,
    )

    df_export = pd.DataFrame([{
        "ID":     d["id"],
        "Nom":    d["original_name"],
        "Type":   d["doc_category"],
        "Langue": d["language"],
        "Taille": f"{d['size_bytes'] / 1024 / 1024:.2f} MB",
        "Date":   d["upload_date"][:16],
        "Statut": d["status"],
    } for d in docs])

    col_a, _ = st.columns([1, 3])
    with col_a:
        csv = df_export.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Exporter CSV",
            data=csv,
            file_name="documents_ocr.csv",
            mime="text/csv",
            use_container_width=True,
        )

# ── Statistiques rapides ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='color:#1E2D40; font-size:0.95rem; font-weight:700; margin-bottom:0.6rem;'>"
    "Statistiques</div>",
    unsafe_allow_html=True,
)

stats = db.get_stats()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total documents", stats["total"], f"+{stats['du_mois']} ce mois")
with col2:
    st.metric("Taux de réussite", f"{stats['taux_reussite']}%")
with col3:
    st.metric("Documents du mois", stats["du_mois"])
