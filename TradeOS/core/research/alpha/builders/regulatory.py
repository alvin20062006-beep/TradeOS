"""
Regulatory Alpha Builder
========================
Detect regulatory flags: limit up/down, suspended, ST, etc.

This builder produces RegulatoryFlag enums for each symbol-timestamp,
indicating trading restrictions or special status.

Input: DataFrame with columns [symbol, timestamp, close, ...]
Output: DataFrame with columns [symbol, timestamp, flags: set[RegulatoryFlag]]
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from ..base import AlphaFactor
from ..filters.schema import RegulatoryFlag


# ─────────────────────────────────────────────────────────────────
# RegulatoryFlagBuilder
# ─────────────────────────────────────────────────────────────────


class RegulatoryFlagBuilder:
    """
    Build regulatory flags for securities.

    This is NOT a standard AlphaFactor - it produces categorical flags
    rather than numeric factor values.

    Parameters
    ----------
    limit_threshold : float
        Price change threshold for limit up/down detection (default 0.099 for ~10%).
    st_symbols : set[str]
        Set of ST symbol prefixes (e.g., {"ST", "*ST"}).
    suspended_symbols : set[str]
        Set of suspended symbols.
    new_listing_days : int
        Days after IPO to consider as "new listing".
    """

    def __init__(
        self,
        limit_threshold: float = 0.099,
        st_symbols: Optional[set[str]] = None,
        suspended_symbols: Optional[set[str]] = None,
        new_listing_days: int = 60,
    ):
        self.limit_threshold = limit_threshold
        self.st_symbols = st_symbols or set()
        self.suspended_symbols = suspended_symbols or set()
        self.new_listing_days = new_listing_days

    def compute(
        self,
        data: pd.DataFrame,
        listing_dates: Optional[dict[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Compute regulatory flags.

        Parameters
        ----------
        data : pd.DataFrame
            Columns: symbol, timestamp, close [, high, low, volume]
        listing_dates : dict, optional
            Map from symbol to listing_date (for new listing detection).

        Returns
        -------
        pd.DataFrame
            Columns: symbol, timestamp, flags (set[RegulatoryFlag])
        """
        df = data.copy()

        # Ensure columns
        if "symbol" not in df.columns or "timestamp" not in df.columns:
            raise ValueError("data must have 'symbol' and 'timestamp' columns")

        df = df.sort_values(["symbol", "timestamp"])
        df["flags"] = [set() for _ in range(len(df))]

        # 1. Limit up/down detection (if we have close)
        if "close" in df.columns:
            df["ret"] = df.groupby("symbol")["close"].pct_change()
            df.loc[df["ret"] >= self.limit_threshold, "flags"].apply(
                lambda s: s.add(RegulatoryFlag.LIMIT_UP)
            )
            df.loc[df["ret"] <= -self.limit_threshold, "flags"].apply(
                lambda s: s.add(RegulatoryFlag.LIMIT_DOWN)
            )

        # 2. ST detection
        if self.st_symbols:
            for st_prefix in self.st_symbols:
                mask = df["symbol"].str.startswith(st_prefix, na=False)
                df.loc[mask, "flags"].apply(lambda s: s.add(RegulatoryFlag.ST))

        # 3. Suspended detection
        if self.suspended_symbols:
            mask = df["symbol"].isin(self.suspended_symbols)
            df.loc[mask, "flags"].apply(lambda s: s.add(RegulatoryFlag.SUSPENDED))

        # 4. New listing detection
        if listing_dates and "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            for sym, list_date in listing_dates.items():
                list_dt = pd.to_datetime(list_date)
                mask = (df["symbol"] == sym) & (
                    df["timestamp"] < list_dt + pd.Timedelta(days=self.new_listing_days)
                )
                df.loc[mask, "flags"].apply(lambda s: s.add(RegulatoryFlag.NEW_LISTING))

        # 5. Low liquidity detection (if we have volume)
        if "volume" in df.columns:
            vol_median = df.groupby("symbol")["volume"].transform("median")
            low_liq_threshold = vol_median * 0.1  # Less than 10% of median
            mask = df["volume"] < low_liq_threshold
            df.loc[mask, "flags"].apply(lambda s: s.add(RegulatoryFlag.LOW_LIQUIDITY))

        return df[["symbol", "timestamp", "flags"]]

    def filter_tradable(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Filter to only tradable securities (no regulatory flags).

        Parameters
        ----------
        data : pd.DataFrame
            Output from compute() with 'flags' column.

        Returns
        -------
        pd.DataFrame
            Rows with empty flags set.
        """
        return data[data["flags"].apply(lambda x: len(x) == 0)].copy()

    def filter_excluding(
        self,
        data: pd.DataFrame,
        exclude_flags: set[RegulatoryFlag],
    ) -> pd.DataFrame:
        """
        Filter excluding specific flags.

        Parameters
        ----------
        data : pd.DataFrame
            Output from compute() with 'flags' column.
        exclude_flags : set[RegulatoryFlag]
            Flags to exclude.

        Returns
        -------
        pd.DataFrame
            Rows where flags ∩ exclude_flags = ∅
        """
        return data[
            data["flags"].apply(lambda x: len(x & exclude_flags) == 0)
        ].copy()


# ─────────────────────────────────────────────────────────────────
# Convenience functions
# ─────────────────────────────────────────────────────────────────


def detect_regulatory_flags(
    data: pd.DataFrame,
    limit_threshold: float = 0.099,
    st_symbols: Optional[set[str]] = None,
    suspended_symbols: Optional[set[str]] = None,
) -> pd.DataFrame:
    """
    Convenience function to detect regulatory flags.

    Returns DataFrame with columns: symbol, timestamp, flags
    """
    builder = RegulatoryFlagBuilder(
        limit_threshold=limit_threshold,
        st_symbols=st_symbols,
        suspended_symbols=suspended_symbols,
    )
    return builder.compute(data)


def is_tradable(data: pd.DataFrame) -> pd.Series:
    """
    Return a boolean Series indicating if each row is tradable.

    Parameters
    ----------
    data : pd.DataFrame
        Output from detect_regulatory_flags().

    Returns
    -------
    pd.Series
        True if flags is empty.
    """
    return data["flags"].apply(lambda x: len(x) == 0)
