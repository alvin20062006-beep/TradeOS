"""
EvaluationMetrics
=================
Computes research evaluation metrics:
    IC, RankIC, Sharpe, MaxDrawdown, HitRate, Calmar, Turnover
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


class EvaluationMetrics:
    """
    Compute evaluation metrics for backtest results.

    Parameters
    ----------
    risk_free_rate : float
        Annualized risk-free rate (default 0.0).
    """

    def __init__(self, risk_free_rate: float = 0.0):
        self.risk_free_rate = risk_free_rate

    def ic(self, predictions: pd.Series, labels: pd.Series) -> float:
        """
        Pearson Information Coefficient.
        Correlation between predictions and realized returns.
        """
        aligned = pd.DataFrame({"pred": predictions, "label": labels}).dropna()
        if len(aligned) < 3:
            return 0.0
        return float(aligned["pred"].corr(aligned["label"]))

    def rank_ic(self, predictions: pd.Series, labels: pd.Series) -> float:
        """
        Rank Information Coefficient (Spearman).
        Rank correlation between predictions and realized returns.
        Falls back to pandas built-in when scipy is unavailable.
        """
        aligned = pd.DataFrame({"pred": predictions, "label": labels}).dropna()
        if len(aligned) < 3:
            return 0.0
        try:
            return float(aligned["pred"].corr(aligned["label"], method="spearman"))
        except (TypeError, ImportError):
            # Fallback: manual Spearman via rank transform
            pred_rank = aligned["pred"].rank()
            label_rank = aligned["label"].rank()
            if pred_rank.std() == 0 or label_rank.std() == 0:
                return 0.0
            return float(pred_rank.corr(label_rank))

    def sharpe(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """
        Annualized Sharpe Ratio.
        """
        if returns.std() == 0 or np.isnan(returns.std()):
            return 0.0
        excess = returns - self.risk_free_rate / periods_per_year
        return float(excess.mean() / returns.std() * np.sqrt(periods_per_year))

    def max_drawdown(self, returns: pd.Series) -> float:
        """
        Maximum drawdown (most negative cumulative peak-to-trough).
        Returns a positive number representing the max % drawdown.
        """
        cumulative = (1 + returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        return float(abs(drawdown.min()))

    def hit_rate(self, predictions: pd.Series, labels: pd.Series) -> float:
        """
        Hit rate: fraction of correct directional predictions.
        """
        aligned = pd.DataFrame({"pred": predictions, "label": labels}).dropna()
        if len(aligned) == 0:
            return 0.0
        correct = (aligned["pred"] * aligned["label"]) > 0
        return float(correct.mean())

    def calmar(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """
        Calmar Ratio: annualized return / max drawdown.
        """
        mdd = self.max_drawdown(returns)
        if mdd == 0:
            return 0.0
        annual_return = returns.mean() * periods_per_year
        return float(annual_return / mdd)

    def turnover(
        self,
        positions: pd.DataFrame,
        positions_next: Optional[pd.DataFrame] = None,
    ) -> Optional[float]:
        """
        Compute portfolio turnover rate.

        Parameters
        ----------
        positions : pd.DataFrame
            DataFrame of positions per period.
        positions_next : pd.DataFrame, optional
            Next period positions. If None, uses positions.shift(-1).
        """
        if positions_next is None:
            positions_next = positions.shift(-1)
        diff = (positions_next - positions).abs()
        return float(diff.sum(axis=1).mean()) if not diff.empty else None

    def compute_all(
        self,
        predictions: pd.Series,
        labels: pd.Series,
        returns: pd.Series,
    ) -> dict[str, float]:
        """
        Compute all available metrics in one call.

        Returns
        -------
        dict[str, float]
            Keys: ic, rank_ic, sharpe, max_drawdown, hit_rate, calmar
        """
        return {
            "ic": self.ic(predictions, labels),
            "rank_ic": self.rank_ic(predictions, labels),
            "sharpe": self.sharpe(returns),
            "max_drawdown": self.max_drawdown(returns),
            "hit_rate": self.hit_rate(predictions, labels),
            "calmar": self.calmar(returns),
        }
