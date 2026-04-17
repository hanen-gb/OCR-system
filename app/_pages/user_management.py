"""Page Gestion des Utilisateurs — Réservée aux administrateurs."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

import streamlit as st
from database.auth_db import AuthManager

# Sécurité — double vérification côté page
if st.session_state.get("user_role") != "admin":
    st.error("Accès réservé aux administrateurs.")
    st.stop()

_auth = AuthManager()

# ── En-tête ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style='
    background: linear-gradient(135deg, #0055A5 0%, #0088DD 100%);
    padding: 1.2rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.4rem;
    box-shadow: 0 4px 18px rgba(0,85,165,0.22);
'>
    <div style='color:white; font-size:1.4rem; font-weight:700; letter-spacing:-0.01em;'>
        Gestion des Utilisateurs
    </div>
    <div style='color:rgba(255,255,255,0.72); font-size:0.82rem; margin-top:0.2rem;'>
        Créer, activer / désactiver et supprimer des comptes
    </div>
</div>
""", unsafe_allow_html=True)

# CSS spécifique à cette page
st.markdown("""
<style>
/* Badges rôle */
.badge-admin {
    display:inline-block; background:#0055A5; color:white;
    font-size:0.7rem; font-weight:700; padding:0.1rem 0.5rem;
    border-radius:20px; letter-spacing:0.05em; text-transform:uppercase;
}
.badge-user {
    display:inline-block; background:#E3F2FD; color:#0055A5;
    font-size:0.7rem; font-weight:700; padding:0.1rem 0.5rem;
    border-radius:20px; letter-spacing:0.05em; text-transform:uppercase;
    border: 1px solid #BBDEFB;
}
.badge-inactive {
    display:inline-block; background:#FFF3E0; color:#E65100;
    font-size:0.7rem; font-weight:700; padding:0.1rem 0.5rem;
    border-radius:20px; letter-spacing:0.05em; text-transform:uppercase;
    border: 1px solid #FFCC80;
}
/* Card section */
.um-card {
    background: white;
    border: 1px solid #DDE5EF;
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 1px 6px rgba(0,0,0,0.05);
}
.um-section-title {
    font-size: 1rem;
    font-weight: 700;
    color: #0D1B2E;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #EEF2F7;
}
/* Bouton danger */
.stButton > button[data-danger="true"] {
    background-color: #FFEBEE !important;
    color: #C62828 !important;
    border-color: #EF9A9A !important;
}
</style>
""", unsafe_allow_html=True)

tab_liste, tab_ajouter = st.tabs(["Liste des utilisateurs", "Ajouter un utilisateur"])

# ═════════════════════════════════════════════════════════════════════════════
# Onglet 1 — Liste des utilisateurs
# ═════════════════════════════════════════════════════════════════════════════
with tab_liste:
    users = _auth.list_users()
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
            last     = u["last_login"] or "Jamais"
            if last != "Jamais":
                last = last[:16].replace("T", " ")
            is_me    = (uname == st.session_state.get("username"))

            with st.container():
                col_info, col_badge, col_act = st.columns([3, 1.5, 2], gap="small")

                with col_info:
                    st.markdown(
                        f"**{dname}** &nbsp; `{uname}`  \n"
                        f"<span style='font-size:0.8rem;color:#6B8099;'>"
                        f"{email} &nbsp;·&nbsp; Dernière connexion : {last}"
                        f"</span>",
                        unsafe_allow_html=True,
                    )

                with col_badge:
                    badge_role = (
                        '<span class="badge-admin">Admin</span>'
                        if role == "admin"
                        else '<span class="badge-user">Utilisateur</span>'
                    )
                    badge_act = (
                        "" if active
                        else '<span class="badge-inactive">Inactif</span>'
                    )
                    st.markdown(
                        f"{badge_role}&nbsp;&nbsp;{badge_act}",
                        unsafe_allow_html=True,
                    )

                with col_act:
                    a1, a2, a3 = st.columns(3)

                    # ── Activer / Désactiver ──────────────────────────────────
                    with a1:
                        _toggle_label = "Désactiver" if active else "Activer"
                        _can_toggle = not (is_me or (role == "admin" and n_admins <= 1))
                        if st.button(
                            _toggle_label, key=f"tog_{uid}",
                            use_container_width=True,
                            disabled=not _can_toggle,
                            help="Impossible de désactiver le dernier admin ou votre propre compte" if not _can_toggle else "",
                        ):
                            _auth.toggle_active(uid, not active)
                            st.rerun()

                    # ── Changer le mot de passe ───────────────────────────────
                    with a2:
                        if st.button("Mdp", key=f"pwd_{uid}", use_container_width=True,
                                     help="Changer le mot de passe"):
                            st.session_state[f"show_pwd_{uid}"] = not st.session_state.get(f"show_pwd_{uid}", False)

                    # ── Supprimer ─────────────────────────────────────────────
                    with a3:
                        _can_del = not is_me and not (role == "admin" and n_admins <= 1)
                        if st.button("Suppr.", key=f"del_{uid}",
                                     use_container_width=True, type="primary",
                                     disabled=not _can_del,
                                     help="Impossible de supprimer le dernier admin ou votre propre compte" if not _can_del else "Supprimer cet utilisateur"):
                            st.session_state[f"confirm_del_{uid}"] = True

                # ── Formulaire changement mdp (inline) ───────────────────────
                if st.session_state.get(f"show_pwd_{uid}"):
                    with st.form(key=f"form_pwd_{uid}"):
                        new_pwd = st.text_input(
                            f"Nouveau mot de passe pour {uname}",
                            type="password",
                            placeholder="Minimum 6 caractères",
                        )
                        c_ok, c_cancel = st.columns(2)
                        submitted = c_ok.form_submit_button("Valider", type="primary")
                        cancelled = c_cancel.form_submit_button("Annuler")
                        if submitted:
                            if len(new_pwd) < 6:
                                st.error("Le mot de passe doit comporter au moins 6 caractères.")
                            else:
                                _auth.change_password(uname, new_pwd)
                                st.session_state.pop(f"show_pwd_{uid}", None)
                                st.success(f"Mot de passe de {dname} mis à jour.")
                                st.rerun()
                        if cancelled:
                            st.session_state.pop(f"show_pwd_{uid}", None)
                            st.rerun()

                # ── Confirmation suppression ──────────────────────────────────
                if st.session_state.get(f"confirm_del_{uid}"):
                    st.warning(
                        f"Confirmer la suppression du compte **{dname}** (`{uname}`) ? "
                        "Cette action est irréversible."
                    )
                    c_yes, c_no, _ = st.columns([1, 1, 3])
                    if c_yes.button("Oui, supprimer", key=f"yes_del_{uid}", type="primary"):
                        _auth.delete_user(uid)
                        st.session_state.pop(f"confirm_del_{uid}", None)
                        st.success(f"Compte « {dname} » supprimé.")
                        st.rerun()
                    if c_no.button("Annuler", key=f"no_del_{uid}"):
                        st.session_state.pop(f"confirm_del_{uid}", None)
                        st.rerun()

            st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# Onglet 2 — Ajouter un utilisateur
# ═════════════════════════════════════════════════════════════════════════════
with tab_ajouter:
    with st.form("form_add_user", clear_on_submit=True):
        st.markdown("**Nouveau compte utilisateur**")

        col_a, col_b = st.columns(2)
        with col_a:
            new_uname  = st.text_input("Nom d'utilisateur *", placeholder="ex : marie.dupont")
            new_dname  = st.text_input("Nom complet *",       placeholder="ex : Marie Dupont")
        with col_b:
            new_email  = st.text_input("Email",               placeholder="marie@unilog.com")
            new_role   = st.selectbox("Rôle", ["user", "admin"],
                                      format_func=lambda x: "Administrateur" if x == "admin" else "Utilisateur")

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            new_pwd    = st.text_input("Mot de passe *",   type="password", placeholder="Minimum 6 caractères")
        with col_p2:
            new_pwd2   = st.text_input("Confirmer le mot de passe *", type="password", placeholder="Répéter")

        submitted = st.form_submit_button("Créer le compte", type="primary", use_container_width=True)

        if submitted:
            errors = []
            if not new_uname.strip():
                errors.append("Le nom d'utilisateur est obligatoire.")
            if not new_dname.strip():
                errors.append("Le nom complet est obligatoire.")
            if not new_pwd:
                errors.append("Le mot de passe est obligatoire.")
            elif len(new_pwd) < 6:
                errors.append("Le mot de passe doit comporter au moins 6 caractères.")
            elif new_pwd != new_pwd2:
                errors.append("Les deux mots de passe ne correspondent pas.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                try:
                    _uid = _auth.create_user(
                        username=new_uname.strip(),
                        display_name=new_dname.strip(),
                        email=new_email.strip(),
                        password=new_pwd,
                        role=new_role,
                    )
                    st.success(
                        f"Compte **{new_dname.strip()}** (`{new_uname.strip()}`) créé "
                        f"avec le rôle {'Administrateur' if new_role == 'admin' else 'Utilisateur'} (ID #{_uid})."
                    )
                except ValueError as ve:
                    st.error(str(ve))
