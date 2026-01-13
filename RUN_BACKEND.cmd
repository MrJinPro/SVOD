@echo off
setlocal
title SVOD Backend (8000)

REM Запуск backend отдельно (SQLite)
set "DATABASE_URL=sqlite+aiosqlite:///d:/alarm/SVOD_SOFT/backend/svod.db"
set "CORS_ORIGINS=http://localhost:4173,http://127.0.0.1:4173,http://localhost,http://0.0.0.0:4173"

cd /d "d:\alarm\SVOD_SOFT\backend"
echo [SVOD] Starting backend on http://0.0.0.0:8000 (LAN)
echo [SVOD] DATABASE_URL=%DATABASE_URL%

d:\alarm\SVOD_SOFT\.venv312\Scripts\python.exe -m uvicorn app.main:app --app-dir d:\alarm\SVOD_SOFT\backend --host 0.0.0.0 --port 8000

echo.
echo [SVOD] Backend stopped.
pause
endlocal
