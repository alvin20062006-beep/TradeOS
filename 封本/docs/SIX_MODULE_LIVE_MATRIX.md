# 六大模块真实数据接入矩阵

## Provider / Adapter 结构

- Market / Bars provider: `core/data/live/providers.py::YahooFinanceLiveProvider`
- Fundamental provider: `core/data/live/providers.py::YahooFinanceLiveProvider`
- Macro provider: `core/data/live/providers.py::FredMacroProvider`
- News provider: `core/data/live/providers.py::YahooFinanceLiveProvider`
- Market adapters: `core/data/live/adapters.py::YahooMarketAdapter`
- Fundamental adapter: `core/data/live/adapters.py::YahooFundamentalAdapter`
- Macro adapter: `core/data/live/adapters.py::FredMacroAdapter`
- News adapter: `core/data/live/adapters.py::YahooNewsAdapter`
- Live orchestration: `core/data/live/orchestrator.py::LiveAnalysisOrchestrator`

## 数据依赖矩阵

| 模块 | 必需输入 | 当前 provider | adapter | 当前真实可用部分 | 当前 placeholder 部分 | 是否已接入 live pipeline |
| -- | -- | -- | -- | -- | -- | -- |
| Fundamental | `FundamentalsSnapshot` | Yahoo Finance | `YahooFundamentalAdapter` | `market_cap`, `PE/PB/PS/PEG`, `revenue`, `EBITDA`, `net_income`, `debt`, `EPS`, `book_value`, `dividend_yield`, `beta`, `avg_volume_20d` | 历史同比增长字段、`ev_ebitda`、`gross_margin`、`current_ratio`、`quick_ratio`、`interest_coverage` 仍按缺字段标注 | 是 |
| Macro | `MacroEvent[]` + 市场 bars | FRED 公共 CSV + Yahoo Finance 宏观新闻 | `FredMacroAdapter` | FRED 实时公开指标：`DFF`, `DGS10`, `CPIAUCSL`, `UNRATE`, `VIXCLS`；Yahoo 宏观新闻标题/摘要进入 `MacroEvent` | `forecast` 在 FRED 路径中暂无公开一致来源，明确标注为空 | 是 |
| Technical | `MarketBar[]` | Yahoo Finance | `YahooMarketAdapter` | 真实 OHLCV、真实 timeframe、真实 lookback | 无主路径 placeholder | 是 |
| Chan | `MarketBar[]` | Yahoo Finance | `YahooMarketAdapter` | 真实 K 线序列、真实 bars 时间轴 | 无主路径 placeholder | 是 |
| OrderFlow | `OrderBookSnapshot` / `TradePrint[]` / `MarketBar[]` | Yahoo Finance（真实行情近似） | `YahooMarketAdapter` + `OrderFlowEngine` 内置 bars proxy path | 真实 1m intraday bars 驱动的 `book_imbalance` 近似、VWAP/absorption/sweep/execution 近似 | `TradePrint[]`、完整 depth-of-book 暂缺，已明确标注 `trade_prints`, `order_book_depth` | 是 |
| Sentiment | `NewsEvent[]` + 市场 bars | Yahoo Finance | `YahooNewsAdapter` + `YahooMarketAdapter` | 真实 symbol 新闻标题/摘要、真实新闻发布时间、真实相关新闻 symbol | `social_sentiment`, `forum_sentiment`, `analyst_sentiment` 暂无真实 provider，保持标注 | 是 |

## 当前真实程度说明

### 1. Fundamental

- 真实数据来源：Yahoo Finance `Ticker.info`
- 接入方式：`YahooFundamentalAdapter -> FundamentalsSnapshot -> FundamentalEngine`
- 禁止路径：不再通过 OHLCV 伪造股票基本面作为主路径
- 非股票场景：`CL=F` / 指数 / 外汇进入 `commodity mode skip`，明确 `skipped`

### 2. Macro

- 真实数据来源：
  - FRED 公共 CSV 指标
  - Yahoo Finance 宏观相关新闻（如 `^TNX`, `^VIX`）
- 接入方式：`FredMacroAdapter -> MacroEvent[] -> MacroEngine`
- 已不再依赖手写 `risk_on/risk_off` 分数

### 3. Technical

- 真实数据来源：Yahoo Finance OHLCV bars
- 接入方式：`YahooMarketAdapter -> MarketBar[] -> TechnicalEngine`

### 4. Chan

- 真实数据来源：Yahoo Finance OHLCV bars
- 接入方式：`YahooMarketAdapter -> MarketBar[] -> ChanEngine`

### 5. OrderFlow

- 正式接口已经建立为三层语义：
  - 完整模式：`TradePrint[] + OrderBookSnapshot`
  - 真实成交驱动：当前 provider 暂无通用公开路径
  - 真实行情近似驱动：当前由 Yahoo Finance 1m bars 进入 `OrderFlowEngine`
- 缺口已明确：完整 depth-of-book 与逐笔成交未混写成完成

### 6. Sentiment

- 真实数据来源：Yahoo Finance 新闻流
- 接入方式：`YahooNewsAdapter -> NewsEvent[] -> SentimentEngine`
- 已不再使用纯假情绪分数作为主路径

## Live 入口

- API:
  - `POST /api/v1/analysis/run-live`
  - `POST /api/v1/pipeline/run-live`
- CLI:
  - `python -m apps.cli pipeline run-live --symbol AAPL`
  - `python run.py pipeline-live --symbol CL=F`

## 全链验证场景

- 商品场景：`CL=F`
  - Fundamental: `skipped / commodity mode`
  - 其余 5 模块真实参与
- 股票场景：`AAPL`
  - 六模块全部进入 live pipeline
- 全链路：
  - 真实数据 -> 六模块 -> Phase 6 -> Phase 7 -> Phase 8 -> Feedback scan
