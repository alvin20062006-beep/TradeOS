# Frontend / Console Alignment Report

## Current Product Surface

TradeOS now uses the FastAPI-mounted web console at `/console/`, opened by the desktop shell. The normal user does not need to see localhost, API Base, or browser tabs.

## Product UX Contract

- Product entry: TradeOS desktop shell.
- Default console: `/console/`.
- Advanced engineering surface: Diagnostics / Advanced API.
- Legacy surface: `apps/console/` fallback only.
- Product-facing pages use a unified bilingual style, shared typography scale, shared spacing scale, and one consistent status/toast language model.

## Completed Console Pages

- Dashboard
- Data Sources
- Pipeline
- Arbitration
- Strategy Pool
- Audit
- Feedback
- Diagnostics / Advanced API

## Real API Alignment

- Data Sources uses `/api/v1/data-sources/*`.
- Pipeline uses `/api/v1/analysis/run-live`, `/api/v1/pipeline/run-live`, and `/api/v1/data-sources/test`.
- Six-module cards render backend `coverage_status`, provider, adapter, input data, row count, latest timestamp, confidence, notes, and raw response.
- Diagnostics sends real requests only; no fake success path exists.

## Legacy Status

The old Streamlit console under `apps/console/` is legacy fallback only and is not the default product console.
