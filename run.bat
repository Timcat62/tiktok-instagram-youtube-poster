@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto install

echo Premiere installation, ca peut prendre une minute...
py -3 -m venv .venv >nul 2>&1
if exist ".venv\Scripts\python.exe" goto install
python -m venv .venv
if exist ".venv\Scripts\python.exe" goto install

echo.
echo Python est introuvable. Installe-le depuis https://www.python.org/downloads/
echo et coche bien la case "Add python.exe to PATH" pendant l'installation.
pause
exit /b 1

:install
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Echec de l'installation des dependances.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
pause
