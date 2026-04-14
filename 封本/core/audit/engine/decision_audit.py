"""DecisionAuditor — Phase 6 仲裁决策 → DecisionRecord。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from core.audit.schemas.decision_record import DecisionRecord, SignalSnapshot


class DecisionAuditor:
    """
    将 Phase 6 ArbitrationDecision 转换为 Phase 8 DecisionRecord。

    职责：
    1. 快照化 EngineSignal → SignalSnapshot[]（避免耦合 Phase 6 原生对象）
    2. 提取决策参数
    3. 生成 DecisionRecord

    使用方式：
        auditor = DecisionAuditor()
        decision_record = auditor.ingest(arbitration_decision)
    """

    def ingest(
        self,
        decision,
        *,
        realized_pnl_pct: Optional[float] = None,
        signal_age_hours: Optional[float] = None,
        holding_period_hours: Optional[float] = None,
        entry_price: Optional[float] = None,
        exit_price: Optional[float] = None,
    ) -> DecisionRecord:
        """
        将 ArbitrationDecision 转换为 DecisionRecord。

        Args:
            decision: Phase 6 ArbitrationDecision 对象
            realized_pnl_pct: 事后追加的开仓→平仓收益
            signal_age_hours: 信号从生成到开仓的时长
            holding_period_hours: 持仓时长（开仓→平仓）
            entry_price: 开仓价（事后填入）
            exit_price: 平仓价（事后填入）
        """
        input_signals = self._snapshot_signals(decision)

        return DecisionRecord(
            audit_id=f"dr-{uuid4().hex[:12]}",
            timestamp=datetime.utcnow(),
            source_phase="Phase 6",
            symbol=getattr(decision, "symbol", ""),
            decision_id=getattr(decision, "decision_id", ""),
            input_signals=input_signals,
            final_confidence=getattr(decision, "confidence", 0.0),
            bias=getattr(decision, "bias", "no_trade"),
            target_direction=str(getattr(decision, "target_direction", "FLAT")),
            target_quantity=getattr(decision, "target_quantity", 0.0),
            stop_price=getattr(decision, "stop_price", None),
            arbitration_confidence=getattr(decision, "confidence", 0.0),
            no_trade_reason=getattr(decision, "no_trade_reason", None),
            # 事后评估字段
            realized_pnl_pct=realized_pnl_pct,
            signal_age_hours=signal_age_hours,
            holding_period_hours=holding_period_hours,
            entry_price=entry_price,
            exit_price=exit_price,
        )

    def _snapshot_signals(self, decision) -> List[SignalSnapshot]:
        """快照化 EngineSignal[] → SignalSnapshot[]。"""
        raw_signals = getattr(decision, "source_signals", []) or []
        if hasattr(decision, "signals"):
            raw_signals = decision.signals or []

        snapshots = []
        for sig in raw_signals:
            if isinstance(sig, dict):
                snapshots.append(SignalSnapshot.from_signal(sig))
            else:
                # 对象形式
                snapshots.append(
                    SignalSnapshot(
                        source_module=getattr(sig, "module", getattr(sig, "source_module", "unknown")),
                        signal_type=getattr(sig, "signal_type", getattr(sig, "type", "unknown")),
                        direction=getattr(sig, "direction", "NEUTRAL"),
                        confidence=getattr(sig, "confidence", 0.0),
                        regime=getattr(sig, "regime"),
                        score=getattr(sig, "score"),
                        metadata=getattr(sig, "metadata", {}),
                    )
                )
        return snapshots
