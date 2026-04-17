"""
Tests unitaires pour LanguageDetector
US-02: Détection automatique de la langue
"""

import pytest
import sys
from pathlib import Path

# Ajouter src au path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from preprocessing.language_detector import LanguageDetector


class TestLanguageDetector:
    """Tests pour le détecteur de langue"""
    
    def test_detect_french(self):
        """Test détection du français"""
        text = "Bonjour, ceci est une facture pour les services rendus."
        result = LanguageDetector.detect_language(text)
        
        assert result['language_code'] == 'fr'
        assert result['language_name'] == 'Français'
        assert result['is_supported'] == True
        assert result['confidence'] > 0.9
    
    def test_detect_english(self):
        """Test détection de l'anglais"""
        text = "Hello, this is an invoice for services rendered."
        result = LanguageDetector.detect_language(text)
        
        assert result['language_code'] == 'en'
        assert result['language_name'] == 'Anglais'
        assert result['is_supported'] == True
        assert result['confidence'] > 0.9
    
    def test_detect_arabic(self):
        """Test détection de l'arabe"""
        text = "مرحبا هذه فاتورة للخدمات المقدمة"
        result = LanguageDetector.detect_language(text)
        
        assert result['language_code'] == 'ar'
        assert result['language_name'] == 'Arabe'
        assert result['is_supported'] == True
    
    def test_empty_text(self):
        """Test avec texte vide"""
        result = LanguageDetector.detect_language("")
        
        assert result['language_code'] == 'unknown'
        assert result['confidence'] == 0.0
        assert 'error' in result
    
    def test_short_text(self):
        """Test avec texte trop court"""
        result = LanguageDetector.detect_language("Hi")
        
        assert result['language_code'] == 'unknown'
        assert result['confidence'] == 0.0
    
    def test_is_language_supported(self):
        """Test vérification langue supportée"""
        assert LanguageDetector.is_language_supported('fr') == True
        assert LanguageDetector.is_language_supported('en') == True
        assert LanguageDetector.is_language_supported('ar') == True
        assert LanguageDetector.is_language_supported('de') == False
    
    def test_get_confidence_level(self):
        """Test niveaux de confiance"""
        assert LanguageDetector.get_confidence_level(0.95) == "Très élevé"
        assert LanguageDetector.get_confidence_level(0.80) == "Élevé"
        assert LanguageDetector.get_confidence_level(0.60) == "Moyen"
        assert LanguageDetector.get_confidence_level(0.30) == "Faible"
    
    def test_detect_from_multiple_samples(self):
        """Test détection avec plusieurs échantillons"""
        samples = [
            "Facture numéro 12345",
            "Date: 15 janvier 2025",
            "Montant total: 1500 euros"
        ]
        result = LanguageDetector.detect_from_sample_text(samples)
        
        assert result['language_code'] == 'fr'
        assert result['is_supported'] == True
    
    def test_clean_text(self):
        """Test nettoyage du texte"""
        dirty_text = "  Bonjour!!!  Ceci   est  un  test...  "
        clean = LanguageDetector._clean_text(dirty_text)
        
        assert "  " not in clean  # Pas d'espaces doubles
        assert clean == clean.strip()  # Pas d'espaces début/fin


if __name__ == "__main__":
    pytest.main([__file__, "-v"])