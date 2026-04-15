# 产品化层 — 完整规划

**旧称**：Phase 11（已弃用）  
**正式名称**：产品化层 / Productization Layer  
**状态**：实施中  
**时间**：2026-04-13  
**核心原则**：不重写主链，不改核心语义，不越权写 registry

---

## A. 文件树

```
ai-trading-tool/
├── apps/                          ← 【新增】应用层（FastAPI + CLI + Console）
│   ├── __init__.py
│   ├── api/                       ← 【新增】FastAPI 应用
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app factory
│   │   ├── deps.py                # 依赖注入（get_db, get_current_user, get_arb_engine）
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── health.py          # GET /health, GET /version
│   │   │   ├── analysis.py        # POST /analysis/run
│   │   │   ├── arbitration.py     # POST /arbitration/run, POST /arbitration/run-portfolio
│   │   │   ├── risk.py            # POST /risk/calculate
│   │   │   ├── audit.py           # GET /audit/decisions, GET /audit/feedback
│   │   │   ├── strategy_pool.py   # POST /strategy-pool/propose
│   │   │   └── pipeline.py        # POST /pipeline/run-full
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── logging.py         # 请求日志
│   │       └── error_handler.py   # 全局异常处理
│   │
│   ├── dto/                       ← 【新增】两层 DTO（与核心对象完全解耦）
│   │   ├── api/                   # API request / response DTO（HTTP 层）
│   │   │   ├── analysis.py        # AnalysisRequest, AnalysisResponse
│   │   │   ├── arbitration.py      # ArbitrationRequest, PortfolioArbitrationRequest, ArbitrationResponse
│   │   │   ├── risk.py            # RiskRequest, RiskResponse
│   │   │   ├── audit.py           # AuditQueryParams
│   │   │   ├── strategy_pool.py   # StrategyPoolRequest
│   │   │   └── common.py          # Pagination, ErrorResponse, HealthResponse
│   │   └── view/                  # Console / Web 展示用 view model（独立于 API）
│   │       ├── analysis.py        # AnalysisSignalView
│   │       ├── arbitration.py     # ArbitrationDecisionView
│   │       ├── risk.py            # PositionPlanView, LimitCheckView
│   │       ├── audit.py           # DecisionRecordView, RiskAuditView, FeedbackView
│   │       └── dashboard.py       # SystemStatusView, OverviewView
│   │
│   ├── cli/                       ← 【新增】CLI 命令入口
│   │   ├── __init__.py
│   │   ├── main.py                # typer app factory
│   │   ├── commands/
│   │   │   ├── __init__.py
│   │   │   ├── run.py             # run full-pipeline / analysis / arbitration / risk
│   │   │   ├── audit.py           # audit query / feedback scan / show status
│   │   │   ├── strategy.py        # strategy-pool propose
│   │   │   └── system.py          # health / version / config
│   │   └── output/                # 控制台输出格式化
│   │       ├── __init__.py
│   │       ├── renderers.py       # 通用渲染器
│   │       └── formatters.py      # JSON/Table/Tree 格式化
│   │
│   ├── console/                   ← 【新增】Web 控制台（Streamlit 单文件方案）
│   │   ├── __init__.py
│   │   ├── dashboard.py           # 主面板（overview + status）
│   │   ├── analysis_console.py    # 分析信号面板
│   │   ├── arbitration_console.py # 仲裁控制台
│   │   ├── risk_console.py       # 风控面板
│   │   ├── audit_console.py      # 审计查询面板
│   │   └── strategy_pool_console.py # 策略池面板
│   │
│   └── auth/                      ← 【新增】轻量权限层
│       ├── __init__.py
│       ├── models.py              # User, OperatorRole enum
│       ├── repository.py          # 用户存储（JSON 文件 / SQLite）
│       ├── service.py             # 权限校验服务
│       └── dependencies.py         # FastAPI 依赖注入

├── core/
│   └── schemas/                   ← 【确认】核心 schema 不改动，只做引用
│
├── infra/
│   ├── db/
│   │   └── migrations/            ← 【扩展】Audit 层与 DB 的映射迁移
│   │   └── versions/
│   │       └── 002_audit_layer.sql # DecisionAudit / RiskAudit / Feedback → DB 表
│   │
│   ├── docker/
│   │   ├── Dockerfile            ← 【更新】添加 streamlit / uvicorn
│   │   └── docker-compose.yml    ← 【更新】添加 api / console 服务
│   │
│   └── config/
│       ├── __init__.py           ← 【新增】配置加载（环境变量 + YAML）
│       ├── settings.py            # Pydantic Settings
│       ├── logging.py             # 日志配置
│       └── environments/
│           ├── dev.yaml
│           ├── test.yaml
│           └── prod.yaml
│
├── scripts/
│   ├── start_api.py              ← 【新增】API 启动脚本
│   ├── start_console.py           ← 【新增】Console 启动脚本
│   └── run_pipeline.py            ← 【新增】CLI pipeline 脚本
│
└── README.md                     ← 【更新】产品化层使用说明
```

---

## B. 各模块职责

| 模块 | 职责 | 禁止行为 |
|------|------|---------|
| `apps/api/` | FastAPI HTTP 入口；请求校验；路由分发；错误处理 | ❌ 不直接实例化核心引擎 |
| `apps/dto/` | API 请求/响应模型；与核心对象完全解耦 | ❌ 不引用 Phase 6/7/8 内部对象 |
| `apps/cli/` | 命令行入口；TTY 输出；批量操作 | ❌ 不绕过 API 层直连核心 |
| `apps/console/` | Streamlit Web 控制台；状态可视化 | ❌ 不直接操作 PositionPlan 等内部对象 |
| `apps/auth/` | 轻量用户/角色；权限 gate；审计线索 | ❌ 不做完整 IAM |
| `infra/config/` | 环境变量加载；多环境配置 | ❌ 不硬编码 secrets |
| `infra/db/` | Audit 层 → DB 持久化映射 | ❌ 不直接写 Phase 1-4 registry |

---

## C. API Layer 规划

### 路由清单

| 端点 | 方法 | 说明 | 写权限 |
|------|------|------|--------|
| `/health` | GET | 服务健康检查 | — |
| `/version` | GET | 系统版本信息 | — |
| `/analysis/run` | POST | 触发分析（suggestion-only）| Operator |
| `/arbitration/run` | POST | 旧入口仲裁（单信号）| Operator |
| `/arbitration/run-portfolio` | POST | 新入口仲裁（策略池）| Operator |
| `/risk/calculate` | POST | 风控计算 | Operator |
| `/audit/decisions` | GET | 查询仲裁决策历史 | Viewer+ |
| `/audit/risk` | GET | 查询风控审计历史 | Viewer+ |
| `/audit/feedback` | GET | 查询 Feedback 历史 | Viewer+ |
| `/audit/feedback/tasks` | POST | 提交 Feedback 扫描任务（task-style）| Operator |
| `/audit/feedback/tasks/{task_id}` | GET | 查询扫描任务状态与结果 | Viewer+ |
| `/strategy-pool/propose` | POST | 策略池提案 | Operator |
| `/pipeline/run-full` | POST | 全链路一次运行 | Operator |

### 写权限约束（核心边界）

```
Operator 可写：
  ✅ POST /analysis/run        → 不改 registry，只输出 AnalysisSignal
  ✅ POST /arbitration/run     → 不改 registry，只输出 ArbitrationDecision
  ✅ POST /risk/calculate      → 不改 registry，只输出 PositionPlan
  ✅ POST /audit/feedback/scan → 写 FeedbackRegistry（append-only，设计允许）
  ✅ POST /strategy-pool/propose → 只写 StrategyPool 内存/临时，不写 Phase 4 registry

❌ 任何 API 端点禁止：
  - 修改 Phase 4 model registry 真值
  - 修改 Phase 2 alpha registry 真值
  - 修改 Phase 1 data registry 真值
  - 删除历史 DecisionRecord
```

### DTO 映射规则

```
核心对象                  → API DTO（apps/dto/）
ArbitrationDecision      → ArbitrationResponse { bias, confidence, rationale, symbol, rules_applied }
PositionPlan             → PositionPlanView { final_quantity, veto_triggered, execution_plan }
DecisionRecord           → DecisionRecordView { decision_id, symbol, timestamp, bias, audit_id }
RiskAudit                → RiskAuditView { plan_id, symbol, filters_passed, limit_checks }
Feedback                 → FeedbackView { feedback_id, type, severity, description, created_at }
AnalysisSignal           → AnalysisSignalView { signal_id, symbol, direction, confidence }
```

---

## D. Console Layer 规划（Streamlit）

### 面板清单

| 面板 | 路径 | 核心功能 |
|------|------|---------|
| Dashboard | `/` | 系统状态总览、版本、活跃决策、最新 Feedback |
| Analysis Console | `/analysis` | 符号输入 → 触发分析 → 展示信号 |
| Arbitration Console | `/arbitration` | 单信号仲裁 + 策略池仲裁双入口 |
| Risk Console | `/risk` | 风控计算结果展示 + veto/cap 可视化 |
| Audit Console | `/audit` | DecisionRecord / RiskAudit / Feedback 查询 |
| Strategy Pool Console | `/strategy-pool` | 多策略提案管理 + 权重可视化 |

### 接入方式

Streamlit 作为独立进程，通过 HTTP 调用 API 层（不直连核心 Python 模块）：

```python
# apps/console/dashboard.py（伪代码）
import streamlit as st
import httpx

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")

def get_health():
    r = httpx.get(f"{API_BASE}/health")
    return r.json()

def get_decisions(limit=10):
    r = httpx.get(f"{API_BASE}/audit/decisions", params={"limit": limit})
    return r.json()["items"]
```

---

## E. CLI Layer 规划

### 命令树

```
ai-tool run full-pipeline    --symbol AAPL --direction LONG --confidence 0.85
ai-tool run analysis         --symbol AAPL --data '{"score":0.7,"alpha":0.3}'
ai-tool run arbitration      --symbol AAPL --technical
ai-tool run arbitration      --symbol AAPL --strategy-pool --portfolio-id AAPL-SP
ai-tool run risk             --symbol AAPL --bias long --quantity 100 --price 155.0
ai-tool audit query          --type decisions --symbol AAPL --limit 20
ai-tool audit feedback       --scan --type loss_amplification
ai-tool status               # 显示引擎版本、风控配置、Feedback 最新摘要
ai-tool strategy-pool propose --symbol AAPL --strategies trend,mean_reversion
ai-tool --help
```

### 输出格式

| 格式 | 触发 | 用途 |
|------|------|------|
| JSON | `ai-tool run arbitration --format json` | 程序化调用 |
| Table | `ai-tool audit query --format table` | 工程排查 |
| Tree | `ai-tool status --format tree` | 系统状态 |
| Detail | `ai-tool run full-pipeline` | 完整流水日志 |

---

## F. 用户入口与部署层规划

### 配置文件结构

```yaml
# config/dev.yaml
system:
  version: "1.0.0"
  log_level: DEBUG

api:
  host: 0.0.0.0
  port: 8000
  workers: 1
  reload: true

console:
  host: 0.0.0.0
  port: 8501

database:
  url: "sqlite:///./ai_trading_tool.db"
  echo: true

auth:
  enabled: false  # dev: no auth
  secret_key: "dev-secret-do-not-use-in-prod"

permissions:
  default_role: operator

risk_engine:
  max_position_pct: 0.1
  default_regime: trending_up

feedback:
  registry_path: ~/.ai-trading-tool/feedback_registry
```

### 启动方式

```bash
# 开发模式
uvicorn apps.api.main:app --reload --port 8000

# Console（独立进程，调用 API）
streamlit run apps/console/dashboard.py --server.port 8501

# CLI
python -m apps.cli.main run full-pipeline --symbol AAPL --direction LONG

# Docker（生产）
docker compose -f infra/docker/docker-compose.yml up api console
```

### 监控 / 运维入口

| 入口 | 地址 | 说明 |
|------|------|------|
| API docs | `GET /docs` | Swagger UI（dev only）|
| API health | `GET /health` | 健康检查 |
| API metrics | `GET /metrics` | 请求计数 / 延迟（future）|
| Console | `http://localhost:8501` | Web 控制台 |
| Audit trail | API `/audit/*` | 所有写操作留痕 |

---

## G. AI 接入点规划

### 定位

AI Operator Layer 位于 API 层之上。**AI 只能通过 API DTO 进出系统。**

### AI 边界（最高优先级）

```
❌ AI 禁止：
  - 直接绑定 core schema（ArbitrationDecision / PositionPlan / Feedback）
  - 直接 import Phase 1-10 核心模块（任何读或写操作）
  - 直接调用 Phase4Updater.apply()
  - 直接消费或返回核心内部对象
  - 绕过 API 层直接操作数据库

✅ AI 合法路径（API DTO 唯一入口）：
  - GET /audit/*      → API DTO → AI（只读查询）
  - POST /analysis/run      → API DTO → Suggestion → FeedbackRegistry（append-only）
  - POST /arbitration/*    → API DTO → Suggestion → FeedbackRegistry（append-only）
  - POST /audit/feedback/tasks  → Task ID → GET /audit/feedback/tasks/{id} → API DTO → AI
  - POST /strategy-pool/propose → API DTO → Suggestion（不写 registry）
```

### 完整 AI → 系统 → 人工确认链路

```
AI Operator
    │  HTTP API（只经过 API DTO）
    ▼
FastAPI（AI 的唯一合法入口）
    │  suggestion-only / append-only
    ▼
FeedbackRegistry（append-only）
    │
    ▼
人工复盘（Console Review 面板）
    │ 确认 → ReviewManager 状态机：pending → reviewed → applied
    │ 拒绝 → pending → rejected（记录原因）
    ▼
Phase 4 registry（需人工确认后写入）
```

### AI Copilot 模式（Console 集成）

Web Console 提供 AI Copilot Tab，AI 通过以下流程操作：

1. **查询**：`GET /audit/*` → API DTO → AI（了解系统状态）
2. **建议**：`POST /analysis/run` / `POST /arbitration/run` → suggestion
3. **记录**：suggestion → FeedbackRegistry（append-only）
4. **轮询**：`GET /audit/feedback/tasks/{id}` → Task 结果
5. **等待**：AI 告知用户"建议已记录，等待人工确认"
6. **人工审批**：用户在 Console Review 面板确认 / 拒绝

**关键约束**：AI 永远不直接操作 registry，永远不绕过 API 层。

---

## G2. 权限方案（首批基线）

**技术选型**：SQLite + local users（首批不做 OAuth / JWT / Keycloak）

```
角色：
  viewer   — 只读（GET 端点）
  operator — 可写（suggestion-only 端点）
  admin    — 人工复盘确认权限（ReviewManager apply）

权限模型：
  - viewer + operator + admin 共享同一 SQLite 数据库
  - 每次 API 请求带 X-User-ID header 或 Basic Auth
  - 写操作记录 audit trail（谁在何时写了什么）
  - 无外部身份提供商依赖
```

### 权限首批范围

| 角色 | 读 | 写（suggestion）| 复盘确认 | 说明 |
|------|:--:|:--:|:--:|------|
| viewer | ✅ | ❌ | ❌ | 只读监控 |
| operator | ✅ | ✅ | ❌ | 普通操作员 |
| admin | ✅ | ✅ | ✅ | 管理员（含人工确认）|

---

## I. 与 Phase 1–10 的边界

| 边界 | 规则 |
|------|------|
| 读操作 | API / CLI / Console 可调用 Phase 1-10 核心引擎 |
| 写 Phase 1-3 registry | ❌ 禁止，只能通过人工确认后写入 |
| 写 FeedbackRegistry | ✅ 允许（append-only，设计保障）|
| 写 Phase 4 registry | ❌ 禁止，只能通过 ReviewManager + 人工确认 |
| 修改核心语义 | ❌ 禁止（bias 计算逻辑、风控阈值、审计 schema）|
| 新增 API 端点写权限 | ✅ 允许，需在 `apps/auth/service.py` 声明 |

---

## J. 验收清单

### 阶段 1：基础设施

- [ ] `apps/` 目录结构建立
- [ ] `apps/dto/api/` 全部 API DTO 模型定义完成
- [ ] `apps/dto/view/` 全部 View Model 定义完成
- [ ] `apps/auth/` 轻量权限层（SQLite / User / OperatorRole / Permission gate）
- [ ] `infra/config/` 配置加载（dev/test/prod 环境）
- [ ] API 可导入并响应 `/health`

### 阶段 2：API 核心

- [ ] `GET /health` — 服务健康检查
- [ ] `GET /version` — 系统版本
- [ ] `POST /analysis/run` — 分析引擎接入（suggestion-only）
- [ ] `POST /arbitration/run` — 旧入口仲裁接入
- [ ] `POST /arbitration/run-portfolio` — 策略池仲裁接入
- [ ] `POST /risk/calculate` — 风控计算接入
- [ ] `POST /audit/feedback/tasks` — 扫描任务提交（task-style）
- [ ] `GET /audit/feedback/tasks/{task_id}` — 任务状态查询
- [ ] `GET /audit/decisions` — 决策查询（分页）
- [ ] `GET /audit/feedback` — Feedback 查询
- [ ] 所有写操作端点权限 gate（非 Operator 角色返回 403）
- [ ] 所有端点参数校验（DTO validation）
- [ ] 写权限约束验证（无任何端点可直接写 Phase 1-4 registry）

### 阶段 3：CLI

- [ ] `ai-tool run full-pipeline` 可用
- [ ] `ai-tool run arbitration --strategy-pool` 可用
- [ ] `ai-tool audit query` 可用
- [ ] `ai-tool status` 可用
- [ ] JSON / Table / Tree 输出格式切换
- [ ] 错误信息工程友好（错误码 + 上下文）

### 阶段 4：Web Console（Streamlit — first implementation）

- [ ] Dashboard 总览面板可用（调用 API）
- [ ] Arbitration Console 双入口可用
- [ ] Audit Console 查询面板可用
- [ ] Feedback Review 面板（人工复盘入口）可用
- [ ] Console 不直接 import 核心内部对象（通过 HTTP + API DTO）
- [ ] AI Copilot Tab（AI 查询 + suggestion 入口）

### 阶段 5：部署与交接

- [ ] `docker-compose up api console` 正常启动
- [ ] dev 环境无需 auth 即可访问
- [ ] prod 环境 auth 生效（local operator）
- [ ] README.md 更新（API / CLI / Console 使用说明）
- [ ] 文档索引更新（`docs/architecture/`）
- [ ] 271 个 Phase 1-10 测试仍然全部通过（回归验证）
