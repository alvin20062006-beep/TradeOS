# 项目总览 — ai-trading-tool

> **最后更新**：2026-04-13  
> **系统状态**：Phase 1–10 总封板测试通过（271/271）  
> **系统定位**：非生产级自动交易研究框架（交易策略研究 + 信号生成 + 回测验证）

---

## 一、系统架构总图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Phase 1: 数据层                            │
│              Alpha 数据 → Qlib Format → Handler                  │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Phase 2: Alpha 因子系统                       │
│  technical / fundamentals / sentiment / composite builders         │
│  → FeatureSetVersion → registry                                  │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Phase 3: Qlib 研究工厂                         │
│  FeatureSetVersion → LabelSetVersion → model training            │
│  → ResearchExperimentRecord → ModelArtifact → SignalCandidate      │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Phase 4: 回测引擎                              │
│  BacktestEngine → CostModel → Evaluator → BacktestResult        │
│  ⚠️ 执行层适配器（Phase 3 adapter）存在但 import path 旧          │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Phase 5: 分析引擎                               │
│  TechnicalSignal / ChanSignal / OrderflowSignal / SentimentSignal│
│  → SignalBundle → DirectionalSignal[]                            │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
               ┌──────────────┴──────────────┐
               ↓                             ↓
┌──────────────────────────┐   ┌──────────────────────────┐
│  Phase 6（旧入口）        │   │  Phase 10（新入口）      │
│  arbitrate()             │   │  arbitrate_portfolio()   │
│  DirectionalSignal[]     │   │  StrategySignalBundle[]  │
└──────────┬───────────────┘   └──────────┬───────────────┘
           │         共用内部规则链          │
           │    _evaluate_and_decide()       │
           └──────────────┬─────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Phase 6: 仲裁层                              │
│  5 条规则链：FundamentalVeto / MacroAdj / DirConflict /          │
│              ConfWeight / RegimeFilter                            │
│  → ArbitrationDecision { bias, confidence, rationale,            │
│                          rules_applied, signal_count }            │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Phase 7: 风控引擎                            │
│  7 个过滤器：LossLimit / RegimeBased / PosLimit / Liquidity /    │
│             VolCap / FactorExposure / Fundamental                │
│  Sizing chain：FixedNotional / VolTarget / Kelly / ... / MaxPos │
│  → ExecutionPlanner → ExecutionPlan { algorithm, limit_price }   │
│  → PositionPlan { final_quantity, veto_triggered, limit_checks } │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Phase 8: 审计反馈                            │
│  DecisionAuditor.ingest()   → DecisionRecord                     │
│  RiskAuditor.ingest()       → RiskAudit                         │
│  ExecutionAuditor.ingest()  → ExecutionRecord ⚠️ 结构就绪        │
│  FeedbackEngine.scan()      → Feedback[]                         │
│  FeedbackRegistry.append()   → append-only 持久化                 │
│  Phase4Updater              → suggestion-only ⚠️ pending→reviewed│
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Phase 9: 策略池                                 │
│  StrategyBuilder[] → MultiStrategyComposer                       │
│  → PortfolioProposal → StrategySignalBundle[]                    │
│  → ArbitrationInputBridge → ArbitrationInputBundle                │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
                     Phase 10: 集成层（闭环入口）
```

---

## 二、Phase 目录结构

```
ai-trading-tool/
├── core/
│   ├── arbitration/           # Phase 6 仲裁层 + Phase 10 集成入口
│   ├── risk/                 # Phase 7 风控引擎
│   ├── audit/                # Phase 8 审计反馈
│   │   ├── engine/           # DecisionAuditor / RiskAuditor / ExecutionAuditor
│   │   ├── feedback/         # FeedbackEngine + 4 类 feedback 类型
│   │   ├── closed_loop/      # FeedbackRegistry / ReviewManager
│   │   └── schemas/         # DecisionRecord / RiskAudit / ExecutionRecord / Feedback
│   ├── strategy_pool/        # Phase 9 策略池
│   │   ├── interfaces/       # ArbitrationInputBridge
│   │   └── schemas/          # StrategySignalBundle / PortfolioProposal / StrategyProposal
│   ├── research/             # Phase 3 Qlib 研究工厂
│   │   ├── qlib/            # result_adapter / baseline_workflow
│   │   ├── backtest/        # BacktestEngine / CostModel / Evaluator
│   │   └── strategy/         # StrategyBase / StrategySignal
│   ├── execution/            # Phase 3 执行适配层 ⚠️ 旧 import path
│   ├── alpha/                # Phase 2 Alpha 因子
│   └── schemas.py            # 统一 schema（核心数据类型）
├── datasets/                  # Phase 1 数据集
├── tests/
│   ├── unit/                 # Phase 单元测试
│   └── integration/          # 集成测试 + 全流程测试
└── docs/
    └── architecture/          # 本文档
```

---

## 三、Schema 架构（核心数据类型）

### 关键 Schema 关系

```
ArbitrationDecision (Phase 6) ──→ Phase 7 ──→ PositionPlan
    │                              │
    │ direction                    │ execution_plan
    │ bias                         ↓
    │ confidence              ExecutionPlan
    │ rationale                    │
    │ rules_applied               ↓
    │                          Phase 8
    │                          ↓
DecisionRecord ←──── DecisionAuditor.ingest()
RiskAudit    ←────  RiskAuditor.ingest()
ExecutionRecord ←── ExecutionAuditor.ingest() ⚠️
Feedback[]   ←────  FeedbackEngine.scan()
```

### Schema 命名空间

| Schema | 位置 | 用途 |
|--------|------|------|
| `ArbitrationDecision` | `core.schemas` | Phase 6-7 通信标准格式 |
| `ArbitrationDecision` | `core.arbitration.schemas` | Phase 6 内部输出（含 bias）|
| `PositionPlan` | `core.risk.schemas` | Phase 7 输出 |
| `ExecutionPlan` | `core.risk.schemas` | Phase 7 → Phase 3 适配层 |
| `DecisionRecord` | `core.audit.schemas.decision_record` | Phase 8 审计快照 |
| `RiskAudit` | `core.audit.schemas.risk_audit` | Phase 8 风控审计快照 |
| `ExecutionRecord` | `core.audit.schemas.execution_record` | Phase 8 执行审计快照 |
| `Feedback` | `core.audit.schemas.feedback` | Phase 8 系统反馈 |
| `StrategySignalBundle` | `core.strategy_pool.schemas.signal_bundle` | Phase 9 策略信号 |
| `ArbitrationInputBundle` | `core.strategy_pool.schemas.arbitration_input` | Phase 9 → Phase 10 输入 |

---

## 四、API 入口清单

| 入口 | Phase | 说明 |
|------|-------|------|
| `ArbitrationEngine.aribtrate()` | 6 | 旧入口：消费 TechnicalSignal 等 Phase 5 信号 |
| `ArbitrationEngine.aribtrate_portfolio()` | 10 | 新入口：消费 ArbitrationInputBundle（Phase 9）|
| `RiskEngine.calculate()` | 7 | 消费 ArbitrationDecision → PositionPlan |
| `DecisionAuditor.ingest()` | 8 | 消费 ArbitrationDecision → DecisionRecord |
| `RiskAuditor.ingest()` | 8 | 消费 PositionPlan → RiskAudit |
| `ExecutionAuditor.ingest()` | 8 | 消费 ExecutionResult → ExecutionRecord ⚠️ |
| `FeedbackEngine.scan()` | 8 | 批处理：DecisionRecord[] + ExecutionRecord[] + RiskAudit[] → Feedback[] |
| `ArbitrationInputBridge.build()` | 9 | PortfolioProposal → ArbitrationInputBundle |

---

## 五、关键约束（系统边界）

| 约束 | 描述 |
|------|------|
| 非生产级 | 本系统为研究框架，不连接真实经纪商 |
| 双重入口 | `aribtrate()` 和 `arbitrate_portfolio()` 共存，共享同一规则链 |
| Schema 解耦 | Phase 8 审计 snapshot 与 Phase 6/7 运行时对象完全解耦 |
| Append-only | FeedbackRegistry 只追加，不覆盖 |
| Suggestion-only | Phase4Updater 只输出建议，不直接修改 Phase 4 registry |
| Symbol 提取 | Phase 10 从 StrategySignalBundle.symbol 提取真实 symbol，不使用 portfolio_id |
