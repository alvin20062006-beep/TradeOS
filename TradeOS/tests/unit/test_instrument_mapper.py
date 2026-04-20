"""
Test Instrument Mapper - 鏍囩殑鏄犲皠鍣ㄥ姛鑳芥祴璇?
楠岃瘉锛?- symbol -> InstrumentId 鏄犲皠
- 涓嶅悓 venue 鏄犲皠閫昏緫
- 闈炴硶 symbol / 缂哄け venue 鐨勯敊璇鐞?- Equity/CryptoPerpetual 鍒涘缓
"""

import pytest
from decimal import Decimal

from core.execution.nautilus import (
    InstrumentMapper,
    NAUTILUS_AVAILABLE,
)


@pytest.mark.skipif(not NAUTILUS_AVAILABLE, reason="NautilusTrader not installed")
class TestInstrumentMapper:
    """InstrumentMapper 鍔熻兘娴嬭瘯"""
    
    @pytest.fixture
    def mapper(self):
        """鍒涘缓 InstrumentMapper fixture"""
        return InstrumentMapper()
    
    def test_symbol_to_instrument_id_basic(self, mapper):
        """娴嬭瘯鍩烘湰 symbol -> InstrumentId 鏄犲皠"""
        instrument_id = mapper.to_instrument_id("AAPL", "NASDAQ")
        
        assert str(instrument_id.symbol) == "AAPL"
        assert str(instrument_id.venue) == "NASDAQ"
    
    def test_symbol_to_instrument_id_crypto(self, mapper):
        """娴嬭瘯鍔犲瘑璐у竵 symbol 鏄犲皠"""
        instrument_id = mapper.to_instrument_id("BTCUSDT", "BINANCE")
        
        assert str(instrument_id.symbol) == "BTCUSDT"
        assert str(instrument_id.venue) == "BINANCE"
    
    def test_infer_venue_for_crypto(self, mapper):
        """娴嬭瘯鍔犲瘑璐у竵 venue 鑷姩鎺ㄦ柇"""
        # USDT 鍚庣紑搴旀帹鏂负 BINANCE
        instrument_id = mapper.to_instrument_id("BTCUSDT")
        assert str(instrument_id.venue) == "BINANCE"
        
        instrument_id = mapper.to_instrument_id("ETHUSDT")
        assert str(instrument_id.venue) == "BINANCE"
    
    def test_infer_venue_for_stock(self, mapper):
        """娴嬭瘯鑲＄エ venue 鑷姩鎺ㄦ柇"""
        # 鏅€氳偂绁ㄤ唬鐮佸簲鎺ㄦ柇涓?NASDAQ
        instrument_id = mapper.to_instrument_id("AAPL")
        assert str(instrument_id.venue) == "NASDAQ"
        
        instrument_id = mapper.to_instrument_id("TSLA")
        assert str(instrument_id.venue) == "NASDAQ"
    
    def test_from_instrument_id(self, mapper):
        """娴嬭瘯 InstrumentId -> symbol/venue 杞崲"""
        instrument_id = mapper.to_instrument_id("MSFT", "NYSE")
        symbol, venue = mapper.from_instrument_id(instrument_id)
        
        assert symbol == "MSFT"
        assert venue == "NYSE"
    
    def test_create_equity_basic(self, mapper):
        """娴嬭瘯鍒涘缓 Equity 鍩烘湰鍔熻兘"""
        equity = mapper.create_equity("AAPL", "NASDAQ")
        
        assert str(equity.id.symbol) == "AAPL"
        assert str(equity.id.venue) == "NASDAQ"
        assert equity.price_precision == 2
    
    def test_create_equity_with_custom_params(self, mapper):
        """娴嬭瘯鍒涘缓 Equity 鑷畾涔夊弬鏁?""
        equity = mapper.create_equity(
            symbol="TSLA",
            venue="NASDAQ",
            price_precision=4,
            min_price=Decimal("0.0001"),
            lot_size=Decimal("10"),
            margin_init=Decimal("0.5"),
            margin_maint=Decimal("0.25"),
            maker_fee=Decimal("0.0001"),
            taker_fee=Decimal("0.0005"),
        )
        
        assert equity.price_precision == 4
        assert equity.margin_init == Decimal("0.5")
        assert equity.taker_fee == Decimal("0.0005")
    
    def test_create_crypto_perpetual_basic(self, mapper):
        """娴嬭瘯鍒涘缓 CryptoPerpetual 鍩烘湰鍔熻兘"""
        crypto = mapper.create_crypto_perpetual("BTCUSDT", "BINANCE")
        
        assert str(crypto.id.symbol) == "BTCUSDT"
        assert str(crypto.id.venue) == "BINANCE"
        assert crypto.price_precision == 2
        assert crypto.size_precision == 6
    
    def test_create_crypto_perpetual_with_margin(self, mapper):
        """娴嬭瘯鍒涘缓 CryptoPerpetual 淇濊瘉閲戝弬鏁?""
        crypto = mapper.create_crypto_perpetual(
            symbol="ETHUSDT",
            venue="BINANCE",
            base_currency="ETH",
            quote_currency="USDT",
            margin_init=Decimal("0.1"),
            margin_maint=Decimal("0.05"),
            maker_fee=Decimal("0.0002"),
            taker_fee=Decimal("0.0005"),
        )
        
        assert crypto.margin_init == Decimal("0.1")
        assert crypto.margin_maint == Decimal("0.05")
        assert crypto.maker_fee == Decimal("0.0002")
    
    def test_cache_mechanism(self, mapper):
        """娴嬭瘯 instrument 缂撳瓨鏈哄埗"""
        # 鍒涘缓 equity
        equity1 = mapper.create_equity("AAPL", "NASDAQ")
        
        # 浠庣紦瀛樿幏鍙?        cached = mapper.get_cached("AAPL")
        assert cached is equity1
        
        # 鍒涘缓 crypto
        crypto = mapper.create_crypto_perpetual("BTCUSDT", "BINANCE")
        cached_crypto = mapper.get_cached("BTCUSDT")
        assert cached_crypto is crypto
    
    def test_clear_cache(self, mapper):
        """娴嬭瘯娓呯┖缂撳瓨"""
        mapper.create_equity("AAPL", "NASDAQ")
        assert mapper.get_cached("AAPL") is not None
        
        mapper.clear_cache()
        assert mapper.get_cached("AAPL") is None
    
    def test_different_symbols_same_mapper(self, mapper):
        """娴嬭瘯鍚屼竴 mapper 澶勭悊澶氫釜 symbol"""
        aapl = mapper.create_equity("AAPL", "NASDAQ")
        tsla = mapper.create_equity("TSLA", "NASDAQ")
        btc = mapper.create_crypto_perpetual("BTCUSDT", "BINANCE")
        
        assert mapper.get_cached("AAPL") is aapl
        assert mapper.get_cached("TSLA") is tsla
        assert mapper.get_cached("BTCUSDT") is btc


class TestInstrumentMapperWithoutNautilus:
    """Nautilus 鏈畨瑁呮椂鐨勬祴璇?""
    
    def test_nautilus_not_available(self):
        """娴嬭瘯 NAUTILUS_AVAILABLE 鏍囧織"""
        # 杩欎釜娴嬭瘯鍦?Nautilus 鏈畨瑁呮椂搴旇閫氳繃
        if not NAUTILUS_AVAILABLE:
            assert NAUTILUS_AVAILABLE is False
        else:
            pytest.skip("Nautilus is installed")
    
    def test_runtime_error_when_nautilus_missing(self):
        """娴嬭瘯 Nautilus 缂哄け鏃舵姏鍑?RuntimeError"""
        if NAUTILUS_AVAILABLE:
            pytest.skip("Nautilus is installed")
        
        mapper = InstrumentMapper()
        
        with pytest.raises(RuntimeError, match="NautilusTrader not available"):
            mapper.to_instrument_id("AAPL", "NASDAQ")

