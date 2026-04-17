"""Page Tableau de bord"""
import streamlit as st
import plotly.graph_objects as go
import sys
from pathlib import Path
from datetime import datetime
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from database.database import DatabaseManager

db = DatabaseManager()
stats = db.get_stats()

# ── En-tête page ──────────────────────────────────────────────────────────────
st.markdown("""
<div style='
    background: linear-gradient(135deg, #0055A5 0%, #0088DD 100%);
    padding: 1.6rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.8rem;
    box-shadow: 0 4px 20px rgba(0,85,165,0.28);
'>
    <div style='color:white; font-size:1.55rem; font-weight:700; letter-spacing:-0.01em;'>
        Tableau de Bord
    </div>
</div>
""", unsafe_allow_html=True)

# ── KPIs ──────────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

kpis = [
    (col1, "Documents traités", str(stats["total"]),        "#0044A0", "#0077CC"),
    (col2, "Taux de réussite",  f"{stats['taux_reussite']}%","#0D6B35", "#18A055"),
    (col3, "En attente",         str(stats["en_attente"]),   "#8A5500", "#C07C00"),
    (col4, "Ce mois",            str(stats["du_mois"]),      "#4B1D90", "#7040CC"),
]

for col, label, value, c1, c2 in kpis:
    with col:
        st.markdown(f"""
        <div style='
            background: linear-gradient(135deg, {c1}, {c2});
            color: white;
            padding: 1.3rem 1.2rem;
            border-radius: 12px;
            box-shadow: 0 3px 12px rgba(0,0,0,0.15);
        '>
            <div style='font-size:0.70rem; opacity:0.82; text-transform:uppercase;
                        letter-spacing:0.10em;'>{label}</div>
            <div style='font-size:2rem; font-weight:800; line-height:1.2;
                        margin-top:0.3rem;'>{value}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ── Graphiques ────────────────────────────────────────────────────────────────
_card  = ("background:white; border-radius:12px; padding:1.2rem 1.4rem 0.4rem;"
          "border:1px solid #DDE5EF; box-shadow:0 1px 6px rgba(0,0,0,0.06);"
          "margin-bottom:1rem;")
_title = "font-size:0.95rem; font-weight:700; color:#1E2D40; margin-bottom:0.5rem;"

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"<div style='{_card}'><div style='{_title}'>Documents par Mois</div>",
                unsafe_allow_html=True)
    par_mois    = stats["par_mois"]
    mois_labels = [r["mois"] for r in reversed(par_mois)] if par_mois else ["—"]
    mois_values = [r["n"]    for r in reversed(par_mois)] if par_mois else [0]

    fig = go.Figure(data=[go.Bar(
        x=mois_labels, y=mois_values,
        marker_color="#0077CC",
        marker_line_color="#0055A5",
        marker_line_width=1,
    )])
    fig.update_layout(
        height=260,
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#3A5070", family="Arial"),
        yaxis=dict(gridcolor="#EEF2F7", zerolinecolor="#DDE5EF"),
        xaxis=dict(gridcolor="#EEF2F7"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown(f"<div style='{_card}'><div style='{_title}'>Répartition par Type</div>",
                unsafe_allow_html=True)
    cats       = stats["categories"]
    cat_labels = list(cats.keys()) if cats else ["Aucun"]
    cat_values = list(cats.values()) if cats else [1]
    colors     = ["#0077CC", "#18A055", "#C07C00", "#7040CC", "#CC3333"]

    fig = go.Figure(data=[go.Pie(
        labels=cat_labels, values=cat_values,
        hole=0.46,
        marker=dict(colors=colors[:len(cat_labels)], line=dict(color="white", width=2)),
        textfont=dict(size=12, family="Arial"),
    )])
    fig.update_layout(
        height=260,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white",
        legend=dict(font=dict(size=11, color="#3A5070", family="Arial"), bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── Documents récents ─────────────────────────────────────────────────────────
st.markdown(f"""
<div style='{_card} padding:1.2rem 1.4rem;'>
    <div style='{_title}'>Documents Récents</div>
""", unsafe_allow_html=True)

docs_recents = db.get_all_documents()[:5]

if not docs_recents:
    st.info("Aucun document traité. Commencez dans 'Traiter un document'")
else:
    for doc in docs_recents:
        statut_color = {
            "traité":  "#18A055",
            "uploadé": "#C07C00",
            "erreur":  "#CC3333",
        }.get(doc["status"], "#5A7A9A")

        st.markdown(f"""
        <div style='
            display:flex; align-items:center; gap:0.8rem;
            padding:0.55rem 0.8rem; border-radius:8px;
            background:#F5F8FC; margin-bottom:0.35rem;
            border:1px solid #E4ECF5; border-left:3px solid #0077CC;
        '>
            <span style='color:#0066B2; font-weight:700; min-width:2.5rem; font-size:0.85rem;'>
                #{doc['id']}
            </span>
            <span style='flex:1; color:#1E2D40; font-size:0.88rem;
                         white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                {doc['original_name']}
            </span>
            <span style='color:#5A7A9A; font-size:0.80rem; min-width:6rem;'>
                {doc['doc_category'].capitalize()}
            </span>
            <span style='color:#5A7A9A; font-size:0.80rem; min-width:4rem;'>
                {doc['language'].capitalize()}
            </span>
            <span style='color:#8A9AB0; font-size:0.78rem; min-width:8rem;'>
                {doc['upload_date'][:16]}
            </span>
            <span style='color:{statut_color}; font-size:0.78rem; font-weight:600; min-width:4rem;'>
                {doc['status']}
            </span>
        </div>
        """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    f"<div style='text-align:right; color:#9AACBE; font-size:0.74rem; margin-top:0.8rem;'>"
    f"Dernière mise à jour : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</div>",
    unsafe_allow_html=True,
)
