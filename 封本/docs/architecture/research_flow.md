# Research Flow

This document describes the research factory workflow using Qlib.

## Overview

The research layer is responsible for:
- Feature engineering
- Label construction
- Model training
- Backtesting
- Evaluation
- Walk-forward analysis
- Rolling retraining
- Live feedback integration

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         RESEARCH LAYER                          │
│                   core/research/ (Qlib Integration)              │
└─────────────────────────────────────────────────────────────────┘
                              │
    ┌─────────────┬────────────┼────────────┬─────────────┐
    ▼             ▼            ▼            ▼             ▼
┌────────┐  ┌──────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐
│Dataset │  │ Features │  │ Labels  │  │ Models  │  │ Backtest │
│Builder │  │ Engine   │  │ Builder │  │ Trainer │  │ Engine   │
└────────┘  └──────────┘  └─────────┘  └─────────┘  └──────────┘
```

## Research Pipeline

### 1. Data Ingestion

```python
from ai_trading_tool.research import DataIngestion

ingestion = DataIngestion(provider="yfinance")
data = ingestion.load(
    symbols=["AAPL", "MSFT"],
    start_date="2020-01-01",
    end_date="2024-12-31",
    fields=["open", "high", "low", "close", "volume"],
)
```

### 2. Feature Engineering

Features are computed using Qlib's feature framework:

```python
from ai_trading_tool.research import FeatureEngine

engine = FeatureEngine(provider="qlib")
features = engine.compute(
    data=data,
    feature_definitions=[
        "Kbars({})->close".format(window),
        "RSI({})->rsi".format(window),
        "MACD({})->macd".format(window),
    ],
)
```

### 3. Label Construction

Labels define the prediction target:

```python
from ai_trading_tool.research import LabelBuilder

builder = LabelBuilder(method="return", horizon=5)
labels = builder.build(
    data=data,
    label_type="regression",  # or "classification"
)
```

### 4. Dataset Assembly

```python
from ai_trading_tool.research import DatasetBuilder

builder = DatasetBuilder()
dataset = builder.assemble(
    features=features,
    labels=labels,
    train_start="2020-01-01",
    train_end="2022-12-31",
    valid_start="2023-01-01",
    valid_end="2023-06-30",
    test_start="2023-07-01",
    test_end="2024-12-31",
)
```

### 5. Model Training

```python
from ai_trading_tool.research import ModelTrainer

trainer = ModelTrainer(model_type="lightgbm")
model = trainer.train(
    dataset=dataset,
    config={
        "learning_rate": 0.05,
        "num_leaves": 31,
        "max_depth": 6,
    },
)
```

### 6. Backtesting

```python
from ai_trading_tool.research import BacktestEngine

engine = BacktestEngine(executor="nautilus")
results = engine.run(
    model=model,
    dataset=dataset,
    initial_capital=100_000,
    commission=0.001,
)
```

### 7. Evaluation

```python
from ai_trading_tool.research import Evaluator

evaluator = Evaluator()
metrics = evaluator.evaluate(
    results=results,
    metrics=["annual_return", "max_drawdown", "sharpe_ratio", "calmar_ratio"],
)
```

## Walk-Forward Analysis

Walk-forward analysis trains and tests on rolling windows:

```python
from ai_trading_tool.research import WalkForwardAnalyzer

analyzer = WalkForwardAnalyzer(
    train_window=252,  # 1 year
    test_window=63,     # 3 months
    step=21,            # monthly roll
)

results = analyzer.run(
    symbols=["AAPL"],
    start_date="2018-01-01",
    end_date="2024-12-31",
)
```

## Rolling Retrain

Rolling retrain schedules periodic model updates:

```python
from ai_trading_tool.research import RollingRetrainScheduler

scheduler = RollingRetrainScheduler(
    frequency="monthly",
    lookback=252,
)

scheduler.schedule(
    model_name="aapl_model_v1",
    trigger_date="2024-02-01",
)
```

## Live Feedback Loop

Live feedback flows from production to research:

```python
from ai_trading_tool.research import LiveFeedbackCollector

collector = LiveFeedbackCollector()

# Collect feedback from closed trades
feedback = collector.collect(
    start_date="2024-01-01",
    end_date="2024-01-31",
)

# Update model performance tracking
analyzer.update_performance_tracking(
    model_name="aapl_model_v1",
    feedback=feedback,
)
```

## Degradation Detection

Monitor model performance for degradation:

```python
from ai_trading_tool.research import DegradationDetector

detector = DegradationDetector(
    threshold_sharpe=1.5,
    threshold_max_drawdown=0.15,
)

status = detector.check(
    model_name="aapl_model_v1",
    recent_metrics={"sharpe": 1.2, "max_drawdown": 0.18},
)

if status.degraded:
    detector.alert(model_name="aapl_model_v1", reason=status.reason)
    detector.trigger_retrain(model_name="aapl_model_v1")
```

## Model Registry

All models are registered:

```python
from ai_trading_tool.research import ModelRegistry

registry = ModelRegistry()

# Register new model
registry.register(
    model_id="aapl_lgb_v1",
    model_name="aapl_lightgbm",
    version="1.0.0",
    metrics={"sharpe": 2.1, "max_drawdown": 0.08},
    artifacts_path="/models/aapl_lgb_v1.pkl",
)

# List models
models = registry.list(active_only=True)

# Activate model for production
registry.activate(model_id="aapl_lgb_v1")
```

## Experiment Tracking

```python
from ai_trading_tool.research import ExperimentTracker

tracker = ExperimentTracker()

# Start experiment
experiment_id = tracker.start(
    name="aapl_rsi_optimization",
    config={
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
    },
)

# Log metrics
tracker.log_metric(experiment_id, "sharpe", 2.1)
tracker.log_metric(experiment_id, "max_drawdown", 0.08)

# Complete experiment
tracker.complete(
    experiment_id,
    results={"profit": 15000, "trades": 45},
)
```

## Research → Execution Handoff

Research outputs signals to arbitration:

```python
from ai_trading_tool.arbitration import SignalReceiver

receiver = SignalReceiver()

# Register research signal
receiver.register(
    engine_name="qlib",
    signal=ResearchSignal(
        symbol="AAPL",
        alpha_score=0.75,
        confidence=0.8,
        regime="trending_up",
    ),
)
```

## Qlib Integration Points

| Qlib Component | Our Wrapper | Purpose |
|----------------|-------------|---------|
| DatasetHDF5 | DataLoader | Load market data |
| Alpha158 | FeatureEngine | Feature computation |
| LabelGenerator | LabelBuilder | Label construction |
| BacktestDAG | BacktestEngine | Strategy backtesting |
| ModelGNNTrainer | ModelTrainer | Model training |
| DumpTreatment | DatasetBuilder | Dataset versioning |

## Configuration

Research configuration in `config/env/production.yaml`:

```yaml
research:
  qlib:
    provider: local
    data_path: "./data/qlib"
    region: us
  
  features:
    lookback: 20
    horizon: 1
  
  labels:
    method: return
    horizon: 5
  
  walk_forward:
    train_window: 252
    test_window: 63
    step: 21
  
  rolling_retrain:
    enabled: true
    frequency: monthly
    lookback: 252
  
  degradation:
    sharpe_threshold: 1.5
    drawdown_threshold: 0.15
    alert_enabled: true
```
