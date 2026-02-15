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

# Use schtasks.exe for maximum compatibility across Windows versions/PowerShell.
$taskCmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{0}" -RepoRoot "{1}" -ServiceName "{2}"' -f $scriptPath, $RepoRoot, $ServiceName

$schtasks = Get-Command schtasks.exe -ErrorAction SilentlyContinue
if (-not $schtasks) { throw 'schtasks.exe not found.' }

& $schtasks.Path /Create /F /TN $TaskName /SC MINUTE /MO 1 /RU SYSTEM /RL HIGHEST /TR $taskCmd | Out-Null

Write-Host "Installed scheduled task: $TaskName" -ForegroundColor Green
Write-Host "Runs every 1 minute as SYSTEM." -ForegroundColor Gray
