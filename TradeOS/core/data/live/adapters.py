from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Optional

import pandas as pd

from core.schemas import (
    FundamentalsSnapshot,
    MacroEvent,
    MarketBar,
    NewsEvent,
    TimeFrame,
)


TIMEFRAME_ENUM_MAP = {
    "1m": TimeFrame.M1,
    "5m": TimeFrame.M5,
    "15m": TimeFrame.M15,
    "30m": TimeFrame.M30,
    "1h": TimeFrame.H1,
    "4h": TimeFrame.H4,
    "1d": TimeFrame.D1,
    "1w": TimeFrame.W1,
}


@dataclass(slots=True)
class AdapterResult:
    adapter: str
    payload: Any
    notes: list[str]
    placeholder_fields: list[str]


class YahooMarketAdapter:
    name = "YahooMarketAdapter"

    def to_bars(self, symbol: str, timeframe: str, frame: pd.DataFrame) -> AdapterResult:
        tf = TIMEFRAME_ENUM_MAP[timeframe]
        bars: list[MarketBar] = []
        for idx, row in frame.iterrows():
            ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            bars.append(
                MarketBar(
                    symbol=symbol,
                    timeframe=tf,
                    timestamp=ts,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row.get("Volume", 0.0)),
                    source="yfinance",
                )
            )
        return AdapterResult(
            adapter=self.name,
            payload=bars,
            notes=[],
            placeholder_fields=[],
        )


class YahooFundamentalAdapter:
    name = "YahooFundamentalAdapter"

    def to_snapshot(self, symbol: str, info: dict[str, Any]) -> AdapterResult:
        placeholder_fields: list[str] = []

        def read(*keys: str) -> Any:
            for key in keys:
                value = info.get(key)
                if value is not None:
                    return value
            placeholder_fields.append(keys[0])
            return None

        snapshot = FundamentalsSnapshot(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            market_cap=read("marketCap"),
            pe_ratio=read("trailingPE", "forwardPE"),
            pb_ratio=read("priceToBook"),
            ps_ratio=read("priceToSalesTrailing12Months"),
            peg_ratio=read("pegRatio"),
            revenue=read("totalRevenue"),
            ebitda=read("ebitda"),
            net_income=read("netIncomeToCommon"),
            total_assets=read("totalAssets"),
            total_debt=read("totalDebt"),
            eps=read("trailingEps"),
            book_value_per_share=read("bookValue"),
            dividend_yield=read("dividendYield"),
            beta=read("beta"),
            avg_volume_20d=read("averageVolume"),
        )
        return AdapterResult(
            adapter=self.name,
            payload=snapshot,
            notes=[],
            placeholder_fields=placeholder_fields,
        )


class YahooNewsAdapter:
    name = "YahooNewsAdapter"

    def to_news_events(self, symbol: str, raw_items: list[dict[str, Any]]) -> AdapterResult:
        events: list[NewsEvent] = []
        for item in raw_items:
            title = item.get("title") or item.get("content", {}).get("title")
            if not title:
                continue
            provider_publish = item.get("providerPublishTime")
            ts = datetime.fromtimestamp(provider_publish, tz=UTC) if provider_publish else datetime.now(UTC)
            summary = item.get("summary") or item.get("content", {}).get("summary", "")
            tickers = item.get("relatedTickers") or [symbol]
            score = None
            label = None
            lower = f"{title} {summary}".lower()
            if any(word in lower for word in ("beat", "surge", "growth", "upgrade", "record")):
                score, label = 0.6, "bullish"
            elif any(word in lower for word in ("miss", "drop", "cut", "downgrade", "lawsuit", "fall")):
                score, label = -0.6, "bearish"
            events.append(
                NewsEvent(
                    timestamp=ts,
                    title=title,
                    source=(item.get("publisher") or item.get("provider") or "Yahoo Finance"),
                    url=item.get("link") or item.get("canonicalUrl", {}).get("url"),
                    symbols=tickers,
                    sentiment_score=score,
                    sentiment_label=label,
                )
            )
        return AdapterResult(
            adapter=self.name,
            payload=events,
            notes=[],
            placeholder_fields=["sentiment_score"] if any(e.sentiment_score is None for e in events) else [],
        )


class FredMacroAdapter:
    name = "FredMacroAdapter"

    INDICATOR_META = {
        "DFF": ("US Fed Funds Rate", "US"),
        "DGS10": ("US 10Y Treasury Yield", "US"),
        "CPIAUCSL": ("US CPI", "US"),
        "UNRATE": ("US Unemployment Rate", "US"),
        "VIXCLS": ("CBOE VIX", "US"),
    }

    def to_macro_events(self, payload: dict[str, pd.DataFrame]) -> AdapterResult:
        events: list[MacroEvent] = []
        for series_id, frame in payload.items():
            if frame.empty:
                continue
            latest = frame.iloc[-1]
            previous = frame.iloc[-2] if len(frame) > 1 else latest
            event_name, country = self.INDICATOR_META.get(series_id, (series_id, "US"))
            actual = float(latest["value"])
            prev_value = float(previous["value"])
            surprise = actual != prev_value
            impact = "high" if series_id in {"DFF", "CPIAUCSL", "UNRATE", "VIXCLS"} else "medium"
            events.append(
                MacroEvent(
                    timestamp=latest["date"].to_pydatetime(),
                    event_name=event_name,
                    country=country,
                    impact=impact,
                    previous=prev_value,
                    forecast=None,
                    actual=actual,
                    affected_assets=["SPY", "QQQ", "TLT", "DXY", "GLD", "CL=F"],
                    is_surprise=surprise,
                )
            )
        return AdapterResult(
            adapter=self.name,
            payload=events,
            notes=[],
            placeholder_fields=["forecast"],
        )

    def macro_news_to_events(self, raw_items: list[dict[str, Any]]) -> AdapterResult:
        events: list[MacroEvent] = []
        for item in raw_items:
            content = item.get("content", {})
            title = item.get("title") or content.get("title")
            if not title:
                continue
            published = content.get("pubDate") or item.get("pubDate")
            ts = pd.to_datetime(published, utc=True).to_pydatetime() if published else datetime.now(UTC)
            summary = content.get("summary") or item.get("summary") or ""
            lowered = f"{title} {summary}".lower()
            impact = "high" if any(word in lowered for word in ("fed", "inflation", "treasury", "yield", "oil", "war")) else "medium"
            events.append(
                MacroEvent(
                    timestamp=ts,
                    event_name=title,
                    country="US",
                    impact=impact,
                    previous=None,
                    forecast=None,
                    actual=None,
                    affected_assets=["SPY", "QQQ", "TLT", "DXY", "GLD", "CL=F"],
                    is_surprise=None,
                )
            )
        return AdapterResult(
            adapter=f"{self.name}News",
            payload=events,
            notes=[],
            placeholder_fields=["previous", "forecast", "actual"],
        )
