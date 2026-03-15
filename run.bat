@echo off
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo WARNING: Virtual environment not found. Running with system Python.
    echo Run setup first: python -m venv venv  ^&^&  venv\Scripts\pip install -r requirements.txt
)

echo Starting Carevender Bot...
python carevender_bot.py

if errorlevel 1 (
    echo.
    echo *** Bot exited with an error. See bot.log for details. ***
)

pause
