[CmdletBinding(PositionalBinding=$false)]
param([Alias('h','-help')][switch]$Help, [Parameter(Position=0)][string]$Incident, [Alias('svc','-svc')][string]$Service, [string]$ReportId, [string]$Operator='Yash Verma', [int]$LoadUsers=20, [switch]$BrowserApproval, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Remaining)
if ($Help -or ($Remaining -contains '--help') -or $Incident -eq '--help') { Write-Output 'Usage: checkpoint3.ps1 <incident> [-Service name] [-ReportId id] [-Operator name] [-LoadUsers 20] [-BrowserApproval]; -Help / --help / -h'; exit 0 }
if ($Remaining) { throw ('Unrecognized arguments: ' + ($Remaining -join ' ')) }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.operator', 'checkpoint3')
if ($Incident) { $a += $Incident }
if ($Service) { $a += @('--svc', $Service) }
if ($ReportId) { $a += @('--report-id', $ReportId) }
$a += @('--operator', $Operator, '--load-users', $LoadUsers)
if ($BrowserApproval) { $a += '--browser-approval' }
Invoke-IncidentPython -Arguments $a
exit $script:IncidentExit
