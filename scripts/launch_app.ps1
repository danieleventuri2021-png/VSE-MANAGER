param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "apps\backend"
$Frontend = Join-Path $Root "apps\frontend"
$Logs = Join-Path $Root "logs"
$BackendLog = Join-Path $Logs "backend-dev.log"
$FrontendLog = Join-Path $Logs "frontend-dev.log"
$Url = "http://127.0.0.1:$FrontendPort"

New-Item -ItemType Directory -Force $Logs | Out-Null

function Write-Step($Message) {
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-Command($Command) {
  return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

function Test-PortOpen($Port) {
  try {
    $Client = New-Object Net.Sockets.TcpClient
    $Async = $Client.BeginConnect("127.0.0.1", $Port, $null, $null)
    $Open = $Async.AsyncWaitHandle.WaitOne(350, $false)
    if ($Open) {
      $Client.EndConnect($Async)
      $Client.Close()
      return $true
    }
    $Client.Close()
    return $false
  } catch {
    return $false
  }
}

function Wait-Http($Address, $Seconds) {
  $Deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $Deadline) {
    try {
      $Response = Invoke-WebRequest -Uri $Address -UseBasicParsing -TimeoutSec 2
      if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 700
    }
  }
  return $false
}

function Get-PythonCommand {
  if (Test-Command "py") {
    try {
      & py -3.13 --version *> $null
      if ($LASTEXITCODE -eq 0) {
        return "py -3.13"
      }
    } catch {}
  }
  if (Test-Command "python") {
    return "python"
  }
  throw "Python non trovato. Installa Python 3.13 o rendi disponibile python nel PATH."
}

$Python = Get-PythonCommand

Write-Step "Controllo dipendenze frontend"
if (-not (Test-Path (Join-Path $Frontend "node_modules")) -and -not $SkipInstall) {
  Push-Location $Frontend
  try {
    npm install
  } finally {
    Pop-Location
  }
}

Write-Step "Applico migration database"
Push-Location $Backend
try {
  Invoke-Expression "$Python -m alembic upgrade head"
} finally {
  Pop-Location
}

Write-Step "Avvio backend FastAPI"
if (-not (Test-PortOpen $BackendPort)) {
  Start-Process -FilePath "powershell.exe" `
    -WindowStyle Hidden `
    -WorkingDirectory $Backend `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "$Python -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort *> `"$BackendLog`""
} else {
  Write-Host "Backend gia' in ascolto sulla porta $BackendPort" -ForegroundColor Yellow
}

Write-Step "Avvio frontend Vite"
if (-not (Test-PortOpen $FrontendPort)) {
  Start-Process -FilePath "powershell.exe" `
    -WindowStyle Hidden `
    -WorkingDirectory $Frontend `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "`$env:VITE_API_BASE_URL='http://127.0.0.1:$BackendPort'; npm run dev -- --host 127.0.0.1 --port $FrontendPort *> `"$FrontendLog`""
} else {
  Write-Host "Frontend gia' in ascolto sulla porta $FrontendPort" -ForegroundColor Yellow
}

Write-Step "Attendo backend"
if (-not (Wait-Http "http://127.0.0.1:$BackendPort/health" 35)) {
  Write-Host "Backend non raggiungibile. Log: $BackendLog" -ForegroundColor Red
  exit 1
}

Write-Step "Attendo frontend"
if (-not (Wait-Http $Url 45)) {
  Write-Host "Frontend non raggiungibile. Log: $FrontendLog" -ForegroundColor Red
  exit 1
}

Write-Step "Apro browser"
Start-Process $Url

Write-Host ""
Write-Host "VSE-MANAGER avviato." -ForegroundColor Green
Write-Host "Frontend: $Url"
Write-Host "Backend:  http://127.0.0.1:$BackendPort"
Write-Host "Log backend:  $BackendLog"
Write-Host "Log frontend: $FrontendLog"
