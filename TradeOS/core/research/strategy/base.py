"""
core.research.strategy.base
===========================
Research-layer strategy base class and simple built-in strategies.

The module stays on the research side only and exposes no trading-order fields.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd

from core.research.strategy.signal import StrategyIntent, StrategySignal


class StrategyBase(ABC):
    """
    Base class for research-layer strategies.

    Subclasses implement `generate_weights(timestamp, features)` and return a
    `pd.Series` indexed by asset id.
    """

    def __init__(self, name: str = "base", description: str = ""):
        self._name = name
        self._description = description
        self._fitted = False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self._name}')"

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @abstractmethod
    def generate_weights(self, timestamp: datetime, features: pd.DataFrame) -> pd.Series:
        """Generate portfolio weights for a single research timestamp."""

    def generate_weights_series(
        self,
        dates: pd.DatetimeIndex,
        features_by_date: dict[datetime, pd.DataFrame],
    ) -> pd.DataFrame:
        records = []
        used_dates = []
        for dt in dates:
            if dt in features_by_date:
                records.append(self.generate_weights(dt, features_by_date[dt]))
                used_dates.append(dt)
        if not records:
            return pd.DataFrame(dtype=float)
        return pd.DataFrame(records, index=pd.DatetimeIndex(used_dates))

    def signals_to_intent(
        self,
        signals: list[StrategySignal],
        timestamp: datetime,
    ) -> StrategyIntent:
        all_weights: dict[str, float] = {}
        for sig in signals:
            for asset, value in sig.to_weights().items():
                all_weights[asset] = all_weights.get(asset, 0.0) + float(value)

        weights = pd.Series(all_weights, dtype=float)
        total = weights.abs().sum()
        if total > 1e-10:
            weights = weights / total

        return StrategyIntent(
            timestamp=timestamp,
            weights=weights,
            signals=signals,
            metadata={"strategy_name": self._name},
        )

    def fit(self, data: pd.DataFrame) -> "StrategyBase":
        self._fitted = True
        return self

    def is_fitted(self) -> bool:
        return self._fitted


class MomentumStrategy(StrategyBase):
    """Simple cross-sectional momentum allocator."""

    def __init__(self, name: str = "momentum", lookback: int = 20, long_only: bool = False):
        super().__init__(name=name, description=f"Momentum (lookback={lookback})")
        self.lookback = lookback
        self.long_only = long_only

    def generate_weights(self, timestamp: datetime, features: pd.DataFrame) -> pd.Series:
        if features.empty:
            return pd.Series(dtype=float)

        scores = features.iloc[:, 0].astype(float)
        n = len(scores)
        if n == 1:
            return pd.Series(1.0, index=scores.index)

        ranks = scores.rank(ascending=True)
        centered = (ranks - (n + 1) / 2) / ((n - 1) / 2)
        if self.long_only:
            centered = centered.clip(lower=0.0)

        total = centered.abs().sum()
        if total < 1e-10:
            return pd.Series(1.0 / n, index=scores.index)
        return centered / total


class MeanReversionStrategy(StrategyBase):
    """Simple z-score mean-reversion allocator."""

    def __init__(
        self,
        name: str = "mean_reversion",
        lookback: int = 20,
        zscore_threshold: float = 1.5,
    ):
        super().__init__(name=name, description=f"Mean reversion (z>{zscore_threshold})")
        self.lookback = lookback
        self.zscore_threshold = zscore_threshold

    def generate_weights(self, timestamp: datetime, features: pd.DataFrame) -> pd.Series:
        if features.empty or features.shape[0] < 2:
            return pd.Series(dtype=float)

        scores = -features.iloc[:, 0].astype(float)
        std = float(scores.std())
        if std < 1e-10:
            return pd.Series(1.0 / len(scores), index=scores.index)

        zscores = (scores - float(scores.mean())) / std
        mask = zscores.abs() >= self.zscore_threshold
        if mask.any():
            zscores = zscores.where(mask, 0.0)
        total = zscores.abs().sum()
        if total < 1e-10:
            return pd.Series(1.0 / len(scores), index=scores.index)
        return zscores / total


class EqualWeightStrategy(StrategyBase):
    """Uniform allocator across the available assets."""

    def __init__(self, name: str = "equal_weight"):
        super().__init__(name=name, description="Equal weight")

    def generate_weights(self, timestamp: datetime, features: pd.DataFrame) -> pd.Series:
        if features.empty:
            return pd.Series(dtype=float)
        n = len(features.index)
        return pd.Series(1.0 / n, index=features.index, dtype=float)
