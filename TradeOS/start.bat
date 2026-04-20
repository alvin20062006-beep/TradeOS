@echo off
chcp 65001 >nul 2>&1
title TradeOS

echo ========================================
echo   TradeOS Local Launcher
echo ========================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

python -c "import fastapi, uvicorn, yfinance, numpy" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Missing packages detected. Installing requirements-local.txt ...
    python -m pip install -r requirements-local.txt
)

echo [START] Launching API + Web Console ...
python run.py start
