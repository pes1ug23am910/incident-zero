param([string]$DemoDir = 'D:\opentelemetry-demo')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    $env:INCIDENT_ZERO_DEMO_DIR = $DemoDir
    $env:DEMO_VERSION = '2.0.2'
    & "$PSScriptRoot\up.ps1" -DemoDir $DemoDir
    try {
        & '.venv\Scripts\python.exe' -m faultctl inject payment-failure
        if ($LASTEXITCODE -ne 0) { throw 'Payment injection failed.' }
        & '.venv\Scripts\python.exe' "$PSScriptRoot\check_health.py" --expect payment-error --timeout 60
        if ($LASTEXITCODE -ne 0) { throw 'Payment errors were not verified in health_table.' }
    } finally {
        & '.venv\Scripts\python.exe' -m faultctl reset
        if ($LASTEXITCODE -ne 0) { throw 'Reset did not pass every readiness check; review its output.' }
    }
    & '.venv\Scripts\python.exe' "$PSScriptRoot\check_health.py" --expect clean --timeout 150
    if ($LASTEXITCODE -ne 0) { throw 'Recovery was not verified in health_table.' }
    Write-Host 'PASS: startup, payment error, reset, and telemetry recovery verified.'
} finally {
    Pop-Location
}
