"""
Test Instrument Mapper - ????????????????????
???????- symbol -> InstrumentId ?????
- ?????venue ?????????
- ?????symbol / ?????venue ???????????- Equity/CryptoPerpetual ?????
"""

import pytest
from decimal import Decimal

from core.execution.nautilus import (
    InstrumentMapper,
    NAUTILUS_AVAILABLE,
)


@pytest.mark.skipif(not NAUTILUS_AVAILABLE, reason="NautilusTrader not installed")
class TestInstrumentMapper:
    """InstrumentMapper ?????????"""
    
    @pytest.fixture
    def mapper(self):
        """?????InstrumentMapper fixture"""
        return InstrumentMapper()
    
    def test_symbol_to_instrument_id_basic(self, mapper):
        """????????? symbol -> InstrumentId ?????"""
        instrument_id = mapper.to_instrument_id("AAPL", "NASDAQ")
        
        assert str(instrument_id.symbol) == "AAPL"
        assert str(instrument_id.venue) == "NASDAQ"
    
    def test_symbol_to_instrument_id_crypto(self, mapper):
        """????????????? symbol ?????"""
        instrument_id = mapper.to_instrument_id("BTCUSDT", "BINANCE")
        
        assert str(instrument_id.symbol) == "BTCUSDT"
        assert str(instrument_id.venue) == "BINANCE"
    
    def test_infer_venue_for_crypto(self, mapper):
        """????????????? venue ?????????"""
        # USDT ?????????????? BINANCE
        instrument_id = mapper.to_instrument_id("BTCUSDT")
        assert str(instrument_id.venue) == "BINANCE"
        
        instrument_id = mapper.to_instrument_id("ETHUSDT")
        assert str(instrument_id.venue) == "BINANCE"
    
    def test_infer_venue_for_stock(self, mapper):
        """????????? venue ?????????"""
        # ???????????????????????NASDAQ
        instrument_id = mapper.to_instrument_id("AAPL")
        assert str(instrument_id.venue) == "NASDAQ"
        
        instrument_id = mapper.to_instrument_id("TSLA")
        assert str(instrument_id.venue) == "NASDAQ"
    
    def test_from_instrument_id(self, mapper):
        """?????InstrumentId -> symbol/venue ?????"""
        instrument_id = mapper.to_instrument_id("MSFT", "NYSE")
        symbol, venue = mapper.from_instrument_id(instrument_id)
        
        assert symbol == "MSFT"
        assert venue == "NYSE"
    
    def test_create_equity_basic(self, mapper):
        """????????? Equity ?????????"""
        equity = mapper.create_equity("AAPL", "NASDAQ")
        
        assert str(equity.id.symbol) == "AAPL"
        assert str(equity.id.venue) == "NASDAQ"
        assert equity.price_precision == 2
    
    def test_create_equity_with_custom_params(self, mapper):
        """????????? Equity ???????????"""
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
        """????????? CryptoPerpetual ?????????"""
        crypto = mapper.create_crypto_perpetual("BTCUSDT", "BINANCE")
        
        assert str(crypto.id.symbol) == "BTCUSDT"
        assert str(crypto.id.venue) == "BINANCE"
        assert crypto.price_precision == 2
        assert crypto.size_precision == 6
    
    def test_create_crypto_perpetual_with_margin(self, mapper):
        """????????? CryptoPerpetual ???????????"""
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
        """?????instrument ?????????"""
        # ?????equity
        equity1 = mapper.create_equity("AAPL", "NASDAQ")
        
        cached = mapper.get_cached("AAPL")
        assert cached is equity1
        
        # ?????crypto
        crypto = mapper.create_crypto_perpetual("BTCUSDT", "BINANCE")
        cached_crypto = mapper.get_cached("BTCUSDT")
        assert cached_crypto is crypto
    
    def test_clear_cache(self, mapper):
        """??????????????"""
        mapper.create_equity("AAPL", "NASDAQ")
        assert mapper.get_cached("AAPL") is not None
        
        mapper.clear_cache()
        assert mapper.get_cached("AAPL") is None
    
    def test_different_symbols_same_mapper(self, mapper):
        """????????? mapper ????????? symbol"""
        aapl = mapper.create_equity("AAPL", "NASDAQ")
        tsla = mapper.create_equity("TSLA", "NASDAQ")
        btc = mapper.create_crypto_perpetual("BTCUSDT", "BINANCE")
        
        assert mapper.get_cached("AAPL") is aapl
        assert mapper.get_cached("TSLA") is tsla
        assert mapper.get_cached("BTCUSDT") is btc


class TestInstrumentMapperWithoutNautilus:
    """Nautilus ????????????????"""
    
    def test_nautilus_not_available(self):
        """?????NAUTILUS_AVAILABLE ?????"""
        # ???????????Nautilus ??????????????????
        if not NAUTILUS_AVAILABLE:
            assert NAUTILUS_AVAILABLE is False
        else:
            pytest.skip("Nautilus is installed")
    
    def test_runtime_error_when_nautilus_missing(self):
        """?????Nautilus ???????????RuntimeError"""
        if NAUTILUS_AVAILABLE:
            pytest.skip("Nautilus is installed")
        
        mapper = InstrumentMapper()
        
        with pytest.raises(RuntimeError, match="NautilusTrader not available"):
            mapper.to_instrument_id("AAPL", "NASDAQ")

