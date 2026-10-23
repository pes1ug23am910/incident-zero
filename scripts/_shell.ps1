$ErrorActionPreference = 'Stop'
function Invoke-IncidentPython {
    param([string[]]$Arguments, [string]$Python = '')
    $repo = Split-Path -Parent $PSScriptRoot
    if (-not $Python) {
        $Python = Join-Path $repo '.venv/Scripts/python.exe'
        if (-not (Test-Path -LiteralPath $Python)) { $Python = Join-Path $repo '.venv/bin/python' }
        if (-not (Test-Path -LiteralPath $Python)) { throw 'Create .venv and install .[test] as documented in README.' }
    }
    Push-Location $repo
    try { & $Python @Arguments; $script:IncidentExit = $LASTEXITCODE }
    finally { Pop-Location }
}
