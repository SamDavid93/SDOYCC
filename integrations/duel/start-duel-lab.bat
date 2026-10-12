@echo off
setlocal
cd /d "%~dp0..\.."
if not exist ".venv\Scripts\python.exe" (
  echo Die Python-Umgebung des Projekts fehlt. Bitte zuerst das Backend einrichten.
  pause
  exit /b 1
)
if not exist "artifacts\duel-probe\verified-files.json" (
  echo Lade die festgeschriebenen Laufzeitdateien fuer das lokale DuelZone-Labor ...
  ".venv\Scripts\python.exe" "integrations\duel\provision.py"
  if errorlevel 1 (
    echo Vorbereitung fehlgeschlagen. Die Fehlermeldung steht oben.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" "integrations\duel\run_lab.py"
if errorlevel 1 (
  echo Laborstart fehlgeschlagen. Die Fehlermeldung steht oben.
  pause
  exit /b 1
)
