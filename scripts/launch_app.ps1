param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [switch]$SkipInstall,
  [switch]$OnlineInstall
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

function Test-PythonBackendReady($Command, $Arguments) {
  try {
    & $Command @Arguments -c "import fastapi, uvicorn, alembic" *> $null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
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

$PythonSpec = @(Get-PythonCommand)
$PythonCommand = $PythonSpec[0]
$PythonArgs = @()
if ($PythonSpec.Count -gt 1) {
  $PythonArgs = @($PythonSpec[1..($PythonSpec.Count - 1)])
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

Write-Step "Avvio locale offline-ready"
Write-Host "Questo avvio usa solo servizi locali. Non serve Internet se le dipendenze sono gia' installate." -ForegroundColor Gray

if (-not (Test-Path (Join-Path $Backend ".env"))) {
  Write-Host "File backend .env mancante: $Backend\.env" -ForegroundColor Red
  Write-Host "Senza .env il backend non conosce DATABASE_URL. Ripristina il file prima di avviare offline." -ForegroundColor Red
  exit 1
}

if (-not (Test-Command "npm")) {
  Write-Host "npm non trovato nel PATH. Installa Node.js o apri un terminale dove npm e' disponibile." -ForegroundColor Red
  exit 1
}

Write-Step "Controllo dipendenze frontend"
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
    Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\launch_app.ps1 -OnlineInstall" -ForegroundColor Yellow
    Write-Host "Poi AVVIA_VSE_MANAGER.bat funzionera' offline." -ForegroundColor Red
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

Write-Step "Avvio backend FastAPI"
if (-not (Test-PortOpen $BackendPort)) {
  Start-Process -FilePath "powershell.exe" `
    -WindowStyle Hidden `
    -WorkingDirectory $Backend `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "$(Get-PythonShellCommand @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', $BackendPort)) *> `"$BackendLog`""
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
