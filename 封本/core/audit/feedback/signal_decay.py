"""SignalDecayFeedback — 信号衰减反馈生成器。"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from core.audit.schemas.decision_record import DecisionRecord
from core.audit.schemas.feedback import Feedback, FeedbackType, FeedbackStatus


class SignalDecayFeedback:
    """
    分析信号年龄 vs realized_pnl，生成信号衰减 feedback。

    逻辑：
    - 按 signal_type 分桶 DecisionRecord
    - 按 age_bucket 分桶：<24h / 24-48h / 48-72h / >72h
    - 计算每个 bucket 的 mean(realized_pnl)
    - threshold: 某 bucket 的 mean_pnl < 0（负期望）且 n ≥ 10 → severity=high
    - threshold: 某 bucket 的 mean_pnl < 0 且 n ≥ 5 → severity=medium
    """

    MIN_SAMPLES_HIGH = 10
    MIN_SAMPLES_MEDIUM = 5

    AGE_BUCKETS = [
        ("<24h", 0, 24),
        ("24-48h", 24, 48),
        ("48-72h", 48, 72),
        (">72h", 72, float("inf")),
    ]

    def generate(
        self,
        records: List[DecisionRecord],
    ) -> List[Feedback]:
        """扫描所有 DecisionRecord，生成信号衰减 feedback。"""
        # 按 signal_type 分桶
        by_signal_type: Dict[str, List[DecisionRecord]] = defaultdict(list)
        for rec in records:
            if rec.realized_pnl_pct is not None:
                for sig in rec.input_signals:
                    key = f"{sig.source_module}:{sig.signal_type}"
                    by_signal_type[key].append(rec)

        feedbacks = []
        for signal_type_key, recs in by_signal_type.items():
            feedbacks.extend(self._analyze_signal_type(signal_type_key, recs))

        return feedbacks

    def _analyze_signal_type(
        self,
        signal_type_key: str,
        records: List[DecisionRecord],
    ) -> List[Feedback]:
        """分析单个信号类型的衰减模式。"""
        # 按 age_bucket 分桶
        by_bucket: Dict[str, List[DecisionRecord]] = defaultdict(list)
        for rec in records:
            age = rec.signal_age_hours
            if age is None:
                continue
            for bucket_name, lo, hi in self.AGE_BUCKETS:
                if lo <= age < hi:
                    by_bucket[bucket_name].append(rec)
                    break

        feedbacks = []
        for bucket_name, recs in by_bucket.items():
            n = len(recs)
            if n < self.MIN_SAMPLES_MEDIUM:
                continue

            pnl_vals = [r.realized_pnl_pct for r in recs]
            mean_pnl = sum(pnl_vals) / n

            if mean_pnl >= 0:
                continue  # 正期望，不生成 feedback

            if n >= self.MIN_SAMPLES_HIGH:
                severity = "high"
            else:
                severity = "medium"

            module, sig_type = signal_type_key.split(":", 1)
            feedbacks.append(
                Feedback(
                    feedback_id=f"fb-decay-{signal_type_key.replace(':', '-')}-{bucket_name}",
                    feedback_type=FeedbackType.SIGNAL_DECAY,
                    severity=severity,
                    symbol=None,  # 全市场聚合
                    sample_size=n,
                    evidence={
                        "signal_module": module,
                        "signal_type": sig_type,
                        "age_bucket": bucket_name,
                        "mean_pnl_pct": round(mean_pnl * 100, 3),
                        "positive_count": sum(1 for p in pnl_vals if p > 0),
                        "negative_count": sum(1 for p in pnl_vals if p < 0),
                    },
                    metric_name="signal_age_pnl_pct",
                    metric_value=round(mean_pnl * 100, 3),
                    threshold_breach=mean_pnl < 0,
                    suggested_action=(
                        f"信号 {signal_type_key} 在 {bucket_name} 窗口内平均收益 {mean_pnl*100:+.2f}%（负期望）"
                        f"，建议缩短标签窗口或降低置信权重"
                    ),
                    confidence=min(n / 50, 0.9),
                    source_audit_ids=[r.audit_id for r in recs],
                    status=FeedbackStatus.PENDING,
                    phase4_suggestion={
                        "registry": "LabelSetRegistry",
                        "field": "label_window_hours",
                        "signal_module": module,
                        "signal_type": sig_type,
                        "current_bucket": bucket_name,
                        "suggested_action": "shorten_window",
                    },
                )
            )

        return feedbacks
