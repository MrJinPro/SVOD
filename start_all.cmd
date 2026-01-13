@echo off
setlocal

REM Откроет 2 отдельных окна (backend и frontend)
start "SVOD Backend" cmd /k ""%~dp0run_backend.cmd""
start "SVOD Frontend" cmd /k ""%~dp0run_frontend_preview.cmd""

echo [SVOD] Opened backend and frontend windows.
echo Затем запустите seed_demo.cmd (в третьем окне) когда backend уже поднялся.
pause
