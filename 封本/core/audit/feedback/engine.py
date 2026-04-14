"""FeedbackEngine — 扫描 AuditRecords，生成系统级 Feedback。"""
from __future__ import annotations

from datetime import datetime
from typing import List

from core.audit.schemas.decision_record import DecisionRecord
from core.audit.schemas.execution_record import ExecutionRecord
from core.audit.schemas.risk_audit import RiskAudit
from core.audit.feedback.slippage_calibration import SlippageCalibrationFeedback
from core.audit.feedback.signal_decay import SignalDecayFeedback
from core.audit.feedback.filter_pattern import FilterPatternFeedback
from core.audit.feedback.factor_attribution import FactorAttributionFeedback
from core.audit.schemas.feedback import Feedback


class FeedbackEngine:
    """
    扫描 AuditRecords，生成系统聚合反馈。

    四大 Feedback 类型：
    1. SlippageCalibration — 预估算 vs 实际滑点偏差
    2. SignalDecay — 信号年龄 vs realized_pnl 衰减分析
    3. FilterPattern — 风控过滤器 veto 率按 regime 分桶
    4. FactorAttribution — 因子模块 realized_pnl 归因

    使用方式：
        engine = FeedbackEngine()
        feedbacks = engine.scan(
            decision_records=[...],
            execution_records=[...],
            risk_audits=[...],
        )
    """

    def __init__(self) -> None:
        self.slippage_fb = SlippageCalibrationFeedback()
        self.signal_decay_fb = SignalDecayFeedback()
        self.filter_pattern_fb = FilterPatternFeedback()
        self.factor_attr_fb = FactorAttributionFeedback()

    def scan(
        self,
        decision_records: List[DecisionRecord],
        execution_records: List[ExecutionRecord],
        risk_audits: List[RiskAudit],
        *,
        scan_since: datetime | None = None,
    ) -> List[Feedback]:
        """
        扫描指定时间窗口内的 AuditRecords，生成所有类型的 Feedback。

        Args:
            decision_records: DecisionRecord 列表
            execution_records: ExecutionRecord 列表
            risk_audits: RiskAudit 列表
            scan_since: 只扫描此时间之后的记录（None = 全量扫描）

        Returns:
            Feedback[] — 所有生成的 feedback（未写入 registry）
        """
        if scan_since:
            drs = [r for r in decision_records if r.timestamp >= scan_since]
            ers = [r for r in execution_records if r.timestamp >= scan_since]
            ras = [r for r in risk_audits if r.timestamp >= scan_since]
        else:
            drs, ers, ras = decision_records, execution_records, risk_audits

        feedbacks: List[Feedback] = []

        # 1. Slippage Calibration — 按 symbol + order_type
        symbol_map: dict[str, list[ExecutionRecord]] = {}
        for rec in ers:
            symbol_map.setdefault(rec.symbol, []).append(rec)
        for symbol, recs in symbol_map.items():
            feedbacks.extend(self.slippage_fb.generate(recs, symbol))

        # 2. Signal Decay
        feedbacks.extend(self.signal_decay_fb.generate(drs))

        # 3. Filter Pattern
        feedbacks.extend(self.filter_pattern_fb.generate(ras))

        # 4. Factor Attribution
        feedbacks.extend(self.factor_attr_fb.generate(drs))

        return feedbacks
