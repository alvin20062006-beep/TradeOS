# Delivery Report

## Delivered Product Shape

- Default local entry: TradeOS desktop shell.
- Default local console: `/console/` served by the embedded FastAPI backend.
- Advanced API access: Diagnostics / Advanced API.
- Legacy fallback: `apps/console/`.

## Unified Entry Matrix

| Entry Type | Command / Path | Notes |
|---|---|---|
| Product entry | `python run.py start` | End-user desktop shell |
| Desktop smoke | `python run.py desktop-smoke` | Startup/shutdown validation |
| API only | `python run.py api` | Developer runtime |
| Browser console | `python run.py console` | Developer fallback |
| Legacy fallback | `apps/console/` | Not default |

## Validation Commands

```powershell
python run.py desktop-smoke
python -m pytest --collect-only -q
python -m pytest -m release -q
```
