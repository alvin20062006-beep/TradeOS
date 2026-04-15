"""
Ensemble Scorer
==============

将所有 SignalScore 聚合成 long_score / short_score / neutrality_score，
并确定最终 bias。

bias 确定规则：
  - 长得分 >> 短得分 → long_bias
  - 短得分 >> 长得分 → short_bias
  - 得分相近（差距 < threshold）→ hold_bias
  - veto 已触发 → no_trade（由 FundamentalVetoRule 设置）
  - risk_adjustment < 1.0 → reduce_risk
  - 得分均为 0 → no_trade
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from core.schemas import Direction

from core.arbitration.schemas import SignalScore

if TYPE_CHECKING:
    from core.arbitration.schemas import ArbitrationDecision


class EnsembleScorer:
    """
    集成评分器。
    """

    # bias 判定阈值（相对差距百分比）
    BIAS_GAP = 0.3

    def aggregate(
        self,
        scores: List[SignalScore],
        decision: "ArbitrationDecision",
    ) -> None:
        """
        计算 long_score / short_score / neutrality_score，
        并更新 decision.bias。

        Args:
            scores:   所有信号评分
            decision: 仲裁决策（in-place 修改）
        """
        # 过滤零贡献信号
        active = [s for s in scores if s.contribution != 0]

        # 分类聚合
        long_scores = [s.contribution for s in active if s.direction == Direction.LONG]
        short_scores = [s.contribution for s in active if s.direction == Direction.SHORT]

        decision.long_score = max(sum(long_scores), 0.0)
        decision.short_score = max(abs(sum(short_scores)), 0.0)  # SHORT contribution 恒负，用绝对值

        # neutrality：来自 flat 方向或降权信号
        flat_scores = [s.contribution for s in active if s.direction == Direction.FLAT]
        neutral_sum = sum(flat_scores)
        decision.neutrality_score = min(abs(neutral_sum), 1.0)

        # 归一化到 0-1
        total = decision.long_score + decision.short_score + decision.neutrality_score
        if total > 0:
            decision.long_score /= total
            decision.short_score /= total
            decision.neutrality_score /= total

        # 确定 bias（已被 veto 规则覆盖时跳过）
        if decision.fundamental_veto_triggered:
            decision.bias = "no_trade"
            return

        # risk_adjustment 已由 MacroAdjustmentRule 设置
        # 若 risk_adjustment < 0.7，发出 reduce_risk 信号
        if decision.risk_adjustment < 0.7 and decision.bias not in ("no_trade",):
            decision.bias = "reduce_risk"
            return

        # 正常 bias 判定
        ls = decision.long_score
        ss = decision.short_score
        ns = decision.neutrality_score

        if ls == 0 and ss == 0:
            decision.bias = "no_trade"
            return

        diff = ls - ss
        gap = abs(diff)

        if gap < self.BIAS_GAP:
            decision.bias = "hold_bias"
        elif ls > ss:
            decision.bias = "long_bias"
        else:
            decision.bias = "short_bias"

        # 决策置信度：取最强方向的得分
        decision.confidence = max(ls, ss, ns)

        # apply risk_adjustment to confidence
        decision.confidence *= decision.risk_adjustment
