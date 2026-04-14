"""
财务比率计算器
==============

从 FundamentalsSnapshot 计算各类财务比率。

字段来源:
- 直接字段: FundamentalsSnapshot 直接提供
- 计算字段: 从 FundamentalsSnapshot 推导
- Proxy 字段: ⚠️ 需要额外数据源，暂无时用 None 标注
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.schemas import FundamentalsSnapshot


@dataclass
class ValuationRatios:
    """估值比率."""
    pe: Optional[float]
    pb: Optional[float]
    ps: Optional[float]
    peg: Optional[float]
    ev_ebitda: Optional[float]
    market_cap: Optional[float]

    source: str = "direct"  # "direct" | "calculated" | "proxy" | "missing"


@dataclass
class QualityRatios:
    """质量比率."""
    roe: Optional[float]     # 净资产收益率
    roa: Optional[float]     # 总资产收益率
    gross_margin: Optional[float]  # 毛利率
    net_margin: Optional[float]    # 净利率
    fcf_quality: Optional[float]  # 自由现金流质量（proxy）
    asset_turnover: Optional[float]  # 资产周转率

    source: str = "direct"


@dataclass
class GrowthMetrics:
    """成长指标."""
    revenue_growth_yoy: Optional[float]
    net_income_growth_yoy: Optional[float]
    eps_growth_yoy: Optional[float]
    dividend_growth_yoy: Optional[float]

    source: str = "direct"


@dataclass
class LeverageMetrics:
    """杠杆/偿债指标."""
    debt_to_equity: Optional[float]
    current_ratio: Optional[float]
    quick_ratio: Optional[float]
    interest_coverage: Optional[float]  # 利息保障倍数

    source: str = "direct"


# ─────────────────────────────────────────────────────────────
# 计算器
# ─────────────────────────────────────────────────────────────


def calc_valuation_ratios(f: FundamentalsSnapshot) -> ValuationRatios:
    """
    计算估值比率.

    ⚠️ ev_ebitda: 需要 enterprise_value 字段，当前缺失 → proxy/missing
    """
    return ValuationRatios(
        pe=f.pe_ratio,
        pb=f.pb_ratio,
        ps=f.ps_ratio,
        peg=f.peg_ratio,
        ev_ebitda=None,  # ⚠️ proxy: 需要 enterprise_value 字段，暂缺失
        market_cap=f.market_cap,
        source="direct" if f.pe_ratio is not None else "proxy",
    )


def calc_quality_ratios(f: FundamentalsSnapshot) -> QualityRatios:
    """
    计算质量比率.

    ⚠️ 实际 ROE = net_income / equity；当前 snapshot 无 equity 字段
        → 从 pb_ratio 反推 equity_per_share = price / pb
        → ROE = eps / book_value_per_share（若两者都有）
    ⚠️ gross_margin: 需要 gross_profit/revenue，当前缺失
    ⚠️ net_margin: net_income / revenue（若两者都有）
    ⚠️ fcf_quality: 需要 cash_flow_statement，当前缺失
    """
    # ROE = EPS / BookValuePerShare
    roe = None
    if f.eps is not None and f.book_value_per_share is not None and f.book_value_per_share > 0:
        roe = f.eps / f.book_value_per_share

    # ROA = net_income / total_assets
    roa = None
    if f.net_income is not None and f.total_assets is not None and f.total_assets > 0:
        roa = f.net_income / f.total_assets

    # 毛利率: gross_profit / revenue（需要 gross_profit，暂缺）
    gross_margin = None  # ⚠️ proxy: 需要 gross_profit 字段，暂缺失

    # 净利率: net_income / revenue
    net_margin = None
    if f.net_income is not None and f.revenue is not None and f.revenue > 0:
        net_margin = f.net_income / f.revenue

    # 资产周转率: revenue / total_assets
    asset_turnover = None
    if f.revenue is not None and f.total_assets is not None and f.total_assets > 0:
        asset_turnover = f.revenue / f.total_assets

    # 现金流质量: ⚠️ proxy（需要 cash_flow_statement）
    fcf_quality = None

    return QualityRatios(
        roe=round(roe, 4) if roe is not None else None,
        roa=round(roa, 4) if roa is not None else None,
        gross_margin=None,  # ⚠️ proxy: 字段缺失
        net_margin=round(net_margin, 4) if net_margin is not None else None,
        fcf_quality=None,   # ⚠️ proxy: 字段缺失
        asset_turnover=round(asset_turnover, 4) if asset_turnover is not None else None,
        source="direct",
    )


def calc_growth_metrics(f: FundamentalsSnapshot) -> GrowthMetrics:
    """
    计算成长指标.

    ⚠️ FundamentalsSnapshot 为单期快照，无法计算 YOY 增长。
        历史增长数据需要历史财务数据源。
        当前返回 None + proxy 标注。
    """
    # ⚠️ proxy: FundamentalsSnapshot 是单期快照，无历史同期数据
    # 若 snapshot 包含历史字段可启用
    return GrowthMetrics(
        revenue_growth_yoy=None,  # ⚠️ proxy: 需要历史 revenue
        net_income_growth_yoy=None,  # ⚠️ proxy: 需要历史 net_income
        eps_growth_yoy=None,      # ⚠️ proxy: 需要历史 EPS
        dividend_growth_yoy=None,  # ⚠️ proxy: 需要历史 dividend
        source="proxy",
    )


def calc_leverage_metrics(f: FundamentalsSnapshot) -> LeverageMetrics:
    """
    计算杠杆/偿债指标.

    ⚠️ debt_to_equity: 需要 total_debt 和 equity（暂缺 equity）
    ⚠️ current_ratio / quick_ratio: 需要 current_assets/current_liabilities（暂缺）
    ⚠️ interest_coverage: 需要 interest_expense 和 EBIT（暂缺）
    """
    # D/E = total_debt / equity（equity 缺失）
    debt_to_equity = None
    if f.total_debt is not None:
        # 从 pb 反推 equity: equity = market_cap / pb
        if f.pb_ratio is not None and f.pb_ratio > 0 and f.market_cap is not None:
            equity_estimate = f.market_cap / f.pb_ratio
            debt_to_equity = f.total_debt / equity_estimate if equity_estimate > 0 else None

    # current_ratio / quick_ratio: ⚠️ proxy（需要 current_assets）
    current_ratio = None   # ⚠️ proxy
    quick_ratio = None     # ⚠️ proxy

    # 利息保障倍数: ⚠️ proxy（需要 interest_expense）
    interest_coverage = None  # ⚠️ proxy

    return LeverageMetrics(
        debt_to_equity=round(debt_to_equity, 4) if debt_to_equity is not None else None,
        current_ratio=None,   # ⚠️ proxy
        quick_ratio=None,    # ⚠️ proxy
        interest_coverage=None,  # ⚠️ proxy
        source="partial",
    )


def calc_dividend_yield(f: FundamentalsSnapshot) -> Optional[float]:
    """股息率: 直接取字段."""
    return f.dividend_yield


def summarize_ratios(
    v: ValuationRatios,
    q: QualityRatios,
    g: GrowthMetrics,
    l: LeverageMetrics,
) -> dict:
    """
    生成比率汇总，标注每个字段的来源.
    """
    summary = {
        "valuation": {
            "pe": {"value": v.pe, "source": v.source},
            "pb": {"value": v.pb, "source": v.source},
            "ps": {"value": v.ps, "source": v.source},
            "peg": {"value": v.peg, "source": v.source},
            "ev_ebitda": {"value": v.ev_ebitda, "source": "proxy"},  # 始终 proxy
        },
        "quality": {
            "roe": {"value": q.roe, "source": q.source},
            "roa": {"value": q.roa, "source": q.source},
            "gross_margin": {"value": q.gross_margin, "source": "proxy"},  # 始终 proxy
            "net_margin": {"value": q.net_margin, "source": q.source},
            "fcf_quality": {"value": q.fcf_quality, "source": "proxy"},
            "asset_turnover": {"value": q.asset_turnover, "source": q.source},
        },
        "growth": {
            "revenue_growth_yoy": {"value": g.revenue_growth_yoy, "source": g.source},
            "net_income_growth_yoy": {"value": g.net_income_growth_yoy, "source": g.source},
            "eps_growth_yoy": {"value": g.eps_growth_yoy, "source": g.source},
        },
        "leverage": {
            "debt_to_equity": {"value": l.debt_to_equity, "source": l.source},
            "current_ratio": {"value": l.current_ratio, "source": "proxy"},
            "quick_ratio": {"value": l.quick_ratio, "source": "proxy"},
            "interest_coverage": {"value": l.interest_coverage, "source": "proxy"},
        },
    }
    return summary
