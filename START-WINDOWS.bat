@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv
if not exist .venv\Scripts\python.exe goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe launch.py
pause
exit /b
:failed
echo Setup failed. Install Python 3.10+ with PATH enabled and check internet access.
pause
