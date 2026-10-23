param([Alias('h','-help')][switch]$Help, [Parameter(Position=0)][string]$Incident, [string]$Combo, [Alias('svc')][string]$Service, [string]$ReportId, [int]$AlertTimeout=150, [int]$CleanTimeout=360)
if ($Help) { Write-Output 'Usage: checkpoint2.ps1 <incident> [-Combo ids] [-Service name] [-ReportId id] [-AlertTimeout 150] [-CleanTimeout 360]; -Help / --help / -h'; exit 0 }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.operator', 'checkpoint2')
if ($Incident) { $a += $Incident }
if ($Combo) { $a += @('--combo', $Combo) }
if ($Service) { $a += @('--svc', $Service) }
if ($ReportId) { $a += @('--report-id', $ReportId) }
$a += @('--alert-timeout', $AlertTimeout, '--clean-timeout', $CleanTimeout)
Invoke-IncidentPython -Arguments $a
exit $script:IncidentExit