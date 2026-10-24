[CmdletBinding(PositionalBinding=$false)]
param([Alias('h','-help')][switch]$Help, [Parameter(Position=0)][string]$Incident, [string]$Combo, [Alias('svc','-svc')][string]$Service, [string]$ReportId, [ValidateRange(0,90)][int]$AlertTimeout=90, [int]$CleanTimeout=360, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Remaining)
if ($Help -or ($Remaining -contains '--help') -or $Incident -eq '--help') { Write-Output 'Usage: checkpoint2.ps1 <incident> [-Combo ids] [-Service name] [-ReportId id] [-AlertTimeout 90] [-CleanTimeout 360]; -Help / --help / -h'; exit 0 }
if ($Remaining) { throw ('Unrecognized arguments: ' + ($Remaining -join ' ')) }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.operator', 'checkpoint2')
if ($Incident) { $a += $Incident }
if ($Combo) { $a += @('--combo', $Combo) }
if ($Service) { $a += @('--svc', $Service) }
if ($ReportId) { $a += @('--report-id', $ReportId) }
$a += @('--alert-timeout', $AlertTimeout, '--clean-timeout', $CleanTimeout)
Invoke-IncidentPython -Arguments $a
exit $script:IncidentExit
