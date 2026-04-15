"""
Labels Module
=============
Label builders for supervised learning.

Submodules:
    schema.py    - LabelSpec, LabelResult, LabelSetResult
    base.py      - ILabelBuilder, ForwardReturnLabel, DirectionLabel
    returns.py   - ReturnLabelBuilder, ExcessReturnLabelBuilder
    direction.py - DirectionLabelBuilder, TernaryDirectionLabelBuilder
    risk.py      - MaxDrawdownLabelBuilder, VolatilityPercentileLabelBuilder, VaRBreachLabelBuilder
"""

from .schema import (
    LabelSpec,
    LabelResult,
    LabelSetResult,
)

from .base import (
    ILabelBuilder,
    ForwardReturnLabel,
    DirectionLabel,
)

from .returns import (
    ReturnLabelBuilder,
    ExcessReturnLabelBuilder,
    build_return_labels,
)

from .direction import (
    DirectionLabelBuilder,
    TernaryDirectionLabelBuilder,
    build_direction_labels,
)

from .risk import (
    MaxDrawdownLabelBuilder,
    VolatilityPercentileLabelBuilder,
    VaRBreachLabelBuilder,
    build_risk_labels,
)

__all__ = [
    # Schema
    "LabelSpec",
    "LabelResult",
    "LabelSetResult",
    # Base
    "ILabelBuilder",
    "ForwardReturnLabel",
    "DirectionLabel",
    # Returns
    "ReturnLabelBuilder",
    "ExcessReturnLabelBuilder",
    "build_return_labels",
    # Direction
    "DirectionLabelBuilder",
    "TernaryDirectionLabelBuilder",
    "build_direction_labels",
    # Risk
    "MaxDrawdownLabelBuilder",
    "VolatilityPercentileLabelBuilder",
    "VaRBreachLabelBuilder",
    "build_risk_labels",
]
