[CmdletBinding(PositionalBinding=$false)]
param([Alias('h','-help')][switch]$Help, [ValidateSet(1,5,6,9)][int[]]$Gate, [switch]$ScanOnly, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Remaining)
if ($Help -or ($Remaining -contains '--help')) { Write-Output 'Usage: release_check.ps1 [-Gate 1,5,6,9] [-ScanOnly] [-Help|--help|-h]; default runs gates 1,5,6,9'; exit 0 }
if ($Remaining) { throw ('Unrecognized arguments: ' + ($Remaining -join ' ')) }
. "$PSScriptRoot/_shell.ps1"
$a = @('-m', 'scripts.release_check')
foreach ($number in $Gate) { $a += @('--gate', $number) }
if ($ScanOnly) { $a += '--scan-only' }
Invoke-IncidentPython -Arguments $a
exit $script:IncidentExit
