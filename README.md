# TradeOS

TradeOS is a local AI trading operating console that connects real-data analysis, formal arbitration, risk planning, simulation execution, audit, feedback, and a desktop-first product shell into one coherent workflow.  
TradeOS 是一个本地 AI 交易操作台，把真实数据分析、正式仲裁、风控规划、执行仿真、审计反馈和桌面化产品壳整合成一条完整工作流。

![TradeOS Product Home](TradeOS/docs/assets/console-home.png)

## Overview | 项目概览

TradeOS is not positioned as a toy demo or a static frontend shell. It is a productized local application built on top of a Phase 1-10 Python/FastAPI backend, with a desktop shell as the default entry and a FastAPI-mounted console as the main user surface.  
TradeOS 不是一个演示性质的小样，也不是静态前端壳。它是建立在 Phase 1-10 Python/FastAPI 后端之上的本地产品化应用，以桌面壳为默认入口，以 FastAPI 挂载的控制台为主界面。

At a high level, TradeOS currently covers:  
当前 TradeOS 已经覆盖：

- real-data live analysis  
  真实数据驱动的实时分析
- six-module signal generation  
  六大模块信号生成
- formal arbitration and conflict resolution  
  正式仲裁与冲突解决
- risk sizing and filtering  
  风控 sizing 与过滤链
- simulation execution  
  执行仿真
- append-only audit and feedback  
  append-only 审计与反馈
- strategy-pool re-entry  
  策略池回流
- desktop shell, console, API, and CLI  
  桌面壳、控制台、API 与 CLI

## Product Highlights | 产品亮点

- Desktop-first local product entry  
  桌面优先的本地产品入口
- FastAPI-mounted bilingual console at `/console/`  
  挂载在 `/console/` 的双语 FastAPI 控制台
- Data Sources, Pipeline, Arbitration, Strategy Pool, Audit, Feedback, and Diagnostics  
  Data Sources、Pipeline、Arbitration、Strategy Pool、Audit、Feedback、Diagnostics 全部到位
- Real Yahoo/FRED-backed product flow with explicit proxy boundaries  
  真实 Yahoo/FRED 驱动的产品路径，并显式暴露 proxy 边界
- Simulation execution, append-only audit, and feedback loop  
  执行仿真、append-only 审计与反馈闭环
- Full local pytest suite green with optional research skips  
  本地全量 pytest 为绿，可选 research 依赖按规则 skip

## Product Contract | 产品约定

- Default entry: TradeOS desktop shell  
  默认入口：TradeOS 桌面壳
- Default local console: `/console/`, opened inside the desktop shell  
  默认本地控制台：桌面壳内打开的 `/console/`
- Legacy fallback: `TradeOS/apps/console/`  
  旧回退入口：`TradeOS/apps/console/`
- Advanced raw API access: Diagnostics / Advanced API  
  高级原始 API 入口：Diagnostics / Advanced API
- Users should not need to understand localhost, API, frontend/backend, bridges, or workers  
  用户不需要理解 localhost、API、前后端拆分、bridge 或 worker

## Entry Matrix | 入口矩阵

| Entry Type | Command / Path | Notes |
|---|---|---|
| Product entry | `python run.py start` or `.\start.ps1` | Desktop shell with embedded `/console/` |
| Developer API | `python run.py api` | FastAPI only |
| Developer console | `python run.py console` | Browser fallback for `/console/` |
| Legacy fallback | `TradeOS/apps/console/` | Old Streamlit implementation |
| Advanced diagnostics | `/console/?view=diagnostics` | Raw API templates and troubleshooting |
| Optional research extras | `pip install -e ".[research]"` | Research-only dependencies and tests |

对应中文说明：

- Product entry：产品默认入口  
- Developer API：开发者 API 入口  
- Developer console：开发态浏览器控制台入口  
- Legacy fallback：旧版回退入口  
- Advanced diagnostics：高级诊断入口  
- Optional research extras：可选研究依赖安装入口

## Core Loop | 主链闭环

```text
Data Sources
-> Six Modules
-> Arbitration
-> Risk
-> Execution Simulation
-> Audit
-> Feedback
-> Strategy Pool
-> Re-enter Arbitration
```

This is the current product-facing loop. The default data profile exposes real Yahoo market/fundamental/news data, FRED macro data, explicit OrderFlow/Sentiment proxy boundaries, and local simulation execution.  
这就是当前面向产品的主链。默认数据 profile 提供真实 Yahoo 行情/基本面/新闻数据、FRED 宏观数据、显式的 OrderFlow/Sentiment proxy 边界，以及本地执行仿真。

## Repository Structure | 仓库结构

The active runnable project is in `TradeOS/`.  
当前实际可运行的主项目在 `TradeOS/` 目录中。

```text
.
├─ README.md
└─ TradeOS/
   ├─ apps/
   ├─ core/
   ├─ docs/
   ├─ infra/
   ├─ tests/
   ├─ run.py
   ├─ start.ps1
   └─ requirements-local.txt
```

Key areas inside `TradeOS/`:  
`TradeOS/` 内部关键区域：

- `apps/`
  - desktop shell, API, web console, CLI, DTO layer  
    桌面壳、API、Web 控制台、CLI、DTO 层
- `core/data/`
  - providers, adapters, validation, live orchestration, source registry  
    数据 provider、adapter、校验、live 编排、数据源注册
- `core/research/`
  - alpha system, datasets, backtest, optimizer-related research workflows  
    Alpha 系统、数据集、回测、优化器相关研究链
- `core/analysis/`
  - Fundamental, Macro, Technical, Chan, OrderFlow, Sentiment  
    六大分析模块
- `core/arbitration/`
  - signal collection, rules chain, decision generation  
    信号收集、规则链、决策生成
- `core/risk/`
  - sizing, filters, execution planning  
    sizing、过滤器、执行规划
- `core/audit/`
  - decision/risk/execution audit, feedback engine, append-only registries  
    决策/风控/执行审计、反馈引擎、append-only 注册表
- `core/strategy_pool/`
  - strategy composition, weight allocation, arbitration bridge  
    策略组合、权重分配、仲裁桥接

## Quick Start | 快速开始

### Default Product Start | 默认产品启动

```powershell
cd TradeOS
.\start.ps1
```

or:

```powershell
cd TradeOS
python run.py start
```

This launches the TradeOS desktop shell, starts the embedded FastAPI backend, opens the console inside an app window, and shuts the backend down when the window closes.  
这会启动 TradeOS 桌面壳，拉起内嵌 FastAPI 后端，在应用窗口中打开控制台，并在窗口关闭时自动关闭后端。

### Developer Commands | 开发命令

```powershell
cd TradeOS
python run.py desktop-smoke
python run.py api
python run.py console
python -m apps.run_console
python -m pytest -q
python -m pytest -m release -q
```

### Local Dependencies | 本地依赖安装

```powershell
cd TradeOS
python -m pip install -r requirements-local.txt
```

## Testing And Validation | 测试与验证

TradeOS uses a product-first dependency policy:  
TradeOS 使用产品优先的依赖策略：

- default runtime: `requirements-local.txt`  
  默认运行时：`requirements-local.txt`
- default full verification: `python -m pytest -q`  
  默认全量验证：`python -m pytest -q`
- release gate: `python -m pytest -m release -q`  
  发布门：`python -m pytest -m release -q`
- optional research extras: `pip install -e ".[research]"`  
  可选 research 扩展：`pip install -e ".[research]"`

If `qlib`, optimizer, or other research-only extras are not installed, those tests should skip cleanly instead of failing collection or turning the default full pytest run red.  
如果 `qlib`、optimizer 或其他 research 专用依赖未安装，对应测试应当被干净地 skip，而不是让默认全量 pytest 变红或 collection 失败。

## Current Product Surfaces | 当前产品界面

- TradeOS desktop shell  
  TradeOS 桌面壳
- `/console/` web console  
  `/console/` Web 控制台
- Data Sources  
  数据源页
- Pipeline  
  流水线页
- Arbitration  
  仲裁页
- Strategy Pool  
  策略池页
- Audit  
  审计页
- Feedback  
  反馈页
- Diagnostics / Advanced API  
  高级诊断 / Advanced API

## Documentation Map | 文档导航

- [Main project README](TradeOS/README.md)  
  主项目 README
- [Local Deployment](TradeOS/docs/LOCAL_DEPLOYMENT.md)  
  本地部署文档
- [Console Guide](TradeOS/apps/CONSOLE.md)  
  控制台说明
- [API Reference](TradeOS/apps/API.md)  
  API 参考
- [Frontend Fix Report](TradeOS/docs/FRONTEND_FIX_REPORT.md)  
  前端修复报告
- [Phase 11 Deployment Guide](TradeOS/docs/architecture/phase11_deployment_guide.md)  
  Phase 11 部署指南
- [System Overview](TradeOS/docs/architecture/system_overview.md)  
  系统总览

## Positioning And Boundary | 定位与边界

TradeOS is a research-grade, productized local trading intelligence platform. It is not a claim of production brokerage execution readiness.  
TradeOS 是一个研究级、产品化的本地交易智能平台，但这并不等于“已达到券商实盘生产级执行就绪”。

Important boundaries:  
重要边界：

- no second backend is introduced for the product layer  
  产品层没有引入第二套后端
- product UI is wired to real backend endpoints  
  产品 UI 对接真实后端接口
- append-only and suggestion-only semantics are preserved where required  
  append-only 与 suggestion-only 语义按要求保留
- explicit PROXY and PLACEHOLDER boundaries are surfaced instead of hidden  
  PROXY 与 PLACEHOLDER 边界显式展示，不做隐藏
- simulation execution is the default product execution mode  
  默认执行模式为 simulation

## Where To Go Next | 下一步看哪里

- Want to run the product now: see [TradeOS/README.md](TradeOS/README.md)  
  现在就要运行产品：看 [TradeOS/README.md](TradeOS/README.md)
- Want local deployment details: see [LOCAL_DEPLOYMENT.md](TradeOS/docs/LOCAL_DEPLOYMENT.md)  
  想看本地部署细节：看 [LOCAL_DEPLOYMENT.md](TradeOS/docs/LOCAL_DEPLOYMENT.md)
- Want raw API endpoints: see [API.md](TradeOS/apps/API.md)  
  想看原始 API：看 [API.md](TradeOS/apps/API.md)
- Want the advanced console/API surface: open Diagnostics from `/console/`  
  想看高级控制台/API 界面：在 `/console/` 中打开 Diagnostics
