"""
core.research.backtest.evaluator
============================
Bridge between BacktestResult and existing evaluation metrics.

- Wraps core.research.evaluation.EvaluationMetrics (prediction-level)
- Wraps core.research.alpha.evaluation.FactorMetrics (factor-level)
- Produces structured BacktestEvaluationReport

No execution semantics. No execution-layer dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from core.research.backtest.result import BacktestResult
from core.research.evaluation.metrics import EvaluationMetrics
from core.research.alpha.evaluation.metrics import FactorMetricsBundle, FactorMetrics


@dataclass
class BacktestEvaluationReport:
    """
    Structured evaluation report combining portfolio + factor metrics.

    Attributes
    ----------
    backtest_metrics : dict[str, float]
        Portfolio-level metrics from BacktestResult.
    factor_metrics : FactorMetricsBundle | None
        Factor-level metrics (if factors were provided).
    evaluator_config : dict
        Configuration used for this evaluation.
    evaluated_at : datetime
        Evaluation timestamp.
    """

    backtest_metrics: dict[str, float] = field(default_factory=dict)
    factor_metrics: Optional[FactorMetricsBundle] = None
    evaluator_config: dict = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Serialize to dict for logging."""
        result = {
            "backtest_metrics": self.backtest_metrics,
            "evaluator_config": self.evaluator_config,
            "evaluated_at": self.evaluated_at.isoformat(),
        }
        if self.factor_metrics is not None:
            result["factor_metrics"] = {
                "best_factor": self.factor_metrics.best_factor,
                "ic_summary": (
                    self.factor_metrics.ic_summary().to_dict()
                    if not self.factor_metrics.ic_summary().empty
                    else {}
                ),
            }
        return result


class BacktestEvaluator:
    """
    Evaluates BacktestResult using existing EvaluationMetrics.

    Parameters
    ----------
    risk_free_rate : float
        Annualized risk-free rate (default 0.0).
    periods_per_year : int
        Number of periods per year for annualization (default 252).
    """

    def __init__(self, risk_free_rate: float = 0.0, periods_per_year: int = 252):
        self.risk_free_rate = risk_free_rate
        self.periods_per_year = periods_per_year
        self._evaluator = EvaluationMetrics(risk_free_rate=risk_free_rate)

    def evaluate(
        self,
        result: BacktestResult,
        predictions: Optional[pd.Series] = None,
        labels: Optional[pd.Series] = None,
        factor_dict: Optional[dict[str, pd.Series]] = None,
    ) -> dict[str, float]:
        """
        Evaluate a BacktestResult.

        Parameters
        ----------
        result : BacktestResult
            Backtest output to evaluate.
        predictions : pd.Series, optional
            Alpha predictions, index = timestamps or asset_ids.
            Used to compute IC / RankIC.
        labels : pd.Series, optional
            Realized returns, index = timestamps or asset_ids.
            Used to compute IC alongside predictions.
        factor_dict : dict[str, pd.Series], optional
            Named factor series for FactorMetrics.
            key = factor name, value = factor values.

        Returns
        -------
        dict[str, float]
            Flat metric dictionary for product/test consumption.
        """
        # Portfolio metrics (already computed in BacktestEngine)
        portfolio_metrics = dict(result.metrics)

        # Enrich with EvaluationMetrics if returns are available
        if result.returns_series is not None and not result.returns_series.empty:
            returns = result.returns_series.dropna()
            if len(returns) > 0:
                # Sharpe via evaluator
                portfolio_metrics["sharpe_evaluator"] = round(
                    self._evaluator.sharpe(returns, self.periods_per_year), 6
                )
                # Max drawdown via evaluator
                portfolio_metrics["max_drawdown_evaluator"] = round(
                    self._evaluator.max_drawdown(returns), 6
                )
                # Hit rate via evaluator
                if predictions is not None and labels is not None:
                    aligned = self._align_series(predictions, labels)
                    if len(aligned) > 0:
                        portfolio_metrics["ic"] = round(
                            self._evaluator.ic(aligned["pred"], aligned["label"]), 6
                        )
                        portfolio_metrics["rank_ic"] = round(
                            self._evaluator.rank_ic(aligned["pred"], aligned["label"]), 6
                        )
                        portfolio_metrics["hit_rate"] = round(
                            self._evaluator.hit_rate(aligned["pred"], aligned["label"]), 6
                        )

        # Factor metrics
        factor_bundle: Optional[FactorMetricsBundle] = None
        if factor_dict:
            factor_bundle = FactorMetricsBundle()
            for name, series in factor_dict.items():
                if labels is not None:
                    fm = FactorMetrics.compute(
                        factor=series,
                        labels=labels,
                        factor_name=name,
                    )
                    factor_bundle.add(fm)

        metrics = {f"bt_{key}": value for key, value in portfolio_metrics.items()}
        benchmark_weights = (result.config or {}).get("benchmark_weights")
        if benchmark_weights:
            returns = result.returns_series.dropna() if result.returns_series is not None else pd.Series(dtype=float)
            if len(returns) > 1:
                tracking_error = float(returns.std() * (self.periods_per_year ** 0.5))
                info_ratio = float(returns.mean() / returns.std() * (self.periods_per_year ** 0.5)) if returns.std() > 1e-10 else 0.0
            else:
                tracking_error = 0.0
                info_ratio = 0.0
            metrics["rel_tracking_error"] = round(tracking_error, 6)
            metrics["rel_information_ratio"] = round(info_ratio, 6)
        if factor_bundle is not None:
            metrics["factor_count"] = len(factor_bundle.metrics)
        return metrics

    def summary(self, result: BacktestResult) -> pd.Series:
        metrics = self.evaluate(result)
        rows = {
            "Total Return": metrics.get("bt_total_return", 0.0),
            "Sharpe Ratio": metrics.get("bt_sharpe_ratio", 0.0),
            "Max Drawdown": metrics.get("bt_max_drawdown", 0.0),
            "Average Turnover": metrics.get("bt_avg_turnover", 0.0),
        }
        if "rel_tracking_error" in metrics:
            rows["Tracking Error"] = metrics["rel_tracking_error"]
        if "rel_information_ratio" in metrics:
            rows["Information Ratio"] = metrics["rel_information_ratio"]
        return pd.Series(rows)

    @staticmethod
    def _align_series(
        a: pd.Series,
        b: pd.Series,
    ) -> pd.DataFrame:
        """Align two series by index for metric computation."""
        df = pd.DataFrame({"a": a, "b": b}).dropna()
        if df.empty:
            return df
        df.columns = ["pred", "label"]
        return df
