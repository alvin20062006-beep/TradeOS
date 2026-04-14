# Phase 8 Lifecycle & Audit IO Contract

## 1. Phase 3 / 6 / 7 → Phase 8 输入映射

```
Phase 6: ArbitrationDecision
  │
  ├─ DecisionAuditor.ingest(decision)
  │   └─ SignalSnapshot[] ← 快照化 EngineSignal（解耦 Phase 6 原生对象）
  │
  └─ 输出: DecisionRecord
      ├─ input_signals: SignalSnapshot[]     ← 最小字段集
      ├─ bias / target_direction / target_quantity
      ├─ arbitration_confidence / stop_price
      └─ 事后追加: realized_pnl_pct / signal_age_hours / holding_period_hours

Phase 3: fill events[] + Phase 7 Evaluator pre/post-trade 结果
  │
  ├─ ExecutionAuditor.ingest(fills, evaluator_pre_result, evaluator_post_result)
  │   └─ FillSnapshot[] ← 快照化 Phase 3 Fill（解耦 Phase 3 原生对象）
  │
  └─ 输出: ExecutionRecord
      ├─ fills: FillSnapshot[]
      ├─ estimated vs realized slippage/impact
      ├─ fill_rate / avg_execution_price / arrival_price
      └─ execution_quality_score / quality_rating

Phase 7: PositionPlan (RiskEngine.calculate() 输出)
  │
  ├─ RiskAuditor.ingest(position_plan, regime, volatility_regime)
  │   └─ FilterCheckSnapshot[] ← 快照化 LimitCheck（解耦 Phase 7 原生对象）
  │
  └─ 输出: RiskAudit
      ├─ filter_results: FilterCheckSnapshot[]
      ├─ sizing_input_qty / final_quantity
      ├─ veto_triggered / veto_filters / total_adjustments / total_vetoes
      └─ regime / volatility_regime
```

### 快照化原则

Phase 8 不直接持有 Phase 3/6/7 的原生运行时对象。所有跨 Phase 边界的数据必须通过
快照化（Snapshot）转为可稳定序列化的 Pydantic model：

| 快照类型 | 原始对象来源 | 保留字段 |
|----------|-------------|----------|
| `SignalSnapshot` | Phase 6 EngineSignal | source_module, signal_type, direction, confidence, regime, score, metadata |
| `FillSnapshot` | Phase 3 Fill | slice_id, filled_qty, fill_price, fill_time, slippage_bps, is_leaving_qty |
| `FilterCheckSnapshot` | Phase 7 LimitCheck | filter_name, mode, passed, raw_qty, adjusted_qty, limit_value, actual_value, details |

---

## 2. Append-Only 审计写入流程

### 核心原则

1. **记录一旦写入不可修改、不可删除**
2. **只追加新记录**，通过 `correction_of` 字段引用旧记录来修正
3. **状态变更通过追加新记录表达**（不修改原记录的 status 字段）

### 写入流程

```
T+0: 交易执行
  │
  ├─ DecisionAuditor.ingest(arbitration_decision)
  │   → DecisionRecord → append audit/
  │
  ├─ ExecutionAuditor.ingest(fills, evaluator_result)
  │   → ExecutionRecord → append audit/
  │
  └─ RiskAuditor.ingest(position_plan)
      → RiskAudit → append audit/

T+N: FeedbackEngine.scan()
  │
  ├─ SlippageCalibrationFeedback.generate()
  ├─ SignalDecayFeedback.generate()
  ├─ FilterPatternFeedback.generate()
  └─ FactorAttributionFeedback.generate()
  │
  └─ Feedback[] → FeedbackRegistry.append_many()

T+N+1: 人工复核
  │
  ├─ FeedbackRegistry.mark_reviewed(fb_id, reviewer)
  │   → 追加 status=REVIEWED 的新记录（不修改原 PENDING 记录）
  │
  └─ FeedbackRegistry.mark_rejected(fb_id, reviewer, reason)
      → 追加 status=REJECTED 的新记录

T+N+2: Phase4Updater.process()
  │
  └─ 读取 read_unprocessed() → 生成 Phase4CandidateUpdate[]
      → 写入 staging 目录（不写 Phase 4 registry 真值）
```

### Append-Only 去重机制

由于原记录的 `status` 字段从不被修改，`read_unprocessed()` 和 `list_pending()`
通过扫描所有记录找出已 resolved 的 ID，排除原始 PENDING 记录：

```python
# FeedbackRegistry.read_unprocessed
resolved_ids = {fb.feedback_id for fb in all_fb if fb.status in (REVIEWED, REJECTED)}
return [fb for fb in all_fb if fb.feedback_id not in resolved_ids and fb.status == PENDING]

# ReviewManager.list_pending
completed_ids = {r.review_id.replace("-completed", "") for r in all_reviews if r.status == COMPLETED}
return [r for r in all_reviews if r.status == PENDING and r.review_id not in completed_ids]
```

---

## 3. Review 与 Feedback 的分层关系

### 职责边界

| 维度 | Review（人工复盘） | Feedback（系统反馈） |
|------|-------------------|---------------------|
| 生成者 | 人工填写 | FeedbackEngine 自动聚合 |
| 内容 | accuracy_score, verdict, notes, tags | metric_name, metric_value, threshold_breach, phase4_suggestion |
| 主观性 | 包含主观判断 | 纯量化统计 |
| 存储路径 | `~/.ai-trading-tool/audit/reviews/{decision\|execution}/` | `~/.ai-trading-tool/audit/feedback_registry/` |
| 状态机 | PENDING → IN_PROGRESS → COMPLETED / DISPUTED | PENDING → REVIEWED → APPLIED / REJECTED |
| 作用 | 事后复盘、个人判断记录 | 触发 Phase 4 候选更新 |

### 互不替代

- **Review 不能替代 Feedback**：Review 的 verdict/accuracy_score 是主观的，不直接触发 Phase 4 更新
- **Feedback 不能替代 Review**：Feedback 是量化统计，不含主观判断，不能替代人工复盘

### 生命周期交互

```
Feedback(PENDING) ──→ 人工复核 ──→ Feedback(REVIEWED) ──→ Phase4Updater.process()
                                                  └─→ candidate_update → Phase 4 确认
Review(PENDING)  ──→ 人工填写 ──→ Review(COMPLETED) ──→ 归档，供未来参考
```

---

## 4. FeedbackRegistry → Phase4Updater → candidate_update 生命周期

### 状态机

```
Feedback(PENDING)
    │
    ├─ mark_reviewed(fb_id, reviewer) → Feedback(REVIEWED)
    │   └─ Phase4Updater 可处理
    │
    ├─ mark_rejected(fb_id, reviewer, reason) → Feedback(REJECTED)
    │   └─ 不会进入 Phase4Updater
    │
    └─ Phase4Updater.process(registry)
        └─ 读 read_unprocessed()
           └─ 对每个 PENDING feedback 生成 Phase4CandidateUpdate
               ├─ suggestion: 人类可读建议
               ├─ flag: 标记（type / severity / 相关字段）
               └─ candidate_update: 候选变更结构
                   ├─ registry: 目标 Registry 名称
                   ├─ action: 建议动作
                   ├─ evidence: 量化证据
                   └─ status: "pending"（待 Phase 4 确认）
```

### 四类 Feedback 的回流目标

| FeedbackType | 回流目标 Registry | 建议动作 |
|---|---|---|
| `SLIPPAGE_CALIBRATION` | ExperimentRegistry | adjust slippage model params |
| `SIGNAL_DECAY` | LabelSetRegistry | shorten label window |
| `FILTER_PATTERN` | ModelRegistry | retrain / review_threshold |
| `FACTOR_ATTRIBUTION` | AlphaFactorRegistry | downweight / deprecate factor |

### 关键约束：不直接写真值

Phase4Updater **不直接修改** Phase 4 的 ExperimentRegistry / ModelRegistry / AlphaFactorRegistry 真值。
只输出 `candidate_update` 到 staging 目录，由 Phase 4 或人工确认后才正式应用。

```
Phase4Updater.process()
  → candidate_update (staging)
  → Phase 4 读取 staging
  → 人工确认
  → Phase 4 正式写入 registry
```

---

## 5. Phase 8 与 Phase 4 / Phase 3 的边界说明

### Phase 8 → Phase 4 边界

- Phase 8 **只输出建议**（candidate_update），不写真值
- Phase 4 拥有 registry 的唯一写入权
- candidate_update 的 `status` 必须经过 `pending → approved → applied` 状态机
- Phase 8 的 Feedback.confidence 是参考值，Phase 4 有权拒绝

### Phase 3 → Phase 8 边界

- Phase 8 通过 `FillSnapshot[]` 消费 Phase 3 的 fill 数据
- Phase 8 不依赖 Phase 3 的原生 Fill 类
- Phase 3 的执行结果通过 ExecutionAuditor 转换为 ExecutionRecord
- Phase 8 不向 Phase 3 反向输出任何数据

### Phase 6 → Phase 8 边界

- Phase 8 通过 `SignalSnapshot[]` 消费 Phase 6 的 EngineSignal
- Phase 8 不依赖 Phase 6 的原生 EngineSignal 类
- DecisionRecord 的事后评估字段（realized_pnl_pct 等）由 Phase 8 自行填充

### Phase 7 → Phase 8 边界

- Phase 8 通过 `FilterCheckSnapshot[]` 消费 Phase 7 的 LimitCheck
- Phase 8 不依赖 Phase 7 的原生 FilterResult / LimitCheck 类
- RiskAudit 的 regime/volatility_regime 由调用方提供（不依赖 Phase 7 内部状态）

---

## 6. 数据持久化路径

```
~/.ai-trading-tool/audit/
├── feedback_registry/
│   └── {YYYY-MM-DD}.jsonl         ← Feedback append-only
├── reviews/
│   ├── decision/
│   │   └── {YYYY-MM-DD}.jsonl     ← DecisionReview append-only
│   └── execution/
│       └── {YYYY-MM-DD}.jsonl     ← ExecutionReview append-only
└── phase4_candidates/
    └── {YYYY-MM-DD}.jsonl         ← Phase4CandidateUpdate staging
```
