param(
  [Parameter(Mandatory = $true)]
  [string]$RepoRoot,

  [Parameter(Mandatory = $true)]
  [string]$NssmExe,

  [string]$ServiceName = 'SVOD-Backend',
  [string]$Host = '0.0.0.0',
  [int]$Port = 8000,

  # Create/update venv in backend\.venv (recommended)
  [switch]$EnsureVenv = $true
)

$ErrorActionPreference = 'Stop'

function Resolve-PythonForService([string]$repoRoot) {
  $backendDir = Join-Path $repoRoot 'backend'
  $venvPython = Join-Path $backendDir '.venv\Scripts\python.exe'
  if (Test-Path $venvPython) { return $venvPython }

  $candidates = @(
    (Join-Path $repoRoot '.venv\Scripts\python.exe'),
    (Join-Path $repoRoot '.venv312\Scripts\python.exe'),
    (Join-Path $backendDir '.venv312\Scripts\python.exe')
  )

  foreach ($p in $candidates) {
    if (Test-Path $p) { return $p }
  }

  # Fallback to system python
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Path }

  # As a last resort, use the Python Launcher if present
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return $py.Path }

  return $null
}

if (-not (Test-Path $RepoRoot)) { throw "RepoRoot not found: $RepoRoot" }
if (-not (Test-Path $NssmExe)) { throw "NSSM not found: $NssmExe" }

$backendDir = Join-Path $RepoRoot 'backend'
if (-not (Test-Path $backendDir)) { throw "Backend dir not found: $backendDir" }

# Create venv if requested
if ($EnsureVenv) {
  $venvDir = Join-Path $backendDir '.venv'
  $venvPython = Join-Path $venvDir 'Scripts\python.exe'

  if (-not (Test-Path $venvPython)) {
    Write-Host "Creating venv: $venvDir" -ForegroundColor Cyan

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
      & $py.Path -3.12 -m venv $venvDir
    } else {
      $python = Get-Command python -ErrorAction SilentlyContinue
      if (-not $python) { throw 'Python not found (install Python 3.12+ or py launcher).' }
      & $python.Path -m venv $venvDir
    }
  }

  Write-Host "Installing backend requirements..." -ForegroundColor Cyan
  & $venvPython -m pip install -r (Join-Path $backendDir 'requirements.txt')
}

$pythonExe = Resolve-PythonForService -repoRoot $RepoRoot
if (-not $pythonExe) { throw 'Unable to resolve python.exe for the service.' }

$logsDir = Join-Path $backendDir 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }

$stdout = Join-Path $logsDir 'uvicorn-service.out.log'
$stderr = Join-Path $logsDir 'uvicorn-service.err.log'

# Install (or re-install) service
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
  Write-Host "Service exists, stopping: $ServiceName" -ForegroundColor Yellow
  try { & $NssmExe stop $ServiceName | Out-Null } catch { }
  try { & $NssmExe remove $ServiceName confirm | Out-Null } catch { }
  Start-Sleep -Seconds 1
}

$parameters = "-m uvicorn app.main:app --app-dir . --host $Host --port $Port"

Write-Host "Installing service: $ServiceName" -ForegroundColor Cyan
& $NssmExe install $ServiceName $pythonExe $parameters | Out-Null
& $NssmExe set $ServiceName AppDirectory $backendDir | Out-Null

& $NssmExe set $ServiceName AppStdout $stdout | Out-Null
& $NssmExe set $ServiceName AppStderr $stderr | Out-Null
& $NssmExe set $ServiceName AppRotateFiles 1 | Out-Null
& $NssmExe set $ServiceName AppRotateOnline 1 | Out-Null

& $NssmExe set $ServiceName AppExit Default Restart | Out-Null
& $NssmExe set $ServiceName AppRestartDelay 5000 | Out-Null
& $NssmExe set $ServiceName Start SERVICE_AUTO_START | Out-Null

# Also configure Windows SCM recovery (belt & suspenders)
try {
  sc.exe failure $ServiceName reset= 0 actions= restart/5000/restart/5000/restart/5000 | Out-Null
  sc.exe failureflag $ServiceName 1 | Out-Null
} catch {
  # ignore
}

Write-Host "Starting service..." -ForegroundColor Cyan
& $NssmExe start $ServiceName | Out-Null

(Get-Service -Name $ServiceName) | Format-List Name, Status, StartType
Write-Host "Logs: $stdout / $stderr" -ForegroundColor Gray
Write-Host "Backend: http://<server-ip>:$Port/docs" -ForegroundColor Green
