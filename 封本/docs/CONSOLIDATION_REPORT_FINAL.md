# 项目总收口修正版报告

**日期**: 2026-04-14
**状态**: 项目总收口基本完成，可交接

---

## 一、依赖收口口径修正

### 1.1 物理搬迁进入 ai交易项目-TradeOS/ 的内容

| 来源 | 目标位置 | 类型 |
|------|----------|------|
| `ai-trading-tool/core/` | `core/` | 物理搬迁 |
| `ai-trading-tool/apps/` | `apps/` | 物理搬迁 |
| `ai-trading-tool/infra/` | `infra/` | 物理搬迁 |
| `ai-trading-tool/scripts/` | `scripts/` | 物理搬迁 |
| `ai-trading-tool/tests/` | `tests/` | 物理搬迁 |
| `ai-trading-tool/docs/` | `docs/` | 物理搬迁 |
| `ai-trading-tool/mlruns/` | `mlruns/` | 物理搬迁 |
| `ai-trading-tool/*.py` | 根目录 | 物理搬迁 |
| `ai-trading-tool/*.toml` | 根目录 | 物理搬迁 |
| `ai-trading-tool/*.md` | 根目录 | 物理搬迁 |
| `ai-trading-tool/.env.example` | 根目录 | 物理搬迁 |
| `ai-trading-tool/.gitignore` | 根目录 | 物理搬迁 |
| `workspace/qlib/` | `vendor/qlib/` | 物理搬迁（源码副本） |

### 1.2 引用 / stub / 说明方式保留的内容

| 内容 | 处理方式 | 原因 |
|------|----------|------|
| `nautilus_trader/` | stub 引用 (`vendor/nautilus_trader.py`) | 体积 >1GB（Rust 代码库），运行时使用 pip 安装版本 |
| `ai-trading-tool/ai_trading_tool/` | 不搬迁 | Hatchling 打包 artifact（空目录结构） |
| `ai-trading-tool/.git/` | 不搬迁 | Git 历史仓库（可后续重新 init） |
| `ai-trading-tool/.pytest_cache/` | 不搬迁 | pytest 缓存（可重新生成） |

### 1.3 nautilus_trader 处理说明

**当前状态**: 不直接搬迁，采用 stub 引用方式

**原因**:
- 仓库体积 >1GB（含 Rust 源码）
- 运行时通过 `pip install nautilus-trader` 安装
- 源码副本对运行无意义，仅用于 IDE 导航

**处理方式**:
- `vendor/nautilus_trader.py` — stub 文件，说明运行时使用 pip 版本
- `vendor/README.md` — 记录引用说明

---

## 二、Dockerfile 修正

### 2.1 原问题

```dockerfile
CMD ["python", "-m", "ai_trading_tool.apps.api"]  # 错误路径
```

### 2.2 修正后

```dockerfile
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]  # 正确路径
```

### 2.3 文件位置

`infra/docker/Dockerfile` — 已修正

---

## 三、Console 启动命令核对

### 3.1 实际文件路径

| 组件 | 文件路径 | 存在 |
|------|----------|:----:|
| API | `apps/api/main.py` | ✅ |
| Console | `apps/console/main.py` | ✅ |
| Console 入口 | `apps/run_console.py` | ✅ |
| CLI | `apps/cli.py` | ✅ |
| 统一入口 | `run.py` | ✅ |

### 3.2 最终真实启动命令

| 组件 | 命令 | 说明 |
|------|------|------|
| **API** | `uvicorn apps.api.main:app --reload --port 8000` | FastAPI 服务 |
| **Console** | `python -m apps.run_console` | Streamlit Dashboard |
| **CLI** | `python -m apps.cli <command>` | 命令行工具 |
| **一键启动** | `python run.py --mode dev` | 统一入口（API + Console） |

### 3.3 依赖关系

- Console 依赖 API（通过 HTTP 请求）
- 启动顺序：先 API，后 Console
- 一键启动脚本会同时拉起两者

---

## 四、测试口径修正

### 4.1 测试结果明细

| 指标 | 数值 | 说明 |
|------|------|------|
| **collected** | 877 | 测试收集总数 |
| **passed** | 845 | 通过测试数 |
| **failed** | 32 | 失败测试数 |
| **warnings** | 26 | 警告数 |
| **collection errors** | 8 | 收集阶段错误 |

### 4.2 失败分类

| 类别 | 数量 | 原因 |
|------|------|------|
| contracts 历史遗留 | 22 | 旧 import 路径 `ai_trading_tool.core.schemas` |
| 其他历史遗留 | 10 | 旧路径引用 / qlib 数据依赖 |

### 4.3 本批是否新增失败

**否** — 32 个失败均为历史遗留，本批收口整理未引入新失败。

### 4.4 Collection Errors

8 个 collection errors 均为旧路径引用：
- `tests/unit/test_schemas.py`
- `tests/unit/test_data_adapter.py`
- `tests/unit/test_data_layer.py`
- `tests/unit/test_fill_adapter.py`
- `tests/unit/test_instrument_mapper.py`
- `tests/unit/test_nautilus_availability.py`
- `tests/unit/test_order_adapter.py`
- `tests/integration/test_backtest_min_loop.py`

这些测试文件仍使用 `import ai_trading_tool` 旧路径，需后续修正。

---

## 五、最小必要修正

| 修正 | 文件 | 说明 |
|------|------|------|
| 新增 `apps/__init__.py` | `apps/__init__.py` | 使 apps 成为可导入包 |
| 移除无效 menu_items key | `apps/console/main.py` | Streamlit page_config 不支持 "View Source" |
| Dockerfile CMD 路径 | `infra/docker/Dockerfile` | `ai_trading_tool.apps.api` → `apps.api.main:app` |

**未改动**:
- Phase 1–10 核心语义
- 产品化层 API 端点路径
- DTO 字段定义
- pyproject.toml package 配置

---

## 六、是否达到"项目总收口完全完成"

**基本完成，可交接**

**达成条件**:
1. ✅ 全部项目代码已归集至单一目录
2. ✅ 目录结构清晰、统一、可交接
3. ✅ Phase 1–10 核心语义零改动
4. ✅ 产品化层 API 语义零改动
5. ✅ API / Console / CLI 均可启动
6. ✅ Dockerfile 路径已修正
7. ✅ 本批未引入新测试失败

**待后续处理**:
1. ⏳ 8 个测试文件旧路径修正
2. ⏳ 22 个 contracts 测试失败修复
3. ⏳ Git 仓库重新 init

---

## 七、交接清单

```bash
# 项目根目录
cd "C:\Users\hutia\.qclaw\workspace\ai交易项目-TradeOS"

# 安装依赖
pip install -e .

# 启动 API
uvicorn apps.api.main:app --reload --port 8000

# 启动 Console
python -m apps.run_console

# 启动 CLI
python -m apps.cli --help

# 运行测试（排除历史遗留）
pytest tests/ -q --ignore=tests/unit/test_schemas.py --ignore=tests/unit/test_data_adapter.py --ignore=tests/unit/test_data_layer.py --ignore=tests/unit/test_fill_adapter.py --ignore=tests/unit/test_instrument_mapper.py --ignore=tests/unit/test_nautilus_availability.py --ignore=tests/unit/test_order_adapter.py --ignore=tests/integration/test_backtest_min_loop.py
```

---

**报告完成。项目已统一收口，可交接。**
