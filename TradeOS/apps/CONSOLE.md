# TradeOS Console

The default user-facing console is the FastAPI-served web console mounted at `/console/` and opened inside the TradeOS desktop shell.

## Default Entry

```powershell
python run.py start
```

This starts the desktop shell, starts the embedded FastAPI backend, opens the in-app window, and stops the backend when the window closes.

## Developer Fallback

```powershell
python run.py console
```

This opens the same `/console/` surface in a browser for development diagnostics only.

## Pages

- Dashboard: health, version, system status, module status.
- Data Sources: provider profiles and connection tests.
- Pipeline: target-first six-module analysis and full TradeOS loop.
- Arbitration: single-symbol and portfolio arbitration.
- Strategy Pool: proposal and bridge into arbitration.
- Audit: append-only read-only decision, risk, feedback, and auth views.
- Feedback: feedback scan task submit/status/results.
- Diagnostics / Advanced API: raw API templates, JSON body, response, history, and curl copy.

## Entry Matrix

| Entry Type | Command / Path | Notes |
|---|---|---|
| Product entry | `python run.py start` | Desktop shell + embedded `/console/` |
| Developer browser console | `python run.py console` | Same console in a browser |
| Legacy fallback | `apps/console/` | Old Streamlit fallback |
| Advanced diagnostics | `/console/?view=diagnostics` | Raw API tooling |

## Legacy

`apps/console/` is the old Streamlit fallback. It is not the default Console and should not be described as the product entry.
