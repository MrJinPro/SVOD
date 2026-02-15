@echo off
setlocal
title SVOD Backend (8000)

set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%backend"

REM Resolve Python executable (prefer venvs if present)
set "PYTHON_EXE="
if exist "%SCRIPT_DIR%.venv312\Scripts\python.exe" set "PYTHON_EXE=%SCRIPT_DIR%.venv312\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%BACKEND_DIR%\.venv312\Scripts\python.exe" set "PYTHON_EXE=%BACKEND_DIR%\.venv312\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%BACKEND_DIR%\.venv\Scripts\python.exe" set "PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

REM Default to SQLite unless DATABASE_URL is explicitly provided.
REM You can override via backend/.env or by setting DATABASE_URL before запуском.
if not defined DATABASE_URL set "DATABASE_URL=sqlite+aiosqlite:///./svod.db"
if not defined CORS_ORIGINS set "CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173,http://localhost"

pushd "%BACKEND_DIR%" || (
	echo [SVOD] ERROR: backend folder not found: "%BACKEND_DIR%"
	pause
	exit /b 1
)
echo [SVOD] Starting backend on http://0.0.0.0:8000 (LAN)
echo [SVOD] DATABASE_URL=%DATABASE_URL%

echo [SVOD] PYTHON=%PYTHON_EXE%

"%PYTHON_EXE%" -m uvicorn app.main:app --app-dir . --host 0.0.0.0 --port 8000 %*

popd

echo.
echo [SVOD] Backend stopped.
pause
endlocal
