"""
Chan Theory Engine (缠论引擎)
=============================

包含:
- 分型识别 (Fractals)
- 笔构建 (Strokes)
- 线段划分 (Segments)
- 中枢识别 (Centers)
- 背驰判断 (Divergence)
- 买卖点判定 (Trading Points)
- 多级别联动 (Multi-timeframe)

输出: ChanSignal (继承 EngineSignal)
"""

from .engine import ChanEngine

__all__ = ["ChanEngine"]
