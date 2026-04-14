# AI Trading Tool - Roadmap

## Project Overview

AI Trading Tool is an AI-first quantitative trading platform that separates intelligence (research + analysis + arbitration) from execution (NautilusTrader). It is designed to be called by AI agents (OpenClaw, Claude Code, etc.).

## Phase 1: Foundation (Current)
**Duration**: 1-2 weeks  
**Goal**: Project scaffolding, schema definitions, configuration, testing infrastructure

### Deliverables
- [x] Project directory structure
- [x] `pyproject.toml` with dependency groups
- [x] Global schema definitions (15+ schemas)
- [x] Configuration system (YAML-based, env-aware)
- [x] Database schema (PostgreSQL-compatible)
- [x] Migration mechanism (Alembic)
- [x] Unified logging system
- [x] Test framework setup
- [x] Documentation skeleton

### Phase 1 Sub-tasks
1. [ ] Initialize git repository with `.gitignore`
2. [ ] Create base config files (`config/base.yaml`, `config/env/development.yaml`)
3. [ ] Set up Alembic migrations
4. [ ] Write initial unit tests for schemas
5. [ ] Write contract tests for schema validation
6. [ ] Create `Makefile` with common commands
7. [ ] Write `Makefile` / development guide docs
8. [ ] Phase 1 acceptance test

### Phase 1 Acceptance Criteria
- [ ] `pip install -e .` succeeds
- [ ] All schemas import without errors
- [ ] Config loads from YAML
- [ ] Database migrations run successfully
- [ ] `pytest tests/unit/` passes
- [ ] `pytest tests/contracts/` passes
- [ ] Documentation builds with `mkdocs`

---

## Phase 2: Data Layer ✅
**Duration**: 2-3 weeks  
**Goal**: Data ingestion, storage, retrieval infrastructure

### Deliverables
- [x] Data provider framework (abstract base)
- [x] Yahoo Finance connector
- [x] CSV provider
- [x] Schema validation for incoming data
- [x] Parquet storage system
- [x] Data quality validator
- [x] Backfill manager
- [x] Provider registry

### Phase 2 Sub-tasks
1. [ ] Abstract data provider interface
2. [ ] Yahoo Finance connector
3. [ ] Polygon.io connector
4. [ ] Alpaca data connector
5. [ ] Parquet storage with partitioning
6. [ ] Redis cache integration
7. [ ] Backfill orchestration
8. [ ] Data quality checks

---

## Phase 3: NautilusTrader Integration
**Duration**: 2-3 weeks  
**Goal**: Execution layer with backtest/paper/live support

### Deliverables
- [ ] NautilusTrader wrapper
- [ ] Backtest engine abstraction
- [ ] Paper trading engine
- [ ] Live execution adapter
- [ ] Order management system
- [ ] Position tracking
- [ ] Execution quality measurement

### Phase 3 Sub-tasks
1. [ ] NautilusTrader initialization
2. [ ] Order type abstractions
3. [ ] Backtest runner
4. [ ] Paper trading mode
5. [ ] Live broker adapters
6. [ ] Fill event handling
7. [ ] Commission calculation
8. [ ] Slippage modeling

---

## Phase 4: Research Factory (Qlib)
**Duration**: 3-4 weeks  
**Goal**: Research workflow automation with Qlib

### Deliverables
- [ ] Qlib dataset integration
- [ ] Feature engineering pipeline
- [ ] Label construction
- [ ] Model training framework
- [ ] Backtest engine
- [ ] Walk-forward analyzer
- [ ] Rolling retrain scheduler
- [ ] Model registry

### Phase 4 Sub-tasks
1. [ ] Qlib environment setup
2. [ ] Dataset builder
3. [ ] Feature definitions (Alpha158, etc.)
4. [ ] Label generators
5. [ ] Model trainer (LightGBM, XGBoost)
6. [ ] Backtest wrapper
7. [ ] Walk-forward framework
8. [ ] Degradation detector
9. [ ] Experiment tracker

---

## Phase 5: Analysis Engines
**Duration**: 4-6 weeks  
**Goal**: Six analysis engines producing structured signals

### Deliverables

#### 5.1 缠论 (Chan Theory) Engine
- [ ] Fractal detection (分型)
- [ ] Stroke building (笔)
- [ ] Segment analysis (线段)
- [ ] Center identification (中枢)
- [ ] Divergence detection (背驰)
- [ ] Purchase point signals (一买/二买/三买)
- [ ] Sell point signals (一卖/二卖/三卖)
- [ ] Multi-timeframe linkage
- [ ] Structure failure detection

#### 5.2 Technical Analysis Engine
- [ ] Trend indicators (MA, ADX, channels)
- [ ] Momentum indicators (MACD, RSI, Stochastic, KDJ, CCI)
- [ ] Volatility indicators (ATR, Bollinger Bands)
- [ ] Chart patterns (head-shoulders, triangles, etc.)
- [ ] Candlestick patterns (engulfing, doji, pin bar)
- [ ] Support/resistance detection
- [ ] Multi-timeframe confirmation

#### 5.3 Order Flow Engine
- [ ] Order book snapshot processing
- [ ] Imbalance calculation
- [ ] Delta/CVD tracking
- [ ] Absorption detection
- [ ] Liquidity sweep detection
- [ ] Execution quality forecasting
- [ ] Stop hunt zone identification

#### 5.4 Sentiment Engine
- [ ] News sentiment analysis
- [ ] Social media integration (Twitter/X, Reddit)
- [ ] Forum sentiment (StockTwits, etc.)
- [ ] Multi-source aggregation
- [ ] Sector heat mapping

#### 5.5 Macro Engine
- [ ] Economic calendar integration
- [ ] Event impact scoring
- [ ] Regime detection
- [ ] Asset impact mapping
- [ ] Central bank policy tracking

#### 5.6 Fundamental Engine
- [ ] Financial metrics retrieval
- [ ] Valuation scoring
- [ ] Earnings quality analysis
- [ ] Sector comparison

---

## Phase 6: Arbitration Layer
**Duration**: 2-3 weeks  
**Goal**: Unified decision from multiple signals

### Deliverables
- [ ] Signal aggregator
- [ ] Weighted consensus calculation
- [ ] Regime-based rules
- [ ] Confidence calibration
- [ ] No-trade condition detection
- [ ] Decision explainability

### Phase 6 Sub-tasks
1. [ ] Signal collection interface
2. [ ] Weight configuration
3. [ ] Consensus scoring algorithm
4. [ ] Regime-specific rules
5. [ ] Decision output schema
6. [ ] Decision explanation generator

---

## Phase 7: Risk Management
**Duration**: 2-3 weeks  
**Goal**: Position sizing, limits, square-root impact

### Deliverables
- [ ] Position limit enforcement
- [ ] Volatility targeting
- [ ] Kelly fraction calculator
- [ ] Drawdown monitoring
- [ ] Correlation tracking
- [ ] Square-root impact estimation (NOT directional)
- [ ] Order size constraints
- [ ] Slippage-aware sizing

### Phase 7 Sub-tasks
1. [ ] Risk limit configuration
2. [ ] Position size calculators
3. [ ] Volatility estimator
4. [ ] Drawdown tracker
5. [ ] Correlation matrix
6. [ ] Square-root impact model
7. [ ] Risk-adjusted sizing

---

## Phase 8: Audit & Feedback
**Duration**: 2-3 weeks  
**Goal**: Complete traceability and live feedback loop

### Deliverables
- [ ] Decision logging
- [ ] Execution logging
- [ ] Risk event logging
- [ ] Live feedback collection
- [ ] Degradation detection
- [ ] Research feedback loop
- [ ] Audit dashboard queries

### Phase 8 Sub-tasks
1. [ ] Audit logger implementation
2. [ ] Database writer
3. [ ] Feedback collector
4. [ ] Degradation detector
5. [ ] Retrain trigger
6. [ ] Audit query interface

---

## Phase 9: Strategies & Production
**Duration**: Ongoing  
**Goal**: Strategy pool and multi-strategy portfolio

### Deliverables
- [ ] Strategy templates
- [ ] Trend-following strategies
- [ ] Mean-reversion strategies
- [ ] Breakout strategies
- [ ] Multi-strategy portfolio
- [ ] Strategy allocation
- [ ] Performance monitoring

---

## Timeline Overview

```
Phase 1:  ██  (1-2 weeks)
Phase 2:  ████  (2-3 weeks)
Phase 3:  ████  (2-3 weeks)
Phase 4:  ████████  (3-4 weeks)
Phase 5:  ██████████████  (4-6 weeks)
Phase 6:  ██████  (2-3 weeks)
Phase 7:  ██████  (2-3 weeks)
Phase 8:  ██████  (2-3 weeks)
Phase 9:  ████████████████████████████████████  (Ongoing)
```

---

## Dependencies

```
Phase 1
  └── (Foundation, no dependencies)

Phase 2
  └── Phase 1

Phase 3
  └── Phase 1, Phase 2

Phase 4
  └── Phase 1, Phase 2

Phase 5
  └── Phase 1, Phase 2

Phase 6
  └── Phase 4, Phase 5

Phase 7
  └── Phase 1

Phase 8
  └── Phase 3, Phase 6, Phase 7

Phase 9
  └── Phase 6, Phase 7, Phase 8
```

---

## Success Metrics

### Phase 1 Success
- All schemas import and validate
- Config system works across environments
- Database migrations succeed
- Tests pass

### Phase 2 Success
- Can load data from multiple providers
- Data stored correctly in Parquet
- Cache hit rate > 80% for recent data

### Phase 3 Success
- Backtest produces same results as manual run
- Paper trading fills match expected
- Live execution connects to broker

### Phase 4 Success
- Walk-forward produces stable metrics
- Models register correctly
- Degradation detection triggers on schedule

### Phase 5 Success
- All engines produce EngineSignal schema
- Engines pass unit tests
- Multi-timeframe works correctly

### Phase 6 Success
- ArbitrationDecision matches manual analysis
- Consensus scoring is stable
- No-trade conditions trigger correctly

### Phase 7 Success
- Risk limits enforced consistently
- Square-root model produces reasonable estimates
- Drawdown protection works

### Phase 8 Success
- All events logged to database
- Feedback flows to research
- Audit queries return correct data

### Phase 9 Success
- Strategies produce consistent returns
- Portfolio allocation works
- Performance meets targets
