param(
  [Parameter(Mandatory = $true)]
  [string]$NssmExe,

  [string]$ServiceName = 'SVOD-Frontend'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $NssmExe)) { throw "NSSM not found: $NssmExe" }

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
  try { & $NssmExe stop $ServiceName | Out-Null } catch { }
  try { & $NssmExe remove $ServiceName confirm | Out-Null } catch { }
  Write-Host "Removed service: $ServiceName" -ForegroundColor Green
} else {
  Write-Host "Service not found: $ServiceName" -ForegroundColor Yellow
}
