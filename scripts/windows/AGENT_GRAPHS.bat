@echo off
set "ROOTDIR=%~dp0..\..\"
title LangGraph graphs — OCR PFE GLM
cd /d "%ROOTDIR%"

REM The venv is at the project root
call "%ROOTDIR%venv\Scripts\activate.bat" 2>nul
if errorlevel 1 (
    echo [ERROR] venv not found: %ROOTDIR%venv\Scripts\activate.bat
    pause
    exit /b 1
)

echo.
echo  Rendering the 4 agent graphs...
echo.

python visualize_graphs.py
