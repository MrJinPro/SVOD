$ErrorActionPreference = 'Stop'

$uri = 'http://127.0.0.1:8000/api/v1/db/seed/demo-events'

Write-Host "Seed demo -> $uri" -ForegroundColor Cyan

# Ждем backend до 10 секунд
$ok = $false
for ($i=0; $i -lt 10; $i++) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/openapi.json' -TimeoutSec 2
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch {
    Start-Sleep -Seconds 1
  }
}

if (-not $ok) {
  Write-Host "Backend не отвечает на 8000. Сначала запустите backend." -ForegroundColor Red
  Read-Host "Enter для выхода"
  exit 1
}

$res = Invoke-RestMethod -Method Post -Uri $uri
$res | ConvertTo-Json -Depth 5
