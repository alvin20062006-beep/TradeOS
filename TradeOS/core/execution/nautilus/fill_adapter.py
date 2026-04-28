"""
Nautilus Fill Adapter - ?????????

??Nautilus OrderFilled ?????????????????? FillRecord??????????????????????????????????"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

try:
    from nautilus_trader.model.events import OrderFilled
    from nautilus_trader.model.enums import LiquiditySide as NautilusLiquiditySide
    NAUTILUS_AVAILABLE = True
except ImportError:
    NAUTILUS_AVAILABLE = False
    OrderFilled = object
    NautilusLiquiditySide = object

from core.execution.enums import Side, LiquiditySide
from core.execution.models import FillRecord
from core.execution.nautilus.instrument_mapper import InstrumentMapper


class FillAdapter:
    """???????????    
    ???????    - Nautilus OrderFilled -> FillRecord ?????
    - ???????????????????????
    """
    
    def __init__(self, instrument_mapper: InstrumentMapper):
        self._mapper = instrument_mapper
    
    def adapt(self, event: "OrderFilled", intent_id: str) -> FillRecord:
        """??Nautilus OrderFilled ???????????FillRecord
        
        Args:
            event: Nautilus ?????????
            intent_id: ?????????????????
            
        Returns:
            FillRecord: ????????????????        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        # ?????symbol ??venue
        symbol, venue = self._mapper.from_instrument_id(event.instrument_id)
        
        # ?????????
        side = self._adapt_side(event.order_side)
        
        liquidity_side = self._adapt_liquidity_side(event.liquidity_side)
        
        filled_at = self._ns_to_datetime(event.ts_event)
        
        return FillRecord(
            order_id=str(event.client_order_id),
            intent_id=intent_id,
            symbol=symbol,
            side=side,
            filled_qty=Decimal(str(event.last_qty)),
            fill_price=Decimal(str(event.last_px)),
            fees=Decimal(str(event.commission.as_double())) if event.commission else Decimal("0"),
            venue=venue,
            trade_id=str(event.trade_id) if event.trade_id else None,
            liquidity_side=liquidity_side,
            filled_at=filled_at,
            raw_reference=str(event),
        )
    
    def _adapt_side(self, nautilus_side) -> Side:
        """??????????????"""
        # Nautilus OrderSide ??flag ???????????????????        # BUY = 1, SELL = 2
        if hasattr(nautilus_side, 'value'):
            side_value = nautilus_side.value
        else:
            side_value = int(nautilus_side)
        
        if side_value == 1:  # BUY
            return Side.BUY
        else:  # SELL (?????)
            return Side.SELL
    
    def _adapt_liquidity_side(
        self,
        nautilus_liquidity: Optional["NautilusLiquiditySide"],
    ) -> Optional[LiquiditySide]:
        """???????????????        
        Nautilus LiquiditySide values:
        - NO_LIQUIDITY_SIDE = 0
        - MAKER = 1
        - TAKER = 2
        """
        if nautilus_liquidity is None:
            return None
        
        if hasattr(nautilus_liquidity, 'value'):
            ls_value = nautilus_liquidity.value
        else:
            ls_value = int(nautilus_liquidity)
        
        if ls_value == 1:  # MAKER
            return LiquiditySide.MAKER
        elif ls_value == 2:  # TAKER
            return LiquiditySide.TAKER
        
        return None
    
    def _ns_to_datetime(self, ns_timestamp: int) -> datetime:
        """????????????????????datetime
        
        Args:
            ns_timestamp: ?????????????
            
        Returns:
            datetime: Python datetime ?????
        """
        seconds = ns_timestamp / 1_000_000_000
        return datetime.fromtimestamp(seconds)
    
    def adapt_many(
        self,
        events: list["OrderFilled"],
        intent_id: str,
    ) -> list[FillRecord]:
        """??????????????????
        
        Args:
            events: Nautilus ??????????????
            intent_id: ?????????????????
            
        Returns:
            list[FillRecord]: ??????????????
        """
        return [self.adapt(e, intent_id) for e in events]

