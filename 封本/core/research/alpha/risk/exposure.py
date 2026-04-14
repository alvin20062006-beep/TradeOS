"""
Factor Exposure Analysis
========================
Compute Barra-style factor exposures for a portfolio.

Given portfolio weights and factor loadings, compute:
    - Exposure to each style factor (size, value, momentum, volatility, etc.)
    - Exposure to each sector/industry
    - Active exposure vs benchmark

No directional prediction - pure exposure measurement.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# ExposureResult Schema
# ─────────────────────────────────────────────────────────────────


class ExposureResult(BaseModel):
    """
    Result of factor exposure analysis.

    Attributes
    ----------
    style_exposures : dict
        Map from factor_name to exposure value.
    sector_exposures : dict
        Map from sector_name to weight.
    active_exposures : dict
        Map from factor_name to active exposure (vs benchmark).
    total_risk : float
        Estimated total portfolio risk (sqrt of variance).
    idiosyncratic_risk : float
        Estimated idiosyncratic risk.
    systematic_risk : float
        Estimated systematic risk.
    """

    style_exposures: dict[str, float] = Field(default_factory=dict)
    sector_exposures: dict[str, float] = Field(default_factory=dict)
    active_exposures: dict[str, float] = Field(default_factory=dict)
    total_risk: float = 0.0
    idiosyncratic_risk: float = 0.0
    systematic_risk: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────
# Factor Exposure Calculator
# ─────────────────────────────────────────────────────────────────


class FactorExposureCalculator:
    """
    Calculate factor exposures for a portfolio.

    Parameters
    ----------
    style_factors : list[str]
        List of style factor names (e.g., ["size", "value", "momentum", "volatility"]).
    sector_factors : list[str]
        List of sector names.
    factor_covariance : pd.DataFrame, optional
        Factor covariance matrix (factors x factors).
    idio_variances : pd.Series, optional
        Idiosyncratic variances by asset.
    """

    def __init__(
        self,
        style_factors: Optional[list[str]] = None,
        sector_factors: Optional[list[str]] = None,
        factor_covariance: Optional[pd.DataFrame] = None,
        idio_variances: Optional[pd.Series] = None,
    ):
        self.style_factors = style_factors or ["size", "value", "momentum", "volatility"]
        self.sector_factors = sector_factors or []
        self.factor_covariance = factor_covariance
        self.idio_variances = idio_variances

    def compute_style_exposures(
        self,
        weights: pd.Series,
        factor_loadings: pd.DataFrame,
    ) -> dict[str, float]:
        """
        Compute style factor exposures.

        Parameters
        ----------
        weights : pd.Series
            Portfolio weights indexed by asset.
        factor_loadings : pd.DataFrame
            Factor loadings (assets x factors).

        Returns
        -------
        dict[str, float]
            Map from factor_name to exposure.
        """
        # Align indices
        common = weights.index.intersection(factor_loadings.index)
        if len(common) == 0:
            return {}

        w = weights.loc[common]
        X = factor_loadings.loc[common]

        # Exposure = w'X
        exposures = (w.values @ X.values)
        return dict(zip(X.columns, exposures))

    def compute_sector_exposures(
        self,
        weights: pd.Series,
        sector_map: dict[str, str],
    ) -> dict[str, float]:
        """
        Compute sector exposures.

        Parameters
        ----------
        weights : pd.Series
            Portfolio weights indexed by asset.
        sector_map : dict
            Map from asset to sector.

        Returns
        -------
        dict[str, float]
            Map from sector to weight.
        """
        sector_weights = {}
        for asset, weight in weights.items():
            sector = sector_map.get(asset, "Unknown")
            sector_weights[sector] = sector_weights.get(sector, 0.0) + weight
        return sector_weights

    def compute_active_exposures(
        self,
        portfolio_exposures: dict[str, float],
        benchmark_exposures: dict[str, float],
    ) -> dict[str, float]:
        """
        Compute active exposures vs benchmark.

        Parameters
        ----------
        portfolio_exposures : dict
        benchmark_exposures : dict

        Returns
        -------
        dict[str, float]
            Active exposure = portfolio - benchmark.
        """
        active = {}
        for factor in portfolio_exposures:
            active[factor] = portfolio_exposures[factor] - benchmark_exposures.get(factor, 0.0)
        return active

    def compute_risk(
        self,
        weights: pd.Series,
        factor_loadings: pd.DataFrame,
    ) -> tuple[float, float, float]:
        """
        Compute portfolio risk decomposition.

        Parameters
        ----------
        weights : pd.Series
        factor_loadings : pd.DataFrame

        Returns
        -------
        tuple[float, float, float]
            (total_risk, systematic_risk, idiosyncratic_risk)
        """
        # Align indices
        common = weights.index.intersection(factor_loadings.index)
        if len(common) == 0:
            return 0.0, 0.0, 0.0

        w = weights.loc[common].values
        X = factor_loadings.loc[common].values

        # Systematic risk
        if self.factor_covariance is not None:
            # sigma_sys = sqrt(w' X F X' w)
            F = self.factor_covariance.values
            XFX = X @ F @ X.T
            var_sys = w @ XFX @ w
            systematic_risk = np.sqrt(max(var_sys, 0))
        else:
            # Assume unit factor covariance
            var_sys = np.sum((w @ X) ** 2)
            systematic_risk = np.sqrt(max(var_sys, 0))

        # Idiosyncratic risk
        if self.idio_variances is not None:
            common_idio = common.intersection(self.idio_variances.index)
            var_idio = np.sum(
                (weights.loc[common_idio] ** 2) * self.idio_variances.loc[common_idio]
            )
            idiosyncratic_risk = np.sqrt(max(var_idio, 0))
        else:
            # Assume 20% annual idio vol per asset
            var_idio = np.sum(w ** 2) * 0.20 ** 2
            idiosyncratic_risk = np.sqrt(var_idio)

        # Total risk
        total_risk = np.sqrt(systematic_risk ** 2 + idiosyncratic_risk ** 2)

        return total_risk, systematic_risk, idiosyncratic_risk

    def compute(
        self,
        weights: pd.Series,
        factor_loadings: pd.DataFrame,
        sector_map: Optional[dict[str, str]] = None,
        benchmark_weights: Optional[pd.Series] = None,
    ) -> ExposureResult:
        """
        Compute full exposure analysis.

        Parameters
        ----------
        weights : pd.Series
            Portfolio weights.
        factor_loadings : pd.DataFrame
            Factor loadings.
        sector_map : dict, optional
            Asset to sector mapping.
        benchmark_weights : pd.Series, optional
            Benchmark weights for active exposure.

        Returns
        -------
        ExposureResult
        """
        # Style exposures
        style_exposures = self.compute_style_exposures(weights, factor_loadings)

        # Sector exposures
        sector_exposures = {}
        if sector_map:
            sector_exposures = self.compute_sector_exposures(weights, sector_map)

        # Active exposures
        active_exposures = {}
        if benchmark_weights is not None:
            benchmark_exposures = self.compute_style_exposures(benchmark_weights, factor_loadings)
            active_exposures = self.compute_active_exposures(style_exposures, benchmark_exposures)

        # Risk
        total_risk, sys_risk, idio_risk = self.compute_risk(weights, factor_loadings)

        return ExposureResult(
            style_exposures=style_exposures,
            sector_exposures=sector_exposures,
            active_exposures=active_exposures,
            total_risk=total_risk,
            systematic_risk=sys_risk,
            idiosyncratic_risk=idio_risk,
            metadata={
                "n_assets": len(weights),
                "n_factors": factor_loadings.shape[1],
            },
        )


# ─────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────


def compute_factor_exposures(
    weights: pd.Series,
    factor_loadings: pd.DataFrame,
    **kwargs,
) -> ExposureResult:
    """
    Convenience function to compute factor exposures.

    Parameters
    ----------
    weights : pd.Series
    factor_loadings : pd.DataFrame
    **kwargs
        Passed to FactorExposureCalculator.

    Returns
    -------
    ExposureResult
    """
    calc = FactorExposureCalculator(**kwargs)
    return calc.compute(weights, factor_loadings)
