# TradeOS

TradeOS is a local AI trading operating console with a desktop shell, a FastAPI-backed product console, real provider wiring, six-module analysis, arbitration, risk planning, simulation execution, audit, and feedback.

![TradeOS Product Home](TradeOS/docs/assets/console-home.png)

## Product Highlights

- Desktop-first local product entry
- FastAPI-mounted bilingual console at `/console/`
- Data Sources, Pipeline, Arbitration, Strategy Pool, Audit, Feedback, and Diagnostics
- Real Yahoo/FRED-backed product flow with explicit proxy boundaries
- Simulation execution, append-only audit, and feedback loop

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

- Default entry: TradeOS desktop shell
- Default local console: `/console/`, opened inside the desktop shell
- Legacy fallback: `TradeOS/apps/console/`
- Advanced raw API access: Diagnostics / Advanced API
- Users should not need to understand localhost, API, frontend/backend, bridges, or workers

## Entry Matrix

| Entry Type | Command / Path | Notes |
|---|---|---|
| Product entry | `python run.py start` or `.\start.ps1` | Desktop shell with embedded `/console/` |
| Developer API | `python run.py api` | FastAPI only |
| Developer console | `python run.py console` | Browser fallback for `/console/` |
| Legacy fallback | `TradeOS/apps/console/` | Old Streamlit implementation |
| Advanced diagnostics | `/console/?view=diagnostics` | Raw API templates and troubleshooting |
| Optional research extras | `pip install -e ".[research]"` | Research-only dependencies and tests |

See `TradeOS/README.md` for developer commands, validation, and local deployment details.
