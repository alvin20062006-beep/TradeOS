# TradeOS

TradeOS is a local AI trading operating console backed by the Phase 1-10 Python/FastAPI core. The default product experience is a desktop shell: users open TradeOS, the backend starts automatically, and the console appears in an embedded window.

![TradeOS Product Home](docs/assets/console-home.png)

## Default Start

```powershell
.\start.ps1
```

or:

```powershell
python run.py start
```

The user should not need to understand API ports, localhost, frontend/backend split, bridge processes, or workers.

## Product Surfaces

| Surface | Role |
|---|---|
| TradeOS desktop shell | Default local product entry |
| `/console/` | FastAPI-mounted web console used inside the shell |
| Data Sources | Configure/test provider profiles |
| Pipeline | Run six-module analysis and full TradeOS loop |
| Diagnostics / Advanced API | Advanced raw API console |
| `apps/console/` | Legacy Streamlit fallback only |

## Entry Matrix

| Entry Type | Command / Path | Audience | Notes |
|---|---|---|---|
| Product entry | `python run.py start` or `.\start.ps1` | End users | Opens the TradeOS desktop shell and embedded `/console/` surface. |
| Developer API | `python run.py api` | Developers | Starts FastAPI only. |
| Developer console | `python run.py console` | Developers | Opens `/console/` in a browser for development fallback. |
| Legacy fallback | `python -m apps.run_console` or `apps/console/` | Legacy only | Retained for fallback and migration, not for default product use. |
| Advanced diagnostics | `/console/?view=diagnostics` | Advanced users | Raw API templates, JSON requests, response history, curl copy. |
| Optional research | `pip install -e ".[research]"` | Research workflows | Enables qlib/optimizer-style extras without changing the default product runtime. |

## Core Loop

```text
Data Sources
-> Six Modules
-> Arbitration
-> Risk
-> Execution Simulation
-> Audit
-> Feedback
-> Strategy Pool
-> Re-enter Arbitration
```

The default data profile exposes real Yahoo market/fundamental/news data, FRED macro data, explicit OrderFlow/Sentiment proxies, and local simulation execution. Placeholder providers are visible as PLACEHOLDER and never report connection success.

## Developer Commands

```powershell
python run.py desktop-smoke
python run.py api
python run.py console
python -m apps.run_console
python -m pytest -q
python -m pytest -m release -q
```

`console` opens `/console/` in a browser for development fallback. It is not the default product entry.

## Install Local Dependencies

```powershell
python -m pip install -r requirements-local.txt
```

## Optional Research Dependencies

TradeOS ships with a product-first dependency policy:

- Default runtime: `requirements-local.txt`
- Full local verification: `python -m pytest -q`
- Optional research extras: `pip install -e ".[research]"`

If `qlib`, optimizer, or other research-only extras are not installed, their tests must skip cleanly instead of failing collection or turning the default full pytest run red.

## Documentation

- [Local Deployment](docs/LOCAL_DEPLOYMENT.md)
- [Console](apps/CONSOLE.md)
- [API](apps/API.md)
- [Phase 11 Deployment](docs/architecture/phase11_deployment_guide.md)
