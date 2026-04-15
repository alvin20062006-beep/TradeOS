"""MeanReversionStrategy — 均值回归策略。

基于 RSI 和布林带的最小可用策略。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.strategy_pool.builders.base import StrategyBuilder
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle
from core.strategy_pool.schemas.strategy import StrategySpec, StrategyType


class MeanReversionStrategy(StrategyBuilder):
    """
    均值回归策略。

    信号逻辑：
    - RSI < oversold → LONG（超卖反弹）
    - RSI > overbought → SHORT（超买回落）
    - 布林带下轨触及 → 强化 LONG
    - 布林带上轨触及 → 强化 SHORT
    """

    def __init__(self, params: Dict[str, Any] = None) -> None:
        defaults = self.get_default_params()
        if params:
            defaults.update(params)
        super().__init__(defaults)
        self._strategy_id = self.params.get("strategy_id", "mean_reversion")

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "strategy_id": "mean_reversion",
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "bb_period": 20,
            "bb_std": 2.0,
        }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return (
            params.get("rsi_period", 14) >= 5
            and 0 < params.get("oversold", 30) < params.get("overbought", 70) < 100
            and params.get("bb_period", 20) >= 5
        )

    def get_spec(self) -> StrategySpec:
        return StrategySpec(
            strategy_id=self._strategy_id,
            name="MeanReversion",
            strategy_type=StrategyType.MEAN_REVERSION,
            bias="market_neutral",
            direction="BOTH",
            params=self.params,
            lookback=self.params.get("bb_period", 20),
        )

    def _compute_rsi(self, data: List[Dict[str, Any]], period: int) -> List[float]:
        """计算 RSI。"""
        closes = [d["close"] for d in data]
        result: List[float] = []
        for i in range(len(closes)):
            if i < period:
                result.append(50.0)
                continue
            gains = 0.0
            losses = 0.0
            for j in range(i - period + 1, i + 1):
                change = closes[j] - closes[j - 1]
                if change > 0:
                    gains += change
                else:
                    losses += abs(change)
            avg_gain = gains / period
            avg_loss = losses / period
            if avg_loss == 0:
                result.append(100.0)
            else:
                rs = avg_gain / avg_loss
                result.append(100.0 - (100.0 / (1.0 + rs)))
        return result

    def _compute_bollinger(
        self, data: List[Dict[str, Any]], period: int, std_mult: float
    ) -> tuple:
        """计算布林带（upper, middle, lower）。"""
        closes = [d["close"] for d in data]
        upper: List[float] = []
        middle: List[float] = []
        lower: List[float] = []
        for i in range(len(closes)):
            if i < period - 1:
                upper.append(float("nan"))
                middle.append(float("nan"))
                lower.append(float("nan"))
            else:
                window = closes[i - period + 1:i + 1]
                mean = sum(window) / period
                variance = sum((x - mean) ** 2 for x in window) / period
                std = variance ** 0.5
                upper.append(mean + std_mult * std)
                middle.append(mean)
                lower.append(mean - std_mult * std)
        return upper, middle, lower

    def generate_signals(
        self,
        data: List[Dict[str, Any]],
        symbol: str,
    ) -> List[StrategySignalBundle]:
        lookback = self.params.get("bb_period", 20)
        if len(data) < lookback + 1:
            return []

        rsi = self._compute_rsi(data, self.params["rsi_period"])
        bb_upper, _, bb_lower = self._compute_bollinger(
            data, self.params["bb_period"], self.params["bb_std"]
        )

        oversold = self.params.get("oversold", 30)
        overbought = self.params.get("overbought", 70)

        signals: List[StrategySignalBundle] = []
        for i in range(lookback, len(data)):
            rsi_val = rsi[i]
            close = data[i]["close"]
            direction = None
            strength = 0.5

            bb_signal = 0
            if not (bb_upper[i] != bb_upper[i] or bb_lower[i] != bb_lower[i]):
                if close <= bb_lower[i]:
                    bb_signal = 1  # below lower band
                elif close >= bb_upper[i]:
                    bb_signal = -1  # above upper band

            if rsi_val < oversold:
                direction = "LONG"
                strength = 0.6 + (oversold - rsi_val) / oversold * 0.3
                if bb_signal == 1:
                    strength = min(1.0, strength + 0.2)
            elif rsi_val > overbought:
                direction = "SHORT"
                strength = 0.6 + (rsi_val - overbought) / (100 - overbought) * 0.3
                if bb_signal == -1:
                    strength = min(1.0, strength + 0.2)

            if direction is None:
                continue

            signals.append(self._make_bundle(
                strategy_id=self._strategy_id,
                symbol=symbol,
                direction=direction,
                strength=strength,
                confidence=strength * 0.85,
                metadata={
                    "signal_type": "rsi_bb",
                    "rsi": rsi_val,
                    "close": close,
                    "bb_signal": bb_signal,
                },
            ))

        return signals
