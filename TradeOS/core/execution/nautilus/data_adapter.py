"""
Nautilus Data Adapter - ??????????????

????????? DataProvider ???????????Nautilus Data ???????????? QuoteTick, TradeTick, Bar ??????????????"""

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

from core.execution.nautilus.instrument_mapper import InstrumentMapper


class DataAdapter:
    """????????????????    
    ???????    - ????????????????-> Nautilus Data ?????????
    - ????? QuoteTick????????????radeTick????????????ar????????
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
        """?????????????????? Nautilus QuoteTick
        
        Args:
            symbol: ?????????
            bid_price: ?????
            bid_size: ?????
            ask_price: ?????
            ask_size: ?????
            timestamp: ???????            venue: ????????
            
        Returns:
            QuoteTick: Nautilus ??????????
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        instrument_id = self._mapper.to_instrument_id(symbol, venue)
        
        # ?????instrument ?????????
        instrument = self._mapper.get_cached(symbol)
        if instrument is None:
            instrument = self._mapper.create_equity(symbol, venue or "NASDAQ")
        
        # ??????????????????
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
        """?????????????????? Nautilus TradeTick
        
        Args:
            symbol: ?????????
            price: ???????            size: ???????            aggressor_side: ??????????????("BUY" or "SELL")
            trade_id: ?????D
            timestamp: ???????            venue: ????????
            
        Returns:
            TradeTick: Nautilus ??????????
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        from nautilus_trader.model.identifiers import TradeId
        
        instrument_id = self._mapper.to_instrument_id(symbol, venue)
        
        # ?????instrument ?????????
        instrument = self._mapper.get_cached(symbol)
        if instrument is None:
            instrument = self._mapper.create_equity(symbol, venue or "NASDAQ")
        
        # ??????????????????
        ts_ns = self._datetime_to_ns(timestamp)
        
        # ?????aggressor side
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
        bar_type: str,  # ??"AAPL.NASDAQ-1-MINUTE-LAST-EXTERNAL"
        venue: Optional[str] = None,
    ) -> "Bar":
        """?????????????????Nautilus Bar
        
        Args:
            symbol: ?????????
            open_price: ????????
            high_price: ????????
            low_price: ????????
            close_price: ???????            volume: ???????            timestamp: ???????            bar_type: K???????????            venue: ????????
            
        Returns:
            Bar: Nautilus K???????        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        from nautilus_trader.model.data import BarType
        
        instrument_id = self._mapper.to_instrument_id(symbol, venue)
        
        # ?????instrument ?????????
        instrument = self._mapper.get_cached(symbol)
        if instrument is None:
            instrument = self._mapper.create_equity(symbol, venue or "NASDAQ")
        
        # ??????????????????
        ts_ns = self._datetime_to_ns(timestamp)
        
        # ?????bar_type
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
        """??datetime ??????????????????
        
        Args:
            dt: Python datetime ?????
            
        Returns:
            int: ?????????????
        """
        # ??-> ?????
        seconds = dt.timestamp()
        return int(seconds * 1_000_000_000)
    
    def _ns_to_datetime(self, ns_timestamp: int) -> datetime:
        """????????????????????datetime
        
        Args:
            ns_timestamp: ?????????????
            
        Returns:
            datetime: Python datetime ?????
        """
        seconds = ns_timestamp / 1_000_000_000
        return datetime.fromtimestamp(seconds)

