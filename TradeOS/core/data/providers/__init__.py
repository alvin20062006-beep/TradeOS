"""Provider exports.

Finnhub is optional and depends on a legacy provider contract, so it is not
loaded during normal Phase 1 data imports.
"""

from core.data.providers.yfinance_provider import YahooFinanceProvider
from core.data.providers.csv_provider import CSVProvider

__all__ = ["YahooFinanceProvider", "CSVProvider", "FinnhubProvider"]


def __getattr__(name: str):
    if name == "FinnhubProvider":
        from core.data.providers.finnhub_provider import FinnhubProvider

        return FinnhubProvider
    raise AttributeError(name)
