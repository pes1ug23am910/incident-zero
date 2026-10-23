param([string]$DemoDir = 'D:\opentelemetry-demo')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    $env:DEMO_VERSION = '2.0.2'
    $env:INCIDENT_ZERO_DEMO_DIR = $DemoDir
    $env:UV_CACHE_DIR = Join-Path $repo '.build\uv-cache'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $repo '.build\python'
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            & uv venv .venv --python 3.11
        } else {
            & py -3 -m venv .venv
        }
        if ($LASTEXITCODE -ne 0) { throw 'Could not create local Python environment.' }
    }
    $python = Join-Path $repo '.venv\Scripts\python.exe'
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        & uv pip install --python $python -e '.[test]'
    } else {
        & $python -m pip install -e '.[test]'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & $python -m faultctl up
    if ($LASTEXITCODE -ne 0) { throw 'Stack startup failed; see the readiness output.' }
    & $python -m faultctl build-netem
    if ($LASTEXITCODE -ne 0) { throw 'Could not build the network-fault helper.' }
    & $python -m faultctl status
    if ($LASTEXITCODE -ne 0) { throw 'Stack is not ready. Inspect collector logs before attempting diagnosis.' }
} finally {
    Pop-Location
}
