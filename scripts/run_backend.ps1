$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backendDir = Join-Path $root 'backend'

function Resolve-PythonExe([string]$rootDir, [string]$backendPath) {
  $candidates = @(
    (Join-Path $rootDir '.venv312\Scripts\python.exe'),
    (Join-Path $backendPath '.venv312\Scripts\python.exe'),
    (Join-Path $rootDir '.venv\Scripts\python.exe'),
    (Join-Path $backendPath '.venv\Scripts\python.exe')
  )

  foreach ($p in $candidates) {
    if (Test-Path $p) { return $p }
  }

  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Path }

  return $null
}

$python = Resolve-PythonExe -rootDir $root -backendPath $backendDir

if (-not $python) {
  Write-Host "Не найден Python (venv или системный)." -ForegroundColor Red
  Write-Host "Ожидается один из путей: .venv312\\Scripts\\python.exe, .venv\\Scripts\\python.exe (в корне или backend/)." -ForegroundColor Yellow
  Read-Host "Enter для выхода"
  exit 1
}

# Освободить порт 8000 (если занят)
try {
  $tcp = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($tcp) {
    Write-Host "Освобождаю порт 8000 (PID $($tcp.OwningProcess))..." -ForegroundColor Yellow
    Stop-Process -Id $tcp.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
  }
} catch {
  # ignore
}


# Dev defaults (can be overridden by environment or backend/.env if you run without this script)
$env:DATABASE_URL = 'sqlite+aiosqlite:///d:/alarm/SVOD_SOFT/backend/svod.db'

# По умолчанию для dev-режима используем SQLite-слепок агентской БД, если он есть.
# Это также отключает попытки синка из MSSQL (которые требуют pyodbc/ODBC).
$agencyDb = Join-Path $backendDir 'agency_raw.db'
if (Test-Path $agencyDb) {
  $env:AGENCY_DATABASE_URL = 'sqlite:///d:/alarm/SVOD_SOFT/backend/agency_raw.db'
}

# Allow Vite dev/preview from LAN. Regex is the most robust here because
# the UI may be opened by IP/hostname, not only localhost.
$env:CORS_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173,http://localhost'
$env:CORS_ORIGIN_REGEX = '^https?://.+(:5173|:4173)$'

Write-Host "Backend: http://0.0.0.0:8000 (docs: /docs)" -ForegroundColor Green
Write-Host "DB: SQLite -> backend/svod.db" -ForegroundColor Gray
Write-Host "Логи: backend/uvicorn.log" -ForegroundColor Gray

$logFile = Join-Path $backendDir 'uvicorn.log'
try { Remove-Item $logFile -Force -ErrorAction SilentlyContinue } catch { }

Set-Location $backendDir

# Uvicorn может писать часть логов в stderr, а Windows PowerShell 5.1
# превращает stderr от native-команд в ErrorRecord (NativeCommandError).
# VS Code task из-за этого может завершаться с ошибкой. Запускаем через cmd.exe.
$cmd = '"{0}" -m uvicorn app.main:app --app-dir "{1}" --host 0.0.0.0 --port 8000' -f $python, $backendDir

# Важно: редирект делаем внутри cmd.exe, чтобы PowerShell не превращал stderr
# от native-команд в NativeCommandError и не завершал VS Code task.
$cmdLine = "$cmd 1>> `"$logFile`" 2>>&1"
cmd /c $cmdLine
exit $LASTEXITCODE
