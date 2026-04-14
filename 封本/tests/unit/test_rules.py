"""
Test: Arbitration Rules
=====================

验证五条规则的独立行为。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.arbitration.rules.base import ArbitrationRule
from core.arbitration.rules.confidence_weight import ConfidenceWeightRule
from core.arbitration.rules.direction_conflict import DirectionConflictRule
from core.arbitration.rules.fundamental_veto import FundamentalVetoRule
from core.arbitration.rules.macro_adjustment import MacroAdjustmentRule
from core.arbitration.rules.regime_filter import RegimeFilterRule

from core.arbitration.schemas import ArbitrationDecision, SignalBundle, SignalScore
from core.schemas import Direction, Regime


def _bundle(ts: datetime, **kwargs) -> SignalBundle:
    defaults = dict(
        timestamp=ts, symbol="AAPL",
        technical=None, chan=None, orderflow=None,
        sentiment=None, macro=None, fundamental=None,
    )
    defaults.update(kwargs)
    return SignalBundle(**defaults)


def _scores(entries) -> list[SignalScore]:
    return [
        SignalScore(
            engine_name=e["engine"],
            direction=e.get("direction", Direction.LONG),
            raw_confidence=e.get("raw", 0.8),
            adjusted_confidence=e.get("adj", e.get("raw", 0.8)),
            weight=e.get("weight", 1.0),
            contribution=e.get("contrib", 0.8 if e.get("direction", Direction.LONG) == Direction.LONG else -0.8),
            rule_adjustments=[],
        )
        for e in entries
    ]


def _decision(ts: datetime, **kwargs) -> ArbitrationDecision:
    defaults = dict(
        decision_id="test", timestamp=ts, symbol="AAPL",
        bias="no_trade", confidence=0.0,
        long_score=0.0, short_score=0.0, neutrality_score=0.0,
    )
    defaults.update(kwargs)
    return ArbitrationDecision(**defaults)


# ── Fundamental Veto ──────────────────────────────────────────


class TestFundamentalVetoRule:
    def test_d_rating_triggers_veto(self) -> None:
        from core.analysis.fundamental.report import FundamentalReport

        ts = datetime.utcnow()
        bundle = _bundle(ts, fundamental=FundamentalReport(
            symbol="AAPL", report_date=ts,
            pe=5.0, pb=0.8, ps=1.0, peg=None, ev_ebitda=None, market_cap=None,
            roe=0.05, roa=0.03, gross_margin=None, net_margin=None,
            revenue_growth_yoy=None, net_income_growth_yoy=None, eps_growth_yoy=None,
            debt_to_equity=None, current_ratio=None, quick_ratio=None, interest_coverage=None,
            dividend_yield=None,
            quality_score=30.0, value_score=40.0, growth_score=20.0,
            red_flags=["debt_to_equity_high"],
            rating="D",
            metadata={},
        ))
        scores = _scores([{"engine": "technical", "direction": Direction.LONG, "raw": 0.9}])
        decision = _decision(ts)
        FundamentalVetoRule().evaluate(bundle, scores, decision)
        assert decision.fundamental_veto_triggered is True
        assert decision.bias == "no_trade"
        assert decision.confidence == 0.0

    def test_c_rating_does_not_veto(self) -> None:
        from core.analysis.fundamental.report import FundamentalReport

        ts = datetime.utcnow()
        bundle = _bundle(ts, fundamental=FundamentalReport(
            symbol="AAPL", report_date=ts,
            pe=5.0, pb=0.8, ps=1.0, peg=None, ev_ebitda=None, market_cap=None,
            roe=0.05, roa=0.03, gross_margin=None, net_margin=None,
            revenue_growth_yoy=None, net_income_growth_yoy=None, eps_growth_yoy=None,
            debt_to_equity=None, current_ratio=None, quick_ratio=None, interest_coverage=None,
            dividend_yield=None,
            quality_score=50.0, value_score=50.0, growth_score=40.0,
            red_flags=[],
            rating="C",
            metadata={},
        ))
        scores = _scores([{"engine": "technical", "direction": Direction.LONG, "raw": 0.8}])
        decision = _decision(ts, bias="long_bias", confidence=0.8)
        FundamentalVetoRule().evaluate(bundle, scores, decision)
        assert decision.fundamental_veto_triggered is False
        assert decision.bias == "long_bias"

    def test_no_fundamental_no_change(self) -> None:
        ts = datetime.utcnow()
        bundle = _bundle(ts, fundamental=None)
        scores = _scores([{"engine": "technical", "direction": Direction.LONG, "raw": 0.8}])
        decision = _decision(ts, bias="long_bias", confidence=0.8)
        FundamentalVetoRule().evaluate(bundle, scores, decision)
        assert decision.fundamental_veto_triggered is False


# ── Macro Adjustment ───────────────────────────────────────────


class TestMacroAdjustmentRule:
    def test_risk_on_sets_adjustment_1(self) -> None:
        from core.schemas import MacroSignal

        ts = datetime.utcnow()
        bundle = _bundle(ts, macro=MacroSignal(
            timestamp=ts, regime=Regime.TRENDING_UP,
            regime_confidence=0.7, risk_on=True,
        ))
        scores = _scores([{"engine": "technical", "direction": Direction.LONG, "raw": 0.8}])
        decision = _decision(ts)
        MacroAdjustmentRule().evaluate(bundle, scores, decision)
        assert decision.risk_adjustment == 1.0
        assert decision.macro_regime == "risk_on"

    def test_risk_off_sets_adjustment_05(self) -> None:
        from core.schemas import MacroSignal

        ts = datetime.utcnow()
        bundle = _bundle(ts, macro=MacroSignal(
            timestamp=ts, regime=Regime.TRENDING_UP,
            regime_confidence=0.7, risk_on=False,
        ))
        scores = _scores([{"engine": "technical", "direction": Direction.LONG, "raw": 0.8}])
        decision = _decision(ts)
        MacroAdjustmentRule().evaluate(bundle, scores, decision)
        assert decision.risk_adjustment == 0.5
        assert decision.macro_regime == "risk_off"

    def test_no_macro_no_change(self) -> None:
        ts = datetime.utcnow()
        bundle = _bundle(ts, macro=None)
        scores = _scores([{"engine": "technical", "direction": Direction.LONG, "raw": 0.8}])
        decision = _decision(ts, risk_adjustment=1.0)
        MacroAdjustmentRule().evaluate(bundle, scores, decision)
        assert decision.risk_adjustment == 1.0


# ── Confidence Weight ──────────────────────────────────────────


class TestConfidenceWeightRule:
    def test_sentiment_weight_lowered(self) -> None:
        ts = datetime.utcnow()
        bundle = _bundle(ts)
        scores = _scores([
            {"engine": "technical", "direction": Direction.LONG, "raw": 0.8},
            {"engine": "sentiment", "direction": Direction.LONG, "raw": 0.7},
        ])
        decision = _decision(ts)
        ConfidenceWeightRule().evaluate(bundle, scores, decision)
        sent = next(s for s in scores if s.engine_name == "sentiment")
        assert sent.weight == 0.8  # DEFAULT_WEIGHTS["sentiment"]
        assert "confidence_weight" in sent.rule_adjustments[0]

    def test_custom_weights_override(self) -> None:
        ts = datetime.utcnow()
        bundle = _bundle(ts)
        scores = _scores([{"engine": "sentiment", "direction": Direction.LONG, "raw": 0.7}])
        decision = _decision(ts)
        ConfidenceWeightRule(weights={"sentiment": 0.5}).evaluate(bundle, scores, decision)
        assert scores[0].weight == 0.5


# ── Regime Filter ──────────────────────────────────────────────


class TestRegimeFilterRule:
    def test_trending_up_boosts_long(self) -> None:
        ts = datetime.utcnow()
        bundle = _bundle(ts)
        scores = _scores([
            {"engine": "technical", "direction": Direction.LONG, "raw": 0.8,
             "regime_override": Regime.TRENDING_UP},
        ])
        # Monkey-patch regime for test
        for s in scores:
            s.regime = Regime.TRENDING_UP
        decision = _decision(ts)
        RegimeFilterRule().evaluate(bundle, scores, decision)
        tech = scores[0]
        assert tech.adjusted_confidence == pytest.approx(0.8 * 1.2, rel=1e-4)


# ── Priority Ordering ──────────────────────────────────────────


class TestRulePriority:
    def test_rules_sorted_by_priority(self) -> None:
        ts = datetime.utcnow()
        rules = [
            RegimeFilterRule(),        # priority=5
            ConfidenceWeightRule(),     # priority=4
            DirectionConflictRule(),    # priority=3
            MacroAdjustmentRule(),     # priority=2
            FundamentalVetoRule(),     # priority=1
        ]
        rules.sort(key=lambda r: r.priority)
        priorities = [r.priority for r in rules]
        assert priorities == [1, 2, 3, 4, 5]
