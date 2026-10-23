param(
    [Parameter(Position = 0)][string]$Incident,
    [string]$Combo,
    [Alias('svc')][string]$Service,
    [string]$ReportId,
    [int]$AlertTimeout = 90,
    [int]$CleanTimeout = 360
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Local environment is missing. Follow the repository setup before rehearsal.'
}
$arguments = @('-m', 'scripts.checkpoint2')
if ($Incident) { $arguments += $Incident }
if ($Combo) { $arguments += @('--combo', $Combo) }
$arguments += @('--alert-timeout', $AlertTimeout, '--clean-timeout', $CleanTimeout)
if ($Service) { $arguments += @('--svc', $Service) }
if ($ReportId) { $arguments += @('--report-id', $ReportId) }
Push-Location $repo
try {
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Checkpoint 2 rehearsal failed. Review the stage output and cleanup status.' }
} finally {
    Pop-Location
}
