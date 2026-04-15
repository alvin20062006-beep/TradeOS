"""
新闻情绪分析模块
================

提取新闻标题/文本的情绪。

⚠️ Proxy 版本: 当无真实文本源时，从 OHLCV bars 合成代理信号。
Proxy 方法: 用日收益方向 + 成交量异动作为情绪代理
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.schemas import NewsEvent


@dataclass
class NewsSentiment:
    """新闻情绪指标."""
    news_sentiment: float       # -1 (强烈看空) ~ 1 (强烈看多)
    sentiment_label: str        # "bullish" | "bearish" | "neutral"
    confidence: float           # 0-1
    sources_count: int          # 来源数量
    
    def __repr__(self):
        return f"NewsSentiment(score={self.news_sentiment:.2f}, label={self.sentiment_label})"


def analyze_news_sentiment(events: list[NewsEvent]) -> NewsSentiment:
    """
    从 NewsEvent 列表提取综合情绪.
    
    Args:
        events: NewsEvent 列表
        
    Returns:
        NewsSentiment
    """
    if not events:
        return NewsSentiment(
            news_sentiment=0.0,
            sentiment_label="neutral",
            confidence=0.0,
            sources_count=0,
        )

    scores = [e.sentiment_score for e in events if e.sentiment_score is not None]
    
    if not scores:
        return NewsSentiment(
            news_sentiment=0.0,
            sentiment_label="neutral",
            confidence=0.0,
            sources_count=len(events),
        )

    # 加权平均（按时间新鲜度？简化：简单平均）
    avg_score = sum(scores) / len(scores)
    
    # 标签
    if avg_score > 0.2:
        label = "bullish"
    elif avg_score < -0.2:
        label = "bearish"
    else:
        label = "neutral"

    # 置信度 = 一致性（标准差反向）
    consistency = 1.0 - min(1.0, np.std(scores) * 2)

    return NewsSentiment(
        news_sentiment=round(avg_score, 3),
        sentiment_label=label,
        confidence=round(consistency, 3),
        sources_count=len(events),
    )


def proxy_news_sentiment_from_returns(
    closes: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 20,
) -> NewsSentiment:
    """
    从 OHLCV bars 估算新闻情绪（Proxy 方法）.
    
    Proxy:
    - 近期上涨 → bullish
    - 近期下跌 → bearish
    - 成交量放大 → 增强 confidence
    
    Args:
        closes: 收盘价序列
        volumes: 成交量序列
        lookback: 回看窗口
        
    Returns:
        NewsSentiment
    """
    n = len(closes)
    if n < lookback:
        return NewsSentiment(
            news_sentiment=0.0,
            sentiment_label="neutral",
            confidence=0.0,
            sources_count=0,
        )

    # 最近 lookback 根的收益
    recent_closes = closes[-lookback:]
    recent_volumes = volumes[-lookback:]

    # 收益率
    returns = (recent_closes[-1] - recent_closes[0]) / recent_closes[0] if recent_closes[0] > 0 else 0.0

    # 成交量放大（相对于更早的平均）
    older_avg_vol = np.mean(volumes[-lookback * 2:-lookback]) if n >= lookback * 2 else np.mean(volumes[:-lookback])
    recent_avg_vol = np.mean(recent_volumes)
    vol_spike = recent_avg_vol / older_avg_vol if older_avg_vol > 0 else 1.0

    # 情绪分数 = 收益率方向 × min(1, 成交量放大)
    sentiment = np.clip(returns * 10, -1, 1)  # 10% 收益 = 满分
    
    # 成交量放大增强置信度
    confidence = min(1.0, vol_spike / 2) * (1 - abs(returns) * 0.5)
    confidence = max(0.1, min(0.9, confidence))

    # 标签
    if sentiment > 0.2:
        label = "bullish"
    elif sentiment < -0.2:
        label = "bearish"
    else:
        label = "neutral"

    return NewsSentiment(
        news_sentiment=round(sentiment, 3),
        sentiment_label=label,
        confidence=round(confidence, 3),
        sources_count=1,  # proxy 单一来源
    )