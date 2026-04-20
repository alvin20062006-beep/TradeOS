"""
Nautilus Order Adapter - 璁㈠崟閫傞厤

灏嗘湰椤圭洰 ExecutionIntent 杞崲涓?Nautilus Order 瀵硅薄銆?鏀寔澶氱璁㈠崟绫诲瀷杞崲銆?
API 鐗堟湰: NautilusTrader 1.225.0
鏇存柊鏃堕棿: 2026-04-06
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from time import time
from typing import Optional

try:
    # 鏍稿績渚濊禆
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
    # 鍗犱綅绫诲瀷
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
    """璁㈠崟閫傞厤鍣ㄩ厤缃?    
    Attributes:
        trader_id: 浜ゆ槗鍛?ID锛屾牸寮?"NAME-XXX"锛堝 "TRADER-001"锛?        strategy_id: 绛栫暐 ID锛屾牸寮?"NAME-XXX"锛堝 "STRAT-001"锛?        default_time_in_force: 榛樿鏈夋晥鏈熺被鍨?    """
    trader_id: str = "TRADER-001"
    strategy_id: str = "STRATEGY-001"
    default_time_in_force: TimeInForce = TimeInForce.GTC


class OrderAdapter:
    """璁㈠崟閫傞厤鍣?    
    璐熻矗锛?    - ExecutionIntent -> Nautilus Order 杞崲
    - 璁㈠崟鍙傛暟鏄犲皠锛堜环鏍笺€佹暟閲忋€佹湁鏁堟湡绛夛級
    - 鑷姩鐢熸垚璁㈠崟鎵€闇€鐨?ID 鍜屾椂闂存埑
    
    Note:
        NautilusTrader 1.225.0 瑕佹眰璁㈠崟鏋勯€犳椂鎻愪緵锛?        - trader_id: 浜ゆ槗鍛?ID
        - strategy_id: 绛栫暐 ID
        - init_id: UUID4 绫诲瀷锛圢autilus 鑷畾涔夛級
        - ts_init: 绾崇绾ф椂闂存埑
    """
    
    def __init__(
        self,
        instrument_mapper: InstrumentMapper,
        config: Optional[OrderAdapterConfig] = None,
    ):
        """鍒濆鍖栬鍗曢€傞厤鍣?        
        Args:
            instrument_mapper: 鏍囩殑鏄犲皠鍣?            config: 閫傞厤鍣ㄩ厤缃紙鍙€夛級
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError(
                "NautilusTrader is not installed. "
                "Install it with: pip install nautilus_trader"
            )
        
        self._mapper = instrument_mapper
        self._config = config or OrderAdapterConfig()
        
        # 棰勫垱寤?Nautilus ID 瀵硅薄
        self._trader_id = TraderId(self._config.trader_id)
        self._strategy_id = StrategyId(self._config.strategy_id)
    
    def adapt(
        self,
        intent: ExecutionIntent,
        client_order_id: Optional[str] = None,
    ) -> "MarketOrder | LimitOrder | StopMarketOrder | StopLimitOrder":
        """灏?ExecutionIntent 杞崲涓?Nautilus Order
        
        Args:
            intent: 鎵ц鎰忓浘
            client_order_id: 瀹㈡埛绔鍗旾D锛堝彲閫夛紝榛樿鑷姩鐢熸垚锛?            
        Returns:
            Nautilus Order 瀵硅薄
            
        Raises:
            RuntimeError: Nautilus 鏈畨瑁?            ValueError: 缂哄皯蹇呰鍙傛暟锛堝 LIMIT 璁㈠崟缂轰环鏍硷級
        """
        # 鐢熸垚璁㈠崟ID
        if client_order_id is None:
            client_order_id = f"O-{intent.intent_id[:8].upper()}"
        
        # 鑾峰彇 Instrument
        instrument_id = self._mapper.to_instrument_id(
            intent.symbol,
            intent.venue,
        )
        
        # 鑾峰彇缂撳瓨鐨?instrument锛堢敤浜庣簿搴︿俊鎭級
        instrument = self._mapper.get_cached(intent.symbol)
        if instrument is None:
            # 鍥炴祴鍦烘櫙锛氳嚜鍔ㄥ垱寤?equity
            instrument = self._mapper.create_equity(intent.symbol, intent.venue or "NASDAQ")
        
        # 杞崲鍙傛暟
        side = self._adapt_side(intent.side)
        quantity = self._adapt_quantity(intent.quantity, instrument.size_precision)
        tif = self._adapt_time_in_force(intent.time_in_force or self._config.default_time_in_force)
        
        # 鐢熸垚 Nautilus 蹇呴渶鐨?ID 鍜屾椂闂存埑
        nautilus_client_order_id = ClientOrderId(client_order_id)
        init_id = UUID4()
        ts_init = self._get_current_ts_ns()
        
        # 鏍规嵁璁㈠崟绫诲瀷鍒涘缓瀵瑰簲璁㈠崟
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
        """杞崲浜ゆ槗鏂瑰悜"""
        if side == Side.BUY:
            return NautilusOrderSide.BUY
        else:
            return NautilusOrderSide.SELL
    
    def _adapt_quantity(self, quantity: Decimal, precision: int) -> "Quantity":
        """杞崲鏁伴噺
        
        Args:
            quantity: 鏁伴噺鍊?            precision: 绮惧害锛堝皬鏁颁綅鏁帮級
            
        Returns:
            Nautilus Quantity 瀵硅薄
        """
        return Quantity(float(quantity), precision)
    
    def _adapt_price(self, price: Decimal, precision: int) -> "Price":
        """杞崲浠锋牸
        
        Args:
            price: 浠锋牸鍊?            precision: 绮惧害锛堝皬鏁颁綅鏁帮級
            
        Returns:
            Nautilus Price 瀵硅薄
        """
        return Price(float(price), precision)
    
    def _adapt_time_in_force(self, tif: TimeInForce) -> "NautilusTIF":
        """杞崲鏈夋晥鏈?""
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
        """鑾峰彇褰撳墠鏃堕棿鎴筹紙绾崇锛?        
        Returns:
            UNIX 鏃堕棿鎴筹紙绾崇绮惧害锛?        """
        return int(time() * 1_000_000_000)

