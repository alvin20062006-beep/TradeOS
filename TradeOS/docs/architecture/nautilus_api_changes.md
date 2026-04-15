# NautilusTrader API 变化记录

**文档版本**: 1.0
**更新时间**: 2026-04-06
**NautilusTrader 版本**: 1.225.0

---

## 概述

本文档记录 NautilusTrader API 与本项目初始假设之间的差异，以及本项目采用的适配方案。

---

## 当前安装版本

```
NautilusTrader: 1.225.0
Python: 3.12.10
Platform: Windows x64
```

---

## 主要 API 变化点

### 1. 订单构造方式

#### 原假设（错误）
```python
# 假设可以直接用简单的参数构造
MarketOrder(
    instrument_id=instrument_id,
    order_side=OrderSide.BUY,
    quantity=100
)
```

#### 实际 API（正确）
```python
MarketOrder(
    TraderId trader_id,           # 必填：交易员 ID
    StrategyId strategy_id,       # 必填：策略 ID
    InstrumentId instrument_id,   # 必填：标的 ID
    ClientOrderId client_order_id, # 必填：客户端订单 ID
    OrderSide order_side,         # 必填：买卖方向
    Quantity quantity,            # 必填：数量（需指定 precision）
    UUID4 init_id,                # 必填：初始化事件 ID（Nautilus UUID4 类型）
    uint64_t ts_init,             # 必填：初始化时间戳（纳秒）
    TimeInForce time_in_force=GTC,
    bool reduce_only=False,
    ...
)
```

### 2. Quantity 和 Price 类型

#### 原假设（错误）
```python
quantity = Quantity(100)
price = Price(150.0)
```

#### 实际 API（正确）
```python
from nautilus_trader.model.objects import Quantity, Price

quantity = Quantity(100, precision=0)  # 必须指定 precision
price = Price(150.0, precision=2)      # 必须指定 precision
```

### 3. UUID4 类型

#### 原假设（错误）
```python
from uuid import uuid4
init_id = uuid4()  # Python 标准库 UUID
```

#### 实际 API（正确）
```python
from nautilus_trader.core.uuid import UUID4
init_id = UUID4()  # Nautilus 自定义 UUID4 类型
```

### 4. InstrumentId 创建

#### 正确用法
```python
from nautilus_trader.model.identifiers import InstrumentId

instrument_id = InstrumentId.from_str('AAPL.XNAS')
# 或
from nautilus_trader.model.identifiers import Symbol, Venue
instrument_id = InstrumentId(Symbol('AAPL'), Venue('XNAS'))
```

### 5. TraderId 和 StrategyId 格式

```python
from nautilus_trader.model.identifiers import TraderId, StrategyId

# TraderId 必须是 "NAME-XXX" 格式（名称-数字，用连字符分隔）
trader_id = TraderId('TESTER-001')

# StrategyId 同样格式
strategy_id = StrategyId('STRATEGY-001')
```

---

## 四种订单类型完整签名

### MarketOrder
```python
MarketOrder(
    trader_id: TraderId,
    strategy_id: StrategyId,
    instrument_id: InstrumentId,
    client_order_id: ClientOrderId,
    order_side: OrderSide,
    quantity: Quantity,
    init_id: UUID4,
    ts_init: int,  # nanoseconds
    time_in_force: TimeInForce = TimeInForce.GTC,
    reduce_only: bool = False,
    quote_quantity: bool = False,
    contingency_type: ContingencyType = ContingencyType.NO_CONTINGENCY,
    ...
)
```

### LimitOrder
```python
LimitOrder(
    trader_id: TraderId,
    strategy_id: StrategyId,
    instrument_id: InstrumentId,
    client_order_id: ClientOrderId,
    order_side: OrderSide,
    quantity: Quantity,
    price: Price,  # 限价
    init_id: UUID4,
    ts_init: int,
    time_in_force: TimeInForce = TimeInForce.GTC,
    expire_time_ns: int = 0,
    post_only: bool = False,
    reduce_only: bool = False,
    ...
)
```

### StopMarketOrder
```python
StopMarketOrder(
    trader_id: TraderId,
    strategy_id: StrategyId,
    instrument_id: InstrumentId,
    client_order_id: ClientOrderId,
    order_side: OrderSide,
    quantity: Quantity,
    trigger_price: Price,  # 触发价
    trigger_type: TriggerType,  # 触发类型
    init_id: UUID4,
    ts_init: int,
    time_in_force: TimeInForce = TimeInForce.GTC,
    expire_time_ns: int = 0,
    reduce_only: bool = False,
    ...
)
```

### StopLimitOrder
```python
StopLimitOrder(
    trader_id: TraderId,
    strategy_id: StrategyId,
    instrument_id: InstrumentId,
    client_order_id: ClientOrderId,
    order_side: OrderSide,
    quantity: Quantity,
    price: Price,           # 限价
    trigger_price: Price,   # 触发价
    trigger_type: TriggerType,
    init_id: UUID4,
    ts_init: int,
    time_in_force: TimeInForce = TimeInForce.GTC,
    expire_time_ns: int = 0,
    post_only: bool = False,
    reduce_only: bool = False,
    ...
)
```

---

## 本项目适配方案

### 方案选择

**方案 A**: 直接在 adapter 中构造订单对象（采用）
- 优点：简单直接，不依赖 Strategy 上下文
- 缺点：需要手动管理 trader_id, strategy_id, init_id, ts_init

**方案 B**: 使用 OrderFactory（未采用）
- OrderFactory 在 NautilusTrader 1.225.0 中不可用
- 主要是 Strategy 类内部的工厂方法

### 实现策略

1. **order_adapter.py** 负责将 `ExecutionIntent` 转换为 Nautilus 订单对象
2. 需要提供 `trader_id` 和 `strategy_id` 作为配置参数
3. 自动生成 `client_order_id`、`init_id`、`ts_init`
4. 从 `ExecutionIntent` 中提取 `instrument_id`、`order_side`、`quantity`、`price` 等参数

### 关键依赖

```python
# 必须从 Nautilus 导入
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.model.objects import Quantity, Price
from nautilus_trader.model.identifiers import (
    TraderId, StrategyId, InstrumentId, ClientOrderId
)
from nautilus_trader.model.enums import OrderSide, TimeInForce, TriggerType
from nautilus_trader.model.orders import (
    MarketOrder, LimitOrder, StopMarketOrder, StopLimitOrder
)
```

---

## 直接构造订单对象的风险

1. **ID 管理风险**：需要手动确保 `client_order_id` 唯一性
2. **时间戳精度**：必须使用纳秒精度（`int(time.time() * 1_000_000_000)`）
3. **精度参数**：`Quantity` 和 `Price` 必须指定 `precision`
4. **类型严格性**：`init_id` 必须是 Nautilus 的 `UUID4` 类型

---

## 测试验证

### 验证时间
2026-04-06 12:45 UTC

### 验证结果
```python
# MarketOrder: ✅ 创建成功
MarketOrder(BUY 100 AAPL.XNAS MARKET GTC, status=INITIALIZED, ...)

# LimitOrder: ✅ 创建成功
LimitOrder(BUY 100 AAPL.XNAS LIMIT @ 150.00 GTC, status=INITIALIZED, ...)

# StopMarketOrder: ✅ 创建成功
StopMarketOrder(BUY 100 AAPL.XNAS STOP_MARKET @ 160.00[DEFAULT] GTC, ...)

# StopLimitOrder: ✅ 创建成功
StopLimitOrder(BUY 100 AAPL.XNAS STOP_LIMIT @ 160.00-STOP[DEFAULT] 155.00-LIMIT GTC, ...)
```

---

## 后续工作

1. 重构 `order_adapter.py` 以使用正确的构造方式
2. 添加 `OrderAdapterConfig` 配置类管理 `trader_id`、`strategy_id`
3. 更新测试用例以匹配新的 API
4. 完成集成测试验证完整链路

---

## 参考资料

- NautilusTrader 官方文档: https://nautilustrader.io/docs/
- 订单类型说明: https://www.interactivebrokers.com/en/trading/orders/
