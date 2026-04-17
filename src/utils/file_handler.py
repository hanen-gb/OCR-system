"""
Utilitaire pour la gestion des fichiers
US-01: Upload et sauvegarde de documents
"""

import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from io import BytesIO


class FileHandler:
    """Gestionnaire de fichiers pour l'application"""
    
    @staticmethod
    def get_file_info(uploaded_file: BytesIO) -> Dict:
        """
        Extrait les informations d'un fichier uploadé
        
        Args:
            uploaded_file: Fichier uploadé via Streamlit
            
        Returns:
            Dict: Dictionnaire contenant les infos du fichier
        """
        file_extension = uploaded_file.name.split('.')[-1].lower()
        file_size_mb = uploaded_file.size / (1024 * 1024)
        
        # Déterminer le type de fichier
        file_type = 'unknown'
        if file_extension in ['jpg', 'jpeg', 'png']:
            file_type = 'image'
        elif file_extension == 'pdf':
            file_type = 'pdf'
        
        return {
            'name': uploaded_file.name,
            'extension': file_extension,
            'type': file_type,
            'size_bytes': uploaded_file.size,
            'size_mb': file_size_mb,
            'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    @staticmethod
    def save_uploaded_file(uploaded_file: BytesIO, save_directory: str) -> Optional[str]:
        """
        Sauvegarde un fichier uploadé dans le système de fichiers
        
        Args:
            uploaded_file: Fichier uploadé via Streamlit
            save_directory: Dossier de destination
            
        Returns:
            str: Chemin du fichier sauvegardé, ou None si erreur
        """
        try:
            # Créer le dossier s'il n'existe pas
            Path(save_directory).mkdir(parents=True, exist_ok=True)
            
            # Générer un nom unique avec timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            original_name = uploaded_file.name
            file_extension = original_name.split('.')[-1]
            base_name = original_name.rsplit('.', 1)[0]
            
            # Nouveau nom: nom_original_timestamp.extension
            new_filename = f"{base_name}_{timestamp}.{file_extension}"
            file_path = os.path.join(save_directory, new_filename)
            
            # Sauvegarder le fichier
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            return file_path
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde: {str(e)}")
            return None
    
    @staticmethod
    def is_valid_file(filename: str, allowed_extensions: list) -> bool:
        """
        Vérifie si un fichier a une extension valide
        
        Args:
            filename: Nom du fichier
            allowed_extensions: Liste des extensions autorisées
            
        Returns:
            bool: True si l'extension est valide
        """
        extension = filename.split('.')[-1].lower()
        return extension in allowed_extensions
    
    @staticmethod
    def get_file_size_mb(file_size_bytes: int) -> float:
        """
        Convertit une taille en bytes en MB
        
        Args:
            file_size_bytes: Taille en bytes
            
        Returns:
            float: Taille en MB
        """
        return file_size_bytes / (1024 * 1024)