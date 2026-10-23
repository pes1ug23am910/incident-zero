param(
    [ValidateSet('mock', 'real')][string]$Mode = 'mock',
    [string]$ReportsDir = '',
    [string]$RunsDir = '',
    [int]$Port = 0,
    [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $localPython = Join-Path $repoRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $localPython) {
        $Python = $localPython
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $Python = 'python'
    } else {
        throw 'Python is missing. Create .venv and install ui/requirements.txt (see README Control Room).'
    }
}
Push-Location $repoRoot
try {
    & $Python -c 'import fastapi, uvicorn'
    if ($LASTEXITCODE -ne 0) {
        throw 'Missing UI dependencies. Run: .\.venv\Scripts\python.exe -m pip install -r ui/requirements.txt'
    }
    $uiArguments = @('-m', 'ui.serve', '--mode', $Mode)
    if ($ReportsDir) { $uiArguments += @('--reports-dir', $ReportsDir) }
    if ($RunsDir) { $uiArguments += @('--runs-dir', $RunsDir) }
    if ($Port -gt 0) { $uiArguments += @('--port', $Port) }
    & $Python @uiArguments
    if ($LASTEXITCODE -ne 0) { throw "Control Room exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
