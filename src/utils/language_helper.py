"""
Utilitaire pour détecter la langue à partir du nom de fichier (temporaire)
US-02: Détection automatique - Version temporaire sans OCR
"""

from preprocessing.language_detector import LanguageDetector
from typing import Dict


def detect_language_from_filename(filename: str) -> Dict:
    """
    Détecte la langue à partir du nom du fichier
    Version temporaire en attendant l'OCR du Sprint 2
    
    Args:
        filename: Nom du fichier
        
    Returns:
        Dict: Informations de langue détectée
    """
    
    # Nettoyer le nom de fichier
    filename_lower = filename.lower()
    
    # Mots-clés par langue
    french_keywords = ['facture', 'devis', 'bon', 'commande', 'recu', 'fr', 'français', 'france']
    english_keywords = ['invoice', 'quote', 'receipt', 'order', 'en', 'english', 'eng']
    arabic_keywords = ['ar', 'arabic', 'عربي', 'فاتورة']
    
    # Détecter par mots-clés
    detected_lang = None
    
    for keyword in french_keywords:
        if keyword in filename_lower:
            detected_lang = 'fr'
            break
    
    if not detected_lang:
        for keyword in english_keywords:
            if keyword in filename_lower:
                detected_lang = 'en'
                break
    
    if not detected_lang:
        for keyword in arabic_keywords:
            if keyword in filename_lower:
                detected_lang = 'ar'
                break
    
    # Si détecté par nom de fichier
    if detected_lang:
        return {
            'language_code': detected_lang,
            'language_name': LanguageDetector.LANGUAGE_MAPPING.get(detected_lang, detected_lang.upper()),
            'confidence': 0.75,  # Confiance moyenne (basé sur nom de fichier)
            'is_supported': detected_lang in LanguageDetector.SUPPORTED_LANGUAGES,
            'all_probabilities': [],
            'detection_method': 'filename'
        }
    
    # Sinon, langue par défaut (français)
    return {
        'language_code': 'fr',
        'language_name': 'Français',
        'confidence': 0.50,
        'is_supported': True,
        'all_probabilities': [],
        'detection_method': 'default'
    }


def detect_language_smart(filename: str, text_sample: str = None) -> Dict:
    """
    Détection intelligente : utilise le texte si disponible, sinon le nom de fichier
    
    Args:
        filename: Nom du fichier
        text_sample: Échantillon de texte (optionnel)
        
    Returns:
        Dict: Informations de langue
    """
    
    # Si on a du texte, l'utiliser (meilleure précision)
    if text_sample and len(text_sample) > 10:
        result = LanguageDetector.detect_language(text_sample)
        result['detection_method'] = 'text_analysis'
        return result
    
    # Sinon, utiliser le nom de fichier
    return detect_language_from_filename(filename)