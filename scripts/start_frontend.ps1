param(
  [int]$FrontendPort = 5173,
  [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$frontend = Join-Path $root "apps\frontend"
$check = Join-Path $root "scripts\check_ports.py"

python $check --backend-port $BackendPort --frontend-port $FrontendPort --only frontend
if ($LASTEXITCODE -ne 0) {
  Write-Host "Avvio frontend interrotto: liberare la porta $FrontendPort o scegliere -FrontendPort alternativa." -ForegroundColor Red
  exit 1
}

Set-Location $frontend
$env:VITE_API_BASE_URL = "http://localhost:$BackendPort"
$env:VITE_FRONTEND_PORT = "$FrontendPort"
npm run dev -- --host 127.0.0.1 --port $FrontendPort
