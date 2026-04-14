"""
Position Sizing Calculators
=========================

6种仓位 sizing 算法，按优先级链使用。
每个 Calculator 返回 dict（含 qty / confidence / rationale）。

算法优先级链：
  VolatilityTargeting → Kelly → ConvictionWeighted → FixedFraction
    → DrawdownAdjusted → RegimeBased
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from core.risk.context import MarketContext


class PositionCalculator(ABC):
    """
    仓位计算器抽象基类。

    所有实现必须返回一致的 dict 结构：
      {
          "qty": float,           # 计算出的理论数量
          "confidence": float,    # 本次 sizing 的置信度（0-1）
          "rationale": str,       # 人类可读理由
          "method": str,          # 算法名称
      }
    """

    @property
    @abstractmethod
    def method_name(self) -> str:
        """算法名称。"""
        ...

    def calculate(
        self,
        portfolio_equity: float,
        direction_confidence: float,
        direction_sign: int,
        market_context: MarketContext,
        *,
        stop_distance_pct: float = 0.02,
        target_annual_vol: float = 0.15,
        regime_multiplier: Optional[float] = None,
        regime_name: str = "unknown",
        drawdown_ratio: float = 0.0,
        kelly_win_rate: Optional[float] = None,
        kelly_avg_win: Optional[float] = None,
        kelly_avg_loss: Optional[float] = None,
    ) -> dict:
        """
        计算仓位数量。

        Parameters
        ----------
        portfolio_equity : float
            当前组合权益（美元）
        direction_confidence : float
            仲裁置信度（0-1）
        direction_sign : int
            方向符号：+1 = LONG，-1 = SHORT
        market_context : MarketContext
            市场环境数据

        Keyword Arguments（各算法可选参数）
        -----------------------------------
        stop_distance_pct : float
            止损距离（比例），用于 FixedFraction（默认 2%）
        target_annual_vol : float
            目标组合年化波动率，用于 VolatilityTargeting（默认 15%）
        regime_multiplier : float
            市场状态修饰系数（默认 1.0）
        drawdown_ratio : float
            当前回撤比例（0-1），用于 DrawdownAdjusted
        kelly_win_rate : float
            历史胜率（Kelly 用，可选）
        kelly_avg_win : float
            平均盈利金额（Kelly 用，可选）
        kelly_avg_loss : float
            平均亏损金额（Kelly 用，可选）
        """
        return self._compute(
            portfolio_equity=portfolio_equity,
            direction_confidence=direction_confidence,
            direction_sign=direction_sign,
            market_context=market_context,
            stop_distance_pct=stop_distance_pct,
            target_annual_vol=target_annual_vol,
            regime_multiplier=regime_multiplier,
            drawdown_ratio=drawdown_ratio,
            kelly_win_rate=kelly_win_rate,
            kelly_avg_win=kelly_avg_win,
            kelly_avg_loss=kelly_avg_loss,
        )

    @abstractmethod
    def _compute(self, **kwargs) -> dict:
        """子类实现具体计算逻辑。"""
        ...
