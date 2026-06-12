param(
  [string]$OutputDir = "C:\tmp",
  [string]$PackageName = "VSE-MANAGER-Windows11"
)

$ErrorActionPreference = "Stop"

$ScriptPath = $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptPath))
$Stamp = Get-Date -Format "yyyyMMdd-HHmm"
$Staging = Join-Path $OutputDir "$PackageName-$Stamp"
$ZipPath = "$Staging.zip"

function Write-Step($Message) {
  Write-Host "==> $Message" -ForegroundColor Cyan
}

Write-Step "Creo staging: $Staging"
if (Test-Path $Staging) {
  Remove-Item -LiteralPath $Staging -Recurse -Force
}
New-Item -ItemType Directory -Force $Staging | Out-Null

Write-Step "Copio sorgenti del pacchetto"
$ExcludedDataDirs = @(
  (Join-Path $Root "data\input"),
  (Join-Path $Root "data\output"),
  (Join-Path $Root "data\backup")
)
$RobocopyArgs = @(
  $Root,
  $Staging,
  "/E",
  "/XD", ".git", ".claude", ".codex", ".venv", "node_modules", "dist", "__pycache__", ".pytest_cache", "pytest-cache-files-*", "logs", "graphify-out", "TEST-PDF", "TEST_RESULT", "DATI-TEST"
) + $ExcludedDataDirs + @(
  "/XF", "*.pyc", "*.log", ".env", "*.tmp", "*.tsbuildinfo"
)
& robocopy @RobocopyArgs
if ($LASTEXITCODE -ge 8) {
  throw "Copia non riuscita. Codice robocopy: $LASTEXITCODE"
}

Write-Step "Creo archivio zip"
if (Test-Path $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "Pacchetto creato:" -ForegroundColor Green
Write-Host $ZipPath
Write-Host ""
Write-Host "Sul PC aziendale estrai lo zip in C:\Users\Daniele\Nextcloud\MEDITECH\VSE-MANAGER e avvia INSTALLA_PC_AZIENDALE.bat"
