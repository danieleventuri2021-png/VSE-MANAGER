param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [ValidateSet("backend", "frontend", "both")]
  [string]$Only = "both"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "check_ports.py"
python $pythonScript --backend-port $BackendPort --frontend-port $FrontendPort --only $Only
exit $LASTEXITCODE
