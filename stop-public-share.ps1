$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pidPath = Join-Path $projectRoot 'runtime\public-share.pid'
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Output 'Public sharing is not running.'; exit 0 }
$processId = 0
if (-not [int]::TryParse([IO.File]::ReadAllText($pidPath).Trim(),[ref]$processId)) { throw 'Invalid public sharing process record.' }
$cloudflared = Join-Path $projectRoot 'runtime\tools\cloudflared.exe'
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
if ($process -and $process.ExecutablePath -eq $cloudflared) { Stop-Process -Id $processId }
Remove-Item -LiteralPath $pidPath -Force
Write-Output 'Public sharing stopped.'
