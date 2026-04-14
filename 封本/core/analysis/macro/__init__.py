"""
Macro Engine (宏观消息引擎)
===========================

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

⚠️ Proxy 标注: 当无真实宏观事件时，从 OHLCV bars + 波动性估算
"""

from .engine import MacroEngine

__all__ = ["MacroEngine"]
