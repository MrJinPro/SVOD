$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $root '.venv312\Scripts\python.exe'
$backendDir = Join-Path $root 'backend'

if (-not (Test-Path $python)) {
  Write-Host "Не найден Python venv: $python" -ForegroundColor Red
  Write-Host "Сначала создайте/настройте venv .venv312 (Python 3.12) и поставьте зависимости backend." -ForegroundColor Yellow
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

$env:DATABASE_URL = 'sqlite+aiosqlite:///d:/alarm/SVOD_SOFT/backend/svod.db'
$env:CORS_ORIGINS = 'http://localhost:4173,http://127.0.0.1:4173,http://localhost'

Write-Host "Backend: http://127.0.0.1:8000 (docs: /docs)" -ForegroundColor Green
Write-Host "DB: SQLite -> backend/svod.db" -ForegroundColor Gray
Write-Host "Логи: backend/uvicorn.out.log и backend/uvicorn.err.log" -ForegroundColor Gray

Set-Location $backendDir
& $python -m uvicorn app.main:app --app-dir $backendDir --host 127.0.0.1 --port 8000
