[CmdletBinding(PositionalBinding=$false)]
param([Alias('h','-help')][switch]$Help, [string]$DemoDir = '', [Parameter(ValueFromRemainingArguments=$true)][string[]]$Remaining)
if ($Help -or ($Remaining -contains '--help')) { Write-Output 'Usage: up.ps1 [-DemoDir path]; -Help / --help / -h'; exit 0 }
if ($Remaining) { throw ('Unrecognized arguments: ' + ($Remaining -join ' ')) }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.operator', 'up')
if ($DemoDir) { $a += @('--demo-dir', $DemoDir) }
Invoke-IncidentPython -Arguments $a
exit $script:IncidentExit
