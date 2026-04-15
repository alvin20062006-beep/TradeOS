# Execution Flow

This document describes how orders are executed using NautilusTrader.

## Overview

The execution layer translates trading decisions into executed orders. It wraps NautilusTrader for the underlying event-driven execution engine while maintaining our own execution control and audit layers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EXECUTION LAYER                                  │
│                  core/execution/ (NautilusTrader Wrapper)               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┼───────────────────────────────┐
    ▼                               ▼                               ▼
┌──────────┐                ┌─────────────┐               ┌──────────────────┐
│  Order   │                │  Position   │               │    Execution     │
│  Manager │                │   Tracker   │               │    Algorithms    │
└──────────┘                └─────────────┘               └──────────────────┘
```

## Execution Flow

### 1. Decision to Intent

ArbitrationDecision is translated to ExecutionIntent:

```python
from ai_trading_tool.execution import OrderGenerator

generator = OrderGenerator()

intent = generator.create_intent(
    decision=arbitration_decision,
    current_price=current_price,
    risk_limits=risk_limits,
)
```

### 2. Order Type Selection

Based on execution conditions:

```python
order_type = generator.select_order_type(
    intent=intent,
    volatility=current_volatility,
    liquidity=current_liquidity,
    time_horizon=time_horizon,
)
```

| Condition | Recommended Order Type |
|-----------|----------------------|
| High volatility, urgent | MARKET |
| Low volatility, patient | LIMIT |
| Large size, need iceber | ICEBERG |
| Time-sensitive execution | TWAP |
| Volume-sensitive execution | VWAP |
| Adaptive to flow | ADAPTIVE |

### 3. Order Submission

Orders submitted to NautilusTrader:

```python
from ai_trading_tool.execution import NautilusExecutor

executor = NautilusExecutor()

order_record = await executor.submit_order(
    intent=intent,
    order_type=order_type,
)
```

### 4. Fill Tracking

```python
# Fill events from NautilusTrader
async for fill in executor.stream_fills(order_id):
    fill_record = executor.process_fill(fill)
    await audit_logger.log(fill_record)
```

## Order Types

### Market Order
```python
Order(
    order_type=OrderType.MARKET,
    quantity=100,
    time_in_force="ioc",  # Immediate or cancel
)
```

### Limit Order
```python
Order(
    order_type=OrderType.LIMIT,
    quantity=100,
    price=150.00,
    time_in_force="gtc",  # Good till cancel
)
```

### TWAP (Time-Weighted Average Price)
```python
Order(
    order_type=OrderType.TWAP,
    quantity=10000,
    time_limit_seconds=3600,  # 1 hour
    slice_interval_seconds=60,  # Slice every minute
)
```

### VWAP (Volume-Weighted Average Price)
```python
Order(
    order_type=OrderType.VWAP,
    quantity=10000,
    participation_rate=0.1,  # 10% of volume
    time_limit_seconds=3600,
)
```

### Iceberg Order
```python
Order(
    order_type=OrderType.ICEBERG,
    quantity=10000,
    visible_quantity=1000,  # Show only 1000
)
```

### Adaptive Order
```python
Order(
    order_type=OrderType.ADAPTIVE,
    quantity=100,
    price_limit=150.00,
    aggression="passive",  # passive/aggressive/neutral
)
```

## Execution Algorithms

### TWAP
Time-weighted execution - slices order into equal parts over time.

```python
from ai_trading_tool.execution.algorithms import TWAPExecutor

twap = TWAPExecutor()
schedule = twap.generate_schedule(
    total_quantity=10000,
    time_limit_seconds=3600,
    slice_interval_seconds=300,
)
```

### VWAP
Volume-weighted execution - matches market volume profile.

```python
from ai_trading_tool.execution.algorithms import VWAPExecutor

vwap = VWAPExecutor()
schedule = vwap.generate_schedule(
    total_quantity=10000,
    participation_rate=0.1,
    expected_volume_profile=volume_profile,
)
```

### POV (Percentage of Volume)
```python
from ai_trading_tool.execution.algorithms import POVExecutor

pov = POVExecutor()
schedule = pov.generate_schedule(
    total_quantity=10000,
    participation_rate=0.15,
    lookback_volume=avg_daily_volume,
)
```

## Square-Root Impact Model

**Constraint**: Square-root formula is used ONLY for impact estimation, NOT directional prediction.

```python
from ai_trading_tool.execution.impact import SquareRootImpact

impact_model = SquareRootImpact(
    daily_volume=1_000_000,  # Average daily volume
    participation_rate=0.1,  # 10% participation
)

estimated_impact_bps = impact_model.estimate_impact(
    order_size=100_000,
    current_price=150.00,
)
# Output: ~5.0 bps estimated impact

# Use for:
# - Position size cap
# - Order splitting optimization
# - Participation rate constraints
# - Slippage forecasting
```

Formula:
```
impact = σ * sqrt(Q / ADV)
where:
    σ = daily volatility
    Q = order size
    ADV = average daily volume
```

## Position Tracking

```python
from ai_trading_tool.execution import PositionTracker

tracker = PositionTracker()

# Update with fills
tracker.update_with_fill(fill_record)

# Get current state
position = tracker.get_position(symbol="AAPL")
print(f"AAPL position: {position.quantity} @ avg {position.avg_entry_price}")
```

## Execution Quality Measurement

```python
from ai_trading_tool.execution import ExecutionQualityMeasurer

measurer = ExecutionQualityMeasurer()

quality = measurer.measure(
    order=order_record,
    fills=fill_records,
    arrival_price=arrival_price,
    market_impact=estimated_impact,
)

# Quality scores:
# - EXCELLENT: slippage < 1 bps
# - GOOD: slippage 1-5 bps
# - FAIR: slippage 5-10 bps
# - POOR: slippage > 10 bps
# - FAILED: order rejected/failed
```

## NautilusTrader Integration

```python
from nautilus_trader import NautilusMuscule
from nautilus_trader.config import ActorConfig

class OurExecutionAdapter(ActorConfig):
    ...
    
# NautilusTrader handles:
# - Order book management
# - Position management
# - Account/balance tracking
# - Commission calculation
# - Venue connectivity
```

## Execution Configuration

```yaml
execution:
  mode: paper  # backtest, paper, live
  
  paper:
    enabled: true
    broker: mock
    fill_probability: 0.99
    fill_latency_ms: 100
  
  live:
    enabled: false
    broker: alpaca
    api_key: ${ALPACA_API_KEY}
    api_secret: ${ALPACA_API_SECRET}
    paper_trading: true
```

## Monitoring

```python
from ai_trading_tool.execution import ExecutionMonitor

monitor = ExecutionMonitor()

# Track execution metrics
metrics = monitor.get_metrics(
    start_date="2024-01-01",
    end_date="2024-01-31",
)

print(f"Total orders: {metrics.total_orders}")
print(f"Filled rate: {metrics.fill_rate}")
print(f"Avg slippage: {metrics.avg_slippage_bps} bps")
print(f"Execution quality distribution: {metrics.quality_distribution}")
```
