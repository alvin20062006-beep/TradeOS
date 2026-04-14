"""DecisionReviewManager — 人工仲裁复盘管理。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from core.audit.schemas.review import Review, ReviewStatus


class DecisionReviewManager:
    """
    管理 DecisionReview 记录的追加（append-only）。

    Review（人工复盘）与 Feedback（系统反馈）的边界：
    - Review 由人工填写，包含 accuracy_score / notes / verdict
    - Review 不替代 Feedback，两者互补

    数据持久化：~/.ai-trading-tool/audit/reviews/decision/{date}.jsonl
    """

    def __init__(self, base_path: str | None = None) -> None:
        if base_path is None:
            base = Path.home() / ".ai-trading-tool" / "audit" / "reviews" / "decision"
        else:
            base = Path(base_path)
        self._base = base
        self._base.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        audit_id: str,
        reviewer: str = "human",
    ) -> Review:
        """创建空的 DecisionReview（待填写）。"""
        review = Review(
            review_id=f"rev-dec-{uuid4().hex[:10]}",
            timestamp=datetime.utcnow(),
            audit_id=audit_id,
            review_type="decision",
            reviewer=reviewer,
            status=ReviewStatus.PENDING,
        )
        self._append(review)
        return review

    def complete(
        self,
        review_id: str,
        accuracy_score: float,
        verdict: str,
        notes: str = "",
        tags: list[str] | None = None,
        audit_id: str = "",
    ) -> Review:
        """完成并追加 Review 记录（append-only，不修改原记录）。"""
        completed = Review(
            review_id=f"{review_id}-completed",
            timestamp=datetime.utcnow(),
            audit_id=audit_id,
            review_type="decision",
            reviewer="human",
            accuracy_score=accuracy_score,
            verdict=verdict,
            notes=notes,
            tags=tags or [],
            status=ReviewStatus.COMPLETED,
            reviewed_at=datetime.utcnow(),
        )
        self._append(completed)
        return completed

    def list_pending(self) -> list[Review]:
        """
        列出所有 pending 状态的 Review。

        append-only 原则：已完成（completed）的原记录 status 不会被修改。
        因此通过检查是否存在对应 completed 版本来判断某 review_id 是否已完成。
        """
        all_reviews: list[Review] = []
        for path in sorted(self._base.glob("*.jsonl")):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        all_reviews.append(Review.model_validate_json(line))
                    except Exception:
                        pass

        # 找出所有已完成的 review_id（去掉了 "-completed" 后缀的原始 ID）
        completed_ids = {
            r.review_id.replace("-completed", "")
            for r in all_reviews
            if r.status == ReviewStatus.COMPLETED
        }

        return [
            r for r in all_reviews
            if r.status == ReviewStatus.PENDING
            and r.review_id not in completed_ids
        ]

    def _append(self, review: Review) -> None:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        path = self._base / f"{date_str}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(review.model_dump_json() + "\n")
