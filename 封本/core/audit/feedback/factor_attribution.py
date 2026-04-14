"""FactorAttributionFeedback — 因子归因反馈生成器。"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from core.audit.schemas.decision_record import DecisionRecord
from core.audit.schemas.feedback import Feedback, FeedbackType, FeedbackStatus


class FactorAttributionFeedback:
    """
    按 alpha_factor_id 聚合 DecisionRecord，计算因子实现收益。

    逻辑：
    - 按 signal.source_module 分桶（作为因子代理）
    - 聚合 realized_pnl_pct
    - 计算 IC ≈ mean(pnl) / std(pnl)（简化 IR）
    - threshold: IR < 0.3 且 n ≥ 30（持续负/低效）→ severity=medium
    - threshold: IR < 0 且 n ≥ 50 → severity=high
    """

    IR_THRESHOLD_LOW = 0.3
    IR_THRESHOLD_NEGATIVE = 0.0
    MIN_SAMPLES_MEDIUM = 30
    MIN_SAMPLES_HIGH = 50

    def generate(
        self,
        records: List[DecisionRecord],
    ) -> List[Feedback]:
        """扫描 DecisionRecord[]，生成因子归因 feedback。"""
        # 按 source_module 分桶
        by_factor: Dict[str, List[DecisionRecord]] = defaultdict(list)
        for rec in records:
            if rec.realized_pnl_pct is None:
                continue
            for sig in rec.input_signals:
                module = sig.source_module
                by_factor[module].append(rec)

        feedbacks = []
        for factor, recs in by_factor.items():
            if len(recs) < self.MIN_SAMPLES_MEDIUM:
                continue

            pnl_vals = [r.realized_pnl_pct for r in recs]
            mean_pnl = sum(pnl_vals) / len(pnl_vals)
            variance = sum((v - mean_pnl) ** 2 for v in pnl_vals) / len(pnl_vals)
            std_pnl = variance ** 0.5
            ir = mean_pnl / std_pnl if std_pnl > 0 else 0.0

            if ir >= self.IR_THRESHOLD_LOW:
                continue  # IR 正常，不生成 feedback

            if len(recs) >= self.MIN_SAMPLES_HIGH and ir < self.IR_THRESHOLD_NEGATIVE:
                severity = "high"
            else:
                severity = "medium"

            feedbacks.append(
                Feedback(
                    feedback_id=f"fb-factor-{factor}",
                    feedback_type=FeedbackType.FACTOR_ATTRIBUTION,
                    severity=severity,
                    symbol=None,
                    sample_size=len(recs),
                    evidence={
                        "factor_module": factor,
                        "mean_pnl_pct": round(mean_pnl * 100, 3),
                        "std_pnl_pct": round(std_pnl * 100, 3),
                        "ir": round(ir, 3),
                        "n": len(recs),
                    },
                    metric_name="factor_ir",
                    metric_value=round(ir, 3),
                    threshold_breach=ir < self.IR_THRESHOLD_NEGATIVE,
                    suggested_action=(
                        f"因子模块 {factor} IR={ir:.3f}（{'负' if ir < 0 else '低'}），n={len(recs)}，"
                        f"建议下调 confidence_weight 或标记待下架"
                    ),
                    confidence=min(len(recs) / 100, 0.9),
                    source_audit_ids=[r.audit_id for r in recs],
                    status=FeedbackStatus.PENDING,
                    phase4_suggestion={
                        "registry": "AlphaFactorRegistry",
                        "field": "ir",
                        "factor_module": factor,
                        "current_ir": round(ir, 3),
                        "suggested_action": "downweight" if severity == "medium" else "deprecate",
                    },
                )
            )

        return feedbacks
