"""
Execution Quality Evaluator
=========================

Pre-trade estimate : 基于 ExecutionPlan + MarketContext 输出预估报告
Post-trade evaluation : 基于 Phase 3 OrderRecord[] / FillRecord[] 输出实际评估报告

共用同一个 ExecutionQualityReport schema，is_pre_trade 字段区分。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from core.risk.impact import estimate_square_root_impact
from core.risk.schemas import ExecutionPlan, ExecutionQualityReport
from core.schemas import ExecutionQuality, FillRecord, OrderRecord


# ─────────────────────────────────────────────────────────────
# Pre-trade estimate
# ─────────────────────────────────────────────────────────────

def estimate(
    plan: ExecutionPlan,
    *,
    avg_daily_volume_20d: float = 0.0,
    realized_vol_20d: float = 0.0,
    lambda_param: float = 0.1,
) -> ExecutionQualityReport:
    """
    Pre-trade 执行质量预估。

    Parameters
    ----------
    plan : ExecutionPlan
        执行计划（含 target_quantity / algorithm / limit_price）
    avg_daily_volume_20d : float
        20日平均成交量（股数/天）
    realized_vol_20d : float
        年化已实现波动率
    lambda_param : float
        Square-root impact 流动性参数（默认 0.1）

    Returns
    -------
    ExecutionQualityReport (is_pre_trade=True)
        预估滑点 / 冲击 / 参与率 / participation_risk
    """
    qty = plan.target_quantity
    symbol = plan.symbol
    timestamp = plan.timestamp or datetime.utcnow()
    direction = plan.direction

    # Square-root impact estimate
    impact = estimate_square_root_impact(
        quantity=qty,
        adv_20d=avg_daily_volume_20d,
        realized_vol=realized_vol_20d,
        lambda_param=lambda_param,
    )

    # Slippage estimate：盘口价差 + 冲击的一半（经验）
    estimated_slippage_bps = (
        plan.limit_price is not None
        and plan.arrival_price is not None
        and plan.arrival_price > 0
    ) and round(
        abs(plan.limit_price - plan.arrival_price) / plan.arrival_price * 10_000, 2
    ) or impact["impact_bps"] * 0.3  # fallback

    # Participation risk
    participation_risk = _participation_risk_from_impact(impact)

    # Pre-trade score（预估，不含 timing/fill_rate）
    slip_score = _slip_score(estimated_slippage_bps, estimated_slippage_bps * 2)
    impact_score = _impact_score(impact["impact_bps"], impact["impact_bps"] * 2)

    execution_score = round(0.4 * slip_score + 0.6 * impact_score, 3)
    quality_rating = _score_to_rating(execution_score)

    report = ExecutionQualityReport(
        evaluation_id=f"pre-{uuid4().hex[:8]}",
        plan_id=plan.plan_id,
        is_pre_trade=True,
        symbol=symbol,
        direction=direction,
        timestamp=timestamp,
        estimated_slippage_bps=estimated_slippage_bps,
        estimated_impact_bps=impact["impact_bps"],
        estimated_participation_rate=impact["participation_rate"],
        participation_risk=participation_risk,
        execution_score=execution_score,
        quality_rating=quality_rating,
        slippage_score=slip_score,
        impact_score=impact_score,
        fill_rate_score=0.0,  # pre-trade 无成交率
        timing_score=0.0,     # pre-trade 无时机
        metadata={
            "lambda_param": lambda_param,
            "adv_used": avg_daily_volume_20d,
            "realized_vol_used": realized_vol_20d,
            "arrival_price": plan.arrival_price,
        },
    )

    return report


# ─────────────────────────────────────────────────────────────
# Post-trade evaluation
# ─────────────────────────────────────────────────────────────

def evaluate(
    plan: ExecutionPlan,
    fills: List[FillRecord],
    orders: List[OrderRecord],
    *,
    arrival_price: Optional[float] = None,
    reference_price: Optional[float] = None,
) -> ExecutionQualityReport:
    """
    Post-trade 执行质量评估。

    基于 Phase 3 执行层返回的 OrderRecord[] / FillRecord[]。

    Parameters
    ----------
    plan : ExecutionPlan
        原始执行计划（用于 vs_plan 比较）
    fills : list[FillRecord]
        Phase 3 返回的成交记录
    orders : list[OrderRecord]
        Phase 3 返回的订单记录
    arrival_price : float, optional
        到达价（若不提供，从第一个 fill 的 price 估算）
    reference_price : float, optional
        参考价（VWAP 开始价等）

    Returns
    -------
    ExecutionQualityReport (is_pre_trade=False)
        realized_slippage_bps / realized_impact_bps / execution_score
    """
    if not fills:
        return _failed_report(plan, "no fills received")

    timestamp = fills[0].timestamp if fills else datetime.utcnow()
    symbol = plan.symbol
    direction = plan.direction

    # 实际执行数据
    total_filled = sum(f.quantity for f in fills)
    avg_fill_price = sum(f.price * f.quantity for f in fills) / total_filled if total_filled > 0 else 0.0

    # arrival_price：从 plan 或 fill 推断
    if arrival_price is None:
        arrival_price = reference_price or (fills[0].price if fills else plan.arrival_price)

    # Slippage：avg_fill vs arrival
    slippage_bps = 0.0
    if arrival_price and arrival_price > 0 and avg_fill_price > 0:
        slippage_bps = round(abs(avg_fill_price - arrival_price) / arrival_price * 10_000, 2)

    # Market impact：从 close_price 分离（简化版）
    # 实际冲击 = (avg_fill - arrival) - slippage（简化：直接用 avg_fill vs arrival）
    impact_bps = slippage_bps  # 简化：事后冲击 ≈ 滑点（完整版需 close price）

    # Implementation shortfall
    notional_cost = total_filled * avg_fill_price
    shortfall_bps = 0.0
    if arrival_price > 0 and total_filled > 0:
        shortfall_bps = round(
            abs(avg_fill_price - arrival_price) * total_filled / (plan.target_quantity * arrival_price) * 10_000,
            2,
        )

    # Participation rate
    fill_rate = min(total_filled / plan.target_quantity, 1.0) if plan.target_quantity > 0 else 0.0

    # Pre-trade 基准（来自 plan）
    est_slip = plan.estimated_slippage_bps or 0.0
    est_impact = plan.estimated_impact_bps or 0.0

    # vs plan 偏离
    vs_plan_slip = round(slippage_bps - est_slip, 2)
    vs_plan_impact = round(impact_bps - est_impact, 2)

    # 评分
    slip_score = _slip_score(slippage_bps, est_slip * 2)
    impact_score = _impact_score(impact_bps, est_impact * 2)
    fill_score = min(fill_rate, 1.0)
    timing_score = 0.5  # timing 评分需要 Phase 3 提供 timing metadata

    execution_score = round(
        0.30 * slip_score + 0.30 * impact_score + 0.20 * fill_score + 0.20 * timing_score,
        3,
    )
    quality_rating = _score_to_rating(execution_score)

    # 时间
    start_time = fills[0].timestamp
    end_time = fills[-1].timestamp
    duration = (end_time - start_time).total_seconds() if start_time and end_time else 0.0

    report = ExecutionQualityReport(
        evaluation_id=f"post-{uuid4().hex[:8]}",
        plan_id=plan.plan_id,
        is_pre_trade=False,
        symbol=symbol,
        direction=direction,
        timestamp=timestamp,
        arrival_price=arrival_price,
        avg_fill_price=avg_fill_price,
        actual_filled_quantity=total_filled,
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration,
        realized_slippage_bps=slippage_bps,
        realized_impact_bps=impact_bps,
        implementation_shortfall_bps=shortfall_bps,
        fill_rate=fill_rate,
        execution_score=execution_score,
        quality_rating=quality_rating,
        slippage_score=slip_score,
        impact_score=impact_score,
        fill_rate_score=fill_score,
        timing_score=timing_score,
        vs_plan_slippage_bps=vs_plan_slip,
        vs_plan_impact_bps=vs_plan_impact,
        metadata={
            "num_fills": len(fills),
            "num_orders": len(orders),
            "arrival_price_used": arrival_price,
        },
    )

    return report


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _participation_risk_from_impact(impact: dict) -> str:
    if impact["impact_bps"] >= 100:
        return "high"
    elif impact["impact_bps"] >= 50:
        return "medium"
    return "low"


def _slip_score(slippage_bps: float, ceiling: float) -> float:
    ceiling = max(ceiling, 20.0)
    return round(max(0.0, 1.0 - slippage_bps / ceiling), 3)


def _impact_score(impact_bps: float, ceiling: float) -> float:
    # TODO: ceiling=100 硬编码，应从 ExecutionThresholds 集中配置（Phase 8）
    ceiling = max(ceiling, 100.0)
    return round(max(0.0, 1.0 - impact_bps / ceiling), 3)


def _score_to_rating(score: float) -> ExecutionQuality:
    if score >= 0.85:
        return ExecutionQuality.EXCELLENT
    elif score >= 0.70:
        return ExecutionQuality.GOOD
    elif score >= 0.50:
        return ExecutionQuality.FAIR
    elif score >= 0.30:
        return ExecutionQuality.POOR
    return ExecutionQuality.FAILED


def _failed_report(plan: ExecutionPlan, reason: str) -> ExecutionQualityReport:
    return ExecutionQualityReport(
        evaluation_id=f"fail-{uuid4().hex[:8]}",
        plan_id=plan.plan_id,
        is_pre_trade=False,
        symbol=plan.symbol,
        direction=plan.direction,
        timestamp=datetime.utcnow(),
        execution_score=0.0,
        quality_rating=ExecutionQuality.FAILED,
        slippage_score=0.0,
        impact_score=0.0,
        fill_rate_score=0.0,
        timing_score=0.0,
        metadata={"failure_reason": reason},
    )
