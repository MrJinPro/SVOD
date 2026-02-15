param(
  [Parameter(Mandatory = $true)]
  [string]$RepoRoot,

  [string]$ServiceName = 'SVOD-Backend',

  # Optional: path to python.exe inside a venv. If not provided, tries to use backend\.venv\Scripts\python.exe
  [string]$PythonExe = '',

  [int]$RestartDelaySeconds = 2
)

$ErrorActionPreference = 'Stop'

function Resolve-PythonExe([string]$repoRoot, [string]$pythonExe) {
  if ($pythonExe -and (Test-Path $pythonExe)) { return $pythonExe }

  $candidates = @(
    (Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'),
    (Join-Path $repoRoot '.venv\Scripts\python.exe'),
    (Join-Path $repoRoot 'backend\.venv312\Scripts\python.exe'),
    (Join-Path $repoRoot '.venv312\Scripts\python.exe')
  )

  foreach ($p in $candidates) {
    if (Test-Path $p) { return $p }
  }

  return $null
}

function Read-TextFile([string]$path) {
  if (-not (Test-Path $path)) { return '' }
  return (Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue).Trim()
}

function Write-TextFile([string]$path, [string]$value) {
  $dir = Split-Path -Parent $path
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
  Set-Content -LiteralPath $path -Value $value -Encoding UTF8
}

if (-not (Test-Path $RepoRoot)) {
  throw "RepoRoot not found: $RepoRoot"
}

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
  # If git is not installed, do nothing (avoid noisy failures every minute).
  exit 0
}

$stateDir = Join-Path $RepoRoot '.svod\deploy-state'
$lastHeadFile = Join-Path $stateDir 'last_head.txt'
$reqHashFile = Join-Path $stateDir 'requirements_sha256.txt'

$backendDir = Join-Path $RepoRoot 'backend'
$reqFile = Join-Path $backendDir 'requirements.txt'

# Determine current HEAD
$head = (& git -C $RepoRoot rev-parse HEAD 2>$null).Trim()
if (-not $head) { exit 0 }

$lastHead = Read-TextFile $lastHeadFile

# First run: record and exit (do not restart unexpectedly)
if (-not $lastHead) {
  Write-TextFile $lastHeadFile $head
  if (Test-Path $reqFile) {
    $reqHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $reqFile).Hash
    Write-TextFile $reqHashFile $reqHash
  }
  exit 0
}

if ($head -eq $lastHead) {
  exit 0
}

# HEAD changed => restart backend (and optionally update deps if requirements changed)
$python = Resolve-PythonExe -repoRoot $RepoRoot -pythonExe $PythonExe

if ((Test-Path $reqFile) -and $python) {
  $newReqHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $reqFile).Hash
  $oldReqHash = Read-TextFile $reqHashFile

  if ($newReqHash -and ($newReqHash -ne $oldReqHash)) {
    try {
      & $python -m pip install -r $reqFile | Out-Null
      Write-TextFile $reqHashFile $newReqHash
    } catch {
      # Don't block restarts on pip issues; service restart is still valuable.
    }
  }
}

try {
  if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Restart-Service -Name $ServiceName -Force
    Start-Sleep -Seconds $RestartDelaySeconds
  }
} catch {
  # ignore; task should be resilient
}

Write-TextFile $lastHeadFile $head
