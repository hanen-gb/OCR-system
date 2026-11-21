@echo off
set "ROOTDIR=%~dp0..\..\"
title LangSmith — OCR PFE GLM
cd /d "%ROOTDIR%"

REM Read the project name from assistant\.env
set "PROJECT=OCR-PFE-GLM"
for /f "tokens=1,* delims==" %%A in ('findstr /i "LANGCHAIN_PROJECT" assistant\.env 2^>nul') do (
    set "PROJECT=%%B"
)

echo.
echo  Opening LangSmith...
echo  Project: %PROJECT%
echo.

REM Open LangSmith in the default browser
start "" "https://smith.langchain.com"

echo  LangSmith opened in the browser.
echo  Go to the project: %PROJECT%
echo.
echo  Tip: click a run to see the graph
echo       and the full trace of each agent.
echo.
timeout /t 4 >nul
