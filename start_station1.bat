@echo off
cd /d "%~dp0"
echo ============================================
echo  Station 1 - Starting all services
echo ============================================
echo.

REM Start the local Flask app (browser UI)
start "Station 1 App" cmd /k "python local\local_app.py"

REM Give the app a moment to start before the watchers connect to it
timeout /t 2 /nobreak > nul

REM Start the MRZ passport scanner watcher
start "MRZ Watcher" cmd /k "python local\mrz_watcher.py"

REM Start the signature pad watcher
start "Sig Watcher" cmd /k "python local\sig_watcher.py"

echo All services started in separate windows.
echo.
echo Open this in Chrome:  http://localhost:5001
echo.
echo To stop: close the three console windows.
pause
