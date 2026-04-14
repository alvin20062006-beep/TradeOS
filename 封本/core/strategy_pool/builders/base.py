"""StrategyBuilder — 策略模板抽象基类。

所有具体策略（trend / mean_reversion / breakout / reversal）继承此类。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle
from core.strategy_pool.schemas.strategy import StrategySpec


class StrategyBuilder(ABC):
    """
    策略模板基类。

    子类必须实现：
    - generate_signals(): 生成信号包列表
    - validate_params(): 校验策略参数合法性
    - get_spec(): 返回策略规格

    子类可选覆写：
    - get_default_params(): 返回默认参数
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        self.params = params or self.get_default_params()

    @abstractmethod
    def generate_signals(
        self,
        data: List[Dict[str, Any]],
        symbol: str,
    ) -> List[StrategySignalBundle]:
        """
        生成信号包列表。

        Args:
            data: 市场数据列表（每条记录至少包含 date, open, high, low, close, volume）
            symbol: 标的代码

        Returns:
            StrategySignalBundle 列表
        """
        ...

    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """校验策略参数是否合法。"""
        ...

    @abstractmethod
    def get_spec(self) -> StrategySpec:
        """返回策略规格。"""
        ...

    def get_default_params(self) -> Dict[str, Any]:
        """返回默认参数（子类可覆写）。"""
        return {}

    @classmethod
    def _make_bundle(
        cls,
        strategy_id: str,
        symbol: str,
        direction: str,
        strength: float,
        confidence: float,
        **kwargs,
    ) -> StrategyStrategySignalBundle:
        """创建 StrategySignalBundle 的便捷方法。"""
        from uuid import uuid4
        return StrategySignalBundle(
            bundle_id=f"sig-{uuid4().hex[:12]}",
            source_strategy_id=strategy_id,
            symbol=symbol,
            direction=direction,
            strength=max(0.0, min(1.0, strength)),
            confidence=max(0.0, min(1.0, confidence)),
            metadata=kwargs.get("metadata", {}),
            supporting_signals=kwargs.get("supporting_signals", []),
            supporting_snapshots=kwargs.get("supporting_snapshots", []),
        )
