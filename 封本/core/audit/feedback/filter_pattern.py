"""FilterPatternFeedback — 风控过滤器模式反馈生成器。"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from core.audit.schemas.risk_audit import RiskAudit
from core.audit.schemas.feedback import Feedback, FeedbackType, FeedbackStatus


class FilterPatternFeedback:
    """
    分析风控过滤器 veto 模式，生成反馈。

    逻辑：
    - 按 filter_name + regime 分桶 RiskAudit
    - 计算每个 bucket 的 veto_rate = veto_count / total_count
    - threshold: veto_rate > 30% 且 n ≥ 20 → severity=high
    - threshold: 20% < veto_rate ≤ 30% 且 n ≥ 10 → severity=medium
    """

    VETO_RATE_HIGH = 0.30
    VETO_RATE_MEDIUM = 0.20
    MIN_SAMPLES_HIGH = 20
    MIN_SAMPLES_MEDIUM = 10

    def generate(
        self,
        audits: List[RiskAudit],
    ) -> List[Feedback]:
        """扫描 RiskAudit[]，生成过滤器模式 feedback。"""
        # 按 filter_name + regime 分桶
        by_key: Dict[str, Dict] = defaultdict(lambda: {"veto": 0, "total": 0, "audits": []})

        for audit in audits:
            regime = audit.regime or "unknown"
            for fr in audit.filter_results:
                key = f"{fr.filter_name}|{regime}"
                by_key[key]["total"] += 1
                by_key[key]["audits"].append(audit.audit_id)
                if fr.mode == "veto":
                    by_key[key]["veto"] += 1

        feedbacks = []
        for key, data in by_key.items():
            filter_name, regime = key.split("|", 1)
            veto_rate = data["veto"] / data["total"] if data["total"] > 0 else 0
            n = data["total"]

            if veto_rate <= self.VETO_RATE_MEDIUM:
                continue

            if veto_rate > self.VETO_RATE_HIGH and n >= self.MIN_SAMPLES_HIGH:
                severity = "high"
            elif veto_rate > self.VETO_RATE_MEDIUM and n >= self.MIN_SAMPLES_MEDIUM:
                severity = "medium"
            else:
                continue

            feedbacks.append(
                Feedback(
                    feedback_id=f"fb-filter-{filter_name}-{regime}",
                    feedback_type=FeedbackType.FILTER_PATTERN,
                    severity=severity,
                    symbol=None,
                    sample_size=n,
                    evidence={
                        "filter_name": filter_name,
                        "regime": regime,
                        "veto_count": data["veto"],
                        "total_count": n,
                        "veto_rate": round(veto_rate, 3),
                    },
                    metric_name="filter_veto_rate",
                    metric_value=round(veto_rate, 3),
                    threshold_breach=veto_rate > self.VETO_RATE_HIGH,
                    suggested_action=(
                        f"过滤器 {filter_name} 在 {regime} 市场状态下 veto 率 {veto_rate:.1%}（n={n}），"
                        f"建议检查风控阈值或模型训练数据"
                    ),
                    confidence=min(n / 50, 0.9),
                    source_audit_ids=data["audits"],
                    status=FeedbackStatus.PENDING,
                    phase4_suggestion={
                        "registry": "ModelRegistry",
                        "field": "flag_for_retrain",
                        "filter_name": filter_name,
                        "regime": regime,
                        "veto_rate": round(veto_rate, 3),
                        "suggested_action": "retrain" if severity == "high" else "review_threshold",
                    },
                )
            )

        return feedbacks
