"""
Execution Planner
==============

算法选择 + ExecutionPlan 生成。

算法选择矩阵：
  exit_bias              → MARKET（立即退出）
  impact > 100bps        → ICEBERG / ADAPTIVE
  impact 50-100bps       → VWAP / POV
  impact < 50bps + high  → MARKET
  impact < 50bps + medium → LIMIT / TWAP
  realized_vol > 30%     → ADAPTIVE
  order_book_depth < threshold → ICEBERG

阈值耦合说明（TODO: Phase 8 集中配置）:
  以下阈值硬编码分散在多处，后续应集中到 ExecutionThresholds dataclass：
  - impact_bps 阈值: 100 / 50（在 planner._select_algorithm + impact.py 中使用）
  - vol 阈值: 0.30（在 planner._select_algorithm 中使用）
  - ALGORITHM_PARAMS["impact_threshold_bps"]: 30（在 evaluator._compute_exec_score 中使用）
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from core.risk.context import MarketContext
from core.risk.evaluator import estimate
from core.risk.filters.slippage_limit import SlippageLimitFilter
from core.risk.schemas import ExecutionPlan, ExecutionSlice, ExecutionQualityReport
from core.risk.schemas import PositionPlan
from core.schemas import ExecutionQuality, OrderType, RiskLimits


# ─────────────────────────────────────────────────────────────
# Algorithm params
# ─────────────────────────────────────────────────────────────

ALGORITHM_PARAMS = {
    "TWAP": {
        "num_slices": 20,
        "slice_duration_seconds": 300,
        "randomize": True,
    },
    "VWAP": {
        "num_slices": 20,
        "randomize": True,
    },
    "POV": {
        "participation_rate": 0.10,
        "min_slice_interval_seconds": 60,
    },
    "ICEBERG": {
        "visible_size_ratio": 0.05,
        "reserve_type": "immediate",
    },
    "ADAPTIVE": {
        "impact_threshold_bps": 30,
        "adjust_interval_seconds": 60,
        "max_spread_bps": 20,
    },
}

MAX_PARTICIPATION = {
    "low": 0.05,
    "medium": 0.10,
    "high": 0.20,
}


# ─────────────────────────────────────────────────────────────
# ExecutionPlanner
# ─────────────────────────────────────────────────────────────

def plan(
    position_plan: PositionPlan,
    market_context: Optional[MarketContext] = None,
    risk_limits: Optional[RiskLimits] = None,
    arrival_price: Optional[float] = None,
    start_time: Optional[datetime] = None,
    *,
    urgency: str = "medium",
) -> ExecutionPlan:
    """
    生成执行计划。

    Parameters
    ----------
    position_plan : PositionPlan
        仓位计划（包含 final_quantity / direction）
    market_context : MarketContext, optional
        市场环境（用于冲击估计和算法选择）
    risk_limits : RiskLimits, optional
        风控限额
    arrival_price : float, optional
        到达价（用于滑点估算）
    start_time : datetime, optional
        开始时间（默认当前时间）
    urgency : str
        low / medium / high

    Returns
    -------
    ExecutionPlan
        含算法选择 / 切片 / 预估冲击 / pre_trade_report
    """
    qty = position_plan.final_quantity
    symbol = position_plan.symbol
    direction = position_plan.direction
    plan_id = f"ep-{uuid4().hex[:8]}"
    ts = start_time or datetime.utcnow()

    # arrival_price 来自 position_plan
    if arrival_price is None:
        arrival_price = market_context.current_price if market_context else 0.0
    notional = qty * arrival_price if arrival_price > 0 else 0.0

    # ── 平方根冲击预估 ──────────────────────────
    impact = _estimate_impact(qty, market_context)

    # ── 算法选择 ──────────────────────────────
    algorithm, algo_params = _select_algorithm(
        position_plan=position_plan,
        impact_bps=impact["impact_bps"],
        market_context=market_context,
        urgency=urgency,
    )

    # ── 参与率约束 ────────────────────────────
    max_pr, target_pr = _participation_rates(urgency, risk_limits)
    estimated_participation_rate = min(
        impact["participation_rate"], max_pr
    )

    # ── 限价 ─────────────────────────────────
    limit_price = _compute_limit_price(
        direction=direction,
        current_price=arrival_price,
        slippage_bps=impact["impact_bps"],
        algorithm=algorithm,
    )

    # ── 分片（TWAP/VWAP/POV/Adaptive） ──────
    slices = _build_slices(
        qty=qty,
        algorithm=algorithm,
        algo_params=algo_params,
        direction=direction,
        limit_price=limit_price,
        start_time=ts,
        time_limit=900,
    )

    # ── 执行评分 ─────────────────────────────
    slippage_bps = impact["impact_bps"] * 0.3
    exec_score = _compute_exec_score(
        impact_bps=impact["impact_bps"],
        slippage_bps=slippage_bps,
        max_participation=max_pr,
        estimated_participation_rate=estimated_participation_rate,
    )

    # ── Pre-trade 质量预估 ────────────────────
    pre_report: Optional[ExecutionQualityReport] = None
    if market_context and market_context.avg_daily_volume_20d > 0:
        # 构造最小 mock plan 以便 estimate 使用字段
        mock_plan = ExecutionPlan(
            plan_id=plan_id,
            position_plan_id=position_plan.plan_id,
            decision_id=position_plan.decision_id,
            timestamp=ts,
            symbol=symbol,
            direction=direction,
            target_quantity=qty,
            notional_value=notional,
            algorithm=algorithm,
            estimated_impact_bps=impact["impact_bps"],
            estimated_slippage_bps=slippage_bps,
            arrival_price=arrival_price,
        )
        pre_report = estimate(
            plan=mock_plan,
            avg_daily_volume_20d=market_context.avg_daily_volume_20d,
            realized_vol_20d=market_context.realized_vol_20d,
        )

    # ── 构造 ExecutionPlan ────────────────────
    end_time = ts + timedelta(seconds=900)
    notional = qty * arrival_price if arrival_price > 0 else 0.0

    plan_obj = ExecutionPlan(
        plan_id=plan_id,
        position_plan_id=position_plan.plan_id,
        decision_id=position_plan.decision_id,
        timestamp=ts,
        symbol=symbol,
        direction=direction,
        target_quantity=qty,
        notional_value=notional,
        algorithm=algorithm,
        algorithm_params=algo_params,
        urgency=urgency,
        limit_price=limit_price,
        worst_price=_worst_price(direction, limit_price, impact["impact_bps"]),
        arrival_price=arrival_price,
        time_limit_seconds=900,
        start_time=ts,
        end_time=end_time,
        max_participation_rate=max_pr,
        target_participation_rate=estimated_participation_rate,
        estimated_impact_bps=impact["impact_bps"],
        estimated_slippage_bps=slippage_bps,
        participation_risk=impact["suggested_action"].replace("reduce_", "").replace("_or_split", ""),
        slices=slices,
        execution_score=exec_score,
        score_factors={
            "impact_bps": impact["impact_bps"],
            "participation_rate": estimated_participation_rate,
            "urgency": urgency,
        },
        pre_trade_report=pre_report,
        metadata={
            "is_reducing": position_plan.is_reducing,
            "market_cap": market_context.market_cap if market_context else 0.0,
        },
    )

    return plan_obj


# ─────────────────────────────────────────────────────────────
# Algorithm selection
# ─────────────────────────────────────────────────────────────

def _select_algorithm(
    position_plan: PositionPlan,
    impact_bps: float,
    market_context: Optional[MarketContext],
    urgency: str,
) -> tuple[OrderType, dict]:
    """
    根据条件选择执行算法。

    优先级（从上到下）：
    1. exit_bias / reduce_risk → MARKET（立即退出/减仓）
    2. impact > 100bps → ICEBERG
    3. realized_vol > 30% → ADAPTIVE
    4. impact 50-100bps → VWAP
    5. impact < 50bps + high urgency → MARKET
    6. default → LIMIT（成本最优）
    """
    # 减仓/退出用 MARKET
    if position_plan.is_reducing:
        return OrderType.MARKET, {}

    # 冲击 > 100bps → ICEBERG
    if impact_bps > 100:
        return OrderType.ICEBERG, ALGORITHM_PARAMS["ICEBERG"]

    # 高波动 → ADAPTIVE
    if market_context and market_context.realized_vol_20d > 0.30:
        return OrderType.ADAPTIVE, ALGORITHM_PARAMS["ADAPTIVE"]

    # 冲击中等 → VWAP
    if 50 <= impact_bps <= 100:
        return OrderType.VWAP, ALGORITHM_PARAMS["VWAP"]

    # 低冲击 + 高紧急 → MARKET
    if urgency == "high":
        return OrderType.MARKET, {}

    # 低冲击 + 低紧急 → LIMIT
    if impact_bps < 50:
        return OrderType.LIMIT, {}

    # 兜底 → VWAP
    return OrderType.VWAP, ALGORITHM_PARAMS["VWAP"]


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _estimate_impact(qty: float, market_context: Optional[MarketContext]) -> dict:
    """估算市场冲击。"""
    if market_context is None:
        return {
            "impact_bps": 0.0,
            "participation_rate": 0.0,
            "is_acceptable": True,
            "is_warning": False,
            "suggested_action": "proceed",
        }

    # 平方根冲击（从 impact.py 导入）
    from core.risk.impact import estimate_square_root_impact

    return estimate_square_root_impact(
        quantity=qty,
        adv_20d=market_context.avg_daily_volume_20d,
        realized_vol=market_context.realized_vol_20d,
    )


def _participation_rates(
    urgency: str,
    risk_limits: Optional[RiskLimits],
) -> tuple[float, float]:
    """获取参与率上限和目标值。"""
    max_pr = MAX_PARTICIPATION.get(urgency, 0.10)
    target_pr = min(max_pr * 0.6, 0.05)
    return max_pr, target_pr


def _compute_limit_price(
    direction, current_price: float, slippage_bps: float, algorithm: OrderType
) -> Optional[float]:
    """计算限价（MARKET 无需限价）。"""
    if algorithm == OrderType.MARKET:
        return None
    if current_price <= 0:
        return None

    slippage = slippage_bps / 10_000
    if direction.value == "long":
        return round(current_price * (1 + slippage * 1.5), 2)
    else:
        return round(current_price * (1 - slippage * 1.5), 2)


def _worst_price(direction, limit_price, impact_bps: float) -> Optional[float]:
    """最差可接受价格。"""
    if limit_price is None or limit_price <= 0:
        return None
    slippage = (impact_bps + 20) / 10_000
    if direction.value == "long":
        return round(limit_price * (1 + slippage), 2)
    else:
        return round(limit_price * (1 - slippage), 2)


def _build_slices(
    qty: float,
    algorithm: OrderType,
    algo_params: dict,
    direction,
    limit_price: Optional[float],
    start_time: datetime,
    time_limit: int,
) -> List[ExecutionSlice]:
    """生成执行分片（TWAP/VWAP/POV/Adaptive）。"""
    if algorithm in (OrderType.MARKET, OrderType.LIMIT, OrderType.ICEBERG):
        return []

    slice_count = algo_params.get("num_slices", 20)
    qty_per_slice = qty / slice_count
    slice_duration = time_limit // slice_count

    slices = []
    for i in range(slice_count):
        slice_start = start_time + timedelta(seconds=i * slice_duration)
        slice_end = slice_start + timedelta(seconds=slice_duration)
        slices.append(
            ExecutionSlice(
                slice_id=i,
                quantity=round(qty_per_slice, 2),
                start_time=slice_start,
                end_time=slice_end,
                target_price=limit_price,
                order_type=OrderType.LIMIT,
            )
        )
    return slices


def _compute_exec_score(
    impact_bps: float,
    slippage_bps: float,
    max_participation: float,
    estimated_participation_rate: float,
) -> float:
    """计算执行计划质量评分（0-1）。"""
    impact_score = max(0.0, 1.0 - min(impact_bps / 100, 1.0))
    slip_score = max(0.0, 1.0 - min(slippage_bps / 50, 1.0))
    pr_score = max(0.0, 1.0 - estimated_participation_rate / max(max_participation, 0.01))
    return round(0.4 * impact_score + 0.3 * slip_score + 0.3 * pr_score, 3)
