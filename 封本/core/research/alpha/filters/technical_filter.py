"""
Technical Filter
================
Filter securities based on technical criteria.

Checks:
    - Liquidity (minimum volume/turnover)
    - Volatility range (not too volatile, not too flat)
    - Price range (minimum price, not penny stocks)

Returns FilterResult for each check.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .schema import FilterResult, CompositeFilterResult


# ─────────────────────────────────────────────────────────────────
# Liquidity Filter
# ─────────────────────────────────────────────────────────────────


def filter_liquidity(
    data: pd.DataFrame,
    min_volume: Optional[float] = None,
    min_turnover: Optional[float] = None,
    min_avg_volume: Optional[float] = None,
    avg_period: int = 20,
    volume_col: str = "volume",
    close_col: str = "close",
) -> FilterResult:
    """
    Check if security meets liquidity requirements.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, volume [, close]
    min_volume : float, optional
        Minimum daily volume.
    min_turnover : float, optional
        Minimum daily turnover (volume * close).
    min_avg_volume : float, optional
        Minimum average volume over avg_period.
    avg_period : int
        Period for average volume calculation.
    volume_col, close_col : str
        Column names.

    Returns
    -------
    FilterResult
    """
    reasons = []
    metadata = {}

    # Check latest volume
    if min_volume is not None and volume_col in data.columns:
        latest_vol = data[volume_col].iloc[-1]
        metadata["latest_volume"] = float(latest_vol)
        if latest_vol < min_volume:
            reasons.append(f"Volume {latest_vol:,.0f} < {min_volume:,.0f}")

    # Check turnover
    if min_turnover is not None and volume_col in data.columns and close_col in data.columns:
        turnover = data[volume_col].iloc[-1] * data[close_col].iloc[-1]
        metadata["latest_turnover"] = float(turnover)
        if turnover < min_turnover:
            reasons.append(f"Turnover {turnover:,.0f} < {min_turnover:,.0f}")

    # Check average volume
    if min_avg_volume is not None and volume_col in data.columns:
        avg_vol = data[volume_col].rolling(avg_period).mean().iloc[-1]
        metadata["avg_volume"] = float(avg_vol)
        if avg_vol < min_avg_volume:
            reasons.append(f"Avg volume {avg_vol:,.0f} < {min_avg_volume:,.0f}")

    passed = len(reasons) == 0
    return FilterResult(
        passed=passed,
        filter_name="liquidity",
        reasons=reasons,
        metadata=metadata,
    )


# ─────────────────────────────────────────────────────────────────
# Volatility Filter
# ─────────────────────────────────────────────────────────────────


def filter_volatility(
    data: pd.DataFrame,
    min_vol: Optional[float] = None,
    max_vol: Optional[float] = None,
    vol_period: int = 20,
    annualize: bool = True,
    close_col: str = "close",
) -> FilterResult:
    """
    Check if security's volatility is within acceptable range.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, close
    min_vol : float, optional
        Minimum annualized volatility (e.g., 0.10 for 10%).
    max_vol : float, optional
        Maximum annualized volatility (e.g., 0.60 for 60%).
    vol_period : int
        Period for volatility calculation.
    annualize : bool
        Whether to annualize volatility.
    close_col : str

    Returns
    -------
    FilterResult
    """
    if close_col not in data.columns:
        return FilterResult(
            passed=False,
            filter_name="volatility",
            reasons=[f"Missing column: {close_col}"],
        )

    # Compute volatility
    returns = data[close_col].pct_change()
    vol = returns.rolling(vol_period).std()
    if annualize:
        vol = vol * np.sqrt(252)

    latest_vol = vol.iloc[-1]
    reasons = []
    metadata = {"volatility": float(latest_vol) if not pd.isna(latest_vol) else None}

    if min_vol is not None and latest_vol < min_vol:
        reasons.append(f"Volatility {latest_vol:.2%} < {min_vol:.2%}")

    if max_vol is not None and latest_vol > max_vol:
        reasons.append(f"Volatility {latest_vol:.2%} > {max_vol:.2%}")

    passed = len(reasons) == 0
    return FilterResult(
        passed=passed,
        filter_name="volatility",
        reasons=reasons,
        metadata=metadata,
    )


# ─────────────────────────────────────────────────────────────────
# Price Filter
# ─────────────────────────────────────────────────────────────────


def filter_price(
    data: pd.DataFrame,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    close_col: str = "close",
) -> FilterResult:
    """
    Check if security's price is within acceptable range.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, close
    min_price : float, optional
        Minimum price (e.g., 1.0 to exclude penny stocks).
    max_price : float, optional
        Maximum price.
    close_col : str

    Returns
    -------
    FilterResult
    """
    if close_col not in data.columns:
        return FilterResult(
            passed=False,
            filter_name="price",
            reasons=[f"Missing column: {close_col}"],
        )

    latest_price = data[close_col].iloc[-1]
    reasons = []
    metadata = {"price": float(latest_price)}

    if min_price is not None and latest_price < min_price:
        reasons.append(f"Price {latest_price:.2f} < {min_price:.2f}")

    if max_price is not None and latest_price > max_price:
        reasons.append(f"Price {latest_price:.2f} > {max_price:.2f}")

    passed = len(reasons) == 0
    return FilterResult(
        passed=passed,
        filter_name="price",
        reasons=reasons,
        metadata=metadata,
    )


# ─────────────────────────────────────────────────────────────────
# Composite Technical Filter
# ─────────────────────────────────────────────────────────────────


def filter_technical(
    data: pd.DataFrame,
    check_liquidity: bool = True,
    check_volatility: bool = True,
    check_price: bool = True,
    liquidity_kwargs: Optional[dict] = None,
    volatility_kwargs: Optional[dict] = None,
    price_kwargs: Optional[dict] = None,
) -> CompositeFilterResult:
    """
    Apply all technical filters.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, close, volume
    check_liquidity, check_volatility, check_price : bool
    liquidity_kwargs, volatility_kwargs, price_kwargs : dict, optional
        Keyword arguments for each filter.

    Returns
    -------
    CompositeFilterResult
    """
    results = []

    if check_liquidity:
        results.append(filter_liquidity(data, **(liquidity_kwargs or {})))

    if check_volatility:
        results.append(filter_volatility(data, **(volatility_kwargs or {})))

    if check_price:
        results.append(filter_price(data, **(price_kwargs or {})))

    return CompositeFilterResult.from_results(results)


# ─────────────────────────────────────────────────────────────────
# Batch Filter for Multiple Securities
# ─────────────────────────────────────────────────────────────────


def filter_technical_batch(
    data: pd.DataFrame,
    group_col: str = "symbol",
    **kwargs,
) -> pd.DataFrame:
    """
    Apply technical filter to each security.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, close, volume
    group_col : str
    **kwargs

    Returns
    -------
    pd.DataFrame
        Columns: symbol, passed, failed_filters, reasons
    """
    results = []

    for sym, group in data.groupby(group_col):
        result = filter_technical(group, **kwargs)
        results.append(
            {
                group_col: sym,
                "passed": result.passed,
                "failed_filters": result.failed_filters,
                "reasons": [r for fr in result.filter_results for r in fr.reasons],
            }
        )

    return pd.DataFrame(results)
