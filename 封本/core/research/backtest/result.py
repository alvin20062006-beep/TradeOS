"""
core.research.backtest.result
===========================
Backtest result container.

Provides BacktestResult.from_series() factory and to_dict() serialization.
No execution semantics (Order, Fill, ExecutionReport).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    """
    Output of a single backtest run.

    Attributes
    ----------
    run_id : str
        Unique identifier for this run.
    returns_series : pd.Series
        Net period returns. Index = timestamps.
    gross_returns : pd.Series
        Gross period returns (before costs).
    net_returns : pd.Series
        Net period returns (after costs).
    equity_curve : pd.Series
        Cumulative portfolio value, normalized to start at 1.0.
    positions_series : pd.DataFrame
        Position weights over time. Columns = asset_ids.
    turnover_series : pd.Series
        Per-period turnover rates.
    costs_series : pd.Series
        Per-period total costs.
    metrics : dict[str, float]
        Aggregated performance metrics.
    metadata : dict
        Arbitrary metadata (run_id, n_rebalance_periods, config, etc.).
    config : dict
        Backtest configuration snapshot.
    """

    run_id: str = ""
    returns_series: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    gross_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    net_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    positions_series: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(dtype=float))
    turnover_series: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    costs_series: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, float] = field(default_factory=dict)
    config: dict = field(default_factory=dict)

    @property
    def transaction_cost_series(self) -> pd.Series:
        """Backward-compatible alias used by existing research tests."""
        return self.costs_series

    @classmethod
    def from_series(
        cls,
        returns: pd.Series,
        gross: pd.Series,
        net: pd.Series,
        positions: pd.DataFrame,
        turnover: pd.Series,
        costs: pd.Series,
        config_dict: dict | None = None,
        run_id: str | None = None,
    ) -> "BacktestResult":
        """
        Factory: construct BacktestResult from time-series data.

        Parameters
        ----------
        returns : pd.Series
            Net period returns (index = timestamps).
        gross : pd.Series
            Gross period returns.
        net : pd.Series
            Net period returns (after costs).
        positions : pd.DataFrame
            Position weights (index = timestamps, columns = asset_ids).
        turnover : pd.Series
            Per-period turnover.
        costs : pd.Series
            Per-period costs.
        config_dict : dict, optional
            Configuration snapshot.

        Returns
        -------
        BacktestResult
        """
        # Equity curve: cumulative product, normalized to start at 1.0
        if returns.empty:
            equity = pd.Series(dtype=float)
        else:
            equity = (1.0 + returns).cumprod()
            equity.iloc[0] = 1.0  # normalize start

        metrics = cls._compute_metrics(returns, gross, net, turnover, costs, config_dict)

        run_id = run_id or f"bt_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        metadata = {
            "run_id": run_id,
            "n_rebalance_periods": int(len(returns)),
            **(config_dict or {}),
        }

        return cls(
            run_id=run_id,
            returns_series=returns,
            gross_returns=gross,
            net_returns=net,
            equity_curve=equity,
            positions_series=positions,
            turnover_series=turnover,
            costs_series=costs,
            metrics=metrics,
            metadata=metadata,
            config=config_dict or {},
        )

    @staticmethod
    def _compute_metrics(
        returns: pd.Series,
        gross: pd.Series,
        net: pd.Series,
        turnover: pd.Series,
        costs: pd.Series,
        config_dict: dict | None = None,
    ) -> dict[str, float]:
        """Compute performance metrics from time-series."""
        metrics: dict[str, float] = {}
        risk_free = (config_dict or {}).get("risk_free_rate", 0.0)

        if returns.empty:
            return {
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "annualized_volatility": 0.0,
                "total_cost": 0.0,
                "total_transaction_cost": 0.0,
                "avg_turnover": 0.0,
            }

        # Total return
        metrics["total_return"] = round(float((1.0 + returns).prod() - 1.0), 8)

        # Annualized volatility (assume daily, 252 days/year)
        n = len(returns)
        periods_per_year = 252
        vol = float(returns.std() * np.sqrt(periods_per_year))
        metrics["annualized_volatility"] = round(vol, 8)

        # Sharpe ratio
        excess = returns.mean() - risk_free / periods_per_year
        if vol > 1e-10:
            metrics["sharpe_ratio"] = round(float(excess / returns.std() * np.sqrt(periods_per_year)), 8)
        else:
            metrics["sharpe_ratio"] = 0.0

        # Max drawdown
        cum = (1.0 + returns).cumprod()
        running_max = cum.cummax()
        drawdown = (cum - running_max) / running_max
        metrics["max_drawdown"] = round(float(drawdown.min()), 8)

        # Win rate
        metrics["win_rate"] = round(float((returns > 0).sum() / n), 8) if n > 0 else 0.0

        # Cost metrics
        total_cost = round(float(costs.sum()), 4) if not costs.empty else 0.0
        metrics["total_cost"] = total_cost
        metrics["total_transaction_cost"] = total_cost
        metrics["avg_turnover"] = round(float(turnover.mean()), 8) if not turnover.empty else 0.0

        return metrics

    def to_dict(self) -> dict:
        """Serialize to dict for JSON logging / experiment records."""
        def _series_to_list(s: pd.Series) -> list:
            if s.empty:
                return []
            return [(str(idx), float(val)) for idx, val in s.items()]

        def _df_to_list(df: pd.DataFrame) -> list:
            if df.empty:
                return []
            return [
                {str(idx): {str(c): float(v) for c, v in row.items()}}
                for idx, row in df.iterrows()
            ]

        return {
            "run_id": self.run_id,
            "returns_series": _series_to_list(self.returns_series),
            "equity_curve": _series_to_list(self.equity_curve),
            "positions_series": _df_to_list(self.positions_series),
            "metrics": self.metrics,
            "metadata": self.metadata,
        }
