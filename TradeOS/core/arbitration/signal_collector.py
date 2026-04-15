"""
Signal Collector
===============

从六大分析模块汇总信号，构建 SignalBundle。
负责时间对齐和缺失信号处理。
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from core.arbitration.schemas import SignalBundle

if TYPE_CHECKING:
    from core.analysis.fundamental.report import FundamentalReport
    from core.schemas import (
        ChanSignal,
        MacroSignal,
        OrderFlowSignal,
        SentimentEvent,
        TechnicalSignal,
    )


class SignalCollector:
    """
    信号收集器。

    职责：
    1. 接收六大分析模块的输出
    2. 统一时间戳
    3. 构建 SignalBundle

    所有信号均为 Optional，缺失时不阻塞。
    """

    def collect(
        self,
        symbol: str,
        timestamp: datetime | None = None,
        technical: Optional["TechnicalSignal"] = None,
        chan: Optional["ChanSignal"] = None,
        orderflow: Optional["OrderFlowSignal"] = None,
        sentiment: Optional["SentimentEvent"] = None,
        macro: Optional["MacroSignal"] = None,
        fundamental: Optional["FundamentalReport"] = None,
    ) -> SignalBundle:
        """
        收集并打包信号。

        Args:
            symbol:       标的代码
            timestamp:    统一时间戳（默认当前 UTC）
            technical:    技术分析信号
            chan:         缠论信号
            orderflow:    订单流信号
            sentiment:    情绪信号
            macro:       宏观信号
            fundamental:  基本盘报表

        Returns:
            SignalBundle
        """
        start = time.perf_counter()
        ts = timestamp or datetime.utcnow()

        bundle = SignalBundle(
            timestamp=ts,
            symbol=symbol,
            technical=technical,
            chan=chan,
            orderflow=orderflow,
            sentiment=sentiment,
            macro=macro,
            fundamental=fundamental,
            collection_latency_ms=(time.perf_counter() - start) * 1000,
        )
        return bundle
