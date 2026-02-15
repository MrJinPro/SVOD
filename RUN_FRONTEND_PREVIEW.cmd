@echo off
setlocal
title SVOD Frontend (preview 4173)

set "SCRIPT_DIR=%~dp0"
set "FRONTEND_DIR=%SCRIPT_DIR%svod-command-center"

set "NPM_CMD="
where npm >nul 2>&1 && set "NPM_CMD=npm"
if not defined NPM_CMD if exist "C:\Program Files\nodejs\npm.cmd" set "NPM_CMD=C:\Program Files\nodejs\npm.cmd"
if not defined NPM_CMD (
	echo [SVOD] ERROR: npm not found. Install Node.js and ensure it is in PATH.
	pause
	exit /b 1
)

pushd "%FRONTEND_DIR%" || (
	echo [SVOD] ERROR: frontend folder not found: "%FRONTEND_DIR%"
	pause
	exit /b 1
)
echo [SVOD] Building frontend...

call "%NPM_CMD%" run build
if errorlevel 1 (
	echo.
	echo [SVOD] Build failed.
	pause
	popd
	exit /b 1
)

echo.
echo [SVOD] Starting preview on http://0.0.0.0:4173 (LAN)
call "%NPM_CMD%" run preview -- --host 0.0.0.0 --port 4173

popd

echo.
echo [SVOD] Frontend preview stopped.
pause
