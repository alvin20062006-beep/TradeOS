# TradeOS Local Deployment

## Default Product Start

```powershell
.\start.ps1
```

or:

```bat
start.bat
```

Both launch the TradeOS desktop shell. Users see one TradeOS window, not a browser address bar, and do not need to understand API, localhost, frontend, backend, bridge, or worker concepts.

## Python Entry

```powershell
python run.py start
```

`start` is the desktop shell entry. It starts embedded FastAPI, opens `/console/` inside pywebview, and stops the backend when the window closes.

## Developer Commands

```powershell
python run.py desktop-smoke  # backend start/stop smoke without GUI
python run.py api            # API only
python run.py console        # developer browser fallback for /console/
python -m apps.run_console   # legacy browser launcher for /console/
```

These are development tools, not the default product flow.

## Runtime Dependencies

Install local runtime dependencies with:

```powershell
python -m pip install -r requirements-local.txt
```

Required product dependencies include FastAPI, uvicorn, pywebview, pandas, numpy, yfinance, and requests.

## Legacy Fallback

`apps/console/` is the old Streamlit fallback and is no longer the default local product console.

## Release Gate

```powershell
python -m pytest --collect-only -q
python -m pytest -m release -q
python run.py desktop-smoke
```

Full pytest may include optional research/legacy failures unless those dependencies and compatibility fixes are installed. The release gate is the product shipping boundary.

