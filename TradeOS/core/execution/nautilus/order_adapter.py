"""
Nautilus Order Adapter - 订单适配

将本项目 ExecutionIntent 转换为 Nautilus Order 对象。
支持多种订单类型转换。

API 版本: NautilusTrader 1.225.0
更新时间: 2026-04-06
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from time import time
from typing import Optional

try:
    # 核心依赖
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
    # 占位类型
    UUID4 = object
    MarketOrder = LimitOrder = StopMarketOrder = StopLimitOrder = object
    ClientOrderId = InstrumentId = StrategyId = TraderId = object
    NautilusOrderSide = NautilusTIF = TriggerType = ContingencyType = object
    Price = Quantity = object

from ai_trading_tool.core.execution.enums import (
    Side,
    OrderType,
    TimeInForce,
)
from ai_trading_tool.core.execution.models import ExecutionIntent
from ai_trading_tool.core.execution.nautilus.instrument_mapper import InstrumentMapper


@dataclass
class OrderAdapterConfig:
    """订单适配器配置
    
    Attributes:
        trader_id: 交易员 ID，格式 "NAME-XXX"（如 "TRADER-001"）
        strategy_id: 策略 ID，格式 "NAME-XXX"（如 "STRAT-001"）
        default_time_in_force: 默认有效期类型
    """
    trader_id: str = "TRADER-001"
    strategy_id: str = "STRATEGY-001"
    default_time_in_force: TimeInForce = TimeInForce.GTC


class OrderAdapter:
    """订单适配器
    
    负责：
    - ExecutionIntent -> Nautilus Order 转换
    - 订单参数映射（价格、数量、有效期等）
    - 自动生成订单所需的 ID 和时间戳
    
    Note:
        NautilusTrader 1.225.0 要求订单构造时提供：
        - trader_id: 交易员 ID
        - strategy_id: 策略 ID
        - init_id: UUID4 类型（Nautilus 自定义）
        - ts_init: 纳秒级时间戳
    """
    
    def __init__(
        self,
        instrument_mapper: InstrumentMapper,
        config: Optional[OrderAdapterConfig] = None,
    ):
        """初始化订单适配器
        
        Args:
            instrument_mapper: 标的映射器
            config: 适配器配置（可选）
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError(
                "NautilusTrader is not installed. "
                "Install it with: pip install nautilus_trader"
            )
        
        self._mapper = instrument_mapper
        self._config = config or OrderAdapterConfig()
        
        # 预创建 Nautilus ID 对象
        self._trader_id = TraderId(self._config.trader_id)
        self._strategy_id = StrategyId(self._config.strategy_id)
    
    def adapt(
        self,
        intent: ExecutionIntent,
        client_order_id: Optional[str] = None,
    ) -> "MarketOrder | LimitOrder | StopMarketOrder | StopLimitOrder":
        """将 ExecutionIntent 转换为 Nautilus Order
        
        Args:
            intent: 执行意图
            client_order_id: 客户端订单ID（可选，默认自动生成）
            
        Returns:
            Nautilus Order 对象
            
        Raises:
            RuntimeError: Nautilus 未安装
            ValueError: 缺少必要参数（如 LIMIT 订单缺价格）
        """
        # 生成订单ID
        if client_order_id is None:
            client_order_id = f"O-{intent.intent_id[:8].upper()}"
        
        # 获取 Instrument
        instrument_id = self._mapper.to_instrument_id(
            intent.symbol,
            intent.venue,
        )
        
        # 获取缓存的 instrument（用于精度信息）
        instrument = self._mapper.get_cached(intent.symbol)
        if instrument is None:
            # 回测场景：自动创建 equity
            instrument = self._mapper.create_equity(intent.symbol, intent.venue or "NASDAQ")
        
        # 转换参数
        side = self._adapt_side(intent.side)
        quantity = self._adapt_quantity(intent.quantity, instrument.size_precision)
        tif = self._adapt_time_in_force(intent.time_in_force or self._config.default_time_in_force)
        
        # 生成 Nautilus 必需的 ID 和时间戳
        nautilus_client_order_id = ClientOrderId(client_order_id)
        init_id = UUID4()
        ts_init = self._get_current_ts_ns()
        
        # 根据订单类型创建对应订单
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
        """转换交易方向"""
        if side == Side.BUY:
            return NautilusOrderSide.BUY
        else:
            return NautilusOrderSide.SELL
    
    def _adapt_quantity(self, quantity: Decimal, precision: int) -> "Quantity":
        """转换数量
        
        Args:
            quantity: 数量值
            precision: 精度（小数位数）
            
        Returns:
            Nautilus Quantity 对象
        """
        return Quantity(float(quantity), precision)
    
    def _adapt_price(self, price: Decimal, precision: int) -> "Price":
        """转换价格
        
        Args:
            price: 价格值
            precision: 精度（小数位数）
            
        Returns:
            Nautilus Price 对象
        """
        return Price(float(price), precision)
    
    def _adapt_time_in_force(self, tif: TimeInForce) -> "NautilusTIF":
        """转换有效期"""
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
        """获取当前时间戳（纳秒）
        
        Returns:
            UNIX 时间戳（纳秒精度）
        """
        return int(time() * 1_000_000_000)
