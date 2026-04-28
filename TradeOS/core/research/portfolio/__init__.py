"""core.research.portfolio: research-layer portfolio optimization."""

from core.research.portfolio.schema import (
    ConstraintConfig,
    OptimizationRequest,
    OptimizationResult,
)

__all__ = [
    "ConstraintConfig",
    "OptimizationRequest",
    "OptimizationResult",
    "PortfolioOptimizer",
]


def __getattr__(name: str):
    """Load the cvxpy-backed optimizer only when it is explicitly requested."""
    if name == "PortfolioOptimizer":
        from core.research.portfolio.optimizer import PortfolioOptimizer

        return PortfolioOptimizer
    raise AttributeError(name)
