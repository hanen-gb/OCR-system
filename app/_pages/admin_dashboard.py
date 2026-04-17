"""
Page Administration — Panneau de contrôle complet (admins uniquement).
4 onglets : Vue d'ensemble · Documents · Utilisateurs · Système
"""
import sys
import json
import sqlite3
import platform
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

import streamlit as st
import plotly.graph_objects as go

from database.database import DatabaseManager
from database.auth_db import AuthManager

# ── Sécurité ───────────────────────────────────────────────────────────────────
if st.session_state.get("user_role") != "admin":
    st.error("Accès réservé aux administrateurs.")
    st.stop()

_db   = DatabaseManager()
_auth = AuthManager()

_CATS   = ["facture", "devis", "bon_commande", "recu", "autre"]
_LANGS  = ["français", "anglais", "arabe", "inconnu"]
_STATUS = ["traité", "uploadé", "erreur"]

# ── En-tête ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='
    background: linear-gradient(135deg, #0044A0 0%, #0088DD 100%);
    padding: 1.4rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.4rem;
    box-shadow: 0 4px 18px rgba(0,68,160,0.25);
    display: flex;
    align-items: center;
    gap: 1rem;
'>
    <div style='font-size:2.2rem; line-height:1;'>⚙️</div>
    <div>
        <div style='color:white; font-size:1.5rem; font-weight:700; letter-spacing:-0.01em;'>
            Administration
        </div>
        <div style='color:rgba(255,255,255,0.72); font-size:0.82rem; margin-top:0.15rem;'>
            Panneau de contrôle — Documents · Utilisateurs · Système
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── CSS propre à ce panneau ────────────────────────────────────────────────────
st.markdown("""
<style>
.adm-section {
    font-size: 0.90rem; font-weight: 700; color: #0D1B2E;
    margin: 1rem 0 0.55rem; padding-bottom: 0.35rem;
    border-bottom: 2px solid #EEF2F7;
}
/* Badges */
.badge-admin    { display:inline-block; background:#0055A5; color:white;
                  font-size:0.67rem; font-weight:700; padding:0.1rem 0.45rem;
                  border-radius:20px; letter-spacing:0.05em; text-transform:uppercase; }
.badge-user     { display:inline-block; background:#E3F2FD; color:#0055A5;
                  font-size:0.67rem; font-weight:700; padding:0.1rem 0.45rem;
                  border-radius:20px; letter-spacing:0.05em; text-transform:uppercase;
                  border:1px solid #BBDEFB; }
.badge-ok       { display:inline-block; background:#E8F5E9; color:#1B5E20;
                  font-size:0.67rem; font-weight:700; padding:0.1rem 0.45rem;
                  border-radius:20px; letter-spacing:0.05em; text-transform:uppercase;
                  border:1px solid #A5D6A7; }
.badge-wait     { display:inline-block; background:#FFF8E1; color:#E65100;
                  font-size:0.67rem; font-weight:700; padding:0.1rem 0.45rem;
                  border-radius:20px; letter-spacing:0.05em; text-transform:uppercase;
                  border:1px solid #FFCC80; }
.badge-err      { display:inline-block; background:#FFEBEE; color:#C62828;
                  font-size:0.67rem; font-weight:700; padding:0.1rem 0.45rem;
                  border-radius:20px; letter-spacing:0.05em; text-transform:uppercase;
                  border:1px solid #EF9A9A; }
.badge-inactive { display:inline-block; background:#FFF3E0; color:#E65100;
                  font-size:0.67rem; font-weight:700; padding:0.1rem 0.45rem;
                  border-radius:20px; letter-spacing:0.05em; text-transform:uppercase;
                  border:1px solid #FFCC80; }
/* Ligne de document */
.doc-row {
    display: flex; align-items: center; gap: 0.7rem;
    padding: 0.42rem 0.7rem; border-radius: 8px;
    background: #F5F8FC; margin-bottom: 0.28rem;
    border: 1px solid #E4ECF5; border-left: 3px solid #0077CC;
}
/* Sysinfo row */
.sysrow {
    padding: 0.35rem 0.7rem; border-radius: 6px;
    background: #F5F8FC; margin-bottom: 0.25rem;
    border: 1px solid #E4ECF5; font-size: 0.84rem;
}
</style>
""", unsafe_allow_html=True)

# ── Helper : carte KPI colorée ─────────────────────────────────────────────────
def _kpi_card(col, label: str, value, c1: str, c2: str):
    with col:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,{c1},{c2});color:white;'
            f'padding:1rem 1.1rem;border-radius:12px;'
            f'box-shadow:0 3px 10px rgba(0,0,0,0.14);margin-bottom:0.2rem;">'
            f'<div style="font-size:0.67rem;opacity:0.82;text-transform:uppercase;'
            f'letter-spacing:0.10em;">{label}</div>'
            f'<div style="font-size:2rem;font-weight:800;line-height:1.15;'
            f'margin-top:0.2rem;">{value}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── Onglets ────────────────────────────────────────────────────────────────────
tab_ov, tab_docs, tab_users, tab_sys = st.tabs([
    "Vue d'ensemble", "Documents", "Utilisateurs", "Système",
])

# ══════════════════════════════════════════════════════════════════════════════
# ONGLET 1 — Vue d'ensemble
# ══════════════════════════════════════════════════════════════════════════════
with tab_ov:
    stats    = _db.get_stats()
    users    = _auth.list_users()
    n_users  = len(users)
    n_active = sum(1 for u in users if u["is_active"])
    n_admins = sum(1 for u in users if u["role"] == "admin")

    # Sessions actives (requête directe)
    try:
        _c = sqlite3.connect(str(_auth.db_path))
        _c.row_factory = sqlite3.Row
        _now = datetime.utcnow().isoformat()
        n_sessions = _c.execute(
            "SELECT COUNT(*) as n FROM sessions WHERE expires_at > ?", (_now,)
        ).fetchone()["n"]
        _c.close()
    except Exception:
        n_sessions = 0

    # ── KPIs Utilisateurs ──────────────────────────────────────────────────
    st.markdown('<div class="adm-section">Utilisateurs</div>', unsafe_allow_html=True)
    cu1, cu2, cu3, cu4 = st.columns(4)
    _kpi_card(cu1, "Total utilisateurs",  n_users,    "#0044A0", "#0077CC")
    _kpi_card(cu2, "Actifs",              n_active,   "#0D6B35", "#18A055")
    _kpi_card(cu3, "Administrateurs",     n_admins,   "#5B2D90", "#8B55CC")
    _kpi_card(cu4, "Sessions actives",    n_sessions, "#8A5500", "#C07C00")

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    # ── KPIs Documents ─────────────────────────────────────────────────────
    st.markdown('<div class="adm-section">Documents</div>', unsafe_allow_html=True)
    cd1, cd2, cd3, cd4 = st.columns(4)
    _kpi_card(cd1, "Total documents", stats["total"],          "#0044A0", "#0077CC")
    _kpi_card(cd2, "Traités",         stats.get("traites", 0), "#0D6B35", "#18A055")
    _kpi_card(cd3, "En attente",      stats["en_attente"],     "#8A5500", "#C07C00")
    _kpi_card(cd4, "Ce mois",         stats["du_mois"],        "#4B1D90", "#7040CC")

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    # ── Graphiques ─────────────────────────────────────────────────────────
    st.markdown('<div class="adm-section">Statistiques visuelles</div>',
                unsafe_allow_html=True)
    _card_css = ("background:white;border-radius:12px;padding:1rem 1.2rem 0.4rem;"
                 "border:1px solid #DDE5EF;box-shadow:0 1px 5px rgba(0,0,0,0.05);")
    _title_css = "font-size:0.88rem;font-weight:700;color:#1E2D40;margin-bottom:0.4rem;"

    gc1, gc2, gc3 = st.columns(3)

    with gc1:
        st.markdown(f"<div style='{_card_css}'><div style='{_title_css}'>Documents par mois</div>",
                    unsafe_allow_html=True)
        pm  = stats["par_mois"]
        fig = go.Figure(go.Bar(
            x=[r["mois"] for r in reversed(pm)] if pm else ["—"],
            y=[r["n"]    for r in reversed(pm)] if pm else [0],
            marker_color="#0077CC",
            marker_line_color="#005599", marker_line_width=0.5,
        ))
        fig.update_layout(height=210, margin=dict(l=0, r=0, t=4, b=0),
                          plot_bgcolor="white", paper_bgcolor="white",
                          font=dict(color="#3A5070", family="Arial"),
                          yaxis=dict(gridcolor="#EEF2F7", tickfont=dict(size=10)),
                          xaxis=dict(gridcolor="#EEF2F7", tickfont=dict(size=9)))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with gc2:
        st.markdown(f"<div style='{_card_css}'><div style='{_title_css}'>Types de documents</div>",
                    unsafe_allow_html=True)
        cats   = stats["categories"]
        colors = ["#0077CC", "#18A055", "#C07C00", "#7040CC", "#CC3333"]
        fig    = go.Figure(go.Pie(
            labels=list(cats.keys()) if cats else ["Aucun"],
            values=list(cats.values()) if cats else [1],
            hole=0.46,
            marker=dict(
                colors=colors[:len(cats)] if cats else colors[:1],
                line=dict(color="white", width=2),
            ),
            textfont=dict(size=11, family="Arial"),
        ))
        fig.update_layout(height=210, margin=dict(l=0, r=0, t=4, b=0),
                          paper_bgcolor="white",
                          legend=dict(font=dict(size=10, color="#3A5070")))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with gc3:
        st.markdown(f"<div style='{_card_css}'><div style='{_title_css}'>Utilisateurs actifs</div>",
                    unsafe_allow_html=True)
        fig = go.Figure(go.Pie(
            labels=["Actifs", "Inactifs"],
            values=[max(n_active, 0), max(n_users - n_active, 0)] if n_users else [1, 0],
            hole=0.46,
            marker=dict(colors=["#18A055", "#CC3333"],
                        line=dict(color="white", width=2)),
            textfont=dict(size=11, family="Arial"),
        ))
        fig.update_layout(height=210, margin=dict(l=0, r=0, t=4, b=0),
                          paper_bgcolor="white",
                          legend=dict(font=dict(size=10, color="#3A5070")))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Activité récente ───────────────────────────────────────────────────
    st.markdown('<div class="adm-section">Derniers documents ajoutés</div>',
                unsafe_allow_html=True)
    docs_rec = _db.get_all_documents()[:8]
    if docs_rec:
        for doc in docs_rec:
            sc = {"traité": "#18A055", "uploadé": "#C07C00", "erreur": "#CC3333"}.get(
                doc["status"], "#5A7A9A"
            )
            _sz = f"{doc['size_bytes'] // 1024} Ko" if doc.get("size_bytes") else "—"
            st.markdown(
                f'<div class="doc-row">'
                f'<span style="color:#0066B2;font-weight:700;min-width:2rem;font-size:0.80rem;">#{doc["id"]}</span>'
                f'<span style="flex:1;color:#1E2D40;font-size:0.82rem;white-space:nowrap;'
                f'overflow:hidden;text-overflow:ellipsis;">{doc["original_name"]}</span>'
                f'<span style="color:#5A7A9A;font-size:0.76rem;min-width:5rem;">{doc["doc_category"].capitalize()}</span>'
                f'<span style="color:#5A7A9A;font-size:0.76rem;min-width:4rem;">{doc["language"].capitalize()}</span>'
                f'<span style="color:#5A7A9A;font-size:0.74rem;min-width:4rem;">{_sz}</span>'
                f'<span style="color:#8A9AB0;font-size:0.74rem;min-width:9rem;">{doc["upload_date"][:16]}</span>'
                f'<span style="color:{sc};font-size:0.76rem;font-weight:600;">{doc["status"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("Aucun document enregistré.")

    st.markdown(
        f'<div style="text-align:right;color:#9AACBE;font-size:0.73rem;margin-top:0.6rem;">'
        f'Données à {datetime.now().strftime("%H:%M:%S")}</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# ONGLET 2 — Gestion des Documents (CRUD complet)
# ══════════════════════════════════════════════════════════════════════════════
with tab_docs:

    # ── Filtres ────────────────────────────────────────────────────────────
    st.markdown('<div class="adm-section">Recherche & Filtres</div>',
                unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])
    with fc1:
        srch = st.text_input("Rechercher", placeholder="Nom de fichier ou contenu OCR…",
                             label_visibility="collapsed", key="adm_srch")
    with fc2:
        cat_f = st.selectbox("Type", ["Tous"] + [c.replace("_", " ").capitalize() for c in _CATS],
                             key="adm_cat", label_visibility="collapsed")
    with fc3:
        lang_f = st.selectbox("Langue", ["Toutes"] + [l.capitalize() for l in _LANGS],
                              key="adm_lang", label_visibility="collapsed")
    with fc4:
        _period_opts = {"Tout": None, "Aujourd'hui": 1, "7 jours": 7, "30 jours": 30}
        period_lbl   = st.selectbox("Période", list(_period_opts.keys()),
                                    key="adm_per", label_visibility="collapsed")

    docs = _db.search_documents(
        search=srch,
        doc_category=cat_f if cat_f != "Tous" else "Tous",
        language=lang_f if lang_f != "Toutes" else "Toutes",
        days=_period_opts[period_lbl],
    )

    # ── Barre info + export ─────────────────────────────────────────────────
    bi1, bi2 = st.columns([4, 1])
    with bi1:
        st.caption(f"{len(docs)} document(s) trouvé(s)")
    with bi2:
        if docs:
            import pandas as pd
            _df_exp = pd.DataFrame([{
                "ID": d["id"], "Nom": d["original_name"],
                "Type": d["doc_category"], "Langue": d["language"],
                "Statut": d["status"], "Taille (o)": d["size_bytes"],
                "Date": d["upload_date"],
            } for d in docs])
            st.download_button(
                "Exporter CSV",
                _df_exp.to_csv(index=False).encode("utf-8"),
                "documents_admin.csv", "text/csv",
                use_container_width=True, key="adm_exp_csv",
            )

    if not docs:
        st.info("Aucun document ne correspond aux critères.")
    else:
        for doc in docs:
            _did    = doc["id"]
            _status_badge = {"traité": "badge-ok", "uploadé": "badge-wait",
                             "erreur": "badge-err"}.get(doc["status"], "badge-wait")
            _sz_str = f"{doc['size_bytes'] // 1024} Ko" if doc.get("size_bytes") else "—"

            with st.container():
                # ── Ligne d'info principale ───────────────────────────────
                li1, li2 = st.columns([3, 2])
                with li1:
                    st.markdown(
                        f'<span style="font-weight:600;color:#0D1B2E;font-size:0.92rem;">'
                        f'<span style="color:#0066B2;">#{_did}</span>'
                        f' — {doc["original_name"]}</span>'
                        f'&nbsp;&nbsp;<span class="{_status_badge}">{doc["status"]}</span>',
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f'Type : {doc["doc_category"].replace("_"," ").capitalize()} · '
                        f'Langue : {doc["language"].capitalize()} · '
                        f'{_sz_str} · {doc["upload_date"][:16]}'
                    )
                with li2:
                    # Changer catégorie
                    _ci = _CATS.index(doc["doc_category"]) if doc["doc_category"] in _CATS else len(_CATS) - 1
                    new_cat = st.selectbox(
                        "Catégorie", _CATS, index=_ci,
                        key=f"adm_cat_{_did}",
                        label_visibility="collapsed",
                        format_func=lambda x: x.replace("_", " ").capitalize(),
                    )
                    if new_cat != doc["doc_category"]:
                        _db.update_category(_did, new_cat)
                        st.rerun()

                # ── Changer statut + actions ──────────────────────────────
                ac1, ac2, ac3, ac4 = st.columns([2, 2, 2, 1])
                with ac1:
                    _si = _STATUS.index(doc["status"]) if doc["status"] in _STATUS else 0
                    new_st = st.selectbox(
                        "Statut", _STATUS, index=_si,
                        key=f"adm_st_{_did}",
                        label_visibility="collapsed",
                    )
                    if new_st != doc["status"]:
                        _db.update_status(_did, new_st)
                        st.rerun()

                with ac2:
                    if st.button(
                        "Voir texte OCR",
                        key=f"adm_ocr_{_did}",
                        use_container_width=True,
                    ):
                        _key = f"adm_show_ocr_{_did}"
                        st.session_state[_key] = not st.session_state.get(_key, False)

                with ac3:
                    _fp = Path(doc["file_path"]) if doc.get("file_path") else None
                    if _fp and _fp.exists():
                        with open(_fp, "rb") as _fh:
                            st.download_button(
                                "Télécharger",
                                _fh.read(),
                                file_name=doc["original_name"],
                                key=f"adm_dl_{_did}",
                                use_container_width=True,
                            )
                    else:
                        st.button("Fichier absent", disabled=True,
                                  key=f"adm_dl_{_did}", use_container_width=True)

                with ac4:
                    if st.button("Suppr.", key=f"adm_del_{_did}",
                                 type="primary", use_container_width=True):
                        st.session_state[f"adm_cdel_{_did}"] = True

                # ── Texte OCR (dépliable) ─────────────────────────────────
                if st.session_state.get(f"adm_show_ocr_{_did}"):
                    ocr_txt = doc.get("ocr_text") or ""
                    st.text_area(
                        "Texte OCR",
                        value=ocr_txt if ocr_txt else "(aucun texte OCR enregistré)",
                        height=170,
                        key=f"adm_ocrtxt_{_did}",
                        disabled=True,
                        label_visibility="collapsed",
                    )

                # ── Confirmation suppression ──────────────────────────────
                if st.session_state.get(f"adm_cdel_{_did}"):
                    st.warning(
                        f"Supprimer **{doc['original_name']}** (ID #{_did}) ? "
                        "Cette action est irréversible et supprime aussi le fichier physique."
                    )
                    dy, dn, _ = st.columns([1, 1, 5])
                    if dy.button("Oui, supprimer", key=f"adm_ydel_{_did}", type="primary"):
                        try:
                            _rfp = Path(doc["file_path"])
                            if _rfp.exists():
                                _rfp.unlink()
                        except Exception:
                            pass
                        _db.delete_document(_did)
                        st.session_state.pop(f"adm_cdel_{_did}", None)
                        st.success(f"Document #{_did} supprimé.")
                        st.rerun()
                    if dn.button("Annuler", key=f"adm_ndel_{_did}"):
                        st.session_state.pop(f"adm_cdel_{_did}", None)
                        st.rerun()

            st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# ONGLET 3 — Gestion des Utilisateurs (CRUD complet)
# ══════════════════════════════════════════════════════════════════════════════
with tab_users:
    utab_list, utab_add = st.tabs(["Liste des utilisateurs", "Ajouter un utilisateur"])

    # ── Liste des utilisateurs ──────────────────────────────────────────────
    with utab_list:
        users    = _auth.list_users()
        n_admins = _auth.count_admins()

        if not users:
            st.info("Aucun utilisateur enregistré.")
        else:
            st.caption(f"{len(users)} compte(s) enregistré(s)")

            for u in users:
                uid      = u["id"]
                uname    = u["username"]
                dname    = u["display_name"]
                email    = u["email"] or "—"
                role     = u["role"]
                active   = bool(u["is_active"])
                verified = bool(u.get("email_verified", 1))
                last     = u["last_login"] or "Jamais"
                if last != "Jamais":
                    last = last[:16].replace("T", " ")
                is_me  = (uname == st.session_state.get("username"))

                with st.container():
                    ui1, ui2, ui3 = st.columns([3, 1.5, 3.5], gap="small")

                    with ui1:
                        _br = ('<span class="badge-admin">Admin</span>'
                               if role == "admin"
                               else '<span class="badge-user">Utilisateur</span>')
                        _ba = '' if active else '<span class="badge-inactive">Inactif</span>'
                        _bv = ('' if verified
                               else '<span style="display:inline-block;background:#FFF3E0;'
                                    'color:#E65100;font-size:0.68rem;font-weight:700;'
                                    'padding:0.05rem 0.45rem;border-radius:20px;'
                                    'border:1px solid #FFCC80;">Email non vérifié</span>')
                        st.markdown(
                            f'**{dname}** &nbsp; `{uname}`  \n'
                            f'<span style="font-size:0.78rem;color:#6B8099;">'
                            f'{email} &nbsp;·&nbsp; Dernière connexion : {last}'
                            f'</span>',
                            unsafe_allow_html=True,
                        )

                    with ui2:
                        st.markdown(
                            f'{_br}&nbsp;&nbsp;{_ba}',
                            unsafe_allow_html=True,
                        )
                        if _bv:
                            st.markdown(_bv, unsafe_allow_html=True)

                    with ui3:
                        ua1, ua2, ua3, ua4 = st.columns(4)

                        # Activer / Désactiver
                        with ua1:
                            _can_tog = not (is_me or (role == "admin" and n_admins <= 1))
                            if st.button(
                                "Désactiver" if active else "Activer",
                                key=f"utog_{uid}",
                                use_container_width=True,
                                disabled=not _can_tog,
                                help=("Impossible de désactiver le dernier admin ou votre propre compte"
                                      if not _can_tog else ""),
                            ):
                                _auth.toggle_active(uid, not active)
                                st.rerun()

                        # Vérifier email manuellement
                        with ua2:
                            if not verified:
                                if st.button(
                                    "✓ Email",
                                    key=f"uverif_{uid}",
                                    use_container_width=True,
                                    help="Marquer l'email comme vérifié manuellement",
                                ):
                                    with _auth._get_conn() as _c:
                                        _c.execute(
                                            "UPDATE users SET email_verified = 1 WHERE id = ?",
                                            (uid,),
                                        )
                                        _c.commit()
                                    st.success(f"Email de {dname} vérifié.")
                                    st.rerun()
                            else:
                                st.markdown(
                                    '<span style="color:#18A055;font-size:0.78rem;">✓ vérifié</span>',
                                    unsafe_allow_html=True,
                                )

                        # Changer mot de passe
                        with ua3:
                            if st.button("Mdp", key=f"upwd_{uid}",
                                         use_container_width=True,
                                         help="Changer le mot de passe"):
                                _k = f"upwd_show_{uid}"
                                st.session_state[_k] = not st.session_state.get(_k, False)

                        # Supprimer
                        with ua4:
                            _can_del = not is_me and not (role == "admin" and n_admins <= 1)
                            if st.button(
                                "Suppr.", key=f"udel_{uid}",
                                type="primary", use_container_width=True,
                                disabled=not _can_del,
                                help=("Impossible de supprimer le dernier admin ou votre propre compte"
                                      if not _can_del else "Supprimer cet utilisateur"),
                            ):
                                st.session_state[f"udel_confirm_{uid}"] = True

                    # Formulaire changement mot de passe (inline)
                    if st.session_state.get(f"upwd_show_{uid}"):
                        with st.form(key=f"form_upwd_{uid}"):
                            new_pw = st.text_input(
                                f"Nouveau mot de passe pour {uname}",
                                type="password",
                                placeholder="Minimum 6 caractères",
                            )
                            sb, cb = st.columns(2)
                            submitted = sb.form_submit_button("Valider", type="primary")
                            cancelled = cb.form_submit_button("Annuler")
                            if submitted:
                                if len(new_pw) < 6:
                                    st.error("Minimum 6 caractères.")
                                else:
                                    _auth.change_password(uname, new_pw)
                                    st.session_state.pop(f"upwd_show_{uid}", None)
                                    st.success(f"Mot de passe de {dname} mis à jour.")
                                    st.rerun()
                            if cancelled:
                                st.session_state.pop(f"upwd_show_{uid}", None)
                                st.rerun()

                    # Confirmation suppression utilisateur
                    if st.session_state.get(f"udel_confirm_{uid}"):
                        st.warning(
                            f"Supprimer le compte **{dname}** (`{uname}`) ? "
                            "Cette action est irréversible."
                        )
                        uy, un, _ = st.columns([1, 1, 5])
                        if uy.button("Oui, supprimer", key=f"uy_{uid}", type="primary"):
                            _auth.delete_user(uid)
                            st.session_state.pop(f"udel_confirm_{uid}", None)
                            st.success(f"Compte « {dname} » supprimé.")
                            st.rerun()
                        if un.button("Annuler", key=f"un_{uid}"):
                            st.session_state.pop(f"udel_confirm_{uid}", None)
                            st.rerun()

                st.divider()

    # ── Ajouter un utilisateur ──────────────────────────────────────────────
    with utab_add:
        with st.form("adm_add_user", clear_on_submit=True):
            st.markdown("**Nouveau compte utilisateur**")

            fa1, fa2 = st.columns(2)
            with fa1:
                nu_un   = st.text_input("Nom d'utilisateur *", placeholder="ex : marie.dupont")
                nu_dn   = st.text_input("Nom complet *",       placeholder="ex : Marie Dupont")
            with fa2:
                nu_em   = st.text_input("Email",               placeholder="marie@unilog.com")
                nu_role = st.selectbox(
                    "Rôle", ["user", "admin"],
                    format_func=lambda x: "Administrateur" if x == "admin" else "Utilisateur",
                )

            fp1, fp2 = st.columns(2)
            with fp1:
                nu_pw1 = st.text_input("Mot de passe *",       type="password",
                                       placeholder="Minimum 6 caractères")
            with fp2:
                nu_pw2 = st.text_input("Confirmer le mot de passe *", type="password",
                                       placeholder="Répéter")

            if st.form_submit_button("Créer le compte", type="primary",
                                     use_container_width=True):
                errs = []
                if not nu_un.strip():   errs.append("Le nom d'utilisateur est obligatoire.")
                if not nu_dn.strip():   errs.append("Le nom complet est obligatoire.")
                if not nu_pw1:          errs.append("Le mot de passe est obligatoire.")
                elif len(nu_pw1) < 6:   errs.append("Le mot de passe doit comporter au moins 6 caractères.")
                elif nu_pw1 != nu_pw2:  errs.append("Les deux mots de passe ne correspondent pas.")
                for e in errs:
                    st.error(e)
                if not errs:
                    try:
                        _uid = _auth.create_user(
                            username=nu_un.strip(),
                            display_name=nu_dn.strip(),
                            email=nu_em.strip(),
                            password=nu_pw1,
                            role=nu_role,
                        )
                        _rlabel = "Administrateur" if nu_role == "admin" else "Utilisateur"
                        st.success(
                            f"Compte **{nu_dn.strip()}** (`{nu_un.strip()}`) créé "
                            f"avec le rôle {_rlabel} (ID #{_uid})."
                        )
                    except ValueError as ve:
                        st.error(str(ve))

# ══════════════════════════════════════════════════════════════════════════════
# ONGLET 4 — Système
# ══════════════════════════════════════════════════════════════════════════════
with tab_sys:

    # ── Statistiques base de données ───────────────────────────────────────
    st.markdown('<div class="adm-section">Base de données</div>', unsafe_allow_html=True)
    try:
        _c2 = sqlite3.connect(str(_auth.db_path))
        _c2.row_factory = sqlite3.Row
        _now2 = datetime.utcnow().isoformat()
        _db_stats = {
            "Utilisateurs":      _c2.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "Documents":         _c2.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            "Sessions actives":  _c2.execute(
                "SELECT COUNT(*) FROM sessions WHERE expires_at > ?", (_now2,)
            ).fetchone()[0],
            "Sessions expirées": _c2.execute(
                "SELECT COUNT(*) FROM sessions WHERE expires_at <= ?", (_now2,)
            ).fetchone()[0],
        }
        _c2.close()
    except Exception as e:
        _db_stats = {}
        st.error(f"Erreur lecture base de données : {e}")

    if _db_stats:
        _cols_db = st.columns(len(_db_stats))
        _palette = [
            ("#0044A0", "#0077CC"),
            ("#0D6B35", "#18A055"),
            ("#8A5500", "#C07C00"),
            ("#6B1E1E", "#A03030"),
        ]
        for (col, (lbl, val), (c1, c2)) in zip(_cols_db, _db_stats.items(), _palette):
            with col:
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,{c1},{c2});color:white;'
                    f'padding:0.9rem 1rem;border-radius:12px;'
                    f'box-shadow:0 2px 8px rgba(0,0,0,0.12);margin-bottom:0.2rem;">'
                    f'<div style="font-size:0.67rem;opacity:0.82;text-transform:uppercase;'
                    f'letter-spacing:0.08em;">{lbl}</div>'
                    f'<div style="font-size:1.8rem;font-weight:800;margin-top:0.15rem;">{val}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Stockage fichiers ──────────────────────────────────────────────────
    st.markdown('<div class="adm-section" style="margin-top:1.2rem;">Stockage fichiers (data/raw/)</div>',
                unsafe_allow_html=True)
    _raw_dir = Path(__file__).parent.parent.parent / "data" / "raw"
    _stg_rows  = []
    _total_sz  = 0
    _total_fls = 0

    if _raw_dir.exists():
        for _sub in sorted(_raw_dir.iterdir()):
            if _sub.is_dir():
                _fls = [f for f in _sub.iterdir() if f.is_file()]
                _sz  = sum(f.stat().st_size for f in _fls)
                _total_sz  += _sz
                _total_fls += len(_fls)
                if _sz < 1_048_576:
                    _sz_fmt = f"{_sz / 1024:.1f} Ko"
                else:
                    _sz_fmt = f"{_sz / 1_048_576:.2f} Mo"
                _stg_rows.append({"Dossier": _sub.name, "Fichiers": len(_fls), "Taille": _sz_fmt})

        _sz_tot_fmt = (f"{_total_sz / 1024:.1f} Ko"
                       if _total_sz < 1_048_576
                       else f"{_total_sz / 1_048_576:.2f} Mo")
        _stg_rows.append({"Dossier": "TOTAL", "Fichiers": _total_fls, "Taille": _sz_tot_fmt})

    if _stg_rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(_stg_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Dossier data/raw/ introuvable ou vide.")

    # ── Outils de maintenance ──────────────────────────────────────────────
    st.markdown('<div class="adm-section" style="margin-top:1.2rem;">Maintenance</div>',
                unsafe_allow_html=True)
    mc1, mc2, mc3 = st.columns(3)

    with mc1:
        if st.button("Nettoyer sessions expirées",
                     use_container_width=True, key="adm_clean_sess"):
            _auth.cleanup_expired_sessions()
            st.success("Sessions expirées supprimées.")
            st.rerun()

    with mc2:
        if st.button("Supprimer docs en erreur",
                     use_container_width=True, key="adm_del_err"):
            st.session_state["adm_confirm_del_err"] = True

    if st.session_state.get("adm_confirm_del_err"):
        st.warning("Cela supprimera définitivement tous les documents en statut **erreur**.")
        ce1, ce2, _ = st.columns([1, 1, 5])
        if ce1.button("Confirmer", type="primary", key="adm_yes_del_err"):
            try:
                _ce = sqlite3.connect(str(_db.db_path))
                n_del = _ce.execute("SELECT COUNT(*) FROM documents WHERE status='erreur'").fetchone()[0]
                _ce.execute("DELETE FROM documents WHERE status='erreur'")
                _ce.commit()
                _ce.close()
                st.session_state.pop("adm_confirm_del_err", None)
                st.success(f"{n_del} document(s) en erreur supprimé(s).")
                st.rerun()
            except Exception as e:
                st.error(str(e))
        if ce2.button("Annuler", key="adm_no_del_err"):
            st.session_state.pop("adm_confirm_del_err", None)
            st.rerun()

    with mc3:
        try:
            _db_bytes = open(str(_auth.db_path), "rb").read()
            st.download_button(
                "Télécharger sauvegarde DB",
                data=_db_bytes,
                file_name=f"ocr_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                mime="application/octet-stream",
                use_container_width=True,
                key="adm_dl_db",
            )
        except Exception:
            st.button("Sauvegarde indisponible", disabled=True,
                      use_container_width=True, key="adm_dl_db")

    # ── Informations système ───────────────────────────────────────────────
    st.markdown('<div class="adm-section" style="margin-top:1.2rem;">Informations système</div>',
                unsafe_allow_html=True)

    import streamlit as _stv
    _sys_info = [
        ("Python",           platform.python_version()),
        ("Streamlit",        _stv.__version__),
        ("Système d'exploitation", platform.system() + " " + platform.release()),
        ("Base de données",  str(_auth.db_path.resolve())),
        ("Stockage raw",     str(_raw_dir.resolve())),
        ("Heure serveur",    datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
    ]
    for _k, _v in _sys_info:
        st.markdown(
            f'<div class="sysrow">'
            f'<strong style="color:#0055A5;">{_k} :</strong>'
            f'&nbsp;<span style="color:#1E2D40;font-family:monospace;">{_v}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
