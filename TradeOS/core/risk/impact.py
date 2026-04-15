"""
Square-Root Market Impact Estimator
=================================

近似公式：impact_bps ≈ λ × σ × √(Q / ADV)

这是 square-root impact 近似估计，非完整的 Almgren-Chriss 最优执行调度。
完整 AC 执行调度 → Phase 8 扩展项。

阈值耦合（TODO: Phase 8 集中配置）:
  50 / 100 bps 阈值与 planner.py _select_algorithm 硬编码耦合，
  应在 ExecutionThresholds dataclass 中统一管理。

Phase 7 实现：
- Square-root impact 估算
- participation rate 计算
- 参与率风险评估
"""

from __future__ import annotations


def estimate_square_root_impact(
    quantity: float,
    adv_20d: float,
    realized_vol: float,
    lambda_param: float = 0.1,
) -> dict:
    """
    Square-root market impact estimator.

    公式：impact_bps ≈ λ × σ × √(Q / ADV)

    Parameters
    ----------
    quantity : float
        目标数量（股数）
    adv_20d : float
        20日平均成交量（股数/天）
    realized_vol : float
        年化已实现波动率（小数，如 0.25 = 25%）
    lambda_param : float
        流动性参数（经验值 0.05-0.2，默认 0.1）

    Returns
    -------
    dict
        impact_bps             : 估算市场冲击（bps）
        participation_rate      : 参与率（Q / ADV）
        is_acceptable          : 是否可接受（impact < 50bps）
        is_warning             : 是否警告（50 <= impact < 100bps）
        suggested_action        : 建议动作

    示例
    ----
      quantity = 300, adv_20d = 10000, realized_vol = 0.25, λ = 0.1
      impact = 0.1 × 0.25 × √(300/10000)
            = 0.1 × 0.25 × 0.173
            ≈ 433 bps → 警告：降低参与率
    """
    if adv_20d <= 0 or quantity <= 0 or realized_vol <= 0:
        return {
            "impact_bps": 0.0,
            "participation_rate": 0.0,
            "is_acceptable": True,
            "is_warning": False,
            "suggested_action": "proceed",
        }

    participation = quantity / adv_20d
    impact = lambda_param * realized_vol * (participation ** 0.5)
    impact_bps = round(impact * 10_000, 2)

    is_acceptable = impact_bps < 50
    is_warning = 50 <= impact_bps < 100

    if impact_bps >= 100:
        suggested_action = "reduce_participation_or_split"
    elif impact_bps >= 50:
        suggested_action = "reduce_participation"
    else:
        suggested_action = "proceed"

    return {
        "impact_bps": impact_bps,
        "participation_rate": round(participation, 4),
        "is_acceptable": is_acceptable,
        "is_warning": is_warning,
        "suggested_action": suggested_action,
    }
