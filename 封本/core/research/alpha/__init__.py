"""
core.research.alpha
==================
Research layer: alpha factors (generation, evaluation, risk, selection).

Sub-packages
------------
builders    Factor builders (technical / fundamentals / sentiment)
evaluation  Factor-level evaluation metrics
risk        Factor risk exposure analysis
selection   Factor selection and pruning
"""

from core.research.alpha.builders.multi_factor import MultiFactorBuilder
from core.research.alpha.evaluation.metrics import FactorMetrics, FactorMetricsBundle
from core.research.alpha.risk.factors import FactorRiskAnalysis
from core.research.alpha.selection.selector import FactorSelector

__all__ = [
    "MultiFactorBuilder",
    "FactorMetrics",
    "FactorMetricsBundle",
    "FactorRiskAnalysis",
    "FactorSelector",
]
