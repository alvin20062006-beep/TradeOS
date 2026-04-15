"""StrategyEvaluator — 策略绩效评估。

复用 Phase 4C 回测引擎的能力。
仅提供策略池视角的绩效评估封装。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel


class EvaluationMetrics(BaseModel):
    """策略绩效指标。"""
    ir: float = 0.0
    sharpe: float = 0.0
    annualized_return: float = 0.0
    annualized_vol: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    calmar: float = 0.0
    sortino: float = 0.0
    trade_count: int = 0


class StrategyEvaluator:
    """
    策略绩效评估器。

    复用 Phase 4C 回测引擎的评估逻辑，提供标准绩效指标。
    """

    def evaluate(
        self,
        pnl_series: List[float],
        trades: Optional[List[Dict[str, Any]]] = None,
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252,
    ) -> EvaluationMetrics:
        """
        评估策略绩效指标。

        Args:
            pnl_series: 每日/每 bar PnL 序列
            trades: 交易记录列表（每条含 pnl 字段）
            risk_free_rate: 年化无风险利率
            periods_per_year: 年化周期数
        """
        import numpy as np

        pnl = np.array(pnl_series, dtype=float)

        total_return = np.sum(pnl)
        annual_ret = total_return * periods_per_year / max(len(pnl), 1)
        annual_vol = np.std(pnl) * np.sqrt(periods_per_year)

        # IR
        ir = annual_ret / annual_vol if annual_vol > 1e-10 else 0.0

        # Sharpe
        excess = annual_ret - risk_free_rate
        sharpe = excess / annual_vol if annual_vol > 1e-10 else 0.0

        # Sortino（下行波动率）
        neg_pnl = pnl[pnl < 0]
        downside_vol = np.std(neg_pnl) * np.sqrt(periods_per_year) if len(neg_pnl) > 1 else 0.0
        sortino = excess / downside_vol if downside_vol > 1e-10 else 0.0

        # Max Drawdown
        cum = np.cumsum(pnl)
        running_max = np.maximum.accumulate(cum)
        drawdowns = running_max - cum
        max_dd = np.max(drawdowns)
        max_dd_pct = max_dd / (running_max[-1] + 1e-10) if len(running_max) > 0 and running_max[-1] > 0 else 0.0

        # Calmar
        calmar = annual_ret / max_dd if max_dd > 1e-10 else 0.0

        # Win Rate
        win_rate = 0.0
        if trades:
            wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
            win_rate = wins / len(trades) if trades else 0.0
        elif len(pnl) > 0:
            wins = sum(1 for p in pnl if p > 0)
            win_rate = wins / len(pnl)

        return EvaluationMetrics(
            ir=float(ir),
            sharpe=float(sharpe),
            annualized_return=float(annual_ret),
            annualized_vol=float(annual_vol),
            max_drawdown=float(max_dd),
            max_drawdown_pct=float(max_dd_pct),
            win_rate=float(win_rate),
            calmar=float(calmar),
            sortino=float(sortino),
            trade_count=len(trades) if trades else int(len(pnl)),
        )

    def rank_strategies(
        self,
        metrics_by_strategy: Dict[str, EvaluationMetrics],
        weights: Optional[Dict[str, float]] = None,
    ) -> List[tuple]:
        """
        多策略排名。

        Returns strategies sorted by composite score (sharpe + ir weighted).
        """
        scored = []
        for sid, m in metrics_by_strategy.items():
            score = m.sharpe * 0.5 + m.ir * 0.3 + (m.win_rate * 0.2)
            if weights and sid in weights:
                score *= (1 + weights[sid] * 0.5)
            scored.append((sid, float(score), m))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
