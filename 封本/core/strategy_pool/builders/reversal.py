"""ReversalStrategy — 反转策略。

基于短期均值回归效应的最小可用策略。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.strategy_pool.builders.base import StrategyBuilder
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle
from core.strategy_pool.schemas.strategy import StrategySpec, StrategyType


class ReversalStrategy(StrategyBuilder):
    """
    反转策略。

    信号逻辑：
    - N 日收益率 < -threshold → LONG（超跌反弹）
    - N 日收益率 > +threshold → SHORT（超涨回落）
    - 配合成交量萎缩（低 Vol/MA Vol）强化信号
    """

    def __init__(self, params: Dict[str, Any] = None) -> None:
        super().__init__(params)
        self._strategy_id = params.get("strategy_id", "reversal") if params else "reversal"

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "strategy_id": "reversal",
            "return_period": 5,
            "long_threshold": -0.03,   # 跌超 3% → LONG
            "short_threshold": 0.03,  # 涨超 3% → SHORT
            "vol_ma_period": 20,
            "vol_ratio_threshold": 0.7,  # vol < MA * 0.7 视为萎缩
        }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return (
            params.get("return_period", 5) >= 2
            and params.get("long_threshold", -0.03) < 0
            and params.get("short_threshold", 0.03) > 0
            and params.get("vol_ma_period", 20) >= 5
        )

    def get_spec(self) -> StrategySpec:
        return StrategySpec(
            strategy_id=self._strategy_id,
            name="Reversal",
            strategy_type=StrategyType.REVERSAL,
            bias="market_neutral",
            direction="BOTH",
            params=self.params,
            lookback=self.params.get("vol_ma_period", 20),
        )

    def generate_signals(
        self,
        data: List[Dict[str, Any]],
        symbol: str,
    ) -> List[StrategySignalBundle]:
        period = self.params.get("return_period", 5)
        vol_period = self.params.get("vol_ma_period", 20)
        vol_ratio_thresh = self.params.get("vol_ratio_threshold", 0.7)

        if len(data) < max(period, vol_period) + 1:
            return []

        signals: List[StrategySignalBundle] = []

        for i in range(vol_period, len(data)):
            # N日收益率
            ret = (data[i]["close"] - data[i - period]["close"]) / data[i - period]["close"]
            lt = self.params.get("long_threshold", -0.03)
            st = self.params.get("short_threshold", 0.03)

            direction = None
            strength = 0.5

            if ret < lt:
                direction = "LONG"
                strength = min(1.0, 0.5 + abs(ret) / abs(lt) * 0.3)
            elif ret > st:
                direction = "SHORT"
                strength = min(1.0, 0.5 + abs(ret) / abs(st) * 0.3)

            if direction is None:
                continue

            # 成交量萎缩确认
            vol_window = data[i - vol_period:i]
            avg_vol = sum(d.get("volume", 0) for d in vol_window) / len(vol_window)
            curr_vol = data[i].get("volume", 0)
            vol_atrophy = avg_vol > 0 and curr_vol < avg_vol * vol_ratio_thresh
            if vol_atrophy:
                strength = min(1.0, strength + 0.2)

            signals.append(self._make_bundle(
                strategy_id=self._strategy_id,
                symbol=symbol,
                direction=direction,
                strength=strength,
                confidence=strength * 0.8 if vol_atrophy else strength * 0.6,
                metadata={
                    "signal_type": "reversal",
                    f"{period}d_return": ret,
                    "vol_atrophy": vol_atrophy,
                    "vol_ratio": curr_vol / avg_vol if avg_vol > 0 else 0,
                    "close": data[i]["close"],
                },
            ))

        return signals
