"""
Tests unitaires pour FileHandler
US-01: Upload de documents
"""

import pytest
import os
from pathlib import Path
import sys

# Ajouter src au path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from utils.file_handler import FileHandler


class TestFileHandler:
    """Tests pour la classe FileHandler"""
    
    def test_is_valid_file_with_valid_extensions(self):
        """Test validation fichier avec extensions valides"""
        allowed_extensions = ['jpg', 'png', 'pdf']
        
        assert FileHandler.is_valid_file("document.jpg", allowed_extensions) == True
        assert FileHandler.is_valid_file("image.PNG", allowed_extensions) == True
        assert FileHandler.is_valid_file("file.pdf", allowed_extensions) == True
    
    def test_is_valid_file_with_invalid_extensions(self):
        """Test validation fichier avec extensions invalides"""
        allowed_extensions = ['jpg', 'png', 'pdf']
        
        assert FileHandler.is_valid_file("document.docx", allowed_extensions) == False
        assert FileHandler.is_valid_file("image.gif", allowed_extensions) == False
    
    def test_get_file_size_mb(self):
        """Test conversion taille fichier en MB"""
        # 1 MB = 1024 * 1024 bytes
        assert FileHandler.get_file_size_mb(1024 * 1024) == 1.0
        assert FileHandler.get_file_size_mb(2 * 1024 * 1024) == 2.0
        assert FileHandler.get_file_size_mb(512 * 1024) == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])