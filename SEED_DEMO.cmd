@echo off
setlocal
cd /d %~dp0
title SVOD Seed Demo

echo [SVOD] Seeding demo events into backend DB (count=500)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/db/seed/demo-events?count=500 | ConvertTo-Json -Depth 5"

echo.
echo [SVOD] Done.
pause
endlocal
