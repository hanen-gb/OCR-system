"""
Composant File Uploader pour l'application Streamlit
US-01: Upload de documents
"""

import streamlit as st
from typing import Optional
from io import BytesIO

# Formats supportés
SUPPORTED_IMAGE_FORMATS = ["jpg", "jpeg", "png"]
SUPPORTED_DOCUMENT_FORMATS = ["pdf"]
ALL_SUPPORTED_FORMATS = SUPPORTED_IMAGE_FORMATS + SUPPORTED_DOCUMENT_FORMATS

def render_file_uploader() -> Optional[BytesIO]:
    """
    Affiche un widget d'upload de fichiers avec validation
    
    Returns:
        BytesIO: Le fichier uploadé si valide, None sinon
    """
    
    # Widget d'upload
    uploaded_file = st.file_uploader(
        "Choisir un document à traiter",
        type=ALL_SUPPORTED_FORMATS,
        help="Formats acceptés: JPG, PNG, PDF (max 10 MB)",
        accept_multiple_files=False
    )
    
    # Validation du fichier
    if uploaded_file is not None:
        # Vérifier la taille (max 10 MB)
        file_size_mb = uploaded_file.size / (1024 * 1024)
        
        if file_size_mb > 10:
            st.error("❌ Erreur: Le fichier est trop volumineux (max 10 MB)")
            return None
        
        # Vérifier l'extension
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in ALL_SUPPORTED_FORMATS:
            st.error(f"❌ Erreur: Format '{file_extension}' non supporté")
            st.info(f"Formats acceptés: {', '.join(ALL_SUPPORTED_FORMATS).upper()}")
            return None
        
        return uploaded_file
    
    return None


def display_upload_stats(uploaded_file: BytesIO) -> None:
    """
    Affiche les statistiques du fichier uploadé
    
    Args:
        uploaded_file: Le fichier uploadé
    """
    if uploaded_file is None:
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📄 Nom", uploaded_file.name)
    
    with col2:
        size_mb = uploaded_file.size / (1024 * 1024)
        st.metric("📦 Taille", f"{size_mb:.2f} MB")
    
    with col3:
        extension = uploaded_file.name.split('.')[-1].upper()
        st.metric("🏷️ Format", extension)