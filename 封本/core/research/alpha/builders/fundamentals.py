"""
Fundamentals Alpha Builders
=========================

L1 raw fundamental factors from financial metrics.

These are simplified baseline implementations using fields that
can be derived from the internal data layer's FundamentalsSnapshot.

Implemented factors (Constraint 3 priority):
    1. PE_RANK   - Rank of PE ratio within cross-section (percentile)
    2. PB_RANK   - Rank of PB ratio within cross-section (percentile)
    3. ROE_TTM   - Return on Equity TTM (simplified)

These builders take a DataFrame with fundamental columns and
return a DataFrame with (symbol, timestamp, raw_value).

Note: These are baseline placeholders. Production implementation
should use audited financial data with proper adjustment logic.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def _to_long_format(
    df: pd.DataFrame,
    symbol_col: str = "symbol",
    ts_col: str = "timestamp",
) -> pd.DataFrame:
    """
    Ensure df has (symbol, timestamp) as columns, not as MultiIndex.

    Handles:
    - MultiIndex (symbol, timestamp) -> unstack to columns
    - DatetimeIndex + symbol column -> already good
    - DatetimeIndex alone -> assign symbol='UNKNOWN'
    """
    if isinstance(df.index, pd.MultiIndex):
        # Unstack: rows = timestamps, cols = (symbol, field)
        df = df.unstack(level=0)  # Now cols: (field, symbol)
        df.columns = [f"{col[0]}_{col[1]}" for col in df.columns]
        df = df.reset_index()
        # Rename timestamp column
        if "timestamp" not in df.columns:
            df = df.rename(columns={df.columns[0]: "timestamp"})
        df = df.melt(
            id_vars=["timestamp"],
            var_name="symbol_field",
            value_name="value",
        )
        # Extract symbol from "field_symbol" name
        df["symbol"] = df["symbol_field"].str.split("_").str[-1]
        df = df.drop(columns=["symbol_field"])
        return df[["symbol", "timestamp", "value"]].set_index(["symbol", "timestamp"])

    if ts_col in df.columns:
        return df.set_index(["symbol", "timestamp"]) if "symbol" in df.columns else df.set_index(ts_col)

    # Only DatetimeIndex
    df = df.copy()
    df[ts_col] = df.index
    df[symbol_col] = "UNKNOWN"
    return df.set_index([symbol_col, ts_col])


def build_pe_rank(df: pd.DataFrame, pe_col: str = "pe_ratio") -> pd.DataFrame:
    """
    L1: Cross-sectional PE ratio rank (percentile 0-1).

    PE_RANK[symbol, t] = percentile rank of pe_ratio vs all symbols at time t

    Value range: 0-1
    Note: raw_value = percentile rank (0 = cheapest PE, 1 = most expensive PE).
    """
    # Unstack to wide form for cross-sectional ranking
    if isinstance(df.index, pd.MultiIndex):
        # Bring symbol to columns
        wide = df[pe_col].unstack(level=0)
    else:
        wide = df[[pe_col]].copy()
        wide["symbol"] = "UNKNOWN"
        wide = wide.pivot_table(columns="symbol", values=pe_col)

    if wide.empty or wide.shape[1] == 0:
        raise ValueError(f"PE_RANK: no data for {pe_col!r}")

    # Cross-sectional percentile rank at each timestamp
    ranked = wide.rank(pct=True, axis=1, ascending=True)

    # Stack back to long format
    ranked = ranked.stack().reset_index()
    ranked.columns = ["timestamp", "symbol", "raw_value"]
    ranked = ranked[["symbol", "timestamp", "raw_value"]].dropna()
    ranked = ranked.sort_values(["symbol", "timestamp"])

    return ranked[ranked["raw_value"].notna()]


def build_pb_rank(df: pd.DataFrame, pb_col: str = "pb_ratio") -> pd.DataFrame:
    """
    L1: Cross-sectional PB ratio rank (percentile 0-1).

    PB_RANK[symbol, t] = percentile rank of pb_ratio vs all symbols at time t
    """
    if isinstance(df.index, pd.MultiIndex):
        wide = df[pb_col].unstack(level=0)
    else:
        wide = df[[pb_col]].copy()
        wide["symbol"] = "UNKNOWN"
        wide = wide.pivot_table(columns="symbol", values=pb_col)

    if wide.empty or wide.shape[1] == 0:
        raise ValueError(f"PB_RANK: no data for {pb_col!r}")

    ranked = wide.rank(pct=True, axis=1, ascending=True)
    ranked = ranked.stack().reset_index()
    ranked.columns = ["timestamp", "symbol", "raw_value"]
    ranked = ranked[["symbol", "timestamp", "raw_value"]].dropna()
    ranked = ranked.sort_values(["symbol", "timestamp"])

    return ranked[ranked["raw_value"].notna()]


def build_roe_ttm(
    df: pd.DataFrame,
    net_income_col: str = "net_income",
    total_assets_col: str = "total_assets",
) -> pd.DataFrame:
    """
    L1: Return on Equity (simplified TTM approximation).

    ROE_TTM = net_income / total_equity (simplified to total_assets)

    Value range: typically -0.5 to 0.5 (annualised)
    """
    if net_income_col not in df.columns:
        raise ValueError(
            f"ROE_TTM requires {net_income_col!r} column. "
            f"Available columns: {list(df.columns)}"
        )

    if total_assets_col in df.columns:
        roe = df[net_income_col] / df[total_assets_col].replace(0, pd.NA)
    else:
        roe = df[net_income_col]

    result = roe.dropna().reset_index()
    if "symbol" not in result.columns:
        result.insert(0, "symbol", "UNKNOWN")
    result.columns = ["symbol", "timestamp", "raw_value"]

    return result[result["raw_value"].notna()]


# ── All fundamental factor registry ──────────────────────────────

FUNDAMENTAL_FACTORS: dict[str, callable] = {
    "PE_RANK": build_pe_rank,
    "PB_RANK": build_pb_rank,
    "ROE_TTM": build_roe_ttm,
}

FUNDAMENTAL_FACTOR_NAMES: list[str] = list(FUNDAMENTAL_FACTORS.keys())


def build_all_fundamental(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Compute all available fundamental factors.

    Returns
    -------
    dict[str, pd.DataFrame]
        Only factors whose required columns are present.
    """
    available_cols = set(df.columns)
    results = {}

    for name, builder in FUNDAMENTAL_FACTORS.items():
        required = ["pe_ratio"] if name == "PE_RANK" else \
                   ["pb_ratio"] if name == "PB_RANK" else \
                   ["net_income"]

        if required[0] in available_cols:
            try:
                results[name] = builder(df)
            except (ValueError, KeyError):
                pass

    return results
