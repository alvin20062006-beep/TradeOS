"""StrategyRegistry — 策略注册表（append-only）。

所有策略变更通过追加记录实现，不修改或删除已有记录。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.strategy_pool.schemas.strategy import StrategySpec, StrategyStatus


class StrategyRegistry:
    """
    策略注册表。

    append-only 原则：
    - register / activate / deactivate / deprecate 均追加新记录
    - 不修改或删除已有记录
    - 通过时间戳排序取最新版本来获取当前状态
    """

    def __init__(self, base_path: Optional[str] = None) -> None:
        if base_path:
            self._base = Path(base_path)
        else:
            self._base = Path.home() / ".ai-trading-tool" / "strategy_registry"
        self._base.mkdir(parents=True, exist_ok=True)

    def _file_path(self, date_str: Optional[str] = None) -> Path:
        if date_str is None:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
        return self._base / f"{date_str}.jsonl"

    def _append(self, spec: StrategySpec) -> None:
        path = self._file_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(spec.model_dump_json() + "\n")

    def read_all(self) -> List[StrategySpec]:
        """读取所有策略记录。"""
        records: List[StrategySpec] = []
        for path in sorted(self._base.glob("*.jsonl")):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(StrategySpec.model_validate_json(line))
                    except Exception:
                        pass
        return records

    def _latest_versions(self) -> Dict[str, StrategySpec]:
        """
        获取每个 strategy_id 的最新版本。

        append-only 原则：多条记录可能存在同一 strategy_id，
        以注册时间最新的一条为当前有效版本。
        """
        all_records = self.read_all()
        latest: Dict[str, StrategySpec] = {}
        for spec in all_records:
            existing = latest.get(spec.strategy_id)
            if existing is None:
                latest[spec.strategy_id] = spec
            else:
                # 统一为 timestamp 秒级比较（naive vs aware 均安全）
                existing_ts = existing.registered_at.timestamp()
                spec_ts = spec.registered_at.timestamp()
                if spec_ts > existing_ts:
                    latest[spec.strategy_id] = spec
        return latest

    def register(self, spec: StrategySpec) -> StrategySpec:
        """注册新策略（append-only）。"""
        latest = self._latest_versions()
        if spec.strategy_id in latest:
            raise ValueError(
                f"Strategy '{spec.strategy_id}' already exists. "
                "Use update() or a new strategy_id."
            )
        self._append(spec)
        return spec

    def get(self, strategy_id: str) -> Optional[StrategySpec]:
        """获取策略的当前有效版本。"""
        return self._latest_versions().get(strategy_id)

    def list_all(self) -> List[StrategySpec]:
        """列出所有策略的当前有效版本。"""
        return list(self._latest_versions().values())

    def list_by_status(self, status: StrategyStatus) -> List[StrategySpec]:
        """按状态过滤策略列表。"""
        return [
            s for s in self._latest_versions().values()
            if s.status == status
        ]

    def activate(self, strategy_id: str) -> Optional[StrategySpec]:
        """
        激活策略（append-only）。

        追加一条新的 ACTIVE 记录，不修改原 CANDIDATE/INACTIVE 记录。
        DEPRECATED 策略不可激活（返回 None）。
        """
        spec = self.get(strategy_id)
        if spec is None:
            return None
        if spec.status == StrategyStatus.DEPRECATED:
            return None  # 永久下架不可激活

        updated = spec.model_copy(deep=True)
        updated.status = StrategyStatus.ACTIVE
        updated.activated_at = datetime.utcnow()
        updated.registered_at = datetime.utcnow()
        self._append(updated)
        return updated

    def deactivate(self, strategy_id: str) -> Optional[StrategySpec]:
        """
        停用策略（append-only）。

        ACTIVE → INACTIVE，可重新激活。
        """
        spec = self.get(strategy_id)
        if spec is None:
            return None

        updated = spec.model_copy(deep=True)
        updated.status = StrategyStatus.INACTIVE
        updated.deactivated_at = datetime.utcnow()
        updated.registered_at = datetime.utcnow()
        self._append(updated)
        return updated

    def deprecate(self, strategy_id: str, reason: str = "") -> Optional[StrategySpec]:
        """
        下架策略（append-only）。

        INACTIVE → DEPRECATED，永久下架。
        """
        spec = self.get(strategy_id)
        if spec is None:
            return None

        updated = spec.model_copy(deep=True)
        updated.status = StrategyStatus.DEPRECATED
        updated.deprecation_reason = reason
        # 先更新时间戳再追加，确保最新版本为 DEPRECATED
        # （activate() 会读到最新版本，如果时间戳更新则 activate 失效）
        updated.registered_at = datetime.utcnow()
        self._append(updated)
        return updated

    def reactivate(self, strategy_id: str) -> Optional[StrategySpec]:
        """
        重新激活策略（append-only）。

        INACTIVE → ACTIVE。
        """
        spec = self.get(strategy_id)
        if spec is None:
            return None
        if spec.status != StrategyStatus.INACTIVE:
            return None

        updated = spec.model_copy(deep=True)
        updated.status = StrategyStatus.ACTIVE
        updated.activated_at = datetime.utcnow()
        updated.deprecation_reason = None
        updated.registered_at = datetime.utcnow()
        self._append(updated)
        return updated
