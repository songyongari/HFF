@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo ==============================================
echo   Biocom Product Insight Dashboard
echo ==============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo         Install from https://www.python.org with "Add to PATH" checked.
    pause
    exit /b 1
)

python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo [INFO] Installing packages...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] pip install failed.
        pause
        exit /b 1
    )
)

echo Opening browser at http://localhost:8501 in 6s...
start "" /b cmd /c "timeout /t 6 /nobreak >nul && start http://localhost:8501"

echo.
echo Press Ctrl+C or close this window to stop.
echo ==============================================
echo.

python -m streamlit run app\Home.py --server.port 8501 --server.headless true
echo.
echo [Stopped]
pause
