@echo off
set "ROOTDIR=%~dp0..\..\"
title LangSmith — OCR PFE GLM
cd /d "%ROOTDIR%"

REM Lire le nom du projet depuis assistant\.env
set "PROJECT=OCR-PFE-GLM"
for /f "tokens=1,* delims==" %%A in ('findstr /i "LANGCHAIN_PROJECT" assistant\.env 2^>nul') do (
    set "PROJECT=%%B"
)

echo.
echo  Ouverture de LangSmith...
echo  Projet : %PROJECT%
echo.

REM Ouvrir LangSmith dans le navigateur par defaut
start "" "https://smith.langchain.com"

echo  Page LangSmith ouverte dans le navigateur.
echo  Naviguez vers le projet : %PROJECT%
echo.
echo  Astuce : cliquez sur un Run pour voir le graphe
echo           et la trace complete de chaque agent.
echo.
timeout /t 4 >nul
