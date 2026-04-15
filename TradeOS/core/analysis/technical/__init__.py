"""
Technical Analysis Engine (经典技术分析引擎)
=========================================

包含:
- 趋势指标: MA(5/20/60/120) / ADX(14)
- 动量指标: MACD(12/26/9) / RSI(14) / KDJ / CCI
- 波动率指标: ATR(14) / Bollinger Bands(20,2)
- 图表形态: 头肩 / 双顶 / 三角形
- K线形态: 吞没 / 十字星 / pin bar
- 支撑阻力位检测

输出: TechnicalSignal (继承 EngineSignal)
"""

from .engine import TechnicalEngine

__all__ = ["TechnicalEngine"]
