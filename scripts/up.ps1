param([Alias('h','-help')][switch]$Help, [string]$DemoDir = '')
if ($Help) { Write-Output 'Usage: up.ps1 [-DemoDir path]; -Help / --help / -h'; exit 0 }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.operator', 'up')
if ($DemoDir) { $a += @('--demo-dir', $DemoDir) }
Invoke-IncidentPython -Arguments $a
exit $script:IncidentExit