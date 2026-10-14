$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$sharedPython = Join-Path (Split-Path $projectRoot -Parent) 'risk-agent\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath) -and (Test-Path -LiteralPath $sharedPython)) { $pythonPath = $sharedPython }
if (-not (Test-Path -LiteralPath $pythonPath)) { $pythonPath = (Get-Command python -ErrorAction Stop).Source }
& $pythonPath (Join-Path $projectRoot 'scripts\set_password.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
