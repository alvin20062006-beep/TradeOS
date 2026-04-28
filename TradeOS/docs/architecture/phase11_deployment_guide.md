# Phase 11 Deployment Guide

## Product Entry

The default local product entry is:

```powershell
python run.py start
```

or the platform launcher:

```powershell
.\start.ps1
```

This opens the TradeOS desktop shell. The shell owns backend startup, health checks, the embedded `/console/` window, and backend shutdown.

## Architecture

```text
TradeOS desktop shell
  -> embedded FastAPI runtime
  -> /console/ web console
  -> /api/v1/* backend capabilities
```

The user-facing product should not require knowledge of browser ports, API base URLs, frontend/backend split, bridges, or workers.

## Developer Commands

```powershell
python run.py desktop-smoke
python run.py api
python run.py console
python -m apps.run_console
```

`console` and `apps.run_console` are development/browser fallbacks for the FastAPI `/console/` surface.

## Entry Matrix

| Entry Type | Command / Path | Contract |
|---|---|---|
| Product entry | `python run.py start` | Default end-user path |
| Desktop smoke | `python run.py desktop-smoke` | Backend startup/shutdown validation |
| Developer API | `python run.py api` | FastAPI only |
| Developer browser console | `python run.py console` | Development fallback |
| Legacy fallback | `apps/console/` | Legacy only |
| Advanced diagnostics | `/console/?view=diagnostics` | Advanced API and troubleshooting |

## Legacy

`apps/console/` is the old Streamlit implementation. It is retained as fallback only and must not be documented as the default console.

## Validation

```powershell
python -m pytest --collect-only -q
python -m pytest -m release -q
python run.py desktop-smoke
```
