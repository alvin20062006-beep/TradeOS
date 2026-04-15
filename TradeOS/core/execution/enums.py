"""
Execution Enums - 本项目自己的执行层枚举定义

不依赖外部枚举，所有执行相关枚举在此统一定义。
"""

from __future__ import annotations

from enum import Enum, auto


class Side(Enum):
    """交易方向"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """订单类型"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"


class TimeInForce(Enum):
    """订单有效期"""
    GTC = "GTC"           # Good Till Cancelled
    IOC = "IOC"           # Immediate Or Cancel
    FOK = "FOK"           # Fill Or Kill
    DAY = "DAY"           # Day order
    GTD = "GTD"           # Good Till Date
    AT_THE_OPEN = "AT_THE_OPEN"     # 开市单
    AT_THE_CLOSE = "AT_THE_CLOSE"   # 收市单


class Urgency(Enum):
    """执行紧急程度
    
    预留参数，Phase 7 平方根执行算法使用
    """
    PASSIVE = "PASSIVE"   # 被动，追求价格
    NORMAL = "NORMAL"     # 正常
    AGGRESSIVE = "AGGRESSIVE"  # 激进，追求成交
    URGENT = "URGENT"     # 紧急


class ExecutionStatus(Enum):
    """执行状态生命周期"""
    PENDING = "PENDING"           # 待提交
    SUBMITTED = "SUBMITTED"       # 已提交
    ACKNOWLEDGED = "ACKNOWLEDGED" # 已确认
    PARTIAL_FILLED = "PARTIAL_FILLED"  # 部分成交
    FILLED = "FILLED"             # 完全成交
    CANCELLED = "CANCELLED"       # 已取消
    REJECTED = "REJECTED"         # 被拒绝
    EXPIRED = "EXPIRED"           # 已过期


class LiquiditySide(Enum):
    """流动性方向"""
    MAKER = "MAKER"       # 提供流动性
    TAKER = "TAKER"       # 消耗流动性


class RiskFlagType(Enum):
    """风险标记类型"""
    SIZE_LIMIT = "SIZE_LIMIT"
    PRICE_LIMIT = "PRICE_LIMIT"
    TIMEOUT = "TIMEOUT"
    VOLATILITY = "VOLATILITY"
    CONCENTRATION = "CONCENTRATION"


class RiskSeverity(Enum):
    """风险严重程度"""
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCK = "BLOCK"


class ExecutionMode(Enum):
    """执行模式"""
    BACKTEST = "BACKTEST"   # 回测模式
    PAPER = "PAPER"         # 模拟交易
    LIVE = "LIVE"           # 实盘交易


class EngineStatus(Enum):
    """引擎状态"""
    STOPPED = "STOPPED"       # 已停止
    STARTING = "STARTING"     # 启动中
    RUNNING = "RUNNING"       # 运行中
    STOPPING = "STOPPING"     # 停止中
    ERROR = "ERROR"           # 错误状态
