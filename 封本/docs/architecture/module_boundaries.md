# Module Boundaries

This document defines the clear boundaries between modules to prevent responsibility drift.

## Top-Level Directory Structure

```
ai-trading-tool/
├── apps/                    # Orchestrators, API, Worker, CLI, Dashboard
├── core/                    # Core business logic (the platform)
│   ├── shared/              # Shared utilities (config, logging, enums, utils)
│   ├── schemas/             # Global I/O schemas
│   ├── data/               # Data ingestion, storage, retrieval
│   ├── research/            # Qlib integration, research workflows
│   ├── analysis/            # Six analysis engines
│   ├── arbitration/         # Decision aggregation
│   ├── execution/           # NautilusTrader wrapper, order management
│   ├── risk/                # Risk management
│   └── audit/               # Audit logging, feedback闭环
├── infra/                   # Infrastructure (DB, cache, queue, docker)
├── tests/                   # Test suite
├── docs/                    # Documentation
├── scripts/                 # Operational scripts
└── migrations/              # Database migrations
```

---

## Module: `apps/`

**Responsibility**: User-facing entry points and orchestration.

**What it contains**:
- `orchestrator.py` - Main orchestration logic
- `api.py` - REST/WebSocket API
- `worker.py` - Celery worker for async tasks
- `cli.py` - Command-line interface
- `dashboard.py` - Monitoring dashboard

**What it does NOT contain**:
- Business logic (goes in `core/`)
- Data processing (goes in `core/data/`)
- Strategy implementations (goes in `core/analysis/`)

**Interfaces**:
- **Inputs**: User commands, API requests, scheduled triggers
- **Outputs**: Calls to `core/arbitration`, `core/execution`, `core/audit`

---

## Module: `core/shared/`

**Responsibility**: Shared utilities used by all modules.

**Sub-modules**:
- `config/` - Configuration loading, schema validation
- `logging/` - Unified structured logging
- `enums/` - Shared enumerations
- `utils/` - Common utility functions
- `time/` - Time zone handling

**Rules**:
- No business logic here
- No imports from `analysis/`, `arbitration/`, `execution/`, `risk/`, `audit/`
- Only base Python + external libraries

---

## Module: `core/schemas/`

**Responsibility**: Unified I/O schemas for all modules.

**What it defines**:
- All Pydantic models for data exchange
- All Enum types
- Type aliases

**Critical Rule**: 
> **All modules MUST use these schemas. No ad-hoc dictionaries.**

**Schema Categories**:
1. Market data schemas (MarketBar, MarketTick, OrderBookSnapshot, TradePrint)
2. External data schemas (FundamentalsSnapshot, MacroEvent, NewsEvent, SentimentEvent)
3. Signal schemas (EngineSignal, ChanSignal, TechnicalSignal, OrderFlowSignal, MacroSignal)
4. Decision schemas (ArbitrationDecision)
5. Execution schemas (ExecutionIntent, OrderRecord, FillRecord)
6. Risk schemas (RiskEvent, RiskLimits)
7. Audit schemas (AuditRecord)
8. Registry schemas (ModelMetadata, ExperimentRecord)

---

## Module: `core/data/`

**Responsibility**: Data ingestion, storage, retrieval.

**What it does**:
- Connects to data providers (exchanges, APIs)
- Normalizes data into standard schemas
- Stores data in Parquet/PostgreSQL
- Caches data in Redis
- Validates data quality

**What it does NOT do**:
- Technical analysis (goes to `core/analysis/technical/`)
- Feature engineering (goes to `core/research/`)
- Sentiment analysis (goes to `core/analysis/sentiment/`)

**Interfaces**:
- **Inputs**: Data provider APIs, files
- **Outputs**: Normalized market data in schema format

---

## Module: `core/research/`

**Responsibility**: Qlib integration and research workflows.

**What it does**:
- Wraps Qlib for feature engineering
- Manages dataset versioning
- Trains and evaluates models
- Runs backtests
- Performs walk-forward analysis
- Registers experiments and models

**What it does NOT do**:
- Real-time analysis (that's `core/analysis/`)
- Execution (that's `core/execution/`)
- Risk management (that's `core/risk/`)

**Interfaces**:
- **Inputs**: Clean market data from `core/data/`
- **Outputs**: 
  - Alpha signals to `core/arbitration/`
  - Model artifacts to `infra/`
  - Experiment records to `core/audit/`

---

## Module: `core/analysis/`

**Responsibility**: Real-time analysis engines.

**Sub-modules**:

### `analysis/chan/`
- 分型 (Fractals)
- 笔 (笔 - strokes)
- 线段 (Segments)
- 中枢 (Zhongshu - centers)
- 背驰 (Divergence)
- 一买/二买/三买 (Buy points 1/2/3)
- 一卖/二卖/三卖 (Sell points 1/2/3)
- Multi-timeframe linkage

### `analysis/technical/`
- Trend analysis (MA, ADX, channels)
- Momentum indicators (MACD, RSI, Stochastic, KDJ, CCI)
- Volatility indicators (ATR, Bollinger Bands)
- Chart patterns (head-shoulders, triangles, etc.)
- Candlestick patterns (engulfing, doji, pin bar, etc.)
- Support/resistance detection

### `analysis/orderflow/`
- Order book imbalance
- Bid/ask pressure
- Delta/CVD tracking
- Absorption detection
- Liquidity sweep detection
- Execution quality forecasting

### `analysis/sentiment/`
- News sentiment analysis
- Social media sentiment
- Forum sentiment
- Sector heat mapping
- Multi-source aggregation

### `analysis/macro/`
- Macro calendar ingestion
- Event impact scoring
- Regime detection
- Asset impact mapping
- Central bank policy tracking

### `analysis/fundamental/`
- Financial metrics retrieval
- Valuation analysis
- Earnings quality scoring

**What it does NOT do**:
- Combine signals (that's `core/arbitration/`)
- Send orders (that's `core/execution/`)

**Interfaces**:
- **Inputs**: Market data from `core/data/`
- **Outputs**: EngineSignal for each engine type

---

## Module: `core/arbitration/`

**Responsibility**: Signal aggregation and final decision.

**What it does**:
- Collects signals from all analysis engines
- Weights signals according to configuration
- Calculates consensus score
- Applies regime-based rules
- Produces final ArbitrationDecision

**What it does NOT do**:
- Execute orders (delegates to `core/execution/`)
- Manage risk (delegates to `core/risk/`)

**Interfaces**:
- **Inputs**: EngineSignal from all analysis engines + research signals
- **Outputs**: ArbitrationDecision to `core/execution/`

---

## Module: `core/execution/`

**Responsibility**: Order execution management.

**What it does**:
- Wraps NautilusTrader
- Translates ArbitrationDecision → orders
- Manages order lifecycle
- Handles execution algorithms (TWAP, VWAP, POV, Iceberg)
- Tracks fills and position updates

**What it does NOT do**:
- Analyze markets (that's `core/analysis/`)
- Arbitrate decisions (that's `core/arbitration/`)

**Interfaces**:
- **Inputs**: ArbitrationDecision + RiskLimits
- **Outputs**: Orders to NautilusTrader, execution records to `core/audit/`

---

## Module: `core/risk/`

**Responsibility**: Risk management and position sizing.

**What it does**:
- Enforces position limits
- Calculates position sizes (volatility targeting, Kelly, etc.)
- Monitors drawdown
- Checks correlation
- **Square-root impact estimation** (NOT directional prediction)
- Generates risk alerts

**Critical Rule**:
> Square-root formula is used ONLY for: impact estimation, position caps, order splitting, participation rate. NEVER for directional signals.

**What it does NOT do**:
- Analyze markets (that's `core/analysis/`)
- Send orders (that's `core/execution/`)

**Interfaces**:
- **Inputs**: ArbitrationDecision, current portfolio state
- **Outputs**: RiskLimits, RiskEvent (if breached)

---

## Module: `core/audit/`

**Responsibility**: Audit logging and feedback闭环.

**What it does**:
- Logs all decisions to database
- Logs all executions
- Logs all risk events
- Logs all configuration changes
- Collects live feedback
- Detects strategy degradation

**What it does NOT do**:
- Business logic (that's other core modules)
- Execution (that's `core/execution/`)

**Interfaces**:
- **Inputs**: Data from all modules
- **Outputs**: Audit records to `infra/db/`

---

## Module: `infra/`

**Responsibility**: Infrastructure components.

**Sub-modules**:
- `db/` - Database schemas, migrations, seeds
- `cache/` - Redis cache configuration
- `queue/` - Celery task queue configuration
- `object_store/` - S3/MinIO configuration
- `docker/` - Docker and docker-compose files

**Rules**:
- Infrastructure configuration only
- No business logic
- No imports from `core/`

---

## Data Flow Between Modules

```
core/data/
    │
    │ (normalized MarketBar, Tick, etc.)
    ▼
core/research/ ←──────────────────────┐
    │                                  │
    │ (alpha signals)                  │
    ▼                                  │
core/analysis/ ───────────────────► core/arbitration/
    │                                  │
    │ (EngineSignal)                   │ (ArbitrationDecision)
    │                                  ▼
    │                            core/risk/
    │                                  │
    │                                  │ (RiskLimits, adjusted decision)
    │                                  ▼
    │                            core/execution/
    │                                  │
    │                                  │ (OrderRecord, FillRecord)
    │                                  ▼
    │                            core/audit/
    │                                  │
    │                                  │ (AuditRecord)
    │                                  ▼
    └──────────────────────────► infra/db/
```

## Dependency Rules

1. `apps/` can import from any `core/` module
2. `core/shared/` can NOT import from any other `core/` module
3. `core/schemas/` can NOT import from any other `core/` module
4. `core/data/` can import from `core/schemas/`, `core/shared/`
5. `core/research/` can import from `core/schemas/`, `core/shared/`, `core/data/`
6. `core/analysis/` can import from `core/schemas/`, `core/shared/`, `core/data/`
7. `core/arbitration/` can import from all `core/analysis/`, `core/schemas/`, `core/shared/`
8. `core/execution/` can import from `core/schemas/`, `core/shared/`, `core/arbitration/`, `core/risk/`
9. `core/risk/` can import from `core/schemas/`, `core/shared/`
10. `core/audit/` can import from all `core/` modules and `infra/`

## Circular Dependency Prevention

Modules must NOT create circular dependencies. If you find yourself needing a circular import:
1. Move shared types to `core/schemas/`
2. Use type hints with quotes: `from __future__ import annotations`
3. Refactor to remove the circular need
