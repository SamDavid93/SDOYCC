@echo off
setlocal
title SDOYCC Oeffentlichen Test beenden
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-public-test.ps1"
set "PUBLIC_EXIT=%ERRORLEVEL%"
if /I not "%~1"=="--no-pause" pause
exit /b %PUBLIC_EXIT%
