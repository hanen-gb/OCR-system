"""
Composant d'affichage de la langue détectée
US-02: Détection automatique de la langue
VERSION CORRIGÉE - Affichage Streamlit natif
"""

import streamlit as st
from typing import Dict


def display_language_detection(language_info: Dict) -> None:
    """
    Affiche les informations de langue détectée avec composants Streamlit natifs
    
    Args:
        language_info: Dictionnaire avec les infos de langue
    """
    
    if 'error' in language_info:
        st.warning(f"⚠️ {language_info['error']}")
        return
    
    # Déterminer le statut et la couleur
    if language_info['is_supported']:
        status_emoji = "✅"
        status_text = "Supportée"
    else:
        status_emoji = "⚠️"
        status_text = "Non supportée"
    
    # Déterminer la couleur de confiance
    confidence = language_info['confidence']
    if confidence >= 0.9:
        conf_emoji = "🟢"
    elif confidence >= 0.7:
        conf_emoji = "🔵"
    elif confidence >= 0.5:
        conf_emoji = "🟡"
    else:
        conf_emoji = "🔴"
    
    # Container principal
    with st.container():
        # En-tête avec nom de langue et statut
        col_header1, col_header2 = st.columns([3, 1])
        with col_header1:
            st.markdown(f"### 🌍 {language_info['language_name']}")
        with col_header2:
            st.success(f"{status_emoji} {status_text}")
        
        st.markdown("---")
        
        # Informations principales
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                label="CODE LANGUE",
                value=language_info['language_code'].upper(),
                delta=None
            )
        
        with col2:
            st.metric(
                label="CONFIANCE",
                value=f"{confidence * 100:.1f}%",
                delta=None
            )
        
        # Méthode de détection si disponible
        if 'detection_method' in language_info:
            method_text = {
                'filename': 'Basée sur le nom du fichier',
                'text_analysis': 'Analyse textuelle complète',
                'default': 'Langue par défaut'
            }.get(language_info['detection_method'], 'Automatique')
            
            st.caption(f"📊 Méthode: {method_text}")
    
    # Afficher les probabilités alternatives si disponibles
    if language_info.get('all_probabilities') and len(language_info['all_probabilities']) > 1:
        with st.expander("📊 Voir toutes les probabilités détectées"):
            for prob in language_info['all_probabilities']:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{prob['name']}** ({prob['code'].upper()})")
                with col2:
                    st.write(f"{prob['confidence']*100:.1f}%")
                st.progress(prob['confidence'])


def display_language_badge(language_code: str, language_name: str, is_supported: bool) -> None:
    """
    Affiche un badge compact de langue avec Streamlit
    
    Args:
        language_code: Code de la langue (ex: 'fr')
        language_name: Nom de la langue (ex: 'Français')
        is_supported: Si la langue est supportée
    """
    status = "✅" if is_supported else "❌"
    st.info(f"{status} **{language_name.upper()}** ({language_code.upper()})")


def display_language_card_simple(language_name: str, language_code: str, confidence: float, is_supported: bool) -> None:
    """
    Affiche une carte simple avec les infos de langue
    Version simplifiée pour éviter les problèmes d'affichage
    
    Args:
        language_name: Nom de la langue
        language_code: Code de la langue
        confidence: Score de confiance
        is_supported: Si supportée
    """
    
    # Créer une carte avec st.container
    with st.container():
        # Titre de la carte
        st.markdown(f"### 🌍 Langue Détectée : {language_name}")
        
        # Colonnes pour les infos
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Code", language_code.upper())
        
        with col2:
            st.metric("Confiance", f"{confidence*100:.1f}%")
        
        with col3:
            if is_supported:
                st.success("✅ Supportée")
            else:
                st.warning("⚠️ Non supportée")