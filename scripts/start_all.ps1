param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$check = Join-Path $root "scripts\check_ports.py"

python $check --backend-port $BackendPort --frontend-port $FrontendPort
if ($LASTEXITCODE -ne 0) {
  Write-Host "Avvio completo interrotto: una o più porte sono occupate." -ForegroundColor Red
  exit 1
}

$backendScript = Join-Path $root "scripts\start_backend.ps1"
$frontendScript = Join-Path $root "scripts\start_frontend.ps1"

Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$backendScript`"", "-BackendPort", "$BackendPort"
Start-Sleep -Seconds 2
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$frontendScript`"", "-FrontendPort", "$FrontendPort", "-BackendPort", "$BackendPort"

Write-Host "Backend:  http://localhost:$BackendPort"
Write-Host "Frontend: http://localhost:$FrontendPort"
