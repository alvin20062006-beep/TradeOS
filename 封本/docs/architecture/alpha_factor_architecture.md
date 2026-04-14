# Alpha Factor Architecture
## Phase 4 - Alpha Factor System Design

---

## System Position

```
┌────────────────────────────────────────────────────────────┐
│                    RESEARCH FACTORY (Phase 4)                │
│                                                            │
│  ┌──────────────┐    ┌────────────────┐    ┌───────────┐ │
│  │ Six Analysis │───→│  ALPHA LAYER   │───→│ Qlib Rsch │ │
│  │   Modules    │    │ (standardized) │    │  Factory  │ │
│  │(existing code)│    │  versioned)    │    │           │ │
│  └──────────────┘    └────────────────┘    └───────────┘ │
│                                                            │
│  Alpha layer responsibilities:                             │
│  • Receive raw candidate signals                           │
│  • Standardize into AlphaFactorSpec                        │
│  • Version management                                      │
│  • L1/L2/L3 layer distinction                             │
│  • Quality validation                                     │
│  • Export to Qlib FeatureSetVersion                        │
└────────────────────────────────────────────────────────────┘
```

---

## Three-Layer Design

### Layer 1: Raw Alpha
- **Output**: `AlphaFactorValue.raw_value`
- **State**: Direct computed factor value, no processing
- **Layer tag**: `"L1"`
- **Registration**: Each raw factor has independent `factor_id`
- **Example**: `RSI(close, period=14)` raw computed value

### Layer 2: Normalized Alpha
- **Output**: `AlphaFactorValue.normalized_value`
- **State**: After statistical processing (winsorize / zscore / rank / neutralize)
- **Layer tag**: `"L2"`
- **Registration**: Independent `factor_id` (derived from L1 parent via `parent_factor_id`)
- **Example**: `zscore(RSI_14)` over cross-sectional window

### Layer 3: Composite Alpha
- **Output**: `CompositeFactor` (single signal from multi-factor combination)
- **State**: Weighted / PCA / IC-weighted combination of L1/L2 factors
- **Layer tag**: `"L3"`
- **Registration**: Independent `factor_id`, owns `component_factor_ids` + `weights`
- **Example**: `0.4 * RET_20D_zscore + 0.3 * RSI_14_zscore + 0.3 * VOL_20D_zscore`

---

## Alpha Object Hierarchy

```
AlphaFactorSpec          # Definition metadata (what the factor is)
    │
    ├── factor_id       # Unique ID
    ├── factor_name     # Human-readable name
    ├── layer           # L1 / L2 / L3
    ├── parent_factor_id # For L2/L3 derived from L1
    └── parameters      # Factor-specific parameters

AlphaFactorValue         # Instance value per symbol-timestamp
    │
    ├── factor_id       # Links to AlphaFactorSpec
    ├── symbol
    ├── timestamp
    ├── raw_value        # L1
    ├── normalized_value  # L2
    └── is_valid         # Quality flag

AlphaFactorSet           # Collection of factors with pre-processing
    │
    ├── factor_set_id
    ├── factor_ids       # List of AlphaFactorSpec IDs
    ├── normalization_method
    ├── neutralization_method
    ├── coverage_summary  # Per-factor coverage rates
    └── ic_summary       # Per-factor IC values

AlphaValidationResult     # Quality check output
    │
    ├── coverage         # > 0.9
    ├── null_ratio       # < 0.1
    ├── constant_ratio   # < 0.05
    ├── outlier_ratio    # < 0.05
    ├── correlation_warning
    ├── leakage_warning
    └── is_qualified

CompositeFactor           # L3 multi-factor combination
    │
    ├── factor_id        # Independent ID
    ├── component_factor_ids
    ├── weights
    └── combination_method
```

---

## Alpha Builders

### Technical Builders (L1)
| Builder | Output | Input Fields |
|---------|--------|--------------|
| `MomentumReturnBuilder(period=N)` | RET_ND | close |
| `VolatilityBuilder(period=N)` | VOL_ND | close |
| `RSIBuilder(period=N)` | RSI_N | close |
| `MACDBuilder(fast, slow, signal)` | MACD | close |
| `BollingerBuilder(period=N)` | BB_WIDTH, BB_POS | close |
| `VolumeRatioBuilder(period=N)` | VOL_RATIO | close, volume |
| `OBVBuilder()` | OBV_DIR | close, volume |

### Fundamentals Builders (L1 - Simplified)
| Builder | Output | Input Fields |
|---------|--------|--------------|
| `PERatioBuilder()` | PE_RANK | fundamentals.pe |
| `PBRatioBuilder()` | PB_RANK | fundamentals.pb |
| `ROEBuilder()` | ROE_TTM | fundamentals.roe |

### Composite Builders (L3)
| Builder | Method | Description |
|---------|--------|-------------|
| `WeightedCompositeBuilder(weights)` | weighted | Fixed-weight combination |
| `PCACompositeBuilder(n_components)` | pca | PCA-based combination |
| `ICWeightedCompositeBuilder()` | ic_weighted | IC-weighted combination |

---

## Normalization Methods

| Method | Description | Use Case |
|--------|-------------|-----------|
| `winsorize` | Clip values at 1st/99th percentile | Remove extreme outliers |
| `zscore` | `(x - mean) / std` cross-sectionally | Standardize distributions |
| `rank` | Cross-sectional percentile rank 0~1 | Remove distribution dependency |
| `neutralize` | Residual after regressing on market/sector | Remove market exposure |

---

## Validation Checks

Each check is an **executable computation** (not a schema placeholder):

| Check | Formula | Threshold |
|-------|---------|-----------|
| `coverage` | `valid_count / total` | > 0.9 |
| `null_ratio` | `null_count / total` | < 0.1 |
| `constant_ratio` | `mean(series == series[0])` | < 0.05 |
| `outlier_ratio` | `mean(\|z_score\| > 3)` | < 0.05 |
| `correlation_warning` | `\|IC_existing\| > 0.9` | boolean |
| `leakage_warning` | `\|IC(label, factor)\| > 0.5` | boolean |

---

## Alpha → Qlib Export

```
AlphaFactorSet (factor_ids, normalization_method, neutralization_method)
        ↓
AlphaExporter.to_feature_set_version()
        ↓
FeatureSetVersion (feature_names, feature_groups, version)
        ↓
Qlib Alpha158 format
        ↓
Qlib Workflow (dataset + FeatureSet + LabelSet)
        ↓
Training → Backtest → Evaluation
```

---

## Registry Layout

```
~/.ai-trading-tool/alpha_registry/
├── factors/
│   ├── {factor_id}.json         # AlphaFactorSpec
│   └── ...
├── sets/
│   ├── {factor_set_id}.json     # AlphaFactorSet
│   └── ...
└── index.json                    # name → factor_id lookup
```

---

## Constraints

1. **Three layers must be distinct**: Each layer has its own `factor_id`, versions are independent.
2. **Baseline data sources**: Use only stable fields currently available from data layer (bars, volume, existing indicators, current fundamental fields).
3. **Validation must be executable**: All 6 checks must compute real values.
4. **No execution-layer fields in SignalCandidate**: No order_type / execution_algo / position_size in research-layer exports.
