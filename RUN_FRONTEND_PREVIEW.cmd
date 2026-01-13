@echo off
setlocal
title SVOD Frontend (preview 4173)

cd /d "d:\alarm\SVOD_SOFT\svod-command-center"
echo [SVOD] Building frontend...

REM Используем npm.cmd (надёжно для cmd)
call "C:\Program Files\nodejs\npm.cmd" run build
if errorlevel 1 (
	echo.
	echo [SVOD] Build failed.
	pause
	exit /b 1
)

echo.
echo [SVOD] Starting preview on http://0.0.0.0:4173 (LAN)
call "C:\Program Files\nodejs\npm.cmd" run preview -- --host 0.0.0.0 --port 4173

echo.
echo [SVOD] Frontend preview stopped.
pause
