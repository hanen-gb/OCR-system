@echo off
set "ROOTDIR=%~dp0..\..\"
setlocal EnableDelayedExpansion
title OCR system start-up - PFE GLM
cd /d "%ROOTDIR%"
color 0A
cls

echo.
echo  ================================================================
echo    OCR Multi-Agent Pipeline  -  Full system start-up
echo    PFE 2026  ^|  Goubaa Hanen  ^|  ENIG Gabes  ^|  ODSInet
echo  ================================================================
echo.
echo  Components:
echo    [1]  PostgreSQL      Windows service  postgresql-x64-16
echo    [2]  Backend         FastAPI          http://localhost:8002
echo    [3]  Frontend        React/Vite       http://localhost:3000
echo    [4]  LangSmith       Tracing          smith.langchain.com
echo    [5]  LangGraph       Studio           http://127.0.0.1:8123
echo.
echo  Terminal window colours:
echo    Cyan    =  Backend FastAPI
echo    Magenta =  Frontend React
echo    Yellow  =  LangGraph Studio
echo.
echo  Press ENTER to start everything...
pause >nul
cls

REM ── Path variables (avoids quoting problems with spaces) ──────────────────────
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
    echo         OK  -  Service already running
) else (
    net start postgresql-x64-16 >nul 2>&1
    if %errorlevel% == 0 (
        echo         OK  -  Service started
    ) else (
        echo         WARNING  -  Start it manually from services.msc
    )
)

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [2]  Backend FastAPI  (cyan window)                         ║
REM ╚══════════════════════════════════════════════════════════════╝
echo.
echo  [2/5]  Backend FastAPI :8002...
call "%VENV%" >nul 2>&1
if errorlevel 1 (
    echo         ERROR - venv not found: %VENV%
    pause & exit /b 1
)
start "Backend - FastAPI :8002" cmd /k "color 0B & title Backend - FastAPI :8002 & call "%VENV%" & cd /d "%ASSISTANT%" & echo. & echo  [BACKEND] FastAPI started on http://localhost:8002 & echo. & uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload"
echo         OK  -  Cyan window opened

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [3]  Frontend React  (magenta window)                       ║
REM ╚══════════════════════════════════════════════════════════════╝
echo.
echo  [3/5]  Frontend React :3000...
start "Frontend - React :3000" cmd /k "color 0D & title Frontend - React :3000 & cd /d "%FRONTEND%" & echo. & echo  [FRONTEND] Starting Vite on http://localhost:3000 & echo. & npm run dev"
echo         OK  -  Magenta window opened

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  [4]  LangGraph Studio  (yellow window)                      ║
REM ╚══════════════════════════════════════════════════════════════╝
echo.
echo  [4/5]  LangGraph Studio :8123...
start "LangGraph Studio :8123" cmd /k "color 0E & title LangGraph Studio :8123 & call "%VENV%" & cd /d "%ASSISTANT%" & echo. & echo  [STUDIO] Starting LangGraph Studio on http://127.0.0.1:8123 & echo. & langgraph dev --host 127.0.0.1 --port 8123"
echo         OK  -  Yellow window opened

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  Wait for the servers before opening the browser             ║
REM ╚══════════════════════════════════════════════════════════════╝
echo.
echo  ----------------------------------------------------------------
echo  Waiting for the servers...
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
REM ║  [5]  Open the browser automatically                         ║
REM ╚══════════════════════════════════════════════════════════════╝
echo  [5/5]  Opening the browser tabs...
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

echo         LangGraph Studio (waiting 8 s for the :8123 server)...
timeout /t 8 /nobreak >nul
start "" "https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123"

REM ╔══════════════════════════════════════════════════════════════╗
REM ║  Final summary                                               ║
REM ╚══════════════════════════════════════════════════════════════╝
cls
color 0A
echo.
echo  ================================================================
echo    OCR system  -  Everything is running!
echo  ================================================================
echo.
echo    Terminal windows:
echo    ----------------------------------------------------------
echo    Cyan    ^|  Backend FastAPI     http://localhost:8002
echo    Magenta ^|  Frontend React      http://localhost:3000
echo    Yellow  ^|  LangGraph Studio    http://127.0.0.1:8123
echo.
echo    Browser tabs:
echo    ----------------------------------------------------------
echo    1.  architecture.svg                   System diagram
echo    2.  http://localhost:3000              Application
echo    3.  http://localhost:8002/docs         API Swagger
echo    4.  https://smith.langchain.com        LangSmith [!PROJECT!]
echo    5.  LangGraph Studio                   :8123
echo.
echo  ================================================================
echo.
echo  To stop a component: close its terminal window.
echo  To stop PostgreSQL       : net stop postgresql-x64-16
echo.
pause
endlocal
