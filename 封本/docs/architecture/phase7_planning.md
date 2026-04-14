# Phase 7 规划文档（修正版）

**项目**: ai-trading-tool  
**阶段**: Phase 7 — 仓位计算、风控约束、执行计划  
**版本**: 1.1.0（修正版）  
**日期**: 2026-04-11  
**状态**: 规划阶段，等待确认后实施

---

## 核心定位（明确）

Phase 7 只做两件事：

1. **ArbitrationDecision → PositionPlan**：把仲裁层决策转化为仓位计划（含 sizing 算法 + 风控约束）
2. **PositionPlan → ExecutionIntent / ExecutionPlan**：把仓位计划映射为可执行的订单指令

**不做**：
- 不重写 Phase 3 执行底盘
- 不重写 Phase 6 仲裁层
- 不自建独立 schema 体系

---

## 一、Schema 边界（修正1）

### 1.1 复用的 schema

| Schema | 来源 | Phase 7 中用途 |
|--------|------|----------------|
| `ArbitrationDecision` | `core.schemas` | 输入：仲裁层决策 |
| `RiskLimits` | `core.schemas` | 输入：风控限额配置 |
| `ExecutionIntent` | `core.schemas` | 输出：对接 Phase 3 执行底盘 |
| `OrderRecord` | `core.schemas` | post-trade 输入：订单记录 |
| `FillRecord` | `core.schemas` | post-trade 输入：成交记录 |
| `Position` | `core.schemas` | 输入：当前仓位状态 |
| `Portfolio` | `core.schemas` | 输入：组合资金状态 |

### 1.2 新增的 schema（仅3个）

| Schema | 用途 | 理由 |
|--------|------|------|
| `PositionPlan` | 仓位计算中间结果 | 仲裁决策 → 最终仓位的桥梁，含 sizing 方法/约束记录 |
| `ExecutionPlan` | 执行计划中间对象 | 包含算法选择/切片/预估冲击，供 Phase 3 或 Phase 8 调用 |
| `ExecutionQualityReport` | 执行质量报告 | pre-trade 预估 + post-trade 实际评估结果 |

**原则**：三个新增 schema 风格与 `core.schemas` 保持一致（Pydantic BaseModel），不另起 dataclass 体系。

### 1.3 Phase 3 已有 ExecutionIntent 字段分析

```python
# ExecutionIntent 已有字段（Phase 3 定义）：
intent_id, decision_id, timestamp, symbol, direction,
quantity, price_limit, order_type,
time_limit_seconds, participation_rate,
algo_params, risk_adjusted, original_quantity, metadata

# Phase 7 需从 PositionPlan 映射到 ExecutionIntent：
quantity         ← PositionPlan.final_quantity
order_type      ← ExecutionPlan.algorithm
price_limit     ← ExecutionPlan.limit_price
participation_rate ← ExecutionPlan.max_participation_rate
algo_params     ← ExecutionPlan.algorithm_params
risk_adjusted   ← PositionPlan.veto_triggered (bool)
```

---

## 二、文件树（修正版）

```
core/risk/
├── __init__.py
│
├── schemas.py                      # 新增 PositionPlan / ExecutionPlan（与 core.schemas 风格一致）
│
├── context.py                     # MarketContext：聚合当前市场数据（ADV/波动率/盘口）
│
├── calculators/                   # 仓位 sizing 计算器
│   ├── __init__.py
│   ├── base.py                   # PositionCalculator ABC
│   ├── fixed_fraction.py         # Fixed Fraction
│   ├── volatility_targeting.py   # Volatility Targeting
│   ├── kelly_fraction.py         # Kelly Criterion（半 Kelly）
│   ├── conviction_weighted.py     # 仲裁置信度权重
│   ├── drawdown_adjusted.py      # 回撤调整
│   └── regime_based.py            # 市场状态修饰
│
├── filters/                      # 风控过滤器链
│   ├── __init__.py
│   ├── base.py                   # RiskFilter ABC
│   ├── position_limit.py         # max_position_pct
│   ├── loss_limit.py             # max_loss_pct_per_trade / per_day
│   ├── drawdown_limit.py         # max_drawdown_pct
│   ├── correlation_limit.py      # max_correlation
│   ├── liquidity_cap.py          # ADV 调整仓位上限
│   ├── participation_rate.py     # 参与率上限
│   └── slippage_limit.py         # max_slippage_bps
│
├── impact.py                     # Square-root impact estimator（修正2）
│
├── planner.py                    # ExecutionPlanner：算法选择 → ExecutionPlan
│
├── evaluator.py                  # 执行质量评估（修正3：拆分为 pre / post 两层）
│
├── engine.py                     # RiskEngine：协调全链路（核心入口）
│
└── tests/
    ├── __init__.py
    ├── test_calculators.py       # 六种 sizing 算法测试
    ├── test_filters.py           # 八种风控过滤器测试
    ├── test_impact.py            # 平方根冲击模型测试
    ├── test_planner.py           # 执行计划生成测试
    ├── test_evaluator.py         # pre-trade 预估 + post-trade 评估测试
    └── test_engine.py            # 全链路集成测试
```

---

## 三、每个文件职责

| 文件 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `schemas.py` | 新增 PositionPlan / ExecutionPlan / ExecutionQualityReport | — | Pydantic Model |
| `context.py` | MarketContext：聚合 ADV/波动率/盘口/市值 | Position / Portfolio / MarketBar | MarketContext dataclass |
| `calculators/base.py` | `PositionCalculator` ABC | ArbitrationDecision / RiskLimits / Portfolio / MarketContext | `dict[str, float]` 各算法 qty |
| `calculators/fixed_fraction.py` | 固定风险比例 | portfolio_equity × fixed_pct / stop_dist | qty |
| `calculators/volatility_targeting.py` | 目标组合波动率 | portfolio_equity × target_vol / (price × realized_vol) | qty |
| `calculators/kelly_fraction.py` | 半 Kelly Criterion | win_rate / avg_win / avg_loss | qty（半 Kelly） |
| `calculators/conviction_weighted.py` | 置信度权重 | arbitration_confidence | qty = base × confidence |
| `calculators/drawdown_adjusted.py` | 回撤调整 | base_qty × max(0, 1 - drawdown_ratio) | qty |
| `calculators/regime_based.py` | 市场状态修饰 | regime × base_qty | qty × regime_multiplier |
| `filters/base.py` | `RiskFilter` ABC | qty / RiskLimits / Portfolio / MarketContext | (passed: bool, adjusted_qty: float) |
| `filters/position_limit.py` | max_position_pct | portfolio_equity × limit_pct / price | filtered qty |
| `filters/loss_limit.py` | 亏损限额 | avg_entry × qty × loss_pct | veto or filtered |
| `filters/drawdown_limit.py` | 回撤限额 | current_drawdown / max_drawdown | veto or filtered |
| `filters/correlation_limit.py` | 相关性限额 | positions correlation matrix | veto or filtered |
| `filters/liquidity_cap.py` | ADV 约束 | qty / adv_20d | capped qty |
| `filters/participation_rate.py` | 参与率上限 | qty × price / adv_20d | limited qty |
| `filters/slippage_limit.py` | 滑点限额 | estimated_slippage_bps / max_slippage_bps | veto or filtered |
| `impact.py` | Square-root impact estimator | qty / adv_20d / realized_vol | estimated_impact_bps |
| `planner.py` | 执行算法选择 | PositionPlan / MarketContext / RiskLimits | ExecutionPlan |
| `evaluator.py` | 执行质量评估 | pre: ExecutionPlan / MarketContext → pre_report / post: OrderRecord[] / FillRecord[] → realized_report | ExecutionQualityReport |
| `engine.py` | RiskEngine：协调全链路 | ArbitrationDecision / RiskLimits / Portfolio / MarketContext | PositionPlan (+ ExecutionPlan) |

---

## 四、Pre-trade vs Post-trade 评估划分（修正3）

### 4.1 Pre-trade（必做）

```
ExecutionPlanner.plan()
    │
    ├─ Square-root impact estimator（impact.py）
    │     → estimated_impact_bps
    │
    ├─ Slippage estimator（经验模型）
    │     → estimated_slippage_bps
    │
    └─ Participation risk estimator
          → participation_rate
          → participation_risk: "low" / "medium" / "high"
```

Pre-trade 输出 → `ExecutionQualityReport（pre_trade=True）`

**用途**：给执行前的人工确认或 Phase 8 自动决策提供依据。

### 4.2 Post-trade（预留接口，最小实现）

```
Phase 3 执行结果 → evaluator.evaluate_post_trade()
    │
    ├─ slippage_bps = (avg_fill_price - arrival_price) / arrival_price × 10000
    ├─ market_impact_bps = (close_price - arrival_price) / arrival_price × 10000
    ├─ implementation_shortfall = (avg_fill_price - arrival_price) × qty / portfolio_equity
    └─ execution_score = weighted(slippage + impact + fill_rate + timing)
```

**关键**：post-trade 的 `arrival_price`（到达价）从 Phase 3 的 `OrderRecord`/`FillRecord` 中获取，不在 Phase 7 自建数据管道。

Phase 3 执行层已有 `avg_fill_price` / `slippage_bps` 字段，Phase 7 post-trade evaluator 直接消费这些字段。

---

## 五、执行算法选择逻辑

### 5.1 算法选择矩阵

| 条件 | 算法 | 说明 |
|------|------|------|
| bias = exit_bias | MARKET | 立即退出，无条件 |
| estimated_impact > 100 bps | ICEBERG / ADAPTIVE | 冲击过高，隐藏大单 |
| estimated_impact 50-100 bps | VWAP / POV | 中等冲击，分时执行 |
| estimated_impact < 50 bps + urgency=high | MARKET | 低冲击 + 紧急，即时 |
| estimated_impact < 50 bps + urgency=medium | LIMIT / TWAP | 低冲击 + 不紧急，成本最优 |
| realized_vol > 30% | ADAPTIVE | 高波动，动态调整 |
| order_book_depth < threshold | ICEBERG | 盘口浅，冰山订单 |

### 5.2 参与率约束

```python
MAX_PARTICIPATION = {
    "low": 0.05,      # 5%  ADV/天（最小市场干扰）
    "medium": 0.10,   # 10%  ADV/天（标准）
    "high": 0.20,     # 20%  ADV/天（大单/紧急）
}
```

---

## 六、Square-root Impact Estimator（修正2）

```python
def estimate_square_root_impact(
    quantity: float,
    adv_20d: float,
    realized_vol: float,
    lambda_param: float = 0.1,
) -> dict:
    """
    Square-root market impact estimator.
    
    公式：impact_bps ≈ λ × σ × √(Q / ADV)
    
    其中：
      λ = 流动性参数（经验值 0.05-0.2，可通过回测校准）
      σ = 年化已实现波动率
      Q = 目标数量
      ADV = 20日平均成交量
    
    示例：
      quantity = 300 shares
      adv_20d = 10000 shares
      realized_vol = 25% (年化)
      λ = 0.1
      
      impact_bps = 0.1 × 0.25 × √(300/10000)
              = 0.1 × 0.25 × 0.173
              ≈ 433 bps → 警告：降低参与率
    
    注意：这是近似估计，不做完整 Almgren-Chriss 执行调度。
          完整 AC 调度（最优执行路径）→ Phase 8 扩展项。
    """
    if adv_20d <= 0 or quantity <= 0:
        return {"impact_bps": 0.0, "is_acceptable": True}
    
    participation = quantity / adv_20d
    impact = lambda_param * realized_vol * (participation ** 0.5)
    impact_bps = impact * 10000  # → bps
    
    return {
        "impact_bps": round(impact_bps, 2),
        "participation_rate": round(participation, 4),
        "is_acceptable": impact_bps < 50,   # 硬阈值
        "is_warning": 50 <= impact_bps < 100,
        "suggested_action": (
            "reduce_participation" if impact_bps >= 50
            else "proceed"
        ),
    }
```

---

## 七、仓位 Sizing 算法优先级链

```
输入：ArbitrationDecision + RiskLimits + Portfolio + MarketContext

第1步：基础数量（Volatility Targeting）
  qty_vt = portfolio_equity × target_annual_vol / (price × realized_vol_20d)

第2步：Kelly 修正（若可用历史数据）
  kelly = (b × p - q) / b
  qty_kelly = qty_vt × kelly / 2  （半 Kelly）

第3步：置信度权重
  qty_conviction = qty_vt × arbitration_confidence

第4步：基础数量（Fixed Fraction，保守备选）
  qty_ff = portfolio_equity × fixed_risk_pct / atr_14

第5步：取最大可用数量（考虑当前回撤）
  base_qty = max(qty_vt, qty_kelly, qty_conviction, qty_ff)
  qty_dd = base_qty × max(0, 1 - drawdown_ratio)
  qty_final = qty_dd × regime_multiplier

第6步：风控过滤器链
  qty_filtered = filters.apply(qty_final, risk_limits, portfolio, market_context)

输出：PositionPlan(final_quantity=qty_filtered)
```

---

## 八、验收清单（修正版）

### A. Schema 边界

- [ ] A1. `PositionPlan` schema 新增，风格与 `core.schemas` 一致（Pydantic BaseModel）
- [ ] A2. `ExecutionPlan` schema 新增（含 algorithm/slices/estimated_impact/pre_trade_report）
- [ ] A3. `ExecutionQualityReport` schema 新增（含 `is_pre_trade: bool` 区分预估/实际）
- [ ] A4. 不新增与 `ArbitrationDecision` / `ExecutionIntent` 平行的冗余 schema
- [ ] A5. `PositionPlan.final_quantity` → `ExecutionIntent.quantity` 映射逻辑存在 `engine.py`

### B. 市场环境聚合

- [ ] B1. `MarketContext` dataclass 聚合：ADV20d / realized_vol_20d / atr_14 / bid_ask_spread / market_cap
- [ ] B2. `context.py` 有从 `Portfolio` + `Position` + `MarketBar` 构建 `MarketContext` 的工厂函数
- [ ] B3. `MarketContext` 在 market_context=None 时有默认值或 fallback 逻辑

### C. 仓位计算器

- [ ] C1. `PositionCalculator.calculate()` 主入口（优先级链协调）
- [ ] C2. `volatility_targeting.py`（目标组合波动率，基准算法）
- [ ] C3. `kelly_fraction.py`（半 Kelly，有历史数据时启用）
- [ ] C4. `conviction_weighted.py`（仲裁置信度权重）
- [ ] C5. `fixed_fraction.py`（ATR 止损距离版）
- [ ] C6. `drawdown_adjusted.py`（回撤调整）
- [ ] C7. `regime_based.py`（市场状态修饰）
- [ ] C8. 优先级链正确：VolTargeting → Kelly → Conviction → Fixed → Drawdown → Regime

### D. 风控过滤器

- [ ] D1. `RiskFilter` ABC + 统一 `apply(qty, ...)` 接口
- [ ] D2. `PositionLimitFilter`（max_position_pct）
- [ ] D3. `LossLimitFilter`（per_trade / per_day）
- [ ] D4. `DrawdownLimitFilter`（max_drawdown_pct）
- [ ] D5. `CorrelationLimitFilter`（positions 相关性矩阵）
- [ ] D6. `LiquidityCapFilter`（qty / adv_20d → capped qty）
- [ ] D7. `ParticipationRateFilter`（参与率上限）
- [ ] D8. `SlippageLimitFilter`（estimated_slippage vs max_slippage_bps）
- [ ] D9. 任意过滤器 veto → `PositionPlan.veto_triggered = True` 且 `final_quantity = 0`

### E. 执行计划

- [ ] E1. `ExecutionPlanner.plan()` 主入口
- [ ] E2. Square-root impact estimator（impact.py）：`λ × σ × √(Q/ADV)` → impact_bps
- [ ] E3. 算法选择矩阵（5个条件分支 → 正确算法）
- [ ] E4. `ExecutionSlice` 列表（TWAP/VWAP/POV/Adaptive 分片逻辑）
- [ ] E5. `ExecutionPlan` 生成（含 estimated_impact_bps / estimated_slippage_bps / execution_score）
- [ ] E6. `ExecutionPlan` → `ExecutionIntent` 映射（algo_params / participation_rate / price_limit）

### F. 执行质量评估

- [ ] F1. `Evaluator.estimate()`（pre-trade）：基于 ExecutionPlan + MarketContext 输出预估值
- [ ] F2. `Evaluator.evaluate()`（post-trade）：基于 OrderRecord[] + FillRecord[] 输出实际报告
- [ ] F3. post-trade 输入明确：avg_fill_price / arrival_price / slippage_bps 均来自 Phase 3
- [ ] F4. `compute_score()`：4因子加权（slippage 30% + impact 30% + fill_rate 20% + timing 20%）
- [ ] F5. 评分 → rating 映射（EXCELLENT ≥ 0.85 / GOOD ≥ 0.70 / FAIR ≥ 0.50 / POOR ≥ 0.30 / FAILED < 0.30）
- [ ] F6. `vs_plan_xxx_bps` 偏离计算（实际 vs 预估）

### G. 风控引擎

- [ ] G1. `RiskEngine.calculate()` 主入口（唯一对外入口）
- [ ] G2. ArbitrationDecision.bias = no_trade/exit/reduce → 直接返回 PositionPlan(quantity=0)
- [ ] G3. ArbitrationDecision.bias = long/short → 进入 sizing → 过滤器链 → PositionPlan
- [ ] G4. PositionPlan → ExecutionPlanner → ExecutionPlan
- [ ] G5. 全链路 latency 记录（arbitration_latency_ms）

### H. 兼容性

- [ ] H1. 输入兼容 Phase 6 `core.arbitration.ArbitrationDecision`（bias/confidence）
- [ ] H2. 输出兼容 Phase 3 `ExecutionIntent` schema
- [ ] H3. 不重写 Phase 3 执行底盘
- [ ] H4. 不重写 Phase 6 仲裁层
- [ ] H5. Phase 7 只做"转换 + 约束"，不做自循环策略

### I. 单元测试

- [ ] I1. 六种 sizing 算法独立测试（已知输入 → 预期输出）
- [ ] I2. 八种过滤器独立测试（限额内 / 超限场景）
- [ ] I3. Square-root impact estimator 测试（已知案例验证公式）
- [ ] I4. 执行计划生成测试（不同条件 → 正确算法选择）
- [ ] I5. pre-trade 预估测试（ExecutionPlan → expected values）
- [ ] I6. post-trade 评估测试（FillRecord[] → realized report）
- [ ] I7. 风控引擎集成测试（全链路端到端）
- [ ] I8. veto 场景测试（过滤器触发 → 零仓位 + reason）
- [ ] I9. Phase 1-6 现有测试全部回归通过

---

## 九、关键设计决定

1. **dataclass 仅用于 MarketContext**：MarketContext 是纯数据聚合器（无验证需求），使用 `@dataclass`；三个核心 schema（PositionPlan / ExecutionPlan / ExecutionQualityReport）用 Pydantic BaseModel。

2. **不重写执行层**：Phase 3 执行底盘已有 `ExecutionIntent` 接口，Phase 7 只生成可映射到该接口的数据，不自建执行管道。

3. **Square-root impact ≠ Almgren-Chriss**：Phase 7 只做冲击估计，完整 AC 最优执行调度 → Phase 8 扩展项。

4. **Pre-trade 和 post-trade 用同一个 Report schema**：通过 `is_pre_trade: bool` 字段区分，预估时 `realized_*` 字段为空，事后填充。

5. **Kelly 半 Kelly**：全 Kelly 过于激进，默认 `Kelly / 2`。

6. **过滤器链不过滤 0**：当 `qty = 0`（已 veto）时，跳过所有后续过滤器直接返回 zero plan。
