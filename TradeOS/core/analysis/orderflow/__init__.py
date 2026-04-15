"""
Order Flow Engine (盘口/订单流引擎)
==================================

独立引擎，不继承 AnalysisEngine（OrderFlowSignal 非 EngineSignal）。

功能:
- 订单簿失衡分析 (Book Imbalance)
- Delta/CVD 计算
- 主动买卖比例 (Aggressive Buy/Sell Ratio)
- VWAP 偏离
- 大单集中度 (Large Trade Ratio)
- 吸收检测 (Absorption)
- 流动性扫荡 (Liquidity Sweep)
- 执行质量预测

输入: OrderBookSnapshot + TradePrint[]
输出: OrderFlowSignal

⚠️ Proxy 版本: 当数据层暂不完整时，可从 OHLCV bars 合成代理数据
"""

from .engine import OrderFlowEngine

__all__ = ["OrderFlowEngine"]
