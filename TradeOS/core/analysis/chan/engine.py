"""
Chan Theory Engine
==================

缠论引擎统一入口。

功能:
- 分型识别 (Fractals)
- 笔构建 (Strokes)
- 线段划分 (Segments)
- 中枢识别 (Centers)
- 背驰判断 (Divergence)
- 买卖点判定 (Trading Points)
- 多级别联动 (Multi-timeframe)
- 结构失效检测

输出: ChanSignal (继承 EngineSignal)
"""

from __future__ import annotations

import numpy as np
from datetime import datetime
from typing import Optional, Any

from core.analysis.base import AnalysisEngine
from core.schemas import (
    Direction,
    Regime,
    TimeFrame,
    MarketBar,
    ChanSignal,
)

from . import fractals as fractal_mod
from . import strokes as stroke_mod
from . import segments as segment_mod
from . import centers as center_mod
from . import divergence as div_mod
from . import points as points_mod
from .config import DEFAULT_CONFIG, ChanConfig


class ChanEngine(AnalysisEngine):
    """
    缠论引擎.
    
    输入: MarketBar[] (OHLCV)
    输出: ChanSignal
    """

    engine_name = "chan"

    def __init__(self, config: Optional[dict] = None):
        self.config = self._apply_config(config or {})
        self._last_structure: Optional[dict] = None

    def _apply_config(self, config: dict) -> ChanConfig:
        """将 dict 配置转换为 ChanConfig."""
        cfg = DEFAULT_CONFIG
        if "bi_min_bars" in config:
            cfg.bi_min_bars = config["bi_min_bars"]
        if "segment_back_ratio" in config:
            cfg.segment_back_ratio = config["segment_back_ratio"]
        if "higher_timeframe" in config:
            cfg.higher_timeframe = config["higher_timeframe"]
        if "lower_timeframe" in config:
            cfg.lower_timeframe = config["lower_timeframe"]
        return cfg

    # ─────────────────────────────────────────────────────────────
    # 核心分析
    # ─────────────────────────────────────────────────────────────

    def analyze(self, data: Any, **kwargs: Any) -> ChanSignal:
        """
        执行完整缠论分析.
        
        Args:
            data: MarketBar[] 或 dict{"bars": [...]}
            **kwargs:
                - multi_tf: 是否做多级别联动（默认 True）
                - min_history: 最小历史数据量（默认 100）
                
        Returns:
            ChanSignal
        """
        # 1. 数据准备
        bars = self._check_bars(data, min_length=30)
        symbol = bars[0].symbol
        timeframe = self._require_timeframe(bars)
        n = len(bars)

        # 转换为 numpy arrays
        opens = np.array([b.open for b in bars])
        highs = np.array([b.high for b in bars])
        lows = np.array([b.low for b in bars])
        closes = np.array([b.close for b in bars])
        volumes = np.array([b.volume for b in bars])

        # 2. 分型识别
        fractals = fractal_mod.detect_fractals(
            highs, lows, opens, closes,
            handle_inclusion=True
        )

        # 3. 笔构建
        strokes = stroke_mod.build_strokes(
            fractals, highs, lows,
            min_bars=self.config.bi_min_bars
        )

        # 4. 线段划分
        segments = segment_mod.build_segments(
            strokes,
            back_ratio=self.config.segment_back_ratio
        )

        # 5. 中枢识别
        centers = center_mod.build_centers(segments)

        # 6. 背驰判断
        divergences = div_mod.detect_divergence(
            strokes, segments, highs, lows, closes,
            macd_fast=self.config.divergence_macd_periods[0],
            macd_slow=self.config.divergence_macd_periods[1],
            macd_signal=self.config.divergence_macd_periods[2],
        )

        # 7. 买卖点判定
        purchases = points_mod.detect_purchase_points(
            strokes, segments, centers, divergences, highs, lows, closes
        )
        sells = points_mod.detect_sell_points(
            strokes, segments, centers, divergences, highs, lows, closes
        )

        # 8. 结构失效检测
        invalid, invalid_reason = points_mod.check_structure_invalidation(
            strokes, divergences, highs, lows
        )

        # 9. 综合信号
        signal = self._synthesize_signal(
            strokes, segments, centers, divergences,
            purchases, sells, invalid, invalid_reason,
            closes, n - 1
        )

        # 10. 多级别联动（最小实现）
        higher_tf_dir = kwargs.get("higher_tf_dir", None)
        lower_tf_dir = kwargs.get("lower_tf_dir", None)

        # 11. 构造 ChanSignal
        latest_div = div_mod.get_latest_divergence(divergences)
        latest_point = points_mod.get_latest_trading_point(purchases + sells)

        purchase_point = None
        sell_point = None
        if latest_point:
            pt = latest_point.point_type
            if pt in {
                points_mod.TradingPointType.PURCHASE_1,
                points_mod.TradingPointType.PURCHASE_2,
                points_mod.TradingPointType.PURCHASE_3,
            }:
                purchase_point = {
                    points_mod.TradingPointType.PURCHASE_1: 1,
                    points_mod.TradingPointType.PURCHASE_2: 2,
                    points_mod.TradingPointType.PURCHASE_3: 3,
                }.get(pt)
            elif pt in {
                points_mod.TradingPointType.SELL_1,
                points_mod.TradingPointType.SELL_2,
                points_mod.TradingPointType.SELL_3,
            }:
                sell_point = {
                    points_mod.TradingPointType.SELL_1: 1,
                    points_mod.TradingPointType.SELL_2: 2,
                    points_mod.TradingPointType.SELL_3: 3,
                }.get(pt)

        divergence_str = None
        if latest_div:
            divergence_str = latest_div.divergence_type.value

        # 保存结构供后续使用
        self._last_structure = {
            "fractals": fractals,
            "strokes": strokes,
            "segments": segments,
            "centers": centers,
            "divergences": divergences,
            "purchases": purchases,
            "sells": sells,
        }

        return ChanSignal(
            engine_name=self.engine_name,
            symbol=symbol,
            timestamp=bars[-1].timestamp,
            timeframe=timeframe,
            direction=signal["direction"],
            confidence=signal["confidence"],
            regime=signal["regime"],
            entry_score=signal["entry_score"],
            exit_score=signal["exit_score"],
            fractal_level=signal.get("fractal_level"),
            bi_status=signal.get("bi_status"),
            segment_status=signal.get("segment_status"),
            zhongshu_status=signal.get("zhongshu_status"),
            divergence=divergence_str,
            purchase_point=purchase_point,
            sell_point=sell_point,
            higher_tf_direction=signal.get("higher_tf_direction"),
            lower_tf_direction=signal.get("lower_tf_direction"),
            reasoning=signal["reasoning"],
            metadata={
                "stroke_count": len(strokes),
                "segment_count": len(segments),
                "center_count": len(centers),
                "divergence_count": len(divergences),
                "structure_invalid": invalid,
                "invalidation_reason": invalid_reason,
                "latest_point": latest_point.description if latest_point else None,
                "latest_center": center_mod.summarize_centers(centers),
            },
        )

    # ─────────────────────────────────────────────────────────────
    # 信号综合
    # ─────────────────────────────────────────────────────────────

    def _synthesize_signal(
        self,
        strokes,
        segments,
        centers,
        divergences,
        purchases,
        sells,
        invalid: bool,
        invalid_reason: Optional[str],
        closes: np.ndarray,
        idx: int,
    ) -> dict:
        """综合所有缠论信号."""
        n = len(closes)
        current_price = closes[idx] if idx < n else closes[-1]

        # 最新笔
        latest_stroke = strokes[-1] if strokes else None
        latest_seg = segments[-1] if segments else None
        latest_div = divergences[-1] if divergences else None
        latest_point = points_mod.get_latest_trading_point(purchases + sells)

        # 笔状态
        bi_status = f"{latest_stroke.direction.value}_forming" if latest_stroke else "unknown"

        # 线段状态
        if latest_seg:
            seg_status = f"{latest_seg.direction.value}_segment"
        else:
            seg_status = "no_segment"

        # 中枢状态
        center_summary = center_mod.summarize_centers(centers)
        zhongshu_status = center_summary["summary"]

        # 分型级别
        fractal_level = None
        if latest_stroke:
            if latest_stroke.direction == stroke_mod.StrokeDirection.UP:
                fractal_level = "potential_top"
            else:
                fractal_level = "potential_bottom"

        # 方向与置信度
        direction, confidence, entry_score, exit_score = self._calc_direction(
            latest_stroke, latest_div, latest_point, invalid, centers, current_price, closes
        )

        # regime
        regime = self._calc_regime(segments, strokes, centers, closes)

        # 多级别方向
        higher_tf_dir = None
        lower_tf_dir = None

        # reasoning
        reasoning = self._build_reasoning(
            latest_stroke, latest_div, latest_point, invalid, invalid_reason,
            centers, direction
        )

        return {
            "direction": direction,
            "confidence": confidence,
            "regime": regime,
            "entry_score": entry_score,
            "exit_score": exit_score,
            "fractal_level": fractal_level,
            "bi_status": bi_status,
            "segment_status": seg_status,
            "zhongshu_status": zhongshu_status,
            "higher_tf_direction": higher_tf_dir,
            "lower_tf_direction": lower_tf_dir,
            "reasoning": reasoning,
        }

    def _calc_direction(
        self,
        latest_stroke,
        latest_div,
        latest_point,
        invalid: bool,
        centers: list,
        current_price: float,
        closes: np.ndarray,
    ) -> tuple[Direction, float, float, float]:
        """计算方向与置信度."""
        entry_score, exit_score = 0.5, 0.5

        if invalid:
            # 结构失效：跟随当前走势方向
            if latest_stroke and latest_stroke.direction == stroke_mod.StrokeDirection.UP:
                return Direction.LONG, 0.6, 0.7, 0.3
            elif latest_stroke and latest_stroke.direction == stroke_mod.StrokeDirection.DOWN:
                return Direction.SHORT, 0.6, 0.3, 0.7
            return Direction.FLAT, 0.3, 0.3, 0.3

        # 有背驰 → 强信号
        if latest_div:
            if latest_div.divergence_type == div_mod.DivergenceType.BULLISH:
                direction = Direction.LONG
                confidence = min(0.9, 0.6 + latest_div.severity * 0.3)
                entry_score = min(0.9, 0.5 + latest_div.severity * 0.4)
                exit_score = 0.3
            elif latest_div.divergence_type == div_mod.DivergenceType.BEARISH:
                direction = Direction.SHORT
                confidence = min(0.9, 0.6 + latest_div.severity * 0.3)
                entry_score = min(0.9, 0.5 + latest_div.severity * 0.4)
                exit_score = 0.3
            else:
                direction = Direction.FLAT
                confidence = 0.3
        # 有买卖点
        elif latest_point:
            pt = latest_point.point_type
            if pt in {
                points_mod.TradingPointType.PURCHASE_1,
                points_mod.TradingPointType.PURCHASE_2,
                points_mod.TradingPointType.PURCHASE_3,
            }:
                direction = Direction.LONG
                confidence = latest_point.confidence
                entry_score = latest_point.confidence
            elif pt in {
                points_mod.TradingPointType.SELL_1,
                points_mod.TradingPointType.SELL_2,
                points_mod.TradingPointType.SELL_3,
            }:
                direction = Direction.SHORT
                confidence = latest_point.confidence
                entry_score = latest_point.confidence
            else:
                direction = Direction.FLAT
                confidence = 0.3
        # 有中枢 → 中性，参考价格位置
        elif centers:
            latest_center = centers[-1]
            if current_price > latest_center.zg:
                direction = Direction.LONG
                confidence = 0.5
            elif current_price < latest_center.zd:
                direction = Direction.SHORT
                confidence = 0.5
            else:
                direction = Direction.FLAT
                confidence = 0.3
        # 只有笔
        elif latest_stroke:
            direction = Direction.LONG if latest_stroke.direction == stroke_mod.StrokeDirection.UP else Direction.SHORT
            confidence = 0.4
        else:
            direction = Direction.FLAT
            confidence = 0.2

        return direction, round(confidence, 3), round(entry_score, 2), round(exit_score, 2)

    def _calc_regime(
        self,
        segments: list,
        strokes: list,
        centers: list,
        closes: np.ndarray,
    ) -> Regime:
        """判断市场状态."""
        if not centers:
            return Regime.UNKNOWN

        latest = centers[-1]
        n = len(closes)
        current_price = closes[-1]

        # 看中枢的数量和稳定性
        if len(centers) >= 2:
            # 中枢上移/下移判断
            if len(centers) >= 2:
                prev = centers[-2]
                if latest.mid > prev.mid:
                    return Regime.TRENDING_UP
                elif latest.mid < prev.mid:
                    return Regime.TRENDING_DOWN
                else:
                    return Regime.RANGING

        # 中枢内震荡
        if center_mod.is_price_in_center(current_price, latest):
            return Regime.RANGING
        elif current_price > latest.zg:
            return Regime.TRENDING_UP
        elif current_price < latest.zd:
            return Regime.TRENDING_DOWN

        return Regime.RANGING

    def _build_reasoning(
        self,
        latest_stroke,
        latest_div,
        latest_point,
        invalid: bool,
        invalid_reason: Optional[str],
        centers: list,
        direction: Direction,
    ) -> str:
        """构建推理说明."""
        parts = []

        if invalid:
            parts.append(f"⚠️ 结构失效: {invalid_reason}")
        elif latest_div:
            parts.append(f"背驰@{latest_div.price_extremum_value:.2f}({latest_div.divergence_type.value})")
        elif latest_point:
            parts.append(f"买卖点: {latest_point.description}")
        elif centers:
            parts.append(f"中枢{centers[-1].range}")

        parts.append(f"信号方向={direction.value}")
        return " | ".join(parts)
