param(
  [Parameter(Mandatory = $true)]
  [string]$RepoRoot,

  [string]$TaskName = 'SVOD-Backend-AutoRestart',
  [string]$ServiceName = 'SVOD-Backend'
)

$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path $RepoRoot 'scripts\server\windows\watch_repo_and_restart.ps1'
if (-not (Test-Path $scriptPath)) {
  throw "Watcher script not found: $scriptPath"
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
  '-NoProfile -ExecutionPolicy Bypass -File "{0}" -RepoRoot "{1}" -ServiceName "{2}"' -f $scriptPath, $RepoRoot, $ServiceName
)

# Every 1 minute, forever
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$trigger.RepetitionInterval = (New-TimeSpan -Minutes 1)
$trigger.RepetitionDuration = [TimeSpan]::MaxValue

$principal = New-ScheduledTaskPrincipal -UserId 'NT AUTHORITY\SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "Installed scheduled task: $TaskName" -ForegroundColor Green
