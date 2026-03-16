@echo off
title Health Clinic - Signature Watcher
color 0E
cd /d "%~dp0\.."

echo ============================================
echo   Signature Pad Watcher
echo ============================================
echo.
echo Watching for patient signatures...
echo Press Ctrl+C to stop.
echo.

python local/sig_watcher.py

pause
