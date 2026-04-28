# Consolidation Report

Current product entry has been consolidated to the TradeOS desktop shell.

## Current Entries

- Default: `python run.py start`
- Desktop smoke: `python run.py desktop-smoke`
- Developer API: `python run.py api`
- Developer browser fallback: `python run.py console`
- Legacy fallback only: `apps/console/`

## Unified Entry Matrix

| Entry Type | Command / Path | Status |
|---|---|---|
| Product entry | `python run.py start` | Default |
| Desktop smoke | `python run.py desktop-smoke` | Validation |
| Developer API | `python run.py api` | Supported |
| Developer browser console | `python run.py console` | Supported |
| Legacy fallback | `apps/console/` | Legacy only |

## Current Product Console

The product console is the FastAPI-mounted `/console/` surface. It includes Dashboard, Data Sources, Pipeline, Arbitration, Strategy Pool, Audit, Feedback, and Diagnostics / Advanced API.

Old Streamlit console references are legacy only and must not be used as the default product description.
