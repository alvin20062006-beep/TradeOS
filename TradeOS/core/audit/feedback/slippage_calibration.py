"""SlippageCalibrationFeedback — 滑点校正反馈生成器。"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from core.audit.schemas.execution_record import ExecutionRecord
from core.audit.schemas.feedback import Feedback, FeedbackType, FeedbackStatus


class SlippageCalibrationFeedback:
    """
    比较预估算滑点 vs 实际滑点，生成校正 feedback。

    逻辑：
    - 按 symbol + order_type 聚合 ExecutionRecord
    - 计算 mean(realized_slippage) - mean(estimated_slippage) = bias
    - threshold: |bias| > 5bps → severity=high
    - threshold: 2bps < |bias| ≤ 5bps → severity=medium
    - threshold: |bias| ≤ 2bps → skip（正常范围）
    """

    MIN_SAMPLES = 20
    THRESHOLD_HIGH_BPS = 5.0
    THRESHOLD_MEDIUM_BPS = 2.0

    def generate(
        self,
        records: List[ExecutionRecord],
        symbol: str,
    ) -> List[Feedback]:
        """按 symbol 生成 slippage 校正 feedback。"""
        # 按 order_type 分桶
        by_type: Dict[str, List[ExecutionRecord]] = defaultdict(list)
        for rec in records:
            if rec.symbol == symbol and rec.estimated_slippage_bps != 0:
                by_type[rec.order_type].append(rec)

        feedbacks = []
        for order_type, recs in by_type.items():
            if len(recs) < self.MIN_SAMPLES:
                continue

            realized_vals = [r.realized_slippage_bps for r in recs]
            estimated_vals = [r.estimated_slippage_bps for r in recs]

            mean_realized = sum(realized_vals) / len(realized_vals)
            mean_estimated = sum(estimated_vals) / len(estimated_vals)
            bias = mean_realized - mean_estimated

            abs_bias = abs(bias)
            if abs_bias <= self.THRESHOLD_MEDIUM_BPS:
                continue

            severity = "high" if abs_bias > self.THRESHOLD_HIGH_BPS else "medium"

            feedbacks.append(
                Feedback(
                    feedback_id=f"fb-slip-{symbol}-{order_type}",
                    feedback_type=FeedbackType.SLIPPAGE_CALIBRATION,
                    severity=severity,
                    symbol=symbol,
                    sample_size=len(recs),
                    evidence={
                        "order_type": order_type,
                        "mean_realized_bps": round(mean_realized, 2),
                        "mean_estimated_bps": round(mean_estimated, 2),
                        "bias_bps": round(bias, 2),
                        "std_bps": round(
                            (sum((v - mean_realized) ** 2 for v in realized_vals)
                             / len(realized_vals)) ** 0.5, 2
                        ),
                    },
                    metric_name="slippage_bias_bps",
                    metric_value=round(bias, 2),
                    threshold_breach=abs_bias > self.THRESHOLD_HIGH_BPS,
                    suggested_action=(
                        f"调整 slippage 模型参数：对 {symbol} {order_type} "
                        f"预期偏置 {bias:+.1f}bps（实际 {mean_realized:+.1f}bps vs 预估 {mean_estimated:+.1f}bps）"
                    ),
                    confidence=min(len(recs) / 100, 0.95),
                    source_audit_ids=[r.audit_id for r in recs],
                    status=FeedbackStatus.PENDING,
                    phase4_suggestion={
                        "registry": "ExperimentRegistry",
                        "field": "slippage_model_params",
                        "symbol": symbol,
                        "order_type": order_type,
                        "suggested_bias_bps": round(bias, 2),
                        "suggested_action": "adjust" if severity == "high" else "monitor",
                    },
                )
            )

        return feedbacks
