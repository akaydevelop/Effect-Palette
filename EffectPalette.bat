@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0EffectPalette.pyw"
    exit /b
)

where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw "%~dp0EffectPalette.pyw"
    exit /b
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0EffectPalette.pyw"
    exit /b
)

echo Pythonw nao encontrado. Instale o Python 3 ou use o instalador final da extensao.
pause
