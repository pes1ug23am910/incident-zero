[CmdletBinding(PositionalBinding=$false)]
param([Alias('h','-help')][switch]$Help, [switch]$NoSmoke, [string]$StackRoot, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Remaining)
if ($Help -or ($Remaining -contains '--help')) { Write-Output 'Usage: morning.ps1 [-NoSmoke] [-StackRoot path]; -NoSmoke skips ALL stack mutations; -Help / --help / -h'; exit 0 }
if ($Remaining) { throw ('Unrecognized arguments: ' + ($Remaining -join ' ')) }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.morning')
if ($NoSmoke) { $a += '--no-smoke' }
if ($StackRoot) { $a += @('--stack-root', $StackRoot) }
Invoke-IncidentPython -Arguments $a
exit $script:IncidentExit
