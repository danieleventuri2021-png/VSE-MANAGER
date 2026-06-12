@echo off
setlocal

cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_app.ps1"

if errorlevel 1 (
  echo.
  echo Avvio non completato. Controlla i messaggi sopra o i log in logs\.
  pause
)
