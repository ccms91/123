@echo off
title Health Clinic - Web Server
color 0A
cd /d "%~dp0"

echo ============================================
echo   Health Screening Clinic - Web Server
echo ============================================
echo.

:: Check .env exists
if not exist ".env" (
    echo ERROR: .env file not found!
    echo.
    echo Please copy .env.example to .env and fill in your Google credentials.
    echo See SETUP_GUIDE.md for instructions.
    echo.
    pause
    exit /b 1
)

:: Install / update dependencies quietly
echo Checking dependencies...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies.
    echo Make sure Python is installed: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Show local IP so other stations know what URL to use
echo.
echo Your local IP addresses (for other stations on this network):
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set ip=%%a
    setlocal enabledelayedexpansion
    set ip=!ip: =!
    echo   http://!ip!:5000
    endlocal
)
echo.
echo Station URLs:
echo   Station 1 (Registration):  http://localhost:5000/
echo   Station 2a (Height/Weight): http://localhost:5000/station2
echo   Station 3b (BP / Snellen): http://localhost:5000/station3b
echo.
echo NOTE: For camera QR scanning to work on OTHER devices,
echo       see SETUP_GUIDE.md - "Camera on LAN devices" section.
echo.
echo Press Ctrl+C to stop the server.
echo ============================================
echo.

python app.py

pause
