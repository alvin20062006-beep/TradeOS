"""
基本盘评分引擎
==============

基于财务比率输出 A/B/C/D 综合评级。

评分逻辑:
- 估值维度: PE/PB 相对历史和行业均值
- 质量维度: ROE/ROA/净利率
- 成长维度: EPS增长（proxy时降权）
- 杠杆维度: D/E
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.analysis.fundamental.ratios import (
    ValuationRatios,
    QualityRatios,
    GrowthMetrics,
    LeverageMetrics,
)


class FundamentalRating(str, Enum):
    """基本盘评级."""
    A = "A"   # 优秀
    B = "B"   # 良好
    C = "C"   # 一般
    D = "D"   # 较差


@dataclass
class ScoreBreakdown:
    """评分分解."""
    valuation_score: float   # 0-100
    quality_score: float
    growth_score: float
    leverage_score: float
    overall_score: float    # 0-100

    def __repr__(self):
        return (
            f"ScoreBreakdown("
            f"val={self.valuation_score:.0f}, "
            f"qual={self.quality_score:.0f}, "
            f"grow={self.growth_score:.0f}, "
            f"lev={self.leverage_score:.0f}, "
            f"overall={self.overall_score:.0f})"
        )


@dataclass
class QualityValueGrowth:
    """Quality-Value-Growth 三维摘要."""
    quality_score: float
    value_score: float       # 逆向（低PE=高分）
    growth_score: float
    has_growth_data: bool   # 是否使用了真实成长数据

    def __repr__(self):
        return (
            f"QVGScore(quality={self.quality_score:.0f}, "
            f"value={self.value_score:.0f}, "
            f"growth={self.growth_score:.0f}, "
            f"has_data={self.has_growth_data})"
        )


# ─────────────────────────────────────────────────────────────
# 评分标准（绝对阈值，非行业相对）
# ─────────────────────────────────────────────────────────────

# 估值评分标准
PE_EXCELLENT_MAX = 15.0    # PE <= 15 → 100分
PE_FAIR_MAX = 25.0          # PE <= 25 → 60分
PE_POOR_MIN = 40.0         # PE >= 40 → 20分

PB_EXCELLENT_MAX = 2.0
PB_FAIR_MAX = 4.0
PB_POOR_MIN = 8.0

# 质量评分标准（ROE）
ROE_EXCELLENT_MIN = 0.20   # ROE >= 20% → 100分
ROE_FAIR_MIN = 0.10       # ROE >= 10% → 60分
ROE_POOR_MIN = 0.03        # ROE < 3% → 20分

# 杠杆评分标准（D/E）
DE_EXCELLENT_MAX = 0.5     # D/E <= 0.5 → 100分
DE_FAIR_MAX = 1.5          # D/E <= 1.5 → 60分
DE_POOR_MIN = 3.0          # D/E >= 3.0 → 20分


def _score_pe(pe: Optional[float]) -> float:
    """PE 估值评分."""
    if pe is None or pe <= 0:
        return 50.0  # 缺失给中性分
    if pe <= PE_EXCELLENT_MAX:
        return 100.0
    if pe <= PE_FAIR_MAX:
        return 60 + (PE_FAIR_MAX - pe) / (PE_FAIR_MAX - PE_EXCELLENT_MAX) * 40
    if pe <= PE_POOR_MIN:
        return 20 + (PE_POOR_MIN - pe) / (PE_POOR_MIN - PE_FAIR_MAX) * 40
    return 20.0


def _score_pb(pb: Optional[float]) -> float:
    """PB 估值评分."""
    if pb is None or pb <= 0:
        return 50.0
    if pb <= PB_EXCELLENT_MAX:
        return 100.0
    if pb <= PB_FAIR_MAX:
        return 60 + (PB_FAIR_MAX - pb) / (PB_FAIR_MAX - PB_EXCELLENT_MAX) * 40
    if pb <= PB_POOR_MIN:
        return 20 + (PB_POOR_MIN - pb) / (PB_POOR_MIN - PB_FAIR_MAX) * 40
    return 20.0


def _score_roe(roe: Optional[float]) -> float:
    """ROE 质量评分."""
    if roe is None:
        return 50.0
    if roe >= ROE_EXCELLENT_MIN:
        return 100.0
    if roe >= ROE_FAIR_MIN:
        return 60 + (roe - ROE_FAIR_MIN) / (ROE_EXCELLENT_MIN - ROE_FAIR_MIN) * 40
    if roe >= ROE_POOR_MIN:
        return 20 + (roe - ROE_POOR_MIN) / (ROE_FAIR_MIN - ROE_POOR_MIN) * 40
    return 20.0


def _score_de(de: Optional[float]) -> float:
    """D/E 杠杆评分."""
    if de is None:
        return 50.0  # 缺失给中性
    if de <= DE_EXCELLENT_MAX:
        return 100.0
    if de <= DE_FAIR_MAX:
        return 60 + (DE_FAIR_MAX - de) / (DE_FAIR_MAX - DE_EXCELLENT_MAX) * 40
    if de <= DE_POOR_MIN:
        return 20 + (DE_POOR_MIN - de) / (DE_POOR_MIN - DE_FAIR_MAX) * 40
    return 20.0


def score_fundamentals(
    v: ValuationRatios,
    q: QualityRatios,
    g: GrowthMetrics,
    l: LeverageMetrics,
) -> tuple[ScoreBreakdown, FundamentalRating, QualityValueGrowth]:
    """
    综合基本盘评分.

    Returns:
        (ScoreBreakdown, FundamentalRating, QualityValueGrowth)
    """
    # 1. 估值评分（PE + PB 平均）
    pe_score = _score_pe(v.pe)
    pb_score = _score_pb(v.pb)

    if v.pe is not None and v.pb is not None:
        val_score = (pe_score + pb_score) / 2
    elif v.pe is not None:
        val_score = pe_score
    elif v.pb is not None:
        val_score = pb_score
    else:
        val_score = 40.0  # 两者都缺 → 低分

    # 2. 质量评分（ROE + ROA + 净利率）
    roe_score = _score_roe(q.roe)
    roa_score = _score_roe(q.roa) if q.roa is not None else 50.0
    net_margin_score = _score_roe(q.net_margin) if q.net_margin is not None else 50.0

    qual_components = [s for s in [roe_score, roa_score, net_margin_score] if s != 50.0]
    qual_score = sum(qual_components) / len(qual_components) if qual_components else 40.0

    # 3. 成长评分（proxy → 低权重）
    has_growth = (
        g.revenue_growth_yoy is not None
        or g.net_income_growth_yoy is not None
        or g.eps_growth_yoy is not None
    )

    if has_growth:
        scores = [s for s in [
            _score_roe(g.revenue_growth_yoy) if g.revenue_growth_yoy is not None else None,
            _score_roe(g.net_income_growth_yoy) if g.net_income_growth_yoy is not None else None,
            _score_roe(g.eps_growth_yoy) if g.eps_growth_yoy is not None else None,
        ] if s is not None]
        grow_score = sum(scores) / len(scores) if scores else 40.0
    else:
        grow_score = 30.0  # proxy → 低分

    # 4. 杠杆评分
    lev_score = _score_de(l.debt_to_equity)

    # 5. 综合评分（加权平均）
    overall = (
        val_score * 0.25
        + qual_score * 0.35
        + grow_score * 0.20
        + lev_score * 0.20
    )

    # 6. 评级
    if overall >= 75:
        rating = FundamentalRating.A
    elif overall >= 55:
        rating = FundamentalRating.B
    elif overall >= 35:
        rating = FundamentalRating.C
    else:
        rating = FundamentalRating.D

    # 7. QVG 三维
    # Value score: 逆向（低PE/PB = 高分）
    value_score = val_score  # 同估值评分
    qvg = QualityValueGrowth(
        quality_score=round(qual_score, 1),
        value_score=round(value_score, 1),
        growth_score=round(grow_score, 1),
        has_growth_data=has_growth,
    )

    breakdown = ScoreBreakdown(
        valuation_score=round(val_score, 1),
        quality_score=round(qual_score, 1),
        growth_score=round(grow_score, 1),
        leverage_score=round(lev_score, 1),
        overall_score=round(overall, 1),
    )

    return breakdown, rating, qvg
