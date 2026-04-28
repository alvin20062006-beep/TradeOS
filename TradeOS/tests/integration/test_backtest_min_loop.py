"""
Test Backtest Min Loop - ????????????????????????
???????- ExecutionIntent -> Nautilus Order -> FillRecord -> ExecutionReport ?????????
- ??????????????rderAdapter / FillAdapter?????????????- ?????????????ecutionReport / FillRecord / PositionState
- Sink ?????????

API ????? NautilusTrader 1.225.0
?????????: 2026-04-07
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
from typing import Optional

from core.execution.enums import (
    Side,
    OrderType,
    TimeInForce,
    ExecutionMode,
    ExecutionStatus,
)
from core.execution.models import (
    ExecutionIntent,
    ExecutionReport,
    FillRecord,
    PositionState,
    OrderSnapshot,
)
from core.execution.sinks import ExecutionEventSink, MemoryEventSink
from core.execution.nautilus import (
    InstrumentMapper,
    OrderAdapter,
    FillAdapter,
    OrderAdapterConfig,
    NAUTILUS_AVAILABLE,
)


@pytest.mark.skipif(not NAUTILUS_AVAILABLE, reason="NautilusTrader not installed")
class TestBacktestMinLoop:
    """????????????????????"""
    
    @pytest.fixture
    def instrument_mapper(self):
        """?????InstrumentMapper"""
        return InstrumentMapper()
    
    @pytest.fixture
    def order_adapter(self, instrument_mapper):
        """?????OrderAdapter"""
        config = OrderAdapterConfig(
            trader_id="TEST-TRADER-001",
            strategy_id="TEST-STRATEGY-001",
        )
        return OrderAdapter(instrument_mapper, config)
    
    @pytest.fixture
    def fill_adapter(self, instrument_mapper):
        """?????FillAdapter"""
        return FillAdapter(instrument_mapper)
    
    @pytest.fixture
    def event_sink(self):
        """??????????????Sink"""
        return MemoryEventSink()
    
    @pytest.fixture
    def intent(self):
        """????????? ExecutionIntent"""
        return ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            venue="NASDAQ",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
            time_in_force=TimeInForce.DAY,
        )
    
    def test_instrument_mapper_equity(self, instrument_mapper):
        """??????????????????"""
        # ?????equity
        instrument = instrument_mapper.create_equity("AAPL", "NASDAQ")
        
        # ?????????
        instrument_id = instrument_mapper.to_instrument_id("AAPL", "NASDAQ")
        assert str(instrument_id.symbol) == "AAPL"
        assert str(instrument_id.venue) == "NASDAQ"
        
        # ??????????????
        symbol, venue = instrument_mapper.from_instrument_id(instrument_id)
        assert symbol == "AAPL"
        assert venue == "NASDAQ"
    
    def test_order_adapter_market_order(self, order_adapter, instrument_mapper):
        """?????MARKET ?????????"""
        # ?????instrument
        instrument_mapper.create_equity("AAPL", "NASDAQ")
        
        # ?????intent
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            venue="NASDAQ",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
        )
        
        # ?????????
        order = order_adapter.adapt(intent, client_order_id="TEST-ORDER-001")
        
        # ??????????????????
        assert order is not None
        assert str(order.client_order_id) == "TEST-ORDER-001"
        assert order.side.name == "BUY"
        assert order.quantity.as_double() == 100.0
    
    def test_order_adapter_limit_order(self, order_adapter, instrument_mapper):
        """?????LIMIT ?????????"""
        instrument_mapper.create_equity("AAPL", "NASDAQ")
        
        intent = ExecutionIntent(
            strategy_id="TEST-001",
            symbol="AAPL",
            venue="NASDAQ",
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("50"),
            price=Decimal("150.00"),
        )
        
        order = order_adapter.adapt(intent, client_order_id="TEST-ORDER-002")
        
        assert order is not None
        assert order.side.name == "SELL"
        assert order.price.as_double() == 150.00
    
    def test_fill_adapter_basic(self, fill_adapter, instrument_mapper):
        """?????FillRecord ?????"""
        from nautilus_trader.model.events import OrderFilled
        from nautilus_trader.model.identifiers import (
            ClientOrderId, TradeId, StrategyId, TraderId,
            VenueOrderId, AccountId
        )
        from nautilus_trader.model.enums import OrderSide, LiquiditySide, CurrencyType
        from nautilus_trader.model.objects import Currency, Quantity, Price, Money
        from nautilus_trader.core.uuid import UUID4
        
        # ?????instrument
        instrument_mapper.create_equity("AAPL", "NASDAQ")
        instrument_id = instrument_mapper.to_instrument_id("AAPL", "NASDAQ")
        
        # ?????USD ????
        usd = Currency('USD', 2, 840, 'US Dollar', CurrencyType.FIAT)
        
        # ?????OrderFilled ?????
        event = OrderFilled(
            trader_id=TraderId('TEST-TRADER-001'),
            strategy_id=StrategyId('TEST-STRATEGY-001'),
            instrument_id=instrument_id,
            client_order_id=ClientOrderId('TEST-ORDER-001'),
            venue_order_id=VenueOrderId('VENUE-ORDER-001'),
            account_id=AccountId('ACC-001'),
            trade_id=TradeId('TRADE-001'),
            position_id=None,
            order_side=OrderSide.BUY,
            order_type=1,  # MARKET
            last_qty=Quantity(100, 0),
            last_px=Price(150.50, 2),
            currency=usd,
            commission=Money(1.50, usd),
            liquidity_side=LiquiditySide.TAKER,
            event_id=UUID4(),
            ts_event=1704000000000000000,
            ts_init=1704000000000000000,
        )
        
        # ?????????
        fill_record = fill_adapter.adapt(event, intent_id="INTENT-001")
        
        # ?????FillRecord
        assert fill_record is not None
        assert fill_record.order_id == "TEST-ORDER-001"
        assert fill_record.intent_id == "INTENT-001"
        assert fill_record.symbol == "AAPL"
        assert fill_record.venue == "NASDAQ"
        assert fill_record.side == Side.BUY
        assert fill_record.filled_qty == Decimal("100")
        assert fill_record.fill_price == Decimal("150.50")
        assert fill_record.fees == Decimal("1.50")
    
    def test_execution_report_generation(self):
        """?????ExecutionReport ?????"""
        # ??FillRecord ?????ExecutionReport
        fill_record = FillRecord(
            order_id="TEST-ORDER-001",
            intent_id="INTENT-001",
            symbol="AAPL",
            side=Side.BUY,
            filled_qty=Decimal("100"),
            fill_price=Decimal("150.50"),
            fees=Decimal("1.50"),
            venue="NASDAQ",
            trade_id="TRADE-001",
            liquidity_side=None,
            filled_at=datetime.now(),
        )
        
        # ?????????
        report = ExecutionReport(
            intent_id=fill_record.intent_id,
            order_id=fill_record.order_id,
            status=ExecutionStatus.FILLED,
            filled_qty=fill_record.filled_qty,
            avg_fill_price=fill_record.fill_price,
            total_fees=fill_record.fees,
            venue=fill_record.venue,
        )
        
        # ?????????
        assert report.is_terminal
        assert report.is_complete
        assert report.filled_qty == Decimal("100")
        assert report.avg_fill_price == Decimal("150.50")
    
    def test_position_state_update(self):
        """?????PositionState ?????"""
        from datetime import datetime
        # ?????????
        position = PositionState(
            symbol="AAPL",
            venue="NASDAQ",
            net_qty=Decimal("0"),
            avg_cost=Decimal("0"),
        )
        
        assert position.net_qty == Decimal("0")
        
        # ?????????
        fill_record = FillRecord(
            order_id="TEST-ORDER-001",
            intent_id="INTENT-001",
            symbol="AAPL",
            side=Side.BUY,
            filled_qty=Decimal("100"),
            fill_price=Decimal("150.00"),
            fees=Decimal("1.00"),
            venue="NASDAQ",
            filled_at=datetime.now(),
        )
        
        # ?????????
        if fill_record.side == Side.BUY:
            new_qty = position.net_qty + fill_record.filled_qty
            position.net_qty = new_qty
            # ????????????????????????????            position.avg_cost = fill_record.fill_price
        else:
            new_qty = position.net_qty - fill_record.filled_qty
            position.net_qty = new_qty
        
        # ?????????
        assert position.net_qty == Decimal("100")
        assert position.avg_cost == Decimal("150.00")
    
    @pytest.mark.asyncio
    async def test_sink_record(self, event_sink):
        """?????Sink ?????"""
        # ?????????
        report = ExecutionReport(
            intent_id="INTENT-001",
            order_id="TEST-ORDER-001",
            status=ExecutionStatus.FILLED,
            filled_qty=Decimal("100"),
            avg_fill_price=Decimal("150.00"),
            total_fees=Decimal("1.00"),
            venue="NASDAQ",
        )
        
        # ?????sink??????????????
        await event_sink.write_report(report)
        
        # ?????????
        assert len(event_sink.reports) == 1
        assert event_sink.reports[0].intent_id == "INTENT-001"
    
    @pytest.mark.asyncio
    async def test_min_loop_full_chain(
        self, 
        instrument_mapper, 
        order_adapter, 
        fill_adapter,
        event_sink,
        intent,
    ):
        """???????????????????
        
        ???????        1. ?????ExecutionIntent
        2. Intent -> Nautilus Order (OrderAdapter)
        3. ?????Fill ?????
        4. Fill -> FillRecord (FillAdapter)
        5. FillRecord -> ExecutionReport
        6. PositionState ?????
        7. Sink ?????
        """
        # Step 1: ?????instrument
        instrument_mapper.create_equity(intent.symbol, intent.venue)
        
        # Step 2: Intent -> Order
        order = order_adapter.adapt(intent, client_order_id="LOOP-ORDER-001")
        assert order is not None
        
        # Step 3: ?????Fill ?????
        from nautilus_trader.model.events import OrderFilled
        from nautilus_trader.model.identifiers import (
            ClientOrderId, TradeId, StrategyId, TraderId,
            VenueOrderId, AccountId
        )
        from nautilus_trader.model.enums import OrderSide, LiquiditySide, CurrencyType
        from nautilus_trader.model.objects import Currency, Quantity, Price, Money
        from nautilus_trader.core.uuid import UUID4
        
        instrument_id = instrument_mapper.to_instrument_id(intent.symbol, intent.venue)
        usd = Currency('USD', 2, 840, 'US Dollar', CurrencyType.FIAT)
        
        # ?????Fill ?????
        fill_event = OrderFilled(
            trader_id=TraderId('TEST-TRADER-001'),
            strategy_id=StrategyId('TEST-STRATEGY-001'),
            instrument_id=instrument_id,
            client_order_id=order.client_order_id,
            venue_order_id=VenueOrderId('VENUE-LOOP-001'),
            account_id=AccountId('ACC-LOOP'),
            trade_id=TradeId('TRADE-LOOP-001'),
            position_id=None,
            order_side=OrderSide.BUY,
            order_type=1,
            last_qty=Quantity(100, 0),
            last_px=Price(150.00, 2),
            currency=usd,
            commission=Money(1.00, usd),
            liquidity_side=LiquiditySide.TAKER,
            event_id=UUID4(),
            ts_event=1704000000000000000,
            ts_init=1704000000000000000,
        )
        
        # Step 4: Fill -> FillRecord
        fill_record = fill_adapter.adapt(fill_event, intent_id=intent.intent_id)
        assert fill_record is not None
        assert fill_record.symbol == intent.symbol
        assert fill_record.filled_qty == intent.quantity
        
        # Step 5: FillRecord -> ExecutionReport
        report = ExecutionReport(
            intent_id=fill_record.intent_id,
            order_id=fill_record.order_id,
            status=ExecutionStatus.FILLED,
            filled_qty=fill_record.filled_qty,
            avg_fill_price=fill_record.fill_price,
            total_fees=fill_record.fees,
            venue=fill_record.venue,
        )
        assert report.is_terminal
        assert report.is_complete
        
        # Step 6: PositionState ?????
        position = PositionState(
            symbol=intent.symbol,
            venue=intent.venue or "NASDAQ",
            net_qty=Decimal("0"),
            avg_cost=Decimal("0"),
        )
        if fill_record.side == Side.BUY:
            position.net_qty = fill_record.filled_qty
            position.avg_cost = fill_record.fill_price
        else:
            position.net_qty = -fill_record.filled_qty
        
        assert position.net_qty == Decimal("100")
        
        # Step 7: Sink ??????????????????
        await event_sink.write_report(report)
        await event_sink.write_fill(fill_record)
        
        assert len(event_sink.reports) == 1
        assert len(event_sink.fills) == 1
        
        print("\n=== ???????????????????===")
        print(f"Intent ID: {intent.intent_id}")
        print(f"Order ID: {fill_record.order_id}")
        print(f"Fill Qty: {fill_record.filled_qty} @ {fill_record.fill_price}")
        print(f"Position: {position.net_qty} @ {position.avg_cost}")
        print(f"Report Status: {report.status.value}")
        print(f"Sink Records: {len(event_sink.reports)} reports, {len(event_sink.fills)} fills")

