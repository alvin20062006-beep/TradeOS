"""
RiskEngine — Phase 7 核心入口
==============================

唯一对外入口：RiskEngine.calculate()

链路：
  ArbitrationDecision
    ├─ bias = no_trade / exit / reduce → PositionPlan(quantity=0)
    └─ bias = long / short
          →
          ① sizing（6种算法优先级链）
          ② filters（7种：PositionLimit/LossLimit/DrawdownLimit/CorrelationLimit[占位]/LiquidityCap/ParticipationRate/SlippageLimit）
          →
          PositionPlan
            →
            ③ planner → ExecutionPlan
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from core.risk.calculators import (
    ConvictionWeightedCalculator,
    DrawdownAdjustedCalculator,
    FixedFractionCalculator,
    KellyFractionCalculator,
    RegimeBasedCalculator,
    VolatilityTargetingCalculator,
)
from core.risk.context import MarketContext, build_market_context
from core.risk.filters import (
    CorrelationLimitFilter,
    DrawdownLimitFilter,
    LiquidityCapFilter,
    LossLimitFilter,
    ParticipationRateFilter,
    PositionLimitFilter,
    SlippageLimitFilter,
)
from core.risk.filters.base import FilterResult
from core.risk.planner import plan as make_execution_plan
from core.risk.schemas import LimitCheck, PositionPlan, RiskAdjustment
from core.risk.schemas import ExecutionPlan
from core.schemas import ArbitrationDecision, Direction, Portfolio, RiskLimits


# ─────────────────────────────────────────────────────────────
# Default config
# ─────────────────────────────────────────────────────────────

DEFAULT_TARGET_ANNUAL_VOL = 0.15  # 15% 目标组合波动率
DEFAULT_FIXED_RISK_PCT = 0.01    # 1% 组合风险


# ─────────────────────────────────────────────────────────────
# RiskEngine
# ─────────────────────────────────────────────────────────────

class RiskEngine:
    """
    风控引擎 — Phase 7 唯一对外入口。

    接收 Phase 6 的 ArbitrationDecision，输出 PositionPlan（含 ExecutionPlan）。

    不做：
    - 不重写 Phase 3 执行底盘
    - 不重写 Phase 6 仲裁层
    - 不做自循环策略
    """

    def __init__(
        self,
        risk_limits: Optional[RiskLimits] = None,
    ):
        self.risk_limits = risk_limits or self._default_risk_limits()

        # 初始化 sizing 计算器（按优先级顺序）
        self._sizing_calculators = [
            ("volatility_targeting", VolatilityTargetingCalculator()),
            ("kelly", KellyFractionCalculator()),
            ("conviction_weighted", ConvictionWeightedCalculator()),
            ("fixed_fraction", FixedFractionCalculator()),
            ("drawdown_adjusted", DrawdownAdjustedCalculator()),
            ("regime_based", RegimeBasedCalculator()),
        ]

        # 初始化风控过滤器（按优先级顺序）
        self._filters = [
            PositionLimitFilter(),
            LossLimitFilter(),
            DrawdownLimitFilter(),
            CorrelationLimitFilter(),
            LiquidityCapFilter(),
            ParticipationRateFilter(),
            SlippageLimitFilter(),
        ]

    # ─────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────

    def calculate(
        self,
        decision: ArbitrationDecision,
        portfolio: Portfolio,
        market_context: Optional[MarketContext] = None,
        *,
        # 额外参数（可选）
        current_price: float = 0.0,
        avg_daily_volume_20d: float = 0.0,
        realized_vol_20d: float = 0.0,
        atr_14: float = 0.0,
        bid_ask_spread_bps: float = 0.0,
        market_cap: float = 0.0,
        vix_level: Optional[float] = None,
        existing_position_qty: float = 0.0,
        existing_direction: Optional[Direction] = None,
        avg_entry_price: float = 0.0,
        daily_loss_pct: float = 0.0,
        current_drawdown_pct: float = 0.0,
        correlation_value: Optional[float] = None,
        kelly_win_rate: Optional[float] = None,
        kelly_avg_win: Optional[float] = None,
        kelly_avg_loss: Optional[float] = None,
        regime_name: str = "unknown",
        urgency: str = "medium",
    ) -> PositionPlan:
        """
        计算仓位计划。

        Parameters
        ----------
        decision : ArbitrationDecision
            Phase 6 仲裁层决策
        portfolio : Portfolio
            当前组合状态
        market_context : MarketContext, optional
            市场环境数据

        Keyword Arguments（可选）
        ------------------------
        current_price : float
            当前标的现价（若 market_context 未提供）
        avg_daily_volume_20d : float
            20日平均成交量（若 market_context 未提供）
        realized_vol_20d : float
            年化已实现波动率（若 market_context 未提供）
        atr_14 : float
            14日 ATR（若 market_context 未提供）
        regime_name : str
            市场状态名称（用于 RegimeBased sizing）
        urgency : str
            执行紧迫度 low / medium / high

        Returns
        -------
        PositionPlan
            含 final_quantity / sizing_method / veto_triggered / execution_plan
        """
        start = datetime.utcnow()
        symbol = decision.symbol
        equity = portfolio.total_equity

        # ── 1. 构建 market_context ─────────────────────────
        if market_context is None:
            market_context = build_market_context(
                symbol=symbol,
                current_price=current_price,
                avg_daily_volume_20d=avg_daily_volume_20d,
                realized_vol_20d=realized_vol_20d,
                atr_14=atr_14,
                bid_ask_spread_bps=bid_ask_spread_bps,
                market_cap=market_cap,
                vix_level=vix_level,
            )

        # ── 2. bias = no_trade / exit / reduce ─────────────
        bias = getattr(decision, "bias", None) or "no_trade"
        if bias in ("no_trade", "hold_bias"):
            return self._zero_plan(
                decision_id=decision.decision_id,
                symbol=symbol,
                bias=bias,
                equity=equity,
                current_price=current_price,
                reason=getattr(decision, "no_trade_reason", None) or "arbitration veto",
                start=start,
            )

        # ── 3. 方向映射 + 执行动作（双向语义） ─────────────────────
        # Phase 6 ArbitrationDecision 无 direction 字段，从 bias 推导。
        #
        # 双字段设计（解耦 direction 和 exec_action）：
        #   direction   : 目标剩余暴露方向（LONG=剩余是多头，SHORT=剩余是空头，FLAT=无暴露）
        #   exec_action : ExecutionLayer 执行动作（BUY=买，SELL=卖，FLAT=无动作）
        #
        # 4 种 bias 的语义矩阵：
        #   bias          existing_dir  direction    exec_action
        #   long_bias     —             LONG        BUY        ← 开多仓
        #   short_bias    —             SHORT       SELL       ← 开空仓
        #   exit_bias     LONG          SHORT       SELL       ← 平多仓
        #   exit_bias     SHORT         LONG        BUY        ← 平空仓（cover）
        #   reduce_risk   LONG          LONG        SELL       ← 减多仓（卖出）
        #   reduce_risk   SHORT         SHORT       BUY        ← 减空仓（买回）
        if bias == "long_bias":
            direction = Direction.LONG
            direction_sign = 1
            exec_action = "BUY"
        elif bias == "short_bias":
            direction = Direction.SHORT
            direction_sign = -1
            exec_action = "SELL"
        elif bias == "exit_bias":
            if existing_direction == Direction.LONG:
                direction = Direction.SHORT
                direction_sign = -1
                exec_action = "SELL"      # 平多仓 → 卖出
            elif existing_direction == Direction.SHORT:
                direction = Direction.LONG
                direction_sign = 1
                exec_action = "BUY"       # 平空仓 → 买入（cover）
            else:
                return self._zero_plan(
                    decision_id=decision.decision_id,
                    symbol=symbol,
                    bias=bias,
                    equity=equity,
                    current_price=current_price,
                    reason="exit_without_position",
                    start=start,
                )
        elif bias == "reduce_risk":
            if existing_direction == Direction.LONG:
                direction = Direction.LONG
                direction_sign = 1
                exec_action = "SELL"     # 减多仓 → 卖出（减少多头暴露）
            elif existing_direction == Direction.SHORT:
                direction = Direction.SHORT
                direction_sign = -1
                exec_action = "BUY"       # 减空仓 → 买入（买回，减少空头暴露）
            else:
                return self._zero_plan(
                    decision_id=decision.decision_id,
                    symbol=symbol,
                    bias=bias,
                    equity=equity,
                    current_price=current_price,
                    reason="reduce_without_position",
                    start=start,
                )
        else:
            direction = Direction.FLAT
            direction_sign = 0
            exec_action = "FLAT"

        confidence = decision.confidence

        # ── 4. Sizing 计算（优先级链） ──────────────────
        sizing_result = self._run_sizing_chain(
            equity=equity,
            confidence=confidence,
            direction_sign=direction_sign,
            market_context=market_context,
            regime_name=regime_name,
            drawdown_ratio=current_drawdown_pct,
            kelly_win_rate=kelly_win_rate,
            kelly_avg_win=kelly_avg_win,
            kelly_avg_loss=kelly_avg_loss,
            bias=bias,
            existing_position_qty=existing_position_qty,
        )

        # ── 4b. exit / reduce 数量修正 ─────────────────
        # sizing chain 计算的是"开仓规模（目标持仓）"。
        # 对于 exit / reduce，数量不能超过已有持仓：
        #   exit   : qty = min(sizing, existing)   ← 平仓量 = min(目标, 现有)
        #   reduce : qty = min(sizing, existing)  ← 减仓量 = min(目标, 现有)
        sizing_qty = sizing_result["qty"]
        if bias in ("exit_bias", "reduce_risk") and existing_position_qty > 0:
            if sizing_qty > existing_position_qty:
                sizing_qty = existing_position_qty
                sizing_result["rationale"] += (
                    f" [clamped to existing_position_qty={existing_position_qty:.0f}]"
                )
            sizing_result["qty"] = sizing_qty

        # ── 5. 风控过滤器链 ──────────────────────────────
        filtered_qty, risk_adjustments, limit_checks, veto = self._run_filters(
            qty=sizing_qty,
            direction_sign=direction_sign,
            symbol=symbol,
            equity=equity,
            market_context=market_context,
            current_price=market_context.current_price,
            existing_position_qty=existing_position_qty,
            existing_position_symbols=[position.symbol for position in portfolio.positions if position.symbol != symbol],
            existing_directions=[
                1 if position.side == Direction.LONG else -1 if position.side == Direction.SHORT else 0
                for position in portfolio.positions
                if position.symbol != symbol
            ],
            correlation_matrix=portfolio.metadata.get("correlation_matrix", {}),
            correlation_value=correlation_value,
            avg_entry_price=avg_entry_price,
            daily_loss_pct=daily_loss_pct,
            current_drawdown_pct=current_drawdown_pct,
        )

        final_qty = filtered_qty if not veto else 0.0
        notional = final_qty * market_context.current_price

        # ── 6. 生成 PositionPlan（exec_action 解耦 direction） ──────
        position_plan = PositionPlan(
            plan_id=f"pp-{uuid4().hex[:8]}",
            decision_id=decision.decision_id,
            timestamp=datetime.utcnow(),
            symbol=symbol,
            bias=bias,
            arbitration_confidence=confidence,
            direction=direction,
            sizing_method=sizing_result["method"],
            base_quantity=sizing_result["qty"],
            final_quantity=final_qty,
            notional_value=notional,
            current_price=market_context.current_price,
            risk_adjustments=risk_adjustments,
            limit_checks=limit_checks,
            veto_triggered=veto,
            veto_reasons=[r for r in (getattr(decision, "no_trade_reason", None) or "").split(";") if r],
            sizing_rationale=sizing_result["rationale"],
            exec_action=exec_action,
            portfolio_snapshot_equity=equity,
        )

        # ── 7. ExecutionPlan ────────────────────────────
        execution_plan: Optional[ExecutionPlan] = None
        if final_qty > 0:
            execution_plan = make_execution_plan(
                position_plan=position_plan,
                market_context=market_context,
                risk_limits=self.risk_limits,
                arrival_price=market_context.current_price,
                urgency=urgency,
            )
            position_plan.execution_plan = execution_plan

        latency_ms = (datetime.utcnow() - start).total_seconds() * 1000
        position_plan.sizing_rationale += f" (risk_engine_latency={latency_ms:.2f}ms)"

        return position_plan

    # ─────────────────────────────────────────────────────────
    # Sizing chain
    # ─────────────────────────────────────────────────────────

    def _run_sizing_chain(
        self,
        equity: float,
        confidence: float,
        direction_sign: int,
        market_context: MarketContext,
        regime_name: str,
        drawdown_ratio: float,
        kelly_win_rate: Optional[float],
        kelly_avg_win: Optional[float],
        kelly_avg_loss: Optional[float],
        bias: str = "long_bias",
        existing_position_qty: float = 0.0,
    ) -> dict:
        """
        执行 6 种 sizing 算法优先级链。

        按顺序尝试，成功则返回；失败则降级到下一个。

        注意：exit_bias / reduce_risk 的数量上限修正由调用方在链外处理
        （engine 层基于 existing_position_qty 钳制）。

        TODO (Phase 8+): 重构为两层架构：
          Layer 1 主算法：VolatilityTargeting / Kelly（条件）
          Layer 2 修饰因子：Conviction / Drawdown / Regime → 直接乘以 Layer 1 结果
        """
        results: List[dict] = []

        for method_name, calc in self._sizing_calculators:
            result = calc.calculate(
                portfolio_equity=equity,
                direction_confidence=confidence,
                direction_sign=direction_sign,
                market_context=market_context,
                target_annual_vol=DEFAULT_TARGET_ANNUAL_VOL,
                stop_distance_pct=DEFAULT_FIXED_RISK_PCT,
                regime_name=regime_name,
                drawdown_ratio=drawdown_ratio,
                kelly_win_rate=kelly_win_rate,
                kelly_avg_win=kelly_avg_win,
                kelly_avg_loss=kelly_avg_loss,
            )
            results.append(result)

            # 优先用 Volatility Targeting（有市场波动率数据时）
            if method_name == "volatility_targeting" and result["qty"] > 0:
                return result

        # Fallback：找第一个有非零结果的
        for r in results:
            if r["qty"] > 0:
                return r

        return {
            "qty": 0.0,
            "confidence": 0.0,
            "rationale": "all sizing methods returned 0",
            "method": "none",
        }

    # ─────────────────────────────────────────────────────────
    # Filter chain
    # ─────────────────────────────────────────────────────────

    def _run_filters(
        self,
        qty: float,
        direction_sign: int,
        symbol: str,
        equity: float,
        market_context,
        current_price: float,
        existing_position_qty: float,
        existing_position_symbols: list[str],
        existing_directions: list[int],
        correlation_matrix: dict,
        correlation_value: Optional[float],
        avg_entry_price: float,
        daily_loss_pct: float,
        current_drawdown_pct: float,
    ) -> tuple[float, List[RiskAdjustment], List[LimitCheck], bool]:
        """
        执行风控过滤器链。

        任意过滤器触发 veto → final_quantity = 0
        """
        if qty <= 0:
            return 0.0, [], [], True

        original_qty = qty  # 链入口的原始数量，用于 LimitCheck.raw_qty
        current_qty = qty
        risk_adjustments: List[RiskAdjustment] = []
        limit_checks: List[LimitCheck] = []
        veto = False

        for f in self._filters:
            result: FilterResult = f.apply(
                qty=current_qty,
                direction_sign=direction_sign,
                risk_limits=self.risk_limits,
                symbol=symbol,
                portfolio_equity=equity,
                current_price=current_price,
                market_context=market_context,
                existing_position_qty=existing_position_qty,
                existing_position_symbols=existing_position_symbols,
                existing_directions=existing_directions,
                correlation_matrix=correlation_matrix,
                correlation_value=correlation_value,
                avg_entry_price=avg_entry_price,
                daily_loss_pct=daily_loss_pct,
                current_drawdown_pct=current_drawdown_pct,
            )

            limit_checks.append(
                LimitCheck(
                    limit_name=f.name,
                    limit_value=getattr(self.risk_limits, f.name, 0.0),
                    raw_qty=original_qty,       # 链入口的原始数量
                    actual_value=current_qty,   # 经前序 filters 调整后的数量
                    passed=result.limit_check_passed,
                    mode=result.mode,           # pass / cap / veto
                    details=result.details,
                )
            )

            if result.adjusted_qty != current_qty:
                # adjustment_type 语义：reduced=被缩小，capped=被限制到上限，zeroed=被归零
                if result.mode == "veto":
                    adj_type = "zeroed"
                elif result.adjusted_qty < current_qty:
                    adj_type = "reduced"
                else:
                    adj_type = "capped"
                risk_adjustments.append(
                    RiskAdjustment(
                        filter_name=f.name,
                        adjustment_type=adj_type,
                        original_quantity=current_qty,
                        adjusted_quantity=result.adjusted_qty,
                        reason=result.details,
                    )
                )
                current_qty = result.adjusted_qty

            if not result.passed:
                veto = True

        return current_qty, risk_adjustments, limit_checks, veto

    # ─────────────────────────────────────────────────────────
    # Zero plan
    # ─────────────────────────────────────────────────────────

    def _zero_plan(
        self,
        decision_id: str,
        symbol: str,
        bias: str,
        equity: float,
        current_price: float,
        reason: str,
        start: datetime,
    ) -> PositionPlan:
        return PositionPlan(
            plan_id=f"pp-{uuid4().hex[:8]}",
            decision_id=decision_id,
            timestamp=datetime.utcnow(),
            symbol=symbol,
            bias=bias,
            arbitration_confidence=0.0,
            direction=Direction.FLAT,
            sizing_method="none",
            base_quantity=0.0,
            final_quantity=0.0,
            notional_value=0.0,
            current_price=max(current_price, 0.01),  # Pydantic gt=0
            veto_triggered=True,
            veto_reasons=[reason],
            sizing_rationale=f"bias={bias}, reason: {reason}",
            portfolio_snapshot_equity=equity,
        )

    # ─────────────────────────────────────────────────────────
    # Defaults
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _default_risk_limits() -> RiskLimits:
        return RiskLimits()
