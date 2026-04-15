"""
Sentiment Engine (情绪/资金博弈引擎)
===================================

独立引擎，输出 SentimentEvent + 资金博弈指标。

功能:
- 新闻情绪评分
- 成交量异动
- 持仓量/资金费率/清算 proxy（占位）
- 资金流向
- 情绪 regime (risk-on/risk-off/neutral)
- 多空拥挤度/挤兑风险 proxy

输入:
  - 理想输入: NewsEvent[] + AnalystRating[] + 资金流数据
  - Proxy 输入: MarketBar[] (OHLCV) ← 外部数据源暂不完整

输出: SentimentEvent (扩展 metadata 包含资金博弈指标)

⚠️ Proxy 标注: 大部分指标为 OHLCV 估算值
"""

from .engine import SentimentEngine

__all__ = ["SentimentEngine"]
