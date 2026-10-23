[CmdletBinding(PositionalBinding=$false)]
param([Alias('h','-help')][switch]$Help, [ValidateSet('mock','real')][string]$Mode='mock', [string]$ReportsDir, [string]$RunsDir, [int]$Port=0, [string]$Python='', [Parameter(ValueFromRemainingArguments=$true)][string[]]$Remaining)
if ($Help -or ($Remaining -contains '--help')) { Write-Output 'Usage: ui.ps1 [-Mode mock|real] [-ReportsDir path] [-RunsDir path] [-Port number] [-Python executable]; -Help / --help / -h'; exit 0 }
if ($Remaining) { throw ('Unrecognized arguments: ' + ($Remaining -join ' ')) }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.operator', 'ui')
$a += @('--mode', $Mode)
if ($ReportsDir) { $a += @('--reports-dir', $ReportsDir) }
if ($RunsDir) { $a += @('--runs-dir', $RunsDir) }
if ($Port) { $a += @('--port', $Port) }
Invoke-IncidentPython -Arguments $a -Python $Python
exit $script:IncidentExit
