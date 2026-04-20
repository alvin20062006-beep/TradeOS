"""Execution-layer enums."""

from __future__ import annotations

from enum import Enum


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"


class TimeInForce(Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    DAY = "DAY"
    GTD = "GTD"
    AT_THE_OPEN = "AT_THE_OPEN"
    AT_THE_CLOSE = "AT_THE_CLOSE"


class Urgency(Enum):
    PASSIVE = "PASSIVE"
    NORMAL = "NORMAL"
    AGGRESSIVE = "AGGRESSIVE"
    URGENT = "URGENT"


class ExecutionStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIAL_FILLED = "PARTIAL_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class LiquiditySide(Enum):
    MAKER = "MAKER"
    TAKER = "TAKER"


class RiskFlagType(Enum):
    SIZE_LIMIT = "SIZE_LIMIT"
    PRICE_LIMIT = "PRICE_LIMIT"
    TIMEOUT = "TIMEOUT"
    VOLATILITY = "VOLATILITY"
    CONCENTRATION = "CONCENTRATION"


class RiskSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCK = "BLOCK"


class ExecutionMode(Enum):
    SIMULATION = "SIMULATION"
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    LIVE = "LIVE"


class EngineStatus(Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"
