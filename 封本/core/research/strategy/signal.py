"""
core.research.strategy.signal
==========================
Strategy signal data containers.

Provides:
- SignalDirection: LONG / SHORT / NEUTRAL enum
- StrategySignal: signal container (direction + confidence + optional weights)
- StrategyIntent: multi-signal portfolio intent container

Design constraints
------------------
- Research-layer only: no order_type, limit_price, TIF, or other execution fields
- StrategySignal can hold pre-computed weights (pd.Series) OR a single asset_id
- BacktestEngine uses weights for position simulation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class SignalDirection(str, Enum):
    """
    Direction of the alpha signal.

    LONG   : positive alpha → long position
    SHORT  : negative alpha → short position
    NEUTRAL: no position (signal near zero)
    """

    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# StrategySignal — core signal container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StrategySignal:
    """
    Output of a strategy's signal generation step.

    Supports two modes:
    1. Single-asset mode: asset_id is set, weights derived from direction
    2. Multi-asset mode: weights is set as pd.Series with full portfolio

    Attributes
    ----------
    signal_id : str
        Unique identifier for this signal (optional, auto-generated).
    asset_id : str, optional
        Single asset this signal applies to (for single-asset mode).
    timestamp : datetime
        When this signal was generated.
    direction : SignalDirection | str
        Direction of the signal (long / short / neutral).
        Accepts str for convenience (auto-converted to SignalDirection).
    confidence : float
        Signal confidence in [0, 1]. 0 = no confidence, 1 = max confidence.
        Default 1.0.
    weights : pd.Series, optional
        Pre-computed portfolio weights.
        If provided, to_weights() returns these directly.
    raw_alpha : pd.Series, optional
        Raw alpha values (before normalization).
    strategy_id : str
        Which strategy generated this signal (default "unknown").
    metadata : dict, optional
        Arbitrary extra metadata.

    No execution fields: no order_type, limit_price, time_in_force, etc.
    """

    timestamp: datetime
    direction: SignalDirection | str
    confidence: float = 1.0
    weights: Optional[pd.Series] = None
    raw_alpha: Optional[pd.Series] = None
    strategy_id: str = "unknown"
    asset_id: Optional[str] = None
    signal_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        # String direction → enum
        if isinstance(self.direction, str):
            try:
                self.direction = SignalDirection(self.direction.lower())
            except ValueError:
                self.direction = SignalDirection.NEUTRAL

        # Confidence bounds
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")

        # Auto-generate signal_id
        if not self.signal_id:
            self.signal_id = (
                f"sig_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            )

    def to_weights(self) -> pd.Series:
        """
        Convert signal to portfolio weights.

        Returns
        -------
        pd.Series
            index = asset_ids, values = weights (normalized, sum(|w|) = 1).

        Logic
        -----
        1. If self.weights is set: use it (normalized)
        2. Else if self.asset_id is set: single-asset weight from direction
        3. Else: fallback uniform weight
        """
        # Mode 1: pre-computed multi-asset weights
        if self.weights is not None and not self.weights.empty:
            w = self.weights.copy()
            total = w.abs().sum()
            if total > 1e-10:
                w = w / total
            return w

        # Mode 2: single-asset from asset_id + direction
        if self.asset_id is not None:
            if self.direction == SignalDirection.LONG:
                return pd.Series({self.asset_id: 1.0})
            elif self.direction == SignalDirection.SHORT:
                return pd.Series({self.asset_id: -1.0})
            else:
                return pd.Series({self.asset_id: 0.0})

        # Mode 3: fallback
        return pd.Series(0.0, index=pd.Index(["asset"]))

    # ── Convenience classmethods ────────────────────────────────────────────

    @classmethod
    def from_alpha(
        cls,
        alpha: pd.Series,
        strategy_id: str = "strategy",
        signal_id: str = "",
        timestamp: Optional[datetime] = None,
    ) -> "StrategySignal":
        """
        Construct a StrategySignal from raw alpha values.

        Parameters
        ----------
        alpha : pd.Series
            Alpha values, index = asset_ids or timestamps.
        strategy_id : str
            Strategy identifier.
        signal_id : str
            Signal identifier (auto-generated if empty).
        timestamp : datetime, optional
            Signal timestamp (now if not provided).

        Returns
        -------
        StrategySignal
            Direction = LONG if mean(alpha) > 0 else SHORT else NEUTRAL.
            confidence = normalized |mean(alpha)|.
            weights = normalized rank(alpha).
        """
        ts = timestamp or datetime.utcnow()
        if not signal_id:
            signal_id = f"{strategy_id}_{ts.strftime('%Y%m%d%H%M%S')}"

        mean_alpha = float(alpha.mean()) if len(alpha) > 0 else 0.0

        if mean_alpha > 1e-10:
            direction = SignalDirection.LONG
        elif mean_alpha < -1e-10:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL

        # Confidence: normalized mean alpha
        std = alpha.std() if len(alpha) > 1 else 1.0
        confidence = min(abs(mean_alpha) / (std + 1e-10), 1.0)

        # Normalized rank weights
        weights = cls._rank_weights(alpha)

        return cls(
            signal_id=signal_id,
            timestamp=ts,
            direction=direction,
            confidence=float(confidence),
            weights=weights,
            raw_alpha=alpha,
            strategy_id=strategy_id,
        )

    @staticmethod
    def _rank_weights(alpha: pd.Series) -> pd.Series:
        """
        Convert alpha to portfolio via rank normalization.

        weights_i = spread_i / Σ|spread|
        spread = rank - (n+1)/2 scaled to [-1, +1]
        """
        if alpha.empty:
            return pd.Series(dtype=float)

        ranks = alpha.rank(ascending=True)
        n = len(ranks)
        if n <= 1:
            return pd.Series(1.0 / n, index=alpha.index)

        # Spread from -1 to +1
        spread = (ranks - (n + 1) / 2) / ((n - 1) / 2)
        abs_sum = spread.abs().sum()
        if abs_sum < 1e-10:
            return pd.Series(1.0 / n, index=alpha.index)
        return spread / abs_sum


# ─────────────────────────────────────────────────────────────────────────────
# StrategyIntent — multi-signal portfolio intent
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StrategyIntent:
    """
    Portfolio intent combining one or more StrategySignals.

    Encapsulates a set of signals and their aggregated weights for a single
    rebalancing period. Used as the output unit for BacktestEngine.

    Attributes
    ----------
    timestamp : datetime
        Intent timestamp (rebalancing period end).
    weights : pd.Series
        Aggregated portfolio weights, index = asset_ids.
    signals : list[StrategySignal], optional
        Individual signals that contributed to this intent.
    metadata : dict, optional
        Arbitrary extra metadata (strategy_id, run_id, etc.).

    Notes
    -----
    - weights must be non-empty and sum to 1.0 when normalized
    - No execution fields: no order_id, fill_price, order_type, TIF, etc.
    """

    timestamp: datetime
    weights: pd.Series
    signals: list[StrategySignal] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.weights.empty:
            raise ValueError("StrategyIntent weights cannot be empty")
        total = self.weights.abs().sum()
        if total < 1e-10:
            raise ValueError("StrategyIntent weights cannot all be zero")

    def to_weights_series(self) -> pd.Series:
        """
        Return normalized weights summing to 1.0.

        Returns
        -------
        pd.Series
            Normalized weights, index = asset_ids.
        """
        w = self.weights.copy()
        total = w.abs().sum()
        if total > 1e-10:
            return w / total
        return w

    def as_dict(self) -> dict:
        """
        Serialize to dict for logging / experiment records.

        Returns
        -------
        dict
            Serializable representation.
        """
        return {
            "timestamp": self.timestamp.isoformat(),
            "weights": self.weights.to_dict(),
            "n_signals": len(self.signals),
            "metadata": self.metadata,
        }
