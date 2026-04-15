"""
AlphaFactor Abstract Base
========================
All alpha factor builders must implement this interface.

Provides a uniform contract:
    1. build()       -> AlphaFactorSpec (definition)
    2. compute()      -> DataFrame[symbol, timestamp, raw_value]
    3. validate()     -> AlphaValidationResult
    4. normalize()    -> DataFrame[symbol, timestamp, normalized_value]
    5. to_spec()     -> AlphaFactorSpec (final registered spec)
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

import pandas as pd

from .models import (
    AlphaFactorSpec,
    AlphaFactorValue,
    AlphaValidationResult,
)


class AlphaFactor(ABC):
    """
    Abstract base for all alpha factor builders.

    Subclasses must implement the compute() method.
    build() and validate() have default implementations that work
    for simple factors; override if custom behaviour is needed.
    """

    def __init__(
        self,
        factor_name: str,
        factor_group: str,
        source_module: str,
        formula_description: str = "",
        parameters: Optional[dict[str, Any]] = None,
    ):
        self.factor_name = factor_name
        self.factor_group = factor_group
        self.source_module = source_module
        self.formula_description = formula_description
        self.parameters = parameters or {}
        self._spec: Optional[AlphaFactorSpec] = None

    # ── Interface ──────────────────────────────────────────────

    @abstractmethod
    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute raw L1 factor values.

        Parameters
        ----------
        data : pd.DataFrame
            Must contain, at minimum, the columns declared in input_fields.
            Index should be (symbol, timestamp) or a DatetimeIndex per symbol.

        Returns
        -------
        pd.DataFrame
            Columns: symbol, timestamp, raw_value
            raw_value is the L1 (raw) factor value.
        """
        ...

    # ── Default implementations ────────────────────────────────

    def build(self) -> AlphaFactorSpec:
        """
        Build the AlphaFactorSpec for this factor.
        """
        if self._spec is None:
            self._spec = AlphaFactorSpec(
                factor_name=self.factor_name,
                factor_group=self.factor_group,
                source_module=self.source_module,
                formula_description=self.formula_description,
                parameters=self.parameters,
                input_fields=self.input_fields,
                output_type="float",
                layer="L1",
            )
        return self._spec

    def to_spec(self) -> AlphaFactorSpec:
        """
        Return the registered spec (builds if not yet built).
        """
        return self.build()

    def validate(
        self, data: pd.DataFrame, factor_values: Optional[pd.DataFrame] = None
    ) -> AlphaValidationResult:
        """
        Run quality checks on computed factor values.

        Parameters
        ----------
        data : pd.DataFrame
            Original OHLCV bar data.
        factor_values : pd.DataFrame, optional
            Output of compute(). If None, compute() is called first.

        Returns
        -------
        AlphaValidationResult
        """
        from .validation import AlphaValidator

        if factor_values is None:
            factor_values = self.compute(data)

        validator = AlphaValidator()
        result = validator.validate_single(
            factor_id=self.build().factor_id,
            factor_values=factor_values,
        )
        return result

    # ── Properties ────────────────────────────────────────────

    @property
    def input_fields(self) -> list[str]:
        """
        Columns required in the input DataFrame.
        Override in subclass if custom columns are needed.
        """
        return ["close"]

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"factor_name={self.factor_name!r}, "
            f"group={self.factor_group!r}, "
            f"params={self.parameters})"
        )
