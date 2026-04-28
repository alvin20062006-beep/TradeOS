# Delivery Report

## Delivered Product Shape

- Default local entry: TradeOS desktop shell.
- Default local console: `/console/` served by the embedded FastAPI backend.
- Advanced API access: Diagnostics / Advanced API.
- Legacy fallback: `apps/console/`.

## Validation Commands

```powershell
python run.py desktop-smoke
python -m pytest --collect-only -q
python -m pytest -m release -q
```

