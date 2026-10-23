param([Alias('h','-help')][switch]$Help, [switch]$Live, [string]$Incident='payment-failure', [Alias('svc')][string]$Service, [string]$ReportId, [string]$Operator='Yash Verma', [int]$LoadUsers=20, [string]$RejectedReport, [switch]$BrowserApproval)
if ($Help) { Write-Output 'Usage: demo.ps1 [-Live] [-Incident name] [-Service name] [-ReportId id] [-Operator name] [-LoadUsers 20] [-RejectedReport path] [-BrowserApproval]; default preview; -Help / --help / -h'; exit 0 }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.operator', 'demo')
if ($Live) { $a += '--live' }
$a += @('--incident', $Incident, '--operator', $Operator, '--load-users', $LoadUsers)
if ($Service) { $a += @('--svc', $Service) }
if ($ReportId) { $a += @('--report-id', $ReportId) }
if ($RejectedReport) { $a += @('--rejected-report', $RejectedReport) }
if ($BrowserApproval) { $a += '--browser-approval' }
Invoke-IncidentPython -Arguments $a
exit $script:IncidentExit