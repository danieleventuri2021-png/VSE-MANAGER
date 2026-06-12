param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [string]$LanIp = "",
  [switch]$SkipInstall,
  [switch]$OnlineInstall
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

function Test-PythonBackendReady($Command, $Arguments) {
  try {
    & $Command @Arguments -c "import fastapi, uvicorn, alembic" *> $null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
}

function Get-PythonCommand {
  $VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
  if (Test-Path $VenvPython) {
    if (Test-PythonBackendReady $VenvPython @()) {
      return @($VenvPython)
    }
    Write-Host "Virtualenv backend presente ma incompleto: uso Python di sistema." -ForegroundColor Yellow
  }
  if (Test-Command "py") {
    try {
      & py -3.13 --version *> $null
      if ($LASTEXITCODE -eq 0 -and (Test-PythonBackendReady "py" @("-3.13"))) {
        return @("py", "-3.13")
      }
    } catch {}
  }
  if ((Test-Command "python") -and (Test-PythonBackendReady "python" @())) {
    return @("python")
  }
  throw "Python backend non pronto. Installa le dipendenze con: py -3.13 -m pip install -r apps\backend\requirements.txt"
}

function Invoke-Python {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
  )
  & $PythonCommand @PythonArgs @Arguments
}

function Get-PythonShellCommand($Arguments) {
  $AllArgs = @($PythonArgs) + @($Arguments)
  return "& `"$PythonCommand`" $($AllArgs -join ' ')"
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

$PythonSpec = @(Get-PythonCommand)
$PythonCommand = $PythonSpec[0]
$PythonArgs = @()
if ($PythonSpec.Count -gt 1) {
  $PythonArgs = @($PythonSpec[1..($PythonSpec.Count - 1)])
}
$FrontendUrl = "http://$LanIp`:$FrontendPort"
$BackendUrl = "http://$LanIp`:$BackendPort"
$LocalFrontendUrl = "http://127.0.0.1:$FrontendPort"
$LocalBackendHealth = "http://127.0.0.1:$BackendPort/health"
$CorsOrigins = "$FrontendUrl,http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort"

Write-Step "Server LAN VSE-MANAGER"
Write-Host "Questo avvio usa servizi locali. Non serve Internet se le dipendenze sono gia' installate." -ForegroundColor Gray
Write-Host "IP LAN rilevato: $LanIp"
Write-Host "Frontend LAN: $FrontendUrl"
Write-Host "Backend LAN:  $BackendUrl"
Write-Host ""

Write-Step "Controllo dipendenze frontend"
if (-not (Test-Command "npm")) {
  Write-Host "npm non trovato nel PATH. Installa Node.js o apri un terminale dove npm e' disponibile." -ForegroundColor Red
  exit 1
}
if (-not (Test-Path (Join-Path $Backend ".env"))) {
  Write-Host "File backend .env mancante: $Backend\.env" -ForegroundColor Red
  Write-Host "Senza .env il backend non conosce DATABASE_URL. Ripristina il file prima di avviare offline." -ForegroundColor Red
  exit 1
}
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
  if ($OnlineInstall -and -not $SkipInstall) {
    Write-Host "node_modules assente: eseguo npm install perche' e' stato richiesto -OnlineInstall." -ForegroundColor Yellow
    Push-Location $Frontend
    try {
      npm install
    } finally {
      Pop-Location
    }
  } else {
    Write-Host "node_modules assente in $Frontend." -ForegroundColor Red
    Write-Host "Per usare il programma senza Internet, avvia una volta con Internet:" -ForegroundColor Red
    Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\launch_lan.ps1 -OnlineInstall" -ForegroundColor Yellow
    Write-Host "Poi AVVIA_SERVER_LAN.bat funzionera' offline." -ForegroundColor Red
    exit 1
  }
} elseif (-not $SkipInstall) {
  Write-Host "Dipendenze frontend gia' presenti: salto npm install per restare compatibile con uso offline." -ForegroundColor Gray
}

Write-Step "Controllo virtualenv backend"
if (-not (Test-Path (Join-Path $Backend ".venv"))) {
  Write-Host "Virtualenv backend assente: $Backend\.venv" -ForegroundColor Yellow
  Write-Host "Uso Python di sistema se disponibile. Se mancano pacchetti, prepararli prima di usare offline." -ForegroundColor Yellow
}

Write-Step "Applico migration database"
Push-Location $Backend
try {
  Invoke-Python -m alembic upgrade head
} finally {
  Pop-Location
}

Ensure-PortFree $BackendPort "Backend"
Ensure-PortFree $FrontendPort "Frontend"

Write-Step "Avvio backend FastAPI in LAN"
Start-Process -FilePath "powershell.exe" `
  -WindowStyle Hidden `
  -WorkingDirectory $Backend `
  -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "`$env:BACKEND_HOST='0.0.0.0'; `$env:BACKEND_PORT='$BackendPort'; `$env:FRONTEND_ORIGIN='$FrontendUrl'; `$env:CORS_ORIGINS='$CorsOrigins'; $(Get-PythonShellCommand @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', $BackendPort)) *> `"$BackendLog`""

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
