param([Alias('h','-help')][switch]$Help, [string]$OutputDir, [switch]$PrintCommand)
if ($Help) { Write-Output 'Usage: crossplatform_check.ps1 [-OutputDir path] [-PrintCommand]; disposable Linux test container; -Help / --help / -h'; exit 0 }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.crossplatform_check')
if ($OutputDir) { $a += @('--output-dir', $OutputDir) }
if ($PrintCommand) { $a += '--print-command' }
Invoke-IncidentPython -Arguments $a
exit $script:IncidentExit