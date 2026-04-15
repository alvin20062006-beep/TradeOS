"""
Signal Scorer
============

将各引擎信号归一化为 DirectionalSignal，计算基础加权得分。

信号方向映射（基于现有 schema，不自造字段）：
  TechnicalSignal     → signal.direction
  ChanSignal          → signal.direction
  OrderFlowSignal     → 从 book_imbalance 推导（>0 → LONG, <0 → SHORT, |imbalance|<0.1 → FLAT）
  SentimentEvent      → 从 composite_sentiment 推导（>0.5 → LONG, <0.5 → SHORT, 接近0.5 → FLAT）
  MacroSignal         → 从 risk_on 推导（risk_on=True → LONG, risk_on=False → SHORT）

置信度映射：
  TechnicalSignal     → signal.confidence
  ChanSignal          → signal.confidence
  OrderFlowSignal     → abs(book_imbalance) 作为置信度代理
  SentimentEvent      → 从 composite_sentiment 距离 0.5 的偏离度
  MacroSignal         → regime_confidence
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.schemas import Direction, Regime

from core.arbitration.schemas import DirectionalSignal, SignalScore

if TYPE_CHECKING:
    from core.arbitration.schemas import SignalBundle


# 弱信号阈值（低于此置信度视为噪音）
LOW_CONFIDENCE_THRESHOLD = 0.3


def derive_direction_and_confidence(
    bundle: "SignalBundle",
) -> list[DirectionalSignal]:
    """
    从 SignalBundle 中提取并归一化所有方向信号。

    Args:
        bundle: SignalBundle

    Returns:
        list[DirectionalSignal]
    """
    signals: list[DirectionalSignal] = []

    # ── TechnicalSignal ──────────────────────────────────
    if bundle.technical is not None:
        sig = bundle.technical
        signals.append(
            DirectionalSignal(
                engine_name="technical",
                direction=sig.direction,
                confidence=sig.confidence,
                regime=sig.regime,
                raw_signal=sig,
            )
        )

    # ── ChanSignal ───────────────────────────────────────
    if bundle.chan is not None:
        sig = bundle.chan
        signals.append(
            DirectionalSignal(
                engine_name="chan",
                direction=sig.direction,
                confidence=sig.confidence,
                regime=sig.regime,
                raw_signal=sig,
            )
        )

    # ── OrderFlowSignal ──────────────────────────────────
    if bundle.orderflow is not None:
        sig = bundle.orderflow
        imbalance = sig.book_imbalance  # -1 到 1

        if abs(imbalance) < 0.1:
            direction = Direction.FLAT
            confidence = 0.0
        elif imbalance > 0:
            direction = Direction.LONG
            confidence = abs(imbalance)
        else:
            direction = Direction.SHORT
            confidence = abs(imbalance)

        signals.append(
            DirectionalSignal(
                engine_name="orderflow",
                direction=direction,
                confidence=min(confidence, 1.0),
                regime=None,  # OrderFlowSignal 没有 regime
                raw_signal=sig,
            )
        )

    # ── SentimentEvent ───────────────────────────────────
    if bundle.sentiment is not None:
        sig = bundle.sentiment
        cs = sig.composite_sentiment  # 0 到 1

        # composite_sentiment 本身是 0-1 的得分
        # > 0.5 → LONG, < 0.5 → SHORT, 接近 0.5 → FLAT
        distance_from_neutral = abs(cs - 0.5)
        if distance_from_neutral < 0.1:
            direction = Direction.FLAT
            confidence = 0.0
        elif cs > 0.5:
            direction = Direction.LONG
            confidence = min(distance_from_neutral * 2, 1.0)
        else:
            direction = Direction.SHORT
            confidence = min(distance_from_neutral * 2, 1.0)

        signals.append(
            DirectionalSignal(
                engine_name="sentiment",
                direction=direction,
                confidence=confidence,
                regime=None,  # SentimentEvent 没有 regime
                raw_signal=sig,
            )
        )

    # ── MacroSignal ──────────────────────────────────────
    if bundle.macro is not None:
        sig = bundle.macro
        # risk_on=True → LONG, risk_on=False → SHORT
        direction = Direction.LONG if sig.risk_on else Direction.SHORT
        confidence = sig.regime_confidence

        # MacroSignal 没有 regime 字段
        regime: Regime | None = None

        signals.append(
            DirectionalSignal(
                engine_name="macro",
                direction=direction,
                confidence=confidence,
                regime=regime,
                raw_signal=sig,
            )
        )

    # 过滤弱信号
    return [s for s in signals if s.confidence >= LOW_CONFIDENCE_THRESHOLD]


def score_signal(ds: DirectionalSignal) -> SignalScore:
    """
    为单个 DirectionalSignal 计算 SignalScore。

    基础权重为 1.0，后续由 ConfidenceWeightRule 调整。
    """
    contribution = ds.score()
    return SignalScore(
        engine_name=ds.engine_name,
        direction=ds.direction,
        raw_confidence=ds.confidence,
        adjusted_confidence=ds.confidence,
        weight=ds.weight,
        contribution=contribution,
        regime=ds.regime,
    )
