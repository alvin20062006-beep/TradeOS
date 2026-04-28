# TradeOS API Reference

Default product users should start TradeOS from the desktop shell and do not need to know API paths or localhost ports. This document is for developers and the Diagnostics / Advanced API page.

## Runtime Surfaces

| Surface | Status | Notes |
|---|---|---|
| TradeOS desktop shell | Default | Starts embedded FastAPI and opens the in-app console window. |
| `/console/` | Developer/local console | Served by FastAPI; used inside the desktop shell. |
| Diagnostics / Advanced API | Advanced | Raw JSON templates, response viewer, curl copy, and request history. |
| `apps/console/` | Legacy fallback | Old Streamlit console; not the default product entry. |

## Core Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/version` | Version |
| GET | `/system/status` | Runtime status |
| GET | `/system/modules` | Phase 1-10 module status |
| GET | `/api/v1/data-sources/profiles` | List local data source profiles |
| POST | `/api/v1/data-sources/profiles` | Save a local data source profile |
| POST | `/api/v1/data-sources/test` | Test one provider; placeholder providers never report success |
| GET | `/api/v1/data-sources/capabilities` | REAL / PROXY / PLACEHOLDER / UNAVAILABLE capability map |
| POST | `/api/v1/analysis/run-live` | Run six-module live analysis |
| POST | `/api/v1/pipeline/run-live` | Run full TradeOS live loop |
| POST | `/api/v1/pipeline/run-full` | Legacy DTO orchestration path |
| POST | `/api/v1/arbitration/run` | Single-symbol arbitration |
| POST | `/api/v1/arbitration/run-portfolio` | Strategy Pool to Arbitration bridge |
| POST | `/api/v1/risk/calculate` | Risk calculation |
| POST | `/api/v1/strategy-pool/propose` | Strategy Pool proposal |
| GET | `/api/v1/audit/decisions` | Append-only decision audit |
| GET | `/api/v1/audit/risk` | Append-only risk audit |
| GET | `/api/v1/audit/feedback` | Feedback audit |
| POST | `/api/v1/audit/feedback/tasks` | Submit feedback scan task |
| GET | `/api/v1/audit/feedback/tasks/{task_id}` | Read feedback task result |

## Live Pipeline Request

```json
{
  "symbol": "AAPL",
  "market_type": "equity",
  "timeframe": "1d",
  "lookback": 90,
  "profile_id": "default-live",
  "news_limit": 6
}
```

The response includes Data Summary, Six Modules, Arbitration Decision, Risk Plan, Execution Simulation, Audit Records, and Feedback Suggestions. Module cards expose `coverage_status` so proxy and placeholder boundaries are visible to the frontend.

