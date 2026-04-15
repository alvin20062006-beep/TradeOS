"""
core.research.backtest.cost_model
===============================
Simplified transaction cost model.

Accepts CostModelConfig (Pydantic) for configuration.
Provides cost_for_trade, turnover_rate, costs_for_period.

No order-book / depth simulation (Phase 3 execution layer handles that).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from core.research.backtest.schema import CostModelConfig


@dataclass
class CostModel:
    """
    Simplified transaction cost model.

    Parameters
    ----------
    config : CostModelConfig | None
        Pydantic cost model configuration.
        If None, defaults to CostModelConfig() (fixed_bps=5.0).

    Notes
    -----
    - Commission + slippage are combined: total_bps = fixed_bps + slippage_bps
    - Both buy and sell incur the same cost (no bid-ask asymmetry)
    - For research-layer only: not a replacement for the execution layer's
      cost simulation
    """

    config: Optional["CostModelConfig"] = None

    def __post_init__(self):
        if self.config is None:
            from core.research.backtest.schema import CostModelConfig
            self.config = CostModelConfig()

    def cost_for_trade(self, notional: float) -> float:
        """
        Total one-way cost in absolute currency units for a single trade.

        Parameters
        ----------
        notional : float
            Trade notional in currency units.

        Returns
        -------
        float
            max(fixed_bps + slippage_bps) * notional / 10000, min_cost)
        """
        return self.config.total_cost_absolute(notional)

    def turnover_rate(self, prev_weights: pd.Series, new_weights: pd.Series) -> float:
        """
        One-way turnover rate: 0.5 * Σ|w_new - w_old|.

        Parameters
        ----------
        prev_weights : pd.Series
            Previous portfolio weights (index = asset_ids).
        new_weights : pd.Series
            New portfolio weights (index = asset_ids).

        Returns
        -------
        float
            One-way turnover rate.
        """
        aligned = new_weights.align(prev_weights, join="outer", fill_value=0.0)
        delta = (aligned[0] - aligned[1]).abs()
        return float(0.5 * delta.sum())

    def costs_for_period(
        self,
        prev_weights: pd.Series,
        new_weights: pd.Series,
        prices: pd.Series,
        capital: float,
    ) -> tuple[float, dict[str, float]]:
        """
        Compute total cost and per-asset costs for a rebalancing period.

        Parameters
        ----------
        prev_weights : pd.Series
            Previous weights (index = asset_ids).
        new_weights : pd.Series
            New weights (index = asset_ids).
        prices : pd.Series
            Current prices (index = asset_ids).
        capital : float
            Current portfolio capital.

        Returns
        -------
        tuple[float, dict[str, float]]
            (total_cost, per_asset_cost_dict).
        """
        per_asset: dict[str, float] = {}
        total = 0.0
        for asset in new_weights.index:
            w_new = float(new_weights.get(asset, 0.0))
            w_prev = float(prev_weights.get(asset, 0.0))
            trade_weight = abs(w_new - w_prev)
            if trade_weight < 1e-12:
                per_asset[asset] = 0.0
                continue
            notional = trade_weight * capital
            cost = self.cost_for_trade(notional)
            per_asset[asset] = cost
            total += cost
        return total, per_asset
