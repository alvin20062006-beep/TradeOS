"""
Nautilus Instrument Mapper - 标的映射

将本项目内部 symbol 格式映射到 Nautilus Instrument 对象。
支持股票、加密货币等资产类型。
"""

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
    # 占位类型
    InstrumentId = Symbol = Venue = Instrument = Equity = CryptoPerpetual = object
    Currency = object


class InstrumentMapper:
    """标的映射器
    
    负责：
    - symbol -> InstrumentId 转换
    - InstrumentId -> symbol 转换
    - 创建 Nautilus Instrument 对象（回测用）
    """
    
    def __init__(self):
        self._cache: dict[str, Instrument] = {}
    
    def to_instrument_id(
        self,
        symbol: str,
        venue: Optional[str] = None,
    ) -> "InstrumentId":
        """将本项目 symbol 转换为 Nautilus InstrumentId
        
        Args:
            symbol: 标的代码，如 "AAPL", "BTCUSDT"
            venue: 交易所，如 "NASDAQ", "BINANCE"
            
        Returns:
            InstrumentId: Nautilus 标的标识
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        # 默认 venue
        if venue is None:
            venue = self._infer_venue(symbol)
        
        return InstrumentId(
            symbol=Symbol(symbol),
            venue=Venue(venue),
        )
    
    def from_instrument_id(self, instrument_id: "InstrumentId") -> tuple[str, str]:
        """将 Nautilus InstrumentId 转换为本项目格式
        
        Returns:
            tuple: (symbol, venue)
        """
        return (
            str(instrument_id.symbol),
            str(instrument_id.venue),
        )
    
    def _infer_venue(self, symbol: str) -> str:
        """根据 symbol 推断 venue"""
        symbol_upper = symbol.upper()
        
        # 加密货币常见后缀
        if any(suffix in symbol_upper for suffix in ["USDT", "USD", "BTC", "ETH"]):
            return "BINANCE"
        
        # 默认股票
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
        """创建股票 Instrument（回测用）
        
        Args:
            symbol: 股票代码
            venue: 交易所
            price_precision: 价格精度（小数位）
            min_price: 最小价格（tick size）
            lot_size: 手大小
            margin_init: 初始保证金率
            margin_maint: 维持保证金率
            maker_fee: Maker 手续费率
            taker_fee: Taker 手续费率
            
        Returns:
            Equity: Nautilus Equity 对象
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        from nautilus_trader.model.objects import Price, Quantity
        
        instrument_id = self.to_instrument_id(symbol, venue)
        
        # 默认值
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
        
        # 缓存
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
        """创建加密货币永续合约 Instrument（回测用）
        
        Args:
            symbol: 交易对代码，如 "BTCUSDT"
            venue: 交易所
            base_currency: 基础货币
            quote_currency: 计价货币
            price_precision: 价格精度
            size_precision: 数量精度
            min_price: 最小价格
            max_price: 最大价格
            min_size: 最小数量
            max_size: 最大数量
            margin_init: 初始保证金率
            margin_maint: 维持保证金率
            maker_fee: Maker 手续费率
            taker_fee: Taker 手续费率
            
        Returns:
            CryptoPerpetual: Nautilus CryptoPerpetual 对象
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        from nautilus_trader.model.objects import Price, Quantity, Money
        from nautilus_trader.model.currencies import Currency
        
        instrument_id = self.to_instrument_id(symbol, venue)
        
        # 默认值
        if min_price is None:
            min_price = Decimal("0.01")
        if max_price is None:
            max_price = Decimal("10000000")
        if min_size is None:
            min_size = Decimal("0.000001")
        if max_size is None:
            max_size = Decimal("10000")
        
        # 创建货币对象
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
        
        # 缓存
        self._cache[symbol] = crypto
        
        return crypto
    
    def get_cached(self, symbol: str) -> Optional["Instrument"]:
        """获取缓存的 Instrument"""
        return self._cache.get(symbol)
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
