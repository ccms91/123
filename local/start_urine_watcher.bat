@echo off
title Health Clinic - Urine Dipstick Watcher
color 0D
cd /d "%~dp0\.."

echo ============================================
echo   Station 3(a) - Urine Dipstick Watcher
echo ============================================
echo.

:: Install computer-vision packages (only needed on this PC)
echo Checking urine watcher dependencies...
pip install opencv-python numpy -q
if errorlevel 1 (
    echo.
    echo ERROR: Could not install required packages.
    echo Ensure Python is installed and you have internet access.
    pause
    exit /b 1
)

echo.
echo Watching for new dipstick images...
echo Press Ctrl+C to stop.
echo.
echo TIP: To calibrate strip positions, run:
echo   python local/urine_watcher.py --calibrate C:\path\to\sample_image.jpg
echo.

python local/urine_watcher.py

pause
