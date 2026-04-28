# Phase 11 Productization Plan

Phase 11 productization is now centered on the TradeOS desktop shell.

## Product Shape

```text
TradeOS desktop shell
  -> embedded FastAPI backend
  -> /console/ product console
  -> Data Sources / Pipeline / Diagnostics / core workflow pages
```

## Naming

- Default entry: TradeOS.
- Default local console: `/console/`.
- Advanced API page: Diagnostics / Advanced API.
- Legacy fallback: `apps/console/`.

## User Experience Goal

The normal user should not need to understand API, localhost, frontend/backend, bridge, worker, or ports. Development commands may expose these details, but product documentation should not make them the default path.

## Release Checks

```powershell
python run.py desktop-smoke
python -m pytest --collect-only -q
python -m pytest -m release -q
```

