"""
报表生成器
===========

将所有计算结果组合成 FundamentalReport。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

from core.schemas import FundamentalsSnapshot

from .ratios import (
    calc_valuation_ratios,
    calc_quality_ratios,
    calc_growth_metrics,
    calc_leverage_metrics,
    calc_dividend_yield,
    summarize_ratios,
)
from .scorer import score_fundamentals, FundamentalRating, QualityValueGrowth


@dataclass
class FundamentalReport:
    """
    基本盘信息报表.

    Attributes:
        symbol: 股票代码
        report_date: 报表日期
        valuation: 估值指标（可能含 None）
        profitability: 盈利能力
        growth: 成长指标（proxy → 大部分 None）
        financial_health: 财务健康度
        dividend: 股息
        signals: 信号与评分
        rating: A/B/C/D 综合评级
        quality_value_growth: QVG 三维评分
        score_breakdown: 评分分解
        metadata: 扩展元数据（含字段来源标注）
    """
    symbol: str
    report_date: datetime

    # 估值
    pe: Optional[float]
    pb: Optional[float]
    ps: Optional[float]
    peg: Optional[float]
    ev_ebitda: Optional[float]    # ⚠️ proxy
    market_cap: Optional[float]

    # 盈利能力
    roe: Optional[float]
    roa: Optional[float]
    gross_margin: Optional[float]  # ⚠️ proxy
    net_margin: Optional[float]

    # 成长
    revenue_growth_yoy: Optional[float]  # ⚠️ proxy
    net_income_growth_yoy: Optional[float]  # ⚠️ proxy
    eps_growth_yoy: Optional[float]        # ⚠️ proxy

    # 财务健康
    debt_to_equity: Optional[float]
    current_ratio: Optional[float]    # ⚠️ proxy
    quick_ratio: Optional[float]       # ⚠️ proxy
    interest_coverage: Optional[float] # ⚠️ proxy

    # 股息
    dividend_yield: Optional[float]

    # 信号
    quality_score: float              # 0-100
    value_score: float                 # 0-100
    growth_score: float                # 0-100
    red_flags: list[str]              # 警告项

    # 综合评级
    rating: str                        # A/B/C/D

    # 元数据
    metadata: dict                    # 字段来源 + proxy 标注


def generate_report(
    f: FundamentalsSnapshot,
    prev_f: Optional[FundamentalsSnapshot] = None,
) -> FundamentalReport:
    """
    生成基本盘报表.

    Args:
        f: 当前基本面数据
        prev_f: 上一期数据（可选，用于计算增长）
    Returns:
        FundamentalReport
    """
    # 计算各项比率
    v = calc_valuation_ratios(f)
    q = calc_quality_ratios(f)

    # 成长指标（尝试用两期数据计算 YOY）
    g = _calc_growth_with_history(f, prev_f)

    l = calc_leverage_metrics(f)
    div_yield = calc_dividend_yield(f)

    # 评分
    breakdown, rating, qvg = score_fundamentals(v, q, g, l)

    # 红线检测
    red_flags = _detect_red_flags(f, v, q, l)

    # 元数据
    summary = summarize_ratios(v, q, g, l)
    is_proxy = summary["growth"]["revenue_growth_yoy"]["source"] == "proxy"

    return FundamentalReport(
        symbol=f.symbol,
        report_date=f.timestamp,

        # 估值
        pe=v.pe,
        pb=v.pb,
        ps=v.ps,
        peg=v.peg,
        ev_ebitda=v.ev_ebitda,
        market_cap=v.market_cap,

        # 盈利能力
        roe=q.roe,
        roa=q.roa,
        gross_margin=q.gross_margin,
        net_margin=q.net_margin,

        # 成长
        revenue_growth_yoy=g.revenue_growth_yoy,
        net_income_growth_yoy=g.net_income_growth_yoy,
        eps_growth_yoy=g.eps_growth_yoy,

        # 财务健康
        debt_to_equity=l.debt_to_equity,
        current_ratio=l.current_ratio,
        quick_ratio=l.quick_ratio,
        interest_coverage=l.interest_coverage,

        # 股息
        dividend_yield=div_yield,

        # 信号
        quality_score=qvg.quality_score,
        value_score=qvg.value_score,
        growth_score=qvg.growth_score,
        red_flags=red_flags,

        # 评级
        rating=rating.value,  # FundamentalRating 是 str 子类

        # 元数据
        metadata={
            "report_date": f.timestamp.isoformat(),
            "proxy": is_proxy,
            "ratios": summary,
            "score_breakdown": {
                "valuation_score": breakdown.valuation_score,
                "quality_score": breakdown.quality_score,
                "growth_score": breakdown.growth_score,
                "leverage_score": breakdown.leverage_score,
                "overall_score": breakdown.overall_score,
            },
            "qvg_detail": {
                "quality_score": qvg.quality_score,
                "value_score": qvg.value_score,
                "growth_score": qvg.growth_score,
                "has_growth_data": qvg.has_growth_data,
            },
            "field_sources": {
                "ev_ebitda": "proxy (需要 enterprise_value 字段)",
                "gross_margin": "proxy (需要 gross_profit 字段)",
                "revenue_growth_yoy": "proxy (需要历史财务数据)",
                "net_income_growth_yoy": "proxy (需要历史财务数据)",
                "eps_growth_yoy": "proxy (需要历史 EPS 数据)",
                "current_ratio": "proxy (需要 current_assets 字段)",
                "quick_ratio": "proxy (需要 current_assets 字段)",
                "interest_coverage": "proxy (需要 interest_expense 字段)",
            },
        },
    )


# ─────────────────────────────────────────────────────────────
# 内部辅助
# ─────────────────────────────────────────────────────────────


def _calc_growth_with_history(
    current: FundamentalsSnapshot,
    prev: Optional[FundamentalsSnapshot],
):
    """
    计算 YOY 增长（如果有历史数据）.
    """
    from .ratios import GrowthMetrics

    if prev is None:
        g = calc_growth_metrics(current)
        return g

    # YOY = (current - prev) / prev
    def yoy(cur, prv):
        if cur is not None and prv is not None and prv != 0:
            return (cur - prv) / abs(prv)
        return None

    return GrowthMetrics(
        revenue_growth_yoy=yoy(current.revenue, prev.revenue),
        net_income_growth_yoy=yoy(current.net_income, prev.net_income),
        eps_growth_yoy=yoy(current.eps, prev.eps),
        dividend_growth_yoy=None,  # 暂不支持
        source="calculated",
    )


def _detect_red_flags(
    f: FundamentalsSnapshot,
    v,
    q,
    l,
) -> list[str]:
    """
    检测基本面红线/警告项.
    """
    flags = []

    # PE 极端
    pe = getattr(f, "pe_ratio", None) or getattr(f, "pe", None)
    net_inc = getattr(f, "net_income", None)
    rev = getattr(f, "revenue", None)

    if pe is not None and pe < 0:
        flags.append("negative_pe")
    if pe is not None and pe > 100:
        flags.append("extreme_pe")

    # 负利润
    if net_inc is not None and net_inc < 0:
        flags.append("net_loss")

    # ROE 极低
    if q.roe is not None and q.roe < 0:
        flags.append("negative_roe")

    # 杠杆过高
    if l.debt_to_equity is not None and l.debt_to_equity > 3.0:
        flags.append("high_leverage")

    # 无营业收入
    if rev is not None and rev == 0:
        flags.append("zero_revenue")

    return flags
