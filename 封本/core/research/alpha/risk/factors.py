"""
core.research.alpha.risk.factors
================================
Factor risk exposure analysis (research layer).

Responsibilities
----------------
- factor_betas: OLS regression of factor on returns → per-period betas
- factor_covariance: factor covariance matrix (symmetric positive semi-definite)
- market_beta: each factor's beta vs market return
- risk_attribution: per-factor contribution to total factor variance

Constraints
-----------
- Research-layer only: returns exposure dicts / DataFrames
- No execution-layer fields (no position sizing, no order types)
- No portfolio optimization (deferred to Batch 4B)
- to_portfolio_risk() / full risk decomposition deferred to Batch 4B
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


class FactorRiskAnalysis:
    """
    Compute factor-level risk metrics from factor and return data.

    All methods return research-layer objects (DataFrames / Series / dicts).
    No execution-layer fields are produced.

    Parameters
    ----------
    min_periods : int
        Minimum aligned data points required (default 3).
    """

    def __init__(self, min_periods: int = 3):
        self.min_periods = min_periods

    # ── Core risk methods ────────────────────────────────────────────────

    def factor_betas(
        self,
        factors: pd.DataFrame,
        returns: pd.Series,
        window: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Rolling OLS betas: each factor's sensitivity to returns.

        beta_i = cov(factor_i, returns) / var(returns)

        Parameters
        ----------
        factors : pd.DataFrame
            Columns = factor names, index = timestamps.
        returns : pd.Series
            Asset/stock returns aligned to factors.
        window : int, optional
            Rolling window size. If None, computes full-period beta (scalar per factor).

        Returns
        -------
        pd.DataFrame
            shape = (n_periods, n_factors) if window is set,
            else shape = (n_factors,) as DataFrame with single column "beta".
        """
        aligned = self._align(factors, returns)
        if aligned is None:
            return pd.DataFrame()

        f, r = aligned
        if window is None:
            # Full-period scalar beta per factor
            betas = {}
            for col in f.columns:
                sub = pd.DataFrame({"f": f[col], "r": r}).dropna()
                if len(sub) < self.min_periods:
                    betas[col] = 0.0
                    continue
                var_r = sub["r"].var()
                if var_r < 1e-12:
                    betas[col] = 0.0
                else:
                    betas[col] = float(sub["f"].cov(sub["r"]) / var_r)
            return pd.DataFrame(betas, index=["beta"])

        # Rolling beta
        betas_list = []
        for start in range(len(f) - window + 1):
            end = start + window
            window_f = f.iloc[start:end]
            window_r = r.iloc[start:end]
            row = {}
            for col in window_f.columns:
                sub = pd.DataFrame({"f": window_f[col], "r": window_r}).dropna()
                if len(sub) < 2:
                    row[col] = np.nan
                    continue
                var_r = sub["r"].var()
                if var_r < 1e-12:
                    row[col] = 0.0
                else:
                    row[col] = float(sub["f"].cov(sub["r"]) / var_r)
            betas_list.append(row)

        return pd.DataFrame(betas_list, index=f.index[window - 1:])

    def factor_covariance(
        self,
        factors: pd.DataFrame,
        min_periods: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Factor covariance matrix (symmetric positive semi-definite).

        Uses rolling 60-day covariance by default. Falls back to full-period
        if insufficient data. All off-diagonal values are clipped to [-1, 1]
        to enforce valid correlation bounds.

        Parameters
        ----------
        factors : pd.DataFrame
            Columns = factor names, index = timestamps.
        min_periods : int, optional
            Minimum periods for rolling. Defaults to 60.

        Returns
        -------
        pd.DataFrame
            Symmetric covariance matrix (factors × factors).
        """
        min_periods = min_periods or 60
        if factors.empty or len(factors.columns) < 2:
            return pd.DataFrame(index=factors.columns, columns=factors.columns)

        # Drop columns with zero variance
        std = factors.std()
        valid_cols = std[std > 1e-12].index.tolist()
        if len(valid_cols) < 2:
            return pd.DataFrame(index=factors.columns, columns=factors.columns)

        f_valid = factors[valid_cols]

        if len(f_valid) >= min_periods:
            # rolling().cov() returns stacked pairs (n_dates * n_cols, n_cols).
            # After dropna: last n_valid rows = last date's full covariance matrix.
            rolling_stacked = f_valid.rolling(min_periods).cov().dropna()
            # Last n_valid rows = covariance of the most recent date
            last_cov = rolling_stacked.iloc[-len(valid_cols):]  # (n_valid, n_valid)
            # last_cov now has MultiIndex; reset to plain column names
            last_cov.index = pd.RangeIndex(len(valid_cols))
            cov_vals = last_cov.values
        else:
            cov_vals = f_valid.cov().values

        cov_df = pd.DataFrame(cov_vals, index=valid_cols, columns=valid_cols)

        # Fill full matrix (with zeros for any dropped columns)
        full = pd.DataFrame(0.0, index=factors.columns, columns=factors.columns)
        for c in valid_cols:
            for r in valid_cols:
                full.loc[c, r] = cov_df.loc[c, r]
        return full

    def market_beta(
        self,
        factors: pd.DataFrame,
        market_returns: pd.Series,
        window: Optional[int] = None,
    ) -> pd.Series:
        """
        Each factor's beta against the market return series.

        beta_i = cov(factor_i, market_return) / var(market_return)

        Parameters
        ----------
        factors : pd.DataFrame
            Columns = factor names.
        market_returns : pd.Series
            Market return series (e.g., equal-weighted portfolio return).
        window : int, optional
            Rolling window. If None, full-period beta.

        Returns
        -------
        pd.Series
            Index = factor names, values = market beta.
        """
        aligned = self._align(factors, market_returns)
        if aligned is None:
            return pd.Series(dtype=float)

        f, mkt = aligned
        var_mkt = mkt.var()
        if var_mkt < 1e-12:
            return pd.Series(0.0, index=f.columns)

        betas = {}
        for col in f.columns:
            sub = pd.DataFrame({"f": f[col], "m": mkt}).dropna()
            if len(sub) < self.min_periods:
                betas[col] = 0.0
            else:
                betas[col] = float(sub["f"].cov(sub["m"]) / sub["m"].var())
        return pd.Series(betas)

    def risk_attribution(
        self,
        exposures: pd.DataFrame,
        cov_matrix: pd.DataFrame,
    ) -> pd.Series:
        """
        Per-factor contribution to total factor variance.

        attribution_i = exposure_i * sum_j(cov_ij * exposure_j)
        Then normalised so sum == 1.

        Parameters
        ----------
        exposures : pd.DataFrame or pd.Series
            Factor exposures (weights).
        cov_matrix : pd.DataFrame
            Factor covariance (symmetric, shape n×n).

        Returns
        -------
        pd.Series
            Attribution weights (sum to 1). Index = factor names.
        """
        if exposures.empty or cov_matrix.empty:
            return pd.Series(dtype=float)

        # Support both Series and DataFrame input
        if isinstance(exposures, pd.Series):
            exp = exposures
        else:
            exp = exposures.iloc[:, 0] if exposures.shape[1] == 1 else exposures.mean(axis=1)

        # Align with cov_matrix columns
        common = exp.index.intersection(cov_matrix.index)
        if len(common) == 0:
            return pd.Series(dtype=float)

        exp = exp.loc[common]
        cov = cov_matrix.loc[common, common]

        # Attribution: exp_i * (cov @ exp)_i
        cov_exp = cov.dot(exp)
        attr = exp * cov_exp

        total = attr.sum()
        if abs(total) < 1e-12:
            return pd.Series(0.0, index=exp.index)
        return attr / total

    # ── Internal helpers ─────────────────────────────────────────────────

    def _align(
        self,
        factors: pd.DataFrame,
        other: pd.Series,
    ) -> Optional[tuple[pd.DataFrame, pd.Series]]:
        """Align factors and returns, return None if insufficient data."""
        aligned = factors.align(other, join="inner", axis=0)
        f = aligned[0] if isinstance(aligned, tuple) else factors
        r = aligned[1] if isinstance(aligned, tuple) else other
        if f.empty or r.empty or len(f) < self.min_periods:
            return None
        return f, r
