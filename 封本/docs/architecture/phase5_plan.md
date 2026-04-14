# Phase 5 规划：六大分析模块收口与补齐

**项目**: ai-trading-tool  
**文档版本**: 2.0.0（逐模块展开版）  
**规划日期**: 2026-04-10  
**状态**: 待实施

---

## 一、A. Phase 5 目标文件树

```
core/
├── schemas/                    # ✅ 已有，全模块共用
│   └── __init__.py            # EngineSignal / MarketBar / ChanSignal 等
│
├── research/                   # ✅ 模块 3：Phase 4 已完成，纳入主干
│   ├── __init__.py
│   ├── models.py
│   ├── registry.py
│   ├── qlib/                   # Qlib 绑定层
│   ├── alpha/                  # Alpha 因子体系（20+L1 + 4 组合）
│   │   ├── builders/          # technical / fundamentals / sentiment / composite
│   │   ├── filters/          # financial_quality / technical_filter / market_regime
│   │   └── risk/             # manager / exposure
│   ├── labels/                # 标签体系
│   ├── portfolio/             # 组合优化器（6 目标 + 约束）
│   ├── backtest/              # 回测引擎
│   ├── strategy/              # 策略框架
│   ├── deployment/            # 部署层
│   └── datasets/              # 数据集版本管理
│
└── analysis/                   # 🔧 Phase 5 实现目标
    ├── __init__.py             # ✅ Stage 1 已完成
    ├── base.py                 # ✅ Stage 1 已完成
    │
    ├── technical/              # [模块 4.2] 🔧 待实现
    │   ├── __init__.py
    │   ├── engine.py           # TechnicalEngine 统一入口
    │   ├── trend.py            # 趋势指标（MA / ADX / 通道）
    │   ├── momentum.py         # 动量指标（MACD / RSI / KDJ / CCI）
    │   ├── volatility.py       # 波动率指标（ATR / Bollinger Bands）
    │   ├── patterns.py         # 图表形态
    │   ├── candles.py          # K线形态
    │   └── levels.py           # 支撑阻力位
    │
    ├── chan/                   # [模块 4.1] 🔧 待实现
    │   ├── __init__.py
    │   ├── engine.py           # ChanEngine 统一入口
    │   ├── fractals.py         # 分型识别
    │   ├── strokes.py          # 笔构建
    │   ├── segments.py         # 线段
    │   ├── centers.py          # 中枢
    │   ├── divergence.py       # 背驰判断
    │   └── points.py            # 买点/卖点判定
    │
    ├── orderflow/              # [模块 5] 🔧 待实现
    │   ├── __init__.py
    │   ├── engine.py           # OrderFlowEngine
    │   ├── imbalance.py        # 订单簿失衡
    │   ├── delta.py            # Delta / CVD 追踪
    │   ├── absorption.py       # 吸收检测
    │   └── liquidity.py        # 流动性扫损
    │
    ├── sentiment/              # [模块 6] 🔧 待实现
    │   ├── __init__.py
    │   ├── engine.py           # SentimentEngine
    │   ├── news.py             # 新闻情绪
    │   ├── aggregator.py       # 多源聚合
    │   └── fund_flow.py        # 资金流向
    │
    ├── macro/                  # [模块 2] 🔧 待实现
    │   ├── __init__.py
    │   ├── engine.py           # MacroEngine
    │   ├── regime.py           # 市场状态检测
    │   ├── calendar.py         # 宏观日历
    │   └── impact.py           # 事件影响评分
    │
    └── fundamental/            # [模块 1] 🔧 待实现
        ├── __init__.py
        ├── engine.py           # FundamentalEngine
        ├── valuation.py        # 估值分析
        ├── financials.py        # 财务指标
        └── quality.py           # 盈利质量

tests/unit/
└── test_analysis_base.py      # ✅ Stage 1 已完成
```

---

## 二、B. 六大模块状态总表

| # | 模块 | 目录 | Schema 定义 | 引擎实现 | 单元测试 | 集成测试 | 状态 |
|---|------|------|:-----------:|:--------:|:--------:|:--------:|------|
| 1 | 基本盘信息报表 | `analysis/fundamental/` | ✅ 复用 | 🔲 | 🔲 | 🔲 | **未开始** |
| 2 | 宏观消息模块 | `analysis/macro/` | ✅ 复用 | 🔲 | 🔲 | 🔲 | **未开始** |
| 3 | 量化研究工厂 | `research/` | ✅ | ✅ | ✅ | ✅ | ✅ **已完成** |
| 4.1 | 缠论引擎 | `analysis/chan/` | ✅ 复用 | 🔲 | 🔲 | 🔲 | **未开始** |
| 4.2 | 经典技术分析 | `analysis/technical/` | ✅ 复用 | 🔲 | 🔲 | 🔲 | **未开始** |
| 5 | 盘口/订单流 | `analysis/orderflow/` | ✅ 复用 | 🔲 | 🔲 | 🔲 | **未开始** |
| 6 | 情绪/资金博弈 | `analysis/sentiment/` | ✅ 复用 | 🔲 | 🔲 | 🔲 | **未开始** |

---

## 三、C. 每个模块的输入输出 Schema

### 模块 1：基本盘信息报表

```
输入:  FundamentalsSnapshot  (core/schemas)
       symbol: str
       timestamp: datetime

输出:  FundamentalReport  (新增 schema)
       ├─ symbol / timestamp
       ├─ valuation:    { pe, pb, ps, peg, market_cap }
       ├─ profitability: { roe, roa, gross_margin, net_margin }
       ├─ growth:       { revenue_growth_yoy, eps_growth_yoy }
       ├─ health:       { debt_to_equity, current_ratio }
       ├─ dividend:     { yield, payout_ratio }
       ├─ quality_score: float [0,1]
       ├─ recommendation: "buy" | "hold" | "sell"
       └─ reasoning: str

       + EngineSignal (方向信号)
```

### 模块 2：宏观消息模块

```
输入:  MacroEvent[]      (core/schemas)
       MarketBar[]       (core/schemas)  ← 用于 regime 检测
       timestamp: datetime

输出:  MacroSignal       (core/schemas)
       ├─ regime:        "risk_on" | "risk_off" | "mixed" | "uncertain"
       ├─ themes:        list[str]
       ├─ asset_impact:  { equity, bond, commodity, fx }
       ├─ central_bank_stance: "hawkish" | "dovish" | "neutral"
       └─ surprise_score: float
```

### 模块 3：量化研究工厂 ✅

```
输入:  MarketBar[]       (core/schemas)
       FeatureSetVersion (research/models)
       LabelSetVersion   (research/models)

输出:  SignalCandidate[] (research/models)
       AlphaFactorSet    (research/alpha/models)
       ModelArtifact     (research/models)
```

### 模块 4.1：缠论引擎

```
输入:  MarketBar[]       (core/schemas)
       timeframe: str    (可选，默认从 bars 推断)

输出:  ChanSignal        (core/schemas)
       ├─ direction:     "long" | "short" | "flat"
       ├─ confidence:    float [0,1]
       ├─ regime:        "trending_up" | "trending_down" | "ranging"
       ├─ fractal_level: "top" | "bottom" | null
       ├─ bi_status:     "completed" | "forming" | null
       ├─ segment_status: str
       ├─ zhongshu_status: str
       ├─ purchase_point: 1 | 2 | 3 | null
       ├─ sell_point:     1 | 2 | 3 | null
       ├─ divergence:     "bullish" | "bearish" | "none"
       ├─ entry_price:   float
       ├─ stop_price:    float
       ├─ target_price:  float
       └─ risk_reward_ratio: float
```

### 模块 4.2：经典技术分析

```
输入:  MarketBar[]       (core/schemas)
       indicators: list[str]  (可选，默认全量)

输出:  TechnicalSignal   (core/schemas)
       ├─ direction:     "long" | "short" | "flat"
       ├─ confidence:    float [0,1]
       ├─ regime:        "trending" | "ranging" | "volatile"
       ├─ indicators:    { rsi_14, macd, bollinger, atr_14, adx_14, stoch }
       ├─ patterns:      list[{ name, confidence, direction }]
       ├─ synthesized_direction: "bullish" | "bearish" | "neutral"
       └─ support_resistance: { support: [...], resistance: [...] }
```

### 模块 5：盘口/订单流

```
输入:  OrderBookSnapshot (core/schemas)
       TradePrint[]      (core/schemas)

输出:  OrderFlowSignal   (core/schemas)
       ├─ direction:     "long" | "short" | "flat"
       ├─ confidence:    float [0,1]
       ├─ net_flow:      float
       ├─ net_flow_ratio: float
       ├─ buy_volume / sell_volume
       ├─ order_imbalance: float [-1,1]
       ├─ bid_ask_spread: float
       ├─ depth_imbalance: float
       ├─ iceberg_detected: bool
       └─ vwap_position: float
```

### 模块 6：情绪/资金博弈

```
输入:  NewsEvent[]       (core/schemas)
       MarketBar[]       (core/schemas)  ← 成交量用于资金流向代理

输出:  SentimentEvent    (core/schemas)
       ├─ sentiment:     { score, label }
       ├─ news_volume:   int
       ├─ analyst_consensus: "buy" | "hold" | "sell"
       ├─ composite_sentiment: float [-1,1]
       ├─ fear_greed_index:  float [0,100]
       └─ momentum:      "accelerating" | "reversing" | "stable"
```

---

## 四、D. 逐模块验收清单

---

### 模块 0：基础层（Stage 1）

| # | 验收项 | 状态 |
|---|--------|:----:|
| 0.1 | `analysis/base.py` — `AnalysisEngine` ABC，`analyze()` 抽象方法 | ✅ |
| 0.2 | `analysis/base.py` — `_check_bars()` / `_require_timeframe()` 工具方法 | ✅ |
| 0.3 | `analysis/base.py` — `batch_analyze()` 批量分析，失败返回中性信号 | ✅ |
| 0.4 | `analysis/base.py` — `health_check()` / `warm_up()` / `shutdown()` 生命周期钩子 | ✅ |
| 0.5 | `analysis/__init__.py` — 惰性导入 6 个子引擎 | ✅ |
| 0.6 | `tests/unit/test_analysis_base.py` — 12 项单元测试全部通过 | ✅ |

---

### 模块 3：量化研究工厂 ✅

| # | 验收项 | 状态 |
|---|--------|:----:|
| 3.1 | `core/research/alpha/` — 20 个 L1 因子全部实现并测试通过 | ✅ |
| 3.2 | `core/research/alpha/builders/composite.py` — 4 种组合方法 | ✅ |
| 3.3 | `core/research/portfolio/optimizer.py` — 6 种优化目标 + 多种约束 | ✅ |
| 3.4 | `core/research/backtest/` — 回测引擎 | ✅ |
| 3.5 | `core/research/strategy/` — 策略基类 + 实现 | ✅ |
| 3.6 | `core/research/deployment/` — DeploymentCandidateManager | ✅ |
| 3.7 | `tests/integration/test_alpha_pipeline.py` — 端到端集成测试 | ✅ |
| 3.8 | `research/` 可通过 `core.analysis.research` 访问（入口文件） | 🔲 |

---

### 模块 4.2：经典技术分析引擎

| # | 验收项 | 状态 |
|---|--------|:----:|
| 4.2.1 | `technical/engine.py` — `TechnicalEngine` 继承 `AnalysisEngine` | 🔲 |
| 4.2.2 | `technical/trend.py` — MA(5/20/60/120) 计算正确 | 🔲 |
| 4.2.3 | `technical/trend.py` — ADX(14) 计算正确 | 🔲 |
| 4.2.4 | `technical/momentum.py` — MACD(12/26/9) 计算正确 | 🔲 |
| 4.2.5 | `technical/momentum.py` — RSI(14) 计算正确 | 🔲 |
| 4.2.6 | `technical/momentum.py` — KDJ / CCI 指标（占位可接受） | 🔲 |
| 4.2.7 | `technical/volatility.py` — ATR(14) 计算正确 | 🔲 |
| 4.2.8 | `technical/volatility.py` — Bollinger Bands(20,2) 计算正确 | 🔲 |
| 4.2.9 | `technical/patterns.py` — 至少 3 种图表形态（头肩/双顶/三角形） | 🔲 |
| 4.2.10 | `technical/candles.py` — 至少 3 种 K 线形态（吞没/十字星/pin bar） | 🔲 |
| 4.2.11 | `technical/levels.py` — 支撑阻力位检测（合成数据验证） | 🔲 |
| 4.2.12 | `technical/engine.py` — `analyze()` 返回 `TechnicalSignal` | 🔲 |
| 4.2.13 | `technical/engine.py` — 指标异常时返回中性信号 + metadata 记录 | 🔲 |
| 4.2.14 | `tests/unit/test_technical_*.py` — 各子模块单元测试 | 🔲 |

---

### 模块 4.1：缠论引擎

| # | 验收项 | 状态 |
|---|--------|:----:|
| 4.1.1 | `chan/engine.py` — `ChanEngine` 继承 `AnalysisEngine` | 🔲 |
| 4.1.2 | `chan/fractals.py` — 顶分型 / 底分型识别（合成 K 线验证） | 🔲 |
| 4.1.3 | `chan/strokes.py` — 笔构建（连续 5 笔，非包含处理） | 🔲 |
| 4.1.4 | `chan/segments.py` — 线段划分（3 笔构成） | 🔲 |
| 4.1.5 | `chan/centers.py` — 中枢识别（3 重叠笔构成） | 🔲 |
| 4.1.6 | `chan/divergence.py` — 背驰判断（价格 vs MACD / 成交量） | 🔲 |
| 4.1.7 | `chan/points.py` — 一买 / 二买 / 三买 / 一卖 / 二卖 / 三卖 | 🔲 |
| 4.1.8 | `chan/engine.py` — `analyze()` 返回 `ChanSignal` | 🔲 |
| 4.1.9 | `tests/unit/test_chan_*.py` — 各子模块单元测试 | 🔲 |

---

### 模块 5：盘口/订单流

| # | 验收项 | 状态 |
|---|--------|:----:|
| 5.1 | `orderflow/engine.py` — `OrderFlowEngine` 继承 `AnalysisEngine` | 🔲 |
| 5.2 | `orderflow/imbalance.py` — 订单簿失衡计算（bid/ask 量比） | 🔲 |
| 5.3 | `orderflow/delta.py` — Delta 计算（主动买 - 主动卖） | 🔲 |
| 5.4 | `orderflow/delta.py` — CVD（Cumulative Volume Delta）追踪 | 🔲 |
| 5.5 | `orderflow/absorption.py` — 吸收检测（占位实现可接受） | 🔲 |
| 5.6 | `orderflow/liquidity.py` — 流动性扫损检测（占位实现可接受） | 🔲 |
| 5.7 | `orderflow/engine.py` — `analyze()` 返回 `OrderFlowSignal` | 🔲 |
| 5.8 | `tests/unit/test_orderflow_*.py` — 各子模块单元测试 | 🔲 |

---

### 模块 6：情绪/资金博弈

| # | 验收项 | 状态 |
|---|--------|:----:|
| 6.1 | `sentiment/engine.py` — `SentimentEngine` 继承 `AnalysisEngine` | 🔲 |
| 6.2 | `sentiment/news.py` — 新闻标题情绪打分（关键词打分法，占位实现） | 🔲 |
| 6.3 | `sentiment/aggregator.py` — 多源情绪加权聚合（news/social/flow） | 🔲 |
| 6.4 | `sentiment/fund_flow.py` — 资金流向代理计算（基于成交量/价格） | 🔲 |
| 6.5 | `sentiment/engine.py` — `analyze()` 返回 `SentimentEvent` | 🔲 |
| 6.6 | `sentiment/engine.py` — 无新闻数据时降级为成交量代理 | 🔲 |
| 6.7 | `tests/unit/test_sentiment_*.py` — 各子模块单元测试 | 🔲 |

---

### 模块 2：宏观消息模块

| # | 验收项 | 状态 |
|---|--------|:----:|
| 2.1 | `macro/engine.py` — `MacroEngine` 继承 `AnalysisEngine` | 🔲 |
| 2.2 | `macro/regime.py` — 市场状态检测（趋势/震荡/高波动，基于 ADX） | 🔲 |
| 2.3 | `macro/calendar.py` — 硬编码宏观日历（利率/CPI/GDP/非农） | 🔲 |
| 2.4 | `macro/impact.py` — 事件影响评分（surprise_score 计算） | 🔲 |
| 2.5 | `macro/engine.py` — 资产配置偏向（equity/bond/commodity/fx） | 🔲 |
| 2.6 | `macro/engine.py` — `analyze()` 返回 `MacroSignal` | 🔲 |
| 2.7 | `tests/unit/test_macro_*.py` — 各子模块单元测试 | 🔲 |

---

### 模块 1：基本盘信息报表

| # | 验收项 | 状态 |
|---|--------|:----:|
| 1.1 | `fundamental/engine.py` — `FundamentalEngine` 继承 `AnalysisEngine` | 🔲 |
| 1.2 | `fundamental/valuation.py` — PE / PB / PS / PEG 计算 | 🔲 |
| 1.3 | `fundamental/financials.py` — ROE / ROA / 营收增长率 / 现金流 | 🔲 |
| 1.4 | `fundamental/quality.py` — 盈利质量评分（综合打分） | 🔲 |
| 1.5 | `fundamental/engine.py` — `analyze()` 返回 `EngineSignal` + `FundamentalReport` | 🔲 |
| 1.6 | `fundamental/engine.py` — 无财务数据时返回中性信号 | 🔲 |
| 1.7 | `tests/unit/test_fundamental_*.py` — 各子模块单元测试 | 🔲 |

---

## 五、实施顺序

```
Stage 1 ✅  基础层（base.py + __init__.py）
Stage 2 🔧  模块 4.2 — 经典技术分析引擎（最高优先级）
Stage 3 🔧  模块 4.1 — 缠论引擎
Stage 4 🔧  模块 5  — 盘口/订单流
Stage 5 🔧  模块 6  — 情绪/资金博弈
Stage 6 🔧  模块 2  — 宏观消息模块
Stage 7 🔧  模块 1  — 基本盘信息报表
Stage 8 🔧  research 入口文件
```

---

**确认后从 Stage 2 开始实施。**
