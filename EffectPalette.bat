@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        py app.py
    ) else (
        python app.py
    )
)

pause
