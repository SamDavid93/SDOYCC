@echo off
setlocal
title SDOYCC Backend
pushd "%~dp0"
if errorlevel 1 exit /b 1

set "BACKEND_PYTHON=python"
if exist "%~dp0.venv\Scripts\python.exe" set "BACKEND_PYTHON=%~dp0.venv\Scripts\python.exe"
set "PYTHONPATH=%~dp0backend"

if not exist ".env" (
    echo FEHLER: .env fehlt. Bitte zuerst .env.example als .env kopieren und konfigurieren.
    goto failed
)

"%BACKEND_PYTHON%" -c "from app.main import app" >nul
if errorlevel 1 (
    echo FEHLER: Python oder Backend-Abhaengigkeiten fehlen.
    echo Installation mit dem verwendeten Python:
    echo "%BACKEND_PYTHON%" -m pip install -r backend/requirements.txt
    goto failed
)

echo Sichere die lokale Datenbank und pruefe das Schema ...
"%BACKEND_PYTHON%" backend/scripts/migrate_database.py
if errorlevel 1 goto failed

echo.
echo Backend: http://127.0.0.1:8002
echo API-Dokumentation: http://127.0.0.1:8002/docs
echo Zum Beenden Strg+C druecken oder dieses Fenster schliessen.
echo.
"%BACKEND_PYTHON%" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002 --no-access-log
if errorlevel 1 goto failed
popd
exit /b 0

:failed
echo.
echo Backend konnte nicht gestartet werden. Siehe Fehlermeldung oben.
if /I not "%~1"=="--no-pause" pause
popd
exit /b 1
