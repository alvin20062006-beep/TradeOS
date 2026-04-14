# Phase 4 规划文档：Qlib 研究工厂接入（含 Alpha 因子体系）

**更新时间**：2026-04-07
**版本**：v1.2（补充执行约束 + Batch 1 实施顺序）

---

## 执行约束（4 条）

### 约束 1：Alpha Baseline 三层区分

Alpha baseline 必须明确区分三层，不得混为一层：

| 层级 | 名称 | 说明 | 输出对象 |
|------|------|------|----------|
| L1 | 原始 Alpha | 因子原始计算值，未做任何处理 | `AlphaFactorValue.raw_value` |
| L2 | 标准化 Alpha | 经过 winsorize / zscore / rank 处理 | `AlphaFactorValue.normalized_value` |
| L3 | 组合 Alpha | 多因子加权 / PCA / IC 加权组合 | 单独的 CompositeFactor 模型 |

三层各自独立注册、独立版本号。

### 约束 2：Baseline 因子数据源约束

Baseline alpha 先优先使用**当前数据层稳定能产出**的字段：
- ✅ bars（OHLCV）
- ✅ volume
- ✅ 已有技术指标（RSI / MACD / BB 等）
- ✅ 当前可得基本面字段（PE / PB / ROE 等，占位简化实现）
- ✅ 当前可得情绪字段（占位简化实现）

❌ 不为凑 14 个因子引入不稳定的新数据依赖。
❌ 不在 baseline 阶段接需要额外爬取/购买的数据源。

### 约束 3：AlphaValidationResult 可执行检查项

`AlphaValidationResult` 必须包含可执行的质量检查（不是空壳 schema）：

```python
class AlphaValidationResult(BaseModel):
    # ... 其他字段 ...
    
    # 可执行检查项
    coverage: float = 0.0          # 非空值比例 0~1，阈值 > 0.9
    null_ratio: float = 0.0       # 空值比例 0~1，阈值 < 0.1
    constant_ratio: float = 0.0   # 常数值比例 0~1，阈值 < 0.05
    outlier_ratio: float = 0.0    # 极端值比例 0~1，阈值 < 0.05
    correlation_warning: bool = False  # 与现有因子相关性 > 0.9
    leakage_warning: bool = False      # 因子值与当期收益相关性异常高
    
    is_qualified: bool = False
    fail_reasons: list[str] = []
```

检查函数必须可执行并返回具体数值，不只是 schema 占位。

### 约束 4：SignalCandidate 研究导出语义

Phase 4 导出的 `SignalCandidate` 先只表达**研究层语义**：

```python
class SignalCandidate(BaseModel):
    # 核心语义字段（Phase 4）
    candidate_id: str
    experiment_id: str
    model_artifact_id: str
    symbol: str
    timestamp: datetime
    score: float                       # 研究层预测分数
    direction_hint: Literal["long", "short", "neutral"] = "neutral"
    confidence: float                  # 置信度 0~1
    horizon: int                       # 预测周期
    
    # ★ Phase 4 禁止出现以下字段 ★
    # order_type:    ← 订单类型（属于执行层）
    # execution_algo: ← 执行算法（属于执行层）
    # position_size:  ← 仓位细节（属于执行层）
    # stop_loss:      ← 风控参数（属于仲裁层/执行层）
    # take_profit:    ← 风控参数（属于仲裁层/执行层）
```

执行层字段留到后续仲裁层/执行层阶段，不在研究层越界。

---

## A. Phase 4 文件树（完整版）

```
core/research/                          # 研究层根目录
├── __init__.py
├── base.py                            # IAlphaBuilder / IDatasetBuilder / IExperimentRegistry 抽象
├── models.py                          # 研究层核心 schema（不含 alpha）
│                                        # ExperimentRecord / ModelArtifact / DeploymentCandidate
│
├── alpha/                             # ★ ALPHA 因子体系
│   ├── __init__.py
│   ├── base.py                        # AlphaFactor 抽象基类
│   ├── models.py                      # AlphaFactorSpec / AlphaFactorValue / AlphaFactorSet
│   │                                    # / AlphaValidationResult / CompositeFactor
│   ├── registry.py                    # 因子注册表
│   │
│   ├── builders/                      # 因子构建器（按三层分类）
│   │   ├── __init__.py
│   │   ├── technical.py               # L1 原始技术 alpha
│   │   ├── fundamentals.py           # L1 原始基本面 alpha（简化占位）
│   │   ├── macro.py                   # L1 原始宏观 alpha（占位）
│   │   ├── sentiment.py               # L1 原始情绪 alpha（简化占位）
│   │   ├── orderflow.py              # L1 原始订单流 alpha（占位）
│   │   └── composite.py              # L3 组合 alpha
│   │
│   ├── normalization.py               # L2 标准化（winsorize / zscore / rank / neutralize）
│   ├── validation.py                  # AlphaValidationResult 可执行检查
│   └── export.py                      # AlphaFactorSet → Qlib FeatureSetVersion
│
├── datasets/
│   ├── __init__.py
│   ├── builder.py
│   ├── versioning.py                   # DatasetVersion 版本管理
│   ├── schemas.py                      # DatasetVersion schema
│   └── adapters.py
│
├── features/
│   ├── __init__.py
│   ├── base.py
│   ├── technical.py
│   ├── fundamentals.py
│   ├── macro.py
│   ├── sentiment.py
│   └── registry.py                     # FeatureSetVersion 注册表
│
├── labels/
│   ├── __init__.py
│   ├── base.py                         # LabelSetVersion schema
│   ├── returns.py
│   ├── direction.py
│   └── risk.py
│
├── qlib/
│   ├── __init__.py                     # init_qlib()
│   ├── availability.py
│   ├── config_builder.py
│   ├── workflow_runner.py
│   ├── model_adapter.py
│   ├── dataset_adapter.py
│   └── result_adapter.py
│
├── evaluation/
│   ├── __init__.py
│   ├── metrics.py
│   ├── ranking.py
│   └── reports.py
│
├── deployment/
│   ├── __init__.py
│   ├── candidates.py
│   └── signal_export.py
│
tests/unit/
├── test_research_models.py
├── test_dataset_versioning.py
├── test_feature_registry.py
├── test_label_builders.py
├── test_qlib_config_builder.py
├── test_result_adapter.py
├── test_alpha_models.py
├── test_alpha_registry.py
├── test_alpha_builders.py
├── test_alpha_normalization.py
├── test_alpha_validation.py
│
tests/integration/
├── test_qlib_init.py
├── test_baseline_workflow.py
├── test_experiment_registry.py
├── test_signal_export.py
└── test_alpha_lifecycle.py
│
docs/architecture/
├── research_architecture.md
├── qlib_integration.md
├── research_io_contract.md
├── phase4_acceptance.md
├── experiment_lifecycle.md
├── alpha_factor_architecture.md
└── alpha_factor_lifecycle.md
```

---

## B. Batch 1 实施顺序

### Batch 1 文件清单（9 个）

| 顺序 | 文件 | 职责 |
|:----:|------|------|
| A | `core/research/models.py` | 研究层核心 schema（ExperimentRecord / ModelArtifact / DeploymentCandidate / DatasetVersion / FeatureSetVersion / LabelSetVersion） |
| B | `core/research/alpha/models.py` | Alpha 因子体系 5 个 schema |
| C | `core/research/alpha/base.py` | AlphaFactor 抽象基类 |
| D | `core/research/alpha/registry.py` | 因子注册表（增/查/列表/搜索） |
| E | `core/research/datasets/versioning.py` | DatasetVersion 版本管理 |
| F | `core/research/features/registry.py` | FeatureSetVersion 注册表 |
| G | `core/research/labels/base.py` | LabelSetVersion schema |
| H | `docs/architecture/research_io_contract.md` | 研究层 IO 契约文档 |
| I | `docs/architecture/alpha_factor_architecture.md` | Alpha 因子架构文档 |

### Batch 1 验收项

Batch 1 完成后验收以下项目：
- [ ] `models.py` 所有 schema 可实例化、可序列化
- [ ] `alpha/models.py` 5 个 schema 完整（L1 原始值 + L2 标准化值 + L3 组合因子 + Validation + Spec）
- [ ] `alpha/base.py` AlphaFactor 抽象接口定义清晰
- [ ] `alpha/registry.py` 因子增/查/列表/搜索方法完整
- [ ] `datasets/versioning.py` DatasetVersion 可版本化
- [ ] `features/registry.py` FeatureSetVersion 可注册
- [ ] `labels/base.py` LabelSetVersion schema 完整
- [ ] `research_io_contract.md` 文档完整
- [ ] `alpha_factor_architecture.md` 文档完整（含三层区分说明）

---

## C. Alpha 三层对象划分

```
┌─────────────────────────────────────────────────────────┐
│                    L1: 原始 Alpha                        │
│  AlphaFactorSpec → AlphaFactorBuilder.build()           │
│  → AlphaFactorValue(raw_value=...)                      │
│  无任何处理，直接输出因子原始计算值                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                 L2: 标准化 Alpha                        │
│  AlphaNormalizer.apply(zscore/winsorize/rank)          │
│  → AlphaFactorValue(normalized_value=...)               │
│  在 L1 基础上做统计处理，不改变因子相对关系               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                 L3: 组合 Alpha                          │
│  CompositeAlphaBuilder.weighted/PCA/IC_weighted        │
│  → CompositeFactor(value=..., component_factors=...)    │
│  多因子组合输出单一信号，作为独立因子注册                 │
└─────────────────────────────────────────────────────────┘
```

三层各自有独立的 `factor_id` 和 `version`，独立参与 validation 和 export。

---

## D. 完整验收清单（Phase 4，含执行约束）

### 执行约束验收
| # | 约束项 | 验收标准 |
|---|--------|----------|
| C1 | Alpha 三层区分 | L1/L2/L3 各自独立 factor_id，不得混层 |
| C2 | 数据源约束 | Baseline alpha 不引入不稳定数据依赖 |
| C3 | Validation 可执行 | coverage/null_ratio/constant_ratio/outlier_ratio/correlation_warning/leakage_warning 可执行 |
| C4 | SignalCandidate 语义边界 | 不含 order_type / execution_algo / position_size 等执行层字段 |

### Alpha 因子体系（17 项）
A1-A17（见下方）

### 研究工厂核心（25 项）
R1-R25

### 合计：46 项验收

---

**请确认 Batch 1 顺序，我将开始实施 A→I。**
