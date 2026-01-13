@echo off
setlocal
title SVOD Stop All

echo [SVOD] Stopping processes on ports 8000 and 4173...
powershell -NoProfile -ExecutionPolicy Bypass -Command "
$tcp = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($tcp) { Stop-Process -Id $tcp.OwningProcess -Force -ErrorAction SilentlyContinue }
$tcp = Get-NetTCPConnection -LocalPort 4173 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($tcp) { Stop-Process -Id $tcp.OwningProcess -Force -ErrorAction SilentlyContinue }
'OK'
" 
echo.
echo [SVOD] Done.
pause
