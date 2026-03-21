@echo off
REM ────────────────────────────────────────────────────────────────────────────
REM  Station 1 – Registration  (Windows)
REM  Double-click this file to start the registration app + MRZ watcher.
REM ────────────────────────────────────────────────────────────────────────────

cd /d "%~dp0"

REM Activate virtual environment (created by: python -m venv .venv)
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment not found.
    echo         Run:  python -m venv .venv  ^&^&  pip install -r requirements.txt
    pause
    exit /b 1
)

REM Start the MRZ watcher in a separate window
start "MRZ Watcher" cmd /k python local\mrz_watcher.py

REM Give the watcher a moment to start, then open the app in the browser
timeout /t 2 /nobreak >nul
start http://localhost:5100/register

REM Start the Flask registration app (this window stays open as the server)
python local\registration_app.py

pause
