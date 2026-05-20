@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo ==============================================
echo   First-time Setup: pip install + data fetch
echo ==============================================
echo.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)
echo.
echo [1/2] Packages installed.
echo.

python collect_master.py
if errorlevel 1 (
    echo [ERROR] Master collection failed.
    pause
    exit /b 1
)
echo.
echo ==============================================
echo   Done. Double-click run.bat to launch.
echo ==============================================
pause
