# Phase 9：策略池与多策略组合

## 概述

Phase 9 在 Phase 1–8 主干系统之上，接入具体策略、策略池管理、多策略组合与策略评估机制。

**不重写**：Phase 3 执行层、Phase 4 研究工厂、Phase 6 仲裁层、Phase 7 风控层。

---

## 文件树

```
core/strategy_pool/
├── schemas/
│   ├── strategy.py            # StrategySpec + StrategyStatus + StrategyType
│   ├── signal_bundle.py       # SignalBundle（策略层统一打包对象）
│   ├── portfolio.py           # StrategyPortfolio + StrategyWeight
│   └── arbitration_input.py   # ArbitrationInputBundle + StrategyProposal + PortfolioProposal
├── registry/
│   └── strategy_registry.py   # StrategyRegistry（append-only）
├── builders/
│   ├── base.py               # StrategyBuilder 抽象基类
│   ├── trend.py              # TrendFollowingStrategy（MA cross）
│   ├── mean_reversion.py      # MeanReversionStrategy（RSI + Bollinger Bands）
│   ├── breakout.py            # BreakoutStrategy（20d high/low 突破）
│   └── reversal.py            # ReversalStrategy（短期反转）
├── portfolio/
│   ├── composer.py           # MultiStrategyComposer
│   └── weight_allocator.py   # WeightAllocator（Equal/IR/InverseVol；RiskParity 封装 Phase 4B）
├── backtest/
│   └── evaluator.py          # StrategyEvaluator（绩效指标）
├── lifecycle/
│   └── manager.py            # StrategyLifecycleManager
└── interfaces/
    └── arbitration_bridge.py  # ArbitrationInputBridge → ArbitrationInputBundle

tests/unit/test_strategy_pool/
├── test_strategy_schema.py    # 11 tests
├── test_strategy_registry.py  # 8 tests
├── test_strategies.py         # 12 tests（4 策略 × 3 场景）
├── test_composer.py          # 7 tests
├── test_weight_allocator.py  # 8 tests
└── test_lifecycle.py         # 8 tests

tests/integration/
└── test_strategy_pool_closed_loop.py  # 6 tests

docs/architecture/
└── phase9_strategy_pool.md   # 本文档
```

---

## 职责矩阵

| 文件 | 职责 |
|------|------|
| `schemas/strategy.py` | StrategySpec + StrategyStatus + StrategyType |
| `schemas/signal_bundle.py` | 策略层统一打包（不自建信号系统） |
| `schemas/portfolio.py` | 策略组合权重配置 |
| `schemas/arbitration_input.py` | 仲裁输入对象（StrategyProposal / PortfolioProposal / ArbitrationInputBundle） |
| `registry/strategy_registry.py` | append-only 注册表：register/activate/deactivate/deprecate |
| `builders/base.py` | StrategyBuilder 抽象基类 |
| `builders/trend.py` | 趋势跟踪（MA 交叉 + 动量确认） |
| `builders/mean_reversion.py` | 均值回归（RSI + 布林带） |
| `builders/breakout.py` | 突破（20d 高低点 + 成交量确认） |
| `builders/reversal.py` | 反转（N 日收益率阈值 + 成交量萎缩确认） |
| `portfolio/composer.py` | 多策略信号聚合 + 冲突仲裁 |
| `portfolio/weight_allocator.py` | EqualWeight / IRWeight / InverseVolWeight；RiskParity 封装 Phase 4B |
| `backtest/evaluator.py` | IR / Sharpe / MaxDD / WinRate / Calmar / Sortino |
| `lifecycle/manager.py` | CANDIDATE → ACTIVE → INACTIVE → DEPRECATED 状态机 |
| `interfaces/arbitration_bridge.py` | StrategyPortfolio → ArbitrationInputBundle 桥接 |

---

## 生命周期

```
[单策略开发]
  StrategyBuilder.generate_signals(data, params)
  → SignalBundle[]

[单策略注册]
  StrategyRegistry.register(StrategySpec)
  → status=CANDIDATE

[上线决策]
  LifecycleManager.activate(strategy_id)
  → CANDIDATE → ACTIVE

[多策略组合]
  MultiStrategyComposer.compose(bundles_by_strategy, weights, portfolio_id)
  ├─ 信号聚合（bundle 合并 / 冲突仲裁）
  ├─ WeightAllocator（EqualWeight / IRWeight / RiskParity）
  └─ PortfolioProposal

[仲裁输入产出]
  ArbitrationInputBridge.build(PortfolioProposal, factor_ids, regime_context)
  → ArbitrationInputBundle
  → Phase 6 正式消费 → ArbitrationDecision[]

[策略启停]
  LifecycleManager.deactivate   → ACTIVE → INACTIVE
  LifecycleManager.reactivate   → INACTIVE → ACTIVE
  LifecycleManager.deprecate     → INACTIVE → DEPRECATED
```

---

## 与 Phase 4 / 6 / 7 的边界

### Phase 9 ↔ Phase 4

- **Backtest 复用**：`backtest/evaluator.py` 复用 Phase 4C 回测引擎，不重造回测底盘
- **Portfolio 复用**：`weight_allocator.py` 中 RiskParity 封装调用 Phase 4B optimizer
- **不修改**：Phase 9 不修改 Phase 4 的 FactorRegistry / DatasetAdapter / AlphaBuilder

### Phase 9 → Phase 6

```
Phase 9                          Phase 6
  MultiStrategyComposer
    → PortfolioProposal
    → ArbitrationInputBundle  ──→ 正式消费
                                   → ArbitrationDecision[]
```

- Phase 9 输出 `ArbitrationInputBundle`（含 PortfolioProposal + StrategyProposal[]）
- Phase 6 正式消费后产出真正的 `ArbitrationDecision[]`
- Phase 9 **不直接产出** `ArbitrationDecision`

### Phase 9 → Phase 7

- 所有策略级仓位通过 Phase 7 风控
- StrategySpec.risk_limits 预设值由 Phase 7 RiskLimits 最终约束

---

## SignalBundle 语义

SignalBundle **不是底层信号系统**，而是策略输出的标准化包装：

```python
class SignalBundle:
    bundle_id: str
    source_strategy_id: str      # 策略 ID
    symbol: str
    direction: LONG / SHORT / FLAT
    strength: float (0-1)        # 信号强度
    confidence: float (0-1)      # 置信度
    supporting_signals: List[str]    # 其他模块信号 ID（仅引用）
    supporting_snapshots: List[str]  # Phase 4 因子 ID（仅引用）
    metadata: dict
```

---

## 权重分配方法

| 方法 | 逻辑 | 复用说明 |
|------|------|---------|
| `equal` | 等权重 | — |
| `inverse_vol` | 波动率倒数 | — |
| `ir` | 信息比率（IR 越大权重越高） | — |
| `risk_parity` | 风险平价 | 封装 Phase 4B PortfolioOptimizer，降级为 InverseVol |

---

## 验收清单

| # | 验收项 | 文件 | 状态 |
|---|--------|------|:----:|
| F9-S1 | StrategySpec + StrategyStatus | `schemas/strategy.py` | ✅ |
| F9-S2 | SignalBundle | `schemas/signal_bundle.py` | ✅ |
| F9-S3 | StrategyPortfolio + StrategyWeight | `schemas/portfolio.py` | ✅ |
| F9-S4 | ArbitrationInputBundle + Proposal 系列 | `schemas/arbitration_input.py` | ✅ |
| F9-R1 | StrategyRegistry append-only | `registry/strategy_registry.py` | ✅ |
| F9-B1 | StrategyBuilder 基类 | `builders/base.py` | ✅ |
| F9-B2 | TrendFollowingStrategy | `builders/trend.py` | ✅ |
| F9-B3 | MeanReversionStrategy | `builders/mean_reversion.py` | ✅ |
| F9-B4 | BreakoutStrategy + ReversalStrategy | `builders/breakout.py` + `reversal.py` | ✅ |
| F9-P1 | MultiStrategyComposer | `portfolio/composer.py` | ✅ |
| F9-P2 | WeightAllocator（Equal/IR/InverseVol；RiskParity 封装 Phase 4B） | `portfolio/weight_allocator.py` | ✅ |
| F9-BT1 | StrategyEvaluator | `backtest/evaluator.py` | ✅ |
| F9-L1 | StrategyLifecycleManager | `lifecycle/manager.py` | ✅ |
| F9-I1 | ArbitrationInputBridge → ArbitrationInputBundle | `interfaces/arbitration_bridge.py` | ✅ |
| F9-T1 | Schema 单元测试（11） | `test_strategy_schema.py` | ✅ |
| F9-T2 | Registry 单元测试（8） | `test_strategy_registry.py` | ✅ |
| F9-T3 | Builders 单元测试（12） | `test_strategies.py` | ✅ |
| F9-T4 | Composer 单元测试（7） | `test_composer.py` | ✅ |
| F9-T5 | WeightAllocator 单元测试（8） | `test_weight_allocator.py` | ✅ |
| F9-T6 | Lifecycle 单元测试（8） | `test_lifecycle.py` | ✅ |
| F9-T7 | Integration 闭环测试（6） | `test_strategy_pool_closed_loop.py` | ✅ |
| F9-D1 | Phase 9 架构文档 | `docs/architecture/phase9_strategy_pool.md` | ✅ |

**Phase 9 完成度：20/20 验收项 ✅  
测试：65/65 通过 ✅**
