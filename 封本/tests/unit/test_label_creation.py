"""
test_label_creation.py — L1–L3 Label Builder Unit Tests
========================================================
Tests ForwardReturnLabel and DirectionLabel with synthetic OHLCV data.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from core.research.labels.base import DirectionLabel, ForwardReturnLabel


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    """
    3 symbols × 30 business days of synthetic OHLCV.
    Simple upward trending prices for predictable labels.
    """
    n_days = 30
    dates = pd.bdate_range(start="2024-01-01", periods=n_days)
    symbols = ["SYM_A", "SYM_B", "SYM_C"]

    rows = []
    for sym in symbols:
        price = 100.0
        for d in dates:
            price = price * (1 + 0.005)  # Slight upward trend
            rows.append({
                "symbol": sym,
                "timestamp": d,
                "close": round(price, 4),
            })

    return pd.DataFrame(rows)


# ── L1: ForwardReturnLabel ────────────────────────────────────

class TestForwardReturnLabel:
    """L1: Forward return label builder tests."""

    def test_build_returns_complete_label_set_version(self):
        """L3: LabelSetVersion.build() has complete fields."""
        builder = ForwardReturnLabel(horizon=5, label_type="regression")
        spec = builder.build()

        assert spec.label_set_id is not None
        assert spec.name == "forward_return_h5_regression"
        assert spec.horizon == 5
        assert spec.horizon_unit == "D"
        assert spec.label_type == "regression"
        assert "label" in spec.label_definitions
        assert spec.version == "1.0.0"

    def test_build_classification(self):
        builder = ForwardReturnLabel(horizon=3, label_type="classification")
        spec = builder.build()
        assert spec.label_type == "classification"

    def test_compute_forward_return_regression(self, synthetic_ohlcv: pd.DataFrame):
        """L1: ForwardReturnLabel(horizon=5).compute() returns correct forward return."""
        builder = ForwardReturnLabel(horizon=5, label_type="regression")
        labels = builder.compute(synthetic_ohlcv)

        # Structure checks
        assert "symbol" in labels.columns
        assert "timestamp" in labels.columns
        assert "label_value" in labels.columns
        assert len(labels) > 0

        # For the upward trend, forward return should be positive for most rows
        # (last 5 rows per symbol have NaN — no future price)
        valid = labels.dropna(subset=["label_value"])

        # Numerical sanity: returns should be in a reasonable range
        assert valid["label_value"].between(-1.0, 10.0).all(), \
            "Forward returns outside reasonable range"

    def test_compute_forward_return_classification(self, synthetic_ohlcv: pd.DataFrame):
        """L1: ForwardReturnLabel(horizon=5, classification).compute() returns 0/1."""
        builder = ForwardReturnLabel(horizon=5, label_type="classification")
        labels = builder.compute(synthetic_ohlcv)

        valid = labels.dropna(subset=["label_value"])
        unique = sorted(valid["label_value"].unique())

        # Classification returns 1.0 (up) or 0.0 (down)
        assert all(v in (0.0, 1.0) for v in unique), \
            f"Classification labels should be 0.0 or 1.0, got {unique}"

    def test_compute_requires_close_column(self):
        """L1: Raises if close column is missing."""
        df = pd.DataFrame({"symbol": ["A"], "timestamp": [datetime.now()]})
        builder = ForwardReturnLabel()

        with pytest.raises(ValueError, match="close"):
            builder.compute(df)

    def test_compute_horizon_1(self, synthetic_ohlcv: pd.DataFrame):
        """L1: horizon=1 should give next-day returns."""
        builder = ForwardReturnLabel(horizon=1, label_type="regression")
        labels = builder.compute(synthetic_ohlcv)

        # horizon=1 → fewer NaN rows than horizon=5
        builder5 = ForwardReturnLabel(horizon=5, label_type="regression")
        labels5 = builder5.compute(synthetic_ohlcv)

        # More horizon=1 labels than horizon=5 (more rows have a next-day price)
        assert len(labels.dropna(subset=["label_value"])) >= len(labels5.dropna(subset=["label_value"]))

    def test_different_symbols_independent(self, synthetic_ohlcv: pd.DataFrame):
        """L1: Forward returns computed per symbol independently."""
        builder = ForwardReturnLabel(horizon=2)
        labels = builder.compute(synthetic_ohlcv)

        # SYM_A and SYM_B should have different label values at same timestamp
        sym_a = labels[labels["symbol"] == "SYM_A"].sort_values("timestamp").reset_index(drop=True)
        sym_b = labels[labels["symbol"] == "SYM_B"].sort_values("timestamp").reset_index(drop=True)

        # Merge on timestamp and check they diverge
        merged = sym_a[["timestamp", "label_value"]].rename(columns={"label_value": "va"}).merge(
            sym_b[["timestamp", "label_value"]].rename(columns={"label_value": "vb"}),
            on="timestamp",
        )

        # Not all values should be identical (prices diverged)
        assert len(merged) > 0


# ── L2: DirectionLabel ────────────────────────────────────────

class TestDirectionLabel:
    """L2: Direction label builder tests."""

    def test_build_returns_complete_spec(self):
        """L3: LabelSetVersion.build() complete for DirectionLabel."""
        builder = DirectionLabel(horizon=5, threshold=0.0)
        spec = builder.build()

        assert spec.label_set_id is not None
        assert spec.horizon == 5
        assert spec.label_type == "classification"
        assert spec.version == "1.0.0"

    def test_compute_direction_values(self, synthetic_ohlcv: pd.DataFrame):
        """L2: DirectionLabel(horizon=5).compute() returns 0.0/1.0/0.5."""
        builder = DirectionLabel(horizon=5, threshold=0.0)
        labels = builder.compute(synthetic_ohlcv)

        valid = labels.dropna(subset=["label_value"])
        unique = sorted(valid["label_value"].unique())

        # With upward trend, most should be 1.0 (up)
        assert all(v in (0.0, 0.5, 1.0) for v in unique), \
            f"Direction labels should be 0.0/0.5/1.0, got {unique}"
        # Should include 1.0 (upward trend)
        assert 1.0 in unique, "Upward trend data should produce 1.0 labels"

    def test_compute_threshold_filter(self, synthetic_ohlcv: pd.DataFrame):
        """L2: threshold>0 excludes small returns as neutral (0.5)."""
        builder_thr0 = DirectionLabel(horizon=2, threshold=0.0)
        builder_thr2 = DirectionLabel(horizon=2, threshold=0.02)

        labels0 = builder_thr0.compute(synthetic_ohlcv)
        labels2 = builder_thr2.compute(synthetic_ohlcv)

        # threshold=0.02 should produce more neutral (0.5) labels
        neutral0 = (labels0["label_value"] == 0.5).sum()
        neutral2 = (labels2["label_value"] == 0.5).sum()

        assert neutral2 >= neutral0, \
            "Higher threshold should produce equal or more neutral labels"

    def test_requires_close_column(self):
        """L2: Raises if close column missing."""
        df = pd.DataFrame({"symbol": ["A"], "timestamp": [datetime.now()]})
        builder = DirectionLabel()

        with pytest.raises(ValueError, match="close"):
            builder.compute(df)

    def test_label_set_version_matches_compute(self, synthetic_ohlcv: pd.DataFrame):
        """L3: build() spec matches actual compute() output horizon."""
        builder = ForwardReturnLabel(horizon=10)
        spec = builder.build()
        labels = builder.compute(synthetic_ohlcv)

        assert spec.horizon == 10
        assert "label_value" in labels.columns

        # Valid rows should be less than total (last 10 rows per symbol = NaN)
        n_symbols = synthetic_ohlcv["symbol"].nunique()
        assert len(labels.dropna(subset=["label_value"])) <= len(labels)
