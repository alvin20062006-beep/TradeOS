# TradeOS Local Product Workspace

The active project is in `TradeOS/`.

## Default Start

```powershell
cd TradeOS
.\start.ps1
```

or:

```powershell
cd TradeOS
python run.py start
```

This launches the TradeOS desktop shell, starts the embedded FastAPI backend, opens the console inside an app window, and shuts the backend down when the window closes.

## Product Contract

- Default entry: TradeOS desktop shell.
- Default local console: `/console/`, opened inside the desktop shell.
- Legacy fallback: `TradeOS/apps/console/`.
- Advanced raw API access: Diagnostics / Advanced API page.
- Users should not need to understand localhost, API, frontend/backend, bridges, or workers.

See `TradeOS/README.md` for developer commands and validation.

