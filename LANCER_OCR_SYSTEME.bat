@echo off
setlocal EnableDelayedExpansion
title Lancement OCR Systeme — PFE GLM
cd /d "%~dp0"
color 0A
cls

echo.
echo  ================================================================
echo    OCR Multi-Agent Pipeline  —  Lancement complet du systeme
echo    PFE 2025  ^|  Goubaa Hanen  ^|  ENIG Gabes  ^|  ODSInet
echo  ================================================================
echo.
echo  Composants qui vont etre lances :
echo.
echo    [1]  PostgreSQL      Service Windows  postgresql-x64-16
echo    [2]  Backend         FastAPI          http://localhost:8002
echo    [3]  Frontend        React/Vite       http://localhost:5173
echo    [4]  Modal           GLM-OCR GPU T4   modal serve (cloud)
echo    [5]  LangSmith       Tracing          smith.langchain.com
echo    [6]  LangGraph       Studio           http://127.0.0.1:8123
echo.
echo  Couleurs des fenetres :
echo    Cyan    =  Backend FastAPI
echo    Magenta =  Frontend React
echo    Rouge   =  Modal GLM-OCR (cloud)
echo    Jaune   =  LangGraph Studio
echo.
echo  Appuyez sur ENTREE pour tout lancer...
pause >nul
echo.

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [1]  PostgreSQL                                             ║
REM ╚══════════════════════════════════════════════════════════════╝
echo  [1/6]  PostgreSQL...
sc query postgresql-x64-16 | findstr /i "RUNNING" >nul 2>&1
if %errorlevel% == 0 (
    echo         OK  -  Service deja actif
) else (
    net start postgresql-x64-16 >nul 2>&1
    if %errorlevel% == 0 (
        echo         OK  -  Service demarre
    ) else (
        echo         ATTENTION  -  Impossible de demarrer postgresql-x64-16
        echo         Ouvrez services.msc et demarrez-le manuellement.
    )
)
echo.

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [2]  Backend FastAPI  (fenetre cyan)                        ║
REM ╚══════════════════════════════════════════════════════════════╝
echo  [2/6]  Backend FastAPI...
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo         ERREUR  -  venv introuvable.
    echo         Creez-le :  python -m venv venv
    echo                     pip install -r assistant\requirements.txt
    pause & exit /b 1
)
start "Backend — FastAPI :8002" /d "%~dp0" cmd /k ^
    "color 0B & title Backend — FastAPI :8002 & echo. & echo  [BACKEND] Activation du venv... & call venv\Scripts\activate.bat & echo  [BACKEND] Demarrage FastAPI :8002... & echo. & cd assistant & uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload"
echo         OK  -  Fenetre ouverte  (cyan)
echo.

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [3]  Frontend React  (fenetre magenta)                      ║
REM ╚══════════════════════════════════════════════════════════════╝
echo  [3/6]  Frontend React/Vite...
if not exist "%~dp0frontend\package.json" (
    echo         ERREUR  -  frontend\package.json introuvable.
    pause & exit /b 1
)
if not exist "%~dp0frontend\node_modules" (
    echo         node_modules absent  -  npm install en cours (peut prendre 1-2 min)...
    start "Frontend — npm install + dev :5173" /d "%~dp0frontend" cmd /k ^
        "color 0D & title Frontend — React :5173 & echo. & echo  [FRONTEND] npm install... & npm install & echo. & echo  [FRONTEND] Demarrage Vite :5173... & npm run dev"
) else (
    start "Frontend — React :5173" /d "%~dp0frontend" cmd /k ^
        "color 0D & title Frontend — React :5173 & echo. & echo  [FRONTEND] Demarrage Vite :5173... & echo. & npm run dev"
)
echo         OK  -  Fenetre ouverte  (magenta)
echo.

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [4]  Modal  GLM-OCR  (fenetre rouge)                        ║
REM ╚══════════════════════════════════════════════════════════════╝
echo  [4/6]  Modal GLM-OCR (GPU T4)...
if not exist "%~dp0modal_app.py" (
    echo         ERREUR  -  modal_app.py introuvable a la racine.
) else (
    REM Verifier que modal est installe dans le venv
    call "%~dp0venv\Scripts\activate.bat" >nul 2>&1
    modal --version >nul 2>&1
    if errorlevel 1 (
        echo         Installation de modal dans le venv...
        pip install modal -q
    )
    start "Modal — GLM-OCR GPU T4" /d "%~dp0" cmd /k ^
        "color 0C & title Modal — GLM-OCR GPU T4 & echo. & echo  [MODAL] Activation du venv... & call venv\Scripts\activate.bat & echo. & echo  [MODAL] Demarrage modal serve (hot-reload cloud)... & echo  URL : https://<workspace>--glmocr-backend-fastapi-app.modal.run & echo. & modal serve modal_app.py"
    echo         OK  -  Fenetre ouverte  (rouge)
    echo         URL cloud : https://<workspace>--glmocr-backend-fastapi-app.modal.run
)
echo.

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  Attente demarrage serveurs                                  ║
REM ╚══════════════════════════════════════════════════════════════╝
echo  Attente du demarrage des serveurs...
echo.
<nul set /p =   Backend  :
timeout /t 3 /nobreak >nul
<nul set /p =[.....]
timeout /t 3 /nobreak >nul
<nul set /p =[.....]
timeout /t 3 /nobreak >nul
echo  OK
echo.

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [5]  LangSmith Tracing  (navigateur)                        ║
REM ╚══════════════════════════════════════════════════════════════╝
echo  [5/6]  LangSmith Tracing...
set "PROJECT=OCR-PFE-GLM"
for /f "tokens=1,* delims==" %%A in ('findstr /i "LANGCHAIN_PROJECT" assistant\.env 2^>nul') do (
    set "_RAW=%%B"
    for /f "tokens=1" %%C in ("!_RAW!") do set "PROJECT=%%C"
)
start "" "https://smith.langchain.com"
echo         OK  -  Navigateur ouvert
echo         Projet : !PROJECT!
echo.
timeout /t 2 /nobreak >nul

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [6]  LangGraph Studio  (fenetre jaune + navigateur)         ║
REM ╚══════════════════════════════════════════════════════════════╝
echo  [6/6]  LangGraph Studio...
start "LangGraph Studio :8123" /d "%~dp0" cmd /k ^
    "color 0E & title LangGraph Studio :8123 & echo. & echo  [STUDIO] Activation du venv... & call venv\Scripts\activate.bat & echo  [STUDIO] Verification langgraph-cli... & langgraph --version >nul 2>&1 || pip install -U langgraph-cli[inmem] -q & echo. & echo  [STUDIO] Demarrage LangGraph Studio :8123... & echo. & cd assistant & langgraph dev --host 127.0.0.1 --port 8123"
echo         OK  -  Fenetre ouverte  (jaune)
echo.
echo  Ouverture de LangGraph Studio dans 8 secondes...
timeout /t 8 /nobreak >nul
start "" "https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123"
echo         OK  -  Studio ouvert dans le navigateur
echo.

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  Resume final                                                ║
REM ╚══════════════════════════════════════════════════════════════╝
cls
color 0A
echo.
echo  ================================================================
echo    Systeme OCR lance avec succes !
echo  ================================================================
echo.
echo    [1] PostgreSQL    Service actif
echo    [2] Backend       http://localhost:8002
echo         API Docs     http://localhost:8002/docs
echo    [3] Frontend      http://localhost:5173
echo    [4] Modal         https://<workspace>--glmocr-backend-fastapi-app.modal.run
echo         Dashboard    https://modal.com/apps
echo    [5] LangSmith     https://smith.langchain.com
echo    [6] Studio        https://smith.langchain.com/studio/
echo                      (serveur local : http://127.0.0.1:8123)
echo.
echo  ----------------------------------------------------------------
echo.
echo  Ouvrir l'application dans le navigateur ? [O/N]
set /p "_OPEN=> "
if /i "!_OPEN!"=="O" start "" "http://localhost:5173"
echo.
echo  Pour arreter un composant : fermez sa fenetre Terminal.
echo  Pour arreter PostgreSQL   : net stop postgresql-x64-16
echo  Pour arreter Modal        : Ctrl+C dans la fenetre rouge
echo.
echo  Fermez cette fenetre quand vous avez termine.
echo.
pause
endlocal
