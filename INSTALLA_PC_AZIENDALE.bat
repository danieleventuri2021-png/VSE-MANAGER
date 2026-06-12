@echo off
setlocal

cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\windows\install_vse_manager.ps1" -InstallPath "%CD%" -InstallPrerequisites

if errorlevel 1 (
  echo.
  echo Installazione non completata. Controlla i messaggi sopra.
  pause
  exit /b 1
)

echo.
echo Installazione completata.
pause
