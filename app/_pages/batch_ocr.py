"""Page Batch OCR — Traitement en masse + export Label Studio ZIP"""
import streamlit as st
import sys
import io
import zipfile
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

INVOICE_LI_DIR = Path(__file__).parent.parent.parent / "data" / "invoice_li"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

st.markdown("""
<div style='
    background: linear-gradient(135deg, #0055A5 0%, #0088DD 100%);
    padding: 1.2rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.2rem;
    box-shadow: 0 4px 18px rgba(0,85,165,0.22);
'>
    <div style='color:white; font-size:1.4rem; font-weight:700;'>
        Batch OCR — Export Label Studio
    </div>
    <div style='color:rgba(255,255,255,0.8); font-size:0.9rem; margin-top:0.3rem;'>
        Traitement en masse · Fusion spatiale · Export ZIP prêt pour annotation
    </div>
</div>
""", unsafe_allow_html=True)

# ── Scan du dossier ────────────────────────────────────────────────────────────
images = sorted([
    f for f in INVOICE_LI_DIR.iterdir()
    if f.suffix.lower() in IMAGE_EXTS
]) if INVOICE_LI_DIR.exists() else []

if not images:
    st.warning(f"Aucune image trouvée dans `data/invoice_li/`")
    st.stop()

st.info(f"**{len(images)} images** trouvées dans `data/invoice_li/`")

# ── Paramètres ─────────────────────────────────────────────────────────────────
with st.expander("Paramètres OCR", expanded=False):
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        min_conf = st.slider("Confiance minimale", 0.0, 1.0, 0.30, 0.05)
    with col_b:
        y_thresh = st.slider("y_thresh (fusion lignes)", 5, 40, 15)
    with col_c:
        x_gap = st.slider("x_gap_thresh (fusion colonnes)", 10, 100, 40)

# ── Bouton lancement ───────────────────────────────────────────────────────────
if st.button("Lancer le traitement OCR + Fusion", type="primary", use_container_width=True):

    try:
        from ocr.doctr_engine import run_ocr, merge_words_into_lines
        from ocr.label_studio_export import words_to_label_studio_json
        import json as _json
    except ImportError as e:
        st.error(f"Import impossible : {e}")
        st.stop()

    progress_bar = st.progress(0, text="Initialisation…")
    status_box   = st.empty()
    errors       = []
    all_tasks    = []   # toutes les tâches Label Studio (une par image)

    for idx, img_path in enumerate(images):
        pct  = int((idx / len(images)) * 100)
        progress_bar.progress(pct, text=f"[{idx+1}/{len(images)}] {img_path.name}")

        try:
            from PIL import Image as _Image
            pil_img = _Image.open(img_path).convert("RGB")

            # OCR
            ocr_data = run_ocr(pil_img, min_confidence=min_conf)
            words    = ocr_data["words"]
            page_w   = ocr_data["page_w"]
            page_h   = ocr_data["page_h"]

            # Fusion spatiale
            words = merge_words_into_lines(words, y_thresh=y_thresh, x_gap_thresh=x_gap)

            # Export Label Studio
            tasks = words_to_label_studio_json(
                words=words,
                image_name=img_path.name,
                page_w=page_w,
                page_h=page_h,
            )
            all_tasks.extend(tasks)

            # Sauvegarde JSON individuel
            json_path = INVOICE_LI_DIR / (img_path.stem + ".json")
            json_path.write_text(
                _json.dumps(tasks, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        except Exception as e:
            errors.append(f"{img_path.name} : {e}")

    progress_bar.progress(100, text="Terminé !")

    # ── Résumé ─────────────────────────────────────────────────────────────────
    ok_count = len(images) - len(errors)
    st.success(f"{ok_count}/{len(images)} images traitées avec succès.")
    if errors:
        with st.expander(f"{len(errors)} erreur(s)"):
            for err in errors:
                st.error(err)

    # ── ZIP de tous les JSONs ──────────────────────────────────────────────────
    if all_tasks:
        import json as _json2

        # ZIP avec un JSON par image
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for img_path in images:
                json_path = INVOICE_LI_DIR / (img_path.stem + ".json")
                if json_path.exists():
                    zf.write(json_path, arcname=json_path.name)
        zip_buf.seek(0)

        st.download_button(
            label=f"Télécharger tous les JSONs ({ok_count} fichiers) — ZIP",
            data=zip_buf.getvalue(),
            file_name="label_studio_invoice_li.zip",
            mime="application/zip",
            use_container_width=True,
            type="primary",
        )

        # Aussi : un seul JSON global (toutes tâches fusionnées)
        global_json = _json2.dumps(all_tasks, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            label=f"Télécharger JSON global ({len(all_tasks)} tâches) — 1 fichier",
            data=global_json,
            file_name="label_studio_all_tasks.json",
            mime="application/json",
            use_container_width=True,
        )

# ── Aperçu des JSONs déjà générés ─────────────────────────────────────────────
existing_jsons = sorted(INVOICE_LI_DIR.glob("*.json"))
if existing_jsons:
    st.markdown("---")
    st.markdown(f"**{len(existing_jsons)} JSON(s) déjà présents dans le dossier**")

    # ZIP des JSONs existants
    zip_buf2 = io.BytesIO()
    with zipfile.ZipFile(zip_buf2, "w", zipfile.ZIP_DEFLATED) as zf:
        for jp in existing_jsons:
            zf.write(jp, arcname=jp.name)
    zip_buf2.seek(0)

    st.download_button(
        label=f"Télécharger les JSONs existants ({len(existing_jsons)} fichiers) — ZIP",
        data=zip_buf2.getvalue(),
        file_name="label_studio_existing.zip",
        mime="application/zip",
        use_container_width=True,
    )
