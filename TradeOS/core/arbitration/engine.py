"""
Arbitration Engine
================

仲裁引擎主入口。

协调流程：
  SignalCollector → 规则链（5条） → DecisionMaker → ArbitrationDecision
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Type

from core.arbitration.conflict_resolver import ConflictResolver
from core.arbitration.decision_maker import DecisionMaker
from core.arbitration.schemas import (
    ArbitrationDecision,
    DecisionRationale,
    SignalBundle,
    SignalScore,
)

from core.arbitration.signal_collector import SignalCollector

from core.arbitration.rules.base import ArbitrationRule
from core.arbitration.rules.confidence_weight import ConfidenceWeightRule
from core.arbitration.rules.direction_conflict import DirectionConflictRule
from core.arbitration.rules.fundamental_veto import FundamentalVetoRule
from core.arbitration.rules.macro_adjustment import MacroAdjustmentRule
from core.arbitration.rules.regime_filter import RegimeFilterRule

if TYPE_CHECKING:
    from core.analysis.fundamental.report import FundamentalReport
    from core.schemas import (
        ChanSignal,
        MacroSignal,
        OrderFlowSignal,
        SentimentEvent,
        TechnicalSignal,
    )
    from core.strategy_pool.schemas.arbitration_input import ArbitrationInputBundle


class ArbitrationEngine:
    """
    仲裁引擎。

    主入口：arbitrate()
    全流程：收集信号 → 提取方向 → 评分 → 应用规则 → 生成决策
    """

    def __init__(self) -> None:
        self.collector = SignalCollector()
        self.maker = DecisionMaker()
        self._conflict_resolver = ConflictResolver()

        # 规则注册表（按 priority 排序）
        self._rules: List[ArbitrationRule] = [
            FundamentalVetoRule(),      # priority=1
            MacroAdjustmentRule(),       # priority=2
            DirectionConflictRule(),     # priority=3
            ConfidenceWeightRule(),      # priority=4
            RegimeFilterRule(),          # priority=5
        ]
        # 确保优先级顺序
        self._rules.sort(key=lambda r: r.priority)

    def arbitrate(
        self,
        symbol: str,
        timestamp: datetime | None = None,
        technical: Optional["TechnicalSignal"] = None,
        chan: Optional["ChanSignal"] = None,
        orderflow: Optional["OrderFlowSignal"] = None,
        sentiment: Optional["SentimentEvent"] = None,
        macro: Optional["MacroSignal"] = None,
        fundamental: Optional["FundamentalReport"] = None,
    ) -> ArbitrationDecision:
        """
        完整仲裁流程。

        Args:
            symbol:       标的代码
            timestamp:    统一时间戳
            technical:    技术分析信号
            chan:         缠论信号
            orderflow:    订单流信号
            sentiment:    情绪信号
            macro:       宏观信号
            fundamental:  基本盘报表

        Returns:
            ArbitrationDecision
        """
        start = time.perf_counter()

        # 1. 收集信号
        bundle = self.collector.collect(
            symbol=symbol,
            timestamp=timestamp,
            technical=technical,
            chan=chan,
            orderflow=orderflow,
            sentiment=sentiment,
            macro=macro,
            fundamental=fundamental,
        )

        # 2. 提取方向信号并评分
        from core.arbitration.scorers.signal_scorer import derive_direction_and_confidence, score_signal

        directional = derive_direction_and_confidence(bundle)
        scores: List[SignalScore] = [score_signal(ds) for ds in directional]

        # 3. 共用内部评估链
        return self._evaluate_and_decide(
            start=start,
            ts=bundle.timestamp,
            symbol=symbol,
            bundle=bundle,
            directional=directional,
            scores=scores,
        )

    @property
    def rules(self) -> List[ArbitrationRule]:
        """当前注册的规则列表（按优先级排序）。"""
        return self._rules

    # ─────────────────────────────────────────────────────
    # Phase 9 集成入口
    # ─────────────────────────────────────────────────────

    def arbitrate_portfolio(
        self,
        arb_in: "ArbitrationInputBundle",
        timestamp: datetime | None = None,
    ) -> ArbitrationDecision:
        """
        Phase 9 → Phase 6 集成入口。

        接收 StrategyPool 产出的 ArbitrationInputBundle，
        内部完全复用 SignalCollector → 5 规则链 → EnsembleScorer，
        产出正式的 ArbitrationDecision。

        职责边界：
        - arbitrate()       = 消费 Phase 5 信号链（主入口）
        - arbitrate_portfolio() = 消费 Phase 9 ArbitrationInputBundle（Phase 9 集成入口）
        - 两者最终调用同一个内部 _evaluate_and_decide()，零逻辑复制

        Phase 9 strategy_pool 信号（engine_name="strategy_pool:{strategy_id}"）
        参与现有 5 规则链，其中 FundamentalVetoRule / MacroAdjustmentRule
        作为 universal 规则可覆盖该信号。

        Args:
            arb_in:     Phase 9 ArbitrationInputBundle（含 PortfolioProposal）
            timestamp:  统一时间戳（默认从 arb_in 读取）

        Returns:
            ArbitrationDecision
        """
        from core.arbitration.schemas import _StrategySignalSource
        from core.arbitration.schemas import DirectionalSignal, SignalScore
        from core.arbitration.scorers.signal_scorer import derive_direction_and_confidence, score_signal

        start = time.perf_counter()
        ts = timestamp or arb_in.timestamp
        proposals = arb_in.portfolio_proposal.proposals

        # 1. 提取真实 symbol：优先从 StrategySignalBundle.bundles 提取，其次从 portfolio_id 解析
        bundle_symbol: str = "UNKNOWN"
        if proposals:
            for p in proposals:
                if p.bundles and p.bundles[0].symbol:
                    bundle_symbol = p.bundles[0].symbol
                    break
        if bundle_symbol == "UNKNOWN" and arb_in.portfolio_proposal.portfolio_id:
            bundle_symbol = arb_in.portfolio_proposal.portfolio_id.split("-")[0]

        # 2. 收集 Phase 5 信号（通常为空，Phase 9 独立运行时 bundle.symbol 即为真实 symbol）
        bundle = self.collector.collect(
            symbol=bundle_symbol,
            timestamp=ts,
        )

        # 3. 提取 Phase 5 方向信号
        directional: List[DirectionalSignal] = derive_direction_and_confidence(bundle)

        # 4. 转换 Phase 9 策略信号并追加
        strategy_sources: List[_StrategySignalSource] = [
            _StrategySignalSource(
                proposal_id=p.proposal_id,
                strategy_id=p.strategy_id,
                aggregate_direction=p.aggregate_direction,
                aggregate_strength=p.aggregate_strength,
                aggregate_confidence=p.aggregate_confidence,
                portfolio_weight=p.portfolio_weight,
            )
            for p in proposals
        ]
        for src in strategy_sources:
            directional.append(src.to_directional())

        # 5. 早退出：既无 Phase 5 信号也无 Phase 9 策略
        if not directional:
            return ArbitrationDecision(
                decision_id=f"arb-portfolio-{arb_in.portfolio_proposal.portfolio_id}-{int(start * 1000)}",
                timestamp=ts,
                symbol=bundle_symbol,
                bias="no_trade",
                confidence=0.0,
                signal_count=0,
                arbitration_latency_ms=(time.perf_counter() - start) * 1000,
            )

        # 6. 评分 → 共用内部评估链
        scores: List[SignalScore] = [score_signal(ds) for ds in directional]
        return self._evaluate_and_decide(
            start=start,
            ts=ts,
            symbol=bundle_symbol,
            bundle=bundle,
            directional=directional,
            scores=scores,
        )

    # ─────────────────────────────────────────────────────
    # 内部共享评估链（供两个入口共同调用）
    # ─────────────────────────────────────────────────────

    def _evaluate_and_decide(
        self,
        start: float,
        ts: datetime,
        symbol: str,
        bundle: "SignalBundle",
        directional: List["DirectionalSignal"],
        scores: List["SignalScore"],
    ) -> ArbitrationDecision:
        """
        内部共享评估链。

        被 arbitrate() 和 arbitrate_portfolio() 共同调用：
        - 从 SignalBundle + DirectionalSignal[] 开始
        - 应用 5 规则链
        - 返回正式 ArbitrationDecision
        """
        from core.arbitration.scorers.ensemble_scorer import EnsembleScorer

        signal_count = len(directional)

        # 1. 生成初始决策
        decision = ArbitrationDecision(
            decision_id=f"arb-{symbol}-{int(start * 1000)}",
            timestamp=ts,
            symbol=symbol,
            bias="no_trade",
            confidence=0.0,
            signal_count=signal_count,
        )

        # 2. 按优先级应用规则链
        for rule in self._rules:
            rule.evaluate(bundle, scores, decision)

        # 3. 集成评分（更新 bias / scores / confidence）
        EnsembleScorer().aggregate(scores, decision)

        # 4. 构建理由链
        decision.rationale = [
            DecisionRationale(
                signal_name=s.engine_name,
                direction=s.direction,
                confidence=s.raw_confidence,
                weight=s.weight,
                contribution=s.contribution,
                rule_adjustments=s.rule_adjustments,
            )
            for s in scores
        ]

        # 5. 记录延迟
        decision.arbitration_latency_ms = (time.perf_counter() - start) * 1000

        return decision
