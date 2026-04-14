"""
Unit tests for risk exposure analysis.
"""

import pytest
import pandas as pd
import numpy as np

from core.research.alpha.risk.exposure import (
    FactorExposureCalculator,
    ExposureResult,
    compute_factor_exposures,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_weights():
    """Sample portfolio weights."""
    return pd.Series({
        "AAPL": 0.30,
        "MSFT": 0.25,
        "GOOGL": 0.20,
        "AMZN": 0.15,
        "META": 0.10,
    })


@pytest.fixture
def sample_factor_loadings():
    """Sample factor loadings."""
    np.random.seed(42)
    assets = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    factors = ["size", "value", "momentum", "volatility"]

    return pd.DataFrame(
        np.random.randn(5, 4) * 0.5,
        index=assets,
        columns=factors,
    )


@pytest.fixture
def sample_sector_map():
    """Sample sector mapping."""
    return {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "GOOGL": "Communication",
        "AMZN": "Consumer",
        "META": "Communication",
    }


# ── Tests ───────────────────────────────────────────────────────────────────


class TestFactorExposure:
    def test_compute_style_exposures(self, sample_weights, sample_factor_loadings):
        calc = FactorExposureCalculator()
        exposures = calc.compute_style_exposures(sample_weights, sample_factor_loadings)

        assert isinstance(exposures, dict)
        assert set(exposures.keys()) == set(sample_factor_loadings.columns)

    def test_compute_sector_exposures(self, sample_weights, sample_sector_map):
        calc = FactorExposureCalculator()
        exposures = calc.compute_sector_exposures(sample_weights, sample_sector_map)

        assert isinstance(exposures, dict)
        # Technology should have 0.30 + 0.25 = 0.55
        assert abs(exposures["Technology"] - 0.55) < 1e-9
        # Communication should have 0.20 + 0.10 = 0.30
        assert abs(exposures["Communication"] - 0.30) < 1e-9

    def test_compute_active_exposures(self):
        calc = FactorExposureCalculator()
        portfolio = {"size": 0.5, "value": -0.2}
        benchmark = {"size": 0.3, "value": 0.0}

        active = calc.compute_active_exposures(portfolio, benchmark)
        assert abs(active["size"] - 0.2) < 1e-9
        assert abs(active["value"] - (-0.2)) < 1e-9

    def test_compute_risk_no_covariance(self, sample_weights, sample_factor_loadings):
        calc = FactorExposureCalculator()
        total, sys, idio = calc.compute_risk(sample_weights, sample_factor_loadings)

        assert total >= 0
        assert sys >= 0
        assert idio >= 0
        # Total^2 should be close to sys^2 + idio^2
        assert abs(total ** 2 - (sys ** 2 + idio ** 2)) < 1e-9

    def test_compute_full(self, sample_weights, sample_factor_loadings, sample_sector_map):
        calc = FactorExposureCalculator()
        result = calc.compute(
            sample_weights,
            sample_factor_loadings,
            sector_map=sample_sector_map,
        )

        assert isinstance(result, ExposureResult)
        assert len(result.style_exposures) == 4
        assert len(result.sector_exposures) == 3
        assert result.total_risk >= 0

    def test_compute_with_benchmark(self, sample_weights, sample_factor_loadings):
        calc = FactorExposureCalculator()
        benchmark = pd.Series({
            "AAPL": 0.20,
            "MSFT": 0.20,
            "GOOGL": 0.20,
            "AMZN": 0.20,
            "META": 0.20,
        })

        result = calc.compute(
            sample_weights,
            sample_factor_loadings,
            benchmark_weights=benchmark,
        )

        assert len(result.active_exposures) == 4

    def test_convenience_function(self, sample_weights, sample_factor_loadings):
        result = compute_factor_exposures(sample_weights, sample_factor_loadings)
        assert isinstance(result, ExposureResult)
