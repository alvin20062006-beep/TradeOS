"""
Test Order Adapter - ????????????????????
???????- MARKET ?????????
- LIMIT ?????????
- STOP_MARKET ?????????
- STOP_LIMIT ?????????
- side / quantity / price / stop_price / tif ?????
- ???????intent ???????
API ????? NautilusTrader 1.225.0
?????????: 2026-04-06
"""

import pytest
from decimal import Decimal

from core.execution.enums import (
    Side,
    OrderType,
    TimeInForce,
)
from core.execution.models import ExecutionIntent
from core.execution.nautilus import (
    InstrumentMapper,
    OrderAdapter,
    NAUTILUS_AVAILABLE,
)


@pytest.mark.skipif(not NAUTILUS_AVAILABLE, reason="NautilusTrader not installed")
class TestOrderAdapter:
    """OrderAdapter ?????????"""
    
    @pytest.fixture
    def mapper(self):
        """?????InstrumentMapper fixture"""
        return InstrumentMapper()
    
    @pytest.fixture
    def adapter(self, mapper):
        """?????OrderAdapter fixture"""
        return OrderAdapter(mapper)
    
    def test_adapt_market_order_buy(self, adapter, mapper):
        """?????MARKET BUY ?????????"""
        # ???????instrument
        mapper.create_equity("AAPL", "NASDAQ")
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            venue="NASDAQ",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
        )
        
        order = adapter.adapt(intent)
        
        assert str(order.instrument_id.symbol) == "AAPL"
        assert str(order.instrument_id.venue) == "NASDAQ"
        assert order.side.name == "BUY"
        assert order.quantity.as_double() == 100.0
    
    def test_adapt_market_order_sell(self, adapter, mapper):
        """?????MARKET SELL ?????????"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            venue="NASDAQ",
            side=Side.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("50"),
        )
        
        order = adapter.adapt(intent)
        
        assert order.side.name == "SELL"
        assert order.quantity.as_double() == 50.0
    
    def test_adapt_limit_order(self, adapter, mapper):
        """?????LIMIT ?????????"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            venue="NASDAQ",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            price=Decimal("150.50"),
        )
        
        order = adapter.adapt(intent)
        
        assert order.side.name == "BUY"
        assert order.quantity.as_double() == 100.0
        assert order.price.as_double() == 150.50
    
    def test_adapt_stop_market_order(self, adapter, mapper):
        """?????STOP_MARKET ?????????"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            venue="NASDAQ",
            side=Side.SELL,
            order_type=OrderType.STOP_MARKET,
            quantity=Decimal("100"),
            stop_price=Decimal("140.00"),
        )
        
        order = adapter.adapt(intent)
        
        assert order.side.name == "SELL"
        assert order.trigger_price.as_double() == 140.00
    
    def test_adapt_stop_limit_order(self, adapter, mapper):
        """?????STOP_LIMIT ?????????"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            venue="NASDAQ",
            side=Side.BUY,
            order_type=OrderType.STOP_LIMIT,
            quantity=Decimal("100"),
            price=Decimal("145.00"),
            stop_price=Decimal("146.00"),
        )
        
        order = adapter.adapt(intent)
        
        assert order.price.as_double() == 145.00
        assert order.trigger_price.as_double() == 146.00
    
    def test_time_in_force_mapping(self, adapter, mapper):
        """?????TimeInForce ?????"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        # GTC
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            time_in_force=TimeInForce.GTC,
        )
        order = adapter.adapt(intent)
        assert order.time_in_force.name == "GTC"
        
        # IOC
        intent.time_in_force = TimeInForce.IOC
        order = adapter.adapt(intent)
        assert order.time_in_force.name == "IOC"
        
        # FOK
        intent.time_in_force = TimeInForce.FOK
        order = adapter.adapt(intent)
        assert order.time_in_force.name == "FOK"
    
    @pytest.mark.skip(reason="Nautilus Instrument precision is read-only; needs proper instrument setup")
    def test_quantity_precision(self, adapter, mapper):
        """??????????????????"""
        # ????????????????instrument
        instrument = mapper.create_equity("BTCUSDT", "BINANCE")
        instrument.size_precision = 6
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="BTCUSDT",
            venue="BINANCE",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.123456"),
        )
        
        order = adapter.adapt(intent)
        
        # ??????????????
        assert order.quantity.precision == 6
    
    @pytest.mark.skip(reason="Nautilus Instrument precision is read-only; needs proper instrument setup")
    def test_price_precision(self, adapter, mapper):
        """??????????????????"""
        instrument = mapper.create_equity("BTCUSDT", "BINANCE")
        instrument.price_precision = 2
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="BTCUSDT",
            venue="BINANCE",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1"),
            price=Decimal("50000.50"),
        )
        
        order = adapter.adapt(intent)
        
        # ??????????????
        assert order.price.precision == 2
    
    def test_limit_order_missing_price_error(self, adapter, mapper):
        """?????LIMIT ????????? price ???????????"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            # price ?????
        )
        
        with pytest.raises(ValueError, match="LIMIT order requires price"):
            adapter.adapt(intent)
    
    def test_stop_market_missing_stop_price_error(self, adapter, mapper):
        """?????STOP_MARKET ????????? stop_price ???????????"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            side=Side.SELL,
            order_type=OrderType.STOP_MARKET,
            quantity=Decimal("100"),
            # stop_price ?????
        )
        
        with pytest.raises(ValueError, match="STOP_MARKET order requires stop_price"):
            adapter.adapt(intent)
    
    def test_stop_limit_missing_prices_error(self, adapter, mapper):
        """?????STOP_LIMIT ????????? price/stop_price ???????????"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        # ?????price
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.STOP_LIMIT,
            quantity=Decimal("100"),
            stop_price=Decimal("140.00"),
            # price ?????
        )
        
        with pytest.raises(ValueError, match="STOP_LIMIT order requires both price and stop_price"):
            adapter.adapt(intent)
        
        # ?????stop_price
        intent.price = Decimal("145.00")
        intent.stop_price = None
        
        with pytest.raises(ValueError, match="STOP_LIMIT order requires both price and stop_price"):
            adapter.adapt(intent)
    
    def test_client_order_id_custom(self, adapter, mapper):
        """???????????client_order_id"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
        )
        
        order = adapter.adapt(intent, client_order_id="MY-ORDER-123")
        
        assert str(order.client_order_id) == "MY-ORDER-123"
    
    def test_client_order_id_auto_generated(self, adapter, mapper):
        """????????????????client_order_id"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
        )
        
        order = adapter.adapt(intent)
        
        # ???????????client_order_id???????intent_id ???????
        assert len(str(order.client_order_id)) > 0

