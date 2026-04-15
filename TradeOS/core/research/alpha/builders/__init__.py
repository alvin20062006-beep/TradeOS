"""
Alpha Builders package.

Submodules:
    technical.py   - L1 raw technical factors (RET, VOL, RSI, MACD, BB, etc.)
    fundamentals.py - L1 raw fundamental factors (PE_RANK, PB_RANK, ROE_TTM)
    sentiment.py   - L1 raw sentiment proxy (VOL_SURPRISE)
    composite.py   - L3 multi-factor combination (equal_weight, ic_weighted, rank_average)
    macro.py       - L1 macro proxy factors (RATE_DELTA, VOL_TREND, YIELD_SPREAD)
    orderflow.py   - L1 orderflow proxy factors (VWAP_DEV, VWAP_SLOPE, VOL_CONCENTRATION)
    regulatory.py  - Regulatory flag detection (limit_up/down, suspended, ST)
"""

from .technical import (
    TECHNICAL_FACTORS,
    TECHNICAL_FACTOR_NAMES,
    build_all_technical,
)

from .fundamentals import (
    FUNDAMENTAL_FACTORS,
    FUNDAMENTAL_FACTOR_NAMES,
    build_all_fundamental,
)

from .sentiment import (
    SENTIMENT_FACTORS,
    SENTIMENT_FACTOR_NAMES,
    build_all_sentiment,
)

from .composite import (
    COMPOSITE_METHODS,
    build_composite,
    build_equal_weight,
    build_ic_weighted,
    build_rank_average,
)

from .macro import (
    RateDeltaBuilder,
    VolTrendBuilder,
    YieldSpreadBuilder,
    all_macro_builders,
    build_all_macro,
)

from .orderflow import (
    VWAPDeviationBuilder,
    VWAPSlopeBuilder,
    VolumeConcentrationBuilder,
    all_orderflow_builders,
    build_all_orderflow,
)

from .regulatory import (
    RegulatoryFlagBuilder,
    detect_regulatory_flags,
    is_tradable,
)

__all__ = [
    # Technical
    "TECHNICAL_FACTORS",
    "TECHNICAL_FACTOR_NAMES",
    "build_all_technical",
    # Fundamentals
    "FUNDAMENTAL_FACTORS",
    "FUNDAMENTAL_FACTOR_NAMES",
    "build_all_fundamental",
    # Sentiment
    "SENTIMENT_FACTORS",
    "SENTIMENT_FACTOR_NAMES",
    "build_all_sentiment",
    # Composite
    "COMPOSITE_METHODS",
    "build_composite",
    "build_equal_weight",
    "build_ic_weighted",
    "build_rank_average",
    # Macro
    "RateDeltaBuilder",
    "VolTrendBuilder",
    "YieldSpreadBuilder",
    "all_macro_builders",
    "build_all_macro",
    # Orderflow
    "VWAPDeviationBuilder",
    "VWAPSlopeBuilder",
    "VolumeConcentrationBuilder",
    "all_orderflow_builders",
    "build_all_orderflow",
    # Regulatory
    "RegulatoryFlagBuilder",
    "detect_regulatory_flags",
    "is_tradable",
]
