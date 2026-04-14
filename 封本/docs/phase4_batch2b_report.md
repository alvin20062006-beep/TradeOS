# Phase 4 Batch 2B 完成报告
> 生成时间：2026-04-08 15:23 GMT+10
> 测试结果：37 passed, 1 warning

## 验收结果

| # | 验收项 | 状态 |
|---|--------|------|
| B1 | build_metadata_only / build_from_csv_dir 输出正确 DatasetVersion | ✅ |
| B2 | build_from_csv_dir 自动探测 symbols 和 date range | ✅ |
| B3 | Registry CRUD（register/get/list_versions/list_all） | ✅ |
| B4 | to_handler_kwargs() 输出有效 kwargs | ✅ |
| B5 | to_csv_path() 输出 CSV 目录 | ✅ |
| B6 | from_dataset_version() 正确转发 | ✅ |
| T1 | 10 个技术因子从 OHLCV DataFrame 计算 | ✅ |
| T2 | build_all_technical() 返回 dict of DataFrames | ✅ |
| T3 | 缺失列抛出 ValueError | ✅ |
| F1 | PE_RANK/PB_RANK/ROE_TTM 从基本面 DataFrame 计算 | ✅ |
| S1 | VOL_SURPRISE 从成交量计算 | ✅ |
| S2 | 缺 volume 列时抛出错误 | ✅ |
| C1 | equal_weight / rank_average 输出 composite_value | ✅ |
| C2 | ic_weighted 需 label；unknown method 报错 | ✅ |
| C3 | 空 factor_dict 抛出 ValueError | ✅ |
| C4 | build_composite() factory 支持三种方法 | ✅ |
| P1 | 完整链路 adapter→builder→exporter→workflow_runner | ✅ |

## 新增文件

```
core/research/qlib/dataset_adapter.py          13.4KB
core/research/datasets/builder.py              10.6KB
core/research/alpha/builders/__init__.py         1.3KB
core/research/alpha/builders/technical.py       11.4KB
core/research/alpha/builders/fundamentals.py     6.3KB
core/research/alpha/builders/sentiment.py        3.2KB
core/research/alpha/builders/composite.py        7.7KB
tests/unit/test_dataset_builder.py               8.3KB
tests/unit/test_alpha_builders.py               13.3KB
tests/integration/test_alpha_pipeline.py        9.0KB
```
共 9 新文件 + 3 更新文件

## Baseline Alpha 清单（17 个）

| ID | 因子名 | 类别 | 层 | 数据要求 |
|----|--------|------|-----|----------|
| T01 | RET_1d | 技术 | L1 | close |
| T02 | RET_5d | 技术 | L1 | close |
| T03 | VOL_5d | 技术 | L1 | close |
| T04 | VOL_20d | 技术 | L1 | close |
| T05 | RSI_14 | 技术 | L1 | close |
| T06 | MACD | 技术 | L1 | close |
| T07 | BB_WIDTH | 技术 | L1 | close |
| T08 | BB_POS | 技术 | L1 | close |
| T09 | VOL_RATIO | 技术 | L1 | volume |
| T10 | OBV_DIR | 技术 | L1 | close, volume |
| F01 | PE_RANK | 基本面 | L1 | pe_ratio |
| F02 | PB_RANK | 基本面 | L1 | pb_ratio |
| F03 | ROE_TTM | 基本面 | L1 | net_income |
| S01 | VOL_SURPRISE | 情绪代理 | L1 | volume |
| C01 | COMPOSITE_EQ | 组合 | L3 | L1 输出 |
| C02 | COMPOSITE_IC | 组合 | L3 | L1 + label |
| C03 | COMPOSITE_RANK | 组合 | L3 | L1 输出 |

## Dataset Spec 转换路径

```
DatasetVersion
  → QlibDatasetAdapter.from_dataset_version()
  → handler_kwargs { symbols, fields, freq, provider }
  → qlib.init() + D.features()
```

## 约束合规

- ✅ dataset_adapter 最小转换（只实现 handler_kwargs / csv_path / dataframe）
- ✅ builder 不实现数据下载（只从 CSV/Parquet/元数据组装）
- ✅ 优先稳定 baseline（10 技术 + 3 基本面 + 1 情绪代理）
- ✅ pipeline 最小链路终点（停在 workflow_runner.start/log_metrics/stop）

## 已知警告（非失败）

- MLflow filesystem backend 将在 2026-02 后废弃
- 后续应迁移到 sqlite:///mlflow.db
