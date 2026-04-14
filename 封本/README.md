# ai-trading-tool

> **状态**：Phase 1–10 总封板测试通过（271/271）  
> **系统定位**：非生产级自动交易研究框架（AI 交易策略研究 + 信号生成 + 回测验证）  
> **更新时间**：2026-04-13

---

## 系统架构

```
Phase 1-5: 数据 → Alpha因子 → Qlib研究 → 回测 → 分析信号
                    ↓
Phase 6: 仲裁层（双重入口）
    ├─ arbitrate()        ← 旧入口（Phase 5 信号）
    └─ arbitrate_portfolio() ← 新入口（Phase 9 策略池）
                    ↓
Phase 7: 风控引擎（7过滤器 + 6种仓位算法）
                    ↓
Phase 8: 审计反馈（DecisionRecord + RiskAudit + Feedback）
                    ↓
Phase 9: 策略池（多策略聚合 → 反馈给仲裁层）
```

详细架构见 [`docs/architecture/project_master_overview.md`](docs/architecture/project_master_overview.md)。

---

## 目录结构

```
ai-trading-tool/
├── core/                        # 核心代码
│   ├── arbitration/            # Phase 6 仲裁层 + Phase 10 集成
│   ├── risk/                  # Phase 7 风控引擎
│   ├── audit/                 # Phase 8 审计反馈
│   │   ├── engine/            # Decision/Risk/Execution Auditor
│   │   ├── feedback/         # FeedbackEngine + 4类Feedback
│   │   └── closed_loop/       # FeedbackRegistry + ReviewManager
│   ├── strategy_pool/         # Phase 9 策略池
│   │   └── interfaces/        # ArbitrationInputBridge
│   └── research/              # Phase 3 Qlib 研究工厂
│       ├── qlib/             # result_adapter + baseline_workflow
│       └── backtest/          # BacktestEngine + CostModel + Evaluator
├── datasets/                   # Phase 1 数据集
├── tests/                      # 测试套件
│   ├── unit/                  # 单元测试
│   └── integration/            # 集成测试 + 全流程测试
└── docs/architecture/          # 架构文档
```

---

## 快速开始

### 安装

```bash
pip install -e .
```

### 运行测试

```bash
# 全量测试（排除旧 import path 的历史遗留文件）
pytest tests/unit/ tests/integration/ \
    --ignore=tests/unit/test_data_adapter.py \
    --ignore=tests/unit/test_schemas.py \
    --ignore=tests/integration/test_backtest_min_loop.py \
    -q

# 仅 Phase 6-10 主干测试
pytest tests/unit/test_arbitration_engine.py \
       tests/unit/test_arbitration_portfolio.py \
       tests/unit/test_audit/ \
       tests/integration/test_phase10_closed_loop.py \
       tests/integration/test_full_system_closed_loop.py \
       -v
```

### 核心 API 用法

#### 旧入口：Phase 5 信号 → 仲裁 → 风控

```python
from core.arbitration import ArbitrationEngine
from core.risk.engine import RiskEngine
from core.schemas import TechnicalSignal, Direction, Regime, Portfolio

engine = ArbitrationEngine()
risk_engine = RiskEngine()

# Phase 5: 产出分析信号
tech = TechnicalSignal(
    engine_name="technical",
    symbol="AAPL",
    timestamp=datetime.utcnow(),
    direction=Direction.LONG,
    confidence=0.85,
    regime=Regime.TRENDING_UP,
)

# Phase 6: 仲裁
decision = engine.arbitrate(symbol="AAPL", timestamp=datetime.utcnow(), technical=tech)
print(f"Bias: {decision.bias}, Confidence: {decision.confidence}")

# Phase 7: 风控
portfolio = Portfolio(...)  # 组合状态
plan = risk_engine.calculate(decision=decision, portfolio=portfolio, current_price=155.0)
print(f"Position: {plan.final_quantity}, Vetoed: {plan.veto_triggered}")
```

#### 新入口：Phase 9 策略池 → 仲裁 → 风控

```python
from core.arbitration import ArbitrationEngine
from core.strategy_pool.interfaces.arbitration_bridge import ArbitrationInputBridge
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle
from core.strategy_pool.schemas.arbitration_input import PortfolioProposal, StrategyProposal

bridge = ArbitrationInputBridge()
engine = ArbitrationEngine()

bundle = StrategySignalBundle(
    bundle_id="bundle-001",
    source_strategy_id="trend",
    symbol="AAPL",
    timestamp=datetime.utcnow(),
    direction="LONG",
    strength=0.75,
    confidence=0.80,
)
proposal = StrategyProposal(
    proposal_id="p-001",
    strategy_id="trend",
    bundles=[bundle],
    aggregate_direction="LONG",
    aggregate_strength=0.75,
    aggregate_confidence=0.80,
    portfolio_weight=1.0,
)
pp = PortfolioProposal(
    proposal_id="pp-001",
    portfolio_id="AAPL-SP",
    proposals=[proposal],
    composite_direction="LONG",
    composite_strength=0.75,
    composite_confidence=0.80,
    weight_method="equal",
)

arb_in = bridge.build(pp)
decision = engine.arbitrate_portfolio(arb_in)
print(f"Bias: {decision.bias}, Rules: {decision.rules_applied}")
```

#### Phase 8: 审计反馈

```python
from core.audit.engine.decision_audit import DecisionAuditor
from core.audit.engine.risk_audit import RiskAuditor
from core.audit.feedback.engine import FeedbackEngine

dec_auditor = DecisionAuditor()
risk_auditor = RiskAuditor()
fb_engine = FeedbackEngine()

dec_rec = dec_auditor.ingest(decision)
risk_aud = risk_auditor.ingest(plan)
feedbacks = fb_engine.scan(
    decision_records=[dec_rec],
    execution_records=[],
    risk_audits=[risk_aud],
)
```

---

## 测试结果（2026-04-13）

| 测试集 | 通过/总数 | 状态 |
|--------|:---------:|:----:|
| Phase 6 仲裁层 | 59/59 | ✅ |
| Phase 7 风控引擎 | 47/47 | ✅ |
| Phase 8 审计反馈 | 42/42 | ✅ |
| Phase 9 策略池 | 64/64 | ✅ |
| Phase 10 集成 | 23/23 | ✅ |
| Phase 1-3 集成 | 21/21 | ✅ |
| **合计** | **271/271** | ✅ |

---

## 关键约束

| 约束 | 说明 |
|------|------|
| **非生产级** | 本系统为研究框架，不连接真实经纪商，不可用于实盘交易 |
| **双重入口** | `aribtrate()` 和 `arbitrate_portfolio()` 共存，共享同一规则链 |
| **Schema 解耦** | Phase 8 审计 snapshot 与 Phase 6/7 运行时对象完全解耦 |
| **Append-only** | FeedbackRegistry 只追加，不覆盖历史记录 |
| **Suggestion-only** | Phase4Updater 只输出建议，不直接修改 Phase 4 registry |

---

## 文档索引

| 文档 | 内容 |
|------|------|
| `docs/architecture/project_master_acceptance.md` | 总验收报告 |
| `docs/architecture/project_master_overview.md` | 系统总览与架构图 |
| `docs/architecture/full_system_test_report.md` | 全流程测试报告 |
| `docs/architecture/project_closed_loop_report.md` | 闭环验证报告 |
| `docs/architecture/phase10_integration.md` | Phase 10 集成架构 |
| `docs/architecture/phase11_productization_plan.md` | 产品化层完整规划 |
| `docs/architecture/phase11_deployment_guide.md` | 产品化层部署指南 |
| `docs/architecture/phase11_final_acceptance.md` | 产品化层总验收报告 |
| `apps/API.md` | API 参考（12 端点） |
| `apps/CLI.md` | CLI 使用说明 |
| `apps/CONSOLE.md` | Streamlit Console 使用说明 |
| `apps/PERMISSION.md` | 权限说明 |

---

## 产品化层（Productization Layer）

### 启动

```bash
python run.py api        # API: http://localhost:8000
python run.py console    # Console: http://localhost:8501
python run.py all        # 同时启动 API + Console
```

### API 端点（12 个）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/version` | GET | 版本信息 |
| `/system/status` | GET | 统一状态面板 |
| `/system/modules` | GET | 模块就绪探测 |
| `/api/v1/analysis/run` | POST | Phase 5 分析 |
| `/api/v1/arbitration/run` | POST | 旧入口仲裁 |
| `/api/v1/arbitration/run-portfolio` | POST | 策略池仲裁 |
| `/api/v1/risk/calculate` | POST | Phase 7 风控 |
| `/api/v1/audit/*` | GET/POST | 审计查询 + Feedback 扫描 |
| `/api/v1/strategy-pool/propose` | POST | 策略池提案 |
| `/api/v1/pipeline/run-full` | POST | 全链路 Phase 5→6→7 |
| `/api/v1/auth/*` | GET | 权限 + 审计轨迹 |

详见 [`apps/API.md`](apps/API.md)

### 核心约束

- **不改 Phase 1-10 核心语义**
- **只通过 DTO / view model 暴露能力**
- **不新增 registry 真值写入口**
- **AI 只能通过产品化层 DTO 进出**
- **append-only / suggestion-only 原则不变**

### 产品化层文件结构

```
apps/
├── api/            FastAPI 应用（12 端点）
├── dto/            两层 DTO（api/ + view/）
├── auth/           轻量权限层（SQLite + role enum）
├── cli.py          CLI 命令入口（click）
├── console/        Streamlit 控制台（6 面板）
├── API.md          API 参考
├── CLI.md          CLI 使用说明
├── CONSOLE.md      Console 使用说明
└── PERMISSION.md   权限说明
```

---

## 已知限制

- Phase 4/Phase 3 执行层 adapter 使用旧 import path（`ai_trading_tool.core.*`），需迁移
- Phase 9 → Phase 5 反馈回路（策略池自我迭代）尚未实现
- 真实交易执行（连接经纪商）未实现，系统为纯研究用途
- Task 存储为内存（Feedback 扫描结果重启后丢失）
- Streamlit 为首批控制台方案，后续可替换为正式前端
