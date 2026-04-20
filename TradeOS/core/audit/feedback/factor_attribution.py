"""Factor-attribution feedback generator."""

from __future__ import annotations

from collections import defaultdict

from core.audit.schemas.decision_record import DecisionRecord
from core.audit.schemas.feedback import Feedback, FeedbackStatus, FeedbackType


class FactorAttributionFeedback:
    """Generate minimal usable factor attribution from audited decision outcomes."""

    IR_THRESHOLD_LOW = 0.3
    IR_THRESHOLD_NEGATIVE = 0.0
    MIN_SAMPLES_MEDIUM = 30
    MIN_SAMPLES_HIGH = 50

    def generate(self, records: list[DecisionRecord]) -> list[Feedback]:
        grouped: dict[str, list[DecisionRecord]] = defaultdict(list)
        for record in records:
            if record.realized_pnl_pct is None:
                continue
            seen_modules: set[str] = set()
            for signal in record.input_signals:
                if signal.source_module in seen_modules:
                    continue
                grouped[signal.source_module].append(record)
                seen_modules.add(signal.source_module)

        feedbacks: list[Feedback] = []
        for module, module_records in grouped.items():
            if len(module_records) < self.MIN_SAMPLES_MEDIUM:
                continue

            pnl_values = [float(record.realized_pnl_pct or 0.0) for record in module_records]
            confidences = [
                float(signal.confidence)
                for record in module_records
                for signal in record.input_signals
                if signal.source_module == module
            ]
            mean_pnl = sum(pnl_values) / len(pnl_values)
            variance = sum((value - mean_pnl) ** 2 for value in pnl_values) / len(pnl_values)
            std_pnl = variance ** 0.5
            ir = mean_pnl / std_pnl if std_pnl > 1e-9 else mean_pnl
            if ir >= self.IR_THRESHOLD_LOW:
                continue

            severity = (
                "high"
                if len(module_records) >= self.MIN_SAMPLES_HIGH and ir < self.IR_THRESHOLD_NEGATIVE
                else "medium"
            )
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            alpha_contribution = mean_pnl * avg_confidence
            signal_contribution = sum(abs(value) for value in pnl_values) / len(pnl_values)

            feedbacks.append(
                Feedback(
                    feedback_id=f"fb-factor-{module}",
                    feedback_type=FeedbackType.FACTOR_ATTRIBUTION,
                    severity=severity,
                    symbol=None,
                    sample_size=len(module_records),
                    evidence={
                        "factor_module": module,
                        "mean_pnl_pct": round(mean_pnl * 100, 4),
                        "std_pnl_pct": round(std_pnl * 100, 4),
                        "ir": round(ir, 4),
                        "avg_signal_confidence": round(avg_confidence, 4),
                        "alpha_contribution": round(alpha_contribution, 6),
                        "signal_contribution": round(signal_contribution, 6),
                    },
                    metric_name="factor_ir",
                    metric_value=round(ir, 4),
                    threshold_breach=ir < self.IR_THRESHOLD_NEGATIVE,
                    suggested_action=(
                        f"factor={module} ir={ir:.4f} sample={len(module_records)} "
                        f"alpha_contribution={alpha_contribution:.6f}; lower weight or review"
                    ),
                    confidence=min(len(module_records) / 100, 0.9),
                    source_audit_ids=[record.audit_id for record in module_records],
                    status=FeedbackStatus.PENDING,
                    phase4_suggestion={
                        "registry": "AlphaFactorRegistry",
                        "field": "factor_ir",
                        "factor_module": module,
                        "current_ir": round(ir, 4),
                        "alpha_contribution": round(alpha_contribution, 6),
                        "signal_contribution": round(signal_contribution, 6),
                        "suggested_action": "downweight" if severity == "medium" else "deprecate",
                    },
                )
            )

        return feedbacks
