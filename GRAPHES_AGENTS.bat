@echo off
title Graphes LangGraph — OCR PFE GLM
cd /d "%~dp0"

REM Le venv est a la racine du projet
call "%~dp0venv\Scripts\activate.bat" 2>nul
if errorlevel 1 (
    echo [ERREUR] venv introuvable : %~dp0venv\Scripts\activate.bat
    pause
    exit /b 1
)

echo.
echo  Lancement de la visualisation des 4 graphes agents...
echo.

python visualize_graphs.py
