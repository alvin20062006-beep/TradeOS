"""
core.research.backtest.engine
===========================
Research-layer portfolio backtest engine.

Provides BacktestEngine: time-loop simulation of portfolio weights.
- Accepts weights_series (from PortfolioOptimizer) + prices + config
- Produces BacktestResult (via BacktestResult.from_series)
- No order/execution fields. No execution-layer dependency.

Boundary: This is NOT the execution-layer backtest engine (Phase 3).
It evaluates whether a weight schedule historically produces returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from core.research.backtest.cost_model import CostModel
from core.research.backtest.result import BacktestResult
from core.research.backtest.schema import BacktestConfig


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class BacktestError(Exception):
    """Base exception for backtest errors."""


class BacktestDataError(BacktestError):
    """Raised when input data is invalid or inconsistent."""


# ─────────────────────────────────────────────────────────────────────────────
# BacktestEngine
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BacktestEngine:
    """
    Research-layer portfolio backtest engine.

    Parameters
    ----------
    weights_series : pd.DataFrame
        Portfolio weights over time.
        index = timestamps, columns = asset_ids.
    prices : pd.DataFrame
        Close prices for assets.
        index = timestamps, columns = asset_ids.
    config : BacktestConfig
        Backtest configuration (from schema.py).
    cost_model : CostModel
        Transaction cost model (default CostModel()).

    Output
    ------
    BacktestResult via BacktestResult.from_series().
    No execution semantics (no Order, Fill, ExecutionReport).
    """

    weights_series: pd.DataFrame
    prices: pd.DataFrame
    config: BacktestConfig
    cost_model: CostModel = field(default_factory=CostModel)

    def __post_init__(self):
        if isinstance(self.weights_series, BacktestConfig):
            config = self.weights_series
            weights = self.prices
            prices = self.config
            self.config = config
            self.weights_series = weights
            self.prices = prices
        if not isinstance(self.config, BacktestConfig):
            raise BacktestDataError("config must be a BacktestConfig instance")
        self._validate_inputs()

    def _validate_inputs(self) -> None:
        if self.weights_series.empty:
            raise BacktestDataError("weights_series is empty")
        if self.prices.empty:
            raise BacktestDataError("prices is empty")
        w_cols = set(self.weights_series.columns)
        p_cols = set(self.prices.columns)
        if w_cols != p_cols:
            raise BacktestDataError(
                f"weights columns {sorted(w_cols)} != prices columns {sorted(p_cols)}"
            )
        w_idx = set(self.weights_series.index)
        p_idx = set(self.prices.index)
        if not w_idx.issubset(p_idx):
            missing = sorted(w_idx - p_idx)
            raise BacktestDataError(f"weights dates not in prices: {missing[:5]}")
        self._prices_aligned = self.prices.loc[self.weights_series.index]

    def run(self, run_id: str | None = None) -> BacktestResult:
        """
        Run the backtest simulation.

        Returns
        -------
        BacktestResult
            Via BacktestResult.from_series(). No execution semantics.
        """
        schedule = self._build_schedule()
        if len(schedule) < 2:
            return BacktestResult.from_series(
                returns=pd.Series(dtype=float),
                gross=pd.Series(dtype=float),
                net=pd.Series(dtype=float),
                positions=pd.DataFrame(dtype=float),
                turnover=pd.Series(dtype=float),
                costs=pd.Series(dtype=float),
                config_dict={"risk_free_rate": self.config.risk_free_rate},
                run_id=run_id,
            )

        equity = self.config.initial_capital
        returns_list: list[float] = []
        gross_list: list[float] = []
        net_list: list[float] = []
        turnover_list: list[float] = []
        costs_list: list[float] = []
        positions_records: list[dict] = []
        dates_used: list = []

        prev_weights: Optional[pd.Series] = None

        for i, date in enumerate(schedule):
            try:
                curr_prices = self._prices_aligned.loc[date]
            except KeyError:
                continue

            curr_weights = self._safe_weights(date)
            if curr_weights.empty:
                continue

            total = curr_weights.abs().sum()
            if total >= 1e-10:
                curr_weights = curr_weights / total
            else:
                curr_weights = curr_weights.astype(float).fillna(0.0)

            positions_records.append(curr_weights.to_dict())
            dates_used.append(date)

            if prev_weights is None:
                prev_weights = curr_weights.copy()
                continue

            # Previous date & prices
            prev_date = schedule[schedule.get_loc(date) - 1]
            try:
                prev_prices = self._prices_aligned.loc[prev_date]
            except KeyError:
                prev_weights = curr_weights.copy()
                continue

            # Asset returns
            with np.errstate(divide="ignore", invalid="ignore"):
                asset_returns = (curr_prices / prev_prices) - 1.0
                asset_returns = asset_returns.fillna(0.0)

            gross_ret = float((curr_weights * asset_returns).sum())

            # Transaction costs
            total_cost, _ = self.cost_model.costs_for_period(
                prev_weights, curr_weights,
                curr_prices, equity,
            )
            net_ret = gross_ret - (total_cost / equity)
            turn = self.cost_model.turnover_rate(prev_weights, curr_weights)

            returns_list.append(net_ret)
            gross_list.append(gross_ret)
            net_list.append(net_ret)
            turnover_list.append(turn)
            costs_list.append(total_cost)

            equity = equity * (1.0 + net_ret)
            prev_weights = curr_weights.copy()

        if not returns_list:
            return BacktestResult.from_series(
                returns=pd.Series(dtype=float),
                gross=pd.Series(dtype=float),
                net=pd.Series(dtype=float),
                positions=pd.DataFrame(dtype=float),
                turnover=pd.Series(dtype=float),
                costs=pd.Series(dtype=float),
                config_dict={"risk_free_rate": self.config.risk_free_rate},
                run_id=run_id,
            )

        idx = pd.DatetimeIndex(dates_used[1:])  # returns start from 2nd date
        returns_s = pd.Series(returns_list, index=idx)
        gross_s = pd.Series(gross_list, index=idx)
        net_s = pd.Series(net_list, index=idx)
        turnover_s = pd.Series(turnover_list, index=idx)
        costs_s = pd.Series(costs_list, index=idx)
        positions_df = pd.DataFrame(positions_records[1:], index=idx)

        return BacktestResult.from_series(
            returns=returns_s,
            gross=gross_s,
            net=net_s,
            positions=positions_df,
            turnover=turnover_s,
            costs=costs_s,
            config_dict={
                "risk_free_rate": self.config.risk_free_rate,
                "initial_capital": self.config.initial_capital,
                "benchmark_weights": self.config.benchmark_weights,
            },
            run_id=run_id,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_schedule(self) -> pd.DatetimeIndex:
        """Build sorted DatetimeIndex of rebalance dates."""
        if self.config.rebalance_freq and self.config.rebalance_freq != "W":
            # Generate schedule from prices index based on freq
            dates = self.prices.index.to_period(self.config.rebalance_freq).to_timestamp()
            dates = dates.unique()
            dates = pd.DatetimeIndex(dates)
        else:
            dates = pd.DatetimeIndex(self.weights_series.index)
        available = pd.DatetimeIndex(self.weights_series.index)
        dates = dates.intersection(available).sort_values().drop_duplicates()
        return dates

    def _safe_weights(self, date) -> pd.Series:
        """Get weights for a date, forward-filling if needed."""
        try:
            return self.weights_series.loc[date]
        except KeyError:
            idx = self.weights_series.index
            past = idx[idx < date]
            if len(past) == 0:
                return pd.Series(dtype=float)
            return self.weights_series.loc[past[-1]]
