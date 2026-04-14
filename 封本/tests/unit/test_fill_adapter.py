"""
Test Fill Adapter - 成交适配器功能测试

验证：
- OrderFilled -> FillRecord 映射
- filled_qty / fill_price / fees / trade_id / liquidity_side / timestamps 映射
- 缺失字段时的处理逻辑

API 版本: NautilusTrader 1.225.0
更新时间: 2026-04-07
"""

import pytest
from datetime import datetime
from decimal import Decimal

from ai_trading_tool.core.execution.nautilus import (
    InstrumentMapper,
    FillAdapter,
    NAUTILUS_AVAILABLE,
)


@pytest.mark.skipif(not NAUTILUS_AVAILABLE, reason="NautilusTrader not installed")
class TestFillAdapter:
    """FillAdapter 功能测试"""
    
    @pytest.fixture
    def mapper(self):
        """创建 InstrumentMapper fixture"""
        return InstrumentMapper()
    
    @pytest.fixture
    def adapter(self, mapper):
        """创建 FillAdapter fixture"""
        return FillAdapter(mapper)
    
    @pytest.fixture
    def usd_currency(self):
        """创建 USD 货币 fixture"""
        from nautilus_trader.model.objects import Currency
        from nautilus_trader.model.enums import CurrencyType
        return Currency('USD', 2, 840, 'US Dollar', CurrencyType.FIAT)
    
    def _create_order_filled(self, mapper, side, qty, price, commission=None, 
                             liquidity_side=None, symbol='AAPL', venue='NASDAQ',
                             usd_currency=None):
        """辅助方法：创建 OrderFilled 事件"""
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
        
        # 简化：使用固定时间戳
        ts = 1704000000000000000
        
        # 转换 commission（None 需要传 Money(0) 而非 Python None）
        nautilus_commission = Money(0, usd_currency) if commission is None else Money(float(commission), usd_currency)
        
        # 转换 liquidity_side（None 需要传 NO_LIQUIDITY_SIDE 而非 Python None）
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
            order_type=OrderType.MARKET.value,  # 使用整数值
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
        """测试基本成交映射"""
        # 创建 instrument
        mapper.create_equity("AAPL", "NASDAQ")
        
        # 创建 OrderFilled 事件
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
        """测试 SELL 方向成交映射"""
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
        """测试时间戳转换"""
        mapper.create_equity("AAPL", "NASDAQ")
        
        # 2024-01-01 00:00:00 UTC 的纳秒时间戳
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
            order_type=OrderType.MARKET.value,  # 使用整数值
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
        
        # 验证时间戳转换
        expected_dt = datetime.fromtimestamp(1_704_067_200)
        assert fill.filled_at == expected_dt
    
    def test_missing_commission(self, adapter, mapper, usd_currency):
        """测试缺失 commission 时的处理"""
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
        
        # 缺失 commission 时应为 0
        assert fill.fees == Decimal("0")
    
    def test_missing_liquidity_side(self, adapter, mapper, usd_currency):
        """测试缺失 liquidity_side 时的处理"""
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
        
        # 缺失 liquidity_side 时应为 None
        assert fill.liquidity_side is None
    
    def test_adapt_many(self, adapter, mapper, usd_currency):
        """测试批量转换"""
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
