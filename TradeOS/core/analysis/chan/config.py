"""
缠论配置模块
============

定义缠论引擎的默认参数。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ChanConfig:
    """
    缠论引擎配置参数.
    
    所有参数均可按需调整。
    """
    # 笔参数
    bi_min_bars: int = 5           # 笔的最少K线数（不含顶底分型）
    bi_min_height_ratio: float = 0.0  # 笔最小高度占整体幅度的比例
    
    # 线段参数
    segment_min_strokes: int = 3   # 线段最少笔数
    segment_back_ratio: float = 0.5  # 线段回撤比例（后笔回到前笔的比例）
    
    # 中枢参数
    center_min_segments: int = 3   # 中枢最少重叠线段数
    
    # 背驰参数
    divergence_macd_periods: tuple[int, int, int] = (12, 26, 9)  # MACD参数
    
    # 买卖点参数
    purchase_confidence: float = 0.6   # 最小置信度
    risk_reward_min: float = 1.5        # 最小风险收益比
    
    # 多级别
    higher_timeframe: str = "D"   # 上一级别
    lower_timeframe: str = "30m"  # 下一级别
    
    # 辅助指标
    use_volume_filter: bool = True  # 是否使用成交量过滤
    volume_threshold: float = 0.5   # 成交量相对阈值


# 默认配置
DEFAULT_CONFIG = ChanConfig()
