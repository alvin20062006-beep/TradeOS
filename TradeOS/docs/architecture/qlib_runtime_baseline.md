# Qlib Runtime Baseline
> **文件位置**: `docs/architecture/qlib_runtime_baseline.md`
> **版本**: 0.1 | **维护人**: OK | **生成时间**: 2026-04-07

---

## 1. 当前实际运行版本

| 项目 | 值 |
|------|-----|
| **Package name** | `pyqlib` |
| **Installed version** | `0.9.7` |
| **Install method** | `pip install pyqlib-0.9.7-cp312-cp312-win_amd64.whl`（预编译 wheel） |
| **Installation source** | PyPI wheel（CPython 3.12 Windows x64） |
| **qlib.__version__** | `"0.9.7"` |
| **qlib.__path__** | `site-packages/qlib` |

**为什么用 wheel 而非源码安装？**
- 源码 clone 的 Cython 扩展（`.pyx` → `.pyd`）需要 C 编译器（MSVC/MinGW）
- 当前 Windows 环境无 C 编译器，无法编译
- `pyqlib-0.9.7` wheel 提供预编译扩展，包含 `_libs.rolling` 等所有编译产物

**workspace/qlib 源码 clone 的用途**
- 仅作 **API 参考**：查阅类签名、方法参数
- **不作为运行时依赖**：不参与实际执行路径
- clone 版本与 wheel 版本可能存在 API 差异，以 wheel 0.9.7 为准

---

## 2. 当前环境

```
Python:         3.12.10
OS:             Windows 10 x64
Shell:          PowerShell 7.x
pip:            25.0.1
Virtual env:    (global, site-packages)
qlib version:  0.9.7 (from wheel)
C compiler:     ❌ 不存在（无法编译 .pyx 扩展）
```

---

## 3. 可用子模块（0.9.7 实测）

| 子模块 | 可用性 | 备注 |
|--------|--------|------|
| `import qlib` | ✅ | `__version__ = "0.9.7"` |
| `qlib.init()` | ✅ | 无 provider_uri 最小初始化成功 |
| `qlib.data.D` | ✅ | 数据接口；`D.inst.register()` 可用 |
| `qlib.data.dataset.Dataset` | ✅ | 通用 Dataset 类 |
| `qlib.data.dataset.handler.DataHandlerLP` | ✅ | 数据处理器基类（替代旧 Alpha158） |
| `qlib.model.base.Model` | ✅ | 模型基类 |
| `qlib.model.base.BaseModel` | ✅ | 基础模型接口 |
| `qlib.model.base.Dataset` | ✅ | 模型训练数据集 |
| `qlib.workflow.R` | ✅ | 实验记录器 |
| `qlib.qlib.QlibConfig` | ✅ | 配置对象 |

---

## 4. 不可用/已变化模块

| 模块/类 | 状态 | 替代方案 |
|---------|------|----------|
| `qlib.data.dataset.handler.Alpha158` | ❌ 不存在 | `DataHandlerLP` 基类 + 自定义 processor |
| `qlib.backtest.Backtest` | ❌ 不存在 | 待探查：`qlib.backtest` 其他类 |
| `qlib.backtest` | ⚠️ 部分可用 | 需实测哪些类仍存在 |
| `qlib.model.baseline` | ⚠️ 需实测 | 旧基准模型包 |
| `qlib.data.dataset.handler.MLC` | ❌ 未知 | 需探查 |
| `setuptools_scm` | ✅ 仅版本探测 | workspace clone 源码版本识别 |

---

## 5. 重要 API 约束

### 5.1 `qlib.init()` 调用约定

```python
# 最小调用（无 provider_uri，使用默认 CN 数据路径）
qlib.init(region='us', auto_mount=False)

# provider_uri 指定
qlib.init(provider_uri="path/to/data", region='cn')

# 默认数据路径（Windows）
# C:/Users/hutia/.qlib/qlib_data/cn_data
```

### 5.2 数据初始化依赖

`qlib.data.D.inst.register()` 需要 `qlib.init()` 已执行。未初始化时调用会静默失败。

### 5.3 路径规范（Windows）

- Qlib 默认路径使用 `Path` 对象
- Windows 上 `C:\Users\...` 路径会被解析为 `WindowsPath` 对象
- 序列化时需注意字符串格式

---

## 6. 兼容性分层策略

### Tier 1：直接使用（0.9.7 确认可用）
- `qlib.data.D` 数据查询
- `qlib.workflow.R` 实验记录
- `qlib.model.base` 模型基类
- `qlib.init()` 初始化

### Tier 2：需适配（API 变化已知）
- `DataHandlerLP` 替代 `Alpha158` handler
- 需要自定义 `processor` chain 构建

### Tier 3：待探查（未测试）
- `qlib.backtest` 完整 API
- `qlib.model.baseline`
- `qlib.contrib` 子模块

---

## 7. 开发实现规范

1. **所有实现以 pyqlib==0.9.7 为准**，不得按 workspace/qlib 源码写出 0.9.7 中不存在的 API 调用
2. **不确定时先探查**：新建文件前先 `python -c "from qlib.xxx import YYY"` 确认可用
3. **Tier 3 模块**：Batch 2 中暂不依赖，留作后续探查
4. **path handling**：统一使用 `pathlib.Path`，避免字符串拼接路径

---

## 8. 版本记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-04-07 | 0.1 | 初始版本：pyqlib 0.9.7 实测基线 |
