from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import pandas as pd
import requests
import yfinance as yf


YF_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "4h": "1h",
    "1d": "1d",
    "1w": "1wk",
}


@dataclass(slots=True)
class ProviderFetchResult:
    provider: str
    payload: Any
    notes: list[str]


class YahooFinanceLiveProvider:
    """Real market/fundamental/news provider backed by Yahoo Finance."""

    name = "yfinance"

    def fetch_bars(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> ProviderFetchResult:
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start,
            end=end,
            interval=YF_INTERVAL_MAP.get(interval, interval),
            auto_adjust=False,
            actions=False,
        )
        if df.empty:
            raise ValueError(f"No bars returned for {symbol} [{interval}]")
        return ProviderFetchResult(provider=self.name, payload=df, notes=[])

    def fetch_fundamentals(self, symbol: str) -> ProviderFetchResult:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        if not info:
            raise ValueError(f"No fundamentals returned for {symbol}")
        return ProviderFetchResult(provider=self.name, payload=info, notes=[])

    def fetch_news(self, symbol: str, limit: int = 10) -> ProviderFetchResult:
        ticker = yf.Ticker(symbol)
        news = getattr(ticker, "news", None) or []
        return ProviderFetchResult(
            provider=self.name,
            payload=news[:limit],
            notes=[],
        )

    def fetch_recent_intraday(self, symbol: str, minutes: int = 120) -> ProviderFetchResult:
        end = datetime.now(UTC)
        start = end - timedelta(days=7)
        result = self.fetch_bars(symbol=symbol, interval="1m", start=start, end=end)
        df = result.payload.tail(minutes)
        if df.empty:
            raise ValueError(f"No intraday bars returned for {symbol}")
        return ProviderFetchResult(provider=self.name, payload=df, notes=result.notes)


class FredMacroProvider:
    """Real macro indicator provider backed by public FRED CSV endpoints."""

    name = "fred_public_csv"
    BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

    INDICATORS = {
        "DFF": ("US Fed Funds Rate", "US"),
        "DGS10": ("US 10Y Treasury Yield", "US"),
        "CPIAUCSL": ("US CPI", "US"),
        "UNRATE": ("US Unemployment Rate", "US"),
        "VIXCLS": ("CBOE VIX", "US"),
    }

    def fetch_indicator(self, series_id: str, lookback_rows: int = 3) -> ProviderFetchResult:
        response = requests.get(
            self.BASE_URL,
            params={"id": series_id},
            timeout=20,
        )
        response.raise_for_status()
        frame = pd.read_csv(io.StringIO(response.text))
        frame = frame.dropna()
        if frame.empty:
            raise ValueError(f"No FRED data for {series_id}")
        date_col = "DATE" if "DATE" in frame.columns else frame.columns[0]
        value_col = series_id if series_id in frame.columns else frame.columns[-1]
        frame = frame[[date_col, value_col]].copy()
        frame.columns = ["date", "value"]
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        frame = frame.dropna().tail(lookback_rows)
        return ProviderFetchResult(provider=self.name, payload=frame, notes=[])

    def fetch_macro_bundle(self) -> ProviderFetchResult:
        payload: dict[str, pd.DataFrame] = {}
        notes: list[str] = []
        for series_id in self.INDICATORS:
            try:
                payload[series_id] = self.fetch_indicator(series_id).payload
            except Exception as exc:
                notes.append(f"{series_id} unavailable: {exc}")
        if not payload:
            raise ValueError("No macro indicators fetched from FRED")
        return ProviderFetchResult(provider=self.name, payload=payload, notes=notes)
