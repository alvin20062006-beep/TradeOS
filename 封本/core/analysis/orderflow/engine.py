"""
Order Flow Engine (盘口/订单流引擎)
==================================

独立引擎，不继承 AnalysisEngine（OrderFlowSignal 非 EngineSignal 子类）。

功能:
- 订单簿失衡分析 (Book Imbalance)
- Delta/CVD 计算
- 主动买卖比例 (Aggressive Buy/Sell Ratio)
- VWAP 偏离
- 大单集中度 (Large Trade Ratio)
- 吸收检测 (Absorption)
- 流动性扫荡 (Liquidity Sweep)
- 执行质量预测

输入: 
  - 理想输入: OrderBookSnapshot + TradePrint[]
  - Proxy 输入: MarketBar[] (OHLCV) ← 数据层暂不完整时的降级方案

输出: OrderFlowSignal

⚠️ Proxy 标注: 当使用 OHLCV bars 作为输入时，部分指标为估算值，
   在 metadata 中标注 "proxy": true
"""

from __future__ import annotations

import numpy as np
from datetime import datetime
from typing import Optional, Any, Union

from core.schemas import (
    OrderBookSnapshot,
    TradePrint,
    MarketBar,
    OrderFlowSignal,
    TimeFrame,
    ExecutionQuality,
    Side,
)

from . import book_analyzer
from . import delta
from . import vwap as vwap_mod
from . import large_trades
from . import absorption
from . import sweep
from . import execution


class OrderFlowEngine:
    """
    订单流引擎.
    
    独立实现，不继承 AnalysisEngine（因为 OrderFlowSignal 不是 EngineSignal）。
    
    支持两种输入模式:
    1. 完整模式: OrderBookSnapshot + TradePrint[] → 精确计算
    2. Proxy 模式: MarketBar[] → 从 OHLCV 估算
    """

    engine_name = "orderflow"

    # ─────────────────────────────────────────────────────────────
    # 配置
    # ─────────────────────────────────────────────────────────────

    DEFAULT_CONFIG = {
        "large_trade_multiplier": 3.0,
        "absorption_price_tolerance": 0.001,
        "absorption_volume_ratio": 3.0,
        "sweep_lookback": 5,
        "sweep_price_threshold": 0.02,
        "sweep_volume_ratio": 2.0,
        "vwap_bars": 50,
        "delta_bars": 100,
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._cum_delta: float = 0.0  # 累计 delta 状态

    # ─────────────────────────────────────────────────────────────
    # 主入口
    # ─────────────────────────────────────────────────────────────

    def analyze(
        self,
        data: Any,
        order_book: Optional[OrderBookSnapshot] = None,
        trades: Optional[list[TradePrint]] = None,
        **kwargs: Any,
    ) -> OrderFlowSignal:
        """
        执行订单流分析.
        
        Args:
            data: 输入数据，支持以下格式:
                  - MarketBar[]: OHLCV bars（Proxy 模式）
                  - dict{"bars": [...], "order_book": {...}, "trades": [...]}: 完整
            order_book: 可选的订单簿快照
            trades: 可选的逐笔成交列表
            **kwargs: 其他参数
            
        Returns:
            OrderFlowSignal
        """
        # 1. 解析输入
        bars, book, trades_list, is_proxy = self._parse_input(data, order_book, trades)

        # 2. 提取 OHLCV arrays（如果可用）
        if bars:
            opens = np.array([b.open for b in bars])
            highs = np.array([b.high for b in bars])
            lows = np.array([b.low for b in bars])
            closes = np.array([b.close for b in bars])
            volumes = np.array([b.volume for b in bars])
            symbol = bars[0].symbol
            timeframe = bars[0].timeframe
            timestamp = bars[-1].timestamp
        else:
            opens = highs = lows = closes = volumes = np.array([])
            symbol = ""
            timeframe = TimeFrame.M1
            timestamp = datetime.utcnow()

        # 3. 订单簿分析
        book_metrics = self._analyze_book(book)

        # 4. Delta/CVD
        delta_metrics = self._analyze_delta(trades_list)

        # 5. VWAP
        vwap_metrics = self._analyze_vwap(highs, lows, closes, volumes, trades_list)

        # 6. 大单检测
        large_metrics = self._analyze_large_trades(trades_list)

        # 7. 吸收检测
        absorption_metrics = self._analyze_absorption(
            trades_list, highs, lows, closes, volumes
        )

        # 8. 流动性扫荡
        sweep_metrics = self._analyze_sweep(highs, lows, closes, volumes)

        # 9. 执行质量
        exec_metrics = self._analyze_execution(book, volumes)

        # 10. 止损猎杀区域
        stop_zones = sweep.detect_stop_hunt_zones(
            highs, lows, closes, volumes, lookback=20
        ) if len(closes) >= 20 else []

        # 11. 综合信号
        signal = self._build_signal(
            symbol=symbol,
            timestamp=timestamp,
            timeframe=timeframe,
            book_metrics=book_metrics,
            delta_metrics=delta_metrics,
            vwap_metrics=vwap_metrics,
            large_metrics=large_metrics,
            absorption_metrics=absorption_metrics,
            sweep_metrics=sweep_metrics,
            exec_metrics=exec_metrics,
            stop_zones=stop_zones,
            is_proxy=is_proxy,
        )

        # 更新累计 delta
        if delta_metrics:
            self._cum_delta = delta_metrics.cum_delta

        return signal

    # ─────────────────────────────────────────────────────────────
    # 输入解析
    # ─────────────────────────────────────────────────────────────

    def _parse_input(
        self,
        data: Any,
        order_book: Optional[OrderBookSnapshot],
        trades: Optional[list[TradePrint]],
    ) -> tuple:
        """
        解析输入数据.
        
        Returns:
            (bars, book, trades, is_proxy)
        """
        bars = []
        book = order_book
        trades_list = trades or []
        is_proxy = False

        if data is None:
            return bars, book, trades_list, True

        # Dict 输入
        if isinstance(data, dict):
            if "bars" in data:
                bars = self._to_bars(data["bars"])
            if "order_book" in data and book is None:
                book = self._to_order_book(data["order_book"])
            if "trades" in data and not trades_list:
                trades_list = self._to_trades(data["trades"])
        # List 输入
        elif isinstance(data, (list, tuple)):
            if data and isinstance(data[0], MarketBar):
                bars = list(data)
            elif data and isinstance(data[0], TradePrint):
                trades_list = list(data)
            else:
                # 尝试解析为 bars
                bars = self._to_bars(data)

        # 判断是否为 proxy 模式
        is_proxy = (book is None) and (not trades_list)

        return bars, book, trades_list, is_proxy

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

    def _to_order_book(self, data: Any) -> Optional[OrderBookSnapshot]:
        """转换为 OrderBookSnapshot."""
        if data is None:
            return None
        if isinstance(data, OrderBookSnapshot):
            return data
        if isinstance(data, dict):
            return OrderBookSnapshot(**data)
        return None

    def _to_trades(self, data: Any) -> list[TradePrint]:
        """转换为 TradePrint 列表."""
        if not data:
            return []
        result = []
        for item in data:
            if isinstance(item, TradePrint):
                result.append(item)
            elif isinstance(item, dict):
                result.append(TradePrint(**item))
        return result

    # ─────────────────────────────────────────────────────────────
    # 子模块分析
    # ─────────────────────────────────────────────────────────────

    def _analyze_book(self, book: Optional[OrderBookSnapshot]):
        """订单簿分析."""
        if book is None:
            return None
        return book_analyzer.analyze_book(book)

    def _analyze_delta(self, trades: Optional[list[TradePrint]]):
        """Delta/CVD 分析."""
        if not trades:
            return None
        return delta.calc_delta(trades, prev_cum_delta=self._cum_delta)

    def _analyze_vwap(self, highs, lows, closes, volumes, trades):
        """VWAP 分析."""
        if len(closes) > 0:
            # 优先用 bars 计算
            return vwap_mod.calc_vwap_from_bars(highs, lows, closes, volumes)
        elif trades:
            # 用 trades 计算
            prices = [t.price for t in trades]
            sizes = [t.size for t in trades]
            return vwap_mod.calc_vwap_from_trades(prices, sizes)
        return None

    def _analyze_large_trades(self, trades: Optional[list[TradePrint]]):
        """大单检测."""
        if not trades:
            return None
        return large_trades.detect_large_trades(
            trades, self.config["large_trade_multiplier"]
        )

    def _analyze_absorption(self, trades, highs, lows, closes, volumes):
        """吸收检测."""
        if trades:
            return absorption.detect_absorption(
                trades,
                price_tolerance=self.config["absorption_price_tolerance"],
                volume_threshold_ratio=self.config["absorption_volume_ratio"],
            )
        elif len(closes) > 0:
            return absorption.detect_absorption_from_bars(
                highs, lows, closes, volumes
            )
        return None

    def _analyze_sweep(self, highs, lows, closes, volumes):
        """流动性扫荡检测."""
        if len(closes) >= self.config["sweep_lookback"]:
            return sweep.detect_sweep_from_bars(
                highs, lows, closes, volumes,
                lookback=self.config["sweep_lookback"],
                price_move_threshold=self.config["sweep_price_threshold"],
                volume_spike_ratio=self.config["sweep_volume_ratio"],
            )
        return None

    def _analyze_execution(self, book, volumes):
        """执行质量分析."""
        if book:
            return execution.estimate_execution_quality(book, order_size=100.0)
        elif len(volumes) > 0:
            slippage = execution.estimate_slippage_from_bars(volumes)
            return execution.ExecutionMetrics(
                expected_slippage=slippage,
                execution_condition=ExecutionQuality.FAIR,
                available_liquidity=float(np.mean(volumes)),
                market_impact=0.0,
            )
        return None

    # ─────────────────────────────────────────────────────────────
    # 构建信号
    # ─────────────────────────────────────────────────────────────

    def _build_signal(
        self,
        symbol: str,
        timestamp: datetime,
        timeframe: TimeFrame,
        book_metrics,
        delta_metrics,
        vwap_metrics,
        large_metrics,
        absorption_metrics,
        sweep_metrics,
        exec_metrics,
        stop_zones: list,
        is_proxy: bool,
    ) -> OrderFlowSignal:
        """构建 OrderFlowSignal."""

        # 订单簿失衡
        book_imbalance = book_metrics.imbalance if book_metrics else 0.0
        bid_pressure = book_metrics.bid_pressure if book_metrics else 0.5
        ask_pressure = book_metrics.ask_pressure if book_metrics else 0.5

        # Delta
        delta_val = delta_metrics.delta if delta_metrics else 0.0
        cum_delta_val = delta_metrics.cum_delta if delta_metrics else self._cum_delta

        # 吸收
        absorption_score = absorption_metrics.absorption_score if absorption_metrics else 0.0
        liquidity_sweep = sweep_metrics.sweep_detected if sweep_metrics else False

        # 执行质量
        slippage = exec_metrics.expected_slippage if exec_metrics else 50.0
        exec_quality = exec_metrics.execution_condition if exec_metrics else ExecutionQuality.FAIR

        # metadata
        metadata = {
            "proxy": is_proxy,
            "book_imbalance_detail": {
                "total_bid_depth": book_metrics.total_bid_depth if book_metrics else 0,
                "total_ask_depth": book_metrics.total_ask_depth if book_metrics else 0,
                "spread": book_metrics.spread if book_metrics else 0,
            } if book_metrics else None,
            "delta_detail": {
                "buy_volume": delta_metrics.buy_volume if delta_metrics else 0,
                "sell_volume": delta_metrics.sell_volume if delta_metrics else 0,
                "aggressive_buy_ratio": delta_metrics.aggressive_buy_ratio if delta_metrics else 0.5,
                "aggressive_sell_ratio": delta_metrics.aggressive_sell_ratio if delta_metrics else 0.5,
            } if delta_metrics else None,
            "vwap_detail": {
                "vwap": vwap_metrics.vwap if vwap_metrics else 0,
                "deviation": vwap_metrics.deviation if vwap_metrics else 0,
            } if vwap_metrics else None,
            "large_trade_detail": {
                "count": large_metrics.large_trade_count if large_metrics else 0,
                "concentration": large_metrics.concentration_ratio if large_metrics else 0,
            } if large_metrics else None,
            "absorption_detail": {
                "score": absorption_score,
                "direction": absorption_metrics.direction if absorption_metrics else "none",
                "price": absorption_metrics.absorbed_at_price if absorption_metrics else None,
            } if absorption_metrics else None,
            "sweep_detail": {
                "detected": liquidity_sweep,
                "direction": sweep_metrics.sweep_direction if sweep_metrics else "none",
                "magnitude": sweep_metrics.sweep_magnitude if sweep_metrics else 0,
            } if sweep_metrics else None,
        }

        return OrderFlowSignal(
            symbol=symbol,
            timestamp=timestamp,
            timeframe=timeframe,
            book_imbalance=round(book_imbalance, 4),
            bid_pressure=round(bid_pressure, 4),
            ask_pressure=round(ask_pressure, 4),
            delta=round(delta_val, 2),
            cum_delta=round(cum_delta_val, 2),
            absorption_score=round(absorption_score, 3),
            liquidity_sweep=liquidity_sweep,
            expected_slippage=round(slippage, 1),
            execution_condition=exec_quality,
            stop_hunt_zones=stop_zones,
            metadata=metadata,
        )

    # ─────────────────────────────────────────────────────────────
    # 批量分析
    # ─────────────────────────────────────────────────────────────

    def batch_analyze(
        self,
        data_map: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, OrderFlowSignal]:
        """
        批量分析多个标的.
        
        Args:
            data_map: {symbol: data} 映射
            
        Returns:
            {symbol: OrderFlowSignal} 映射
        """
        results = {}
        for symbol, data in data_map.items():
            try:
                results[symbol] = self.analyze(data, **kwargs)
            except Exception as exc:
                # 返回中性信号
                results[symbol] = OrderFlowSignal(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    timeframe=TimeFrame.M1,
                    metadata={"error": str(exc)},
                )
        return results

    # ─────────────────────────────────────────────────────────────
    # 生命周期
    # ─────────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        """引擎健康检查."""
        return True

    def reset(self) -> None:
        """重置引擎状态."""
        self._cum_delta = 0.0
