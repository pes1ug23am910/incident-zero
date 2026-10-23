[CmdletBinding(PositionalBinding=$false)]
param([Alias('h','-help')][switch]$Help, [string]$StackRoot, [string]$OutputDir, [switch]$NoModel, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Remaining)
if ($Help -or ($Remaining -contains '--help')) { Write-Output 'Usage: preflight.ps1 [-StackRoot path] [-OutputDir path] [-NoModel]; read-only; -Help / --help / -h'; exit 0 }
if ($Remaining) { throw ('Unrecognized arguments: ' + ($Remaining -join ' ')) }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.preflight')
if ($StackRoot) { $a += @('--stack-root', $StackRoot) }
if ($OutputDir) { $a += @('--output-dir', $OutputDir) }
if ($NoModel) { $a += '--no-model' }
Invoke-IncidentPython -Arguments $a
exit $script:IncidentExit
