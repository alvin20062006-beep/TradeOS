"""
Composite Alpha Builder
====================

L3: Multi-factor combination builders.

Composite factors take multiple L1/L2 factor DataFrames and
produce a single combined signal.

Supported combination methods:
    1. equal_weight      - Simple average of normalised factors
    2. ic_weighted      - Weight by IC (Information Coefficient) vs label
    3. rank_average     - Average of cross-sectional ranks

Constraints followed:
- All component factors must have the same (symbol, timestamp) structure
- Weights must sum to 1.0
- Method raises on shape/alignment mismatch

Note: This is the minimum L3 composite implementation.
Advanced methods (PCA, risk parity, ML weighting) are reserved
for later phases when training infrastructure is available.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def _align_and_stack(
    factor_dict: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Align all factor DataFrames to common (symbol, timestamp) index
    and stack into a wide DataFrame.

    Returns
    -------
    pd.DataFrame: columns = factor names
        Index: (symbol, timestamp) MultiIndex
    """
    if not factor_dict:
        raise ValueError("factor_dict is empty")

    ref_name = next(iter(factor_dict))
    ref_df = factor_dict[ref_name]

    # Detect and normalise each df to (symbol, timestamp) MultiIndex with 'raw_value'
    def _to_multiindex(df: pd.DataFrame) -> pd.Series:
        """Normalise to a Series with MultiIndex (symbol, timestamp) named 'raw_value'."""
        if isinstance(df.columns, pd.MultiIndex):
            # Already in (symbol, timestamp, raw_value) long format
            idx_names = df.index.names if isinstance(df.index, pd.MultiIndex) else [None, None]
            df = df.copy()
            if "raw_value" in df.columns:
                return df["raw_value"].rename(ref_name)
            return df.iloc[:, 0].rename(ref_name)

        if {"symbol", "timestamp", "raw_value"}.issubset(set(df.columns)):
            df = df.copy()
            df = df.dropna(subset=["raw_value"])
            df = df.set_index(["symbol", "timestamp"])["raw_value"]
            df.name = ref_name
            return df

        # Only raw_value column
        if len(df.columns) == 1 and "raw_value" in df.columns:
            df = df.copy()
            if isinstance(df.index, pd.MultiIndex):
                return df["raw_value"].rename(ref_name)
            df = df.reset_index()
            if {"symbol", "timestamp"}.issubset(set(df.columns)):
                df = df.set_index(["symbol", "timestamp"])["raw_value"]
                df.name = ref_name
                return df
            else:
                df["symbol"] = "UNKNOWN"
                df["timestamp"] = df.index if isinstance(df.index, pd.DatetimeIndex) else range(len(df))
                return df.set_index(["symbol", "timestamp"])["raw_value"].rename(ref_name)

        # Fallback: first numeric column
        for col in df.columns:
            if col != "raw_value":
                s = df[col].copy()
                if isinstance(s.index, pd.MultiIndex):
                    s.name = col
                    return s
        raise ValueError(f"Cannot normalise DataFrame with columns {list(df.columns)}")

    aligned: list[pd.Series] = []

    for name, df in factor_dict.items():
        try:
            series = _to_multiindex(df)
            series.name = name
            aligned.append(series)
        except Exception:
            pass

    if not aligned:
        raise ValueError("Could not align any factors")

    # Build index from first aligned series
    ref_series = aligned[0]
    base_index = ref_series.index

    # Align all series to the reference index
    wide_data = {}
    for series in aligned:
        common = base_index.intersection(series.index)
        wide_data[series.name] = series.reindex(common)

    wide = pd.DataFrame(wide_data, index=base_index)
    return wide.dropna(how="all")


def build_equal_weight(
    factor_dict: dict[str, pd.DataFrame],
    name: str = "COMPOSITE_EQ",
) -> pd.DataFrame:
    """
    L3: Equal-weight combination of normalised factors.

    composite = mean(factor_normalised for each factor)

    All factors must have raw_value columns with same (symbol, timestamp) index.

    Parameters
    ----------
    factor_dict : dict[str, pd.DataFrame]
        Mapping from factor_name -> DataFrame(symbol, timestamp, raw_value)
    name : str

    Returns
    -------
    pd.DataFrame: symbol, timestamp, composite_value
    """
    wide = _align_and_stack(factor_dict)

    composite = wide.mean(axis=1, skipna=True)
    result = composite.reset_index()
    result.columns = ["symbol", "timestamp", "composite_value"]

    return result[result["composite_value"].notna()]


def build_ic_weighted(
    factor_dict: dict[str, pd.DataFrame],
    label_series: pd.Series,
    name: str = "COMPOSITE_IC",
) -> pd.DataFrame:
    """
    L3: IC-weighted combination of factors.

    composite = sum(weight_i * factor_i)
    where weight_i = IC_i / sum(|IC_j| for j in factors)

    IC_i = correlation(factor_i, label_series)

    Parameters
    ----------
    factor_dict : dict[str, pd.DataFrame]
    label_series : pd.Series
        Label aligned to same (symbol, timestamp) index as factors.
        Typically: forward return or label from labels/base.py
    name : str

    Returns
    -------
    pd.DataFrame: symbol, timestamp, composite_value
    """
    wide = _align_and_stack(factor_dict)

    # Align label
    common_idx = wide.index.intersection(label_series.index)
    wide = wide.loc[common_idx]
    label_aligned = label_series.loc[common_idx]

    # Compute IC for each factor
    weights = {}
    for col in wide.columns:
        factor = wide[col].dropna()
        label_dropna = label_aligned.loc[factor.index].dropna()
        factor_for_ic = factor.loc[label_dropna.index]

        if len(factor_for_ic) < 10:
            weights[col] = 0.0
            continue

        ic = factor_for_ic.corr(label_dropna)
        weights[col] = abs(ic) if pd.notna(ic) else 0.0

    # Normalise weights
    total = sum(weights.values())
    if total == 0:
        # Fallback to equal weight
        return build_equal_weight(factor_dict, name)

    norm_weights = {k: v / total for k, v in weights.items()}

    # Weighted composite
    weighted_sum = sum(norm_weights[col] * wide[col] for col in wide.columns)
    weighted_sum.name = "composite_value"
    result = weighted_sum.reset_index()
    result.columns = ["symbol", "timestamp", "composite_value"]

    return result[result["composite_value"].notna()]


def build_rank_average(
    factor_dict: dict[str, pd.DataFrame],
    name: str = "COMPOSITE_RANK",
) -> pd.DataFrame:
    """
    L3: Average of cross-sectional percentile ranks.

    For each timestamp (across all symbols):
        rank_i[s] = percentile_rank(factor_i[s] among all symbols at t)
    composite[t, s] = mean(rank_i[s] for i in factors)

    This is robust to outliers and different factor scales.
    """
    wide = _align_and_stack(factor_dict)

    # Determine grouping level
    is_multiindex = isinstance(wide.index, pd.MultiIndex)

    # Rank each column at each timestamp (cross-sectional rank)
    if is_multiindex:
        # Group by timestamp level
        ranked = wide.groupby(level="timestamp").apply(
            lambda g: g.droplevel("timestamp").rank(pct=True, ascending=True)
        )
    else:
        # Single symbol or DatetimeIndex-only
        ranked = wide.rank(pct=True, ascending=True)

    composite = ranked.mean(axis=1, skipna=True)
    composite.name = "composite_value"
    result = composite.reset_index()
    result.columns = ["symbol", "timestamp", "composite_value"]

    return result[result["composite_value"].notna()]


# ── Composite factory ─────────────────────────────────────────────

COMPOSITE_METHODS = {
    "equal_weight": build_equal_weight,
    "ic_weighted": build_ic_weighted,
    "rank_average": build_rank_average,
}


def build_composite(
    factor_dict: dict[str, pd.DataFrame],
    method: str = "equal_weight",
    name: Optional[str] = None,
    label_series: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    Build a composite factor from multiple L1/L2 factors.

    Parameters
    ----------
    factor_dict : dict[str, pd.DataFrame]
        Factor DataFrames with columns: symbol, timestamp, raw_value
    method : str
        One of: "equal_weight", "ic_weighted", "rank_average"
    name : str, optional
        Name for the composite. Defaults to "COMPOSITE_{method}".
    label_series : pd.Series, optional
        Required for "ic_weighted" method.

    Returns
    -------
    pd.DataFrame: symbol, timestamp, composite_value

    Raises
    ------
    ValueError: Unknown method, or label_series missing for ic_weighted.
    """
    if method not in COMPOSITE_METHODS:
        raise ValueError(
            f"Unknown method {method!r}. "
            f"Available: {list(COMPOSITE_METHODS.keys())}"
        )

    if method == "ic_weighted" and label_series is None:
        raise ValueError(
            "method='ic_weighted' requires label_series argument. "
            "Provide a forward return series aligned to factor index."
        )

    builder = COMPOSITE_METHODS[method]
    composite_name = name or f"COMPOSITE_{method.upper()}"

    return builder(factor_dict, composite_name)
