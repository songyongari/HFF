@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo ==============================================
echo   Biocom Master Data Collector
echo ==============================================
echo   Existing data\*.json cache will be reused.
echo   Delete files in data\ first to force refresh.
echo ==============================================
echo.

python collect_master.py
echo.
pause
