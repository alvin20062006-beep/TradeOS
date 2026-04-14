# AI Trading Tool - System Overview

## Vision

AI Trading Tool is an **AI-first quantitative trading platform** that separates concerns between intelligence (research + analysis + arbitration) and execution (NautilusTrader). It is designed to be called by AI agents (OpenClaw, Claude Code, etc.) rather than requiring human traders to operate it directly.

## Architecture Principles

1. **Brain-Tool Separation**: Research and analysis are "brains" that produce signals; execution is a "tool" that follows instructions. They communicate via well-defined schemas.

2. **Schema-First Design**: Every module communicates through Pydantic schemas. No ad-hoc dictionaries, no implicit contracts.

3. **Audit Everything**: Every decision, execution, and risk event is logged to the audit database.

4. **Reproducibility**: All experiments are versioned. All models are registered. All data is versioned.

5. **Production-Grade Foundation**: NautilusTrader handles the event-driven execution; we don't reinvent the wheel.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AI AGENTS                                   │
│            (OpenClaw / Claude Code / Other AI Brains)                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATION LAYER                            │
│                    apps/ (CLI / API / Worker / Dashboard)                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ARBITRATION LAYER                               │
│              core/arbitration/ (Decision Aggregator)                     │
│                                                                         │
│   Inputs: Engine signals from 6 analysis engines + Qlib research         │
│   Output: Unified ArbitrationDecision                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
        ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
        │  ANALYSIS ENGINES │ │    RISK      │ │  EXECUTION LAYER │
        │                  │ │   LAYER      │ │                  │
        │  • 缠论 (Chan)   │ │              │ │  NautilusTrader  │
        │  • Technical     │ │  • Position  │ │ 封装             │
        │  • Order Flow   │ │  • Sizing    │ │                  │
        │  • Sentiment    │ │  • Limits    │ │  • Market orders │
        │  • Macro        │ │  • Square-   │ │  • Limit orders  │
        │  • Fundamental  │ │    root      │ │  • TWAP/VWAP     │
        └──────────────────┘ │    impact    │ │  • Iceberg       │
                    ▲         └──────────────┘ └──────────────────┘
                    │                          │
                    │ engine_signals           │ ExecutionIntent
                    │                          ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │                        RESEARCH LAYER                          │
        │              core/research/ (Qlib Integration)                  │
        │                                                                     │
        │  • Feature engineering   • Model training   • Walk-forward      │
        │  • Label construction    • Backtesting      • Rolling retrain    │
        │  • Dataset versioning    • Evaluation       • Live feedback      │
        └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │                          DATA LAYER                             │
        │                 core/data/ (Providers + Storage)                 │
        │                                                                     │
        │  • Market data    • News    • Macro calendar    • Sentiment      │
        │  • Storage: Parquet / PostgreSQL / Redis cache                     │
        └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │                     INFRASTRUCTURE LAYER                       │
        │           infra/ (DB / Cache / Queue / Object Store)            │
        │                                                                     │
        │  • Database: SQLite (dev) / PostgreSQL (prod)                   │
        │  • Cache: Redis    • Queue: Celery   • Storage: S3/MinIO       │
        └─────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Ingestion**: Market data, news, macro events ingested via data layer
2. **Research**: Qlib processes data, trains models, generates alpha signals
3. **Analysis**: Six engines analyze data, each produces EngineSignal
4. **Arbitration**: Arbitration layer aggregates signals, produces ArbitrationDecision
5. **Risk Check**: Risk layer validates against limits, adjusts position size
6. **Execution**: Execution layer sends order to NautilusTrader
7. **Audit**: All events logged to audit database
8. **Feedback**: Live performance data flows back to research layer

## Key Design Decisions

### Why NautilusTrader?
- Event-driven, production-grade execution engine
- Backtest/Paper/Live in same architecture
- Built-in order management and portfolio tracking
- We wrap it, not replace it

### Why Qlib?
- AI-oriented quantitative research platform
- Built-in workflow automation (qrun)
- Feature/label framework already battle-tested
- We extend it, not replace it

### Why TA-Lib/ta?
- 200+ proven technical indicators
- Candlestick pattern recognition
- We use them for indicator computation, wrap with our interpretation

### Why Self-Implement These?
- **缠论 (Chan Theory)**: No standard library; requires custom implementation
- **Order Flow Analysis**: Exchange-specific; requires real-time processing
- **Sentiment Analysis**: Custom integration with news/social APIs
- **Macro Analysis**: Event parsing and regime detection
- **Arbitration**: Our proprietary decision logic
- **Audit**: Complete traceability requirement

### Square-Root Formula Constraint
The square-root formula is used **only** for:
- Execution impact estimation
- Position size caps
- Order splitting optimization
- Participation rate constraints
- Slippage-aware scheduling

**Never** used for directional prediction.

## Deployment Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| Backtest | Historical simulation | Research, strategy development |
| Paper | Simulated execution | Strategy validation |
| Live | Real money execution | Production |

## Technology Stack

- **Language**: Python 3.10+
- **Execution**: NautilusTrader (Rust-based)
- **Research**: Qlib
- **Data**: Pandas, Polars, PyArrow
- **Schema**: Pydantic v2
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Cache**: Redis
- **Queue**: Celery
- **Logging**: Structlog
- **Testing**: Pytest, Hypothesis
