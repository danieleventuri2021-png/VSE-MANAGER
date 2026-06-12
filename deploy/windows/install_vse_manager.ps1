param(
  [string]$InstallPath = "C:\Users\Daniele\Nextcloud\MEDITECH\VSE-MANAGER",
  [string]$PostgresPassword = "Daniele",
  [string]$PostgresUser = "postgres",
  [string]$PostgresHost = "localhost",
  [int]$PostgresPort = 5432,
  [string]$DatabaseName = "postgres",
  [string]$DbSchema = "gestione_vse",
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [switch]$InstallPrerequisites,
  [switch]$ForceEnv
)

$ErrorActionPreference = "Stop"

$ScriptPath = $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptPath))
$InstallPath = $InstallPath.Trim().Trim('"')
$InstallPath = [System.IO.Path]::GetFullPath($InstallPath)
$Backend = Join-Path $InstallPath "apps\backend"
$Frontend = Join-Path $InstallPath "apps\frontend"
$DataRoot = Join-Path $InstallPath "data"
$Logs = Join-Path $InstallPath "logs"
$EnvFile = Join-Path $Backend ".env"

function Write-Step($Message) {
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok($Message) {
  Write-Host "OK  $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
  Write-Host "ATTENZIONE  $Message" -ForegroundColor Yellow
}

function Test-Command($Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-Logged($FilePath, [string[]]$Arguments, $WorkingDirectory = $null) {
  $argText = $Arguments -join " "
  Write-Host "> $FilePath $argText" -ForegroundColor DarkGray
  if ($WorkingDirectory) {
    Push-Location $WorkingDirectory
  }
  try {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Comando fallito con codice ${LASTEXITCODE}: $FilePath $argText"
    }
  } finally {
    if ($WorkingDirectory) {
      Pop-Location
    }
  }
}

function Install-WingetPackage($Name, [string[]]$Ids) {
  if (-not $InstallPrerequisites) {
    throw "$Name non trovato. Rilancia INSTALLA_PC_AZIENDALE.bat o lo script con -InstallPrerequisites, oppure installalo manualmente."
  }
  if (-not (Test-Command "winget")) {
    throw "winget non trovato. Aggiorna 'Installazione app' dal Microsoft Store o installa $Name manualmente."
  }

  foreach ($Id in $Ids) {
    Write-Warn "Provo a installare $Name con winget id $Id"
    & winget install --exact --id $Id --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -eq 0) {
      Write-Ok "$Name installato"
      return
    }
  }

  throw "Installazione automatica di $Name non riuscita. Installa manualmente e rilancia questo script."
}

function Get-PythonCommand {
  if (Test-Command "py") {
    foreach ($Version in @("-3.13", "-3.12")) {
      & py $Version --version *> $null
      if ($LASTEXITCODE -eq 0) {
        return @("py", $Version)
      }
    }
  }

  if (Test-Command "python") {
    $VersionText = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($LASTEXITCODE -eq 0) {
      $Parts = $VersionText.Split(".")
      if ([int]$Parts[0] -eq 3 -and [int]$Parts[1] -ge 12) {
        return @("python")
      }
    }
  }

  return $null
}

function Ensure-Python {
  Write-Step "Controllo Python"
  $Python = Get-PythonCommand
  if ($Python) {
    Write-Ok "Python trovato: $($Python -join ' ')"
    return $Python
  }

  Install-WingetPackage "Python 3.13" @("Python.Python.3.13", "Python.Python.3.12")
  $Python = Get-PythonCommand
  if (-not $Python) {
    throw "Python installato ma non disponibile nel PATH. Chiudi e riapri PowerShell, poi rilancia l'installer."
  }
  return $Python
}

function Ensure-Node {
  Write-Step "Controllo Node.js e npm"
  if (-not (Test-Command "npm")) {
    Install-WingetPackage "Node.js LTS" @("OpenJS.NodeJS.LTS", "OpenJS.NodeJS")
  }
  if (-not (Test-Command "npm")) {
    throw "npm non disponibile nel PATH. Chiudi e riapri PowerShell, poi rilancia l'installer."
  }
  Write-Ok "npm trovato"
}

function Ensure-Postgres {
  Write-Step "Controllo PostgreSQL"
  $Service = Get-Service -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "postgresql*" -or $_.DisplayName -like "postgresql*" } |
    Select-Object -First 1

  if (-not $Service) {
    Install-WingetPackage "PostgreSQL" @("PostgreSQL.PostgreSQL", "EnterpriseDB.PostgreSQL")
    $Service = Get-Service -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -like "postgresql*" -or $_.DisplayName -like "postgresql*" } |
      Select-Object -First 1
  }

  if (-not $Service) {
    throw "PostgreSQL non risulta installato come servizio Windows. Installa PostgreSQL 15+ e rilancia."
  }

  if ($Service.Status -ne "Running") {
    Write-Warn "Avvio servizio PostgreSQL: $($Service.Name)"
    Start-Service -Name $Service.Name
    Start-Sleep -Seconds 3
  }

  Write-Ok "PostgreSQL presente: $($Service.DisplayName)"
}

function Copy-PackageToInstallPath {
  Write-Step "Preparo cartella installazione"
  New-Item -ItemType Directory -Force $InstallPath | Out-Null

  $Source = [System.IO.Path]::GetFullPath($PackageRoot)
  if ($Source.TrimEnd("\") -ieq $InstallPath.TrimEnd("\")) {
    Write-Ok "Il pacchetto e' gia' nella cartella di installazione"
    return
  }

  Write-Host "Copio da: $Source"
  Write-Host "Copio in: $InstallPath"
  $ExcludedDataDirs = @(
    (Join-Path $Source "data\input"),
    (Join-Path $Source "data\output"),
    (Join-Path $Source "data\backup")
  )
  $RobocopyArgs = @(
    $Source,
    $InstallPath,
    "/E",
    "/XD", ".git", ".claude", ".codex", ".venv", "node_modules", "dist", "__pycache__", ".pytest_cache", "pytest-cache-files-*", "logs", "graphify-out", "TEST-PDF", "TEST_RESULT", "DATI-TEST"
  ) + $ExcludedDataDirs + @(
    "/XF", "*.pyc", "*.log", ".env", "*.tmp", "*.tsbuildinfo"
  )
  & robocopy @RobocopyArgs
  if ($LASTEXITCODE -ge 8) {
    throw "Copia file non riuscita. Codice robocopy: $LASTEXITCODE"
  }
  Write-Ok "File progetto copiati"
}

function Ensure-ProjectFolders {
  Write-Step "Controllo cartelle dati"
  foreach ($Path in @(
    $DataRoot,
    (Join-Path $DataRoot "input"),
    (Join-Path $DataRoot "output"),
    (Join-Path $DataRoot "backup"),
    (Join-Path $DataRoot "templates"),
    $Logs
  )) {
    New-Item -ItemType Directory -Force $Path | Out-Null
  }
  Write-Ok "Cartelle dati pronte"
}

function Write-BackendEnv {
  Write-Step "Configuro backend .env"
  if ((Test-Path $EnvFile) -and -not $ForceEnv) {
    Write-Ok ".env gia' presente, non lo sovrascrivo"
    return
  }

  $DatabaseUrl = "postgresql://${PostgresUser}:$PostgresPassword@$PostgresHost`:$PostgresPort/$DatabaseName"
  $EnvContent = @"
DATABASE_URL=$DatabaseUrl
DB_SCHEMA=$DbSchema
BACKEND_HOST=127.0.0.1
BACKEND_PORT=$BackendPort
FRONTEND_ORIGIN=http://localhost:$FrontendPort
CORS_ORIGINS=http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort
DATA_ROOT=../../data
INPUT_DIR=../../data/input
OUTPUT_DIR=../../data/output
BACKUP_DIR=../../data/backup
TEMPLATE_DIR=../../data/templates
APP_ENV=development
LOG_LEVEL=INFO
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600
DB_POOL_TIMEOUT=30
AUTH_SECRET_KEY=cambia-questa-chiave-vse-manager
AUTH_TOKEN_EXPIRE_MINUTES=720
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
"@
  Set-Content -Path $EnvFile -Value $EnvContent -Encoding UTF8
  Write-Ok ".env scritto"
}

function Ensure-Backend {
  param([string[]]$Python)

  Write-Step "Installo dipendenze backend"
  $VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
  if (-not (Test-Path $VenvPython)) {
    $PythonArgs = @()
    if ($Python.Length -gt 1) {
      $PythonArgs = $Python[1..($Python.Length - 1)]
    }
    Invoke-Logged $Python[0] ($PythonArgs + @("-m", "venv", ".venv")) $Backend
  }

  Invoke-Logged $VenvPython @("-m", "pip", "install", "--upgrade", "pip") $Backend
  Invoke-Logged $VenvPython @("-m", "pip", "install", "-r", "requirements.txt") $Backend
  Write-Ok "Backend pronto"
}

function Ensure-Frontend {
  Write-Step "Installo dipendenze frontend"
  Invoke-Logged "npm" @("install") $Frontend
  Write-Ok "Frontend pronto"
}

function Apply-Migrations {
  Write-Step "Applico migration database"
  $VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
  Invoke-Logged $VenvPython @("-m", "alembic", "upgrade", "head") $Backend
  Write-Ok "Database pronto sullo schema $DbSchema"
}

function Verify-Install {
  Write-Step "Verifica finale"
  $VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
  Invoke-Logged $VenvPython @("-c", "from app.main import app; print('backend import ok')") $Backend
  Invoke-Logged "npm" @("run", "build") $Frontend
  Write-Ok "Build frontend completata"
}

Write-Host "Installazione VSE-MANAGER per Windows 11" -ForegroundColor White
Write-Host "Destinazione: $InstallPath"
Write-Host "Database: postgresql://${PostgresUser}:***@$PostgresHost`:$PostgresPort/$DatabaseName schema $DbSchema"

Copy-PackageToInstallPath
Ensure-ProjectFolders
$Python = Ensure-Python
Ensure-Node
Ensure-Postgres
Write-BackendEnv
Ensure-Backend -Python $Python
Ensure-Frontend
Apply-Migrations
Verify-Install

Write-Host ""
Write-Host "Installazione completata." -ForegroundColor Green
Write-Host "Avvio locale: $InstallPath\AVVIA_PC_AZIENDALE.bat"
Write-Host "URL: http://127.0.0.1:$FrontendPort"
Write-Host "Credenziali iniziali: admin / admin"
