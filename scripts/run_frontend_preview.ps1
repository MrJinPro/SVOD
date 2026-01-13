$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$frontendDir = Join-Path $root 'svod-command-center'

# Освободить порт 4173 (если занят)
try {
  $tcp = Get-NetTCPConnection -LocalPort 4173 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($tcp) {
    Write-Host "Освобождаю порт 4173 (PID $($tcp.OwningProcess))..." -ForegroundColor Yellow
    Stop-Process -Id $tcp.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
  }
} catch {
  # ignore
}

Set-Location $frontendDir

Write-Host "Собираю фронтенд (npm run build)..." -ForegroundColor Cyan
npm run build

Write-Host "Frontend preview: http://127.0.0.1:4173" -ForegroundColor Green
Write-Host "API по умолчанию: http://localhost:8000/api/v1" -ForegroundColor Gray

npm run preview -- --host 127.0.0.1 --port 4173
