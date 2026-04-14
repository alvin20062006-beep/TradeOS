# Research IO Contract
## Phase 4 Research Factory - Object Schemas & Contracts

This document defines the internal research objects and their contracts.
Qlib-native objects must NEVER be exposed outside the qlib/ sub-package.

---

## Schema Summary

| Object | Location | Description |
|--------|----------|-------------|
| `DatasetVersion` | `core/research/models.py` | Dataset snapshot for reproducibility |
| `FeatureSetVersion` | `core/research/models.py` | Feature set snapshot |
| `LabelSetVersion` | `core/research/models.py` | Label set snapshot |
| `ExperimentRecord` | `core/research/models.py` | Full experiment run record |
| `ModelArtifact` | `core/research/models.py` | Trained model artifact |
| `SignalCandidate` | `core/research/models.py` | Research-layer signal (export to arbitration) |
| `DeploymentCandidate` | `core/research/models.py` | Deployment-ready model snapshot |
| `AlphaFactorSpec` | `core/research/alpha/models.py` | Alpha factor definition metadata |
| `AlphaFactorValue` | `core/research/alpha/models.py` | Per-symbol-timestamp factor values (raw + normalized) |
| `AlphaFactorSet` | `core/research/alpha/models.py` | Curated factor set with pre-processing config |
| `AlphaValidationResult` | `core/research/alpha/models.py` | Executable quality check results |
| `CompositeFactor` | `core/research/alpha/models.py` | L3 multi-factor combination |

---

## Field Constraints

### SignalCandidate (Phase 4 Scope)
**Allowed fields (research semantics):**
- `candidate_id`, `experiment_id`, `model_artifact_id`
- `symbol`, `timestamp`
- `score`, `score_normalized`
- `direction_hint` (long / short / neutral)
- `confidence` (0.0 ~ 1.0)
- `horizon`
- `feature_snapshot` (optional)

**Forbidden in Phase 4 (execution-layer fields):**
- ❌ `order_type` (belongs to execution layer)
- ❌ `execution_algo` (belongs to execution layer)
- ❌ `position_size` (belongs to execution layer)
- ❌ `stop_loss` / `take_profit` (belong to arbitration/execution)

---

## Layer Contract (Alpha Factor System)

### Layer 1: Raw Alpha
- Object: `AlphaFactorValue.raw_value`
- State: Unprocessed computed factor values
- Layer tag: `"L1"`
- Independent `factor_id`

### Layer 2: Normalized Alpha
- Object: `AlphaFactorValue.normalized_value`
- State: After winsorize / zscore / rank / neutralize
- Layer tag: `"L2"`
- Independent `factor_id` (derived from L1 parent)

### Layer 3: Composite Alpha
- Object: `CompositeFactor`
- State: Multi-factor combination (weighted / PCA / IC-weighted)
- Layer tag: `"L3"`
- Independent `factor_id`

Each layer: independent registration, independent versioning.

---

## Validation Thresholds

| Check | Threshold | Pass Condition |
|-------|-----------|----------------|
| `coverage` | > 0.9 | 90% non-null values |
| `null_ratio` | < 0.1 | < 10% null values |
| `constant_ratio` | < 0.05 | < 5% constant values |
| `outlier_ratio` | < 0.05 | < 5% extreme values |
| `correlation_warning` | boolean | No > 0.9 correlation with existing factors |
| `leakage_warning` | boolean | Contemporaneous IC not suspiciously high |

---

## Data Flow

```
DataStore (core/data/)
        ↓
DatasetBuilder.build() → DatasetVersion
        ↓
AlphaFactorBuilder.compute() → AlphaFactorValue (L1 raw)
        ↓
AlphaNormalizer.apply() → AlphaFactorValue (L2 normalized)
        ↓
AlphaValidator.validate() → AlphaValidationResult
        ↓
AlphaFactorSet.assemble() → AlphaFactorSet
        ↓
AlphaExporter.to_feature_set_version() → FeatureSetVersion
        ↓
Qlib Workflow (dataset + FeatureSet + LabelSet)
        ↓
ResultAdapter → ExperimentRecord + ModelArtifact + SignalCandidate
        ↓
Arbitration Layer (SignalCandidate)
```

---

## Versioning Rules

- All versioned objects use **semver**: `MAJOR.MINOR.PATCH`
- `MAJOR`: breaking changes (e.g., formula change)
- `MINOR`: new factors / parameters added
- `PATCH`: bug fixes / metadata updates
- Each build produces a new `PATCH` version
- `bump_version()` increments `MINOR` for new feature builds
- Registry stores: `index.json` + `{id}_{version}.json`

---

## Storage Locations

| Registry | Default Location |
|----------|-----------------|
| Dataset | `~/.ai-trading-tool/dataset_registry/` |
| Feature | `~/.ai-trading-tool/feature_registry/` |
| Alpha | `~/.ai-trading-tool/alpha_registry/` |
| Experiment | `~/.ai-trading-tool/experiment_registry/` |

All configurable via environment variables:
- `AI_TRADING_TOOL_DATASET_REGISTRY_DIR`
- `AI_TRADING_TOOL_FEATURE_REGISTRY_DIR`
- `AI_TRADING_TOOL_ALPHA_REGISTRY_DIR`
- `AI_TRADING_TOOL_EXPERIMENT_REGISTRY_DIR`
