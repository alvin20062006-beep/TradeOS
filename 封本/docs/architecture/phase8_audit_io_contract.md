# Phase 8 Audit IO Contract

## 总则

1. 所有审计对象继承 `AuditRecord`（append-only 基类）
2. 跨 Phase 边界的数据必须通过 Snapshot 快照化，不持有原生运行时对象
3. Review（人工）与 Feedback（系统）完全独立，互不替代
4. Phase4Updater 不直接写真值，只输出 candidate_update

---

## 1. AuditRecord（顶层基类）

| 维度 | 说明 |
|------|------|
| **输入来源** | 无直接输入（抽象基类） |
| **关键字段** | `audit_id: str`（UUID）、`timestamp: datetime`（UTC）、`source_phase: str`、`symbol: str`、`decision_id: str` |
| **输出去向** | 被 DecisionRecord / ExecutionRecord / RiskAudit 继承 |
| **append-only** | ✅ 是 — 一旦写入不可修改 |
| **允许改写真值** | ❌ 否 — 错误通过 `correction_of` 字段追加新记录修正 |

---

## 2. DecisionRecord

| 维度 | 说明 |
|------|------|
| **输入来源** | Phase 6 ArbitrationDecision → `DecisionAuditor.ingest()` |
| **关键字段** | `input_signals: SignalSnapshot[]`、`bias: str`、`target_direction: str`、`target_quantity: float`、`arbitration_confidence: float`、`realized_pnl_pct: float?`（事后追加）、`signal_age_hours: float?`、`holding_period_hours: float?`、`entry_price: float?`、`exit_price: float?` |
| **输出去向** | FeedbackEngine（signal_decay + factor_attribution 的数据源）、DecisionReviewManager（人工复盘对象） |
| **append-only** | ✅ 是 |
| **允许改写真值** | ❌ 否 — 事后评估字段通过新记录追加，不修改原记录的 `realized_pnl_pct` |

### SignalSnapshot（解耦 Phase 6）

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_module` | `str` | technical / fundamental / chan / macro / sentiment / orderflow |
| `signal_type` | `str` | breakout / trend_up / divergence 等 |
| `direction` | `str` | LONG / SHORT / NEUTRAL |
| `confidence` | `float` | 0-1 |
| `regime` | `str?` | 市场状态 |
| `score` | `float?` | 信号评分 |
| `metadata` | `dict` | 可扩展，不强耦合 |

---

## 3. ExecutionRecord

| 维度 | 说明 |
|------|------|
| **输入来源** | Phase 3 fill events + Phase 7 Evaluator 结果 → `ExecutionAuditor.ingest()` |
| **关键字段** | `fills: FillSnapshot[]`、`estimated_slippage_bps: float`、`realized_slippage_bps: float`、`estimated_impact_bps: float`、`realized_impact_bps: float`、`fill_rate: float`、`avg_execution_price: float`、`arrival_price: float`、`execution_quality_score: float`、`quality_rating: ExecutionQuality` |
| **输出去向** | FeedbackEngine（slippage_calibration 的数据源）、ExecutionReviewManager（人工复盘对象） |
| **append-only** | ✅ 是 |
| **允许改写真值** | ❌ 否 |

### FillSnapshot（解耦 Phase 3）

| 字段 | 类型 | 说明 |
|------|------|------|
| `slice_id` | `str` | 分片 ID |
| `filled_qty` | `float` | 成交数量 |
| `fill_price` | `float` | 成交价 |
| `fill_time` | `datetime` | 成交时间 |
| `slippage_bps` | `float` | 相对 arrival_price 的滑点 |
| `is_leaving_qty` | `bool` | 是否遗留未成交 |

---

## 4. RiskAudit

| 维度 | 说明 |
|------|------|
| **输入来源** | Phase 7 PositionPlan → `RiskAuditor.ingest()` |
| **关键字段** | `filter_results: FilterCheckSnapshot[]`、`sizing_input_qty: float`、`final_quantity: float`、`veto_triggered: bool`、`veto_filters: List[str]`、`total_adjustments: int`、`total_vetoes: int`、`regime: str?`、`volatility_regime: str?` |
| **输出去向** | FeedbackEngine（filter_pattern 的数据源） |
| **append-only** | ✅ 是 |
| **允许改写真值** | ❌ 否 |

### FilterCheckSnapshot（解耦 Phase 7）

| 字段 | 类型 | 说明 |
|------|------|------|
| `filter_name` | `str` | 过滤器名称 |
| `mode` | `str` | pass / cap / veto |
| `passed` | `bool` | 是否通过 |
| `raw_qty` | `float` | 进入过滤器的原始数量 |
| `adjusted_qty` | `float` | 调整后数量（可为 0，无 ge 约束） |
| `limit_value` | `float?` | 触发限额的阈值 |
| `actual_value` | `float?` | 实际值（可为负，如 loss_limit） |
| `details` | `str` | 人类可读说明 |

---

## 5. Review（人工复盘）

| 维度 | 说明 |
|------|------|
| **输入来源** | 人工创建 → `DecisionReviewManager.create()` / `ExecutionReviewManager.create()` |
| **关键字段** | `review_id: str`、`audit_id: str`、`review_type: "decision" \| "execution"`、`accuracy_score: float`（0-1）、`verdict: "correct" \| "incorrect" \| "lucky" \| "unlucky" \| "inconclusive"`、`notes: str`、`tags: List[str]`、`status: ReviewStatus` |
| **输出去向** | 归档，供未来参考。不直接触发 Phase 4 更新 |
| **append-only** | ✅ 是 — complete() 追加新记录（`{review_id}-completed`），不修改原 PENDING 记录 |
| **允许改写真值** | ❌ 否 — 原记录 status 从不改变，去重通过扫描 completed_ids 实现 |

### Review 状态机

```
PENDING → IN_PROGRESS → COMPLETED
                     ↘ DISPUTED
```

### Review 与 Feedback 的边界

- Review 由人工填写，包含主观评分（accuracy_score / verdict / notes）
- Feedback 由系统自动聚合，不含主观评分
- Review 不触发 Phase 4 更新，Feedback 通过 Phase4Updater 触发候选更新
- 两者存储在不同路径，不同 schema，互不替代

---

## 6. Feedback（系统聚合反馈）

| 维度 | 说明 |
|------|------|
| **输入来源** | FeedbackEngine.scan() 自动生成（基于 AuditRecords 量化统计） |
| **关键字段** | `feedback_id: str`、`feedback_type: FeedbackType`、`severity: "low" \| "medium" \| "high"`、`sample_size: int`、`evidence: Dict`、`metric_name: str`、`metric_value: float`、`threshold_breach: bool`、`suggested_action: str`、`phase4_suggestion: Dict`、`status: FeedbackStatus` |
| **输出去向** | FeedbackRegistry → Phase4Updater → candidate_update → Phase 4 staging |
| **append-only** | ✅ 是 — mark_reviewed/mark_rejected 追加新记录，不修改原 PENDING |
| **允许改写真值** | ❌ 否 — Phase4Updater 只输出 candidate_update，不直接写 Phase 4 registry |

### Feedback 状态机

```
PENDING → REVIEWED → APPLIED（Phase 4 确认后）
                  ↘ REJECTED（附 rejection_reason）
```

### 四类 Feedback 的触发条件

| FeedbackType | 触发条件 | 回流目标 |
|---|---|---|
| `SLIPPAGE_CALIBRATION` | \|estimated - realized\| > 5bps（high）或 > 2bps（medium），n ≥ 20 | ExperimentRegistry |
| `SIGNAL_DECAY` | 某 age_bucket 的 mean_pnl < 0，n ≥ 10（high）或 ≥ 5（medium） | LabelSetRegistry |
| `FILTER_PATTERN` | veto_rate > 30%（high）或 > 20%（medium），n ≥ 20（high）或 ≥ 10（medium） | ModelRegistry |
| `FACTOR_ATTRIBUTION` | IR < 0（high，n ≥ 50）或 < 0.3（medium，n ≥ 30） | AlphaFactorRegistry |

---

## IO Contract 总表

| 对象 | 输入来源 | 输出去向 | append-only | 允许写真值 |
|------|---------|---------|:-----------:|:----------:|
| AuditRecord | 抽象基类 | 被继承 | ✅ | ❌ |
| DecisionRecord | Phase 6 → DecisionAuditor | FeedbackEngine / ReviewManager | ✅ | ❌ |
| SignalSnapshot | Phase 6 EngineSignal | DecisionRecord.input_signals | ✅ | ❌ |
| ExecutionRecord | Phase 3 fills → ExecutionAuditor | FeedbackEngine / ReviewManager | ✅ | ❌ |
| FillSnapshot | Phase 3 Fill | ExecutionRecord.fills | ✅ | ❌ |
| RiskAudit | Phase 7 PositionPlan → RiskAuditor | FeedbackEngine | ✅ | ❌ |
| FilterCheckSnapshot | Phase 7 LimitCheck | RiskAudit.filter_results | ✅ | ❌ |
| Review | 人工创建 | 归档 | ✅ | ❌ |
| Feedback | FeedbackEngine.scan() | FeedbackRegistry → Phase4Updater | ✅ | ❌ |
| Phase4CandidateUpdate | Phase4Updater.process() | Phase 4 staging | ✅ | ❌ |
