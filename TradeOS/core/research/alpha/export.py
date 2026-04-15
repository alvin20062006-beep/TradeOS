"""
AlphaExporter - Export AlphaFactorSet to Qlib FeatureSetVersion
===============================================================
Converts the alpha layer's standardized objects into Qlib-compatible
FeatureSetVersion objects, ready for Qlib workflow consumption.

Supports two modes:
1. Registry mode: factors registered via AlphaRegistry, then exported
2. Direct mode: factors added directly via add_factor(), then exported
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from .models import AlphaFactorSet, AlphaFactorSpec, AlphaFactorValue
from .registry import AlphaRegistry
from ..models import FeatureSetVersion


class AlphaExporter:
    """
    Export an AlphaFactorSet to a FeatureSetVersion for Qlib consumption.

    Supports two workflows:
    - Registry mode: factors in registry → get_set() → to_feature_set_version()
    - Direct mode: add_factor() → to_feature_set_version() (no registry needed)

    Responsibilities
    ----------------
    1. Convert AlphaFactorSet → FeatureSetVersion (schema bridge)
    2. Generate feature_names list from factor specs
    3. Map factor_group → feature_groups
    4. Optionally write Qlib-compatible CSV of factor values
    """

    def __init__(self, alpha_registry: Optional[AlphaRegistry] = None):
        self.alpha_registry = alpha_registry or AlphaRegistry()
        self._local_factors: list[tuple[AlphaFactorSpec, pd.DataFrame]] = []

    # ── Direct mode (no registry required) ──────────────────

    def add_factor(
        self,
        factor_id: str,
        factor_name: str,
        factor_values: pd.DataFrame,
        factor_group: str = "technical",
        layer: str = "L1",
        parameters: Optional[dict] = None,
    ) -> None:
        """
        Add a factor directly without registry.

        Parameters
        ----------
        factor_id : str
        factor_name : str
        factor_values : pd.DataFrame
            Columns: symbol, timestamp, raw_value
        factor_group : str
            technical / fundamental / macro / sentiment / orderflow
        layer : str
            L1 / L2 / L3
        parameters : dict, optional
        """
        spec = AlphaFactorSpec(
            factor_id=factor_id,
            factor_name=factor_name,
            factor_group=factor_group,
            source_module="alpha.export",
            layer=layer,
            parameters=parameters or {},
        )
        self._local_factors.append((spec, factor_values))

    def to_feature_set_version(
        self,
        factor_set_id: Optional[str] = None,
        feature_set_name: Optional[str] = None,
        lookback_window: int = 20,
        frequency: str = "1D",
        version: str = "1.0.0",
    ) -> FeatureSetVersion:
        """
        Convert accumulated factors to a FeatureSetVersion.

        Tries direct mode first (local_factors), then registry mode.

        Parameters
        ----------
        factor_set_id : str, optional
            Registry factor set ID (if using registry mode).
        feature_set_name : str, optional
            Override the FeatureSetVersion name.
        lookback_window : int
            Lookback window in periods.
        frequency : str
            Data frequency.
        version : str
            Semver version string.

        Returns
        -------
        FeatureSetVersion
        """
        # Mode 1: Direct factors
        if self._local_factors:
            feature_names = []
            feature_groups: dict[str, list[str]] = {}

            for spec, _ in self._local_factors:
                feature_names.append(spec.factor_name)
                group = spec.factor_group
                if group not in feature_groups:
                    feature_groups[group] = []
                if spec.factor_name not in feature_groups[group]:
                    feature_groups[group].append(spec.factor_name)

            name = feature_set_name or f"AlphaExport_v{version.replace('.', '_')}"
            fset_id = factor_set_id or f"export_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            return FeatureSetVersion(
                feature_set_id=fset_id,
                name=name,
                feature_names=feature_names,
                feature_groups=feature_groups,
                version=version,
                lookback_window=lookback_window,
                frequency=frequency,
                description=f"Exported from AlphaExporter ({len(self._local_factors)} factors)",
                metadata={
                    "normalization_method": "none",
                    "neutralization_method": "none",
                    "exported_at": datetime.now().isoformat(),
                    "factor_count": len(self._local_factors),
                },
            )

        # Mode 2: Registry-based
        if factor_set_id is None:
            raise ValueError(
                "No local factors added. Provide factor_set_id to use registry mode, "
                "or use add_factor() to add factors directly."
            )

        factor_set = self.alpha_registry.get_set(factor_set_id)
        if factor_set is None:
            raise ValueError(f"AlphaFactorSet not found: {factor_set_id}")

        feature_names: list[str] = []
        feature_groups: dict[str, list[str]] = {}

        for fid in factor_set.factor_ids:
            spec = self.alpha_registry.get_factor(fid)
            if spec is None:
                continue
            feature_names.append(spec.factor_name)
            group = spec.factor_group
            if group not in feature_groups:
                feature_groups[group] = []
            if spec.factor_name not in feature_groups[group]:
                feature_groups[group].append(spec.factor_name)

        name = feature_set_name or f"{factor_set.name}_fs"

        return FeatureSetVersion(
            feature_set_id=factor_set.factor_set_id,
            name=name,
            feature_names=feature_names,
            feature_groups=feature_groups,
            version=factor_set.version,
            lookback_window=lookback_window,
            frequency=frequency,
            description=f"Exported from AlphaFactorSet {factor_set.name}",
            metadata={
                "alpha_set_id": factor_set.factor_set_id,
                "normalization_method": factor_set.normalization_method,
                "neutralization_method": factor_set.neutralization_method,
                "exported_at": datetime.now().isoformat(),
            },
        )

    def to_qlib_feature_csv(
        self,
        factor_values_df: pd.DataFrame,
        output_path: str,
    ) -> None:
        """
        Write factor values to Qlib-compatible CSV format.

        Parameters
        ----------
        factor_values_df : pd.DataFrame
            Columns: symbol, timestamp, raw_value[, normalized_value]
        output_path : str
            Path to write CSV.
        """
        # Qlib expects: symbol, timestamp, and factor columns
        # Pivot to wide format: one column per factor
        factor_values_df.to_csv(output_path, index=False)

    def clear(self) -> None:
        """Clear locally added factors (does not affect registry)."""
        self._local_factors.clear()
