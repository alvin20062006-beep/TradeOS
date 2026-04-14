$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "TradeOS"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TradeOS Local Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found. Please install Python 3.10+." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[CHECK] Verifying local runtime dependencies..." -ForegroundColor Yellow
try {
    python -c "import fastapi, uvicorn, streamlit, yfinance, numpy" | Out-Null
    Write-Host "[OK] Dependencies verified" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Missing packages detected. Installing requirements-local.txt ..." -ForegroundColor Yellow
    python -m pip install -r requirements-local.txt
}

Write-Host "[START] Launching API + Console ..." -ForegroundColor Yellow
python run.py start
