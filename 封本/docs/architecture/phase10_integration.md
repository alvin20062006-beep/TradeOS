# Phase 10 架构文档：Phase 9 → Phase 6 正式集成

## 目的

完成 Phase 9（策略池）到 Phase 6（仲裁层）的正式接入验证。
将 StrategyPool 的多策略聚合输出接入 ArbitrationEngine，
使策略池决策可参与完整的"仲裁 → 风控 → 执行计划 → 审计反馈"链路。

## 接入架构

### 数据流图

```
Phase 9 StrategyPool
    ├── StrategyBuilder[] → MultiStrategyComposer.compose()
    │       → PortfolioProposal
    │              ├── proposals: StrategyProposal[]
    │              │        ├── strategy_id
    │              │        ├── aggregate_direction ("LONG"/"SHORT"/"FLAT")
    │              │        ├── aggregate_confidence (0-1)
    │              │        ├── aggregate_strength (0-1)
    │              │        └── portfolio_weight (0-1)
    │              │
    │              └── composite_direction / composite_confidence
    │
    └── ArbitrationInputBridge.build()
            → ArbitrationInputBundle
                    │
                    ▼
Phase 6 ArbitrationEngine.arbitrate_portfolio()
    │
    ├── 1. SignalCollector.collect(symbol) ← 提取真实 symbol
    ├── 2. derive_direction_and_confidence(bundle) ← Phase 5 信号
    ├── 3. _StrategySignalSource → to_directional()
    │        engine_name = "strategy_pool:{strategy_id}"
    │        direction ← aggregate_direction
    │        confidence ← aggregate_confidence
    │        weight ← portfolio_weight
    │        → DirectionalSignal[] 追加到规则链
    │
    ├── 4. 早退出检查（无任何信号）
    │
    ├── 5. _evaluate_and_decide() ← 与 arbitrate() 共用内部链
    │        ├── FundamentalVetoRule (universal，可覆盖 strategy_pool)
    │        ├── MacroAdjustmentRule (universal，可覆盖 strategy_pool)
    │        ├── DirectionConflictRule (平等参与)
    │        ├── ConfidenceWeightRule (平等参与)
    │        └── RegimeFilterRule (平等参与)
    │
    └── ArbitrationDecision { bias, confidence, rationale }
            │
            ▼
Phase 7 RiskEngine.calculate()
    └── PositionPlan { final_quantity, execution_plan, limit_checks }
            │
            ▼
Phase 8 DecisionAuditor.ingest() / RiskAuditor.ingest()
    └── DecisionRecord / RiskAudit
            │
            ▼
Phase 8 FeedbackEngine.scan() → Feedback[]
    └── FeedbackRegistry.append()
```

## 两个入口的边界

| 属性 | `arbitrate()` | `arbitrate_portfolio()` |
|------|--------------|-------------------------|
| 输入来源 | Phase 5 分析引擎 | Phase 9 策略池 |
| 入口签名 | `arbitrate(symbol, technical, chan, ...)` | `arbitrate_portfolio(arb_in)` |
| 信号转换 | `derive_direction_and_confidence()` | `_StrategySignalSource.to_directional()` |
| 规则链 | **完全共用** | **完全共用** |
| 内部方法 | `_evaluate_and_decide()` | `_evaluate_and_decide()` |
| 输出 | `ArbitrationDecision` | `ArbitrationDecision` |
| 逻辑复制 | **零复制** | **零复制** |

### 复用关系图

```
                    ArbitrationEngine
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
  arbitrate()    arbitrate_portfolio()   _evaluate_and_decide()
  (Phase 5)       (Phase 9)               (内部共用)
        │                  │                  │
        ▼                  ▼                  ▼
  SignalCollector    Symbol 提取          5 规则链
        │                  │
        ▼                  ▼
  derive_direction   _StrategySignalSource
  _and_confidence    → to_directional()
        │                  │
        └────────┬─────────┘
                 ▼
          DirectionalSignal[]
                 │
                 ▼
        _evaluate_and_decide()
                 │
         ┌───────┴───────┐
         ▼               ▼
  规则链 (5条)    EnsembleScorer
         │
         ▼
  ArbitrationDecision
```

## strategy_pool 信号源语义

### 与五类基础分析信号的区别

| 信号源 | engine_name | 性质 | 参与规则 |
|--------|-------------|------|---------|
| technical | `technical` | 原始市场分析 | 全部 5 条 |
| chan | `chan` | 原始市场分析 | 全部 5 条 |
| orderflow | `orderflow` | 原始市场分析 | 全部 5 条 |
| sentiment | `sentiment` | 原始市场分析 | 全部 5 条 |
| macro | `macro` | 原始市场分析 | 全部 5 条 |
| **strategy_pool** | **`strategy_pool:{strategy_id}`** | **多策略聚合决策（已仲裁）** | **全部 5 条** |

### 规则对 strategy_pool 的处理

| 规则 | 优先级 | 对 strategy_pool 的处理 | 原因 |
|------|:------:|------------------------|------|
| FundamentalVetoRule | 1 (最高) | **universal — 覆盖** | 基本盘 D 级是硬约束，无论信号来源 |
| MacroAdjustmentRule | 2 | **universal — 覆盖** | 宏观系统性风险不因策略池而豁免 |
| DirectionConflictRule | 3 | **平等参与** | 多空冲突检测适用于所有方向信号 |
| ConfidenceWeightRule | 4 | **平等参与** | 置信度权重适用于所有信号 |
| RegimeFilterRule | 5 (最低) | **平等参与**（含灵活性） | 特定 regime 下可额外降低权重 |

### 默认权重处理

Phase 9 传入的 `portfolio_weight` 直接映射为 `DirectionalSignal.weight`，不进行二次调整。
Phase 9 传入的 `aggregate_confidence` 直接映射为 `DirectionalSignal.confidence`。

如果 `portfolio_weight = 0`（未分配权重），`to_directional()` 默认返回 `weight = 1.0`。

## 与 Phase 1-9 的边界

### Phase 9 负责的部分

- `core/strategy_pool/schemas/arbitration_input.py`：输入 schema
- `core/strategy_pool/interfaces/arbitration_bridge.py`：输入转换
- `core/strategy_pool/`：策略池生命周期管理

### Phase 6 负责的部分

- `core/arbitration/schemas.py`：` ArbitrationInputBundle`（作为 type hint）和 `_StrategySignalSource`（桥接对象）
- `core/arbitration/engine.py`：`arbitrate_portfolio()` 和 `_evaluate_and_decide()`

### 不涉及的部分

| Phase | 边界 |
|-------|------|
| Phase 1-3 | 数据层、研究工厂 — 无需修改 |
| Phase 4 | Alpha 因子系统 — 无需修改 |
| Phase 5 | 分析引擎 — 无需修改 |
| Phase 7 | 风控引擎 — 无需修改（消费 ` ArbitrationDecision`）|
| Phase 8 | 审计反馈 — 无需修改（消费 ` ArbitrationDecision`）|

## Symbol 提取策略

Phase 9 `ArbitrationInputBundle` 中 symbol 的来源优先级：

1. `StrategySignalBundle.symbol`（从 Phase 9 各策略 builder 产生）
2. `PortfolioProposal.portfolio_id` 解析（取第一段，如 "AAPL" from "AAPL-SP"）
3. 默认 "UNKNOWN"（不阻塞，早退出返回 `no_trade`）

## 文件清单

| 文件 | 操作 | 职责 |
|------|:----:|------|
| `core/arbitration/schemas.py` | 修改 | 新增 `_StrategySignalSource` 桥接对象 |
| `core/arbitration/engine.py` | 修改 | 新增 `arbitrate_portfolio()` + `_evaluate_and_decide()` 重构 |
| `tests/unit/test_arbitration_portfolio.py` | 新增 | 单元测试（13 个） |
| `tests/integration/test_phase10_closed_loop.py` | 新增 | Integration 测试（5 个） |
| `docs/architecture/phase10_integration.md` | 新增 | 本文档 |

## 验收清单

| ID | 验收项 | 验证方式 |
|----|--------|---------|
| F10-S1 | `_StrategySignalSource` 方向映射正确 | 单元测试 |
| F10-S2 | 置信度 / 权重正确传递 | 单元测试 |
| F10-S3 | 两个入口共用 `_evaluate_and_decide()` | 代码审查 |
| F10-S4 | `arbitrate_portfolio()` 不破坏原有 `arbitrate()` | 单元测试 |
| F10-I1 | Phase 9 ArbitrationInputBundle 被 Phase 6 实际消费 | Integration 测试 |
| F10-I2 | Phase 6 产出正式 ArbitrationDecision | Integration 测试 |
| F10-I3 | Phase 6 输出被 Phase 7 正确消费 | Integration 测试 |
| F10-I4 | Phase 8 生成 DecisionRecord / RiskAudit / Feedback | Integration 测试 |
| F10-I5 | 原有 Phase 5 → arbitrate() 路径不被破坏 | 全量回归 |
| F10-R1 | 多策略反向时 DirectionConflictRule 触发 | Integration 测试 |
| F10-R2 | FundamentalVetoRule / MacroAdjustmentRule 对 strategy_pool 仍有覆盖效果 | 单元测试（隐含在规则链复用中）|
| F10-R3 | 空 portfolio graceful 降级 | 单元测试 |
| F10-E1 | 全量回归（Phase 6-9 + Phase 10）：192/192 | pytest |
| F10-D1 | 本文档完整 | 人工审核 |
