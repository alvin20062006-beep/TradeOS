"""
Test: Decision Maker
=================

验证加权投票、bias 生成、理由链。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.arbitration.decision_maker import DecisionMaker
from core.arbitration.schemas import SignalBundle
from core.schemas import SentimentEvent


class TestDecisionMaker:
    def setup_method(self) -> None:
        self.maker = DecisionMaker()

    def test_no_signals_returns_no_trade(self) -> None:
        bundle = SignalBundle(timestamp=datetime.utcnow(), symbol="AAPL")
        decision = self.maker.decide(bundle)
        assert decision.bias == "no_trade"
        assert decision.confidence == 0.0

    def test_single_long_returns_long_bias(self) -> None:
        from core.schemas import Direction, Regime, TechnicalSignal

        ts = datetime.utcnow()
        bundle = SignalBundle(
            timestamp=ts,
            symbol="AAPL",
            technical=TechnicalSignal(
                engine_name="technical",
                symbol="AAPL",
                timestamp=ts,
                direction=Direction.LONG,
                confidence=0.8,
                regime=Regime.TRENDING_UP,
            ),
        )
        decision = self.maker.decide(bundle)
        assert decision.bias in ("long_bias", "hold_bias")
        assert decision.confidence > 0

    def test_reasoning_chain_populated(self) -> None:
        from core.schemas import Direction, Regime, TechnicalSignal

        ts = datetime.utcnow()
        bundle = SignalBundle(
            timestamp=ts,
            symbol="AAPL",
            technical=TechnicalSignal(
                engine_name="technical",
                symbol="AAPL",
                timestamp=ts,
                direction=Direction.LONG,
                confidence=0.8,
                regime=Regime.TRENDING_UP,
            ),
        )
        decision = self.maker.decide(bundle)
        assert len(decision.rationale) == 1
        r = decision.rationale[0]
        assert r.signal_name == "technical"
        assert r.confidence == 0.8
        assert hasattr(r, "contribution")
        assert hasattr(r, "rule_adjustments")

    def test_multiple_signals_scores_aggregated(self) -> None:
        from core.schemas import Direction, Regime, TechnicalSignal

        ts = datetime.utcnow()
        bundle = SignalBundle(
            timestamp=ts,
            symbol="AAPL",
            technical=TechnicalSignal(
                engine_name="technical",
                symbol="AAPL",
                timestamp=ts,
                direction=Direction.LONG,
                confidence=0.8,
                regime=Regime.TRENDING_UP,
            ),
            sentiment=SentimentEvent(symbol="AAPL", timestamp=ts, composite_sentiment=0.7),
        )
        decision = self.maker.decide(bundle)
        assert decision.signal_count == 2
        assert decision.long_score + decision.short_score + decision.neutrality_score > 0


class TestSentimentEventDirectionDerivation:
    """验证 SentimentEvent → direction 的推导逻辑。"""

    def setup_method(self) -> None:
        self.maker = DecisionMaker()

    def test_composite_above_05_maps_to_long(self) -> None:
        from core.arbitration.schemas import SignalBundle
        from core.schemas import SentimentEvent

        ts = datetime.utcnow()
        bundle = SignalBundle(
            timestamp=ts, symbol="AAPL",
            sentiment=SentimentEvent(symbol="AAPL", timestamp=ts, composite_sentiment=0.8),
        )
        decision = self.maker.decide(bundle)
        # 0.8 离 0.5 差 0.3，置信度 = min(0.3*2, 1.0) = 0.6
        assert decision.bias in ("long_bias",)

    def test_composite_below_05_maps_to_short(self) -> None:
        from core.arbitration.schemas import SignalBundle
        from core.schemas import SentimentEvent

        ts = datetime.utcnow()
        bundle = SignalBundle(
            timestamp=ts, symbol="AAPL",
            sentiment=SentimentEvent(symbol="AAPL", timestamp=ts, composite_sentiment=0.2),
        )
        decision = self.maker.decide(bundle)
        assert decision.bias in ("short_bias",)

    def test_composite_near_05_maps_to_neutral(self) -> None:
        from core.arbitration.schemas import SignalBundle
        from core.schemas import SentimentEvent

        ts = datetime.utcnow()
        bundle = SignalBundle(
            timestamp=ts, symbol="AAPL",
            sentiment=SentimentEvent(symbol="AAPL", timestamp=ts, composite_sentiment=0.55),
        )
        decision = self.maker.decide(bundle)
        # 0.05 < 0.1 阈值 → FLAT → confidence=0 → no_trade
        assert decision.bias == "no_trade"
