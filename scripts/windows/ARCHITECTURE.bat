@echo off
set "ROOTDIR=%~dp0..\..\"
title Architecture — OCR PFE GLM
cd /d "%ROOTDIR%"
start "" "%ROOTDIR%diagrams\architecture.svg"
