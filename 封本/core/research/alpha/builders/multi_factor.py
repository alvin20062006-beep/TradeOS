"""
core.research.alpha.builders.multi_factor
========================================
Multi-factor combination: weighted aggregation of individual factors.

Responsibilities
----------------
- equal_weighted: simple average of all factors
- ic_weighted: weights proportional to IC mean
- ir_weighted: weights proportional to IC / IC_std
- pca_weighted: PCA principal component weights
- combine(): unified entry point

Constraints
-----------
- Research-layer output only (pd.Series of composite factor scores)
- No execution-layer fields
- No portfolio optimization (deferred to Batch 4B)
- No factor selection (deferred to FactorSelector)
"""

from __future__ import annotations

from typing import Literal, Optional

import numpy as np
import pandas as pd


class MultiFactorBuilder:
    """
    Combine multiple factors into a single composite signal.

    Parameters
    ----------
    handle_neg_ic : bool
        If True, negative IC weights are zeroed out (default True).
        Set False to allow short exposure on weak factors.
    """

    def __init__(self, handle_neg_ic: bool = True):
        self.handle_neg_ic = handle_neg_ic

    # ── Weighting methods ───────────────────────────────────────────────────

    def equal_weighted(self, factors: pd.DataFrame) -> pd.Series:
        """
        Simple equal-weight average of all factors.

        Each factor receives weight 1/n_factors regardless of IC.

        Returns
        -------
        pd.Series
            Index = factor index, values = composite scores.
        """
        if factors.empty:
            return pd.Series(dtype=float)
        if len(factors.shape) == 1:
            return factors
        return factors.mean(axis=1)

    def ic_weighted(
        self,
        factors: pd.DataFrame,
        labels: pd.Series,
    ) -> pd.Series:
        """
        Weight factors by IC mean.

        Weight_i = max(IC_i, 0) / sum(max(IC_j, 0))  if handle_neg_ic
        Weight_i = IC_i / sum(|IC_j|)                 if handle_neg_ic=False

        Parameters
        ----------
        factors : pd.DataFrame
            Columns = factor names, index = timestamps.
        labels : pd.Series
            Forward returns aligned with factors index.

        Returns
        -------
        pd.Series
            IC-weighted composite factor scores.
        """
        if factors.empty:
            return pd.Series(dtype=float)

        ic_scores = self._ic_series_dict(factors, labels)
        if not ic_scores:
            return self.equal_weighted(factors)

        ic_vals = np.array(list(ic_scores.values()))
        names = list(ic_scores.keys())

        if self.handle_neg_ic:
            ic_vals = np.maximum(ic_vals, 0.0)
        else:
            ic_vals = np.abs(ic_vals)

        total = ic_vals.sum()
        if total < 1e-10:
            return self.equal_weighted(factors)

        weights = dict(zip(names, ic_vals / total))
        result = pd.Series(0.0, index=factors.index)
        for name, w in weights.items():
            result += factors[name] * w

        return result

    def ir_weighted(
        self,
        factors: pd.DataFrame,
        labels: pd.Series,
    ) -> pd.Series:
        """
        Weight factors by Information Ratio (IC_mean / IC_std).

        Weight_i = max(IR_i, 0) / sum(max(IR_j, 0))

        Parameters
        ----------
        factors : pd.DataFrame
            Columns = factor names, index = timestamps.
        labels : pd.Series
            Forward returns.

        Returns
        -------
        pd.Series
            IR-weighted composite factor scores.
        """
        if factors.empty:
            return pd.Series(dtype=float)

        ir_scores = self._ir_series_dict(factors, labels)
        if not ir_scores:
            return self.equal_weighted(factors)

        ir_vals = np.array([max(v, 0.0) for v in ir_scores.values()])
        names = list(ir_scores.keys())

        total = ir_vals.sum()
        if total < 1e-10:
            return self.equal_weighted(factors)

        weights = dict(zip(names, ir_vals / total))
        result = pd.Series(0.0, index=factors.index)
        for name, w in weights.items():
            result += factors[name] * w

        return result

    def pca_weighted(
        self,
        factors: pd.DataFrame,
        n_components: Optional[int] = None,
    ) -> pd.Series:
        """
        Weight factors by PCA first principal component loadings.

        Falls back to equal_weighted if sklearn is unavailable or
        factor count < 2.

        Parameters
        ----------
        factors : pd.DataFrame
            Columns = factor names, index = timestamps.
        n_components : int, optional
            Number of PCA components. Defaults to 1.

        Returns
        -------
        pd.Series
            PCA-weighted composite factor scores.
        """
        if factors.empty:
            return pd.Series(dtype=float)
        if len(factors.columns) < 2:
            return factors.iloc[:, 0] if factors.shape[1] == 1 else self.equal_weighted(factors)

        n_components = n_components or 1
        try:
            from sklearn.decomposition import PCA
        except ImportError:
            return self.equal_weighted(factors)

        X = factors.dropna()
        if X.shape[0] < 3 or X.shape[1] < 2:
            return self.equal_weighted(factors)

        try:
            pca = PCA(n_components=min(n_components, X.shape[1]))
            pca.fit(X)
            loadings = pca.components_[0]
            # Flip negative loadings to keep positive direction
            if loadings.sum() < 0:
                loadings = -loadings
            loadings = np.maximum(loadings, 0.0)
            total = loadings.sum()
            if total < 1e-10:
                return self.equal_weighted(factors)
            weights = dict(zip(X.columns, loadings / total))
            result = pd.Series(0.0, index=X.index)
            for name, w in weights.items():
                result += X[name] * w
            # Reindex back to original index (fill missing with 0)
            out = pd.Series(0.0, index=factors.index)
            out.loc[result.index] = result
            return out
        except Exception:
            return self.equal_weighted(factors)

    # ── Main entry point ──────────────────────────────────────────────────

    def combine(
        self,
        factors: pd.DataFrame,
        method: Literal["equal", "ic", "ir", "pca"] = "ic",
        labels: Optional[pd.Series] = None,
        **kwargs,
    ) -> pd.Series:
        """
        Unified entry point for factor combination.

        Parameters
        ----------
        factors : pd.DataFrame
            Candidate factor columns.
        method : str
            Combination method: "equal" | "ic" | "ir" | "pca".
        labels : pd.Series, optional
            Required for "ic" and "ir" methods.
        kwargs : dict
            Passed to the underlying method (e.g., n_components for "pca").

        Returns
        -------
        pd.Series
            Composite factor scores (research-layer).
        """
        if factors.empty:
            return pd.Series(dtype=float)

        if method == "equal":
            return self.equal_weighted(factors)
        elif method == "ic":
            if labels is None:
                raise ValueError("labels required for method='ic'")
            return self.ic_weighted(factors, labels)
        elif method == "ir":
            if labels is None:
                raise ValueError("labels required for method='ir'")
            return self.ir_weighted(factors, labels)
        elif method == "pca":
            return self.pca_weighted(factors, **kwargs)
        else:
            raise ValueError(f"Unknown combination method: {method!r}")

    # ── Internal helpers ─────────────────────────────────────────────────

    def _ic_series_dict(
        self,
        factors: pd.DataFrame,
        labels: pd.Series,
        min_periods: int = 3,
    ) -> dict[str, float]:
        """Compute per-factor IC mean over the full aligned window."""
        scores: dict[str, float] = {}
        for col in factors.columns:
            sub = pd.DataFrame({"f": factors[col], "l": labels}).dropna()
            if len(sub) < min_periods:
                continue
            ic = float(sub["f"].corr(sub["l"]))
            if not np.isnan(ic):
                scores[col] = ic
        return scores

    def _ir_series_dict(
        self,
        factors: pd.DataFrame,
        labels: pd.Series,
        rolling_window: int = 20,
    ) -> dict[str, float]:
        """Compute per-factor IR (IC_mean / IC_std) over rolling IC series."""
        scores: dict[str, float] = {}
        for col in factors.columns:
            sub = pd.DataFrame({"f": factors[col], "l": labels}).dropna()
            if len(sub) < max(rolling_window, 5):
                continue
            ic_roll = sub["f"].rolling(rolling_window).corr(sub["l"]).dropna()
            if len(ic_roll) < 2 or ic_roll.std() < 1e-8:
                continue
            ir = ic_roll.mean() / ic_roll.std()
            if not np.isnan(ir):
                scores[col] = ir
        return scores
