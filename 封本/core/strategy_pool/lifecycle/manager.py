"""StrategyLifecycleManager — 策略启/停/下架/候选状态机。"""
from __future__ import annotations

from typing import List, Optional

from core.strategy_pool.registry.strategy_registry import StrategyRegistry
from core.strategy_pool.schemas.strategy import StrategySpec, StrategyStatus


class StrategyLifecycleManager:
    """
    策略生命周期管理器。

    封装 StrategyRegistry 的状态变更操作，提供清晰的状态机语义：
    CANDIDATE → ACTIVE → INACTIVE → DEPRECATED
    """

    def __init__(self, registry: Optional[StrategyRegistry] = None) -> None:
        self._registry = registry or StrategyRegistry()

    # ── 状态查询 ────────────────────────────────────

    def list_candidates(self) -> List[StrategySpec]:
        """列出所有候选策略。"""
        return self._registry.list_by_status(StrategyStatus.CANDIDATE)

    def list_active(self) -> List[StrategySpec]:
        """列出所有启用策略。"""
        return self._registry.list_by_status(StrategyStatus.ACTIVE)

    def list_inactive(self) -> List[StrategySpec]:
        """列出所有停用策略。"""
        return self._registry.list_by_status(StrategyStatus.INACTIVE)

    def list_deprecated(self) -> List[StrategySpec]:
        """列出所有已下架策略。"""
        return self._registry.list_by_status(StrategyStatus.DEPRECATED)

    def get_status(self, strategy_id: str) -> Optional[StrategyStatus]:
        """获取策略当前状态。"""
        spec = self._registry.get(strategy_id)
        return spec.status if spec else None

    # ── 状态变更 ────────────────────────────────────

    def activate(self, strategy_id: str) -> Optional[StrategySpec]:
        """
        激活候选策略。

        CANDIDATE → ACTIVE
        已在 ACTIVE 状态的策略返回 None。
        """
        spec = self._registry.get(strategy_id)
        if spec is None:
            return None
        if spec.status == StrategyStatus.ACTIVE:
            return spec  # 已是 ACTIVE
        if spec.status == StrategyStatus.DEPRECATED:
            return None  # 已下架不可激活
        return self._registry.activate(strategy_id)

    def deactivate(self, strategy_id: str) -> Optional[StrategySpec]:
        """
        停用策略。

        ACTIVE → INACTIVE（可重新激活）。
        """
        spec = self._registry.get(strategy_id)
        if spec is None:
            return None
        if spec.status in (StrategyStatus.INACTIVE, StrategyStatus.DEPRECATED):
            return spec  # 已是 INACTIVE 或 DEPRECATED
        return self._registry.deactivate(strategy_id)

    def deprecate(self, strategy_id: str, reason: str = "") -> Optional[StrategySpec]:
        """
        下架策略。

        INACTIVE → DEPRECATED（永久下架，不可重新激活）。
        ACTIVE → INACTIVE → DEPRECATED（需先停用）。
        DEPRECATED 不可重复下架。
        """
        spec = self._registry.get(strategy_id)
        if spec is None:
            return None
        if spec.status == StrategyStatus.DEPRECATED:
            return spec  # 已下架
        if spec.status == StrategyStatus.ACTIVE:
            self._registry.deactivate(strategy_id)
        return self._registry.deprecate(strategy_id, reason)

    def reactivate(self, strategy_id: str) -> Optional[StrategySpec]:
        """
        重新激活已停用策略。

        INACTIVE → ACTIVE。
        DEPRECATED 不可重新激活。
        """
        spec = self._registry.get(strategy_id)
        if spec is None:
            return None
        if spec.status == StrategyStatus.DEPRECATED:
            return None  # 永久下架
        return self._registry.reactivate(strategy_id)

    def promote(self, strategy_id: str) -> Optional[StrategySpec]:
        """
        将候选策略提升为激活（activate 的别名，语义更明确）。

        CANDIDATE → ACTIVE
        """
        return self.activate(strategy_id)
