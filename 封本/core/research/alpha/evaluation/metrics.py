"""
core.research.alpha.evaluation.metrics
====================================
Factor-level evaluation metrics.

Extends core.research.evaluation.EvaluationMetrics (prediction-level IC/Sharpe)
with factor-level IC time series, IR, group IC, and turnover.

Responsibilities
----------------
- FactorMetrics: per-factor IC/IR/group IC/turnover
- FactorMetricsBundle: aggregate metrics across multiple factors

Constraints
-----------
- Research-layer only (no backtest engine)
- No execution-layer fields
- No performance attribution requiring execution assumptions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class FactorMetrics:
    """
    Factor-level evaluation metrics for a single factor.

    Attributes
    ----------
    ic_series : pd.Series or None
        Rolling IC (Pearson) time series. Index = timestamps.
    ic_mean : float
        Mean of ic_series.
    ic_std : float
        Std of ic_series.
    information_ratio : float
        IC_mean / IC_std (IR). 0.0 if ic_std == 0.
    group_ic_dict : dict[int, pd.Series] or None
        Group-wise IC series keyed by group number (0 to n_groups-1).
    turnover_series : pd.Series or None
        Turnover rate series (absolute rank change / 2). Non-negative.
    factor_name : str
        Identifier for this factor.
    """

    factor_name: str
    ic_series: Optional[pd.Series] = None
    ic_mean: float = 0.0
    ic_std: float = 0.0
    information_ratio: float = 0.0
    group_ic_dict: Optional[dict[int, pd.Series]] = None
    turnover_series: Optional[pd.Series] = None

    @classmethod
    def compute(
        cls,
        factor: pd.Series,
        labels: pd.Series,
        factor_name: str = "factor",
        n_groups: int = 5,
        rolling_ic_window: int = 20,
    ) -> "FactorMetrics":
        """
        Compute all factor metrics from a single factor and label series.

        Parameters
        ----------
        factor : pd.Series
            Factor values.
        labels : pd.Series
            Forward returns.
        factor_name : str
            Label for this factor.
        n_groups : int
            Number of quantile groups for group IC.
        rolling_ic_window : int
            Window for rolling IC computation.

        Returns
        -------
        FactorMetrics
        """
        aligned = pd.DataFrame({"factor": factor, "label": labels}).dropna()
        if len(aligned) < 3:
            return cls(factor_name=factor_name)

        ic_roll = (
            aligned["factor"]
            .rolling(rolling_ic_window)
            .corr(aligned["label"])
            .dropna()
        )
        ic_mean = float(ic_roll.mean()) if len(ic_roll) > 0 else 0.0
        ic_std = float(ic_roll.std()) if len(ic_roll) > 0 else 0.0
        ir = ic_mean / ic_std if ic_std > 1e-8 else 0.0

        # Group IC
        group_ic_dict: Optional[dict[int, pd.Series]] = None
        if len(aligned) >= n_groups:
            try:
                quantile_labels = pd.qcut(aligned["factor"], q=n_groups, labels=False, duplicates="drop")
                group_ic_dict = {}
                for g in quantile_labels.unique():
                    mask = quantile_labels == g
                    sub_ic = (
                        aligned.loc[mask, "factor"]
                        .rolling(rolling_ic_window)
                        .corr(aligned.loc[mask, "label"])
                        .dropna()
                    )
                    if len(sub_ic) > 0:
                        group_ic_dict[int(g)] = sub_ic
            except Exception:
                pass

        # Turnover: absolute rank change between consecutive periods
        turnover = cls._compute_turnover(factor)

        return cls(
            factor_name=factor_name,
            ic_series=ic_roll,
            ic_mean=ic_mean,
            ic_std=ic_std,
            information_ratio=ir,
            group_ic_dict=group_ic_dict,
            turnover_series=turnover,
        )

    @staticmethod
    def _compute_turnover(factor: pd.Series) -> pd.Series:
        """
        Rank-based turnover: mean absolute rank change scaled to [0, 2].

        turnover_t = mean(|rank_t - rank_{t-1}|) / n_assets
        Max value ≈ 2.0 for completely reversed portfolios.
        """
        if len(factor) < 2:
            return pd.Series(dtype=float)
        rank = factor.rank()
        diff = rank.diff().abs()
        # Scale by number of unique ranks
        n_ranks = factor.nunique()
        scale = n_ranks if n_ranks > 1 else 2.0
        return diff / scale

    def as_dict(self) -> dict:
        """Serialize to dict for logging / experiment records."""
        return {
            "factor_name": self.factor_name,
            "ic_mean": round(self.ic_mean, 6),
            "ic_std": round(self.ic_std, 6),
            "information_ratio": round(self.information_ratio, 6),
            "n_ic_observations": len(self.ic_series) if self.ic_series is not None else 0,
            "n_groups": len(self.group_ic_dict) if self.group_ic_dict else 0,
        }


@dataclass
class FactorMetricsBundle:
    """
    Aggregate metrics across multiple factors.

    Attributes
    ----------
    factor_metrics : dict[str, FactorMetrics]
        Per-factor FactorMetrics objects.
    best_factor : str or None
        Factor with highest IR (or IC_mean if IR unavailable).
    """

    factor_metrics: dict[str, FactorMetrics] = field(default_factory=dict)
    best_factor: Optional[str] = None

    def add(self, metrics: FactorMetrics) -> None:
        """Register a FactorMetrics object."""
        self.factor_metrics[metrics.factor_name] = metrics
        self._recompute_best()

    def _recompute_best(self) -> None:
        """Update best_factor based on highest IR."""
        if not self.factor_metrics:
            self.best_factor = None
            return
        scores = {
            name: m.information_ratio if m.information_ratio != 0 else m.ic_mean
            for name, m in self.factor_metrics.items()
        }
        self.best_factor = max(scores, key=scores.get)  # type: ignore[arg-type]

    def ic_summary(self) -> pd.DataFrame:
        """
        Summary table of IC/IR metrics across all factors.

        Returns
        -------
        pd.DataFrame
            Columns: ic_mean, ic_std, information_ratio, n_groups.
            Index: factor names.
        """
        rows = []
        for name, m in self.factor_metrics.items():
            rows.append(
                {
                    "ic_mean": m.ic_mean,
                    "ic_std": m.ic_std,
                    "information_ratio": m.information_ratio,
                    "n_groups": len(m.group_ic_dict) if m.group_ic_dict else 0,
                    "turnover_mean": (
                        float(m.turnover_series.mean()) if m.turnover_series is not None else None
                    ),
                }
            )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, index=list(self.factor_metrics.keys()))
        return df.sort_values("information_ratio", ascending=False)

    def top_factors(self, n: int = 5) -> list[str]:
        """
        Return top-n factors by IR (or IC_mean).

        Returns
        -------
        list[str]
            Factor names.
        """
        summary = self.ic_summary()
        if summary.empty:
            return []
        return list(summary.index[:n])
