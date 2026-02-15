param(
  [string]$TaskName = 'SVOD-Backend-AutoRestart'
)

$ErrorActionPreference = 'Stop'

$schtasks = Get-Command schtasks.exe -ErrorAction SilentlyContinue
if (-not $schtasks) { throw 'schtasks.exe not found.' }

try {
  & $schtasks.Path /Delete /F /TN $TaskName | Out-Null
  Write-Host "Removed scheduled task: $TaskName" -ForegroundColor Green
} catch {
  Write-Host "Task not found (or cannot delete): $TaskName" -ForegroundColor Yellow
}
