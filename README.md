# TradeOS

**TradeOS** is a full-stack AI trading research and decision platform that connects market data, multi-module analysis, signal arbitration, risk management, audit feedback, strategy pooling, and productized delivery into one coherent system.

**TradeOS** 是一个全栈 AI 交易研究与决策平台，把市场数据、六大分析模块、信号仲裁、风险控制、审计反馈、策略池和产品化交付整合成一条完整链路。

## Overview | 项目概览

TradeOS is designed as a serious research-grade operating system for trading intelligence rather than a toy demo.  
It combines:

- real-data live analysis
- multi-engine signal generation
- formal arbitration and conflict resolution
- position planning and risk filtering
- audit and feedback traceability
- strategy-pool re-entry and closed-loop orchestration
- API, Console, CLI, and local deployment packaging

TradeOS 的目标不是做一个“能跑一下”的演示项目，而是做成具备完整主链语义的研究级交易智能操作系统。  
它目前已经覆盖：

- 真实数据驱动的 live 分析
- 多引擎分析信号生成
- 正式仲裁与冲突解决
- 仓位规划与风控过滤
- 审计与反馈可追踪闭环
- 策略池回流仲裁
- API、Console、CLI 与本地交付

## What Makes It Strong | 这个项目厉害在哪里

- **Phase 1–10 mainline architecture is preserved**
  - The system is not a pile of scripts. It follows a frozen phase-based blueprint with clear responsibilities and boundaries.
- **Six-module live analysis is wired into the product layer**
  - Fundamental, Macro, Technical, Chan, OrderFlow, and Sentiment all have formal provider/adapter/live-entry paths.
- **Real market data is integrated**
  - Yahoo Finance and FRED are used for live verification instead of pretending with manual scores or mocks.
- **Arbitration is treated as a first-class decision layer**
  - Single-signal entry and portfolio entry both map into the formal rules chain.
- **Risk and audit are part of the main path**
  - Decisions do not stop at “analysis looks good”; they continue into risk planning, audit records, and feedback scanning.
- **Productization is not a fake shell**
  - FastAPI, Streamlit, CLI, local launchers, and desktop shortcut flow are aligned to real backend DTOs and real endpoints.
- **The execution and research foundations are included**
  - `qlib` and `nautilus_trader` are kept in the repository as foundational layers rather than external placeholders.

- **Phase 1–10 主链没有漂移**
  - 这不是一堆临时脚本拼起来的项目，而是按冻结蓝图逐层落下来的系统。
- **六大分析模块已经进入产品化 live 路径**
  - Fundamental、Macro、Technical、Chan、OrderFlow、Sentiment 都有正式 provider / adapter / live 入口。
- **真实市场数据已接入**
  - 使用 Yahoo Finance 与 FRED 做真实验证，而不是用手工打分或 mock 假装完成。
- **仲裁层是正式核心，不是装饰层**
  - 单信号入口和策略池入口都进入统一规则链。
- **风控与审计在主路径里真实存在**
  - 结果不会停留在“分析完成”，而是继续进入风控、审计和反馈链。
- **产品化层不是空壳**
  - FastAPI、Streamlit、CLI、本地启动器、桌面快捷方式都对齐真实 DTO 和真实接口。
- **研究与执行底盘一并纳入**
  - `qlib` 与 `nautilus_trader` 作为底盘源码保留在仓库内，而不是“口头依赖”。

## Repository Structure | 仓库结构

```text
.
├─ TradeOS/            # Main runnable product bundle / 主可运行项目
├─ qlib/               # Vendored qlib source / 研究底盘源码
├─ nautilus_trader/    # Vendored Nautilus Trader source / 执行底盘源码
└─ README.md
```

### Main Entry | 主入口

- Main project bundle: [TradeOS/README.md](TradeOS/README.md)
- Local deployment: [TradeOS/docs/LOCAL_DEPLOYMENT.md](TradeOS/docs/LOCAL_DEPLOYMENT.md)
- Backend capability report: [TradeOS/docs/BACKEND_CAPABILITY_REPORT.md](TradeOS/docs/BACKEND_CAPABILITY_REPORT.md)
- Frontend fix report: [TradeOS/docs/FRONTEND_FIX_REPORT.md](TradeOS/docs/FRONTEND_FIX_REPORT.md)
- Blueprint audit report: [TradeOS/docs/BLUEPRINT_AUDIT_REPORT.md](TradeOS/docs/BLUEPRINT_AUDIT_REPORT.md)
- WTI live test report: [TradeOS/docs/WTI_LIVE_TEST_REPORT.md](TradeOS/docs/WTI_LIVE_TEST_REPORT.md)
- qlib closure report: [TradeOS/docs/QLIB_CLOSURE_REPORT.md](TradeOS/docs/QLIB_CLOSURE_REPORT.md)

- 主项目说明：[TradeOS/README.md](TradeOS/README.md)
- 本地部署文档：[TradeOS/docs/LOCAL_DEPLOYMENT.md](TradeOS/docs/LOCAL_DEPLOYMENT.md)
- 后端能力报告：[TradeOS/docs/BACKEND_CAPABILITY_REPORT.md](TradeOS/docs/BACKEND_CAPABILITY_REPORT.md)
- 前端修复报告：[TradeOS/docs/FRONTEND_FIX_REPORT.md](TradeOS/docs/FRONTEND_FIX_REPORT.md)
- 蓝图审计报告：[TradeOS/docs/BLUEPRINT_AUDIT_REPORT.md](TradeOS/docs/BLUEPRINT_AUDIT_REPORT.md)
- WTI 真实数据报告：[TradeOS/docs/WTI_LIVE_TEST_REPORT.md](TradeOS/docs/WTI_LIVE_TEST_REPORT.md)
- qlib 收口报告：[TradeOS/docs/QLIB_CLOSURE_REPORT.md](TradeOS/docs/QLIB_CLOSURE_REPORT.md)

## Core Architecture | 核心架构

Inside `TradeOS/`, the system is organized around the frozen phase blueprint:

`Data -> Research -> Analysis -> Arbitration -> Risk -> Audit/Feedback -> Strategy Pool -> Re-enter Arbitration`

`TradeOS/` 内部按冻结的主链蓝图组织：

`数据 -> 研究 -> 分析 -> 仲裁 -> 风控 -> 审计/反馈 -> 策略池 -> 回流仲裁`

Key areas:

- `TradeOS/core/data/`
  - market data providers, adapters, validation, live orchestration
- `TradeOS/core/research/`
  - alpha system, datasets, backtest, portfolio optimization, signal export
- `TradeOS/core/analysis/`
  - six analysis modules
- `TradeOS/core/arbitration/`
  - signal collection, rules chain, decision making
- `TradeOS/core/risk/`
  - sizing, filters, execution planning
- `TradeOS/core/audit/`
  - decision audit, risk audit, feedback engine, append-only registries
- `TradeOS/core/strategy_pool/`
  - strategy composition, weight allocation, arbitration bridge
- `TradeOS/apps/`
  - API, Console, CLI, auth, DTO layer

关键目录：

- `TradeOS/core/data/`
  - 数据 provider、adapter、校验与 live 编排
- `TradeOS/core/research/`
  - Alpha 因子、数据集、回测、组合优化、信号导出
- `TradeOS/core/analysis/`
  - 六大分析模块
- `TradeOS/core/arbitration/`
  - 信号收集、规则链、决策生成
- `TradeOS/core/risk/`
  - 仓位 sizing、过滤器、执行规划
- `TradeOS/core/audit/`
  - 决策审计、风险审计、反馈引擎、append-only registry
- `TradeOS/core/strategy_pool/`
  - 策略组合、权重分配、仲裁桥接
- `TradeOS/apps/`
  - API、控制台、CLI、权限、DTO 层

## Product Surface | 产品化能力

TradeOS currently exposes a real product surface through:

- **FastAPI API**
  - health, version, system status, analysis, arbitration, risk, audit, strategy pool, pipeline, auth
- **Streamlit Console**
  - Dashboard, Pipeline, Arbitration, Strategy Pool, Audit, Feedback
- **CLI**
  - status checks, pipeline live runs, local operation entry points
- **Windows local launcher**
  - `start.ps1`, `start.bat`, and desktop shortcut generation

TradeOS 当前对外可见的产品面包括：

- **FastAPI API**
  - health、version、system、analysis、arbitration、risk、audit、strategy pool、pipeline、auth
- **Streamlit Console**
  - Dashboard、Pipeline、Arbitration、Strategy Pool、Audit、Feedback
- **CLI**
  - 状态检查、live pipeline、本地运行入口
- **Windows 本地启动器**
  - `start.ps1`、`start.bat`、桌面快捷方式生成

## Quick Start | 快速开始

### Run the main application | 启动主项目

```powershell
cd .\TradeOS
python -m pip install -r requirements-local.txt
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

### Start components separately | 分别启动组件

```powershell
cd .\TradeOS
python run.py api
python run.py console
python run.py pipeline-live --symbol AAPL --timeframe 1d --lookback 90
```

### Desktop shortcut | 桌面快捷方式

```powershell
cd .\TradeOS
powershell -ExecutionPolicy Bypass -File .\_make_shortcut.ps1
```

## Live Data and Validation | 真实数据与验证

The project includes formal live-data validation work using:

- Yahoo Finance
- FRED
- AAPL / NVDA equity scenarios
- CL=F WTI commodity scenario
- live API and CLI validation
- audit readback verification

项目已经完成正式真实数据验证，覆盖：

- Yahoo Finance
- FRED
- AAPL / NVDA 股票场景
- CL=F WTI 商品场景
- live API 与 CLI 验证
- audit 查询真实读回验证

## Technology Stack | 技术栈

- Python
- FastAPI
- Streamlit
- Pydantic
- yfinance
- qlib
- nautilus_trader
- cvxpy
- SQLite

## Positioning and Boundary | 项目定位与边界

This is a **research-grade and productized trading intelligence platform**, not a claim of production brokerage execution readiness.

Important boundaries:

- no direct registry truth-write backdoor was introduced for the product layer
- Phase 1–10 core semantics were not intentionally rewritten for convenience
- product UI is adapted to backend DTOs instead of inventing fake behavior
- append-only and suggestion-only semantics are preserved where required

这是一个**研究级、产品化的交易智能平台**，不是“已经接入券商即可实盘”的宣传口径。

重要边界：

- 产品层没有新增真值直写后门
- 没有为了方便演示去改写 Phase 1–10 核心语义
- 前端按真实 DTO 适配，而不是自己想象功能
- append-only 与 suggestion-only 语义按要求保留

## Top-Level Folder Guide | 顶层目录说明

- `TradeOS/`
  - the main runnable and documented application bundle
  - 主可运行、主交付、主文档目录
- `qlib/`
  - vendored qlib source used for research-layer integration and compatibility work
  - 研究层集成与兼容性收口所用的 qlib 源码
- `nautilus_trader/`
  - vendored Nautilus Trader source used for execution-adapter integration work
  - 执行适配层集成所用的 Nautilus Trader 源码

## Current Naming | 当前命名

The original delivery folder name has been normalized to `TradeOS`v1.0.

原先的交付目录名已统一规范为 `TradeOS`v1.0。
