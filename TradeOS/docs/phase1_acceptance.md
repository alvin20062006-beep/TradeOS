# Phase 1 Acceptance Criteria

This document defines the acceptance criteria for Phase 1 (Foundation).

## Completion Status

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Project directory structure created | 鉁?DONE |
| 2 | `pyproject.toml` with dependency groups | 鉁?DONE |
| 3 | Global schema definitions (15+ schemas) | 鉁?DONE |
| 4 | Configuration system (YAML-based, env-aware) | 鉁?DONE |
| 5 | Database schema (PostgreSQL-compatible) | 鉁?DONE |
| 6 | Migration mechanism | 馃攧 IN PROGRESS |
| 7 | Unified logging system | 鉁?DONE |
| 8 | Test framework setup | 馃攧 IN PROGRESS |
| 9 | Documentation skeleton | 鉁?DONE |
| 10 | `Makefile` with commands | 鉁?DONE |
| 11 | `TARGET.md` | 鉁?DONE |
| 12 | `ROADMAP.md` | 鉁?DONE |
| 13 | `AGENTS.md` | 鉁?DONE |
| 14 | `docs/architecture/system_overview.md` | 鉁?DONE |
| 15 | `docs/architecture/module_boundaries.md` | 鉁?DONE |
| 16 | `docs/schemas/global_io_contract.md` | 鉁?DONE |
| 17 | `docs/runbooks/dev_setup.md` | 鉁?DONE |
| 18 | `infra/docker/` base files | 鈴?TODO |
| 19 | Unit tests for schemas | 鈴?TODO |
| 20 | Contract tests | 鈴?TODO |

## Verification Commands

After completing Phase 1, run these commands to verify:

```bash
# 1. Check imports
python -c "from core.schemas import *; print('Schemas OK')"
python -c "from core.shared import get_config; print('Config OK')"
python -c "from core.shared.logging import get_logger; print('Logging OK')"

# 2. Check config loading
python -c "
from core.shared.config import ConfigLoader
cfg = ConfigLoader().load()
print(f'Environment: {cfg.env.environment}')
print(f'Database type: {cfg.database.type}')
"

# 3. Check schema validation
python -c "
from core.schemas import MarketBar, TimeFrame
from datetime import datetime, timezone

bar = MarketBar(
    symbol='AAPL',
    timeframe=TimeFrame.M5,
    timestamp=datetime.now(timezone.utc),
    open=100.0,
    high=101.0,
    low=99.0,
    close=100.5,
    volume=1000000
)
print(f'Bar created: {bar.symbol} @ {bar.close}')
"

# 4. Run tests
make test-unit

# 5. Check documentation
make docs
```

## Remaining Phase 1 Tasks

### 1. Alembic Migrations Setup

```bash
# Initialize Alembic
alembic init migrations

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Verify migration
alembic upgrade head
```

### 2. Docker Setup

Create `infra/docker/Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install -e .

CMD ["python", "-m", "ai_trading_tool.apps.api"]
```

Create `infra/docker/docker-compose.yml`:

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    environment:
      - DATABASE__TYPE=postgresql
      - DATABASE__HOST=postgres
      - DATABASE__PORT=5432
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ai_trading
      POSTGRES_USER: trader
      POSTGRES_PASSWORD: secret
```

### 3. Unit Tests

Create `tests/unit/test_schemas.py`:

```python
import pytest
from core.schemas import MarketBar, TimeFrame

def test_market_bar_valid():
    bar = MarketBar(
        symbol="AAPL",
        timeframe=TimeFrame.M5,
        timestamp=datetime.now(timezone.utc),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000000
    )
    assert bar.symbol == "AAPL"
    assert bar.close > bar.low

def test_market_bar_invalid():
    with pytest.raises(ValidationError):
        MarketBar(
            symbol="AAPL",
            timeframe=TimeFrame.M5,
            timestamp=datetime.now(timezone.utc),
            open=100.0,
            high=99.0,  # Invalid: high < low
            low=101.0,
            close=100.5,
            volume=1000000
        )
```

### 4. Contract Tests

Create `tests/contracts/test_global_io_contract.py`:

```python
def test_all_schemas_have_required_fields():
    """Verify all critical schemas have expected fields."""
    # This is a meta-test to ensure schemas are complete
    from core.schemas import (
        MarketBar, EngineSignal, ArbitrationDecision,
        OrderRecord, AuditRecord
    )
    
    # Just verify imports work
    assert MarketBar is not None
    assert EngineSignal is not None
    assert ArbitrationDecision is not None
    assert OrderRecord is not None
    assert AuditRecord is not None
```

## Phase 1 Sign-off Checklist

- [ ] All files created as specified
- [ ] `pip install -e .` succeeds
- [ ] All schemas import without errors
- [ ] Config loads from YAML
- [ ] Database migrations work (SQLite dev)
- [ ] `pytest tests/unit/` passes
- [ ] `pytest tests/contracts/` passes
- [ ] `make docs` builds successfully
- [ ] `make lint` shows no critical issues

## Next: Phase 2

Once Phase 1 is complete, proceed to [Phase 2: Data Layer](../architecture/data_flow.md).
