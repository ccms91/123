@echo off
title Health Clinic - MRZ Watcher
color 0B
cd /d "%~dp0\.."

echo ============================================
echo   MRZ Passport Scanner Watcher
echo ============================================
echo.
echo Watching for new passport scans...
echo Press Ctrl+C to stop.
echo.

python local/mrz_watcher.py

pause
