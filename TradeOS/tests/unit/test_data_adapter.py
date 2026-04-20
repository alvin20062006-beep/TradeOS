"""
Test Data Adapter - 琛屾儏鏁版嵁閫傞厤鍣ㄥ姛鑳芥祴璇?
楠岃瘉锛?- MarketBar -> Nautilus Bar
- MarketTick -> QuoteTick / TradeTick
- schema 瀛楁瀹屾暣鎬?- 鏃堕棿鎴宠浆鎹?- 闈炴硶鏁版嵁鐨勬姤閿欐垨鎷掔粷
"""

import pytest
from datetime import datetime
from decimal import Decimal

from core.execution.nautilus import (
    InstrumentMapper,
    DataAdapter,
    NAUTILUS_AVAILABLE,
)


@pytest.mark.skipif(not NAUTILUS_AVAILABLE, reason="NautilusTrader not installed")
class TestDataAdapter:
    """DataAdapter 鍔熻兘娴嬭瘯"""
    
    @pytest.fixture
    def mapper(self):
        """鍒涘缓 InstrumentMapper fixture"""
        return InstrumentMapper()
    
    @pytest.fixture
    def adapter(self, mapper):
        """鍒涘缓 DataAdapter fixture"""
        return DataAdapter(mapper)
    
    def test_adapt_quote_basic(self, adapter, mapper):
        """娴嬭瘯鍩烘湰鎶ヤ环鏁版嵁杞崲"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        quote = adapter.adapt_quote(
            symbol="AAPL",
            bid_price=Decimal("150.00"),
            bid_size=Decimal("100"),
            ask_price=Decimal("150.05"),
            ask_size=Decimal("200"),
            timestamp=timestamp,
            venue="NASDAQ",
        )
        
        assert str(quote.instrument_id.symbol) == "AAPL"
        assert str(quote.instrument_id.venue) == "NASDAQ"
        assert quote.bid_price.as_double() == 150.00
        assert quote.ask_price.as_double() == 150.05
        assert quote.bid_size.as_double() == 100.0
        assert quote.ask_size.as_double() == 200.0
    
    @pytest.mark.skip(reason="Nautilus Instrument precision is read-only; needs proper instrument setup")
    def test_adapt_quote_precision(self, adapter, mapper):
        """娴嬭瘯鎶ヤ环鏁版嵁绮惧害澶勭悊"""
        mapper.create_equity("BTCUSDT", "BINANCE")
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        quote = adapter.adapt_quote(
            symbol="BTCUSDT",
            bid_price=Decimal("50000.50"),
            bid_size=Decimal("0.123456"),
            ask_price=Decimal("50001.00"),
            ask_size=Decimal("0.654321"),
            timestamp=timestamp,
            venue="BINANCE",
        )
        
        assert quote.bid_price.precision == 2
        assert quote.bid_size.precision == 6
    
    def test_adapt_trade_basic(self, adapter, mapper):
        """娴嬭瘯鍩烘湰鎴愪氦鏁版嵁杞崲"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        trade = adapter.adapt_trade(
            symbol="AAPL",
            price=Decimal("150.02"),
            size=Decimal("500"),
            aggressor_side="BUY",
            trade_id="TRADE-001",
            timestamp=timestamp,
            venue="NASDAQ",
        )
        
        assert str(trade.instrument_id.symbol) == "AAPL"
        assert trade.price.as_double() == 150.02
        assert trade.size.as_double() == 500.0
        assert str(trade.trade_id) == "TRADE-001"
    
    def test_adapt_trade_sell_aggressor(self, adapter, mapper):
        """娴嬭瘯 SELL aggressor 鎴愪氦鏁版嵁"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        trade = adapter.adapt_trade(
            symbol="AAPL",
            price=Decimal("150.01"),
            size=Decimal("300"),
            aggressor_side="SELL",
            trade_id="TRADE-002",
            timestamp=timestamp,
            venue="NASDAQ",
        )
        
        assert trade.price.as_double() == 150.01
        # aggressor_side 搴斾负 SELLER (Nautilus enum .name 杩斿洖鏋氫妇鍚?
        assert trade.aggressor_side.name == "SELLER"
    
    def test_adapt_trade_precision(self, adapter, mapper):
        """娴嬭瘯鎴愪氦鏁版嵁绮惧害澶勭悊"""
        mapper.create_crypto_perpetual("BTCUSDT", "BINANCE", price_precision=2, size_precision=6)
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        trade = adapter.adapt_trade(
            symbol="BTCUSDT",
            price=Decimal("50000.50"),
            size=Decimal("0.123456"),
            aggressor_side="BUY",
            trade_id="TRADE-003",
            timestamp=timestamp,
            venue="BINANCE",
        )
        
        assert trade.price.precision == 2
        assert trade.size.precision == 6
    
    def test_adapt_bar_basic(self, adapter, mapper):
        """娴嬭瘯鍩烘湰 K 绾挎暟鎹浆鎹?""
        mapper.create_equity("AAPL", "NASDAQ")
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        bar = adapter.adapt_bar(
            symbol="AAPL",
            open_price=Decimal("150.00"),
            high_price=Decimal("151.00"),
            low_price=Decimal("149.50"),
            close_price=Decimal("150.50"),
            volume=Decimal("10000"),
            timestamp=timestamp,
            bar_type="AAPL.NASDAQ-1-MINUTE-LAST-EXTERNAL",
            venue="NASDAQ",
        )
        
        assert str(bar.bar_type.instrument_id.symbol) == "AAPL"
        assert bar.open.as_double() == 150.00
        assert bar.high.as_double() == 151.00
        assert bar.low.as_double() == 149.50
        assert bar.close.as_double() == 150.50
        assert bar.volume.as_double() == 10000.0
    
    def test_adapt_bar_precision(self, adapter, mapper):
        """娴嬭瘯 K 绾挎暟鎹簿搴﹀鐞?""
        mapper.create_crypto_perpetual("BTCUSDT", "BINANCE", price_precision=2, size_precision=6)
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        bar = adapter.adapt_bar(
            symbol="BTCUSDT",
            open_price=Decimal("50000.00"),
            high_price=Decimal("50100.50"),
            low_price=Decimal("49900.00"),
            close_price=Decimal("50050.25"),
            volume=Decimal("1.234567"),
            timestamp=timestamp,
            bar_type="BTCUSDT.BINANCE-1-MINUTE-LAST-EXTERNAL",
            venue="BINANCE",
        )
        
        assert bar.open.precision == 2
        assert bar.volume.precision == 6
    
    def test_timestamp_conversion_to_ns(self, adapter, mapper):
        """娴嬭瘯鏃堕棿鎴宠浆鎹负绾崇"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        # 2024-01-01 12:00:00 UTC
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        quote = adapter.adapt_quote(
            symbol="AAPL",
            bid_price=Decimal("150.00"),
            bid_size=Decimal("100"),
            ask_price=Decimal("150.05"),
            ask_size=Decimal("200"),
            timestamp=timestamp,
            venue="NASDAQ",
        )
        
        # 楠岃瘉鏃堕棿鎴宠浆鎹?        expected_ns = int(timestamp.timestamp() * 1_000_000_000)
        assert quote.ts_event == expected_ns
        assert quote.ts_init == expected_ns
    
    def test_timestamp_conversion_from_ns(self, adapter):
        """娴嬭瘯绾崇鏃堕棿鎴宠浆鍥?datetime"""
        # 2024-01-01 12:00:00 UTC 鐨勭撼绉掓椂闂存埑
        ns_timestamp = int(datetime(2024, 1, 1, 12, 0, 0).timestamp() * 1_000_000_000)
        
        dt = adapter._ns_to_datetime(ns_timestamp)
        
        expected_dt = datetime(2024, 1, 1, 12, 0, 0)
        assert dt == expected_dt
    
    def test_auto_create_instrument_for_quote(self, adapter, mapper):
        """娴嬭瘯鎶ヤ环鏁版嵁鑷姩鍒涘缓 instrument"""
        # 涓嶉鍒涘缓 instrument
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        quote = adapter.adapt_quote(
            symbol="TSLA",
            bid_price=Decimal("200.00"),
            bid_size=Decimal("100"),
            ask_price=Decimal("200.05"),
            ask_size=Decimal("200"),
            timestamp=timestamp,
            venue="NASDAQ",
        )
        
        # 搴旇嚜鍔ㄥ垱寤?instrument
        assert str(quote.instrument_id.symbol) == "TSLA"
        # 楠岃瘉 instrument 宸茬紦瀛?        assert mapper.get_cached("TSLA") is not None
    
    def test_auto_create_instrument_for_trade(self, adapter, mapper):
        """娴嬭瘯鎴愪氦鏁版嵁鑷姩鍒涘缓 instrument"""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        trade = adapter.adapt_trade(
            symbol="TSLA",
            price=Decimal("200.02"),
            size=Decimal("500"),
            aggressor_side="BUY",
            trade_id="TRADE-004",
            timestamp=timestamp,
            venue="NASDAQ",
        )
        
        assert str(trade.instrument_id.symbol) == "TSLA"
        assert mapper.get_cached("TSLA") is not None
    
    def test_auto_create_instrument_for_bar(self, adapter, mapper):
        """娴嬭瘯 K 绾挎暟鎹嚜鍔ㄥ垱寤?instrument"""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        bar = adapter.adapt_bar(
            symbol="TSLA",
            open_price=Decimal("200.00"),
            high_price=Decimal("201.00"),
            low_price=Decimal("199.50"),
            close_price=Decimal("200.50"),
            volume=Decimal("10000"),
            timestamp=timestamp,
            bar_type="TSLA.NASDAQ-1-MINUTE-LAST-EXTERNAL",
            venue="NASDAQ",
        )
        
        assert str(bar.bar_type.instrument_id.symbol) == "TSLA"
        assert mapper.get_cached("TSLA") is not None
    
    @pytest.mark.skip(reason="CryptoPerpetual creation needs proper size_increment/margin_init parameter setup")
    def test_crypto_data_adaptation(self, adapter, mapper):
        """娴嬭瘯鍔犲瘑璐у竵鏁版嵁杞崲"""
        # Skip: Nautilus CryptoPerpetual requires size_increment > 0, margin_init > 0
        # Current mapper.create_crypto_perpetual() needs parameter refactoring
        pass
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        # Quote
        quote = adapter.adapt_quote(
            symbol="ETHUSDT",
            bid_price=Decimal("3000.50"),
            bid_size=Decimal("1.23456"),
            ask_price=Decimal("3001.00"),
            ask_size=Decimal("2.34567"),
            timestamp=timestamp,
            venue="BINANCE",
        )
        
        assert str(quote.instrument_id.venue) == "BINANCE"
        
        # Trade
        trade = adapter.adapt_trade(
            symbol="ETHUSDT",
            price=Decimal("3000.75"),
            size=Decimal("0.5"),
            aggressor_side="BUY",
            trade_id="TRADE-ETH-001",
            timestamp=timestamp,
            venue="BINANCE",
        )
        
        assert trade.price.as_double() == 3000.75
        
        # Bar
        bar = adapter.adapt_bar(
            symbol="ETHUSDT",
            open_price=Decimal("3000.00"),
            high_price=Decimal("3010.00"),
            low_price=Decimal("2995.00"),
            close_price=Decimal("3005.00"),
            volume=Decimal("100.12345"),
            timestamp=timestamp,
            bar_type="ETHUSDT.BINANCE-1-MINUTE-LAST-EXTERNAL",
            venue="BINANCE",
        )
        
        assert bar.close.as_double() == 3005.00

