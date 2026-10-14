param(
    [ValidateSet('start', 'restart', 'stop')][string]$Action = 'start',
    [switch]$Check
)
$ErrorActionPreference = 'Stop'
$riskEntryNames = @{ start = '启动智能体.ps1'; restart = '重启智能体.ps1'; stop = '停止智能体.ps1' }
if ($Check) {
    foreach ($riskEntryName in $riskEntryNames.Values) {
        $riskEntryPath = Join-Path $PSScriptRoot $riskEntryName
        if (-not (Test-Path -LiteralPath $riskEntryPath)) { throw "Entry not found: $riskEntryName" }
        $riskSyntaxErrors = $null
        $riskSyntaxTokens = $null
        [System.Management.Automation.Language.Parser]::ParseFile($riskEntryPath, [ref]$riskSyntaxTokens, [ref]$riskSyntaxErrors) | Out-Null
        if ($riskSyntaxErrors.Count) { throw "Entry syntax invalid: $riskEntryName" }
    }
    Write-Output 'Launcher paths and PowerShell syntax OK; service unchanged.'
    exit 0
}
& (Join-Path $PSScriptRoot $riskEntryNames[$Action])
