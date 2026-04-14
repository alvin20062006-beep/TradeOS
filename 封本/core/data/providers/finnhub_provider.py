"""
core/data/providers/finnhub_provider.py — Finnhub 实时行情 Provider

数据源：Finnhub.io
支持：股票、ETF、大宗商品、外汇实时/历史数据
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from core.data.providers.base import BaseProvider, MarketData, Quote


class FinnhubProvider(BaseProvider):
    """Finnhub 数据Provider"""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY", "d69biahr01qjmno4n1t0d69biahr01qjmno4n1tg")

    @property
    def name(self) -> str:
        return "finnhub"

    def get_quote(self, symbol: str) -> Optional[Quote]:
        """获取实时报价"""
        try:
            r = requests.get(
                f"{self.BASE_URL}/quote",
                params={"symbol": symbol, "token": self.api_key},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("c") is None:  # 无数据
                return None
            return Quote(
                symbol=symbol,
                last=data.get("c", 0),
                open=data.get("o", 0),
                high=data.get("h", 0),
                low=data.get("l", 0),
                volume=data.get("v", 0),
                timestamp=datetime.now(),
            )
        except Exception as e:
            print(f"[Finnhub] get_quote {symbol} failed: {e}")
            return None

    def get_ohlcv(
        self,
        symbol: str,
        interval: str = "D",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional[pd.DataFrame]:
        """
        获取历史K线数据
        
        interval: D=日, W=周, M=月, 1=1分钟, 5=5分钟, 15=15分钟, 30=30分钟, 60=60分钟
        """
        try:
            # Finnhub stock candle API
            resolution = self._map_interval(interval)
            params = {
                "symbol": symbol,
                "resolution": resolution,
                "token": self.api_key,
            }
            if start:
                params["from"] = int(start.timestamp())
            if end:
                params["to"] = int(end.timestamp())

            r = requests.get(
                f"{self.BASE_URL}/stock/candle",
                params=params,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()

            if data.get("s") != "ok" or not data.get("c"):
                return None

            df = pd.DataFrame({
                "timestamp": pd.to_datetime(data["t"], unit="s"),
                "open": data["o"],
                "high": data["h"],
                "low": data["l"],
                "close": data["c"],
                "volume": data["v"],
            })
            df.set_index("timestamp", inplace=True)
            return df

        except Exception as e:
            print(f"[Finnhub] get_ohlcv {symbol} failed: {e}")
            return None

    def get_company_info(self, symbol: str) -> Optional[dict]:
        """获取公司基本信息"""
        try:
            r = requests.get(
                f"{self.BASE_URL}/stock/profile2",
                params={"symbol": symbol, "token": self.api_key},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            if not data.get("name"):
                return None
            return data
        except Exception as e:
            print(f"[Finnhub] get_company_info {symbol} failed: {e}")
            return None

    def get_market_news(self, category: str = "general") -> list[dict]:
        """获取市场新闻"""
        try:
            r = requests.get(
                f"{self.BASE_URL}/news",
                params={"category": category, "token": self.api_key},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[Finnhub] get_market_news failed: {e}")
            return []

    def _map_interval(self, interval: str) -> str:
        """将通用 interval 映射到 Finnhub resolution"""
        mapping = {
            "1m": "1",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "D": "D",
            "W": "W",
            "M": "M",
        }
        return mapping.get(interval.upper(), "D")


# 全局实例
_finnhub: Optional[FinnhubProvider] = None


def get_finnhub() -> FinnhubProvider:
    """获取全局 Finnhub Provider 实例"""
    global _finnhub
    if _finnhub is None:
        _finnhub = FinnhubProvider()
    return _finnhub
