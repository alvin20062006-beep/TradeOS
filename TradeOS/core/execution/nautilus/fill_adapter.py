"""
Nautilus Fill Adapter - 鎴愪氦閫傞厤

灏?Nautilus OrderFilled 浜嬩欢杞崲涓烘湰椤圭洰 FillRecord銆?澶勭悊鎴愪氦鏁版嵁鎻愬彇鍜屾牸寮忚浆鎹€?"""

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
    """鎴愪氦閫傞厤鍣?    
    璐熻矗锛?    - Nautilus OrderFilled -> FillRecord 杞崲
    - 鎴愪氦鏁版嵁鎻愬彇鍜屾牸寮忓寲
    """
    
    def __init__(self, instrument_mapper: InstrumentMapper):
        self._mapper = instrument_mapper
    
    def adapt(self, event: "OrderFilled", intent_id: str) -> FillRecord:
        """灏?Nautilus OrderFilled 浜嬩欢杞崲涓?FillRecord
        
        Args:
            event: Nautilus 鎴愪氦浜嬩欢
            intent_id: 鍏宠仈鐨勬墽琛屾剰鍥綢D
            
        Returns:
            FillRecord: 鏈」鐩垚浜よ褰?        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        # 鎻愬彇 symbol 鍜?venue
        symbol, venue = self._mapper.from_instrument_id(event.instrument_id)
        
        # 杞崲鏂瑰悜
        side = self._adapt_side(event.order_side)
        
        # 杞崲娴佸姩鎬ф柟鍚?        liquidity_side = self._adapt_liquidity_side(event.liquidity_side)
        
        # 杞崲鏃堕棿鎴筹紙绾崇 -> datetime锛?        filled_at = self._ns_to_datetime(event.ts_event)
        
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
        """杞崲浜ゆ槗鏂瑰悜"""
        # Nautilus OrderSide 鏄?flag 鏋氫妇锛屽€间负鏁存暟鍊?        # BUY = 1, SELL = 2
        if hasattr(nautilus_side, 'value'):
            # 濡傛灉鏄灇涓剧被鍨?            side_value = nautilus_side.value
        else:
            # 濡傛灉鏄暣鏁?            side_value = int(nautilus_side)
        
        if side_value == 1:  # BUY
            return Side.BUY
        else:  # SELL (鍊间负2)
            return Side.SELL
    
    def _adapt_liquidity_side(
        self,
        nautilus_liquidity: Optional["NautilusLiquiditySide"],
    ) -> Optional[LiquiditySide]:
        """杞崲娴佸姩鎬ф柟鍚?        
        Nautilus LiquiditySide values:
        - NO_LIQUIDITY_SIDE = 0
        - MAKER = 1
        - TAKER = 2
        """
        if nautilus_liquidity is None:
            return None
        
        # 妫€鏌ュ€?        if hasattr(nautilus_liquidity, 'value'):
            ls_value = nautilus_liquidity.value
        else:
            ls_value = int(nautilus_liquidity)
        
        if ls_value == 1:  # MAKER
            return LiquiditySide.MAKER
        elif ls_value == 2:  # TAKER
            return LiquiditySide.TAKER
        
        return None
    
    def _ns_to_datetime(self, ns_timestamp: int) -> datetime:
        """灏嗙撼绉掓椂闂存埑杞崲涓?datetime
        
        Args:
            ns_timestamp: 绾崇绾ф椂闂存埑
            
        Returns:
            datetime: Python datetime 瀵硅薄
        """
        # 绾崇 -> 绉?        seconds = ns_timestamp / 1_000_000_000
        return datetime.fromtimestamp(seconds)
    
    def adapt_many(
        self,
        events: list["OrderFilled"],
        intent_id: str,
    ) -> list[FillRecord]:
        """鎵归噺杞崲鎴愪氦浜嬩欢
        
        Args:
            events: Nautilus 鎴愪氦浜嬩欢鍒楄〃
            intent_id: 鍏宠仈鐨勬墽琛屾剰鍥綢D
            
        Returns:
            list[FillRecord]: 鎴愪氦璁板綍鍒楄〃
        """
        return [self.adapt(e, intent_id) for e in events]

