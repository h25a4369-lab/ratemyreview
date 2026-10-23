@echo off
REM Rate My Review — start the site on Windows.
REM Double-click this file, or run it from a terminal.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the virtual environment...
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo.
        echo Python 3.12 was not found. Install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo.
echo Starting Rate My Review at http://127.0.0.1:8000
echo Press Ctrl+C to stop.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload
pause
