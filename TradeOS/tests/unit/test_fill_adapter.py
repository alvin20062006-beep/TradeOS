"""
Test Fill Adapter - 鎴愪氦閫傞厤鍣ㄥ姛鑳芥祴璇?

楠岃瘉锛?
- OrderFilled -> FillRecord 鏄犲皠
- filled_qty / fill_price / fees / trade_id / liquidity_side / timestamps 鏄犲皠
- 缂哄け瀛楁鏃剁殑澶勭悊閫昏緫

API 鐗堟湰: NautilusTrader 1.225.0
鏇存柊鏃堕棿: 2026-04-07
"""

import pytest
from datetime import datetime
from decimal import Decimal

from core.execution.nautilus import (
    InstrumentMapper,
    FillAdapter,
    NAUTILUS_AVAILABLE,
)


@pytest.mark.skipif(not NAUTILUS_AVAILABLE, reason="NautilusTrader not installed")
class TestFillAdapter:
    """FillAdapter 鍔熻兘娴嬭瘯"""
    
    @pytest.fixture
    def mapper(self):
        """鍒涘缓 InstrumentMapper fixture"""
        return InstrumentMapper()
    
    @pytest.fixture
    def adapter(self, mapper):
        """鍒涘缓 FillAdapter fixture"""
        return FillAdapter(mapper)
    
    @pytest.fixture
    def usd_currency(self):
        """鍒涘缓 USD 璐у竵 fixture"""
        from nautilus_trader.model.objects import Currency
        from nautilus_trader.model.enums import CurrencyType
        return Currency('USD', 2, 840, 'US Dollar', CurrencyType.FIAT)
    
    def _create_order_filled(self, mapper, side, qty, price, commission=None, 
                             liquidity_side=None, symbol='AAPL', venue='NASDAQ',
                             usd_currency=None):
        """杈呭姪鏂规硶锛氬垱寤?OrderFilled 浜嬩欢"""
        from nautilus_trader.model.events import OrderFilled
        from nautilus_trader.model.identifiers import (
            ClientOrderId, InstrumentId, Symbol, Venue,
            TradeId, StrategyId, TraderId, VenueOrderId, AccountId
        )
        from nautilus_trader.model.enums import OrderSide, OrderType, LiquiditySide
        from nautilus_trader.model.objects import Quantity, Price, Money
        from nautilus_trader.core.uuid import UUID4
        
        if usd_currency is None:
            from nautilus_trader.model.objects import Currency
            from nautilus_trader.model.enums import CurrencyType
            usd_currency = Currency('USD', 2, 840, 'US Dollar', CurrencyType.FIAT)
        
        instrument_id = mapper.to_instrument_id(symbol, venue)
        
        # 绠€鍖栵細浣跨敤鍥哄畾鏃堕棿鎴?
        ts = 1704000000000000000
        
        # 杞崲 commission锛圢one 闇€瑕佷紶 Money(0) 鑰岄潪 Python None锛?
        nautilus_commission = Money(0, usd_currency) if commission is None else Money(float(commission), usd_currency)
        
        # 杞崲 liquidity_side锛圢one 闇€瑕佷紶 NO_LIQUIDITY_SIDE 鑰岄潪 Python None锛?
        nautilus_ls = LiquiditySide.NO_LIQUIDITY_SIDE
        if liquidity_side is not None:
            if liquidity_side.upper() == 'TAKER':
                nautilus_ls = LiquiditySide.TAKER
            elif liquidity_side.upper() == 'MAKER':
                nautilus_ls = LiquiditySide.MAKER
        
        return OrderFilled(
            trader_id=TraderId('TEST-TRADER'),
            strategy_id=StrategyId('TEST-001'),
            instrument_id=instrument_id,
            client_order_id=ClientOrderId('ORDER-123'),
            venue_order_id=VenueOrderId('VENUE-123'),
            account_id=AccountId('ACC-001'),
            trade_id=TradeId('TRADE-456'),
            position_id=None,
            order_side=OrderSide.BUY if side == 'BUY' else OrderSide.SELL,
            order_type=OrderType.MARKET.value,  # 浣跨敤鏁存暟鍊?
            last_qty=Quantity(int(qty), 0),
            last_px=Price(float(price), 2),
            currency=usd_currency,
            commission=nautilus_commission,
            liquidity_side=nautilus_ls,
            event_id=UUID4(),
            ts_event=ts,
            ts_init=ts,
        )
    
    def test_adapt_basic_fill(self, adapter, mapper, usd_currency):
        """娴嬭瘯鍩烘湰鎴愪氦鏄犲皠"""
        # 鍒涘缓 instrument
        mapper.create_equity("AAPL", "NASDAQ")
        
        # 鍒涘缓 OrderFilled 浜嬩欢
        event = self._create_order_filled(
            mapper=mapper,
            side='BUY',
            qty=100,
            price=150.50,
            commission=1.50,
            liquidity_side='TAKER',
            usd_currency=usd_currency,
        )
        
        fill = adapter.adapt(event, intent_id="INTENT-789")
        
        assert fill.order_id == "ORDER-123"
        assert fill.intent_id == "INTENT-789"
        assert fill.symbol == "AAPL"
        assert fill.side.value == "BUY"
        assert fill.filled_qty == Decimal("100")
        assert fill.fill_price == Decimal("150.50")
        assert fill.fees == Decimal("1.50")
        assert fill.venue == "NASDAQ"
        assert fill.trade_id == "TRADE-456"
        assert fill.liquidity_side.value == "TAKER"
    
    def test_adapt_sell_fill(self, adapter, mapper, usd_currency):
        """娴嬭瘯 SELL 鏂瑰悜鎴愪氦鏄犲皠"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        from nautilus_trader.model.enums import LiquiditySide
        
        event = self._create_order_filled(
            mapper=mapper,
            side='SELL',
            qty=50,
            price=151.00,
            commission=0.75,
            liquidity_side='MAKER',
            usd_currency=usd_currency,
        )
        
        fill = adapter.adapt(event, intent_id="INTENT-790")
        
        assert fill.side.value == "SELL"
        assert fill.filled_qty == Decimal("50")
        assert fill.fill_price == Decimal("151.00")
        assert fill.liquidity_side.value == "MAKER"
    
    def test_timestamp_conversion(self, adapter, mapper, usd_currency):
        """娴嬭瘯鏃堕棿鎴宠浆鎹?""
        mapper.create_equity("AAPL", "NASDAQ")
        
        # 2024-01-01 00:00:00 UTC 鐨勭撼绉掓椂闂存埑
        ns_timestamp = 1_704_067_200_000_000_000
        
        from nautilus_trader.model.events import OrderFilled
        from nautilus_trader.model.identifiers import (
            ClientOrderId, InstrumentId, Symbol, Venue,
            TradeId, StrategyId, TraderId, VenueOrderId, AccountId
        )
        from nautilus_trader.model.enums import OrderSide, OrderType, LiquiditySide
        from nautilus_trader.model.objects import Quantity, Price, Money
        from nautilus_trader.core.uuid import UUID4
        
        instrument_id = mapper.to_instrument_id("AAPL", "NASDAQ")
        
        event = OrderFilled(
            trader_id=TraderId('TEST-TRADER'),
            strategy_id=StrategyId('TEST-001'),
            instrument_id=instrument_id,
            client_order_id=ClientOrderId('ORDER-126'),
            venue_order_id=VenueOrderId('VENUE-126'),
            account_id=AccountId('ACC-001'),
            trade_id=TradeId('TRADE-459'),
            position_id=None,
            order_side=OrderSide.BUY,
            order_type=OrderType.MARKET.value,  # 浣跨敤鏁存暟鍊?
            last_qty=Quantity(100, 0),
            last_px=Price(150.00, 2),
            currency=usd_currency,
            commission=Money(0, usd_currency),
            liquidity_side=LiquiditySide.NO_LIQUIDITY_SIDE,
            event_id=UUID4(),
            ts_event=ns_timestamp,
            ts_init=ns_timestamp,
        )
        
        fill = adapter.adapt(event, intent_id="INTENT-792")
        
        # 楠岃瘉鏃堕棿鎴宠浆鎹?
        expected_dt = datetime.fromtimestamp(1_704_067_200)
        assert fill.filled_at == expected_dt
    
    def test_missing_commission(self, adapter, mapper, usd_currency):
        """娴嬭瘯缂哄け commission 鏃剁殑澶勭悊"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        event = self._create_order_filled(
            mapper=mapper,
            side='BUY',
            qty=100,
            price=150.00,
            commission=None,
            liquidity_side=None,
            usd_currency=usd_currency,
        )
        
        fill = adapter.adapt(event, intent_id="INTENT-793")
        
        # 缂哄け commission 鏃跺簲涓?0
        assert fill.fees == Decimal("0")
    
    def test_missing_liquidity_side(self, adapter, mapper, usd_currency):
        """娴嬭瘯缂哄け liquidity_side 鏃剁殑澶勭悊"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        event = self._create_order_filled(
            mapper=mapper,
            side='BUY',
            qty=100,
            price=150.00,
            commission=None,
            liquidity_side=None,
            usd_currency=usd_currency,
        )
        
        fill = adapter.adapt(event, intent_id="INTENT-794")
        
        # 缂哄け liquidity_side 鏃跺簲涓?None
        assert fill.liquidity_side is None
    
    def test_adapt_many(self, adapter, mapper, usd_currency):
        """娴嬭瘯鎵归噺杞崲"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        events = []
        for i in range(3):
            from nautilus_trader.model.events import OrderFilled
            from nautilus_trader.model.identifiers import (
                ClientOrderId, InstrumentId, Symbol, Venue,
                TradeId, StrategyId, TraderId, VenueOrderId, AccountId
            )
            from nautilus_trader.model.enums import OrderSide, OrderType, LiquiditySide
            from nautilus_trader.model.objects import Quantity, Price, Money
            from nautilus_trader.core.uuid import UUID4
            
            instrument_id = mapper.to_instrument_id("AAPL", "NASDAQ")
            ts = 1704000000000000000
            
            event = OrderFilled(
                trader_id=TraderId('TEST-TRADER'),
                strategy_id=StrategyId('TEST-001'),
                instrument_id=instrument_id,
                client_order_id=ClientOrderId(f'ORDER-{i}'),
                venue_order_id=VenueOrderId(f'VENUE-{i}'),
                account_id=AccountId('ACC-001'),
                trade_id=TradeId(f'TRADE-{i}'),
                position_id=None,
                order_side=OrderSide.BUY,
                order_type=OrderType.MARKET.value,
                last_qty=Quantity(100, 0),
                last_px=Price(150.00, 2),
                currency=usd_currency,
                commission=Money(0, usd_currency),
                liquidity_side=LiquiditySide.NO_LIQUIDITY_SIDE,
                event_id=UUID4(),
                ts_event=ts,
                ts_init=ts,
            )
            events.append(event)
        
        fills = adapter.adapt_many(events, intent_id="INTENT-BATCH")
        
        assert len(fills) == 3
        for i, fill in enumerate(fills):
            assert fill.order_id == f"ORDER-{i}"
            assert fill.intent_id == "INTENT-BATCH"

