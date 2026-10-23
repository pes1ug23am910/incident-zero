param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Incident,
    [Alias('svc')][string]$Service,
    [string]$ReportId,
    [string]$Operator = 'Yash Verma',
    [switch]$BrowserApproval
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Local environment is missing. Follow README setup before rehearsal.'
}
if ($env:INCIDENT_ZERO_TEST -eq '1') {
    throw 'Unset INCIDENT_ZERO_TEST for the mentor run. Checkpoint 3 always collects a real human decision.'
}
$arguments = @('-m', 'scripts.hands_rehearsal', $Incident, '--live', '--operator', $Operator, '--ensure-control-room')
if ($Service) { $arguments += @('--svc', $Service) }
if ($ReportId) { $arguments += @('--report-id', $ReportId) }
if ($BrowserApproval) { $arguments += @('--approval-mode', 'browser') }
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DEMO_VERSION = '2.0.2'
Write-Host 'Control Room: http://127.0.0.1:8787. The same pending approval is visible there and in the terminal.'
Write-Host 'Review the evidence, then approve once in either surface. Verification and both cleanup windows take at least 180 seconds each.'
Push-Location $repo
try {
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Checkpoint 3 failed. Inspect the saved bundle and cleanup measurements.' }
} finally {
    Pop-Location
}
