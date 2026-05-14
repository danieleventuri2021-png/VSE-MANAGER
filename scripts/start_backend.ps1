param(
  [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backend = Join-Path $root "apps\backend"
$check = Join-Path $root "scripts\check_ports.py"

python $check --backend-port $BackendPort --frontend-port 5173 --only backend
if ($LASTEXITCODE -ne 0) {
  Write-Host "Avvio backend interrotto: liberare la porta $BackendPort o scegliere -BackendPort alternativa." -ForegroundColor Red
  exit 1
}

Set-Location $backend
$env:BACKEND_PORT = "$BackendPort"
python -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort --reload
