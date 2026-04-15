"""
Financial Quality Filter
=======================
Filter securities based on financial quality metrics.

Checks:
    - ROE consistency (positive ROE for N consecutive periods)
    - Revenue growth (positive YoY growth)
    - Cash flow match (operating CF > net income)

Returns FilterResult for each check.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .schema import FilterResult, CompositeFilterResult


# ─────────────────────────────────────────────────────────────────
# ROE Consistency Filter
# ─────────────────────────────────────────────────────────────────


def filter_roe_consistency(
    data: pd.DataFrame,
    min_periods: int = 4,
    roe_col: str = "roe",
) -> FilterResult:
    """
    Check if ROE is consistently positive.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, roe
    min_periods : int
        Minimum consecutive periods with positive ROE.
    roe_col : str
        Column name for ROE.

    Returns
    -------
    FilterResult
    """
    if roe_col not in data.columns:
        return FilterResult(
            passed=False,
            filter_name="roe_consistency",
            reasons=[f"Missing column: {roe_col}"],
        )

    # Check positive ROE
    positive_roe = data[roe_col] > 0
    n_positive = positive_roe.sum()
    n_total = len(data)

    passed = n_positive >= min_periods
    reasons = [] if passed else [f"Only {n_positive}/{n_total} periods with positive ROE"]

    return FilterResult(
        passed=passed,
        filter_name="roe_consistency",
        reasons=reasons,
        metadata={
            "n_positive": int(n_positive),
            "n_total": n_total,
            "min_periods": min_periods,
        },
    )


# ─────────────────────────────────────────────────────────────────
# Revenue Growth Filter
# ─────────────────────────────────────────────────────────────────


def filter_revenue_growth(
    data: pd.DataFrame,
    min_growth: float = 0.0,
    revenue_col: str = "revenue",
) -> FilterResult:
    """
    Check if revenue growth is positive.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, revenue
    min_growth : float
        Minimum YoY growth rate (default 0.0).
    revenue_col : str
        Column name for revenue.

    Returns
    -------
    FilterResult
    """
    if revenue_col not in data.columns:
        return FilterResult(
            passed=False,
            filter_name="revenue_growth",
            reasons=[f"Missing column: {revenue_col}"],
        )

    # Compute YoY growth
    df = data.sort_values("timestamp")
    df["revenue_yoy"] = df[revenue_col].pct_change(4)  # Assume quarterly data

    latest_growth = df["revenue_yoy"].iloc[-1] if len(df) > 4 else None

    if latest_growth is None or pd.isna(latest_growth):
        return FilterResult(
            passed=False,
            filter_name="revenue_growth",
            reasons=["Insufficient data for YoY calculation"],
        )

    passed = latest_growth >= min_growth
    reasons = [] if passed else [f"Revenue growth {latest_growth:.2%} < {min_growth:.2%}"]

    return FilterResult(
        passed=passed,
        filter_name="revenue_growth",
        reasons=reasons,
        metadata={"latest_growth": float(latest_growth), "min_growth": min_growth},
    )


# ─────────────────────────────────────────────────────────────────
# Cash Flow Match Filter
# ─────────────────────────────────────────────────────────────────


def filter_cashflow_match(
    data: pd.DataFrame,
    cf_col: str = "operating_cf",
    ni_col: str = "net_income",
) -> FilterResult:
    """
    Check if operating cash flow >= net income.

    High-quality earnings have cash backing.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, operating_cf, net_income
    cf_col : str
        Column name for operating cash flow.
    ni_col : str
        Column name for net income.

    Returns
    -------
    FilterResult
    """
    missing = {cf_col, ni_col} - set(data.columns)
    if missing:
        return FilterResult(
            passed=False,
            filter_name="cashflow_match",
            reasons=[f"Missing columns: {missing}"],
        )

    # Check latest period
    latest = data.iloc[-1]
    cf = latest[cf_col]
    ni = latest[ni_col]

    if pd.isna(cf) or pd.isna(ni):
        return FilterResult(
            passed=False,
            filter_name="cashflow_match",
            reasons=["Missing values in latest period"],
        )

    passed = cf >= ni
    reasons = [] if passed else [f"Operating CF ({cf:,.0f}) < Net Income ({ni:,.0f})"]

    return FilterResult(
        passed=passed,
        filter_name="cashflow_match",
        reasons=reasons,
        metadata={"operating_cf": float(cf), "net_income": float(ni)},
    )


# ─────────────────────────────────────────────────────────────────
# Composite Financial Quality Filter
# ─────────────────────────────────────────────────────────────────


def filter_financial_quality(
    data: pd.DataFrame,
    check_roe: bool = True,
    check_revenue: bool = True,
    check_cashflow: bool = True,
    min_roe_periods: int = 4,
    min_revenue_growth: float = 0.0,
) -> CompositeFilterResult:
    """
    Apply all financial quality filters.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, roe, revenue, operating_cf, net_income
    check_roe, check_revenue, check_cashflow : bool
        Which checks to apply.
    min_roe_periods : int
    min_revenue_growth : float

    Returns
    -------
    CompositeFilterResult
    """
    results = []

    if check_roe:
        results.append(filter_roe_consistency(data, min_periods=min_roe_periods))

    if check_revenue:
        results.append(filter_revenue_growth(data, min_growth=min_revenue_growth))

    if check_cashflow:
        results.append(filter_cashflow_match(data))

    return CompositeFilterResult.from_results(results)


# ─────────────────────────────────────────────────────────────────
# Batch Filter for Multiple Securities
# ─────────────────────────────────────────────────────────────────


def filter_financial_quality_batch(
    data: pd.DataFrame,
    group_col: str = "symbol",
    **kwargs,
) -> pd.DataFrame:
    """
    Apply financial quality filter to each security.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, roe, revenue, operating_cf, net_income
    group_col : str
        Column to group by (default "symbol").
    **kwargs
        Passed to filter_financial_quality().

    Returns
    -------
    pd.DataFrame
        Columns: symbol, passed, failed_filters, reasons
    """
    results = []

    for sym, group in data.groupby(group_col):
        result = filter_financial_quality(group, **kwargs)
        results.append(
            {
                group_col: sym,
                "passed": result.passed,
                "failed_filters": result.failed_filters,
                "reasons": [r for fr in result.filter_results for r in fr.reasons],
            }
        )

    return pd.DataFrame(results)
