"""
Filter Schema Definitions
=========================
Unified schema for all filter modules.

Defines:
    FilterResult        - Single filter pass/fail result
    RegulatoryFlag      - Regulatory status flags (limit_up, limit_down, suspended, ST)
    MarketRegimeResult  - Market regime detection result
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# RegulatoryFlag
# ─────────────────────────────────────────────────────────────────


class RegulatoryFlag(str, Enum):
    """
    Regulatory status flags for a security.

    These flags indicate trading restrictions or special status.
    """
    LIMIT_UP = "limit_up"           # 涨停
    LIMIT_DOWN = "limit_down"       # 跌停
    SUSPENDED = "suspended"         # 停牌
    ST = "st"                       # ST标记
    DELISTING = "delisting"         # 退市风险
    NEW_LISTING = "new_listing"     # 新股（上市不足N天）
    LOW_LIQUIDITY = "low_liquidity" # 流动性不足


# ─────────────────────────────────────────────────────────────────
# FilterResult
# ─────────────────────────────────────────────────────────────────


class FilterResult(BaseModel):
    """
    Result of a single filter check.

    Attributes
    ----------
    passed : bool
        Whether the item passed the filter.
    filter_name : str
        Name of the filter that produced this result.
    reasons : list[str]
        List of reasons for failure (empty if passed).
    metadata : dict
        Additional context (e.g., threshold values, actual values).
    """

    passed: bool
    filter_name: str
    reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __and__(self, other: "FilterResult") -> "FilterResult":
        """Combine two filters with AND logic."""
        return FilterResult(
            passed=self.passed and other.passed,
            filter_name=f"{self.filter_name}&{other.filter_name}",
            reasons=self.reasons + other.reasons,
            metadata={**self.metadata, **other.metadata},
        )

    def __or__(self, other: "FilterResult") -> "FilterResult":
        """Combine two filters with OR logic."""
        return FilterResult(
            passed=self.passed or other.passed,
            filter_name=f"{self.filter_name}|{other.filter_name}",
            reasons=[] if (self.passed or other.passed) else self.reasons + other.reasons,
            metadata={**self.metadata, **other.metadata},
        )


# ─────────────────────────────────────────────────────────────────
# MarketRegimeResult
# ─────────────────────────────────────────────────────────────────


class MarketRegime(str, Enum):
    """Market regime classification."""
    TREND_UP = "trend_up"       # 上升趋势
    TREND_DOWN = "trend_down"   # 下降趋势
    RANGE = "range"             # 震荡
    CRISIS = "crisis"           # 危机/恐慌
    RECOVERY = "recovery"       # 反弹/修复
    UNKNOWN = "unknown"         # 无法判断


class MarketRegimeResult(BaseModel):
    """
    Result of market regime detection.

    Attributes
    ----------
    regime : MarketRegime
        Detected market regime.
    confidence : float
        Confidence level 0~1.
    indicators : dict
        Supporting indicators (e.g., trend_slope, volatility_percentile).
    timestamp : datetime
        Time of detection.
    """

    regime: MarketRegime = MarketRegime.UNKNOWN
    confidence: float = 0.0
    indicators: dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None

    class Config:
        use_enum_values = True


# ─────────────────────────────────────────────────────────────────
# CompositeFilterResult
# ─────────────────────────────────────────────────────────────────


class CompositeFilterResult(BaseModel):
    """
    Result of applying multiple filters.

    Attributes
    ----------
    passed : bool
        Overall pass status (all filters passed).
    filter_results : list[FilterResult]
        Individual filter results.
    failed_filters : list[str]
        Names of filters that failed.
    """

    passed: bool
    filter_results: list[FilterResult] = Field(default_factory=list)
    failed_filters: list[str] = Field(default_factory=list)

    @classmethod
    def from_results(cls, results: list[FilterResult]) -> "CompositeFilterResult":
        """Create from a list of FilterResult."""
        failed = [r.filter_name for r in results if not r.passed]
        return cls(
            passed=len(failed) == 0,
            filter_results=results,
            failed_filters=failed,
        )
