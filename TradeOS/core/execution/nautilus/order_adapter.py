"""
Nautilus Order Adapter - ?????????

????????? ExecutionIntent ???????Nautilus Order ????????????????????????????????
API ????? NautilusTrader 1.225.0
?????????: 2026-04-06
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from time import time
from typing import Optional

try:
    # ?????????
    from nautilus_trader.core.uuid import UUID4
    from nautilus_trader.model.orders import (
        MarketOrder,
        LimitOrder,
        StopMarketOrder,
        StopLimitOrder,
    )
    from nautilus_trader.model.identifiers import (
        ClientOrderId,
        InstrumentId,
        StrategyId,
        TraderId,
    )
    from nautilus_trader.model.enums import (
        OrderSide as NautilusOrderSide,
        TimeInForce as NautilusTIF,
        TriggerType,
        ContingencyType,
    )
    from nautilus_trader.model.objects import Price, Quantity
    NAUTILUS_AVAILABLE = True
except ImportError:
    NAUTILUS_AVAILABLE = False
    # ??????????
    UUID4 = object
    MarketOrder = LimitOrder = StopMarketOrder = StopLimitOrder = object
    ClientOrderId = InstrumentId = StrategyId = TraderId = object
    NautilusOrderSide = NautilusTIF = TriggerType = ContingencyType = object
    Price = Quantity = object

from core.execution.enums import (
    Side,
    OrderType,
    TimeInForce,
)
from core.execution.models import ExecutionIntent
from core.execution.nautilus.instrument_mapper import InstrumentMapper


@dataclass
class OrderAdapterConfig:
    """????????????????    
    Attributes:
        trader_id: ???????ID???????"NAME-XXX"?????"TRADER-001"??        strategy_id: ?????ID???????"NAME-XXX"?????"STRAT-001"??        default_time_in_force: ????????????????    """
    trader_id: str = "TRADER-001"
    strategy_id: str = "STRATEGY-001"
    default_time_in_force: TimeInForce = TimeInForce.GTC


class OrderAdapter:
    """???????????    
    ???????    - ExecutionIntent -> Nautilus Order ?????
    - ??????????????????????????????????????????
    - ??????????????????????ID ?????????
    
    Note:
        NautilusTrader 1.225.0 ???????????????????????        - trader_id: ???????ID
        - strategy_id: ?????ID
        - init_id: UUID4 ????????utilus ?????????
        - ts_init: ?????????????
    """
    
    def __init__(
        self,
        instrument_mapper: InstrumentMapper,
        config: Optional[OrderAdapterConfig] = None,
    ):
        """???????????????????        
        Args:
            instrument_mapper: ???????????            config: ?????????????????????
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError(
                "NautilusTrader is not installed. "
                "Install it with: pip install nautilus_trader"
            )
        
        self._mapper = instrument_mapper
        self._config = config or OrderAdapterConfig()
        
        # ???????Nautilus ID ?????
        self._trader_id = TraderId(self._config.trader_id)
        self._strategy_id = StrategyId(self._config.strategy_id)
    
    def adapt(
        self,
        intent: ExecutionIntent,
        client_order_id: Optional[str] = None,
    ) -> "MarketOrder | LimitOrder | StopMarketOrder | StopLimitOrder":
        """??ExecutionIntent ???????Nautilus Order
        
        Args:
            intent: ?????????
            client_order_id: ????????????D?????????????????????????            
        Returns:
            Nautilus Order ?????
            
        Raises:
            RuntimeError: Nautilus ???????            ValueError: ?????????????????? LIMIT ??????????????
        """
        # ?????????ID
        if client_order_id is None:
            client_order_id = f"O-{intent.intent_id[:8].upper()}"
        
        # ?????Instrument
        instrument_id = self._mapper.to_instrument_id(
            intent.symbol,
            intent.venue,
        )
        
        # ???????????instrument??????????????????
        instrument = self._mapper.get_cached(intent.symbol)
        if instrument is None:
            # ????????????????????equity
            instrument = self._mapper.create_equity(intent.symbol, intent.venue or "NASDAQ")
        
        # ?????????
        side = self._adapt_side(intent.side)
        quantity = self._adapt_quantity(intent.quantity, instrument.size_precision)
        tif = self._adapt_time_in_force(intent.time_in_force or self._config.default_time_in_force)
        
        # ?????Nautilus ???????ID ?????????
        nautilus_client_order_id = ClientOrderId(client_order_id)
        init_id = UUID4()
        ts_init = self._get_current_ts_ns()
        
        # ???????????????????????????
        if intent.order_type == OrderType.MARKET:
            return MarketOrder(
                trader_id=self._trader_id,
                strategy_id=self._strategy_id,
                instrument_id=instrument_id,
                client_order_id=nautilus_client_order_id,
                order_side=side,
                quantity=quantity,
                init_id=init_id,
                ts_init=ts_init,
                time_in_force=tif,
            )
        
        elif intent.order_type == OrderType.LIMIT:
            if intent.price is None:
                raise ValueError("LIMIT order requires price")
            price = self._adapt_price(intent.price, instrument.price_precision)
            return LimitOrder(
                trader_id=self._trader_id,
                strategy_id=self._strategy_id,
                instrument_id=instrument_id,
                client_order_id=nautilus_client_order_id,
                order_side=side,
                quantity=quantity,
                price=price,
                init_id=init_id,
                ts_init=ts_init,
                time_in_force=tif,
            )
        
        elif intent.order_type == OrderType.STOP_MARKET:
            if intent.stop_price is None:
                raise ValueError("STOP_MARKET order requires stop_price")
            trigger_price = self._adapt_price(intent.stop_price, instrument.price_precision)
            return StopMarketOrder(
                trader_id=self._trader_id,
                strategy_id=self._strategy_id,
                instrument_id=instrument_id,
                client_order_id=nautilus_client_order_id,
                order_side=side,
                quantity=quantity,
                trigger_price=trigger_price,
                trigger_type=TriggerType.DEFAULT,
                init_id=init_id,
                ts_init=ts_init,
                time_in_force=tif,
            )
        
        elif intent.order_type == OrderType.STOP_LIMIT:
            if intent.price is None or intent.stop_price is None:
                raise ValueError("STOP_LIMIT order requires both price and stop_price")
            price = self._adapt_price(intent.price, instrument.price_precision)
            trigger_price = self._adapt_price(intent.stop_price, instrument.price_precision)
            return StopLimitOrder(
                trader_id=self._trader_id,
                strategy_id=self._strategy_id,
                instrument_id=instrument_id,
                client_order_id=nautilus_client_order_id,
                order_side=side,
                quantity=quantity,
                price=price,
                trigger_price=trigger_price,
                trigger_type=TriggerType.DEFAULT,
                init_id=init_id,
                ts_init=ts_init,
                time_in_force=tif,
            )
        
        else:
            raise ValueError(f"Unsupported order type: {intent.order_type}")
    
    def _adapt_side(self, side: Side) -> "NautilusOrderSide":
        """??????????????"""
        if side == Side.BUY:
            return NautilusOrderSide.BUY
        else:
            return NautilusOrderSide.SELL
    
    def _adapt_quantity(self, quantity: Decimal, precision: int) -> "Quantity":
        """?????????
        
        Args:
            quantity: ???????            precision: ??????????????????
            
        Returns:
            Nautilus Quantity ?????
        """
        return Quantity(float(quantity), precision)
    
    def _adapt_price(self, price: Decimal, precision: int) -> "Price":
        """?????????
        
        Args:
            price: ???????            precision: ??????????????????
            
        Returns:
            Nautilus Price ?????
        """
        return Price(float(price), precision)
    
    def _adapt_time_in_force(self, tif: TimeInForce) -> "NautilusTIF":
        """???????????"""
        mapping = {
            TimeInForce.GTC: NautilusTIF.GTC,
            TimeInForce.IOC: NautilusTIF.IOC,
            TimeInForce.FOK: NautilusTIF.FOK,
            TimeInForce.DAY: NautilusTIF.DAY,
            TimeInForce.GTD: NautilusTIF.GTD,
            TimeInForce.AT_THE_OPEN: NautilusTIF.AT_THE_OPEN,
            TimeInForce.AT_THE_CLOSE: NautilusTIF.AT_THE_CLOSE,
        }
        return mapping.get(tif, NautilusTIF.GTC)
    
    def _get_current_ts_ns(self) -> int:
        """?????????????????????????        
        Returns:
            UNIX ????????????????????        """
        return int(time() * 1_000_000_000)

