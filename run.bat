@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto install

echo First-time setup, this may take a minute...
py -3 -m venv .venv >nul 2>&1
if exist ".venv\Scripts\python.exe" goto install
python -m venv .venv
if exist ".venv\Scripts\python.exe" goto install

echo.
echo Python was not found. Install it from https://www.python.org/downloads/
echo and make sure to tick "Add python.exe to PATH" during installation.
pause
exit /b 1

:install
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
pause
