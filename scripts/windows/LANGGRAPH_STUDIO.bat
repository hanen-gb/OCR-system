@echo off
set "ROOTDIR=%~dp0..\..\"
title LangGraph Studio Server — OCR PFE GLM
setlocal

REM ── Venv ────────────────────────────────────────────────────────────
echo.
echo [1/4] Activation du venv...
call "%ROOTDIR%venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERREUR] venv introuvable : %ROOTDIR%venv\
    pause & exit /b 1
)
echo       OK - Python: & python --version

REM ── langgraph-cli ───────────────────────────────────────────────────
echo.
echo [2/4] Verification langgraph-cli...
langgraph --version >nul 2>&1
if errorlevel 1 (
    echo       Installation de langgraph-cli...
    pip install -U "langgraph-cli[inmem]"
    if errorlevel 1 (
        echo [ERREUR] Echec installation langgraph-cli
        pause & exit /b 1
    )
) else (
    echo       OK - & langgraph --version
)

REM ── Se placer dans assistant/ (ou est langgraph.json) ───────────────
echo.
echo [3/4] Demarrage du serveur LangGraph Studio...
cd /d "%ROOTDIR%assistant"
echo       Repertoire: %CD%
echo       Config    : langgraph.json
echo.

REM ── Ouvrir le navigateur apres 5 secondes ───────────────────────────
echo [4/4] Ouverture du navigateur dans 5 secondes...
start /b cmd /c "timeout /t 5 >nul && start https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123"

echo.
echo =====================================================================
echo   Serveur en cours de demarrage sur http://127.0.0.1:8123
echo   Si erreur d'import s'affiche -> voir message ci-dessous
echo   Ctrl+C pour arreter le serveur
echo =====================================================================
echo.

langgraph dev --host 127.0.0.1 --port 8123

echo.
echo [INFO] Le serveur s'est arrete.
pause
