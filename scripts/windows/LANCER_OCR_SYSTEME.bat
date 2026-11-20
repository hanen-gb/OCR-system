@echo off
set "ROOTDIR=%~dp0..\..\"
setlocal EnableDelayedExpansion
title Lancement OCR Systeme - PFE GLM
cd /d "%ROOTDIR%"
color 0A
cls

echo.
echo  ================================================================
echo    OCR Multi-Agent Pipeline  -  Lancement complet du systeme
echo    PFE 2026  ^|  Goubaa Hanen  ^|  ENIG Gabes  ^|  ODSInet
echo  ================================================================
echo.
echo  Composants :
echo    [1]  PostgreSQL      Service Windows  postgresql-x64-16
echo    [2]  Backend         FastAPI          http://localhost:8002
echo    [3]  Frontend        React/Vite       http://localhost:3000
echo    [4]  LangSmith       Tracing          smith.langchain.com
echo    [5]  LangGraph       Studio           http://127.0.0.1:8123
echo.
echo  Couleurs des fenetres terminales :
echo    Cyan    =  Backend FastAPI
echo    Magenta =  Frontend React
echo    Jaune   =  LangGraph Studio
echo.
echo  Appuyez sur ENTREE pour tout lancer...
pause >nul
cls

REM ── Variables chemins (pour eviter problemes guillemets avec espaces) ─────────
set "ROOT=%ROOTDIR%"
set "VENV=%ROOTDIR%venv\Scripts\activate.bat"
set "FRONTEND=%ROOTDIR%frontend"
set "ASSISTANT=%ROOTDIR%assistant"

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [1]  PostgreSQL                                             ║
REM ╚══════════════════════════════════════════════════════════════╝
echo.
echo  [1/5]  PostgreSQL...
sc query postgresql-x64-16 | findstr /i "RUNNING" >nul 2>&1
if %errorlevel% == 0 (
    echo         OK  -  Service deja actif
) else (
    net start postgresql-x64-16 >nul 2>&1
    if %errorlevel% == 0 (
        echo         OK  -  Service demarre
    ) else (
        echo         ATTENTION  -  Lancement manuel requis via services.msc
    )
)

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [2]  Backend FastAPI  (fenetre cyan)                        ║
REM ╚══════════════════════════════════════════════════════════════╝
echo.
echo  [2/5]  Backend FastAPI :8002...
call "%VENV%" >nul 2>&1
if errorlevel 1 (
    echo         ERREUR - venv introuvable : %VENV%
    pause & exit /b 1
)
start "Backend - FastAPI :8002" cmd /k "color 0B & title Backend - FastAPI :8002 & call "%VENV%" & cd /d "%ASSISTANT%" & echo. & echo  [BACKEND] FastAPI demarre sur http://localhost:8002 & echo. & uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload"
echo         OK  -  Fenetre cyan ouverte

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [3]  Frontend React  (fenetre magenta)                      ║
REM ╚══════════════════════════════════════════════════════════════╝
echo.
echo  [3/5]  Frontend React :3000...
start "Frontend - React :3000" cmd /k "color 0D & title Frontend - React :3000 & cd /d "%FRONTEND%" & echo. & echo  [FRONTEND] Demarrage Vite sur http://localhost:3000 & echo. & npm run dev"
echo         OK  -  Fenetre magenta ouverte

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [4]  LangGraph Studio  (fenetre jaune)                      ║
REM ╚══════════════════════════════════════════════════════════════╝
echo.
echo  [4/5]  LangGraph Studio :8123...
start "LangGraph Studio :8123" cmd /k "color 0E & title LangGraph Studio :8123 & call "%VENV%" & cd /d "%ASSISTANT%" & echo. & echo  [STUDIO] Demarrage LangGraph Studio sur http://127.0.0.1:8123 & echo. & langgraph dev --host 127.0.0.1 --port 8123"
echo         OK  -  Fenetre jaune ouverte

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  Attente demarrage serveurs avant ouverture navigateur       ║
REM ╚══════════════════════════════════════════════════════════════╝
echo.
echo  ----------------------------------------------------------------
echo  Attente demarrage serveurs...
echo  ----------------------------------------------------------------
<nul set /p =  3s...
timeout /t 3 /nobreak >nul
<nul set /p =  6s...
timeout /t 3 /nobreak >nul
<nul set /p =  9s...
timeout /t 3 /nobreak >nul
<nul set /p =  12s...
timeout /t 3 /nobreak >nul
echo   OK !
echo.

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [5]  Ouverture navigateur automatique                       ║
REM ╚══════════════════════════════════════════════════════════════╝
echo  [5/5]  Ouverture des onglets navigateur...
echo.

echo         Architecture SVG...
start "" "%ROOT%diagrams\architecture.svg"
timeout /t 1 /nobreak >nul

echo         Frontend React  http://localhost:3000
start "" "http://localhost:3000"
timeout /t 1 /nobreak >nul

echo         API Swagger     http://localhost:8002/docs
start "" "http://localhost:8002/docs"
timeout /t 1 /nobreak >nul

echo         LangSmith       https://smith.langchain.com
set "PROJECT=OCR-PFE-GLM"
for /f "tokens=1,* delims==" %%A in ('findstr /i "LANGCHAIN_PROJECT" assistant\.env 2^>nul') do (
    set "_RAW=%%B"
    for /f "tokens=1" %%C in ("!_RAW!") do set "PROJECT=%%C"
)
start "" "https://smith.langchain.com"
timeout /t 1 /nobreak >nul

echo         LangGraph Studio (attente 8s que le serveur :8123 soit pret)...
timeout /t 8 /nobreak >nul
start "" "https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123"

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  Resume final                                                ║
REM ╚══════════════════════════════════════════════════════════════╝
cls
color 0A
echo.
echo  ================================================================
echo    Systeme OCR  -  Tout est lance !
echo  ================================================================
echo.
echo    Fenetres Terminal :
echo    ----------------------------------------------------------
echo    Cyan    ^|  Backend FastAPI     http://localhost:8002
echo    Magenta ^|  Frontend React      http://localhost:3000
echo    Jaune   ^|  LangGraph Studio    http://127.0.0.1:8123
echo.
echo    Onglets navigateur :
echo    ----------------------------------------------------------
echo    1.  architecture.svg                   Diagramme systeme
echo    2.  http://localhost:3000              Application
echo    3.  http://localhost:8002/docs         API Swagger
echo    4.  https://smith.langchain.com        LangSmith [!PROJECT!]
echo    5.  LangGraph Studio                   :8123
echo.
echo  ================================================================
echo.
echo  Pour arreter un composant : fermez sa fenetre Terminal.
echo  Pour arreter PostgreSQL   : net stop postgresql-x64-16
echo.
pause
endlocal
