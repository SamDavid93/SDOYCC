@echo off
setlocal
title SDOYCC Veroeffentlichung vorbereiten
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "BACKEND_PYTHON=python"
if exist "%~dp0.venv\Scripts\python.exe" set "BACKEND_PYTHON=%~dp0.venv\Scripts\python.exe"
"%BACKEND_PYTHON%" backend/scripts/configure_public.py %*
set "CONFIG_EXIT=%ERRORLEVEL%"
popd
exit /b %CONFIG_EXIT%
