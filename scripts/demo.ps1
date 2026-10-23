param(
    [switch]$Live,
    [string]$Operator = 'Yash Verma',
    [string]$Incident = 'payment-failure',
    [Alias('svc')][string]$Service,
    [string]$RejectedReport,
    [switch]$BrowserApproval,
    [string]$ReportId = ('demo-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root '.venv/Scripts/python.exe'
if (-not $Live) {
    Write-Host 'Preview. Run scripts/demo.ps1 -Live for the real demonstration; add -BrowserApproval to approve in the Control Room.'
    Write-Host 'Before presentation: reset and measure >=180s of clean, traffic-qualified telemetry.'
    Write-Host '0:00-1:15 inject, alert, investigation, evidence and human approval in terminal or browser.'
    Write-Host '1:15-4:30 execute and verify >=180s; show the final report and action log.'
    Write-Host '4:30-5:00 BLOCK forbidden operation (403/reason code), STOP, and a stopped allowed action (423).'
    Write-Host 'Optional -RejectedReport shows rejection of an existing real tier-2 checkpoint without executing it.'
    Write-Host 'After presentation: reset, measure >=180s of clean traffic, and explicitly clear STOP.'
    Write-Host 'Five minutes is a target. Model/alert latency can exceed it; verification is never shortened.'
    exit 0
}
if ($env:INCIDENT_ZERO_TEST -eq '1') { throw 'Unset INCIDENT_ZERO_TEST before the demo; only real human approval is accepted.' }
if (-not (Test-Path -LiteralPath $py)) { throw 'Create the local Python environment using README setup.' }
if ($ReportId -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$') { throw 'ReportId must be a safe metadata slug.' }
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
    if ($RejectedReport) {
        $rejected = Get-Content -Raw -LiteralPath $RejectedReport | ConvertFrom-Json
        if ($rejected.impact.tier -ne 2) { throw 'The optional rejection report must be tier 2.' }
    }
    $ownsStack = $true
    Write-Host 'Control Room: http://127.0.0.1:8787. Initial reset and clearance are preflight; begin the five-minute clock at injection.'
    $arguments = @('-m', 'scripts.hands_rehearsal', $Incident, '--live', '--report-id', $ReportId, '--operator', $Operator, '--ensure-control-room', '--defer-cleanup')
    if ($Service) { $arguments += @('--svc', $Service) }
    if ($BrowserApproval) { $arguments += @('--approval-mode', 'browser') }
    Invoke-CheckedPython @arguments
    if ($RejectedReport) {
        Write-Host 'Reject the prepared tier-2 proposal: no action executes.'
        Invoke-CheckedPython -m agent.respond --report $RejectedReport --operator $Operator --reject
    }
    Write-Host 'BLOCK and STOP through the running real Action API.'
    Invoke-CheckedPython -m scripts.show_block --operator $Operator
    Write-Host 'Presentation ends. STOP stays latched until the operator reviews recovery and types the clear phrase.'
}
finally {
    try {
        if ($ownsStack) {
            Write-Host 'Operator cleanup, outside the five-minute presentation.'
            Invoke-CheckedPython -m faultctl reset --timeout 90
            $cleanup = Join-Path $root ('reports/' + $ReportId + '/demo-cleanup.json')
            Invoke-CheckedPython -c 'import json,sys; from pathlib import Path; from scripts.hands_rehearsal import require_clean,check_demo_unchanged; from tools.evidence import run_path; check_demo_unchanged(); result=require_clean(run_path(create=True),360); path=Path(sys.argv[1]); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")' $cleanup
            if (Test-Path STOP) { Invoke-CheckedPython -m action_api clear-stop --operator $Operator }
        }
    } finally { Pop-Location }
}
