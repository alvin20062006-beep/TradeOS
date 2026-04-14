"""
core.research.backtest.schema
=============================
Research-layer backtest configuration schemas.

Design constraints
-----------------
- Research-layer only: no order/execution semantics.
- Output: BacktestResult (weights → P&L, no Order/Fill).
- Cost model: fixed_bps only (Phase 1); market impact is execution layer.
- BacktestConfig: single rebalancing pass (no multi-period optimization).

Field definitions for BacktestConfig
------------------------------------
rebalance_freq       : str  — pandas offset alias ('D','W','ME','QE','YE')
initial_capital      : float — portfolio starting capital
cost_model           : CostModelConfig
benchmark_weights    : dict[str, float] | None — optional benchmark for relative metrics
risk_free_rate       : float — annualized risk-free rate for Sharpe/Sortino
output_dir           : pathlib.Path | None — where to write JSON report

Field definitions for CostModelConfig
-------------------------------------
fixed_bps            : float — one-way cost in basis points (default 5.0 bps)
slippage_bps         : float — price slippage in bps (default 0.0, optional)
min_cost             : float — minimum cost per trade in currency units
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Cost Model Config ────────────────────────────────────────────────────────

class CostModelConfig(BaseModel):
    """
    Simplified cost model for research-layer backtesting.

    Supported (Phase 1)
    -------------------
    - fixed_bps   : one-way fixed cost in basis points of trade notional
    - slippage_bps: optional symmetric price slippage in bps

    NOT supported (execution layer / future research)
    -------------------------------------------------
    - market impact models
    - queue position / order book depth
    - maker/taker distinction
    - crossing spread

    Examples
    --------
    >>> cfg = CostModelConfig(fixed_bps=5.0, slippage_bps=0.5)
    >>> cfg.total_cost_bps(10000.0)
    5.5   # 5 bps + 0.5 bps
    """

    model_config = ConfigDict(extra="forbid")

    fixed_bps: float = Field(
        default=5.0,
        ge=0.0,
        description="One-way fixed cost in basis points (1 bps = 0.01%)."
    )
    slippage_bps: float = Field(
        default=0.0,
        ge=0.0,
        description="Symmetric price slippage in basis points (optional, default 0.0)."
    )
    min_cost: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum cost per trade in absolute currency units."
    )

    def total_cost_bps(self, notional: float) -> float:
        """
        Total one-way cost in basis points for a given notional trade.

        Parameters
        ----------
        notional : float
            Trade notional in currency units.

        Returns
        -------
        float
            Total cost in bps (fixed + slippage).
        """
        total = self.fixed_bps + self.slippage_bps
        return total

    def total_cost_absolute(self, notional: float) -> float:
        """
        Total one-way cost in absolute currency units.

        Parameters
        ----------
        notional : float
            Trade notional in currency units.

        Returns
        -------
        float
            max(fixed_bps * notional / 10000, min_cost)
        """
        cost = notional * (self.total_cost_bps(notional) / 10000.0)
        return max(cost, self.min_cost)


# ── Backtest Config ─────────────────────────────────────────────────────────

class BacktestConfig(BaseModel):
    """
    Research-layer backtest configuration.

    Parameters
    ----------
    rebalance_freq : str
        Rebalancing frequency as pandas offset alias.
        Common values: 'D' (daily), 'W' (weekly), 'ME' (month-end),
        'QE' (quarter-end), 'YE' (year-end).
    initial_capital : float
        Starting portfolio capital in currency units.
    cost_model : CostModelConfig
        Transaction cost parameters.
    benchmark_weights : dict[str, float] | None
        Optional benchmark weights for relative performance metrics.
        Keys are asset IDs, values are benchmark weights summing to 1.0.
    risk_free_rate : float
        Annualized risk-free rate (e.g. 0.03 for 3%) used in Sharpe/Sortino.
    output_dir : Path | None
        Directory for JSON report output. If None, no file is written.

    Examples
    --------
    >>> cfg = BacktestConfig(
    ...     rebalance_freq='W',
    ...     initial_capital=1_000_000.0,
    ...     cost_model=CostModelConfig(fixed_bps=5.0),
    ...     risk_free_rate=0.04,
    ... )
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    rebalance_freq: str = Field(
        default="W",
        description="Rebalancing frequency (pandas offset alias)."
    )
    initial_capital: float = Field(
        default=1_000_000.0,
        gt=0.0,
        description="Starting capital in currency units."
    )
    cost_model: CostModelConfig = Field(
        default_factory=CostModelConfig,
        description="Transaction cost parameters."
    )
    benchmark_weights: Optional[dict[str, float]] = Field(
        default=None,
        description="Optional benchmark weights {asset_id: weight} for relative metrics."
    )
    risk_free_rate: float = Field(
        default=0.0,
        ge=0.0,
        description="Annualized risk-free rate (e.g. 0.04 for 4%)."
    )
    output_dir: Optional[Path] = Field(
        default=None,
        description="Directory for JSON report. Created automatically."
    )

    @field_validator("rebalance_freq", mode="before")
    @classmethod
    def _validate_freq(cls, v):
        if not isinstance(v, str):
            raise TypeError("rebalance_freq must be a string (pandas offset alias)")
        valid = {"D", "W", "ME", "QE", "YE", "M", "Q", "Y", "H", "h"}
        base = v.upper().rstrip("0123456789")
        if base not in valid and not v[0].isdigit():
            # Accept any pandas-like alias but warn if dubious
            pass
        return v

    @field_validator("benchmark_weights", mode="before")
    @classmethod
    def _validate_benchmark(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            total = sum(v.values())
            if abs(total - 1.0) > 1e-6:
                raise ValueError(
                    f"benchmark_weights must sum to 1.0, got {total:.6f}"
                )
            return v
        raise TypeError("benchmark_weights must be dict or None")

    def create_output_dir(self) -> Optional[Path]:
        """Create output directory if configured and not exists."""
        if self.output_dir is None:
            return None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir
