"""
Nautilus Data Adapter - 琛屾儏鏁版嵁閫傞厤

灏嗘湰椤圭洰 DataProvider 鏁版嵁杞崲涓?Nautilus Data 瀵硅薄銆?鏀寔 QuoteTick, TradeTick, Bar 绛夋暟鎹被鍨嬨€?"""

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
    """琛屾儏鏁版嵁閫傞厤鍣?    
    璐熻矗锛?    - 鏈」鐩競鍦烘暟鎹?-> Nautilus Data 瀵硅薄杞崲
    - 鏀寔 QuoteTick锛堟姤浠凤級銆乀radeTick锛堟垚浜わ級銆丅ar锛圞绾匡級
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
        """灏嗘姤浠锋暟鎹浆鎹负 Nautilus QuoteTick
        
        Args:
            symbol: 鏍囩殑浠ｇ爜
            bid_price: 涔颁环
            bid_size: 涔伴噺
            ask_price: 鍗栦环
            ask_size: 鍗栭噺
            timestamp: 鏃堕棿鎴?            venue: 浜ゆ槗鎵€
            
        Returns:
            QuoteTick: Nautilus 鎶ヤ环瀵硅薄
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        instrument_id = self._mapper.to_instrument_id(symbol, venue)
        
        # 鑾峰彇 instrument 鐢ㄤ簬绮惧害
        instrument = self._mapper.get_cached(symbol)
        if instrument is None:
            instrument = self._mapper.create_equity(symbol, venue or "NASDAQ")
        
        # 杞崲鏃堕棿鎴充负绾崇
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
        """灏嗘垚浜ゆ暟鎹浆鎹负 Nautilus TradeTick
        
        Args:
            symbol: 鏍囩殑浠ｇ爜
            price: 鎴愪氦浠?            size: 鎴愪氦閲?            aggressor_side: 涓诲姩鎴愪氦鏂瑰悜 ("BUY" or "SELL")
            trade_id: 鎴愪氦ID
            timestamp: 鏃堕棿鎴?            venue: 浜ゆ槗鎵€
            
        Returns:
            TradeTick: Nautilus 鎴愪氦瀵硅薄
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        from nautilus_trader.model.identifiers import TradeId
        
        instrument_id = self._mapper.to_instrument_id(symbol, venue)
        
        # 鑾峰彇 instrument 鐢ㄤ簬绮惧害
        instrument = self._mapper.get_cached(symbol)
        if instrument is None:
            instrument = self._mapper.create_equity(symbol, venue or "NASDAQ")
        
        # 杞崲鏃堕棿鎴充负绾崇
        ts_ns = self._datetime_to_ns(timestamp)
        
        # 杞崲 aggressor side
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
        bar_type: str,  # 濡?"AAPL.NASDAQ-1-MINUTE-LAST-EXTERNAL"
        venue: Optional[str] = None,
    ) -> "Bar":
        """灏咾绾挎暟鎹浆鎹负 Nautilus Bar
        
        Args:
            symbol: 鏍囩殑浠ｇ爜
            open_price: 寮€鐩樹环
            high_price: 鏈€楂樹环
            low_price: 鏈€浣庝环
            close_price: 鏀剁洏浠?            volume: 鎴愪氦閲?            timestamp: 鏃堕棿鎴?            bar_type: K绾跨被鍨嬫爣璇?            venue: 浜ゆ槗鎵€
            
        Returns:
            Bar: Nautilus K绾垮璞?        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        from nautilus_trader.model.data import BarType
        
        instrument_id = self._mapper.to_instrument_id(symbol, venue)
        
        # 鑾峰彇 instrument 鐢ㄤ簬绮惧害
        instrument = self._mapper.get_cached(symbol)
        if instrument is None:
            instrument = self._mapper.create_equity(symbol, venue or "NASDAQ")
        
        # 杞崲鏃堕棿鎴充负绾崇
        ts_ns = self._datetime_to_ns(timestamp)
        
        # 瑙ｆ瀽 bar_type
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
        """灏?datetime 杞崲涓虹撼绉掓椂闂存埑
        
        Args:
            dt: Python datetime 瀵硅薄
            
        Returns:
            int: 绾崇绾ф椂闂存埑
        """
        # 绉?-> 绾崇
        seconds = dt.timestamp()
        return int(seconds * 1_000_000_000)
    
    def _ns_to_datetime(self, ns_timestamp: int) -> datetime:
        """灏嗙撼绉掓椂闂存埑杞崲涓?datetime
        
        Args:
            ns_timestamp: 绾崇绾ф椂闂存埑
            
        Returns:
            datetime: Python datetime 瀵硅薄
        """
        seconds = ns_timestamp / 1_000_000_000
        return datetime.fromtimestamp(seconds)

