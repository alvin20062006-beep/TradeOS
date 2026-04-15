"""TrendFollowingStrategy — 趋势跟踪策略。

基于 MA 交叉和动量突破的最小可用策略。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.strategy_pool.builders.base import StrategyBuilder
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle
from core.strategy_pool.schemas.strategy import StrategySpec, StrategyType


class TrendFollowingStrategy(StrategyBuilder):
    """
    趋势跟踪策略。

    信号逻辑：
    - 短期 MA 上穿长期 MA → LONG
    - 短期 MA 下穿长期 MA → SHORT
    - 动量（N 日收益率）超过阈值 → 强化信号
    """

    def __init__(self, params: Dict[str, Any] = None) -> None:
        super().__init__(params)
        self._strategy_id = params.get("strategy_id", "trend_following") if params else "trend_following"

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "strategy_id": "trend_following",
            "short_ma_period": 10,
            "long_ma_period": 30,
            "momentum_window": 20,
            "momentum_threshold": 0.02,
            "strength_multiplier": 1.0,
        }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        short_ma = params.get("short_ma_period", 10)
        long_ma = params.get("long_ma_period", 30)
        return (
            1 < short_ma < long_ma
            and params.get("momentum_window", 20) >= 5
        )

    def get_spec(self) -> StrategySpec:
        return StrategySpec(
            strategy_id=self._strategy_id,
            name="TrendFollowing",
            strategy_type=StrategyType.TREND,
            bias="market_neutral",
            direction="BOTH",
            params=self.params,
            lookback=self.params.get("long_ma_period", 30),
        )

    def _compute_ma(self, data: List[Dict[str, Any]], period: int) -> List[float]:
        """计算简单移动平均线。"""
        closes = [d["close"] for d in data]
        result: List[float] = []
        for i in range(len(closes)):
            if i < period - 1:
                result.append(float("nan"))
            else:
                result.append(sum(closes[i - period + 1:i + 1]) / period)
        return result

    def generate_signals(
        self,
        data: List[Dict[str, Any]],
        symbol: str,
    ) -> List[StrategySignalBundle]:
        if len(data) < self.params.get("long_ma_period", 30):
            return []

        short_ma = self._compute_ma(data, self.params["short_ma_period"])
        long_ma = self._compute_ma(data, self.params["long_ma_period"])
        mom_window = self.params.get("momentum_window", 20)
        mom_threshold = self.params.get("momentum_threshold", 0.02)
        strength_mult = self.params.get("strength_multiplier", 1.0)

        signals: List[StrategySignalBundle] = []
        for i in range(1, len(data)):
            if i < self.params["long_ma_period"]:
                continue

            # MA cross detection
            prev_short = short_ma[i - 1]
            prev_long = long_ma[i - 1]
            curr_short = short_ma[i]
            curr_long = long_ma[i]

            direction = None
            strength = 0.5

            if prev_short <= prev_long and curr_short > curr_long:
                direction = "LONG"
            elif prev_short >= prev_long and curr_short < curr_long:
                direction = "SHORT"

            if direction is None:
                continue

            # Momentum confirmation
            if i >= mom_window:
                momentum = (data[i]["close"] - data[i - mom_window]["close"]) / data[i - mom_window]["close"]
                if momentum * (1 if direction == "LONG" else -1) > mom_threshold:
                    strength = min(1.0, 0.5 + abs(momentum) * strength_mult * 5)

            signals.append(self._make_bundle(
                strategy_id=self._strategy_id,
                symbol=symbol,
                direction=direction,
                strength=strength,
                confidence=strength * 0.9,
                metadata={
                    "signal_type": "ma_cross",
                    "short_ma": curr_short,
                    "long_ma": curr_long,
                    "close": data[i]["close"],
                },
            ))

        return signals
