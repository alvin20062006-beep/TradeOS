"""
Test: Scorers
============

验证信号评分和集成评分逻辑。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.arbitration.schemas import (
    ArbitrationDecision,
    DirectionalSignal,
    SignalBundle,
    SignalScore,
)
from core.schemas import Direction, Regime
from core.arbitration.scorers.ensemble_scorer import EnsembleScorer
from core.arbitration.scorers.signal_scorer import (
    derive_direction_and_confidence,
    score_signal,
)


def _bundle(ts: datetime, **kwargs) -> SignalBundle:
    defaults = dict(
        timestamp=ts, symbol="AAPL",
        technical=None, chan=None, orderflow=None,
        sentiment=None, macro=None, fundamental=None,
    )
    defaults.update(kwargs)
    return SignalBundle(**defaults)


# ── Direction Derivation Tests ──────────────────────────────────


class TestDeriveDirectionAndConfidence:
    def test_technical_signal_extracted(self) -> None:
        from core.schemas import TechnicalSignal
        ts = datetime.utcnow()
        sig = TechnicalSignal(
            engine_name="technical", symbol="AAPL", timestamp=ts,
            direction=Direction.LONG, confidence=0.85,
            regime=Regime.TRENDING_UP,
        )
        bundle = _bundle(ts, technical=sig)
        derived = derive_direction_and_confidence(bundle)
        assert any(s.engine_name == "technical" for s in derived)
        t = next(s for s in derived if s.engine_name == "technical")
        assert t.direction == Direction.LONG
        assert t.confidence == 0.85

    def test_orderflow_positive_imbalance_maps_long(self) -> None:
        from core.schemas import OrderFlowSignal, TimeFrame
        ts = datetime.utcnow()
        sig = OrderFlowSignal(
            symbol="AAPL", timestamp=ts, timeframe=TimeFrame.M5,
            book_imbalance=0.7,
        )
        bundle = _bundle(ts, orderflow=sig)
        derived = derive_direction_and_confidence(bundle)
        assert len(derived) == 1
        assert derived[0].engine_name == "orderflow"
        assert derived[0].direction == Direction.LONG
        assert derived[0].confidence == 0.7

    def test_orderflow_negative_imbalance_maps_short(self) -> None:
        from core.schemas import OrderFlowSignal, TimeFrame
        ts = datetime.utcnow()
        sig = OrderFlowSignal(
            symbol="AAPL", timestamp=ts, timeframe=TimeFrame.M5,
            book_imbalance=-0.6,
        )
        bundle = _bundle(ts, orderflow=sig)
        derived = derive_direction_and_confidence(bundle)
        assert derived[0].direction == Direction.SHORT

    def test_orderflow_low_imbalance_filtered(self) -> None:
        from core.schemas import OrderFlowSignal, TimeFrame
        ts = datetime.utcnow()
        sig = OrderFlowSignal(
            symbol="AAPL", timestamp=ts, timeframe=TimeFrame.M5,
            book_imbalance=0.05,
        )
        bundle = _bundle(ts, orderflow=sig)
        derived = derive_direction_and_confidence(bundle)
        # abs(0.05) < 0.1 → confidence=0 → filtered by LOW_CONFIDENCE_THRESHOLD
        assert len(derived) == 0

    def test_sentiment_high_composite_maps_long(self) -> None:
        from core.schemas import SentimentEvent
        ts = datetime.utcnow()
        bundle = _bundle(ts, sentiment=SentimentEvent(
            symbol="AAPL", timestamp=ts, composite_sentiment=0.8,
        ))
        derived = derive_direction_and_confidence(bundle)
        assert derived[0].direction == Direction.LONG
        # 0.8 - 0.5 = 0.3; 0.3 * 2 = 0.6
        assert derived[0].confidence == pytest.approx(0.6, rel=1e-3)

    def test_sentiment_low_composite_maps_short(self) -> None:
        from core.schemas import SentimentEvent
        ts = datetime.utcnow()
        bundle = _bundle(ts, sentiment=SentimentEvent(
            symbol="AAPL", timestamp=ts, composite_sentiment=0.2,
        ))
        derived = derive_direction_and_confidence(bundle)
        assert derived[0].direction == Direction.SHORT
        # 0.5 - 0.2 = 0.3; 0.3 * 2 = 0.6
        assert derived[0].confidence == 0.6

    def test_sentiment_near_neutral_maps_flat(self) -> None:
        from core.schemas import SentimentEvent
        ts = datetime.utcnow()
        bundle = _bundle(ts, sentiment=SentimentEvent(
            symbol="AAPL", timestamp=ts, composite_sentiment=0.52,
        ))
        derived = derive_direction_and_confidence(bundle)
        # |0.52-0.5| = 0.02 < 0.1 threshold → FLAT → confidence=0 → filtered
        assert len(derived) == 0

    def test_macro_risk_on_maps_long(self) -> None:
        from core.schemas import MacroSignal
        ts = datetime.utcnow()
        bundle = _bundle(ts, macro=MacroSignal(
            timestamp=ts, regime=Regime.TRENDING_UP,
            regime_confidence=0.75, risk_on=True,
        ))
        derived = derive_direction_and_confidence(bundle)
        assert derived[0].engine_name == "macro"
        assert derived[0].direction == Direction.LONG
        assert derived[0].confidence == 0.75

    def test_macro_risk_off_maps_short(self) -> None:
        from core.schemas import MacroSignal
        ts = datetime.utcnow()
        bundle = _bundle(ts, macro=MacroSignal(
            timestamp=ts, regime=Regime.TRENDING_UP,
            regime_confidence=0.65, risk_on=False,
        ))
        derived = derive_direction_and_confidence(bundle)
        assert derived[0].direction == Direction.SHORT

    def test_multiple_signals_all_extracted(self) -> None:
        from core.schemas import (
            ChanSignal, MacroSignal, OrderFlowSignal,
            SentimentEvent, TechnicalSignal, TimeFrame,
        )
        ts = datetime.utcnow()
        bundle = _bundle(ts,
            technical=TechnicalSignal(
                engine_name="technical", symbol="AAPL", timestamp=ts,
                direction=Direction.LONG, confidence=0.8, regime=Regime.TRENDING_UP,
            ),
            chan=ChanSignal(
                engine_name="chan", symbol="AAPL", timestamp=ts,
                direction=Direction.LONG, confidence=0.75, regime=Regime.TRENDING_UP,
            ),
            orderflow=OrderFlowSignal(
                symbol="AAPL", timestamp=ts, timeframe=TimeFrame.M5,
                book_imbalance=0.6,
            ),
            sentiment=SentimentEvent(symbol="AAPL", timestamp=ts, composite_sentiment=0.7),
            macro=MacroSignal(
                timestamp=ts, regime=Regime.TRENDING_UP,
                regime_confidence=0.7, risk_on=True,
            ),
        )
        derived = derive_direction_and_confidence(bundle)
        assert len(derived) == 5
        names = {s.engine_name for s in derived}
        assert names == {"technical", "chan", "orderflow", "sentiment", "macro"}


# ── Score Signal Tests ─────────────────────────────────────────


class TestScoreSignal:
    def test_long_signal_positive_contribution(self) -> None:
        ds = DirectionalSignal(
            engine_name="technical",
            direction=Direction.LONG,
            confidence=0.8,
            weight=1.0,
        )
        score = score_signal(ds)
        assert score.contribution == pytest.approx(0.8)
        assert score.engine_name == "technical"

    def test_short_signal_negative_contribution(self) -> None:
        ds = DirectionalSignal(
            engine_name="technical",
            direction=Direction.SHORT,
            confidence=0.6,
            weight=1.0,
        )
        score = score_signal(ds)
        assert score.contribution == pytest.approx(-0.6)

    def test_weight_applied_to_contribution(self) -> None:
        ds = DirectionalSignal(
            engine_name="sentiment",
            direction=Direction.LONG,
            confidence=0.5,
            weight=0.8,
        )
        score = score_signal(ds)
        assert score.contribution == pytest.approx(0.4)


# ── Ensemble Scorer Tests ───────────────────────────────────────


class TestEnsembleScorer:
    def setup_method(self) -> None:
        self.scorer = EnsembleScorer()

    def test_long_wins(self) -> None:
        ts = datetime.utcnow()
        decision = ArbitrationDecision(
            decision_id="e1", timestamp=ts, symbol="AAPL",
            bias="no_trade", confidence=0.0,
            long_score=0.0, short_score=0.0, neutrality_score=0.0,
        )
        scores = [
            SignalScore(
                engine_name="technical", direction=Direction.LONG,
                raw_confidence=0.8, adjusted_confidence=0.8,
                weight=1.0, contribution=0.8,
            ),
            SignalScore(
                engine_name="chan", direction=Direction.LONG,
                raw_confidence=0.6, adjusted_confidence=0.6,
                weight=1.0, contribution=0.6,
            ),
        ]
        self.scorer.aggregate(scores, decision)
        assert decision.bias == "long_bias"
        assert decision.long_score > decision.short_score

    def test_short_wins(self) -> None:
        ts = datetime.utcnow()
        decision = ArbitrationDecision(
            decision_id="e2", timestamp=ts, symbol="AAPL",
            bias="no_trade", confidence=0.0,
            long_score=0.0, short_score=0.0, neutrality_score=0.0,
        )
        scores = [
            SignalScore(
                engine_name="technical", direction=Direction.SHORT,
                raw_confidence=0.8, adjusted_confidence=0.8,
                weight=1.0, contribution=-0.8,
            ),
        ]
        self.scorer.aggregate(scores, decision)
        assert decision.bias == "short_bias"

    def test_near_equal_triggers_hold(self) -> None:
        ts = datetime.utcnow()
        decision = ArbitrationDecision(
            decision_id="e3", timestamp=ts, symbol="AAPL",
            bias="no_trade", confidence=0.0,
            long_score=0.0, short_score=0.0, neutrality_score=0.0,
        )
        scores = [
            SignalScore(
                engine_name="technical", direction=Direction.LONG,
                raw_confidence=0.7, adjusted_confidence=0.7,
                weight=1.0, contribution=0.7,
            ),
            SignalScore(
                engine_name="sentiment", direction=Direction.SHORT,
                raw_confidence=0.68, adjusted_confidence=0.68,
                weight=1.0, contribution=-0.68,
            ),
        ]
        self.scorer.aggregate(scores, decision)
        # diff = |0.7 - 0.68| = 0.02 < 0.3 → hold_bias
        assert decision.bias == "hold_bias"

    def test_scores_normalize_to_one(self) -> None:
        ts = datetime.utcnow()
        decision = ArbitrationDecision(
            decision_id="e4", timestamp=ts, symbol="AAPL",
            bias="no_trade", confidence=0.0,
            long_score=0.0, short_score=0.0, neutrality_score=0.0,
        )
        scores = [
            SignalScore(
                engine_name="technical", direction=Direction.LONG,
                raw_confidence=0.8, adjusted_confidence=0.8,
                weight=1.0, contribution=0.8,
            ),
        ]
        self.scorer.aggregate(scores, decision)
        total = decision.long_score + decision.short_score + decision.neutrality_score
        assert abs(total - 1.0) < 1e-6

    def test_veto_always_no_trade(self) -> None:
        ts = datetime.utcnow()
        decision = ArbitrationDecision(
            decision_id="e5", timestamp=ts, symbol="AAPL",
            bias="long_bias", confidence=0.9,
            long_score=0.8, short_score=0.0, neutrality_score=0.0,
            fundamental_veto_triggered=True,
        )
        scores = [
            SignalScore(
                engine_name="technical", direction=Direction.LONG,
                raw_confidence=0.9, adjusted_confidence=0.9,
                weight=1.0, contribution=0.9,
            ),
        ]
        self.scorer.aggregate(scores, decision)
        assert decision.bias == "no_trade"

    def test_reduce_risk_when_risk_off(self) -> None:
        ts = datetime.utcnow()
        decision = ArbitrationDecision(
            decision_id="e6", timestamp=ts, symbol="AAPL",
            bias="long_bias", confidence=0.8,
            long_score=0.8, short_score=0.0, neutrality_score=0.0,
            fundamental_veto_triggered=False,
            risk_adjustment=0.5,
        )
        scores = [
            SignalScore(
                engine_name="technical", direction=Direction.LONG,
                raw_confidence=0.8, adjusted_confidence=0.8,
                weight=1.0, contribution=0.8,
            ),
        ]
        self.scorer.aggregate(scores, decision)
        # risk_adjustment=0.5 < 0.7 → reduce_risk
        assert decision.bias == "reduce_risk"
