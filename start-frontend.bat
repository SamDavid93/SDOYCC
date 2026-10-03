@echo off
setlocal
title SDOYCC Frontend
pushd "%~dp0"
if errorlevel 1 exit /b 1

if exist "%ProgramFiles%\nodejs\npm.cmd" set "PATH=%ProgramFiles%\nodejs;%PATH%"
where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo FEHLER: Node.js mit npm wurde nicht gefunden.
    goto failed
)

echo Hub: http://localhost:5173
echo Das Backend muss zusaetzlich ueber start-backend.bat laufen.
echo Zum Beenden Strg+C druecken oder dieses Fenster schliessen.
call npm.cmd --workspace frontend run dev -- --host localhost --port 5173 --strictPort
if errorlevel 1 goto failed
popd
exit /b 0

:failed
echo.
echo Frontend konnte nicht gestartet werden. Siehe Fehlermeldung oben.
if /I not "%~1"=="--no-pause" pause
popd
exit /b 1
