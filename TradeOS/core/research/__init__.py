"""Lazy exports for the research package.

This module intentionally avoids importing heavy alpha/research dependencies
at import time so availability/config checks can run without pandas/numpy/qlib.
"""

from __future__ import annotations

from importlib import import_module

_EXPORTS: dict[str, tuple[str, str]] = {
    "DatasetVersion": ("core.research.models", "DatasetVersion"),
    "FeatureSetVersion": ("core.research.models", "FeatureSetVersion"),
    "LabelSetVersion": ("core.research.models", "LabelSetVersion"),
    "ResearchExperimentRecord": ("core.research.models", "ResearchExperimentRecord"),
    "ModelArtifact": ("core.research.models", "ModelArtifact"),
    "DeploymentCandidate": ("core.research.models", "DeploymentCandidate"),
    "SignalCandidate": ("core.research.models", "SignalCandidate"),
    "AlphaFactorSpec": ("core.research.alpha.models", "AlphaFactorSpec"),
    "AlphaFactorValue": ("core.research.alpha.models", "AlphaFactorValue"),
    "AlphaFactorSet": ("core.research.alpha.models", "AlphaFactorSet"),
    "AlphaValidationResult": ("core.research.alpha.models", "AlphaValidationResult"),
    "CompositeFactor": ("core.research.alpha.models", "CompositeFactor"),
    "ExperimentRegistry": ("core.research.registry", "ExperimentRegistry"),
    "AlphaFactor": ("core.research.alpha.base", "AlphaFactor"),
    "AlphaRegistry": ("core.research.alpha.registry", "AlphaRegistry"),
    "AlphaNormalizer": ("core.research.alpha.normalization", "AlphaNormalizer"),
    "AlphaValidator": ("core.research.alpha.validation", "AlphaValidator"),
    "AlphaExporter": ("core.research.alpha.export", "AlphaExporter"),
    "ILabelBuilder": ("core.research.labels.base", "ILabelBuilder"),
    "ForwardReturnLabel": ("core.research.labels.base", "ForwardReturnLabel"),
    "DirectionLabel": ("core.research.labels.base", "DirectionLabel"),
    "EvaluationMetrics": ("core.research.evaluation.metrics", "EvaluationMetrics"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
