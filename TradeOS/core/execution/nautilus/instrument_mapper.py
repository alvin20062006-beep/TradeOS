"""
Nautilus Instrument Mapper - ??????

????????? symbol ????????Nautilus Instrument ????????????????????????????"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

try:
    from nautilus_trader.model.identifiers import (
        InstrumentId,
        Symbol,
        Venue,
    )
    from nautilus_trader.model.instruments import Instrument, Equity, CryptoPerpetual
    from nautilus_trader.model.objects import Currency
    NAUTILUS_AVAILABLE = True
except ImportError:
    NAUTILUS_AVAILABLE = False
    # ??????
    InstrumentId = Symbol = Venue = Instrument = Equity = CryptoPerpetual = object
    Currency = object


class InstrumentMapper:
    """????????    
    ?????    - symbol -> InstrumentId ???
    - InstrumentId -> symbol ???
    - ??? Nautilus Instrument ???????????    """
    
    def __init__(self):
        self._cache: dict[str, Instrument] = {}
    
    def to_instrument_id(
        self,
        symbol: str,
        venue: Optional[str] = None,
    ) -> "InstrumentId":
        """?????? symbol ?????Nautilus InstrumentId
        
        Args:
            symbol: ????????? "AAPL", "BTCUSDT"
            venue: ???????? "NASDAQ", "BINANCE"
            
        Returns:
            InstrumentId: Nautilus ??????
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        # ??? venue
        if venue is None:
            venue = self._infer_venue(symbol)
        
        return InstrumentId(
            symbol=Symbol(symbol),
            venue=Venue(venue),
        )
    
    def from_instrument_id(self, instrument_id: "InstrumentId") -> tuple[str, str]:
        """??Nautilus InstrumentId ????????????
        
        Returns:
            tuple: (symbol, venue)
        """
        return (
            str(instrument_id.symbol),
            str(instrument_id.venue),
        )
    
    def _infer_venue(self, symbol: str) -> str:
        """??? symbol ??? venue"""
        symbol_upper = symbol.upper()
        
        # ????????????
        if any(suffix in symbol_upper for suffix in ["USDT", "USD", "BTC", "ETH"]):
            return "BINANCE"
        
        # ??????
        return "NASDAQ"
    
    def create_equity(
        self,
        symbol: str,
        venue: str = "NASDAQ",
        price_precision: int = 2,
        min_price: Optional[Decimal] = None,
        lot_size: Optional[Decimal] = None,
        margin_init: Decimal = Decimal("0"),
        margin_maint: Decimal = Decimal("0"),
        maker_fee: Decimal = Decimal("0.001"),
        taker_fee: Decimal = Decimal("0.001"),
    ) -> "Equity":
        """?????? Instrument????????        
        Args:
            symbol: ??????
            venue: ?????
            price_precision: ??????????????            min_price: ????????tick size??            lot_size: ?????            margin_init: ?????????
            margin_maint: ?????????
            maker_fee: Maker ??????
            taker_fee: Taker ??????
            
        Returns:
            Equity: Nautilus Equity ???
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        from nautilus_trader.model.objects import Price, Quantity
        
        instrument_id = self.to_instrument_id(symbol, venue)
        
        if min_price is None:
            min_price = Decimal("0.01")
        if lot_size is None:
            lot_size = Decimal("1")
        
        equity = Equity(
            instrument_id=instrument_id,
            raw_symbol=Symbol(symbol),
            currency=Currency.from_str("USD"),
            price_precision=price_precision,
            price_increment=Price(min_price, price_precision),
            lot_size=Quantity(float(lot_size), 0),
            ts_event=0,
            ts_init=0,
            margin_init=margin_init,
            margin_maint=margin_maint,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
        )
        
        # ???
        self._cache[symbol] = equity
        
        return equity
    
    def create_crypto_perpetual(
        self,
        symbol: str,
        venue: str = "BINANCE",
        base_currency: str = "BTC",
        quote_currency: str = "USDT",
        price_precision: int = 2,
        size_precision: int = 6,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        min_size: Optional[Decimal] = None,
        max_size: Optional[Decimal] = None,
        margin_init: Decimal = Decimal("0.1"),
        margin_maint: Decimal = Decimal("0.05"),
        maker_fee: Decimal = Decimal("0.0002"),
        taker_fee: Decimal = Decimal("0.0005"),
    ) -> "CryptoPerpetual":
        """??????????????? Instrument????????        
        Args:
            symbol: ???????????"BTCUSDT"
            venue: ?????
            base_currency: ??????
            quote_currency: ??????
            price_precision: ??????
            size_precision: ??????
            min_price: ???????            max_price: ???????            min_size: ???????            max_size: ???????            margin_init: ?????????
            margin_maint: ?????????
            maker_fee: Maker ??????
            taker_fee: Taker ??????
            
        Returns:
            CryptoPerpetual: Nautilus CryptoPerpetual ???
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        from nautilus_trader.model.objects import Price, Quantity, Money
        from nautilus_trader.model.currencies import Currency
        
        instrument_id = self.to_instrument_id(symbol, venue)
        
        if min_price is None:
            min_price = Decimal("0.01")
        if max_price is None:
            max_price = Decimal("10000000")
        if min_size is None:
            min_size = Decimal("0.000001")
        if max_size is None:
            max_size = Decimal("10000")
        
        # ?????????
        base = Currency.from_str(base_currency)
        quote = Currency.from_str(quote_currency)
        
        crypto = CryptoPerpetual(
            instrument_id=instrument_id,
            raw_symbol=Symbol(symbol),
            base_currency=base,
            quote_currency=quote,
            settlement_currency=quote,
            is_inverse=False,
            price_precision=price_precision,
            size_precision=size_precision,
            price_increment=Price(min_price, price_precision),
            size_increment=Quantity(min_size, size_precision),
            multiplier=Quantity.from_int(1),
            lot_size=Quantity.from_int(1),
            max_quantity=Quantity(max_size, size_precision),
            min_quantity=Quantity(min_size, size_precision),
            max_notional=None,
            min_notional=None,
            max_price=Price(max_price, price_precision),
            min_price=Price(min_price, price_precision),
            margin_init=margin_init,
            margin_maint=margin_maint,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            ts_event=0,
            ts_init=0,
        )
        
        # ???
        self._cache[symbol] = crypto
        
        return crypto
    
    def get_cached(self, symbol: str) -> Optional["Instrument"]:
        """????????Instrument"""
        return self._cache.get(symbol)
    
    def clear_cache(self) -> None:
        """??????"""
        self._cache.clear()
