"""
Fundamental Engine (基本盘信息报表引擎)
=====================================

独立引擎，输出 FundamentalReport。

功能:
- 估值分析 (PE/PB/PS/PEG/EV/EBITDA)
- 质量分析 (ROE/ROA/毛利率/净利率/现金流质量)
- 成长分析 (营收/利润/EPS 增长)
- 杠杆/偿债能力 (负债率/流动比率/利息保障)
- 综合基本盘评分

输入:
  - 理想输入: FundamentalsSnapshot
  - Proxy 输入: MarketBar[] (OHLCV) ← 外部基本面数据暂不完整

输出: FundamentalReport

⚠️ Proxy 标注: 当 FundamentalsSnapshot 字段缺失时，metadata["proxy"] = True
"""

from .engine import FundamentalEngine

__all__ = ["FundamentalEngine"]
