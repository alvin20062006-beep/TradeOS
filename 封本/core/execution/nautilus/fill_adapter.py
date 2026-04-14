"""
Nautilus Fill Adapter - 成交适配

将 Nautilus OrderFilled 事件转换为本项目 FillRecord。
处理成交数据提取和格式转换。
"""

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

from ai_trading_tool.core.execution.enums import Side, LiquiditySide
from ai_trading_tool.core.execution.models import FillRecord
from ai_trading_tool.core.execution.nautilus.instrument_mapper import InstrumentMapper


class FillAdapter:
    """成交适配器
    
    负责：
    - Nautilus OrderFilled -> FillRecord 转换
    - 成交数据提取和格式化
    """
    
    def __init__(self, instrument_mapper: InstrumentMapper):
        self._mapper = instrument_mapper
    
    def adapt(self, event: "OrderFilled", intent_id: str) -> FillRecord:
        """将 Nautilus OrderFilled 事件转换为 FillRecord
        
        Args:
            event: Nautilus 成交事件
            intent_id: 关联的执行意图ID
            
        Returns:
            FillRecord: 本项目成交记录
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError("NautilusTrader not available")
        
        # 提取 symbol 和 venue
        symbol, venue = self._mapper.from_instrument_id(event.instrument_id)
        
        # 转换方向
        side = self._adapt_side(event.order_side)
        
        # 转换流动性方向
        liquidity_side = self._adapt_liquidity_side(event.liquidity_side)
        
        # 转换时间戳（纳秒 -> datetime）
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
        """转换交易方向"""
        # Nautilus OrderSide 是 flag 枚举，值为整数值
        # BUY = 1, SELL = 2
        if hasattr(nautilus_side, 'value'):
            # 如果是枚举类型
            side_value = nautilus_side.value
        else:
            # 如果是整数
            side_value = int(nautilus_side)
        
        if side_value == 1:  # BUY
            return Side.BUY
        else:  # SELL (值为2)
            return Side.SELL
    
    def _adapt_liquidity_side(
        self,
        nautilus_liquidity: Optional["NautilusLiquiditySide"],
    ) -> Optional[LiquiditySide]:
        """转换流动性方向
        
        Nautilus LiquiditySide values:
        - NO_LIQUIDITY_SIDE = 0
        - MAKER = 1
        - TAKER = 2
        """
        if nautilus_liquidity is None:
            return None
        
        # 检查值
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
        """将纳秒时间戳转换为 datetime
        
        Args:
            ns_timestamp: 纳秒级时间戳
            
        Returns:
            datetime: Python datetime 对象
        """
        # 纳秒 -> 秒
        seconds = ns_timestamp / 1_000_000_000
        return datetime.fromtimestamp(seconds)
    
    def adapt_many(
        self,
        events: list["OrderFilled"],
        intent_id: str,
    ) -> list[FillRecord]:
        """批量转换成交事件
        
        Args:
            events: Nautilus 成交事件列表
            intent_id: 关联的执行意图ID
            
        Returns:
            list[FillRecord]: 成交记录列表
        """
        return [self.adapt(e, intent_id) for e in events]
