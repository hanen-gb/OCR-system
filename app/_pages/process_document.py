"""
Page Traiter un document
Pipeline identique au backend HF Spaces :
    prétraitement → docTR OCR → clean_invoice_ocr → export JSON Label Studio
Pas de fusion spatiale.
"""
import streamlit as st
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

st.markdown("""
<div style='
    background: linear-gradient(135deg, #0055A5 0%, #0088DD 100%);
    padding: 1.2rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.2rem;
    box-shadow: 0 4px 18px rgba(0,85,165,0.22);
'>
    <div style='color:white; font-size:1.4rem; font-weight:700;'>
        Traiter un Document
    </div>
    <div style='color:rgba(255,255,255,0.8); font-size:0.9rem; margin-top:0.3rem;'>
        Prétraitement · OCR docTR · Post-processing · Export JSON Label Studio
    </div>
</div>
""", unsafe_allow_html=True)

# ── Upload ─────────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Déposer une image de facture",
    type=["jpg", "jpeg", "png", "bmp", "tiff", "webp"],
    label_visibility="collapsed",
)

if uploaded_file is None:
    st.info("Déposez une image pour démarrer.")
    st.stop()

# ── Layout : image originale | bounding boxes ──────────────────────────────────
col_img, col_viz = st.columns([1, 1], gap="large")

with col_img:
    st.caption("Image originale")
    st.image(uploaded_file, use_container_width=True)

    if st.button("Lancer OCR", type="primary", use_container_width=True):
        try:
            from PIL import Image as _PIL
            from preprocessing.image_preprocessor import preprocess_for_ocr
            from ocr.doctr_engine import run_ocr, draw_bounding_boxes
            from ocr.post_processor import clean_invoice_ocr

            img_bytes = uploaded_file.getvalue()

            # ── 1. Prétraitement (identique backend) ──────────────────────────
            with st.spinner("Prétraitement…"):
                pil_pre = preprocess_for_ocr(
                    img_bytes,
                    dpi=200,
                    denoise=True,
                    deskew=True,
                    binarize=True,
                    return_pil=True,
                )

            # ── 2. OCR docTR ──────────────────────────────────────────────────
            with st.spinner("OCR docTR…"):
                ocr_data = run_ocr(pil_pre, min_confidence=0.30)
                words    = ocr_data["words"]
                page_w   = ocr_data["page_w"]
                page_h   = ocr_data["page_h"]

            # ── 3. Post-processing (clean_invoice_ocr) ────────────────────────
            with st.spinner("Post-processing…"):
                words = clean_invoice_ocr(words)

            # ── Visualisation bounding boxes ──────────────────────────────────
            viz = draw_bounding_boxes(pil_pre, words, show_text=True, show_confidence=False)

            st.session_state["ocr_words"]   = words
            st.session_state["ocr_page_w"]  = page_w
            st.session_state["ocr_page_h"]  = page_h
            st.session_state["ocr_viz"]     = viz
            st.session_state["ocr_imgname"] = uploaded_file.name

        except Exception as e:
            st.error(f"Erreur OCR : {e}")

with col_viz:
    if st.session_state.get("ocr_viz"):
        st.caption("Bounding boxes détectées")
        st.image(st.session_state["ocr_viz"], use_container_width=True)

# ── Texte extrait mot par mot + JSON ──────────────────────────────────────────
if st.session_state.get("ocr_words"):
    words    = st.session_state["ocr_words"]
    page_w   = st.session_state["ocr_page_w"]
    page_h   = st.session_state["ocr_page_h"]
    img_name = st.session_state.get("ocr_imgname", uploaded_file.name)

    st.markdown("---")
    st.markdown(f"### Texte extrait — {len(words)} mots")

    full_text = "\n".join(w["text"] for w in words)
    st.text_area("Texte extrait", value=full_text, height=400, label_visibility="collapsed")

    # ── Export JSON Label Studio ───────────────────────────────────────────────
    st.markdown("---")
    try:
        from ocr.label_studio_export import to_json_bytes
        json_bytes = to_json_bytes(
            words=words,
            image_name=img_name,
            page_w=page_w,
            page_h=page_h,
        )
        stem = Path(img_name).stem
        st.download_button(
            label=f"Télécharger JSON Label Studio — {len(words)} boxes",
            data=json_bytes,
            file_name=f"{stem}_label_studio.json",
            mime="application/json",
            use_container_width=True,
            type="primary",
        )
        st.caption("Importable dans Label Studio · une tâche par image · coordonnées en %")
    except Exception as e:
        st.error(f"Export JSON impossible : {e}")
