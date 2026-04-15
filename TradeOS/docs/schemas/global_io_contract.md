# Global I/O Contract

This document defines the canonical input/output schemas for all modules. All modules MUST use these schemas. No ad-hoc dictionaries.

## Schema Location

All schemas are defined in: `core/schemas/__init__.py`

## Import Pattern

```python
from ai_trading_tool.core.schemas import (
    # Market data
    MarketBar,
    MarketTick,
    OrderBookSnapshot,
    TradePrint,
    
    # External data
    FundamentalsSnapshot,
    MacroEvent,
    NewsEvent,
    SentimentEvent,
    
    # Signals
    EngineSignal,
    ChanSignal,
    TechnicalSignal,
    OrderFlowSignal,
    MacroSignal,
    
    # Decisions
    ArbitrationDecision,
    
    # Execution
    ExecutionIntent,
    OrderRecord,
    FillRecord,
    
    # Risk
    RiskEvent,
    RiskLimits,
    
    # Audit
    AuditRecord,
    
    # Enums
    Direction,
    OrderType,
    Side,
    Regime,
    TimeFrame,
)
```

## Schema Index

### Market Data Schemas

#### MarketBar
**Purpose**: OHLCV bar data
```python
MarketBar(
    symbol: str,
    timeframe: TimeFrame,
    timestamp: datetime,
    open: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    quote_volume: float | None = None,
    trades: int | None = None,
    vwap: float | None = None,
    source: str | None = None,
)
```

#### MarketTick
**Purpose**: Individual trade tick
```python
MarketTick(
    symbol: str,
    timestamp: datetime,
    price: float,
    size: float,
    side: Side | None,
    bid: float | None,
    ask: float | None,
    bid_size: float | None,
    ask_size: float | None,
)
```

#### OrderBookSnapshot
**Purpose**: Full order book state
```python
OrderBookSnapshot(
    symbol: str,
    timestamp: datetime,
    bids: list[tuple[float, float]],  # [(price, size), ...]
    asks: list[tuple[float, float]],
    bid_depth: float,
    ask_depth: float,
    spread: float,
    mid_price: float,
    imbalance: float,  # -1 to 1
)
```

#### TradePrint
**Purpose**: Single exchange trade
```python
TradePrint(
    symbol: str,
    timestamp: datetime,
    price: float,
    size: float,
    side: Side,  # Aggressive side
    trade_id: str | None,
    is_buy_side_taker: bool | None,
)
```

### External Data Schemas

#### FundamentalsSnapshot
**Purpose**: Fundamental data
```python
FundamentalsSnapshot(
    symbol: str,
    timestamp: datetime,
    market_cap: float | None,
    pe_ratio: float | None,
    # ... other financial metrics
)
```

#### MacroEvent
**Purpose**: Economic events
```python
MacroEvent(
    timestamp: datetime,
    event_name: str,
    country: str,
    impact: str,  # high/medium/low
    previous: float | None,
    forecast: float | None,
    actual: float | None,
    affected_assets: list[str],
    is_surprise: bool | None,
)
```

#### NewsEvent
**Purpose**: News headlines
```python
NewsEvent(
    timestamp: datetime,
    title: str,
    source: str,
    url: str | None,
    symbols: list[str],
    sentiment_score: float | None,  # -1 to 1
    sentiment_label: str | None,
)
```

#### SentimentEvent
**Purpose**: Aggregated sentiment
```python
SentimentEvent(
    symbol: str,
    timestamp: datetime,
    news_sentiment: float,  # 0-1
    social_sentiment: float,
    forum_sentiment: float,
    analyst_sentiment: float,
    composite_sentiment: float,
    bullish_ratio: float,
    bearish_ratio: float,
    neutral_ratio: float,
    sources_count: int,
)
```

### Signal Schemas

#### EngineSignal (Base)
**Purpose**: Standard output from any analysis engine
```python
EngineSignal(
    engine_name: str,
    symbol: str,
    timestamp: datetime,
    timeframe: TimeFrame | None,
    direction: Direction,
    confidence: float,  # 0-1
    regime: Regime,
    entry_score: float,  # 0-1
    exit_score: float,
    entry_price: float | None,
    stop_price: float | None,
    target_price: float | None,
    risk_reward_ratio: float | None,
    pattern_type: str | None,
    pattern_name: str | None,
    module_scores: dict[str, float],
    reasoning: str,
    metadata: dict,
)
```

#### ChanSignal (缠论)
**Purpose**: Chan theory signal
```python
ChanSignal(
    # Base EngineSignal fields
    engine_name: str = "chan",
    ...
    
    # Chan-specific
    fractal_level: str | None,
    笔_status: str | None,
    segment_status: str | None,
    zhongshu_status: str | None,
    divergence: str | None,
    purchase_point: int | None,  # 1/2/3
    sell_point: int | None,
    higher_tf_direction: Direction | None,
    lower_tf_direction: Direction | None,
)
```

#### TechnicalSignal
**Purpose**: Classical technical analysis
```python
TechnicalSignal(
    # Base EngineSignal fields
    ...
    
    # Technical-specific
    trend: str | None,
    momentum: str | None,
    volatility_state: str | None,
    chart_pattern: str | None,
    candle_pattern: str | None,
    support_levels: list[float],
    resistance_levels: list[float],
)
```

#### OrderFlowSignal
**Purpose**: Order flow analysis
```python
OrderFlowSignal(
    symbol: str,
    timestamp: datetime,
    timeframe: TimeFrame,
    book_imbalance: float,  # -1 to 1
    bid_pressure: float,
    ask_pressure: float,
    delta: float,
    cum_delta: float,
    absorption_score: float,
    liquidity_sweep: bool,
    expected_slippage: float,
    execution_condition: ExecutionQuality,
    stop_hunt_zones: list[tuple[float, float]],
    metadata: dict,
)
```

#### MacroSignal
**Purpose**: Macro regime signal
```python
MacroSignal(
    timestamp: datetime,
    regime: Regime,
    regime_confidence: float,
    dominant_themes: list[str],
    risk_on: bool,
    equity_bias: str,
    bond_bias: str,
    commodity_bias: str,
    fx_bias: dict[str, str],
    vix_level: float | None,
    move_level: float | None,
    high_impact_events: list[str],
    metadata: dict,
)
```

### Decision Schemas

#### ArbitrationDecision
**Purpose**: Final unified trading decision
```python
ArbitrationDecision(
    decision_id: str,  # UUID
    timestamp: datetime,
    symbol: str,
    direction: Direction,
    confidence: float,
    regime: Regime,
    entry_permission: bool,
    no_trade_reason: str | None,
    max_position_pct: float,
    suggested_quantity: float | None,
    execution_style: OrderType,
    limit_price: float | None,
    stop_price: float | None,
    stop_logic: dict,
    take_profit: float | None,
    engine_signals: dict[str, float],
    consensus_score: float,
    reasoning: str,
    key_factors: list[str],
    version: str = "1.0.0",
    metadata: dict,
)
```

### Execution Schemas

#### ExecutionIntent
**Purpose**: Intent sent to execution layer
```python
ExecutionIntent(
    intent_id: str,
    decision_id: str,
    timestamp: datetime,
    symbol: str,
    direction: Direction,
    quantity: float,
    price_limit: float | None,
    order_type: OrderType,
    time_limit_seconds: int | None,
    participation_rate: float | None,
    algo_params: dict,
    risk_adjusted: bool,
    original_quantity: float | None,
    metadata: dict,
)
```

#### OrderRecord
**Purpose**: Order lifecycle tracking
```python
OrderRecord(
    order_id: str,
    decision_id: str,
    intent_id: str | None,
    symbol: str,
    timestamp: datetime,
    side: Side,
    order_type: OrderType,
    quantity: float,
    price: float | None,
    stop_price: float | None,
    status: OrderStatus,
    submitted_at: datetime | None,
    filled_at: datetime | None,
    cancelled_at: datetime | None,
    filled_quantity: float,
    avg_fill_price: float | None,
    slippage_bps: float | None,
    execution_quality: ExecutionQuality,
    exchange_order_id: str | None,
    exchange: str | None,
    metadata: dict,
)
```

#### FillRecord
**Purpose**: Individual fill
```python
FillRecord(
    fill_id: str,
    order_id: str,
    timestamp: datetime,
    price: float,
    quantity: float,
    side: Side,
    commission: float,
    commission_currency: str,
    is_maker: bool | None,
    liquidity_type: str | None,
    exchange_fill_id: str | None,
    venue: str | None,
)
```

### Risk Schemas

#### RiskEvent
**Purpose**: Risk breach record
```python
RiskEvent(
    event_id: str,
    timestamp: datetime,
    event_type: RiskEventType,
    symbol: str | None,
    description: str,
    triggered_value: float,
    threshold_value: float,
    action_taken: str,
    position_closed: bool,
    order_cancelled: bool,
    decision_id: str | None,
    metadata: dict,
)
```

#### RiskLimits
**Purpose**: Risk limit configuration
```python
RiskLimits(
    max_position_pct: float,
    max_position_absolute: float | None,
    max_positions: int,
    max_loss_pct_per_trade: float,
    max_loss_pct_per_day: float,
    max_drawdown_pct: float,
    max_leverage: float,
    max_sector_exposure_pct: float,
    max_slippage_bps: float,
    max_order_size_pct: float,
    max_correlation: float,
)
```

### Audit Schemas

#### AuditRecord
**Purpose**: Universal audit record
```python
AuditRecord(
    audit_id: str,
    timestamp: datetime,
    record_type: str,
    entity_type: str,
    entity_id: str,
    source: EventSource,
    actor: str,
    action: str,
    before_state: dict | None,
    after_state: dict | None,
    reason: str | None,
    correlation_id: str | None,
    metadata: dict,
    checksum: str | None,
)
```

### Registry Schemas

#### ModelMetadata
**Purpose**: Model version tracking
```python
ModelMetadata(
    model_id: str,
    model_name: str,
    version: str,
    model_type: str,
    created_at: datetime,
    created_by: str,
    training_start: datetime | None,
    training_end: datetime | None,
    training_samples: int,
    metrics: dict[str, float],
    is_active: bool,
    is_production: bool,
    parent_model_id: str | None,
    experiment_id: str | None,
    config: dict,
    artifacts_path: str | None,
    metadata: dict,
)
```

#### ExperimentRecord
**Purpose**: Research experiment tracking
```python
ExperimentRecord(
    experiment_id: str,
    experiment_name: str,
    started_at: datetime,
    completed_at: datetime | None,
    status: str,
    config: dict,
    results: dict,
    metrics: dict[str, float],
    model_ids: list[str],
    dataset_version: str | None,
    metadata: dict,
)
```

## Enum Values

### Direction
- `LONG` - Buy/Long position
- `SHORT` - Sell/Short position
- `FLAT` - No position

### Side
- `BUY` - Buy side
- `SELL` - Sell side

### OrderType
- `MARKET` - Market order
- `LIMIT` - Limit order
- `STOP` - Stop order
- `STOP_LIMIT` - Stop-limit order
- `TWAP` - Time-weighted average price
- `VWAP` - Volume-weighted average price
- `POV` - Percentage of volume
- `ICEBERG` - Iceberg/hidden order
- `ADAPTIVE` - Adaptive to market conditions

### Regime
- `TRENDING_UP` - Uptrend
- `TRENDING_DOWN` - Downtrend
- `RANGING` - Range-bound
- `VOLATILE` - High volatility
- `UNKNOWN` - Undetermined

### TimeFrame
- `S1`, `M1`, `M5`, `M15`, `M30`
- `H1`, `H4`
- `D1`, `W1`, `MN`

## Schema Validation

### Validating Input

```python
from pydantic import ValidationError
from ai_trading_tool.core.schemas import MarketBar, TimeFrame

try:
    bar = MarketBar(
        symbol="AAPL",
        timeframe=TimeFrame.M5,
        timestamp=datetime.now(),
        open=185.50,
        high=185.50,  # Error: high must be >= open
        low=185.00,
        close=185.75,
        volume=150000,
    )
except ValidationError as e:
    print(e)  # Shows validation errors
```

### Serialization

```python
# To JSON
bar_json = bar.model_dump_json()

# From JSON
bar = MarketBar.model_validate_json(bar_json)
```

## No Ad-Hoc Schemas Rule

> **CRITICAL**: All module inputs and outputs MUST use schemas from `core/schemas/`. Do NOT create ad-hoc dictionaries.

### ❌ Forbidden
```python
# Don't do this
def get_signal():
    return {
        "dir": "long",  # No!
        "conf": 0.8,    # No!
    }
```

### ✅ Correct
```python
# Do this
from ai_trading_tool.core.schemas import EngineSignal, Direction

def get_signal() -> EngineSignal:
    return EngineSignal(
        engine_name="chan",
        symbol="AAPL",
        direction=Direction.LONG,
        confidence=0.8,
        ...
    )
```
