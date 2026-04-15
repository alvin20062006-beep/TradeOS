"""
Macro Engine (宏观消息引擎)
==========================

独立引擎，输出 MacroSignal。

功能:
- 利率变化 / rate pressure
- 通胀冲击 / inflation surprise
- 流动性状态 / liquidity condition
- 风险事件强度 / event shock score
- 宏观 regime（risk-on / risk-off / stagflation / deflationary）

输入:
  - 理想输入: MacroEvent[] + VIX/MOVE 数据
  - Proxy 输入: MarketBar[] (OHLCV) ← 外部宏观数据源暂不完整

输出: MacroSignal

⚠️ Proxy 标注: 当无真实宏观事件时，metadata["proxy"] = True
"""

from __future__ import annotations

import numpy as np
from datetime import datetime
from typing import Optional, Any

from core.schemas import (
    MacroSignal,
    MacroEvent,
    MarketBar,
    Regime,
)

from . import rate_pressure
from . import inflation_shock
from . import liquidity
from . import event_shock
from . import regime_detector


class MacroEngine:
    """
    宏观消息引擎.

    独立实现，不继承 AnalysisEngine（MacroSignal 非 EngineSignal）。

    支持两种输入模式:
    1. 完整模式: MacroEvent[] + 市场数据 → 精确计算
    2. Proxy 模式: MarketBar[] → 从 OHLCV 估算
    """

    engine_name = "macro"

    DEFAULT_CONFIG = {
        "lookback": 60,
        "volume_lookback": 20,
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

    # ─────────────────────────────────────────────────────────────
    # 主入口
    # ─────────────────────────────────────────────────────────────

    def analyze(
        self,
        data: Any,
        macro_events: Optional[list[MacroEvent]] = None,
        vix_level: Optional[float] = None,
        **kwargs: Any,
    ) -> MacroSignal:
        """
        执行宏观分析.

        Args:
            data: 输入数据:
                  - MarketBar[]: OHLCV bars（Proxy 模式）
                  - dict{"bars": [...], "events": [...]}: 完整
            macro_events: 可选的宏观事件列表
            vix_level: VIX 水平（可选）
            **kwargs: 其他参数

        Returns:
            MacroSignal
        """
        # 1. 解析输入
        bars, events, is_proxy = self._parse_input(data, macro_events)

        # 2. 提取 OHLCV arrays
        if bars:
            highs = np.array([b.high for b in bars])
            lows = np.array([b.low for b in bars])
            closes = np.array([b.close for b in bars])
            volumes = np.array([b.volume for b in bars])
            timestamp = bars[-1].timestamp
        else:
            highs = lows = closes = volumes = np.array([])
            timestamp = datetime.utcnow()

        # 3. 提取市场数据
        if len(closes) > 0:
            returns_1d = float((closes[-1] - closes[-2]) / closes[-2]) if len(closes) > 1 else 0.0
            returns = np.diff(closes) / closes[:-1]
            volatility_20d = float(np.std(returns[-20:])) if len(returns) >= 20 else float(np.std(returns))
            lookback = min(self.config["lookback"], len(closes))
            returns_60d = float((closes[-1] - closes[-lookback]) / closes[-lookback]) if lookback > 1 else 0.0
        else:
            returns_1d = 0.0
            volatility_20d = 0.01
            returns_60d = 0.0

        # 4. VIX / 波动性
        vix = vix_level if vix_level is not None else self._estimate_vix(volatility_20d)

        # 5. 利率压力
        rate_met = self._analyze_rate(events, returns_1d, volatility_20d)

        # 6. 通胀冲击
        infl_met = self._analyze_inflation(events, volatility_20d)

        # 7. 流动性
        liq_met = self._analyze_liquidity(highs, lows, closes, volumes)

        # 8. 事件冲击
        shock_met = self._analyze_shock(events, returns_1d, volatility_20d)

        # 9. 宏观 Regime
        regime_met = self._analyze_regime(events, rate_met, infl_met, liq_met, highs, lows, closes, volumes)

        # 10. 主导主题
        themes = self._extract_themes(rate_met, infl_met, shock_met, regime_met)

        # 11. 资产配置偏见
        biases = self._calc_asset_biases(rate_met, infl_met, shock_met, regime_met, liq_met)

        # 12. 高影响事件列表
        high_impact = [e.event_name for e in events if e.impact == "high"] if events else []

        # 13. Risk-On/Off
        risk_on = regime_met.regime in [
            regime_detector.MacroRegime.RISK_ON,
            regime_detector.MacroRegime.NEUTRAL,
        ]

        # 14. 转换 Regime 枚举
        mapped_regime = self._map_regime(regime_met.regime)

        return MacroSignal(
            timestamp=timestamp,
            regime=mapped_regime,
            regime_confidence=regime_met.confidence,
            dominant_themes=themes,
            risk_on=risk_on,
            equity_bias=biases["equity"],
            bond_bias=biases["bond"],
            commodity_bias=biases["commodity"],
            fx_bias=biases["fx"],
            vix_level=round(vix, 2),
            high_impact_events=high_impact,
            metadata={
                "proxy": is_proxy,
                "rate_detail": {
                    "direction": rate_met.rate_direction.value,
                    "pressure_score": rate_met.pressure_score,
                    "central_bank_stance": rate_met.central_bank_stance,
                    "shock_probability": rate_met.rate_shock_probability,
                    "is_proxy": is_proxy,
                },
                "inflation_detail": {
                    "shock_score": infl_met.shock_score,
                    "direction": infl_met.direction,
                    "unexpected": infl_met.unexpected,
                    "is_proxy": is_proxy,
                },
                "liquidity_detail": {
                    "condition": liq_met.condition,
                    "score": liq_met.score,
                    "is_proxy": liq_met.is_proxy,
                },
                "shock_detail": {
                    "shock_score": shock_met.shock_score,
                    "category": shock_met.category,
                    "affected_assets": shock_met.affected_assets,
                    "duration_hours": shock_met.duration_hours,
                    "is_proxy": shock_met.is_proxy,
                },
                "regime_detail": {
                    "macro_regime": regime_met.regime.value,
                    "growth_outlook": regime_met.growth_outlook,
                    "inflation_outlook": regime_met.inflation_outlook,
                    "is_proxy": is_proxy,
                },
            },
        )

    # ─────────────────────────────────────────────────────────────
    # 输入解析
    # ─────────────────────────────────────────────────────────────

    def _parse_input(self, data: Any, macro_events: Optional[list[MacroEvent]]) -> tuple:
        """解析输入数据."""
        bars = []
        events = macro_events or []
        is_proxy = True

        if data is None:
            return bars, events, is_proxy

        if isinstance(data, dict):
            if "bars" in data:
                bars = self._to_bars(data["bars"])
            if "events" in data and not events:
                events = [e if isinstance(e, MacroEvent) else MacroEvent(**e) for e in data["events"]]
        elif isinstance(data, (list, tuple)):
            if data and isinstance(data[0], MarketBar):
                bars = list(data)

        is_proxy = not events
        return bars, events, is_proxy

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

    def _estimate_vix(self, volatility_20d: float) -> float:
        """从日波动率估算 VIX 水平（Proxy）."""
        # VIX ≈ 年化波动率 × 100
        return min(80.0, volatility_20d * np.sqrt(252) * 100)

    # ─────────────────────────────────────────────────────────────
    # 子模块分析
    # ─────────────────────────────────────────────────────────────

    def _analyze_rate(self, events, returns_1d, volatility_20d):
        """利率压力分析."""
        if events:
            # 从宏观事件提取
            rate_events = [
                e for e in events
                if any(k in e.event_name.lower()
                       for k in ["rate", "fed", "ecb", "boe", "货币政策", "fomc"])
            ]
            if rate_events:
                # 用最高影响的事件
                high = next((e for e in rate_events if e.impact == "high"), None)
                event = high or rate_events[0]
                return rate_pressure.parse_macro_event_rate(event.event_name, event.impact)
        # Proxy
        return rate_pressure.calc_rate_pressure_proxy(
            returns_1d=returns_1d,
            volatility_20d=volatility_20d,
        )

    def _analyze_inflation(self, events, volatility_20d):
        """通胀冲击分析."""
        if events:
            infl_events = [
                e for e in events
                if any(k in e.event_name.lower()
                       for k in ["cpi", "ppi", "pce", "inflation", "通胀", "消费者"])
            ]
            if infl_events:
                event = infl_events[0]
                # 尝试获取 actual/consensus（如果有的话）
                # MacroEvent 没有 actual/consensus 字段，这里用占位
                return inflation_shock.calc_inflation_shock_proxy(volatility=volatility_20d)
        return inflation_shock.calc_inflation_shock_proxy(volatility=volatility_20d)

    def _analyze_liquidity(self, highs, lows, closes, volumes):
        """流动性分析."""
        if len(closes) > 0:
            return liquidity.calc_liquidity_from_bars(
                highs, lows, closes, volumes,
                lookback=self.config["volume_lookback"],
            )
        return liquidity.LiquidityCondition(
            condition="normal", score=0.5,
            spread_proxy=0.0, depth_proxy=0.0, is_proxy=True,
        )

    def _analyze_shock(self, events, returns_1d, volatility_20d):
        """事件冲击分析."""
        if events:
            high_events = [e for e in events if e.impact == "high"]
            if high_events:
                event = high_events[0]
                return event_shock.calc_event_shock(
                    event.event_name, event.country, event.impact,
                )
        # Proxy: 从市场表现估算
        return event_shock.calc_shock_from_returns(
            returns_1d, volatility_20d,
        )

    def _analyze_regime(self, events, rate_met, infl_met, liq_met, highs, lows, closes, volumes):
        """宏观 Regime 分析."""
        if events and not all(volumes[i] == 0 for i in range(len(volumes))):
            return regime_detector.detect_regime_from_macro_events(
                events, rate_met, infl_met, liq_met,
            )
        elif len(closes) >= self.config["lookback"]:
            return regime_detector.detect_macro_regime_proxy(
                closes, highs, lows, volumes,
                lookback=self.config["lookback"],
            )
        return regime_detector.MacroRegimeMetrics(
            regime=regime_detector.MacroRegime.NEUTRAL,
            confidence=0.0,
            growth_outlook="stable",
            inflation_outlook="stable",
        )

    # ─────────────────────────────────────────────────────────────
    # 辅助方法
    # ─────────────────────────────────────────────────────────────

    def _extract_themes(self, rate_met, infl_met, shock_met, regime_met) -> list[str]:
        """提取主导宏观主题."""
        themes = []

        # 利率主题
        if rate_met.rate_direction.value == "hiking":
            themes.append("rate_hike")
        elif rate_met.rate_direction.value == "cutting":
            themes.append("rate_cut")

        # 通胀主题
        if infl_met.direction == "hot":
            themes.append("inflation")
        elif infl_met.direction == "cold":
            themes.append("deflation")

        # 流动性
        if infl_met.unexpected:
            themes.append("inflation_surprise")

        # 冲击
        if shock_met.shock_score > 0.6:
            themes.append(shock_met.category)

        # Regime
        regime_map = {
            regime_detector.MacroRegime.RISK_ON: "risk_on",
            regime_detector.MacroRegime.RISK_OFF: "risk_off",
            regime_detector.MacroRegime.STAGFLATION: "stagflation",
            regime_detector.MacroRegime.DEFLATIONARY: "deflationary",
        }
        themes.append(regime_map.get(regime_met.regime, "neutral"))

        return list(set(themes))

    def _calc_asset_biases(
        self, rate_met, infl_met, shock_met, regime_met, liq_met
    ) -> dict:
        """计算资产配置偏见."""
        # 初始化：基于 regime
        if regime_met.regime == regime_detector.MacroRegime.RISK_ON:
            equity, bond, commodity, fx = "bullish", "neutral", "bullish", "neutral"
        elif regime_met.regime == regime_detector.MacroRegime.RISK_OFF:
            equity, bond, commodity, fx = "bearish", "bullish", "neutral", "neutral"
        else:
            equity, bond, commodity, fx = "neutral", "neutral", "neutral", "neutral"

        # 通胀加成
        if infl_met.direction == "hot":
            equity = "bearish"
            bond = "bearish"
            commodity = "bullish"

        # 利率加成
        if rate_met.rate_direction.value == "hiking":
            bond = "bearish"
            equity = "bearish"
        elif rate_met.rate_direction.value == "cutting":
            bond = "bullish"

        # 流动性加成
        if liq_met.condition in ["strained", "crisis"]:
            equity = "bearish"

        # 冲击加成
        if shock_met.affected_assets:
            for asset, impact in shock_met.affected_assets.items():
                if asset == "equity":
                    equity = impact
                elif asset == "bond":
                    bond = impact
                elif asset == "commodity":
                    commodity = impact
                elif asset == "fx":
                    fx = impact  # 这里 fx 仍是字符串

        return {
            "equity": equity,
            "bond": bond,
            "commodity": commodity,
            "fx": {"DXY": fx},  # 默认用 DXY 美元指数
        }

    def _map_regime(self, macro_regime: regime_detector.MacroRegime) -> Regime:
        """将 MacroRegime 映射到 schema.Regime."""
        mapping = {
            regime_detector.MacroRegime.RISK_ON: Regime.TRENDING_UP,
            regime_detector.MacroRegime.RISK_OFF: Regime.TRENDING_DOWN,
            regime_detector.MacroRegime.STAGFLATION: Regime.VOLATILE,
            regime_detector.MacroRegime.DEFLATIONARY: Regime.TRENDING_DOWN,
            regime_detector.MacroRegime.NEUTRAL: Regime.RANGING,
        }
        return mapping.get(macro_regime, Regime.UNKNOWN)

    # ─────────────────────────────────────────────────────────────
    # 批量分析
    # ─────────────────────────────────────────────────────────────

    def batch_analyze(
        self,
        data_map: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, MacroSignal]:
        """批量分析."""
        results = {}
        for symbol, data in data_map.items():
            try:
                results[symbol] = self.analyze(data, **kwargs)
            except Exception as exc:
                results[symbol] = MacroSignal(
                    timestamp=datetime.utcnow(),
                    regime=Regime.UNKNOWN,
                    metadata={"error": str(exc)},
                )
        return results

    # ─────────────────────────────────────────────────────────────
    # 生命周期
    # ─────────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        """健康检查."""
        return True
