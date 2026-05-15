param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [string]$LanIp = "",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "apps\backend"
$Frontend = Join-Path $Root "apps\frontend"
$Logs = Join-Path $Root "logs"
$BackendLog = Join-Path $Logs "backend-lan.log"
$FrontendLog = Join-Path $Logs "frontend-lan.log"

New-Item -ItemType Directory -Force $Logs | Out-Null

function Write-Step($Message) {
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-Command($Command) {
  return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
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

function Get-LanIp {
  $Candidates = Get-NetIPConfiguration |
    Where-Object { $_.IPv4Address -and $_.IPv4DefaultGateway } |
    ForEach-Object { $_.IPv4Address.IPAddress } |
    Where-Object { $_ -and $_ -notlike "127.*" -and $_ -notlike "169.254.*" }

  if ($Candidates) {
    return @($Candidates)[0]
  }

  $Fallback = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -First 1 -ExpandProperty IPAddress

  if ($Fallback) {
    return $Fallback
  }

  throw "Impossibile rilevare l'indirizzo IP LAN. Rilancia con: powershell -File scripts\launch_lan.ps1 -LanIp 192.168.1.29"
}

function Get-ListeningProcessId($Port) {
  $Connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($Connection) {
    return $Connection.OwningProcess
  }
  return $null
}

function Ensure-PortFree($Port, $Name) {
  $PidOnPort = Get-ListeningProcessId $Port
  if (-not $PidOnPort) {
    return
  }

  $Process = Get-Process -Id $PidOnPort -ErrorAction SilentlyContinue
  $ProcessName = if ($Process) { $Process.ProcessName } else { "processo sconosciuto" }
  Write-Host "${Name}: porta $Port gia' occupata da PID $PidOnPort ($ProcessName)." -ForegroundColor Yellow
  $Answer = Read-Host "Vuoi chiudere questo processo e riavviarlo in modalita' LAN? [S/N]"
  if ($Answer -match "^[sS]") {
    Stop-Process -Id $PidOnPort -Force
    Start-Sleep -Seconds 1
    return
  }
  throw "Porta $Port occupata. Chiudi il processo o scegli un'altra porta."
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

if (-not $LanIp) {
  $LanIp = Get-LanIp
}

$Python = Get-PythonCommand
$FrontendUrl = "http://$LanIp`:$FrontendPort"
$BackendUrl = "http://$LanIp`:$BackendPort"
$LocalFrontendUrl = "http://127.0.0.1:$FrontendPort"
$LocalBackendHealth = "http://127.0.0.1:$BackendPort/health"
$CorsOrigins = "$FrontendUrl,http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort"

Write-Step "Server LAN VSE-MANAGER"
Write-Host "IP LAN rilevato: $LanIp"
Write-Host "Frontend LAN: $FrontendUrl"
Write-Host "Backend LAN:  $BackendUrl"
Write-Host ""

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

Ensure-PortFree $BackendPort "Backend"
Ensure-PortFree $FrontendPort "Frontend"

Write-Step "Avvio backend FastAPI in LAN"
Start-Process -FilePath "powershell.exe" `
  -WindowStyle Hidden `
  -WorkingDirectory $Backend `
  -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "`$env:BACKEND_HOST='0.0.0.0'; `$env:BACKEND_PORT='$BackendPort'; `$env:FRONTEND_ORIGIN='$FrontendUrl'; `$env:CORS_ORIGINS='$CorsOrigins'; $Python -m uvicorn app.main:app --host 0.0.0.0 --port $BackendPort *> `"$BackendLog`""

Write-Step "Avvio frontend Vite in LAN"
Start-Process -FilePath "powershell.exe" `
  -WindowStyle Hidden `
  -WorkingDirectory $Frontend `
  -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "`$env:VITE_API_BASE_URL='$BackendUrl'; `$env:VITE_FRONTEND_PORT='$FrontendPort'; npm run dev -- --host 0.0.0.0 --port $FrontendPort *> `"$FrontendLog`""

Write-Step "Attendo backend"
if (-not (Wait-Http $LocalBackendHealth 35)) {
  Write-Host "Backend non raggiungibile. Log: $BackendLog" -ForegroundColor Red
  exit 1
}

Write-Step "Attendo frontend"
if (-not (Wait-Http $LocalFrontendUrl 45)) {
  Write-Host "Frontend non raggiungibile. Log: $FrontendLog" -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "VSE-MANAGER avviato in modalita' LAN." -ForegroundColor Green
Write-Host "Da questo PC:       $LocalFrontendUrl"
Write-Host "Da altri dispositivi: $FrontendUrl"
Write-Host "Backend:           $BackendUrl"
Write-Host "Log backend:       $BackendLog"
Write-Host "Log frontend:      $FrontendLog"
Write-Host ""
Write-Host "Se da Safari/altro PC non si apre, esegui PowerShell come amministratore e autorizza il firewall:" -ForegroundColor Yellow
Write-Host "New-NetFirewallRule -DisplayName 'VSE Manager Frontend $FrontendPort' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $FrontendPort"
Write-Host "New-NetFirewallRule -DisplayName 'VSE Manager Backend $BackendPort' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $BackendPort"
Write-Host ""
Write-Host "Usa http, non https: $FrontendUrl"
