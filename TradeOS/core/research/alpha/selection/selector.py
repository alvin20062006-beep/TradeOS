"""
core.research.alpha.selection.selector
=====================================
Factor selection and pruning.

Responsibilities
----------------
- best_k: select top-k factors by IC/IR
- correlation_prune: remove highly correlated redundant factors
- ic_threshold / ir_threshold: filter factors below minimum thresholds
- select(): composite strategy using the above primitives

Constraints
-----------
- Research-layer only: returns factor names, NOT portfolio weights
- No execution-layer fields (order_type, position, exec_algo, etc.)
- No portfolio optimization (deferred to Batch 4B)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


class FactorSelector:
    """
    Selects and prunes candidate factors based on IC / IR criteria.

    Parameters
    ----------
    min_ic : float
        Minimum IC threshold (inclusive). Factors with IC < min_ic are filtered.
    min_ir : float
        Minimum IC-IR threshold. Factors with IR < min_ir are filtered.
    corr_threshold : float
        Correlation threshold. When two factors have abs(corr) >= threshold,
        the one with lower IC is dropped.
    """

    def __init__(
        self,
        min_ic: float = 0.02,
        min_ir: float = 0.3,
        corr_threshold: float = 0.9,
    ):
        if not (0.0 <= corr_threshold <= 1.0):
            raise ValueError(f"corr_threshold must be in [0, 1], got {corr_threshold}")
        self.min_ic = min_ic
        self.min_ir = min_ir
        self.corr_threshold = corr_threshold

    # ── Primitive methods ────────────────────────────────────────────────────

    def best_k(
        self,
        factors: pd.DataFrame,
        labels: pd.Series,
        k: int,
        metric: str = "ic_mean",
    ) -> list[str]:
        """
        Select top-k factors ranked by IC mean.

        Parameters
        ----------
        factors : pd.DataFrame
            Columns = factor names, index = timestamps.
        labels : pd.Series
            Forward returns. Index must align with factors.
        k : int
            Number of factors to return. If k > n_candidates, returns all.
        metric : str
            Sort key: "ic_mean" (default) or "ir".

        Returns
        -------
        list[str]
            Names of selected factors (k or fewer).
        """
        if factors.empty or labels.empty:
            return list(factors.columns[:k]) if k > 0 and len(factors.columns) > 0 else []

        aligned = factors.align(labels, join="inner", axis=0)
        f_aligned = aligned[0] if isinstance(aligned, tuple) else factors.loc[labels.index]
        l_aligned = aligned[1] if isinstance(aligned, tuple) else labels.loc[factors.index]

        scores = {}
        for col in f_aligned.columns:
            sub = pd.DataFrame({"f": f_aligned[col], "l": l_aligned}).dropna()
            if len(sub) < 3:
                scores[col] = 0.0
                continue
            ic = float(sub["f"].corr(sub["l"]))
            if metric == "ir" and sub["f"].std() > 0:
                ir = ic / sub["f"].std()
                scores[col] = ir
            else:
                scores[col] = ic

        sorted_factors = sorted(scores, key=scores.__getitem__, reverse=True)
        return sorted_factors[:k]

    def correlation_prune(
        self,
        factors: pd.DataFrame,
        threshold: Optional[float] = None,
    ) -> list[str]:
        """
        Remove highly correlated redundant factors.

        Parameters
        ----------
        factors : pd.DataFrame
            Columns = factor names.
        threshold : float, optional
            Correlation threshold. Defaults to self.corr_threshold.

        Returns
        -------
        list[str]
            Names of factors that survive pruning.
        """
        threshold = threshold if threshold is not None else self.corr_threshold
        if factors.empty or len(factors.columns) <= 1:
            return list(factors.columns)

        corr = factors.corr().copy()
        corr_values = corr.to_numpy(copy=True)
        np.fill_diagonal(corr_values, 0.0)
        corr.iloc[:, :] = corr_values

        kept: list[str] = []
        dropped: set[str] = set()

        for col in corr.columns:
            if col in dropped:
                continue
            kept.append(col)
            # Drop all factors with |corr| >= threshold to this one
            for other, val in corr[col].items():
                if other not in dropped and abs(val) >= threshold:
                    dropped.add(other)

        return kept

    def ic_threshold(
        self,
        factors: pd.DataFrame,
        labels: pd.Series,
        min_ic: Optional[float] = None,
    ) -> list[str]:
        """
        Filter factors below minimum IC threshold.

        Returns
        -------
        list[str]
            Names of factors with |IC| >= min_ic.
        """
        min_ic = min_ic if min_ic is not None else self.min_ic
        if factors.empty or labels.empty:
            return []

        scores = {}
        for col in factors.columns:
            sub = pd.DataFrame({"f": factors[col], "l": labels}).dropna()
            if len(sub) < 3:
                continue
            scores[col] = abs(float(sub["f"].corr(sub["l"])))

        return [k for k, v in scores.items() if v >= min_ic]

    def ir_threshold(
        self,
        factors: pd.DataFrame,
        labels: pd.Series,
        min_ir: Optional[float] = None,
    ) -> list[str]:
        """
        Filter factors below minimum IC-IR threshold.

        IR = IC_mean / IC_std.

        Returns
        -------
        list[str]
            Names of factors with IR >= min_ir.
        """
        min_ir = min_ir if min_ir is not None else self.min_ir
        if factors.empty or labels.empty:
            return []

        scores = {}
        for col in factors.columns:
            sub = pd.DataFrame({"f": factors[col], "l": labels}).dropna()
            if len(sub) < 5:
                continue
            ic_vals = sub["f"].rolling(5).corr(sub["l"]).dropna()
            if len(ic_vals) < 2:
                continue
            ic_mean = ic_vals.mean()
            ic_std = ic_vals.std()
            if ic_std > 1e-8:
                scores[col] = ic_mean / ic_std

        return [k for k, v in scores.items() if v >= min_ir]

    # ── Composite selection ─────────────────────────────────────────────────

    def select(
        self,
        factors: pd.DataFrame,
        labels: pd.Series,
        strategy: str = "ic_ir",
    ) -> list[str]:
        """
        Composite factor selection strategy.

        Parameters
        ----------
        factors : pd.DataFrame
            Candidate factors.
        labels : pd.Series
            Forward returns.
        strategy : str
            - "ic_ir": ic_threshold → correlation_prune → ir_threshold → best_k(5)
            - "corr_ic": correlation_prune → ic_threshold
            - "best_only": best_k(5)

        Returns
        -------
        list[str]
            Selected factor names (may be empty).
        """
        if factors.empty:
            return []

        selected: list[str] = list(factors.columns)

        # Step 1: IC threshold
        selected = [f for f in selected if f in self.ic_threshold(factors[selected], labels)]
        if len(selected) <= 1:
            return selected

        # Step 2: correlation prune
        selected = self.correlation_prune(factors[selected], self.corr_threshold)
        if len(selected) <= 1:
            return selected

        # Strategy branches
        if strategy == "ic_ir":
            # Step 3: IR threshold
            selected = [f for f in selected if f in self.ir_threshold(factors[selected], labels)]
            if len(selected) <= 1:
                return selected
            # Step 4: best 5
            selected = self.best_k(factors[selected], labels, k=5)
        elif strategy == "corr_ic":
            selected = [f for f in selected if f in self.ic_threshold(factors[selected], labels)]
        elif strategy == "best_only":
            selected = self.best_k(factors[selected], labels, k=5)
        else:
            raise ValueError(f"Unknown strategy: {strategy!r}")

        return selected
