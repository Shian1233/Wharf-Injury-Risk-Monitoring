$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot 'runtime'
$toolsRoot = Join-Path $runtimeRoot 'tools'
$cloudflared = Join-Path $toolsRoot 'cloudflared.exe'
$pidPath = Join-Path $runtimeRoot 'public-share.pid'
$urlPath = Join-Path $runtimeRoot 'public-share.url'
$stdoutPath = Join-Path $runtimeRoot 'public-share.stdout.log'
$stderrPath = Join-Path $runtimeRoot 'public-share.stderr.log'
$origin = 'http://127.0.0.1:8001'

New-Item -ItemType Directory -Path $toolsRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath $cloudflared)) {
    Write-Output 'Downloading Cloudflare Tunnel...'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile $cloudflared
}
& $cloudflared --version
if ($LASTEXITCODE -ne 0) { throw 'cloudflared could not start.' }

try { Invoke-RestMethod -Uri "$origin/api/health" -TimeoutSec 3 | Out-Null }
catch {
    & (Join-Path $projectRoot 'preview.ps1') -Action start -NoBrowser
    if ($LASTEXITCODE -ne 0) { throw 'The application could not be started.' }
}

if (Test-Path -LiteralPath $pidPath) {
    $existingId = 0
    if ([int]::TryParse([IO.File]::ReadAllText($pidPath).Trim(), [ref]$existingId)) {
        $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$existingId" -ErrorAction SilentlyContinue
        if ($existing -and $existing.ExecutablePath -eq $cloudflared) {
            if (Test-Path -LiteralPath $urlPath) { Write-Output ([IO.File]::ReadAllText($urlPath).Trim()); exit 0 }
        }
    }
}

foreach ($path in @($stdoutPath,$stderrPath,$urlPath)) { if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force } }
$tunnel = Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--no-autoupdate','--protocol','http2','--url',$origin) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
[IO.File]::WriteAllText($pidPath,[string]$tunnel.Id)
for ($attempt=0; $attempt -lt 120; $attempt++) {
    $tunnel.Refresh()
    if ($tunnel.HasExited) { throw "Cloudflare Tunnel stopped. See $stderrPath" }
    $logs=''
    if (Test-Path -LiteralPath $stderrPath) { $logs += [IO.File]::ReadAllText($stderrPath) }
    if (Test-Path -LiteralPath $stdoutPath) { $logs += [IO.File]::ReadAllText($stdoutPath) }
    $match=[regex]::Match($logs,'https://[a-z0-9-]+\.trycloudflare\.com')
    if ($match.Success) {
        [IO.File]::WriteAllText($urlPath,$match.Value)
        Write-Output $match.Value
        exit 0
    }
    Start-Sleep -Milliseconds 250
}
throw "Timed out waiting for a public URL. See $stderrPath"
