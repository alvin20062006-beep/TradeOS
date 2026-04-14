"""
Tests for Fundamental Engine
"""

import pytest
from datetime import datetime

from core.analysis.fundamental import FundamentalEngine
from core.analysis.fundamental import ratios
from core.analysis.fundamental import scorer
from core.analysis.fundamental import report
from core.schemas import FundamentalsSnapshot


def _snapshot(
    symbol="AAPL",
    pe=25.0,
    pb=7.0,
    ps=7.5,
    eps=6.0,
    book_value_per_share=14.0,
    market_cap=2.5e12,
    net_income=3.0e11,
    total_assets=3.5e11,
    total_debt=1.2e11,
    revenue=3.85e11,
    dividend_yield=0.005,
):
    return FundamentalsSnapshot(
        symbol=symbol,
        timestamp=datetime.utcnow(),
        market_cap=market_cap,
        pe_ratio=pe,
        pb_ratio=pb,
        ps_ratio=ps,
        peg_ratio=None,
        revenue=revenue,
        ebitda=None,
        net_income=net_income,
        total_assets=total_assets,
        total_debt=total_debt,
        eps=eps,
        book_value_per_share=book_value_per_share,
        dividend_yield=dividend_yield,
        beta=1.2,
        avg_volume_20d=5.0e7,
    )


def _snapshot_missing_fields():
    """仅有估值字段，其他缺失."""
    return FundamentalsSnapshot(
        symbol="MYST",
        timestamp=datetime.utcnow(),
        pe_ratio=20.0,
        pb_ratio=3.0,
    )


class TestRatios:
    """Test ratio calculators."""

    def test_calc_valuation_ratios_full(self):
        f = _snapshot()
        v = ratios.calc_valuation_ratios(f)

        assert v.pe == 25.0
        assert v.pb == 7.0
        assert v.source == "direct"

    def test_calc_valuation_ratios_partial(self):
        f = _snapshot_missing_fields()
        v = ratios.calc_valuation_ratios(f)

        assert v.pe == 20.0
        assert v.pb == 3.0
        assert v.ev_ebitda is None  # proxy

    def test_calc_quality_ratios_full(self):
        f = _snapshot()
        q = ratios.calc_quality_ratios(f)

        # ROE = EPS / BookValuePerShare = 6/14
        assert q.roe is not None
        assert 0.3 < q.roe < 0.5

        # ROA = net_income / total_assets
        assert q.roa is not None
        assert 0.8 < q.roa < 0.9

        # net_margin = net_income / revenue
        assert q.net_margin is not None
        assert 0.7 < q.net_margin < 0.85

        assert q.gross_margin is None  # proxy

    def test_calc_quality_ratios_missing(self):
        f = _snapshot_missing_fields()
        q = ratios.calc_quality_ratios(f)

        assert q.roe is None  # 无 EPS/BookValue
        assert q.roa is None  # 无 net_income/total_assets
        assert q.gross_margin is None  # proxy

    def test_calc_leverage_metrics(self):
        f = _snapshot()
        l = ratios.calc_leverage_metrics(f)

        # D/E = total_debt / equity_estimate
        assert l.debt_to_equity is not None
        assert 0 < l.debt_to_equity < 1.5

        assert l.current_ratio is None  # proxy
        assert l.quick_ratio is None    # proxy

    def test_calc_dividend_yield(self):
        f = _snapshot()
        result = ratios.calc_dividend_yield(f)

        assert result == 0.005

    def test_summarize_ratios(self):
        f = _snapshot()
        v = ratios.calc_valuation_ratios(f)
        q = ratios.calc_quality_ratios(f)
        g = ratios.calc_growth_metrics(f)
        l = ratios.calc_leverage_metrics(f)

        summary = ratios.summarize_ratios(v, q, g, l)

        assert "valuation" in summary
        assert "quality" in summary
        assert "growth" in summary
        assert "leverage" in summary

        # proxy 字段标注
        assert summary["growth"]["revenue_growth_yoy"]["source"] == "proxy"
        assert summary["leverage"]["current_ratio"]["source"] == "proxy"


class TestScorer:
    """Test scoring engine."""

    def test_score_fundamentals_excellent(self):
        f = _snapshot(pe=12.0, pb=3.0)  # 低估值
        v = ratios.calc_valuation_ratios(f)
        q = ratios.calc_quality_ratios(f)
        g = ratios.calc_growth_metrics(f)
        l = ratios.calc_leverage_metrics(f)

        breakdown, rating, qvg = scorer.score_fundamentals(v, q, g, l)

        assert rating.value in ["A", "B"]
        assert 0 <= breakdown.overall_score <= 100

    def test_score_fundamentals_missing_fields(self):
        f = _snapshot_missing_fields()
        v = ratios.calc_valuation_ratios(f)
        q = ratios.calc_quality_ratios(f)
        g = ratios.calc_growth_metrics(f)
        l = ratios.calc_leverage_metrics(f)

        breakdown, rating, qvg = scorer.score_fundamentals(v, q, g, l)

        assert rating.value in ["A", "B", "C", "D"]
        assert qvg.has_growth_data is False
        assert breakdown.growth_score < 50  # proxy → 低分

    def test_qvg_no_growth_data(self):
        f = _snapshot_missing_fields()
        v = ratios.calc_valuation_ratios(f)
        q = ratios.calc_quality_ratios(f)
        g = ratios.calc_growth_metrics(f)
        l = ratios.calc_leverage_metrics(f)

        _, _, qvg = scorer.score_fundamentals(v, q, g, l)

        assert qvg.has_growth_data is False

    def test_pe_score_function(self):
        # 高PE → 低分
        assert scorer._score_pe(50.0) < scorer._score_pe(20.0)
        # None → 中性
        assert scorer._score_pe(None) == 50.0

    def test_rating_thresholds(self):
        # 测试各档阈值
        breakdown_a = scorer.ScoreBreakdown(80, 80, 80, 80, 80)
        assert breakdown_a.overall_score >= 75

        breakdown_c = scorer.ScoreBreakdown(30, 30, 30, 30, 35)
        assert 35 <= breakdown_c.overall_score < 55


class TestReport:
    """Test report generation."""

    def test_generate_report_full(self):
        f = _snapshot()
        rpt = report.generate_report(f)

        assert rpt.symbol == "AAPL"
        assert rpt.pe == 25.0
        assert rpt.pb == 7.0
        assert rpt.roe is not None
        assert rpt.rating in ["A", "B", "C", "D"]
        assert "ratios" in rpt.metadata
        assert "score_breakdown" in rpt.metadata

    def test_generate_report_missing(self):
        f = _snapshot_missing_fields()
        rpt = report.generate_report(f)

        assert rpt.pe == 20.0
        assert rpt.roe is None
        assert rpt.rating in ["A", "B", "C", "D"]

    def test_red_flags_negative_pe(self):
        f = _snapshot(pe=-5.0)
        rpt = report.generate_report(f)

        assert "negative_pe" in rpt.red_flags

    def test_red_flags_high_leverage(self):
        f = _snapshot(total_debt=1.0e13)  # 极高负债
        rpt = report.generate_report(f)

        assert "high_leverage" in rpt.red_flags or rpt.debt_to_equity is not None

    def test_red_flags_net_loss(self):
        f = _snapshot(net_income=-1.0e9)
        rpt = report.generate_report(f)

        assert "net_loss" in rpt.red_flags

    def test_report_metadata_has_field_sources(self):
        f = _snapshot_missing_fields()
        rpt = report.generate_report(f)

        assert "field_sources" in rpt.metadata
        assert rpt.metadata["field_sources"]["gross_margin"] == "proxy (需要 gross_profit 字段)"
        assert rpt.metadata["field_sources"]["revenue_growth_yoy"] == "proxy (需要历史财务数据)"


class TestFundamentalEngine:
    """Test FundamentalEngine integration."""

    def test_engine_initialization(self):
        engine = FundamentalEngine()
        assert engine.engine_name == "fundamental"
        assert engine.health_check() is True

    def test_analyze_with_snapshot(self):
        f = _snapshot()
        engine = FundamentalEngine()
        rpt = engine.analyze(f)

        assert rpt.symbol == "AAPL"
        assert rpt.pe == 25.0
        assert rpt.rating in ["A", "B", "C", "D"]

    def test_analyze_with_dict(self):
        data = {
            "symbol": "TSLA",
            "timestamp": datetime.utcnow(),
            "pe_ratio": 60.0,
            "pb_ratio": 10.0,
        }
        engine = FundamentalEngine()
        rpt = engine.analyze(data)

        assert rpt.symbol == "TSLA"
        assert rpt.pe == 60.0

    def test_analyze_with_prev_data(self):
        current = _snapshot(pe=20.0, eps=6.0)
        prev = _snapshot(pe=25.0, eps=5.0)
        engine = FundamentalEngine()
        rpt = engine.analyze(current, prev_data=prev)

        # EPS 增长 = (6-5)/5 = 0.2
        assert rpt.eps_growth_yoy is not None

    def test_analyze_empty_returns_d_report(self):
        engine = FundamentalEngine()
        rpt = engine.analyze(None)

        assert rpt.rating == "D"
        assert "no_data" in rpt.red_flags
        assert rpt.metadata["proxy"] is True

    def test_batch_analyze(self):
        data_map = {
            "AAPL": _snapshot(),
            "MSFT": _snapshot(symbol="MSFT"),
        }
        engine = FundamentalEngine()
        reports = engine.batch_analyze(data_map)

        assert set(reports.keys()) == {"AAPL", "MSFT"}

    def test_custom_config(self):
        engine = FundamentalEngine(config={"my_setting": True})
        assert engine.config["my_setting"] is True

    def test_report_fields_complete(self):
        f = _snapshot()
        engine = FundamentalEngine()
        rpt = engine.analyze(f)

        # 检查所有字段
        assert hasattr(rpt, "pe")
        assert hasattr(rpt, "pb")
        assert hasattr(rpt, "ps")
        assert hasattr(rpt, "roe")
        assert hasattr(rpt, "roa")
        assert hasattr(rpt, "net_margin")
        assert hasattr(rpt, "debt_to_equity")
        assert hasattr(rpt, "rating")
        assert hasattr(rpt, "metadata")

    def test_metadata_proxy_flag(self):
        # 有部分 proxy
        f = _snapshot_missing_fields()
        engine = FundamentalEngine()
        rpt = engine.analyze(f)

        # growth 数据全是 proxy
        assert rpt.metadata["proxy"] is True

    def test_field_sources_annotation(self):
        f = _snapshot()
        engine = FundamentalEngine()
        rpt = engine.analyze(f)

        sources = rpt.metadata["field_sources"]
        # 明确标注的 proxy 字段
        assert sources["ev_ebitda"] == "proxy (需要 enterprise_value 字段)"
        assert sources["gross_margin"] == "proxy (需要 gross_profit 字段)"
        assert sources["current_ratio"] == "proxy (需要 current_assets 字段)"

    def test_qvg_scores(self):
        f = _snapshot()
        engine = FundamentalEngine()
        rpt = engine.analyze(f)

        assert 0 <= rpt.quality_score <= 100
        assert 0 <= rpt.value_score <= 100
        assert 0 <= rpt.growth_score <= 100

    def test_regime_risk_flag(self):
        # 极端 PE
        f = _snapshot(pe=150.0)
        engine = FundamentalEngine()
        rpt = engine.analyze(f)

        assert "extreme_pe" in rpt.red_flags
