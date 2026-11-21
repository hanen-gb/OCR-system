@echo off
set "ROOTDIR=%~dp0..\..\"
title LangGraph Studio Server — OCR PFE GLM
setlocal

REM ── Venv ────────────────────────────────────────────────────────────
echo.
echo [1/4] Activating the venv...
call "%ROOTDIR%venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] venv not found: %ROOTDIR%venv\
    pause & exit /b 1
)
echo       OK - Python: & python --version

REM ── langgraph-cli ───────────────────────────────────────────────────
echo.
echo [2/4] Checking langgraph-cli...
langgraph --version >nul 2>&1
if errorlevel 1 (
    echo       Installing langgraph-cli...
    pip install -U "langgraph-cli[inmem]"
    if errorlevel 1 (
        echo [ERROR] langgraph-cli installation failed
        pause & exit /b 1
    )
) else (
    echo       OK - & langgraph --version
)

REM ── Move to assistant/ (where langgraph.json is) ───────────────────
echo.
echo [3/4] Starting the LangGraph Studio server...
cd /d "%ROOTDIR%assistant"
echo       Folder: %CD%
echo       Config    : langgraph.json
echo.

REM ── Open the browser after 5 seconds ────────────────────────────────
echo [4/4] Opening the browser in 5 seconds...
start /b cmd /c "timeout /t 5 >nul && start https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123"

echo.
echo =====================================================================
echo   Server starting on http://127.0.0.1:8123
echo   If an import error appears -> see the message below
echo   Ctrl+C to stop the server
echo =====================================================================
echo.

langgraph dev --host 127.0.0.1 --port 8123

echo.
echo [INFO] The server has stopped.
pause
