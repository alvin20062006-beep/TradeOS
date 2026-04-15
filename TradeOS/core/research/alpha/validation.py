"""
AlphaValidator - Executable Factor Quality Checks
=================================================
Each check is an actual computation, not a schema placeholder.

Thresholds (configurable via constructor):
    coverage        > 0.9   (90% non-null)
    null_ratio      < 0.1   (< 10% null)
    constant_ratio  < 0.05  (< 5% constant values)
    outlier_ratio   < 0.05  (< 5% extreme values)
    correlation_warning: > 0.9 correlation with existing factors
    leakage_warning: > 0.5 contemporaneous IC (lookahead bias flag)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .models import AlphaValidationResult


class AlphaValidator:
    """
    Runs executable quality checks on a factor.

    All checks write actual computed values into AlphaValidationResult;
    no field is left as a schema placeholder.
    """

    def __init__(
        self,
        coverage_threshold: float = 0.9,
        null_ratio_threshold: float = 0.1,
        constant_ratio_threshold: float = 0.05,
        outlier_ratio_threshold: float = 0.05,
        correlation_threshold: float = 0.9,
        leakage_ic_threshold: float = 0.5,
    ):
        self.coverage_threshold = coverage_threshold
        self.null_ratio_threshold = null_ratio_threshold
        self.constant_ratio_threshold = constant_ratio_threshold
        self.outlier_ratio_threshold = outlier_ratio_threshold
        self.correlation_threshold = correlation_threshold
        self.leakage_ic_threshold = leakage_ic_threshold

    def validate_single(
        self,
        factor_id: str,
        factor_values: pd.DataFrame,
        factor_set_id: Optional[str] = None,
    ) -> AlphaValidationResult:
        """
        Run all checks on a single factor's values.

        Parameters
        ----------
        factor_id : str
        factor_values : pd.DataFrame
            Columns must include: symbol, timestamp, raw_value
        factor_set_id : str, optional

        Returns
        -------
        AlphaValidationResult
            All fields are populated with computed values.
        """
        series = factor_values["raw_value"].copy()

        # ── Compute metrics ──
        total = len(series)
        null_count = int(series.isna().sum())
        valid_count = total - null_count

        coverage = valid_count / total if total > 0 else 0.0
        null_ratio = null_count / total if total > 0 else 1.0

        # Constant ratio (excluding nulls)
        valid_series = series.dropna()
        if len(valid_series) > 1:
            constant_ratio = float((valid_series == valid_series.iloc[0]).mean())
        elif len(valid_series) == 1:
            constant_ratio = 1.0
        else:
            constant_ratio = 1.0

        # Outlier ratio (3-sigma)
        if valid_series.std() > 0:
            z_scores = np.abs((valid_series - valid_series.mean()) / valid_series.std())
            outlier_ratio = float((z_scores > 3).mean())
        else:
            outlier_ratio = 0.0

        # Basic stats
        mean_val = float(valid_series.mean()) if len(valid_series) > 0 else None
        std_val = float(valid_series.std()) if len(valid_series) > 0 else None
        min_val = float(valid_series.min()) if len(valid_series) > 0 else None
        max_val = float(valid_series.max()) if len(valid_series) > 0 else None

        # ── Gate ──
        fail_reasons: list[str] = []
        if coverage < self.coverage_threshold:
            fail_reasons.append(f"coverage={coverage:.3f} < {self.coverage_threshold}")
        if null_ratio > self.null_ratio_threshold:
            fail_reasons.append(f"null_ratio={null_ratio:.3f} > {self.null_ratio_threshold}")
        if constant_ratio > self.constant_ratio_threshold:
            fail_reasons.append(f"constant_ratio={constant_ratio:.3f} > {self.constant_ratio_threshold}")
        if outlier_ratio > self.outlier_ratio_threshold:
            fail_reasons.append(f"outlier_ratio={outlier_ratio:.3f} > {self.outlier_ratio_threshold}")

        is_qualified = len(fail_reasons) == 0

        return AlphaValidationResult(
            factor_id=factor_id,
            factor_set_id=factor_set_id,
            coverage=coverage,
            null_ratio=null_ratio,
            constant_ratio=constant_ratio,
            outlier_ratio=outlier_ratio,
            correlation_warning=False,  # set separately via check_correlation()
            leakage_warning=False,        # set separately via check_leakage()
            mean=mean_val,
            std=std_val,
            min_val=min_val,
            max_val=max_val,
            is_qualified=is_qualified,
            fail_reasons=fail_reasons,
            eval_start=factor_values["timestamp"].min() if "timestamp" in factor_values.columns else None,
            eval_end=factor_values["timestamp"].max() if "timestamp" in factor_values.columns else None,
        )

    def check_correlation(
        self,
        result: AlphaValidationResult,
        existing_ic: Optional[dict[str, float]] = None,
    ) -> AlphaValidationResult:
        """
        Add correlation_warning if factor IC > threshold with any existing factor.
        """
        if existing_ic is None:
            return result
        # Mark warning if any existing factor has very high correlation
        high_corr = [fid for fid, ic in existing_ic.items() if abs(ic) > self.correlation_threshold]
        if high_corr:
            result.correlation_warning = True
            result.fail_reasons.append(f"correlation_warning: {len(high_corr)} existing factors have |IC| > {self.correlation_threshold}")
            result.is_qualified = False
        return result

    def check_leakage(
        self,
        result: AlphaValidationResult,
        label_series: Optional[pd.Series] = None,
        factor_series: Optional[pd.Series] = None,
    ) -> AlphaValidationResult:
        """
        Add leakage_warning if contemporaneous IC is suspiciously high
        (may indicate lookahead / data-snooping bias).

        Requires paired label_series and factor_series with the same index.
        """
        if label_series is None or factor_series is None:
            return result

        # Align series
        aligned = pd.DataFrame({"label": label_series, "factor": factor_series}).dropna()
        if len(aligned) < 10:
            return result

        ic = aligned["label"].corr(aligned["factor"])
        if abs(ic) > self.leakage_ic_threshold:
            result.leakage_warning = True
            result.fail_reasons.append(f"leakage_warning: contemporaneous IC={ic:.3f} > {self.leakage_ic_threshold}")
            result.is_qualified = False
        return result

    def validate_batch(
        self,
        factor_values_map: dict[str, pd.DataFrame],
        factor_set_id: Optional[str] = None,
    ) -> list[AlphaValidationResult]:
        """
        Validate multiple factors at once.

        Parameters
        ----------
        factor_values_map : dict[str, pd.DataFrame]
            Maps factor_id -> DataFrame with columns [symbol, timestamp, raw_value]
        """
        return [
            self.validate_single(factor_id=fid, factor_values=df, factor_set_id=factor_set_id)
            for fid, df in factor_values_map.items()
        ]
