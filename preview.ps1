param(
    [ValidateSet('start','restart','stop')][string]$Action = 'start',
    [switch]$NoBrowser,
    [switch]$Check
)
$ErrorActionPreference = 'Stop'
$designRoot = $PSScriptRoot
$designRuntime = Join-Path $designRoot 'runtime'
$designPidPath = Join-Path $designRuntime 'service.pid'
$designUrl = 'http://127.0.0.1:8001'

function Get-DesignProcess {
    if (-not (Test-Path -LiteralPath $designPidPath)) { return $null }
    $designServiceId = 0
    if (-not [int]::TryParse([IO.File]::ReadAllText($designPidPath).Trim(), [ref]$designServiceId)) { throw 'Invalid preview process record.' }
    $designService = Get-CimInstance Win32_Process -Filter "ProcessId=$designServiceId"
    if ($designService -and ($designService.CommandLine -notlike '*uvicorn app.main:app*' -or $designService.CommandLine -notlike '*--port 8001*' -or -not $designService.CommandLine.Contains($designRoot))) {
        throw 'Process identity does not match this design preview. Nothing was stopped.'
    }
    return $designService
}

if ($Check) {
    if (-not (Test-Path -LiteralPath (Join-Path $designRoot 'frontend\design.css'))) { throw 'Design stylesheet not found.' }
    $designParseErrors = $null
    $designParseTokens = $null
    [System.Management.Automation.Language.Parser]::ParseFile($PSCommandPath, [ref]$designParseTokens, [ref]$designParseErrors) | Out-Null
    if ($designParseErrors.Count) { throw 'Preview launcher syntax error.' }
    Write-Output 'Design preview: port 8001, independent runtime, launcher syntax OK.'
    exit 0
}

if ($Action -in @('stop','restart')) {
    $designService = Get-DesignProcess
    if ($designService) {
        $designJobs = @()
        try { $designJobs = Invoke-RestMethod -Uri "$designUrl/api/jobs" -TimeoutSec 3 } catch { }
        if (@($designJobs | Where-Object { $_.status -in @('running','queued') }).Count) { throw 'A preview task is still running. Try again after it finishes.' }
        $designChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($designService.ProcessId)" | Where-Object { $_.CommandLine -like '*uvicorn app.main:app*' -and $_.CommandLine.Contains($designRoot) }
        foreach ($designChild in $designChildren) { Stop-Process -Id $designChild.ProcessId -ErrorAction SilentlyContinue }
        Stop-Process -Id $designService.ProcessId -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $designPidPath) { Remove-Item -LiteralPath $designPidPath }
    if ($Action -eq 'stop') { Write-Output 'Design preview stopped. Original service unchanged.'; exit 0 }
}

$designHealth = $null
try { $designHealth = Invoke-RestMethod -Uri "$designUrl/api/health" -TimeoutSec 2 } catch { }
if ($designHealth) {
    if (-not (Get-DesignProcess)) { throw 'Port 8001 is already occupied by another process.' }
    if (-not $NoBrowser) { Start-Process "$designUrl/agent" }
    Write-Output "$designUrl/agent"
    exit 0
}

$designPython = Join-Path $designRoot '.venv\Scripts\python.exe'
$designSharedPython = Join-Path (Split-Path $designRoot -Parent) 'risk-agent\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $designPython) -and (Test-Path -LiteralPath $designSharedPython)) { $designPython = $designSharedPython }
if (-not (Test-Path -LiteralPath $designPython)) {
    $designPythonCommand = Get-Command python -ErrorAction Stop
    & $designPythonCommand.Source -m venv (Join-Path $designRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment.' }
    & $designPython -m pip install -r (Join-Path $designRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not install Python dependencies.' }
}
Set-Location -LiteralPath $designRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:RISK_RUNTIME = $designRuntime
if (-not (Test-Path -LiteralPath (Join-Path $designRoot '.env'))) {
    $designEnv = [IO.File]::ReadAllText((Join-Path $designRoot '.env.example'))
    $designEnv = $designEnv.Replace('replace-with-at-least-32-random-characters', ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')))
    [IO.File]::WriteAllText((Join-Path $designRoot '.env'), $designEnv, [Text.UTF8Encoding]::new($false))
}
New-Item -ItemType Directory -Path $designRuntime -Force | Out-Null
$designStoreLauncher = Join-Path $designRoot 'scripts\local_stores.ps1'
$designEnvText = [IO.File]::ReadAllText((Join-Path $designRoot '.env'))
if ($designEnvText -match '(?m)^DB_BACKEND=postgres\s*$' -or $designEnvText -match '(?m)^STORAGE_BACKEND=s3\s*$') {
    & $designStoreLauncher -Action start
    if ($LASTEXITCODE -ne 0) { throw 'Could not start local database and object storage.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $designRuntime 'risk.db'))) {
    & $designPython (Join-Path $designRoot 'scripts\bootstrap.py')
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the preview database.' }
}
$designServer = Start-Process -FilePath $designPython -ArgumentList @('-m','uvicorn','app.main:app','--app-dir',('"' + $designRoot + '"'),'--host','127.0.0.1','--port','8001','--workers','1') -WorkingDirectory $designRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $designRuntime 'service.stdout.log') -RedirectStandardError (Join-Path $designRuntime 'service.stderr.log') -PassThru
[IO.File]::WriteAllText($designPidPath, [string]$designServer.Id)
$designReady = $false
for ($designAttempt = 0; $designAttempt -lt 40; $designAttempt++) {
    $designServer.Refresh()
    if ($designServer.HasExited) { throw 'Preview failed to start. See runtime/service.stderr.log.' }
    try {
        $designHealth = Invoke-RestMethod -Uri "$designUrl/api/health" -TimeoutSec 1
        if ($designHealth.status -eq 'ok') { $designReady = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 250
}
if (-not $designReady) { throw 'Preview startup timed out.' }
Write-Output "$designUrl/agent"
if (-not $NoBrowser) { Start-Process "$designUrl/agent" }
