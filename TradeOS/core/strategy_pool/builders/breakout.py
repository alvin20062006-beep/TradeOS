"""BreakoutStrategy — 突破策略。

基于 N 日高低点突破 + 成交量确认的最小可用策略。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.strategy_pool.builders.base import StrategyBuilder
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle
from core.strategy_pool.schemas.strategy import StrategySpec, StrategyType


class BreakoutStrategy(StrategyBuilder):
    """
    突破策略。

    信号逻辑：
    - 收盘价突破 N 日最高价 + 成交量放大 → LONG
    - 收盘价跌破 N 日最低价 + 成交量放大 → SHORT
    - 成交量放大 = 当前 volume > MA(volume, vol_period) * vol_threshold
    """

    def __init__(self, params: Dict[str, Any] = None) -> None:
        super().__init__(params)
        self._strategy_id = params.get("strategy_id", "breakout") if params else "breakout"

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "strategy_id": "breakout",
            "lookback_period": 20,
            "vol_period": 20,
            "vol_threshold": 1.2,
        }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return (
            params.get("lookback_period", 20) >= 5
            and params.get("vol_period", 20) >= 5
            and params.get("vol_threshold", 1.2) >= 1.0
        )

    def get_spec(self) -> StrategySpec:
        return StrategySpec(
            strategy_id=self._strategy_id,
            name="Breakout",
            strategy_type=StrategyType.BREAKOUT,
            bias="market_neutral",
            direction="BOTH",
            params=self.params,
            lookback=self.params.get("lookback_period", 20),
        )

    def generate_signals(
        self,
        data: List[Dict[str, Any]],
        symbol: str,
    ) -> List[StrategySignalBundle]:
        lookback = self.params.get("lookback_period", 20)
        vol_period = self.params.get("vol_period", 20)
        vol_threshold = self.params.get("vol_threshold", 1.2)

        if len(data) < lookback + vol_period:
            return []

        signals: List[StrategySignalBundle] = []

        for i in range(lookback, len(data)):
            window = data[i - lookback:i]
            highs = [d["high"] for d in window]
            lows = [d["low"] for d in window]
            period_high = max(highs)
            period_low = min(lows)

            close = data[i]["close"]
            vol = data[i].get("volume", 0)

            # Volume confirmation
            vol_window = data[i - vol_period:i]
            avg_vol = sum(d.get("volume", 0) for d in vol_window) / len(vol_window)
            vol_confirmed = avg_vol > 0 and vol > avg_vol * vol_threshold

            direction = None
            strength = 0.5

            if close > period_high:
                direction = "LONG"
                penetration = (close - period_high) / period_high
                strength = min(1.0, 0.5 + penetration * 10)
                if vol_confirmed:
                    strength = min(1.0, strength + 0.15)
            elif close < period_low:
                direction = "SHORT"
                penetration = (period_low - close) / close
                strength = min(1.0, 0.5 + penetration * 10)
                if vol_confirmed:
                    strength = min(1.0, strength + 0.15)

            if direction is None:
                continue

            signals.append(self._make_bundle(
                strategy_id=self._strategy_id,
                symbol=symbol,
                direction=direction,
                strength=strength,
                confidence=strength * 0.8 if vol_confirmed else strength * 0.6,
                metadata={
                    "signal_type": "breakout",
                    "period_high": period_high,
                    "period_low": period_low,
                    "close": close,
                    "vol_confirmed": vol_confirmed,
                    "vol_ratio": vol / avg_vol if avg_vol > 0 else 0,
                },
            ))

        return signals
