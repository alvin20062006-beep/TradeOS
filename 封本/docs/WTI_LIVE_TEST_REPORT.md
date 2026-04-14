# WTI Live Test Report

Test date: 2026-04-15  
Target symbol: `CL=F`  
Execution path: `Yahoo Finance + FRED -> six-module live pipeline -> Phase 6 -> Phase 7 -> Phase 8`

## A. Test Environment

- Workspace: `C:\Users\Alvin\Desktop\AI交易TradeOS\封本`
- Host OS: Windows
- Python: `3.14.3`
- Live entry used:
  - product API equivalent: `POST /api/v1/pipeline/run-live`
  - direct orchestration evidence: `core.data.live.LiveAnalysisOrchestrator.run_live_pipeline(symbol="CL=F", timeframe="1d", lookback=90, news_limit=6)`
- Audit readback path:
  - decisions: `C:\Users\Alvin\.ai-trading-tool\audit\decision_registry`
  - risk: `C:\Users\Alvin\.ai-trading-tool\audit\risk_registry`
  - feedback: `C:\Users\Alvin\.ai-trading-tool\audit\feedback_registry`

## B. Data Sources And Time Range

### Primary data sources

- Market bars: Yahoo Finance / `yfinance`
- News: Yahoo Finance news feed
- Macro indicators: FRED public CSV
- Macro news augmentation: Yahoo Finance news for `^TNX` and `^VIX`

### Request parameters

- `symbol = CL=F`
- `timeframe = 1d`
- `lookback = 90`
- `news_limit = 6`

### Actual fetched range

- requested start: `2025-12-15 14:56:27+00:00`
- requested end: `2026-04-14 14:56:27+00:00`
- first daily bar timestamp: `2025-12-15T00:00:00-05:00`
- last daily bar timestamp: `2026-04-14T00:00:00-04:00`
- daily bar count: `82`
- intraday bar count: `90`
- symbol news items: `6`
- macro indicator events: `5`
- macro news events: `6`

### Data quality / provider limits

- daily OHLCV bars were returned successfully with no empty-frame failure
- Yahoo daily bars do not provide full `quote_volume`, `trades`, or `vwap`; these fields remained `null`
- OrderFlow path is driven by real 1-minute bars, not true exchange order book depth
- no empty-value failure occurred in this run

## C. Six-Module Participation Matrix

| Module | Input data | Real-driven | Placeholder / skip | Participated in arbitration |
| -- | -- | -- | -- | -- |
| Fundamental | none for commodity mode | No | explicit `CommodityModeSkip`; no OHLCV proxying | No |
| Macro | FRED indicators + Yahoo macro news | Yes | some `forecast / previous / actual` fields remain partial | Yes |
| Technical | Yahoo daily OHLCV bars | Yes | none on main path | Yes |
| Chan | Yahoo daily OHLCV bars | Yes | none on main path | Yes |
| OrderFlow | Yahoo 1-minute recent bars | Yes, market approximation | `trade_prints`, `order_book_depth` missing | Yes, but contributed neutral |
| Sentiment | Yahoo news + daily bars | Yes | social / forum / analyst sentiment still placeholder | Yes, but contributed neutral |

### Per-module details

#### Fundamental

- mode: skipped
- reason: `CL=F` is non-equity and is explicitly treated as commodity mode
- audit conclusion: correct behavior; did not fake fundamental data from OHLCV

#### Macro

- inputs:
  - `US Fed Funds Rate`
  - `US CPI`
  - `US Unemployment Rate`
  - `CBOE VIX`
  - Yahoo macro headlines related to rates / volatility
- signal summary:
  - regime: `trending_down`
  - confidence: `0.6`
  - dominant themes: `risk_off`, `fed`
  - `vix_level = 19.12`

#### Technical

- input: real daily OHLCV bars
- signal summary:
  - direction: `flat`
  - confidence: `0.3`
  - regime: `ranging`
  - reasoning: `趋势=sideways | 动量=neutral | 波动率=neutral | 图表形态=double_top | K线形态=bearish_engulfing`

#### Chan

- input: real daily K-line sequence from Yahoo OHLCV
- signal summary:
  - direction: `short`
  - confidence: `0.4`
  - bi status: `down_forming`
  - zhongshu status: `no_center`

#### OrderFlow

- input: real recent 1-minute bars from Yahoo Finance
- signal summary:
  - book imbalance: `0.0`
  - expected slippage: `13.1`
  - execution condition: `fair`
- placeholder boundary:
  - no true trade prints
  - no true order book depth

#### Sentiment

- input: `6` Yahoo news items plus market-bar auxiliary context
- signal summary:
  - composite sentiment: `0.625`
  - bullish ratio: `0.625`
  - bearish ratio: `0.375`
  - sources count: `6`
- placeholder boundary:
  - social sentiment placeholder
  - forum sentiment placeholder
  - analyst sentiment placeholder

## D. Arbitration Result

### Module-level arbitration inputs actually used

- Technical:
  - direction: `flat`
  - confidence: `0.3`
  - contribution: `-0.15`
  - rule adjustments: `macro_risk_off: confidence *= 0.5`
- Chan:
  - direction: `short`
  - confidence: `0.4`
  - contribution: `-0.2`
  - rule adjustments:
    - `macro_risk_off: confidence *= 0.5`
    - `confidence_weight: chan *= 0.9`
- Macro:
  - direction: `short`
  - confidence: `0.6`
  - contribution: `-0.3`
  - rule adjustments:
    - `macro_risk_off: confidence *= 0.5`
    - `confidence_weight: macro *= 0.9`
- OrderFlow:
  - recorded into `DecisionRecord`
  - current contribution: neutral / zero-confidence
- Sentiment:
  - recorded into `DecisionRecord`
  - current contribution: neutral
- Fundamental:
  - skipped, no contribution

### Phase 6 final decision

- `decision_id = arb-CL=F-1479804765`
- bias: `short_bias`
- bias direction: `SHORT`
- confidence: `0.3846153846153846`
- `signal_count = 3`
- long score: `0.0`
- short score: `0.7692307692307692`
- neutrality score: `0.23076923076923075`
- macro regime: `risk_off`
- risk adjustment: `0.5`
- conflicts: none

### Rule-chain outcome

- fundamental veto: not triggered
- macro adjustment: triggered
- confidence weighting: triggered
- regime filter: triggered with `regime=ranging`

### Arbitration rationale conclusion

This WTI run formed a real short bias mainly from:

- Chan short structure
- Macro `risk_off / fed` pressure
- Technical neutral-to-bearish context with bearish engulfing and double-top evidence

The final confidence stayed moderate rather than high because:

- Technical was not outright short
- OrderFlow stayed neutral under approximation mode
- Sentiment was not strongly bearish

## E. Risk Result

### PositionPlan

- `plan_id = pp-4dee53e1`
- symbol: `CL=F`
- direction: `short`
- sizing method: `volatility_targeting`
- base quantity: `174.89947257036434`
- final quantity: `106.8376085792869`
- notional value: `10000.0`
- current price: `93.5999984741211`
- veto triggered: `False`

### Risk actions

- `cap`: yes
  - filter: `max_position_pct`
  - effect: `174.90 -> 106.84`
- `reduce`: no additional reduce filter beyond cap
- `veto`: no
- `exit`: no

### Limit checks

- `max_position_pct`: pass in `cap` mode
- `loss_limit`: pass
- `max_drawdown_pct`: pass
- `max_correlation`: pass
- `liquidity_cap`: pass
- `participation_rate`: pass
- `max_slippage_bps`: pass

### Execution plan summary

- execution action: `SELL`
- algorithm: `adaptive`
- urgency: `medium`
- target quantity: `106.8376085792869`
- limit price: `93.38`
- worst price: `93.04`
- estimated impact: `15.93 bps`
- estimated slippage: `4.779 bps`
- slice count: `20`
- target participation rate: `0.0003`

## F. Audit / Feedback Result

### Phase 8 write outcome

- `DecisionRecord` generated: Yes
  - `audit_id = dr-07b207257365`
- `RiskAudit` generated: Yes
  - `audit_id = ra-a7cd63fbcfd4`
- `Feedback` generated: No
  - count: `0`

### Why feedback was not written

The live scan completed without a threshold breach or review suggestion severe enough to emit a pending feedback item in this run, so `feedback_registry_appended = false`.

### Product-layer readback verification

After live runs, the product audit API read back real append-only records:

- `GET /api/v1/audit/decisions?limit=5` returned `CL=F` and `AAPL` records from `decision_registry`
- `GET /api/v1/audit/risk?limit=5` returned `CL=F` and `AAPL` records from `risk_registry`
- `GET /api/v1/audit/feedback?limit=5` returned an empty list because no feedback record was generated

## G. Real Parts Vs Placeholder Parts

### Real parts in this WTI run

- Yahoo real daily OHLCV bars
- Yahoo real recent 1-minute bars
- Yahoo real news items for the symbol
- FRED real macro indicators
- Yahoo real macro-related headlines
- real Phase 6 arbitration object
- real Phase 7 risk object
- real Phase 8 `DecisionRecord` write
- real Phase 8 `RiskAudit` write
- real product-layer audit readback for decisions and risk

### Explicit placeholder / partial parts

- Fundamental is `N/A` for commodity mode and therefore skipped
- OrderFlow lacks true exchange trade prints
- OrderFlow lacks full depth-of-book
- Sentiment still lacks social / forum / analyst channels
- Macro still has partial placeholder fields for some forecast/previous values
- no feedback record was generated in this particular WTI run

## H. Conclusion

### Direct answers

- WTI real data chain established: Yes
- Which parts were real-driven:
  - Technical, Chan, Macro, OrderFlow approximation, Sentiment news path, Arbitration, Risk, Decision audit, Risk audit
- Which parts remained placeholder or non-applicable:
  - Fundamental commodity skip
  - OrderFlow depth/trade-print gap
  - Sentiment non-news channels
  - partial Macro auxiliary fields
- WTI real data test passed: Yes
- Can this run be used as one proof item for project-level real-data closure: Yes

### Final judgment

`CL=F` can already serve as a valid commodity evidence case for the project's real-data live path. It proves that the system can ingest real Yahoo/FRED data, drive multiple analysis modules, produce a real arbitration decision, pass through risk control, and write append-only audit objects without falling back to manual scoring as the primary path.
