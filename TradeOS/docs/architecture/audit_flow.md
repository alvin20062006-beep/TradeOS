# Audit Flow

This document describes the audit and feedback loop system.

## Overview

Every significant system event is logged to the audit database. The audit layer ensures complete traceability from decision to execution to outcome.

## Audit Events

### Tracked Events

| Event Type | Description | Table |
|------------|-------------|-------|
| Decision | Trading decisions | `decisions` |
| Order | Order lifecycle | `orders` |
| Fill | Individual fills | `fills` |
| Risk Event | Risk breaches | `risk_events` |
| Config Change | Configuration changes | `system_events` |
| Model Change | Model activation/deactivation | `model_registry` |
| Experiment | Research experiments | `experiments` |
| Live Feedback | Trade outcome feedback | `live_feedback` |

## Audit Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         MODULES                                   │
│  arbitration | execution | risk | research | analysis | apps    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ (emit events)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AUDIT LAYER                                 │
│                   core/audit/                                     │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │  Logger    │  │  Recorder    │  │   Feedback Collector │    │
│  │  (async)   │  │  (sync)      │  │   (async)            │    │
│  └─────────────┘  └──────────────┘  └──────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DATABASE                                    │
│                    infra/db/                                     │
│                                                                     │
│  decisions | orders | fills | risk_events | model_registry       │
│  experiments | live_feedback | system_events | audit_log         │
└─────────────────────────────────────────────────────────────────┘
```

## Audit Logger Usage

### Basic Usage

```python
from ai_trading_tool.audit import AuditLogger

audit = AuditLogger()

# Log a decision
audit.log_decision(
    decision=arbitration_decision,
)

# Log an execution
audit.log_execution(
    order=order_record,
    fills=fill_records,
)

# Log a risk event
audit.log_risk_event(
    event=risk_event,
)
```

### Structured Logging

```python
from ai_trading_tool.audit import get_audit_logger

logger = get_audit_logger()

# With context
logger.info(
    "decision_made",
    decision_id="uuid-123",
    symbol="AAPL",
    direction="long",
    confidence=0.85,
)

logger.info(
    "order_submitted",
    order_id="uuid-456",
    decision_id="uuid-123",
    symbol="AAPL",
    quantity=100,
)
```

## Decision Audit

```python
from ai_trading_tool.audit import DecisionAuditor

auditor = DecisionAuditor()

# Create audit record
audit = auditor.create_decision_audit(
    decision=arbitration_decision,
    engine_signals={
        "chan": EngineSignal(direction=Direction.LONG, confidence=0.8),
        "technical": EngineSignal(direction=Direction.LONG, confidence=0.7),
        "qlib": EngineSignal(direction=Direction.LONG, confidence=0.9),
    },
)

# Store
await auditor.store(audit)
```

### Decision Record Schema

```sql
CREATE TABLE decisions (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ,
    symbol TEXT,
    direction TEXT,
    confidence REAL,
    regime TEXT,
    entry_permission BOOLEAN,
    max_position_pct REAL,
    engine_signals JSONB,
    consensus_score REAL,
    reasoning TEXT,
);
```

## Execution Audit

```python
from ai_trading_tool.audit import ExecutionAuditor

auditor = ExecutionAuditor()

# Track order
await auditor.log_order(order_record)

# Track fill
await auditor.log_fill(fill_record)

# Calculate execution quality
quality = auditor.measure_execution_quality(
    order=order_record,
    fills=fill_records,
    arrival_price=arrival_price,
)
```

## Risk Event Audit

```python
from ai_trading_tool.audit import RiskAuditor

auditor = RiskAuditor()

# Log risk breach
await auditor.log_risk_event(
    event_type=RiskEventType.MAX_POSITION_BREACH,
    symbol="AAPL",
    description="Position exceeded 15% of portfolio",
    triggered_value=0.18,
    threshold_value=0.15,
    action_taken="Reduced position to 10%",
    decision_id="uuid-123",
)
```

## Live Feedback Loop

```python
from ai_trading_tool.audit import LiveFeedbackCollector

collector = LiveFeedbackCollector()

# Collect feedback for closed trade
feedback = await collector.collect(
    decision_id="uuid-123",
)

# Update model performance
await collector.update_model_feedback(
    model_id="aapl_lgb_v1",
    feedback=feedback,
)
```

### Feedback Collection Flow

```
Trade Closed
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Outcome Calculation                               │
│  • P&L calculation                                              │
│  • Holding period                                              │
│  • Win/Loss/Breakeven classification                           │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Feedback Storage                                │
│  live_feedback table                                            │
│  • actual_return vs predicted_return                            │
│  • key_lessons                                                  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│               Research Layer Update                               │
│  • Update model performance tracking                            │
│  • Trigger degradation detection                                │
│  • Schedule retrain if needed                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Degradation Detection

```python
from ai_trading_tool.audit import DegradationDetector

detector = DegradationDetector(
    config={
        "sharpe_threshold": 1.5,
        "max_drawdown_threshold": 0.15,
        "win_rate_threshold": 0.45,
        "check_window": 30,  # days
    },
)

# Check model health
status = await detector.check_model(
    model_id="aapl_lgb_v1",
)

if status.degraded:
    # Alert
    await detector.send_alert(
        model_id="aapl_lgb_v1",
        reason=status.reason,
        metrics=status.metrics,
    )
    
    # Trigger retrain
    await detector.trigger_retrain(
        model_id="aapl_lgb_v1",
    )
```

## Audit Queries

### Decision Analysis

```python
from ai_trading_tool.audit import AuditQuerier

querier = AuditQuerier()

# Get decision history
decisions = await querier.get_decisions(
    symbol="AAPL",
    start_date="2024-01-01",
    end_date="2024-01-31",
)

# Get decision with execution
full_record = await querier.get_decision_with_execution(
    decision_id="uuid-123",
)
```

### Performance Attribution

```python
# Analyze decision quality by engine
attribution = await querier.get_engine_attribution(
    start_date="2024-01-01",
    end_date="2024-03-31",
)

# Output:
# {
#     "chan": {"win_rate": 0.65, "avg_pnl": 150},
#     "technical": {"win_rate": 0.55, "avg_pnl": 100},
#     "qlib": {"win_rate": 0.70, "avg_pnl": 200},
# }
```

## Audit Retention

```python
from ai_trading_tool.audit import AuditRetentionPolicy

policy = AuditRetentionPolicy(
    retention_days=90,
    archive_before_days=365,
)

# Apply retention policy
deleted = await policy.apply()
print(f"Deleted {deleted} old records")

# Archive old records
archived = await policy.archive()
print(f"Archived {archived} records")
```

## Audit Dashboard Queries

### Daily Summary

```sql
SELECT 
    date(timestamp) as date,
    count(*) as total_decisions,
    count(*) filter (where no_trade_flag = true) as no_trades,
    count(*) filter (where direction = 'long') as longs,
    count(*) filter (where direction = 'short') as shorts,
    avg(confidence) as avg_confidence
FROM decisions
WHERE timestamp >= '2024-01-01'
GROUP BY date(timestamp)
ORDER BY date DESC;
```

### Execution Quality

```sql
SELECT 
    date(filled_at) as date,
    count(*) as total_fills,
    avg(slippage_bps) as avg_slippage,
    count(*) filter (where execution_quality = 'excellent') as excellent,
    count(*) filter (where execution_quality = 'poor') as poor
FROM orders
WHERE filled_at >= '2024-01-01'
GROUP BY date(filled_at)
ORDER BY date DESC;
```

### Risk Events

```sql
SELECT 
    event_type,
    count(*) as total_events,
    count(*) filter (where action_taken = 'rejected') as rejected,
    count(*) filter (where position_closed = true) as positions_closed
FROM risk_events
WHERE timestamp >= '2024-01-01'
GROUP BY event_type;
```
