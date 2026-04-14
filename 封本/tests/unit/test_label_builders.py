"""
Unit tests for label builders.
"""

import pytest
import pandas as pd
import numpy as np

from core.research.labels.schema import LabelSpec, LabelResult, LabelSetResult
from core.research.labels.returns import (
    ReturnLabelBuilder,
    ExcessReturnLabelBuilder,
    build_return_labels,
)
from core.research.labels.direction import (
    DirectionLabelBuilder,
    TernaryDirectionLabelBuilder,
    build_direction_labels,
)
from core.research.labels.risk import (
    MaxDrawdownLabelBuilder,
    VolatilityPercentileLabelBuilder,
    VaRBreachLabelBuilder,
    build_risk_labels,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_price_data():
    """Sample price data for 2 symbols."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")

    frames = []
    for sym in ["AAPL", "MSFT"]:
        close = 100 * np.exp(np.cumsum(np.random.randn(60) * 0.02))
        frames.append(pd.DataFrame({
            "symbol": sym,
            "timestamp": dates,
            "close": close,
        }))

    return pd.concat(frames, ignore_index=True)


# ── Schema Tests ────────────────────────────────────────────────────────────


class TestLabelSchema:
    def test_label_spec(self):
        spec = LabelSpec(
            label_name="test_label",
            label_type="regression",
            horizon=5,
        )
        assert spec.label_name == "test_label"
        assert spec.horizon == 5

    def test_label_result_from_dataframe(self, sample_price_data):
        spec = LabelSpec(label_name="test", horizon=1)
        df = sample_price_data[["symbol", "timestamp"]].copy()
        df["label_value"] = np.random.randn(len(df))

        result = LabelResult.from_dataframe(spec, df)
        assert result.spec.label_name == "test"
        assert "n_samples" in result.metadata

    def test_label_set_result(self, sample_price_data):
        set_result = LabelSetResult()

        spec1 = LabelSpec(label_name="label1", horizon=1)
        df1 = sample_price_data[["symbol", "timestamp"]].copy()
        df1["label_value"] = 0.1
        result1 = LabelResult.from_dataframe(spec1, df1)

        set_result.add(result1)
        assert "label1" in set_result.labels

    def test_label_set_result_to_combined_dataframe(self, sample_price_data):
        set_result = LabelSetResult()

        for name in ["label1", "label2"]:
            spec = LabelSpec(label_name=name, horizon=1)
            df = sample_price_data[["symbol", "timestamp"]].copy()
            df["label_value"] = np.random.randn(len(df))
            result = LabelResult.from_dataframe(spec, df)
            set_result.add(result)

        combined = set_result.to_combined_dataframe()
        assert "label1" in combined.columns
        assert "label2" in combined.columns


# ── Return Label Tests ───────────────────────────────────────────────────────


class TestReturnLabels:
    def test_return_label_builder_1d(self, sample_price_data):
        builder = ReturnLabelBuilder(horizon=1)
        result = builder.compute(sample_price_data)

        assert result.spec.label_name == "return_1d"
        assert len(result.to_dataframe()) > 0

    def test_return_label_builder_5d(self, sample_price_data):
        builder = ReturnLabelBuilder(horizon=5)
        result = builder.compute(sample_price_data)

        assert result.spec.horizon == 5

    def test_excess_return_label(self, sample_price_data):
        # Simple benchmark returns
        dates = sample_price_data["timestamp"].unique()
        bench_returns = pd.Series(np.random.randn(len(dates)) * 0.01, index=dates)

        builder = ExcessReturnLabelBuilder(horizon=1, benchmark_returns=bench_returns)
        result = builder.compute(sample_price_data)

        assert result.spec.label_name == "excess_return_1d"

    def test_build_return_labels_multi(self, sample_price_data):
        results = build_return_labels(sample_price_data, horizons=[1, 5, 20])

        assert "return_1d" in results
        assert "return_5d" in results
        assert "return_20d" in results


# ── Direction Label Tests ────────────────────────────────────────────────────


class TestDirectionLabels:
    def test_direction_label_builder(self, sample_price_data):
        builder = DirectionLabelBuilder(horizon=1, threshold=0.0)
        result = builder.compute(sample_price_data)

        df = result.to_dataframe()
        # Values should be 0.0, 0.5, or 1.0
        assert set(df["label_value"].unique()).issubset({0.0, 0.5, 1.0})

    def test_direction_label_with_threshold(self, sample_price_data):
        builder = DirectionLabelBuilder(horizon=5, threshold=0.02)
        result = builder.compute(sample_price_data)

        assert result.spec.parameters["threshold"] == 0.02

    def test_ternary_direction_label(self, sample_price_data):
        builder = TernaryDirectionLabelBuilder(horizon=1, threshold=0.01)
        result = builder.compute(sample_price_data)

        df = result.to_dataframe()
        # Values should be 0.0, 1.0, or 2.0
        assert set(df["label_value"].unique()).issubset({0.0, 1.0, 2.0})

    def test_build_direction_labels_multi(self, sample_price_data):
        results = build_direction_labels(
            sample_price_data,
            horizons=[1, 5],
            thresholds=[0.0, 0.01],
        )

        # Should have 2 labels (one per horizon with first threshold)
        # The function iterates horizons x thresholds but only last threshold per horizon is kept
        assert len(results) >= 2


# ── Risk Label Tests ─────────────────────────────────────────────────────────


class TestRiskLabels:
    def test_max_drawdown_label(self, sample_price_data):
        builder = MaxDrawdownLabelBuilder(horizon=20)
        result = builder.compute(sample_price_data)

        df = result.to_dataframe()
        # Max drawdown should be <= 0
        assert (df["label_value"] <= 0).all()

    def test_volatility_percentile_label(self, sample_price_data):
        builder = VolatilityPercentileLabelBuilder(vol_period=20, lookback=40)
        result = builder.compute(sample_price_data)

        df = result.to_dataframe()
        # Percentile should be in [0, 1]
        assert (df["label_value"] >= 0).all()
        assert (df["label_value"] <= 1).all()

    def test_var_breach_label(self, sample_price_data):
        builder = VaRBreachLabelBuilder(var_level=0.05, var_period=20)
        result = builder.compute(sample_price_data)

        df = result.to_dataframe()
        # Breach indicator should be 0 or 1
        assert set(df["label_value"].unique()).issubset({0.0, 1.0})

    def test_build_risk_labels_all(self, sample_price_data):
        results = build_risk_labels(sample_price_data)

        assert "max_drawdown_20d" in results
        assert "volatility_percentile" in results
        assert "var_breach_95pct" in results
