param(
    [switch]$Live,
    [string]$Operator = 'Yash Verma',
    [string]$RejectedReport,
    [string]$Incident = 'catalog-one-product',
    [string]$ReportId = ('demo-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root '.venv/Scripts/python.exe'
if (-not $Live) {
    Write-Host 'Preview only. After exclusive stack handoff: scripts/demo.ps1 -Live -RejectedReport reports/<paused-tier2>/report.json'
    Write-Host 'Preflight outside presentation: reset, wait >=180s for clean metrics, retain a paused tier-2 report.'
    Write-Host '0:00-0:45 inject and wait for alert; 0:45-1:30 report and tier-1 human approval.'
    Write-Host '1:30-4:30 verification (>=180s); 4:30-4:45 reject the prepared tier-2 proposal.'
    Write-Host '4:45-5:00 forbidden-operation 403 and STOP; cleanup and metric clearance follow.'
    Write-Host 'Actual alert/model latency can exceed this target. Never shorten verification to fit the clock.'
    exit 0
}
if (-not $RejectedReport) { throw 'Pass a real paused tier-2 report with -RejectedReport.' }
if ($env:INCIDENT_ZERO_TEST -eq '1') { throw 'Unset INCIDENT_ZERO_TEST before the demo.' }
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DEMO_VERSION = '2.0.2'
function Invoke-CheckedPython {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$CommandArgs)
    & $py @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw ('Command failed: ' + ($CommandArgs -join ' ')) }
}
Push-Location $root
$ownsStack = $false
try {
    if (Test-Path STOP) { throw 'STOP is latched; review and clear it explicitly before starting.' }
    $rejected = Get-Content -Raw -LiteralPath $RejectedReport | ConvertFrom-Json
    if ($rejected.impact.tier -ne 2) { throw 'The prepared rejection report must be tier 2.' }
    $ownsStack = $true
    Write-Host 'Preflight, outside the five-minute presentation.'
    Invoke-CheckedPython -m faultctl reset
    Invoke-CheckedPython -m detect.recovery --timeout 360
    Write-Host 'Presentation begins. Approve only if the evidence and tier are appropriate.'
    Invoke-CheckedPython -m scripts.hands_rehearsal $Incident --live --report-id $ReportId --operator $Operator --prepared-stack --defer-cleanup
    Write-Host 'Tier-2 rejection: no action executes.'
    Invoke-CheckedPython -m agent.respond --report $RejectedReport --operator $Operator --reject
    Write-Host 'BLOCK path, through an in-process HTTP client: require status 403, then STOP.'
    Invoke-CheckedPython -m scripts.show_block --operator $Operator
}
finally {
    try {
      if ($ownsStack) {
        Write-Host 'Operator cleanup, outside the timed presentation.'
        Invoke-CheckedPython -m faultctl reset
        Invoke-CheckedPython -m detect.recovery --timeout 360
        $demoChanges = git -C D:/opentelemetry-demo status --porcelain
        if ($LASTEXITCODE -ne 0 -or $demoChanges) { throw 'Demo checkout is not confirmed clean.' }
        if (Test-Path STOP) {
            Invoke-CheckedPython -m action_api clear-stop --operator $Operator
        }
      }
    }
    finally { Pop-Location }
}
