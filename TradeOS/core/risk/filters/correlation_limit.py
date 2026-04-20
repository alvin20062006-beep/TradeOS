"""Correlation limit filter."""

from __future__ import annotations

from core.risk.filters.base import FilterResult, RiskFilter


class CorrelationLimitFilter(RiskFilter):
    """Reduce same-direction exposure when correlation breaches the threshold."""

    name = "max_correlation"

    def _filter(
        self,
        qty,
        direction_sign,
        risk_limits=None,
        symbol: str | None = None,
        existing_position_symbols=None,
        existing_directions=None,
        correlation_matrix=None,
        correlation_value: float | None = None,
        **kwargs,
    ):
        if risk_limits is None:
            return FilterResult(True, qty, True, "pass", "no risk limits configured")

        max_corr = float(getattr(risk_limits, "max_correlation", 0.0) or 0.0)
        if max_corr <= 0:
            return FilterResult(True, qty, True, "pass", "max_correlation disabled")

        resolved_corr = correlation_value
        if resolved_corr is None and correlation_matrix and symbol and existing_position_symbols:
            for existing_symbol in existing_position_symbols:
                pair_value = correlation_matrix.get((symbol, existing_symbol))
                if pair_value is None:
                    pair_value = correlation_matrix.get((existing_symbol, symbol))
                if pair_value is not None:
                    resolved_corr = max(abs(float(pair_value)), abs(float(resolved_corr or 0.0)))

        if resolved_corr is None:
            return FilterResult(True, qty, True, "pass", "no correlation data")

        abs_corr = abs(float(resolved_corr))
        if abs_corr <= max_corr:
            return FilterResult(
                True,
                qty,
                True,
                "pass",
                f"correlation {abs_corr:.3f} within threshold {max_corr:.3f}",
            )

        same_direction = True
        if existing_directions:
            same_direction = any(int(existing_dir) == int(direction_sign) for existing_dir in existing_directions if existing_dir in (-1, 1))

        if not same_direction:
            return FilterResult(
                True,
                qty,
                True,
                "pass",
                f"correlation {abs_corr:.3f} breached but exposure offsets existing positions",
            )

        overflow_ratio = min((abs_corr - max_corr) / max(1.0 - max_corr, 1e-6), 1.0)
        reduction_ratio = max(0.25, 1.0 - overflow_ratio)
        adjusted_qty = round(float(qty) * reduction_ratio, 6)

        if adjusted_qty <= 0:
            return FilterResult(
                False,
                0.0,
                False,
                "veto",
                f"correlation {abs_corr:.3f} exceeds threshold {max_corr:.3f}; vetoed",
            )

        return FilterResult(
            True,
            adjusted_qty,
            False,
            "cap",
            f"correlation {abs_corr:.3f} exceeds threshold {max_corr:.3f}; qty reduced to {adjusted_qty}",
        )
