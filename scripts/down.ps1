param([string]$DemoDir = 'D:\opentelemetry-demo')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    $env:INCIDENT_ZERO_DEMO_DIR = $DemoDir
    $env:DEMO_VERSION = '2.0.2'
    & '.venv\Scripts\python.exe' -m faultctl down
    if ($LASTEXITCODE -ne 0) { throw 'Teardown failed; inspect the reported cleanup errors.' }
} finally {
    Pop-Location
}
