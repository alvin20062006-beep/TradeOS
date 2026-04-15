"""
Sentiment Engine (情绪/资金博弈引擎)
===================================

独立引擎，输出 SentimentEvent。

功能:
- 新闻情绪评分 (News Sentiment)
- 成交量异动 (Volume Surprise)
- 持仓量/资金费率/清算 proxy (OI/Funding/Liquidation Proxy)
- 资金流向 (Money Flow)
- 情绪 regime (Risk-On/Risk-Off/Neutral)
- 多空拥挤度/挤兑风险 (Crowding/Squeeze)

输入:
  - 理想输入: NewsEvent[] + AnalystRating[] + 资金流数据
  - Proxy 输入: MarketBar[] (OHLCV) ← 外部数据源暂不完整

输出: SentimentEvent (扩展 metadata 包含资金博弈指标)

⚠️ Proxy 标注: 大部分指标为 OHLCV 估算值，metadata["proxy"] = True
"""

from __future__ import annotations

import numpy as np
from datetime import datetime
from typing import Optional, Any

from core.schemas import (
    SentimentEvent,
    NewsEvent,
    MarketBar,
    TimeFrame,
)

from . import news_sentiment
from . import volume_metrics
from . import oi_proxy
from . import money_flow
from . import regime
from . import crowding


class SentimentEngine:
    """
    情绪/资金博弈引擎.
    
    独立实现，不继承 AnalysisEngine（SentimentEvent 非 EngineSignal）。
    
    支持两种输入模式:
    1. 完整模式: NewsEvent[] + 资金流数据 → 精确计算
    2. Proxy 模式: MarketBar[] → 从 OHLCV 估算
    """

    engine_name = "sentiment"

    DEFAULT_CONFIG = {
        "lookback": 20,
        "volume_lookback": 20,
        "mfi_period": 14,
        "crowding_threshold": 0.8,
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

    # ─────────────────────────────────────────────────────────────
    # 主入口
    # ─────────────────────────────────────────────────────────────

    def analyze(
        self,
        data: Any,
        news_events: Optional[list[NewsEvent]] = None,
        **kwargs: Any,
    ) -> SentimentEvent:
        """
        执行情绪/资金博弈分析.
        
        Args:
            data: 输入数据:
                  - MarketBar[]: OHLCV bars（Proxy 模式）
                  - dict{"bars": [...], "news": [...]}: 完整
            news_events: 可选的新闻事件列表
            **kwargs: 其他参数
            
        Returns:
            SentimentEvent
        """
        # 1. 解析输入
        bars, news, is_proxy = self._parse_input(data, news_events)

        # 2. 提取 OHLCV arrays
        if bars:
            highs = np.array([b.high for b in bars])
            lows = np.array([b.low for b in bars])
            closes = np.array([b.close for b in bars])
            volumes = np.array([b.volume for b in bars])
            symbol = bars[0].symbol
            timestamp = bars[-1].timestamp
        else:
            highs = lows = closes = volumes = np.array([])
            symbol = ""
            timestamp = datetime.utcnow()

        # 3. 新闻情绪
        news_sent = self._analyze_news(news, closes, volumes)

        # 4. 成交量异动
        vol_metrics = self._analyze_volume(volumes)

        # 5. OI/Funding/Liquidation proxy
        oi_metrics = self._analyze_oi(closes, volumes)

        # 6. 资金流向
        mf_metrics = self._analyze_money_flow(highs, lows, closes, volumes)

        # 7. 情绪 regime
        regime_metrics = self._analyze_regime(closes, highs, lows, volumes)

        # 8. 拥挤度
        crowd_metrics = self._analyze_crowding(closes, volumes)

        # 9. 综合情绪评分
        composite = self._calc_composite(
            news_sent, vol_metrics, regime_metrics, crowd_metrics
        )

        # 10. 构建 SentimentEvent
        # news_sentiment: -1~1 → 0~1 (SentimentEvent schema 要求)
        news_sentiment_norm = round((news_sent.news_sentiment + 1) / 2, 3)
        return SentimentEvent(
            symbol=symbol,
            timestamp=timestamp,
            news_sentiment=news_sentiment_norm,
            social_sentiment=0.5,  # proxy 占位
            forum_sentiment=0.5,   # proxy 占位
            analyst_sentiment=0.5, # proxy 占位
            composite_sentiment=round(composite, 3),
            bullish_ratio=round(max(0, composite), 3),
            bearish_ratio=round(max(0, 1 - composite), 3),
            neutral_ratio=round(1 - abs(composite - 0.5) * 2, 3),
            sources_count=news_sent.sources_count,
            metadata={
                "proxy": is_proxy,
                "news_detail": {
                    "label": news_sent.sentiment_label,
                    "confidence": news_sent.confidence,
                },
                "volume_detail": {
                    "surprise": vol_metrics.volume_surprise,
                    "trend": vol_metrics.volume_trend,
                    "crowding_score": vol_metrics.crowding_score,
                },
                "oi_detail": {
                    "oi_change_pct": oi_metrics.oi_change_pct,
                    "funding_rate": oi_metrics.funding_rate,
                    "liquidation_risk": oi_metrics.liquidation_risk,
                    "is_proxy": oi_metrics.is_proxy,
                },
                "money_flow_detail": {
                    "net_flow": mf_metrics.net_flow,
                    "mfi": mf_metrics.money_flow_index,
                    "accumulation": mf_metrics.accumulation,
                },
                "regime_detail": {
                    "regime": regime_metrics.regime.value,
                    "fear_greed_index": regime_metrics.fear_greed_index,
                    "volatility_state": regime_metrics.volatility_state,
                },
                "crowding_detail": {
                    "long_crowding": crowd_metrics.long_crowding,
                    "short_crowding": crowd_metrics.short_crowding,
                    "direction": crowd_metrics.crowding_direction,
                    "squeeze_risk": crowd_metrics.squeeze_risk,
                },
            },
        )

    # ─────────────────────────────────────────────────────────────
    # 输入解析
    # ─────────────────────────────────────────────────────────────

    def _parse_input(self, data: Any, news_events: Optional[list[NewsEvent]]) -> tuple:
        """解析输入数据."""
        bars = []
        news = news_events or []
        is_proxy = True

        if data is None:
            return bars, news, is_proxy

        if isinstance(data, dict):
            if "bars" in data:
                bars = self._to_bars(data["bars"])
            if "news" in data and not news:
                news = [n if isinstance(n, NewsEvent) else NewsEvent(**n) for n in data["news"]]
        elif isinstance(data, (list, tuple)):
            if data and isinstance(data[0], MarketBar):
                bars = list(data)

        is_proxy = not news

        return bars, news, is_proxy

    def _to_bars(self, data: Any) -> list[MarketBar]:
        """转换为 MarketBar 列表."""
        if not data:
            return []
        result = []
        for item in data:
            if isinstance(item, MarketBar):
                result.append(item)
            elif isinstance(item, dict):
                result.append(MarketBar(**item))
        return result

    # ─────────────────────────────────────────────────────────────
    # 子模块分析
    # ─────────────────────────────────────────────────────────────

    def _analyze_news(self, news, closes, volumes):
        """新闻情绪分析."""
        if news:
            return news_sentiment.analyze_news_sentiment(news)
        elif len(closes) > 0:
            return news_sentiment.proxy_news_sentiment_from_returns(
                closes, volumes, lookback=self.config["lookback"]
            )
        return news_sentiment.NewsSentiment(0.0, "neutral", 0.0, 0)

    def _analyze_volume(self, volumes):
        """成交量分析."""
        if len(volumes) > 0:
            return volume_metrics.calc_volume_surprise(
                volumes, lookback=self.config["volume_lookback"]
            )
        return volume_metrics.VolumeMetrics(1.0, 0.0, 0.0, "stable", 0.5)

    def _analyze_oi(self, closes, volumes):
        """OI/Funding proxy."""
        if len(closes) > 1:
            price_change = (closes[-1] - closes[-self.config["lookback"]]) / closes[-self.config["lookback"]] if len(closes) > self.config["lookback"] else 0.0
            recent_vol = np.mean(volumes[-5:]) if len(volumes) >= 5 else volumes[-1] if len(volumes) > 0 else 0.0
            avg_vol = np.mean(volumes) if len(volumes) > 0 else 1.0
            return oi_proxy.proxy_oi_from_volume(recent_vol, avg_vol, price_change)
        return oi_proxy.OIProxy(0.0, 0.0, 0.0, "low", True)

    def _analyze_money_flow(self, highs, lows, closes, volumes):
        """资金流向分析."""
        if len(closes) > self.config["mfi_period"]:
            return money_flow.calc_money_flow(
                highs, lows, closes, volumes,
                lookback=self.config["mfi_period"],
            )
        return money_flow.MoneyFlow(0.0, 1.0, 50.0, "neutral")

    def _analyze_regime(self, closes, highs, lows, volumes):
        """情绪 regime 分析."""
        if len(closes) >= self.config["lookback"]:
            return regime.detect_sentiment_regime(
                closes, highs, lows, volumes,
                lookback=self.config["lookback"],
            )
        return regime.RegimeMetrics(
            regime=regime.SentimentRegime.NEUTRAL,
            confidence=0.0,
            fear_greed_index=50.0,
            volatility_state="normal",
            trend_strength=0.0,
        )

    def _analyze_crowding(self, closes, volumes):
        """拥挤度分析."""
        if len(closes) >= self.config["lookback"]:
            return crowding.detect_crowding(
                closes, volumes, lookback=self.config["lookback"]
            )
        return crowding.CrowdingMetrics(0.5, 0.5, "neutral", "none", 0.0)

    # ─────────────────────────────────────────────────────────────
    # 综合评分
    # ─────────────────────────────────────────────────────────────

    def _calc_composite(self, news_sent, vol_metrics, regime_metrics, crowd_metrics):
        """
        综合情绪评分.
        
        Returns:
            0-1 (0=极度看空, 1=极度看多)
        """
        scores = []

        # 新闻情绪: -1~1 → 0~1
        news_score = (news_sent.news_sentiment + 1) / 2
        scores.append(news_score * news_sent.confidence)

        # Regime: risk_on=1, risk_off=0, neutral=0.5
        if regime_metrics.regime == regime.SentimentRegime.RISK_ON:
            regime_score = 0.8
        elif regime_metrics.regime == regime.SentimentRegime.RISK_OFF:
            regime_score = 0.2
        else:
            regime_score = 0.5
        scores.append(regime_score * regime_metrics.confidence)

        # 拥挤度: 反向指标（极端拥挤 → 风险）
        if crowd_metrics.crowding_direction == "long" and crowd_metrics.long_crowding > 0.7:
            crowd_score = 0.3  # 多头过度拥挤 → 看跌
        elif crowd_metrics.crowding_direction == "short" and crowd_metrics.short_crowding > 0.7:
            crowd_score = 0.7  # 空头过度拥挤 → 看涨
        else:
            crowd_score = 0.5
        scores.append(crowd_score)

        # 成交量: 放量上涨看涨，放量下跌看跌
        if vol_metrics.volume_surprise > 1.5:
            # 放量，需要结合新闻方向
            vol_score = 0.5 + (news_score - 0.5) * 0.3
        else:
            vol_score = 0.5
        scores.append(vol_score)

        # 加权平均
        total_weight = news_sent.confidence + regime_metrics.confidence + 0.5 + 0.3
        if total_weight > 0:
            composite = sum(scores) / total_weight
        else:
            composite = 0.5

        return np.clip(composite, 0, 1)

    # ─────────────────────────────────────────────────────────────
    # 批量分析
    # ─────────────────────────────────────────────────────────────

    def batch_analyze(
        self,
        data_map: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, SentimentEvent]:
        """批量分析."""
        results = {}
        for symbol, data in data_map.items():
            try:
                results[symbol] = self.analyze(data, **kwargs)
            except Exception as exc:
                results[symbol] = SentimentEvent(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    metadata={"error": str(exc)},
                )
        return results

    # ─────────────────────────────────────────────────────────────
    # 生命周期
    # ─────────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        """健康检查."""
        return True
