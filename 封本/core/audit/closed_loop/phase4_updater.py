"""Phase4Updater — Feedback → Phase 4 候选更新建议（不直接改 registry）。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from core.audit.schemas.feedback import Feedback, FeedbackStatus


class Phase4CandidateUpdate:
    """
    Phase 4 候选更新建议（由 Phase4Updater 根据 Feedback 生成）。

    本轮不动 Phase 4 registry 真值，只输出：
    - suggestion: 人类可读建议
    - flag: Phase 4 可处理的标记
    - candidate_update: 候选变更结构（供 Phase 4 后续处理）

    由 Phase 4 或人工确认后，candidate_update 才写入 ExperimentRegistry。
    """

    def __init__(
        self,
        feedback: Feedback,
        suggestion: str,
        flag: dict,
        candidate_update: dict,
    ) -> None:
        self.feedback_id = feedback.feedback_id
        self.feedback_type = feedback.feedback_type
        self.severity = feedback.severity
        self.timestamp = datetime.utcnow()
        self.suggestion = suggestion
        self.flag = flag
        self.candidate_update = candidate_update
        self.status: str = "pending"  # pending / approved / rejected

    def to_dict(self) -> dict:
        return {
            "candidate_update_id": f"cu-{self.feedback_id}",
            "feedback_id": self.feedback_id,
            "feedback_type": self.feedback_type,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "suggestion": self.suggestion,
            "flag": self.flag,
            "candidate_update": self.candidate_update,
            "status": self.status,
        }


class Phase4Updater:
    """
    将 Feedback 转换为 Phase 4 候选更新建议。

    原则：
    - 不直接修改 Phase 4 registry 真值
    - 只生成 candidate_update 写入 staging 目录
    - 由 Phase 4 或人工确认后才正式应用

    使用方式：
        updater = Phase4Updater()
        candidates = updater.process(feedback_registry)
        for cu in candidates:
            print(cu.suggestion)
    """

    def __init__(self, staging_path: str | None = None) -> None:
        if staging_path is None:
            staging = Path.home() / ".ai-trading-tool" / "audit" / "phase4_candidates"
        else:
            staging = Path(staging_path)
        self._staging = staging
        self._staging.mkdir(parents=True, exist_ok=True)

    def process(self, feedback_registry) -> List[Phase4CandidateUpdate]:
        """
        处理所有 pending feedback，生成 Phase 4 候选更新。

        Args:
            feedback_registry: FeedbackRegistry 实例

        Returns:
            Phase4CandidateUpdate[] — 所有候选更新建议
        """
        feedbacks = feedback_registry.read_unprocessed()
        candidates: List[Phase4CandidateUpdate] = []

        for fb in feedbacks:
            if fb.status != FeedbackStatus.PENDING:
                continue
            cu = self._process_single(fb)
            if cu:
                candidates.append(cu)
                self._write_candidate(cu)

        return candidates

    def _process_single(self, feedback: Feedback) -> Phase4CandidateUpdate | None:
        """根据 Feedback 类型生成候选更新。"""
        if feedback.feedback_type.value == "slippage_calibration":
            return self._slippage_candidate(feedback)
        elif feedback.feedback_type.value == "signal_decay":
            return self._signal_decay_candidate(feedback)
        elif feedback.feedback_type.value == "filter_pattern":
            return self._filter_pattern_candidate(feedback)
        elif feedback.feedback_type.value == "factor_attribution":
            return self._factor_attribution_candidate(feedback)
        return None

    def _slippage_candidate(self, fb: Feedback) -> Phase4CandidateUpdate:
        e = fb.evidence
        return Phase4CandidateUpdate(
            feedback=fb,
            suggestion=fb.suggested_action,
            flag={
                "type": "slippage_calibration",
                "symbol": fb.symbol,
                "order_type": e.get("order_type"),
                "bias_bps": e.get("bias_bps"),
                "severity": fb.severity,
            },
            candidate_update={
                "registry": "ExperimentRegistry",
                "action": "update_slippage_model",
                "symbol": fb.symbol,
                "order_type": e.get("order_type"),
                "suggested_bias_bps": e.get("bias_bps", 0),
                "evidence": e,
            },
        )

    def _signal_decay_candidate(self, fb: Feedback) -> Phase4CandidateUpdate:
        e = fb.evidence
        return Phase4CandidateUpdate(
            feedback=fb,
            suggestion=fb.suggested_action,
            flag={
                "type": "signal_decay",
                "signal_module": e.get("signal_module"),
                "signal_type": e.get("signal_type"),
                "age_bucket": e.get("age_bucket"),
                "severity": fb.severity,
            },
            candidate_update={
                "registry": "LabelSetRegistry",
                "action": "review_label_window",
                "signal_module": e.get("signal_module"),
                "signal_type": e.get("signal_type"),
                "current_bucket": e.get("age_bucket"),
                "suggested_action": "shorten_window",
                "evidence": e,
            },
        )

    def _filter_pattern_candidate(self, fb: Feedback) -> Phase4CandidateUpdate:
        e = fb.evidence
        return Phase4CandidateUpdate(
            feedback=fb,
            suggestion=fb.suggested_action,
            flag={
                "type": "filter_pattern",
                "filter_name": e.get("filter_name"),
                "regime": e.get("regime"),
                "veto_rate": e.get("veto_rate"),
                "severity": fb.severity,
            },
            candidate_update={
                "registry": "ModelRegistry",
                "action": "flag_for_retrain",
                "filter_name": e.get("filter_name"),
                "regime": e.get("regime"),
                "suggested_action": "retrain" if fb.severity == "high" else "review_threshold",
                "evidence": e,
            },
        )

    def _factor_attribution_candidate(self, fb: Feedback) -> Phase4CandidateUpdate:
        e = fb.evidence
        return Phase4CandidateUpdate(
            feedback=fb,
            suggestion=fb.suggested_action,
            flag={
                "type": "factor_attribution",
                "factor_module": e.get("factor_module"),
                "ir": e.get("ir"),
                "severity": fb.severity,
            },
            candidate_update={
                "registry": "AlphaFactorRegistry",
                "action": "update_factor_ir",
                "factor_module": e.get("factor_module"),
                "suggested_ir": e.get("ir"),
                "suggested_action": "downweight" if fb.severity == "medium" else "deprecate",
                "evidence": e,
            },
        )

    def _write_candidate(self, cu: Phase4CandidateUpdate) -> None:
        """将候选更新写入 staging 目录。"""
        import json
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        path = self._staging / f"{date_str}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(cu.to_dict(), ensure_ascii=False) + "\n")
