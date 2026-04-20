"""FeedbackRegistry — Feedback 持久化（append-only JSONL）。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from core.audit.schemas.feedback import Feedback, FeedbackStatus


class FeedbackRegistry:
    """
    Feedback 的追加写入和查询接口。

    append-only 原则：所有操作只追加新记录，不修改已有记录。

    数据路径：~/.ai-trading-tool/audit/feedback_registry/{YYYY-MM-DD}.jsonl

    使用方式：
        registry = FeedbackRegistry()
        registry.append(feedback)           # 追加
        registry.read_unprocessed()         # 读 pending
        registry.mark_reviewed(fb_id, "agent")  # 标记已复核
        registry.mark_rejected(fb_id, "agent", "reason")  # 标记拒绝
    """

    def __init__(self, base_path: str | None = None) -> None:
        if base_path is not None:
            base = Path(base_path)
        else:
            try:
                from infra.config.settings import get_settings

                base = get_settings().app_data_dir / "audit" / "feedback_registry"
            except Exception:
                base = Path(__file__).resolve().parents[3] / ".runtime" / "audit" / "feedback_registry"
        self._base = base
        self._base.mkdir(parents=True, exist_ok=True)

    def append(self, feedback: Feedback) -> None:
        """
        追加一条 Feedback 到当日文件（append-only）。

        仅接受 Feedback 类型，拒绝 Review 或其他 Pydantic model。
        """
        if not isinstance(feedback, Feedback):
            raise TypeError(
                f"FeedbackRegistry.append() requires Feedback, got {type(feedback).__name__}. "
                "Use ReviewManager for Review objects."
            )
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        path = self._base / f"{date_str}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(feedback.model_dump_json() + "\n")

    def append_many(self, feedbacks: List[Feedback]) -> None:
        """批量追加多条 Feedback。"""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        path = self._base / f"{date_str}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            for fb in feedbacks:
                if not isinstance(fb, Feedback):
                    raise TypeError(
                        f"FeedbackRegistry.append_many() requires Feedback[], "
                        f"got {type(fb).__name__}."
                    )
                f.write(fb.model_dump_json() + "\n")

    def read_all(self, since: datetime | None = None) -> List[Feedback]:
        """读取所有 Feedback（可选时间过滤）。"""
        feedbacks = []
        for path in sorted(self._base.glob("*.jsonl")):
            if since:
                # 跳过更早的日期
                date_part = path.stem  # "YYYY-MM-DD"
                try:
                    file_date = datetime.strptime(date_part, "%Y-%m-%d")
                    if file_date < since:
                        continue
                except ValueError:
                    pass
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        feedbacks.append(Feedback.model_validate_json(line))
                    except Exception:
                        pass
        return feedbacks

    def read_unprocessed(self) -> List[Feedback]:
        """
        读取所有待处理的 Feedback。

        append-only 原则：reviewed/rejected 状态的原记录 status 不会被修改。
        因此通过是否存在对应 reviewed/rejected 版本来判断是否仍待处理。
        """
        all_fb = self.read_all()

        # 已被 reviewed 或 rejected 的 feedback_id
        resolved_ids = {
            fb.feedback_id
            for fb in all_fb
            if fb.status in (FeedbackStatus.REVIEWED, FeedbackStatus.REJECTED)
        }

        return [
            fb for fb in all_fb
            if fb.feedback_id not in resolved_ids
            and fb.status == FeedbackStatus.PENDING
        ]

    def mark_reviewed(
        self,
        feedback_id: str,
        reviewer: str,
    ) -> None:
        """将 Feedback 标记为 reviewed（追加新记录，不修改原记录）。"""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        # 读取原记录，找到对应 feedback，追加 updated 版本
        all_fb = self.read_all()
        updated = None
        for fb in all_fb:
            if fb.feedback_id == feedback_id:
                updated = fb.model_copy(deep=True)
                updated.status = FeedbackStatus.REVIEWED
                updated.reviewed_by = reviewer
                updated.reviewed_at = datetime.utcnow()
                break

        if updated:
            path = self._base / f"{date_str}.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(updated.model_dump_json() + "\n")

    def mark_rejected(
        self,
        feedback_id: str,
        reviewer: str,
        reason: str,
    ) -> None:
        """将 Feedback 标记为 rejected（追加新记录）。"""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        all_fb = self.read_all()
        updated = None
        for fb in all_fb:
            if fb.feedback_id == feedback_id:
                updated = fb.model_copy(deep=True)
                updated.status = FeedbackStatus.REJECTED
                updated.reviewed_by = reviewer
                updated.reviewed_at = datetime.utcnow()
                updated.rejection_reason = reason
                break

        if updated:
            path = self._base / f"{date_str}.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(updated.model_dump_json() + "\n")
