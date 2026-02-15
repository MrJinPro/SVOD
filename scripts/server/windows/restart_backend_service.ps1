param(
  [string]$ServiceName = 'SVOD-Backend'
)

$ErrorActionPreference = 'Stop'

Write-Host "Restarting service: $ServiceName" -ForegroundColor Cyan

if (-not (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) {
  throw "Service not found: $ServiceName"
}

Restart-Service -Name $ServiceName -Force
Start-Sleep -Seconds 1
(Get-Service -Name $ServiceName) | Format-List Name, Status, StartType
