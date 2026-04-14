# Data Flow

This document describes how data flows through the system.

## Overview

Data flows from external sources through the data layer, gets processed and stored, then flows to analysis engines, research, and execution layers.

## Data Categories

| Category | Examples | Frequency | Storage |
|----------|----------|-----------|---------|
| Market Data | Bars, Ticks, Order Book | Real-time | Parquet + Redis |
| Reference Data | Symbols, Exchange info | Daily | PostgreSQL |
| Alternative Data | News, Sentiment | As available | PostgreSQL |
| Macro Data | Economic events, Fed speakers | As available | PostgreSQL |
| Fundamental | Financial statements | Quarterly | PostgreSQL |

## Data Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                       EXTERNAL SOURCES                            │
│  Exchanges / APIs / Feeds / Files                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA INGESTION LAYER                        │
│                core/data/loaders/ (Providers)                    │
│                                                                     │
│  • Exchange connectors                                            │
│  • API clients (Yahoo, Polygon, Alpaca, etc.)                     │
│  • File parsers (CSV, Parquet, HDF5)                              │
│  • WebSocket streams                                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA NORMALIZATION LAYER                     │
│               core/data/processors/ (Normalizers)                │
│                                                                     │
│  • Schema validation (Pydantic)                                   │
│  • Timezone normalization                                         │
│  • Symbol standardization                                         │
│  • Data quality checks                                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌───────────────────┐   ┌───────────────────┐
        │   HOT STORAGE     │   │   COLD STORAGE   │
        │   (Redis Cache)   │   │   (Parquet)      │
        │                   │   │   (PostgreSQL)   │
        └───────────────────┘   └───────────────────┘
                    │                       │
                    └───────────┬───────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        CONSUMERS                                  │
│                                                                     │
│  • core/analysis/ (Real-time engines)                             │
│  • core/research/ (Qlib for backtesting)                          │
│  • core/execution/ (Execution layer)                               │
│  • apps/dashboard/ (UI display)                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Data Schemas

All data uses schema-defined formats from `core/schemas/`:

### MarketBar
```python
MarketBar(
    symbol="AAPL",
    timeframe=TimeFrame.M5,
    timestamp=datetime(2024, 1, 15, 14, 30),
    open=185.50,
    high=186.00,
    low=185.25,
    close=185.75,
    volume=150000,
)
```

### MarketTick
```python
MarketTick(
    symbol="AAPL",
    timestamp=datetime(2024, 1, 15, 14, 30, 5),
    price=185.76,
    size=100,
    side=Side.BUY,
    bid=185.75,
    ask=185.77,
)
```

### OrderBookSnapshot
```python
OrderBookSnapshot(
    symbol="AAPL",
    timestamp=datetime(2024, 1, 15, 14, 30),
    bids=[(185.75, 500), (185.74, 300), ...],
    asks=[(185.77, 400), (185.78, 250), ...],
    spread=0.02,
    mid_price=185.76,
    imbalance=0.15,  # Positive = buy pressure
)
```

## Data Providers

### Built-in Providers

| Provider | Type | Symbols | Frequency |
|----------|------|---------|-----------|
| yfinance | Free API | US stocks, ETFs | EOD + intraday |
| polygon | Paid API | US markets | Real-time |
| alpaca | Broker API | US markets | Real-time |
| binance | Exchange API | Crypto | Real-time |
| csv | File | Any | Historical |
| parquet | File | Any | Historical |

### Provider Configuration

```yaml
data:
  providers:
    - name: yfinance
      enabled: true
      rate_limit: 100  # req/min
      
    - name: polygon
      enabled: true
      api_key: ${POLYGON_API_KEY}
      
    - name: csv
      enabled: true
      path: "./data/historical"
```

## Data Storage

### Hot Storage (Redis)

Used for real-time data caching:

```
# Recent bars
bars:{symbol}:{timeframe}:{date} → [Bar, Bar, ...]

# Order book snapshots
obook:{symbol} → OrderBookSnapshot (JSON)

# Latest prices
price:{symbol} → float
```

### Cold Storage (Parquet)

Used for historical data:

```
data/
├── bars/
│   ├── symbol=AAPL/
│   │   ├── timeframe=5m/
│   │   │   ├── 2024-01.parquet
│   │   │   ├── 2024-02.parquet
│   │   │   └── ...
│   │   └── timeframe=1h/
│   └── symbol=MSFT/
├── ticks/
│   └── ...
└── options/
    └── ...
```

### Reference Data (PostgreSQL)

```sql
-- Symbols
CREATE TABLE symbols (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    exchange TEXT,
    currency TEXT,
    tick_size REAL,
    lot_size INTEGER,
    timezone TEXT,
    is_active BOOLEAN,
);

-- Corporate actions
CREATE TABLE corporate_actions (
    id SERIAL PRIMARY KEY,
    symbol TEXT,
    action_type TEXT,  -- dividend, split, spin-off
    effective_date DATE,
    details JSONB,
);
```

## Data Quality

### Validation Rules

```python
from ai_trading_tool.data import DataValidator

validator = DataValidator()

# Validate bar data
issues = validator.validate_bar(bar)

if issues:
    # Log quality issue
    logger.warning("data_quality_issue", 
        symbol=bar.symbol,
        issues=issues)
```

### Common Issues

| Issue | Detection | Action |
|-------|-----------|--------|
| Missing bars | Gap in timestamps | Backfill or mark as missing |
| Stale data | Timestamp > threshold | Alert, mark as stale |
| Price spike | % change > threshold | Flag for review |
| Zero volume | Volume = 0 on active day | Flag for review |
| Out-of-order | Timestamp decreases | Sort and log |

## Backfill Strategy

```python
from ai_trading_tool.data import BackfillManager

manager = BackfillManager()

# Backfill missing data
manager.backfill(
    symbols=["AAPL", "MSFT"],
    start_date="2020-01-01",
    end_date="2024-01-01",
    timeframe="5m",
    provider="yfinance",
)

# Check fill rate
stats = manager.get_stats()
print(f"Fill rate: {stats.fill_rate}")
```

## Real-time Data Flow

```
WebSocket Stream
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WebSocket Client                               │
│  core/data/loaders/websocket_client.py                           │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Message Normalizer                            │
│  core/data/processors/normalizer.py                              │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─────────────────────────────────────────────────────────────┐
    │                                                             │
    ▼                                                             ▼
┌───────────────────────────┐           ┌───────────────────────────┐
│      Redis Cache          │           │     Analysis Engines      │
│  (Latest bar, book)       │           │  (OrderFlow, Technical)  │
└───────────────────────────┘           └───────────────────────────┘
```

## Historical Data Flow

```
CSV/Parquet Files
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CSV/Parquet Loader                            │
│  core/data/loaders/file_loader.py                               │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Schema Validator                              │
│  core/data/processors/validator.py                               │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Parquet Writer                                │
│  core/data/stores/parquet_store.py                               │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Qlib Dataset                                  │
│  core/research/qlib_integration.py                               │
└─────────────────────────────────────────────────────────────────┘
```
