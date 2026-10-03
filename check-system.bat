@echo off
setlocal
title SDOYCC Systempruefung
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "BACKEND_PYTHON=python"
if exist "%~dp0.venv\Scripts\python.exe" set "BACKEND_PYTHON=%~dp0.venv\Scripts\python.exe"
set "PYTHONPATH=%~dp0backend"
"%BACKEND_PYTHON%" backend/scripts/release_check.py %*
set "CHECK_EXIT=%ERRORLEVEL%"
echo.
echo Diese Pruefung veraendert keine Konten oder Bestaende.
popd
exit /b %CHECK_EXIT%
