# TradeOS - Target

## Vision

An **AI-first quantitative trading platform** that is modular, auditable, and designed to be called by AI agents rather than operated directly by humans.

## Ultimate Goal

Build a "trading brain" that:
1. Conducts continuous research on what signals work
2. Compares strategies and models
3. Deploys research outputs to execution
4. Feeds live performance back to research

All powered by AI agents (OpenClaw, Claude Code) that orchestrate the platform.

## Module Boundaries

### Core Modules

| Module | Responsibility | Self-Implement? |
|--------|---------------|-----------------|
| `core/execution/` | Order execution via NautilusTrader | ✅ Wrap, not replace |
| `core/research/` | Qlib-based research workflows | ✅ Extend, not replace |
| `core/analysis/chan/` | 缠论 (Chan Theory) engine | 🔴 Must implement |
| `core/analysis/technical/` | Classical technical analysis | 🟡 Use TA-Lib, wrap |
| `core/analysis/orderflow/` | Order flow analysis | 🔴 Must implement |
| `core/analysis/sentiment/` | Sentiment analysis | 🔴 Must implement |
| `core/analysis/macro/` | Macro regime analysis | 🔴 Must implement |
| `core/analysis/fundamental/` | Fundamental analysis | 🔴 Must implement |
| `core/arbitration/` | Decision aggregation | 🔴 Must implement |
| `core/risk/` | Risk management | 🔴 Must implement |
| `core/audit/` | Audit and feedback | 🔴 Must implement |

### Key Principles

1. **NautilusTrader = Execution Only**: Don't touch its core event-driven engine
2. **Qlib = Research Factory**: Don't rebuild the research platform
3. **TA-Lib = Indicator Computation**: Use for math, wrap with interpretation
4. **缠论/OrderFlow/Sentiment/Macro = Custom**: These require proprietary logic

## Non-Goals

### What This Platform Is NOT

1. **Not a strategy library**: We build the platform, not specific trading strategies
2. **Not a human-facing trading app**: Designed for AI orchestration
3. **Not a backtesting-only tool**: Live execution is a first-class concern
4. **Not dependent on a single AI**: Modular enough for any AI to call
5. **Not a replacement for NautilusTrader**: We wrap it, not replace it
6. **Not a replacement for Qlib**: We extend it, not rebuild it

## Deliverable: The Complete Stack

```
┌─────────────────────────────────────────────────────────────┐
│                   AI AGENTS (OpenClaw, Claude Code)          │
│           These orchestrate the platform, not humans          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        ORCHESTRATION                         │
│          CLI / API / Worker / Dashboard (apps/)             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      ANALYSIS ENGINES                        │
│                                                             │
│  ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌─────────────┐   │
│  │ 缠论    │ │ Technical│ │ OrderFlow │ │ Sentiment   │   │
│  │ Chan    │ │ Analysis │ │ Analysis  │ │ Analysis    │   │
│  └─────────┘ └──────────┘ └───────────┘ └─────────────┘   │
│  ┌─────────┐ ┌──────────┐ ┌───────────────────────────┐   │
│  │ Macro   │ │Fundament │ │ Qlib Research (Features, │   │
│  │ Analysis│ │al       │ │ Labels, Models)          │   │
│  └─────────┘ └──────────┘ └───────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     ARBITRATION LAYER                       │
│           Unified decision from all signals                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         RISK LAYER                          │
│    Position sizing, limits, square-root impact (NOT signal)  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      EXECUTION LAYER                        │
│           NautilusTrader wrapper (backtest/paper/live)      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       INFRASTRUCTURE                        │
│         Database / Cache / Queue / Object Store            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         AUDIT LAYER                         │
│      Every decision/execution/risk event logged             │
└─────────────────────────────────────────────────────────────┘
```

## Square-Root Constraint

The square-root formula is **ONLY** used for:
- ✅ Execution impact estimation
- ✅ Position size caps
- ✅ Order splitting optimization
- ✅ Participation rate constraints
- ✅ Slippage-aware scheduling

**NEVER** used for:
- ❌ Directional prediction
- ❌ Entry signal generation
- ❌ Market regime classification

## Schema Contract

All modules communicate via schemas defined in `core/schemas/`. No ad-hoc dictionaries.

```
core/schemas/
├── __init__.py     # All schemas
├── market.py       # MarketBar, MarketTick, etc.
├── signal.py       # EngineSignal, ArbitrationDecision
├── execution.py    # OrderRecord, FillRecord
├── risk.py         # RiskEvent, RiskLimits
└── audit.py        # AuditRecord
```

## Testing Requirements

Every module must have:
1. ✅ Unit tests for core logic
2. ✅ Integration tests for module interfaces
3. ✅ Contract tests for schema validation
4. ✅ Regression tests for bug fixes

## Audit Requirements

Every significant event must be logged:
- ✅ Trading decisions
- ✅ Order submissions
- ✅ Fills and executions
- ✅ Risk events
- ✅ Configuration changes
- ✅ Model updates
- ✅ Experiment runs

## Success Criteria

A platform is successful when:
1. **AI can orchestrate it**: OpenClaw/Claude Code can run the full workflow
2. **Modules are replaceable**: Each engine can be swapped independently
3. **Everything is auditable**: Any decision can be traced back
4. **Research feeds execution**: Models deploy to production
5. **Execution feeds research**: Live feedback improves models
6. **It's production-ready**: Backtest/paper/live all work

## Current Phase

Phase 1: Foundation (In Progress)
- Project scaffolding
- Schema definitions
- Configuration system
- Testing infrastructure
