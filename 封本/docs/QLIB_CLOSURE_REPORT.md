# Qlib Closure Report

Date: 2026-04-15  
Scope: `qlib` local runtime closure only

## A. Current Qlib Status Before Repair

### Installation shape before repair

- main machine runtime only had Python `3.14.3`
- `pyqlib` was not installed into the main interpreter
- there was a local source checkout at:
  - `C:\Users\Alvin\Desktop\AI交易TradeOS\qlib`
- temporary usage mode was effectively:
  - source-path import via `PYTHONPATH`
  - no formal wheel install
  - no successful compiled extension build

### Version facts before repair

- current source-imported version: `0.1.dev1`
- test-expected version: `0.9.7`

### Precise failure root cause

The previous failure was not one single issue. It was a stack of compatibility problems:

1. Python version mismatch
   - machine baseline was Python `3.14.3`
   - this was a poor fit for `pyqlib==0.9.7`

2. Windows compiled extension missing
   - `qlib.init()` failed on:
   - `ModuleNotFoundError: No module named 'qlib.data._libs.rolling'`

3. Source-version drift
   - local checkout exposed `0.1.dev1`
   - tests explicitly require `0.9.7`

4. Editable/source install on Windows was not the minimal path
   - local source install attempted to compile Cython extension
   - that path required `Microsoft Visual C++ 14.0+`

### Recommendation decision

Best repair choice:

- do **not** continue forcing `qlib` through Python `3.14`
- do **not** keep using source-path import as the primary runtime
- use a dedicated compatibility environment with:
  - Python `3.11`
  - official `pyqlib==0.9.7` Windows wheel

This was the smallest real-success path because it solved all of the following at once:

- exact version alignment
- compiled extension availability via wheel
- no repeated local C-extension build attempts
- no need to change Phase 1-10 semantics

## B. Repair Actions

### Environment actions performed

1. Installed Python `3.11.9`
2. Created dedicated virtual environment:
   - `C:\Users\Alvin\Desktop\AI交易TradeOS\.venv-qlib311`
3. Installed official `pyqlib==0.9.7`
4. Installed runtime and workflow dependencies needed for real init/tests

### Final qlib environment

- Python executable:
  - `C:\Users\Alvin\Desktop\AI交易TradeOS\.venv-qlib311\Scripts\python.exe`
- qlib package:
  - `pyqlib==0.9.7`
- environment type:
  - dedicated compatibility venv

### Dependencies added in the qlib venv

Core/runtime:

- `pyqlib==0.9.7`
- `numpy`
- `pandas`
- `pyyaml`
- `filelock`
- `redis`
- `dill`
- `fire`
- `ruamel.yaml`
- `python-redis-lock`
- `tqdm`
- `pymongo`
- `loguru`
- `lightgbm`
- `cvxpy`
- `joblib`
- `matplotlib`
- `pyarrow`
- `pydantic-settings`
- `setuptools-scm`

Workflow/test/runtime support:

- `mlflow`
- `pytest`
- transitive packages such as `pluggy`, `python-dateutil`, `sqlalchemy`, `scikit-learn`, `scipy`, `fastapi`, `aiohttp`

### Toolchain decision

- no local C-extension toolchain was required for the successful path
- we avoided relying on `Microsoft Visual C++` by switching to the official `cp311` wheel

## C. Verification Results

### Direct init verification

Command:

```powershell
C:\Users\Alvin\Desktop\AI交易TradeOS\.venv-qlib311\Scripts\python.exe - <<'PY'
import qlib
print(qlib.__version__)
qlib.init(region="us", auto_mount=False)
print("init_ok")
PY
```

Result:

- `qlib.__version__ = 0.9.7`
- `qlib.init()` succeeded

### Workflow import verification

- `from qlib.workflow import R` succeeded

### Test results

#### Qlib-specific tests

- `tests/integration/test_qlib_init.py`
  - result: `13 passed`
- `tests/unit/test_qlib_availability.py`
  - result: `14 passed`
- `tests/unit/test_qlib_config_builder.py`
  - result: `15 passed`
- `tests/integration/test_baseline_workflow.py`
  - result: `21 passed`

#### Related research-layer verification

- `tests/integration/test_backtest_research_pipeline.py`
  - result: `9 passed`

### Non-blocking observations

- `mlflow` emits a future warning about filesystem tracking backend deprecation
- qlib emits a shutdown-time logging message after pytest closes stdout

These did **not** block:

- `qlib.init()`
- qlib workflow usage
- qlib-related test success

## D. Final Environment State

### Main machine runtimes

- main product/live environment:
  - Python `3.14.3`
  - used for API / Console / live data pipeline
- qlib compatibility environment:
  - Python `3.11.9`
  - used for qlib research/runtime verification

### Why dual environment is acceptable here

`qlib` was the only subsystem with a hard interpreter compatibility constraint on this machine.  
Using an isolated compatibility venv avoided:

- breaking the already-working live product environment
- risky source recompilation
- fake “import-only” closure

This is a real runtime closure, not a documentation-only workaround.

## E. Final Conclusion

### Is qlib truly closed on this machine?

Yes.

Closure standard requested by the audit:

- `qlib.init()` real pass: Yes
- related tests real pass: Yes
- import-only fake closure: No, not used

### Does the project now reach “entire project real-data structure sealed”?

Yes, with the machine-level note that:

- product/live path runs in the existing main environment
- qlib research/runtime uses the dedicated compatibility environment `.venv-qlib311`

### Remaining unique blocker

None at the level defined by this closure task.
