"""
Technical Analysis Engine
========================

经典技术分析引擎，统一入口。

功能:
- 趋势分析: MA 系统 + ADX
- 动量分析: MACD + RSI + KDJ/CCI
- 波动率分析: ATR + Bollinger Bands
- 图表形态: 头肩 / 双顶 / 三角形
- K线形态: 吞没 / 十字星 / pin bar
- 支撑阻力位检测

输出: TechnicalSignal (继承 EngineSignal)
"""

from __future__ import annotations

import numpy as np
from datetime import datetime
from typing import Optional, Any

from core.analysis.base import AnalysisEngine
from core.schemas import (
    EngineSignal,
    Direction,
    Regime,
    TimeFrame,
    MarketBar,
    TechnicalSignal,
)

from . import trend as trend_mod
from . import momentum as momentum_mod
from . import volatility as volatility_mod
from . import patterns as patterns_mod
from . import candles as candles_mod
from . import levels as levels_mod


class TechnicalEngine(AnalysisEngine):
    """
    经典技术分析引擎.
    
    输入: MarketBar[] (OHLCV)
    输出: TechnicalSignal
    """

    engine_name = "technical"

    # ─────────────────────────────────────────────────────────────
    # 配置
    # ─────────────────────────────────────────────────────────────

    DEFAULT_CONFIG = {
        "ma_periods": [5, 20, 60, 120],
        "adx_period": 14,
        "macd": {"fast": 12, "slow": 26, "signal": 9},
        "rsi_period": 14,
        "atr_period": 14,
        "bollinger": {"period": 20, "std_dev": 2.0},
        "pattern_window": 5,
        "level_lookback": 100,
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._last_analysis: Optional[dict] = None

    # ─────────────────────────────────────────────────────────────
    # 核心分析
    # ─────────────────────────────────────────────────────────────

    def analyze(self, data: Any, **kwargs: Any) -> TechnicalSignal:
        """
        执行完整技术分析.
        
        Args:
            data: MarketBar[] 或 dict{"bars": [...]} 或 numpy arrays
            **kwargs: indicators=["ma", "rsi", ...] 可选指定指标
            
        Returns:
            TechnicalSignal
        """
        # 1. 数据准备
        bars = self._check_bars(data, min_length=20)
        n = len(bars)
        symbol = bars[0].symbol
        timeframe = self._require_timeframe(bars)

        # 转换为 numpy arrays
        opens = np.array([b.open for b in bars])
        highs = np.array([b.high for b in bars])
        lows = np.array([b.low for b in bars])
        closes = np.array([b.close for b in bars])
        volumes = np.array([b.volume for b in bars])

        # 2. 计算指标
        indicators = self._calc_indicators(opens, highs, lows, closes, volumes)

        # 3. 形态识别
        patterns = self._scan_patterns(closes, highs, lows, opens)
        candle_patterns = self._scan_candles(opens, closes, highs, lows)

        # 4. 支撑阻力
        levels = self._detect_levels(highs, lows, closes)
        support_resist = self._format_levels(levels, closes[-1])

        # 5. 综合信号
        signal = self._synthesize_signal(
            indicators, patterns, candle_patterns, support_resist, closes
        )

        # 6. 构造 TechnicalSignal
        return TechnicalSignal(
            engine_name=self.engine_name,
            symbol=symbol,
            timestamp=bars[-1].timestamp,
            timeframe=timeframe,
            direction=signal["direction"],
            confidence=signal["confidence"],
            regime=signal["regime"],
            entry_score=signal["entry_score"],
            exit_score=signal["exit_score"],
            trend=signal["trend"],
            momentum=signal["momentum"],
            volatility_state=signal["volatility_state"],
            chart_pattern=signal["chart_pattern"],
            candle_pattern=signal["candle_pattern"],
            support_levels=signal["support_levels"],
            resistance_levels=signal["resistance_levels"],
            module_scores=signal["module_scores"],
            reasoning=signal["reasoning"],
            metadata={"config": self.config, **signal["metadata"]},
        )

    # ─────────────────────────────────────────────────────────────
    # 指标计算
    # ─────────────────────────────────────────────────────────────

    def _calc_indicators(
        self, opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, 
        closes: np.ndarray, volumes: np.ndarray
    ) -> dict:
        """计算所有指标."""
        result: dict[str, Any] = {}

        # MA 系统
        for period in self.config["ma_periods"]:
            result[f"ma_{period}"] = trend_mod.sma(closes, period)

        # ADX
        adx_data = trend_mod.adx(highs, lows, closes, self.config["adx_period"])
        result["adx"] = adx_data["adx"]
        result["plus_di"] = adx_data["plus_di"]
        result["minus_di"] = adx_data["minus_di"]

        # MACD
        macd_cfg = self.config["macd"]
        macd_data = momentum_mod.macd(
            closes, macd_cfg["fast"], macd_cfg["slow"], macd_cfg["signal"]
        )
        result["macd_line"] = macd_data["line"]
        result["macd_signal"] = macd_data["signal"]
        result["macd_histogram"] = macd_data["histogram"]

        # RSI
        result["rsi"] = momentum_mod.rsi(closes, self.config["rsi_period"])

        # KDJ
        kdj_data = momentum_mod.kdj(highs, lows, closes)
        result["k"] = kdj_data["k"]
        result["d"] = kdj_data["d"]
        result["j"] = kdj_data["j"]

        # CCI
        result["cci"] = momentum_mod.cci(highs, lows, closes)

        # ATR
        result["atr"] = volatility_mod.atr(
            highs, lows, closes, self.config["atr_period"]
        )

        # Bollinger Bands
        bb_cfg = self.config["bollinger"]
        bb_data = volatility_mod.bollinger_bands(
            closes, bb_cfg["period"], bb_cfg["std_dev"]
        )
        result["bb_upper"] = bb_data["upper"]
        result["bb_middle"] = bb_data["middle"]
        result["bb_lower"] = bb_data["lower"]
        result["bb_bandwidth"] = bb_data["bandwidth"]

        self._last_analysis = result
        return result

    # ─────────────────────────────────────────────────────────────
    # 形态识别
    # ─────────────────────────────────────────────────────────────

    def _scan_patterns(
        self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, opens: np.ndarray
    ) -> list:
        """扫描图表形态."""
        window = self.config["pattern_window"]
        return patterns_mod.scan_patterns(closes, window)

    def _scan_candles(
        self, opens: np.ndarray, closes: np.ndarray, 
        highs: np.ndarray, lows: np.ndarray
    ) -> list:
        """扫描K线形态."""
        return candles_mod.scan_candle_patterns(opens, closes, highs, lows)

    # ─────────────────────────────────────────────────────────────
    # 支撑阻力
    # ─────────────────────────────────────────────────────────────

    def _detect_levels(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray
    ) -> list:
        """检测支撑阻力位."""
        lookback = min(self.config["level_lookback"], len(closes))
        return levels_mod.detect_support_resistance(
            highs[-lookback:], lows[-lookback:], closes[-lookback:]
        )

    def _format_levels(self, levels: list, current_price: float) -> dict:
        """格式化支撑阻力位."""
        nearest = levels_mod.get_nearest_levels(levels, current_price)
        return {
            "support": [l.price for l in nearest["support"]],
            "resistance": [l.price for l in nearest["resistance"]],
        }

    # ─────────────────────────────────────────────────────────────
    # 信号综合
    # ─────────────────────────────────────────────────────────────

    def _synthesize_signal(
        self,
        indicators: dict,
        patterns: list,
        candle_patterns: list,
        support_resist: dict,
        closes: np.ndarray,
    ) -> dict:
        """综合所有信号."""
        n = len(closes)
        idx = n - 1

        # 趋势判断
        trend = self._determine_trend(indicators, idx)
        
        # 动量状态
        momentum = self._determine_momentum(indicators, idx)
        
        # 波动率状态
        volatility_state = self._determine_volatility(indicators, idx)
        
        # 形态 (取最强的)
        chart_pattern = None
        if patterns:
            best = patterns[0]
            chart_pattern = best.name
        
        candle_pattern = None
        if candle_patterns:
            best_candle = candle_patterns[0]
            candle_pattern = best_candle.name

        # 方向与置信度
        direction, confidence = self._calc_direction_confidence(
            trend, momentum, volatility_state, patterns, candle_patterns
        )

        # regime
        regime = self._determine_regime(indicators, idx)

        # entry/exit score
        entry_score, exit_score = self._calc_entry_exit_scores(
            indicators, direction, idx
        )

        # module_scores
        module_scores = {
            "trend": self._score_trend(trend, indicators["adx"][idx]),
            "momentum": self._score_momentum(indicators["rsi"][idx], indicators["macd_histogram"][idx]),
            "volatility": self._score_volatility(indicators["bb_bandwidth"][idx]),
            "patterns": patterns[0].confidence if patterns else 0.0,
            "candles": candle_patterns[0].confidence if candle_patterns else 0.0,
        }

        # reasoning
        reasoning = self._build_reasoning(
            trend, momentum, volatility_state, chart_pattern, candle_pattern
        )

        return {
            "direction": direction,
            "confidence": confidence,
            "regime": regime,
            "entry_score": entry_score,
            "exit_score": exit_score,
            "trend": trend,
            "momentum": momentum,
            "volatility_state": volatility_state,
            "chart_pattern": chart_pattern,
            "candle_pattern": candle_pattern,
            "support_levels": support_resist["support"],
            "resistance_levels": support_resist["resistance"],
            "module_scores": module_scores,
            "reasoning": reasoning,
            "metadata": {
                "adx": float(indicators["adx"][idx]) if not np.isnan(indicators["adx"][idx]) else None,
                "rsi": float(indicators["rsi"][idx]) if not np.isnan(indicators["rsi"][idx]) else None,
                "atr": float(indicators["atr"][idx]) if not np.isnan(indicators["atr"][idx]) else None,
            },
        }

    def _determine_trend(self, indicators: dict, idx: int) -> str:
        """判断趋势."""
        ma5 = indicators.get("ma_5", np.array([]))
        ma20 = indicators.get("ma_20", np.array([]))
        ma60 = indicators.get("ma_60", np.array([]))

        if idx < 0 or len(ma5) <= idx:
            return "sideways"

        # 多头排列
        if not np.isnan(ma5[idx]) and not np.isnan(ma20[idx]) and not np.isnan(ma60[idx]):
            if ma5[idx] > ma20[idx] > ma60[idx]:
                return "up"
            if ma5[idx] < ma20[idx] < ma60[idx]:
                return "down"

        return "sideways"

    def _determine_momentum(self, indicators: dict, idx: int) -> str:
        """判断动量."""
        rsi = indicators.get("rsi", np.array([]))
        macd_hist = indicators.get("macd_histogram", np.array([]))

        if idx < 0 or len(rsi) <= idx:
            return "neutral"

        rsi_val = rsi[idx]
        hist_val = macd_hist[idx] if idx < len(macd_hist) else np.nan

        return momentum_mod.momentum_state(rsi_val, hist_val)

    def _determine_volatility(self, indicators: dict, idx: int) -> str:
        """判断波动率."""
        atr = indicators.get("atr", np.array([]))
        bb_width = indicators.get("bb_bandwidth", np.array([]))

        if idx < 0 or len(atr) <= idx:
            return "neutral"

        atr_val = atr[idx]
        # 计算 ATR 的移动平均作为基准
        atr_ma = np.nanmean(atr[max(0, idx - 20) : idx + 1])
        bb_w = bb_width[idx] if idx < len(bb_width) else np.nan

        return volatility_mod.volatility_state(atr_val, atr_ma, bb_w)

    def _determine_regime(self, indicators: dict, idx: int) -> Regime:
        """判断市场状态."""
        adx = indicators.get("adx", np.array([]))
        rsi = indicators.get("rsi", np.array([]))

        if idx < 0 or len(adx) <= idx:
            return Regime.UNKNOWN

        adx_val = adx[idx]
        rsi_val = rsi[idx]

        if np.isnan(adx_val) or np.isnan(rsi_val):
            return Regime.UNKNOWN

        # ADX > 25 → 趋势市
        if adx_val > 25:
            if rsi_val > 55:
                return Regime.TRENDING_UP
            elif rsi_val < 45:
                return Regime.TRENDING_DOWN
            else:
                return Regime.RANGING
        else:
            # ADX < 25 → 震荡市
            if rsi_val > 65:
                return Regime.VOLATILE
            elif rsi_val < 35:
                return Regime.VOLATILE
            else:
                return Regime.RANGING

    def _calc_direction_confidence(
        self,
        trend: str,
        momentum: str,
        volatility_state: str,
        patterns: list,
        candle_patterns: list,
    ) -> tuple[Direction, float]:
        """计算方向与置信度."""
        score = 0.0
        count = 0

        # 趋势贡献
        if trend == "up":
            score += 1.0
        elif trend == "down":
            score -= 1.0
        count += 1

        # 动量贡献
        if momentum == "strengthening":
            score += 0.5 if trend == "up" else -0.5
        elif momentum == "weakening":
            score += -0.5 if trend == "up" else 0.5
        count += 1

        # 图表形态
        if patterns:
            p = patterns[0]
            if p.direction == "bullish":
                score += p.confidence
            elif p.direction == "bearish":
                score -= p.confidence
            count += 1

        # K线形态
        if candle_patterns:
            c = candle_patterns[0]
            if c.direction == "bullish":
                score += c.confidence * 0.5
            elif c.direction == "bearish":
                score -= c.confidence * 0.5
            count += 1

        # 归一化
        if count > 0:
            net_score = score / count
        else:
            net_score = 0.0

        # 映射到方向
        if net_score > 0.3:
            direction = Direction.LONG
            confidence = min(0.95, 0.5 + abs(net_score) * 0.5)
        elif net_score < -0.3:
            direction = Direction.SHORT
            confidence = min(0.95, 0.5 + abs(net_score) * 0.5)
        else:
            direction = Direction.FLAT
            confidence = 0.3

        return direction, round(confidence, 3)

    def _calc_entry_exit_scores(
        self, indicators: dict, direction: Direction, idx: int
    ) -> tuple[float, float]:
        """计算入场/出场得分."""
        rsi = indicators.get("rsi", np.array([]))
        macd_hist = indicators.get("macd_histogram", np.array([]))

        if idx < 0 or len(rsi) <= idx:
            return 0.5, 0.5

        rsi_val = rsi[idx]
        hist_val = macd_hist[idx] if idx < len(macd_hist) else 0.0

        if np.isnan(rsi_val):
            rsi_val = 50.0

        # 简单逻辑
        if direction == Direction.LONG:
            # RSI < 50 且 histogram 为负 → 好入场点
            if rsi_val < 50 and hist_val < 0:
                entry_score = 0.7
            else:
                entry_score = 0.5
            # RSI > 70 → 出场信号
            exit_score = 0.7 if rsi_val > 70 else 0.4
        elif direction == Direction.SHORT:
            if rsi_val > 50 and hist_val > 0:
                entry_score = 0.7
            else:
                entry_score = 0.5
            exit_score = 0.7 if rsi_val < 30 else 0.4
        else:
            entry_score, exit_score = 0.3, 0.3

        return round(entry_score, 2), round(exit_score, 2)

    def _score_trend(self, trend: str, adx_val: float) -> float:
        """趋势得分."""
        if np.isnan(adx_val):
            return 0.0
        base = 0.3 if trend == "up" else -0.3 if trend == "down" else 0.0
        return round(base + min(0.7, adx_val / 100), 2)

    def _score_momentum(self, rsi_val: float, macd_hist: float) -> float:
        """动量得分."""
        if np.isnan(rsi_val):
            return 0.0
        # RSI 偏离中值的程度
        return round(abs(rsi_val - 50) / 50, 2)

    def _score_volatility(self, bb_width: float) -> float:
        """波动率得分."""
        if np.isnan(bb_width):
            return 0.0
        return round(min(1.0, bb_width), 2)

    def _build_reasoning(
        self,
        trend: str,
        momentum: str,
        volatility_state: str,
        chart_pattern: Optional[str],
        candle_pattern: Optional[str],
    ) -> str:
        """构建推理说明."""
        parts = [f"趋势={trend}", f"动量={momentum}", f"波动率={volatility_state}"]
        if chart_pattern:
            parts.append(f"图表形态={chart_pattern}")
        if candle_pattern:
            parts.append(f"K线形态={candle_pattern}")
        return " | ".join(parts)
