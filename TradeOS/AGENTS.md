# AI Agents Collaboration Rules

This document defines how AI agents (OpenClaw, Claude Code, etc.) should interact with the AI Trading Tool platform.

## Overview

AI Trading Tool is designed to be orchestrated by AI agents, not directly operated by humans. This document provides rules and patterns for AI-to-platform interaction.

## Agent Roles

### Primary Agents

| Agent | Primary Role | Entry Points |
|-------|-------------|--------------|
| OpenClaw | Daily operations, monitoring, quick decisions | CLI, API |
| Claude Code | Development, strategy research, complex analysis | CLI, Scripts |
| Other Agents | Specialized tasks (research, execution monitoring) | API |

### Agent vs. Human

- **Agents**: Orchestrate the platform, make automated decisions
- **Humans**: Review, approve high-impact decisions, handle exceptions

## Interaction Patterns

### 1. Agent-Initiated Workflow

Agent triggers a complete workflow:

```bash
# Example: Run a research experiment
python -m ai_trading_tool.apps.cli research run \
    --experiment-name="aapl_momentum_v1" \
    --symbols=AAPL \
    --start-date=2020-01-01 \
    --end-date=2024-01-01
```

### 2. Scheduled Operations

Agent schedules recurring tasks:

```python
# Example: Schedule daily research update
from ai_trading_tool.apps.orchestrator import TaskScheduler

scheduler = TaskScheduler()
scheduler.schedule(
    task_name="daily_research_update",
    cron="0 6 * * *",  # 6 AM daily
    handler="ai_trading_tool.research.daily_update",
)
```

### 3. Real-Time Decision Flow

```python
# Example: Get trading decision for symbol
from ai_trading_tool.apps.api import TradingAPI

api = TradingAPI()

# Request decision
decision = await api.request_decision(
    symbol="AAPL",
    timeframe="5m",
    mode="production",  # or "paper" or "backtest"
)

# Execute if approved
if decision.entry_permission and decision.confidence > 0.7:
    await api.execute(decision)
```

## Agent Commands

### Research Commands

```bash
# Run experiment
ai-trading research run --experiment-name=<name>

# List experiments
ai-trading research list

# Get experiment results
ai-trading research results --experiment-id=<id>

# Trigger model retrain
ai-trading research retrain --model-id=<id>

# Check degradation
ai-trading research check-degradation --model-id=<id>
```

### Execution Commands

```bash
# Start execution mode
ai-trading execution start --mode=paper  # or "live"

# Stop execution
ai-trading execution stop

# Get current positions
ai-trading execution positions

# Cancel order
ai-trading execution cancel --order-id=<id>

# Get execution status
ai-trading execution status
```

### Analysis Commands

```bash
# Run analysis on symbol
ai-trading analysis run --symbol=AAPL --timeframe=5m

# Get engine signals
ai-trading analysis signals --symbol=AAPL

# Get arbitration decision
ai-trading analysis decision --symbol=AAPL
```

### Audit Commands

```bash
# Get decision history
ai-trading audit decisions --symbol=AAPL --days=30

# Get execution quality
ai-trading audit quality --days=7

# Get risk events
ai-trading audit risk-events --days=7

# Get model performance
ai-trading audit model-performance --model-id=<id>
```

## API Patterns

### REST API

Base URL: `http://localhost:8000/api/v1`

#### Research Endpoints

```
POST   /research/experiments          # Start experiment
GET    /research/experiments          # List experiments
GET    /research/experiments/{id}     # Get experiment
POST   /research/models/retrain       # Trigger retrain

#### Execution Endpoints

POST   /execution/decide              # Get decision
POST   /execution/submit              # Submit order
GET    /execution/positions           # Get positions
GET    /execution/orders             # Get orders
DELETE /execution/orders/{id}          # Cancel order

#### Analysis Endpoints

POST   /analysis/run                   # Run analysis
GET    /analysis/signals/{symbol}      # Get signals
GET    /analysis/decision/{symbol}    # Get decision

#### Audit Endpoints

GET    /audit/decisions               # Query decisions
GET    /audit/executions              # Query executions
GET    /audit/risk-events             # Query risk events
GET    /audit/models/{id}/performance # Model performance
```

### WebSocket API

For real-time updates:

```
WS /ws/execution          # Execution updates
WS /ws/analysis           # Analysis updates
WS /ws/audit              # Audit events
```

## Agent Memory Patterns

### Session Memory

Agents should maintain:

```
SESSION/
├── current_task/         # What agent is working on
├── pending_decisions/    # Decisions awaiting approval
├── execution_state/      # Current portfolio state
└── last_update/          # Timestamp of last interaction
```

### Long-Term Memory

Platform maintains:

```
PLATFORM/
├── models/               # Registered models
├── experiments/          # Experiment history
├── decisions/            # Decision history
├── executions/           # Execution history
└── performance/          # Performance metrics
```

## Error Handling

### Agent Error Recovery

```python
# Retry with exponential backoff
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def run_research():
    return await api.run_research()
```

### Circuit Breaker

```python
from core.shared.utils import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
)

async def get_decision():
    return await breaker.call(api.request_decision)
```

## Human-in-the-Loop

### Approval Gates

Certain actions require human approval:

```python
APPROVAL_GATES = {
    "live_execution": True,           # Always require approval
    "large_position": 0.2,           # > 20% portfolio
    "high_confidence": 0.95,          # Very high confidence
    "model_deactivation": True,       # Changing models
}
```

### Approval Flow

```python
# Request approval
approval = await api.request_approval(
    action="execute",
    decision=decision,
    reason="High-confidence signal",
)

if approval.status == "approved":
    await api.execute(decision)
elif approval.status == "rejected":
    log.warning("Execution rejected", reason=approval.reason)
```

## Logging Standards

Agents should log all actions:

```python
from core.shared.logging import get_logger

logger = get_logger("agent")

# Log agent action
logger.info(
    "agent_action",
    agent="openclaw",
    action="request_decision",
    symbol="AAPL",
    context={"mode": "paper"},
)

# Log decision
logger.info(
    "decision_received",
    decision_id=decision.decision_id,
    confidence=decision.confidence,
    direction=decision.direction,
)
```

## Security

### API Authentication

```python
# All API calls require authentication
headers = {
    "Authorization": f"Bearer {AGENT_API_KEY}",
    "X-Agent-Id": "openclaw",
}
```

### Permission Levels

| Level | Capabilities |
|-------|-------------|
| read | Query only |
| research | Run experiments |
| paper | Paper trading |
| execution | Live trading |
| admin | Full access |

## Best Practices

### 1. Idempotency
All operations should be idempotent. Use decision IDs for deduplication.

### 2. Audit Everything
Log all agent actions with context.

### 3. Timeout Handling
Set reasonable timeouts and handle timeout gracefully.

### 4. State Verification
Verify state before taking actions.

### 5. Fallback
Have fallback plans for API failures.

## Example Agent Workflow

```python
from ai_trading_tool.apps.orchestrator import AgentOrchestrator

async def daily_research_workflow():
    """Daily workflow for an AI agent."""
    
    orchestrator = AgentOrchestrator()
    
    # 1. Check market status
    market_status = await orchestrator.check_market()
    if not market_status.is_open:
        return
    
    # 2. Run research updates
    await orchestrator.run_research_update()
    
    # 3. Check model health
    models = await orchestrator.check_model_health()
    for model in models.degraded:
        await orchestrator.trigger_retrain(model.id)
    
    # 4. Get decisions for watchlist
    for symbol in ["AAPL", "MSFT", "GOOGL"]:
        decision = await orchestrator.get_decision(symbol)
        
        # 5. Execute if conditions met
        if should_execute(decision):
            await orchestrator.execute(decision)
    
    # 6. Log summary
    await orchestrator.log_daily_summary()
```

## Troubleshooting

### API Connection Issues

```python
# Check connectivity
health = await api.health_check()
if not health.ok:
    logger.error("API unhealthy", details=health)
    # Switch to backup or alert human
```

### Execution Failures

```python
try:
    await api.execute(decision)
except ExecutionError as e:
    logger.error("Execution failed", error=str(e))
    # Record failure, notify human
```

### Model Degradation

```python
status = await api.check_model_degradation(model_id)
if status.is_degraded:
    logger.warning("Model degraded", 
        model_id=model_id,
        current_sharpe=status.sharpe,
        threshold=status.threshold)
    
    # Trigger retrain
    await api.trigger_retrain(model_id)
```
