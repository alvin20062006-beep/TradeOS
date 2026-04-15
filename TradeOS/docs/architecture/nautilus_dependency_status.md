# NautilusTrader 依赖状态说明

## 当前状态

**NautilusTrader 安装状态**: ❌ 未安装

**最后检查时间**: 2026-04-06 22:10 UTC+10

---

## 组件状态

| 组件 | 代码实现 | 导入测试 | 功能测试 | 备注 |
|------|---------|---------|---------|------|
| `instrument_mapper.py` | ✅ | ✅ | ⏭️ SKIP | 需要 Nautilus |
| `order_adapter.py` | ✅ | ✅ | ⏭️ SKIP | 需要 Nautilus |
| `fill_adapter.py` | ✅ | ✅ | ⏭️ SKIP | 需要 Nautilus |
| `data_adapter.py` | ✅ | ✅ | ⏭️ SKIP | 需要 Nautilus |
| `nautilus/adapter.py` | ✅ | ✅ | ⏭️ SKIP | 需要 Nautilus |
| `router.py` | ✅ | ✅ | ⏭️ SKIP | 需要 Nautilus |
| `runtime.py` | ✅ | ✅ | ⏭️ SKIP | 需要 Nautilus |

**图例**:
- ✅ 已完成
- ⏭️ SKIP 因依赖缺失跳过
- ❌ 失败
- ⬜ 未开始

---

## 测试状态

### 单元测试

| 测试文件 | 测试用例数 | 通过 | 跳过 | 失败 |
|---------|-----------|------|------|------|
| `test_instrument_mapper.py` | 14 | 2 | 12 | 0 |
| `test_order_adapter.py` | 13 | 0 | 13 | 0 |
| `test_fill_adapter.py` | 8 | 0 | 8 | 0 |
| `test_data_adapter.py` | 14 | 0 | 14 | 0 |
| `test_nautilus_availability.py` | 14 | 14 | 0 | 0 |

**总计**: 63 个测试用例，16 通过，47 跳过，0 失败

### 集成测试

| 测试文件 | 状态 | 备注 |
|---------|------|------|
| `test_backtest_min_loop.py` | ⬜ 待创建 | 最小闭环集成测试 |

---

## 降级行为验证

### ✅ 已验证

1. **NAUTILUS_AVAILABLE 标志**: 正确返回 `False`
2. **NautilusAdapter 初始化**: 抛出 `RuntimeError`，包含安装指令
3. **NautilusRouter 初始化**: 抛出 `RuntimeError`，包含安装指令
4. **ExecutionRuntime 初始化**: 抛出 `RuntimeError`，包含安装指令
5. **错误信息**: 所有错误信息包含 `pip install nautilus-trader`

### ⏳ 待验证（需要 Nautilus 安装）

1. **instrument_mapper 映射逻辑**: Symbol ↔ InstrumentId 转换
2. **order_adapter 订单创建**: 4 种订单类型映射
3. **fill_adapter 成交转换**: OrderFilled → FillRecord
4. **data_adapter 数据转换**: Bar/Tick 映射
5. **最小闭环**: ExecutionIntent → Order → Fill → Report

---

## 安装说明

### 安装 NautilusTrader

```bash
# 从 PyPI 安装
pip install nautilus-trader

# 或从源码安装（获取最新功能）
pip install git+https://github.com/nautechsystems/nautilus_trader.git
```

### 验证安装

```bash
python -c "import nautilus_trader; print(nautilus_trader.__version__)"
```

### 安装后测试

```bash
cd C:\Users\hutia\.qclaw\workspace\ai-trading-tool
python -m pytest tests/unit/ -v
```

---

## 设计约束

1. **可选依赖**: NautilusTrader 为可选依赖，不影响项目其他部分
2. **显式失败**: Nautilus 不可用时，组件初始化抛出明确异常
3. **不静默失败**: 所有 Nautilus 相关操作都有明确的错误处理
4. **安装指令**: 错误信息包含完整的安装指南

---

## 下一步

1. 安装 NautilusTrader
2. 重新运行单元测试，验证所有测试通过
3. 创建并运行集成测试 `test_backtest_min_loop.py`
4. 验证最小闭环：ExecutionIntent → Order → Fill → Report

---

## 更新日志

- **2026-04-06**: 初始创建，记录 Nautilus 未安装状态
