param(
  [Parameter(Mandatory = $true)]
  [string]$RepoRoot,

  [Parameter(Mandatory = $true)]
  [string]$NssmExe,

  [string]$ServiceName = 'SVOD-Frontend',
  [string]$BindHost = '0.0.0.0',
  [int]$Port = 4173,

  # If set, run `npm ci` (or `npm install` fallback) before build.
  [switch]$EnsureNodeModules = $true
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $RepoRoot)) { throw "RepoRoot not found: $RepoRoot" }
if (-not (Test-Path $NssmExe)) { throw "NSSM not found: $NssmExe" }

$frontendDir = Join-Path $RepoRoot 'svod-command-center'
if (-not (Test-Path $frontendDir)) { throw "Frontend dir not found: $frontendDir" }

function Resolve-NpmCmd() {
  $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if ($npm) { return $npm.Path }
  $npm2 = Get-Command npm -ErrorAction SilentlyContinue
  if ($npm2) { return $npm2.Path }
  return $null
}

$npmCmd = Resolve-NpmCmd
if (-not $npmCmd) {
  throw 'npm not found. Install Node.js 18+ and ensure it is in PATH.'
}

$logsDir = Join-Path $frontendDir 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }

$stdout = Join-Path $logsDir 'frontend-service.out.log'
$stderr = Join-Path $logsDir 'frontend-service.err.log'

if ($EnsureNodeModules) {
  Write-Host 'Installing frontend dependencies...' -ForegroundColor Cyan
  Push-Location $frontendDir
  try {
    & $npmCmd ci
    if ($LASTEXITCODE -ne 0) {
      & $npmCmd install
    }
  } finally {
    Pop-Location
  }
}

Write-Host 'Building frontend (npm run build)...' -ForegroundColor Cyan
Push-Location $frontendDir
try {
  & $npmCmd run build
} finally {
  Pop-Location
}

if ($LASTEXITCODE -ne 0) {
  throw 'Frontend build failed.'
}

# Install (or re-install) service
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
  Write-Host "Service exists, stopping: $ServiceName" -ForegroundColor Yellow
  try { & $NssmExe stop $ServiceName | Out-Null } catch { }
  try { & $NssmExe remove $ServiceName confirm | Out-Null } catch { }
  Start-Sleep -Seconds 1
}

# Run preview server as a long-running service.
$parameters = 'run preview -- --host {0} --port {1}' -f $BindHost, $Port

Write-Host "Installing service: $ServiceName" -ForegroundColor Cyan
& $NssmExe install $ServiceName $npmCmd $parameters | Out-Null
& $NssmExe set $ServiceName AppDirectory $frontendDir | Out-Null

& $NssmExe set $ServiceName AppStdout $stdout | Out-Null
& $NssmExe set $ServiceName AppStderr $stderr | Out-Null
& $NssmExe set $ServiceName AppRotateFiles 1 | Out-Null
& $NssmExe set $ServiceName AppRotateOnline 1 | Out-Null

& $NssmExe set $ServiceName AppExit Default Restart | Out-Null
& $NssmExe set $ServiceName AppRestartDelay 5000 | Out-Null
& $NssmExe set $ServiceName Start SERVICE_AUTO_START | Out-Null

try {
  sc.exe failure $ServiceName reset= 0 actions= restart/5000/restart/5000/restart/5000 | Out-Null
  sc.exe failureflag $ServiceName 1 | Out-Null
} catch {
  # ignore
}

Write-Host 'Starting service...' -ForegroundColor Cyan
& $NssmExe start $ServiceName | Out-Null

(Get-Service -Name $ServiceName) | Format-List Name, Status, StartType
Write-Host "Logs: $stdout / $stderr" -ForegroundColor Gray
Write-Host "Frontend: http://<server-ip>:$Port" -ForegroundColor Green
