"""
Nautilus Data Adapter - 行情数据适配

将本项目 DataProvider 数据转换为 Nautilus Data 对象。
支持 QuoteTick, TradeTick, Bar 等数据类型。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

try:
    from nautilus_trader.model.data import QuoteTick, TradeTick, Bar
    from nautilus_trader.model.enums import AggressorSide
    from nautilus_trader.model.objects import Price, Quantity
    NAUTILUS_AVAILABLE = True
except ImportError:
    NAUTILUS_AVAILABLE = False
    QuoteTick = TradeTick = Bar = object
    AggressorSide = object
    Price = Quantity = object

from ai_trading_tool.core.execution.nautilus.instrument_mapper import InstrumentMapper


class DataAdapter:
    """行情数据适配器
    
    负责：
    - 本项目市场数据 -> Nautilus Data 对象转换
    - 支持 QuoteTick（报价）、TradeTick（成交）、Bar（K线）
    """
    
    def __init__(self, instrument_mapper: InstrumentMapper):
        self._mapper = instrument_mapper
    
    def adapt_quote(
        self,
        symbol: str,
        bid_price: Decimal,
        bid_size: Decimal,
        ask_price: Decimal,
        ask_size: Decimal,
        timestamp: datetime,
        venue: Optional[str] = None,
    ) -> "QuoteTick":
        """将报价数据转换为 Nautilus QuoteTick
        
        Args:
            symbol: 标的代码
            bid_price: 买价
            bid_size: 买量
            ask_price: 卖价
            ask_size: 卖量
            timestamp: 时间戳
            venue: 交易所
            
        Returns:
            QuoteTick: Nautilus 报价对象
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        instrument_id = self._mapper.to_instrument_id(symbol, venue)
        
        # 获取 instrument 用于精度
        instrument = self._mapper.get_cached(symbol)
        if instrument is None:
            instrument = self._mapper.create_equity(symbol, venue or "NASDAQ")
        
        # 转换时间戳为纳秒
        ts_ns = self._datetime_to_ns(timestamp)
        
        return QuoteTick(
            instrument_id=instrument_id,
            bid_price=Price(bid_price, instrument.price_precision),
            ask_price=Price(ask_price, instrument.price_precision),
            bid_size=Quantity(bid_size, instrument.size_precision),
            ask_size=Quantity(ask_size, instrument.size_precision),
            ts_event=ts_ns,
            ts_init=ts_ns,
        )
    
    def adapt_trade(
        self,
        symbol: str,
        price: Decimal,
        size: Decimal,
        aggressor_side: str,  # "BUY" or "SELL"
        trade_id: str,
        timestamp: datetime,
        venue: Optional[str] = None,
    ) -> "TradeTick":
        """将成交数据转换为 Nautilus TradeTick
        
        Args:
            symbol: 标的代码
            price: 成交价
            size: 成交量
            aggressor_side: 主动成交方向 ("BUY" or "SELL")
            trade_id: 成交ID
            timestamp: 时间戳
            venue: 交易所
            
        Returns:
            TradeTick: Nautilus 成交对象
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        from nautilus_trader.model.identifiers import TradeId
        
        instrument_id = self._mapper.to_instrument_id(symbol, venue)
        
        # 获取 instrument 用于精度
        instrument = self._mapper.get_cached(symbol)
        if instrument is None:
            instrument = self._mapper.create_equity(symbol, venue or "NASDAQ")
        
        # 转换时间戳为纳秒
        ts_ns = self._datetime_to_ns(timestamp)
        
        # 转换 aggressor side
        if aggressor_side.upper() == "BUY":
            side = AggressorSide.BUYER
        else:
            side = AggressorSide.SELLER
        
        return TradeTick(
            instrument_id=instrument_id,
            price=Price(price, instrument.price_precision),
            size=Quantity(size, instrument.size_precision),
            aggressor_side=side,
            trade_id=TradeId(trade_id),
            ts_event=ts_ns,
            ts_init=ts_ns,
        )
    
    def adapt_bar(
        self,
        symbol: str,
        open_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        close_price: Decimal,
        volume: Decimal,
        timestamp: datetime,
        bar_type: str,  # 如 "AAPL.NASDAQ-1-MINUTE-LAST-EXTERNAL"
        venue: Optional[str] = None,
    ) -> "Bar":
        """将K线数据转换为 Nautilus Bar
        
        Args:
            symbol: 标的代码
            open_price: 开盘价
            high_price: 最高价
            low_price: 最低价
            close_price: 收盘价
            volume: 成交量
            timestamp: 时间戳
            bar_type: K线类型标识
            venue: 交易所
            
        Returns:
            Bar: Nautilus K线对象
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        from nautilus_trader.model.data import BarType
        
        instrument_id = self._mapper.to_instrument_id(symbol, venue)
        
        # 获取 instrument 用于精度
        instrument = self._mapper.get_cached(symbol)
        if instrument is None:
            instrument = self._mapper.create_equity(symbol, venue or "NASDAQ")
        
        # 转换时间戳为纳秒
        ts_ns = self._datetime_to_ns(timestamp)
        
        # 解析 bar_type
        bar_type_obj = BarType.from_str(bar_type)
        
        return Bar(
            bar_type=bar_type_obj,
            open=Price(open_price, instrument.price_precision),
            high=Price(high_price, instrument.price_precision),
            low=Price(low_price, instrument.price_precision),
            close=Price(close_price, instrument.price_precision),
            volume=Quantity(volume, instrument.size_precision),
            ts_event=ts_ns,
            ts_init=ts_ns,
        )
    
    def _datetime_to_ns(self, dt: datetime) -> int:
        """将 datetime 转换为纳秒时间戳
        
        Args:
            dt: Python datetime 对象
            
        Returns:
            int: 纳秒级时间戳
        """
        # 秒 -> 纳秒
        seconds = dt.timestamp()
        return int(seconds * 1_000_000_000)
    
    def _ns_to_datetime(self, ns_timestamp: int) -> datetime:
        """将纳秒时间戳转换为 datetime
        
        Args:
            ns_timestamp: 纳秒级时间戳
            
        Returns:
            datetime: Python datetime 对象
        """
        seconds = ns_timestamp / 1_000_000_000
        return datetime.fromtimestamp(seconds)
