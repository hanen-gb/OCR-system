"""
inference_hitl.py — Page Streamlit : Inférence GLM-OCR + Human-in-the-Loop
===========================================================================

Flux :
    1. Upload image facture
    2. Appel API /predict  (backend FastAPI sur Modal GPU T4)
    3. Affichage :
         - Image originale
         - 5 entités extraites par GLM-OCR dans des champs modifiables
    4. Validation humaine → sauvegarde en SQLite (table corrections)
    5. Historique des corrections validées
"""

import io
import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st
from PIL import Image

# ── Configuration ──────────────────────────────────────────────────────────────
DEFAULT_API_URL = "https://<workspace>--glmocr-backend-fastapi-app.modal.run"
DB_PATH         = Path(__file__).parent.parent.parent / "data" / "corrections.db"

LABEL_COLORS = {
    "FOURNISSEUR":    "#E63946",
    "CLIENT":         "#2A9D8F",
    "DATE_FACTURE":   "#E9C46A",
    "NUMERO_FACTURE": "#F4A261",
    "MONTANT_TTC":    "#6A4C93",
}

# Les 5 entités extraites par GLM-OCR — toujours affichées
TARGET_LABELS = ["FOURNISSEUR", "CLIENT", "NUMERO_FACTURE", "DATE_FACTURE", "MONTANT_TTC"]


# ─────────────────────────────────────────────────────────────────────────────
# SQLite — Gestion des corrections HITL
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS corrections (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT    NOT NULL,
            filename    TEXT,
            label       TEXT    NOT NULL,
            original    TEXT,
            corrected   TEXT    NOT NULL,
            validated   INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


def save_corrections(filename: str, corrections: list[dict]):
    now  = datetime.utcnow().isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    for c in corrections:
        conn.execute(
            "INSERT INTO corrections (created_at, filename, label, original, corrected) "
            "VALUES (?, ?, ?, ?, ?)",
            (now, filename, c["label"], c["original"], c["corrected"]),
        )
    conn.commit()
    conn.close()


def load_corrections_history(limit: int = 50) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT id, created_at, filename, label, original, corrected "
        "FROM corrections ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(zip(["id", "created_at", "filename", "label", "original", "corrected"], r))
            for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Appel API
# ─────────────────────────────────────────────────────────────────────────────

def _check_health(timeout: int = 15) -> bool:
    try:
        r = requests.get(f"{DEFAULT_API_URL}/health", timeout=timeout)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


def _wake_backend(progress_placeholder) -> bool:
    """Attend que le backend Modal réponde (cold start ~40s). Max 3 min."""
    bar = progress_placeholder.progress(0, text="Démarrage du GPU Modal (GLM-OCR)...")
    for attempt in range(36):  # 36 × 5s = 3 min max
        bar.progress(min(95, (attempt + 1) * 3),
                     text=f"Démarrage GPU en cours… ({attempt * 5}s)")
        try:
            r = requests.get(f"{DEFAULT_API_URL}/health", timeout=10)
            if r.status_code == 200 and r.json().get("status") == "ok":
                bar.progress(100, text="Backend GLM-OCR prêt !")
                time.sleep(0.5)
                progress_placeholder.empty()
                return True
        except Exception:
            pass
        time.sleep(5)
    progress_placeholder.empty()
    return False


def call_predict_api(file_bytes: bytes, filename: str) -> dict | None:
    try:
        resp = requests.post(
            f"{DEFAULT_API_URL}/predict",
            files={"file": (filename, file_bytes, "image/jpeg")},
            timeout=300,  # 5 min — couvre le cold start + inference GLM
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"__error__": "connection_error"}
    except requests.exceptions.Timeout:
        return {"__error__": "Timeout — le backend GLM-OCR met trop de temps à répondre (> 5 min)"}
    except requests.exceptions.HTTPError as e:
        return {"__error__": f"Erreur backend {e.response.status_code} : {e.response.text[:300]}"}
    except Exception as e:
        return {"__error__": f"Erreur inattendue : {e}"}


def call_predict_with_progress(file_bytes: bytes, filename: str):
    """Lance l'appel API en thread + affiche une progression adaptée GLM-OCR."""

    shared = {"done": False, "result": None}

    def _worker():
        shared["result"] = call_predict_api(file_bytes, filename)
        shared["done"] = True

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    steps = [
        (8,  "Envoi de l'image au backend Modal..."),
        (20, "Démarrage du container GPU T4..."),
        (40, "Chargement du modèle GLM-OCR (si cold start)..."),
        (65, "Analyse de la facture par GLM-OCR..."),
        (88, "Extraction et structuration des entités..."),
    ]

    progress_bar = st.progress(0, text="Initialisation...")
    step_idx = 0
    t_start  = time.time()

    while not shared["done"]:
        elapsed = time.time() - t_start
        if step_idx < len(steps) and elapsed > step_idx * 8:
            pct, msg = steps[step_idx]
            progress_bar.progress(pct, text=msg)
            step_idx += 1
        time.sleep(0.4)

    progress_bar.progress(100, text="Analyse terminée !")
    time.sleep(0.4)
    progress_bar.empty()

    return shared["result"]


# ─────────────────────────────────────────────────────────────────────────────
# Page principale
# ─────────────────────────────────────────────────────────────────────────────

def render():
    init_db()

    # ── En-tête ───────────────────────────────────────────────────────────────
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0055A5,#0088DD);
                padding:1.2rem 2rem;border-radius:14px;margin-bottom:1rem;
                box-shadow:0 4px 18px rgba(0,85,165,.22);'>
        <div style='color:white;font-size:1.4rem;font-weight:700;'>
            Extraction de Factures — GLM-OCR + Correction Humaine
        </div>
        <div style='color:#cce4ff;font-size:.85rem;margin-top:.3rem;'>
            Modèle GLM-OCR fine-tuné sur factures tunisiennes · GPU T4 (Modal) · Human-in-the-Loop
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Statut backend dans la sidebar ────────────────────────────────────────
    with st.sidebar:
        st.markdown("---")
        _status_ph = st.empty()
        if st.session_state.get("backend_ready"):
            _status_ph.markdown(
                "<span style='color:#4CAF50;font-size:.8rem;'>● GLM-OCR connecté (GPU T4)</span>",
                unsafe_allow_html=True,
            )
        else:
            _status_ph.markdown(
                "<span style='color:#FFA726;font-size:.8rem;'>● Vérification backend…</span>",
                unsafe_allow_html=True,
            )

    # ── Upload ────────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "Uploader une facture (JPG, PNG)",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed",
    )

    if uploaded is None:
        st.info("Uploadez une image de facture pour démarrer l'analyse GLM-OCR.")
        _show_history()
        return

    img_bytes = uploaded.read()
    file_key  = f"{uploaded.name}_{len(img_bytes)}"

    if st.session_state.get("last_file_key") != file_key:
        st.session_state["predict_result"] = None
        st.session_state["last_file_key"]  = file_key

    result = st.session_state.get("predict_result")

    # ── AVANT analyse : aperçu + bouton ───────────────────────────────────────
    if not result:
        col_prev, col_btn = st.columns([1, 2], gap="medium")
        with col_prev:
            try:
                st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
            except Exception:
                st.caption("Aperçu non disponible.")
        with col_btn:
            st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
            st.info("**Première analyse** : le cold start GPU peut prendre ~40s.")
            if st.button("Analyser la facture", type="primary"):
                t0  = time.time()
                res = call_predict_with_progress(img_bytes, uploaded.name)

                # Si connection_error → le backend est en veille, on attend
                if res and res.get("__error__") == "connection_error":
                    wake_ph = st.empty()
                    wake_ph.warning("Backend en veille — démarrage automatique du GPU...")
                    woke = _wake_backend(st.empty())
                    wake_ph.empty()
                    if woke:
                        res = call_predict_with_progress(img_bytes, uploaded.name)
                    else:
                        res = {"__error__": "Le backend n'a pas démarré après 3 minutes. Réessayez."}

                elapsed = time.time() - t0

                if res and "__error__" in res:
                    st.error(res["__error__"])
                    st.session_state["backend_ready"] = False
                elif res:
                    st.session_state["predict_result"] = res
                    st.session_state["backend_ready"]  = True
                    timing = res.get("timing", {})
                    ms = timing.get("inference_ms", timing.get("total_ms", 0))
                    st.success(
                        f"{len(res.get('entities', []))} entités extraites "
                        f"en {elapsed:.1f}s  (inférence GLM : {ms}ms)"
                    )
                    st.rerun()
        return

    # ── APRÈS analyse : résultats ─────────────────────────────────────────────
    entities = result.get("entities", [])

    st.markdown("### Résultats de l'analyse")

    if st.button("Nouvelle analyse", type="secondary"):
        st.session_state["predict_result"] = None
        st.rerun()

    col_img, col_hitl = st.columns([1, 1], gap="large")

    # ── Image originale ───────────────────────────────────────────────────────
    with col_img:
        st.markdown("**Image de la facture**")
        try:
            st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
        except Exception as e:
            st.warning(f"Impossible d'afficher l'image : {e}")

    # ── Human-in-the-Loop ─────────────────────────────────────────────────────
    with col_hitl:
        st.markdown("**Champs extraits — 5 entités GLM-OCR**")
        st.caption("Cliquez sur ✎ pour corriger une valeur avant validation.")

        # Construire dictionnaire label → texte extrait
        detected: dict[str, str] = {}
        for ent in entities:
            lbl = ent.get("label", "")
            if lbl in TARGET_LABELS and lbl not in detected:
                detected[lbl] = ent.get("text", "")

        corrections_inputs = {}

        for label in TARGET_LABELS:
            color    = LABEL_COLORS.get(label, "#CCCCCC")
            val      = detected.get(label, "")
            edit_key = f"edit_{label}_{file_key}"

            if edit_key not in st.session_state:
                st.session_state[edit_key] = False

            detected_badge = (
                "<span style='background:#4CAF50;color:white;"
                "padding:1px 7px;border-radius:10px;font-size:.72rem;"
                "margin-left:6px;'>détecté</span>"
                if val else
                "<span style='color:#aaa;font-size:.72rem;margin-left:6px;'>non détecté</span>"
            )

            st.markdown(
                f"<div style='margin-top:10px;'>"
                f"<span style='background:{color};color:white;padding:2px 10px;"
                f"border-radius:6px;font-size:.8rem;font-weight:600;'>"
                f"{label}</span>{detected_badge}</div>",
                unsafe_allow_html=True,
            )

            col_val, col_btn = st.columns([5, 1])
            with col_val:
                if st.session_state[edit_key]:
                    new_val = st.text_input(
                        label=label, value=val,
                        key=f"input_{label}_{file_key}",
                        label_visibility="collapsed",
                    )
                else:
                    display = val if val else "—"
                    st.markdown(
                        f"<div style='padding:6px 10px;border:1px solid {color};"
                        f"border-radius:6px;min-height:36px;"
                        f"color:{'#333' if val else '#aaa'};font-size:.9rem;'>"
                        f"{display}</div>",
                        unsafe_allow_html=True,
                    )
                    new_val = val

            with col_btn:
                icon = "\u270e" if not st.session_state[edit_key] else "\u00d7"
                if st.button(icon, key=f"btn_{label}_{file_key}", help="Corriger"):
                    st.session_state[edit_key] = not st.session_state[edit_key]
                    st.rerun()

            corrections_inputs[label] = {
                "label":     label,
                "original":  val,
                "corrected": new_val if st.session_state[edit_key] else val,
            }

        st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
        if st.button("Valider et sauvegarder", type="primary", use_container_width=True):
            all_entries = list(corrections_inputs.values())
            changed     = [c for c in all_entries if c["original"] != c["corrected"]]
            save_corrections(uploaded.name, all_entries)
            for label in TARGET_LABELS:
                st.session_state[f"edit_{label}_{file_key}"] = False
            st.success(
                f"Sauvegardé ! {len(changed)} correction(s) "
                f"+ {len(all_entries) - len(changed)} valeur(s) confirmée(s)."
            )

    # ── Réponse brute GLM-OCR ─────────────────────────────────────────────────
    with st.expander("Réponse brute GLM-OCR", expanded=False):
        st.text_area(
            "glm_raw",
            value=result.get("full_text", ""),
            height=200,
            label_visibility="collapsed",
        )

    # ── Export JSON ───────────────────────────────────────────────────────────
    with st.expander("Exporter les résultats", expanded=False):
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "Télécharger JSON complet",
                data=json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"{Path(uploaded.name).stem}_glmocr.json",
                mime="application/json",
                use_container_width=True,
            )
        with col_dl2:
            entities_only = [{"label": e["label"], "text": e["text"]} for e in entities]
            st.download_button(
                "Télécharger Entités (.json)",
                data=json.dumps(entities_only, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"{Path(uploaded.name).stem}_entities.json",
                mime="application/json",
                use_container_width=True,
            )

    _show_history()


def _show_history():
    history = load_corrections_history(50)
    if not history:
        return

    st.markdown("---")
    with st.expander(f"Historique des corrections HITL ({len(history)} entrées)", expanded=False):
        import pandas as pd
        df = pd.DataFrame(history)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(
            df[["created_at", "filename", "label", "original", "corrected"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "created_at": st.column_config.TextColumn("Date"),
                "filename":   st.column_config.TextColumn("Fichier"),
                "label":      st.column_config.TextColumn("Champ"),
                "original":   st.column_config.TextColumn("Valeur GLM-OCR"),
                "corrected":  st.column_config.TextColumn("Correction humaine"),
            },
        )


if __name__ == "__main__":
    render()
else:
    render()
