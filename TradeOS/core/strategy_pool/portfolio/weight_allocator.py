"""WeightAllocator — 多策略权重分配器。

支持三种分配方法：
- equal: 等权重
- inverse_vol: 逆波动率权重
- ir: 信息比率权重（需提供 IR 估计）

RiskParity: 封装调用 Phase 4B PortfolioOptimizer（不重造优化器）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from core.strategy_pool.schemas.portfolio import StrategyWeight


class WeightAllocator:
    """权重分配器基类。"""

    def allocate(
        self,
        strategy_ids: List[str],
        strategy_metrics: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, float]:
        """返回 {strategy_id: weight} 字典，权重和为 1。"""
        raise NotImplementedError


class EqualWeightAllocator(WeightAllocator):
    """等权重分配。"""

    def allocate(
        self,
        strategy_ids: List[str],
        strategy_metrics: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, float]:
        if not strategy_ids:
            return {}
        n = len(strategy_ids)
        return {sid: 1.0 / n for sid in strategy_ids}


class InverseVolWeightAllocator(WeightAllocator):
    """逆波动率权重分配（年化波动率倒数）。"""

    def allocate(
        self,
        strategy_ids: List[str],
        strategy_metrics: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, float]:
        if not strategy_ids:
            return {}
        if strategy_metrics is None:
            return {sid: 1.0 / len(strategy_ids) for sid in strategy_ids}

        weights: Dict[str, float] = {}
        inv_vols: List[float] = []

        for sid in strategy_ids:
            metrics = strategy_metrics.get(sid, {})
            volatility = metrics.get("annualized_vol", 0.01)
            inv_vols.append(1.0 / max(volatility, 0.001))

        total = sum(inv_vols)
        for i, sid in enumerate(strategy_ids):
            weights[sid] = inv_vols[i] / total if total > 0 else 1.0 / len(strategy_ids)

        return weights


class IRWeightAllocator(WeightAllocator):
    """信息比率权重分配（IR 越大权重越高）。"""

    def allocate(
        self,
        strategy_ids: List[str],
        strategy_metrics: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, float]:
        if not strategy_ids:
            return {}
        if strategy_metrics is None:
            return {sid: 1.0 / len(strategy_ids) for sid in strategy_ids}

        ir_scores: List[float] = []
        for sid in strategy_ids:
            metrics = strategy_metrics.get(sid, {})
            ir = metrics.get("ir", 0.0)
            # IR 可以是负数，用 max(ir, 0) 保证非负
            ir_scores.append(max(ir, 0.0))

        total = sum(ir_scores)
        if total == 0:
            return {sid: 1.0 / len(strategy_ids) for sid in strategy_ids}

        return {sid: ir_scores[i] / total for i, sid in enumerate(strategy_ids)}


class RiskParityWeightAllocator(WeightAllocator):
    """
    Risk Parity 权重分配。

    封装调用 Phase 4B PortfolioOptimizer。
    每个策略被视为一个"资产"，其波动率作为风险贡献分配依据。
    如果 Phase 4B optimizer 不可用，降级为 InverseVolWeightAllocator。
    """

    def allocate(
        self,
        strategy_ids: List[str],
        strategy_metrics: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, float]:
        if not strategy_ids:
            return {}

        # 优先尝试调用 Phase 4B optimizer
        weights = self._try_phase4b_optimize(strategy_ids, strategy_metrics)
        if weights is not None:
            return weights

        # 降级：使用逆波动率
        fallback = InverseVolWeightAllocator()
        return fallback.allocate(strategy_ids, strategy_metrics)

    def _try_phase4b_optimize(
        self,
        strategy_ids: List[str],
        strategy_metrics: Optional[Dict[str, Dict]],
    ) -> Optional[Dict[str, float]]:
        """
        尝试调用 Phase 4B PortfolioOptimizer。

        Returns weights dict if successful, None if Phase 4B unavailable.
        """
        try:
            from core.research.portfolio.optimizer import PortfolioOptimizer
            from core.research.portfolio.schemas import (
                PortfolioSpec,
                AssetSpec,
                OptimizationConstraint,
            )

            assets = [
                AssetSpec(
                    asset_id=sid,
                    expected_return=strategy_metrics.get(sid, {}).get("mean_return", 0.0)
                    if strategy_metrics
                    else 0.0,
                    volatility=strategy_metrics.get(sid, {}).get("annualized_vol", 0.01)
                    if strategy_metrics
                    else 0.01,
                    is_long=True,
                )
                for sid in strategy_ids
            ]

            spec = PortfolioSpec(
                portfolio_id="risk_parity_wrapper",
                assets=assets,
                optimization_method="risk_parity",
                constraints=[],
            )

            optimizer = PortfolioOptimizer(spec)
            result = optimizer.optimize()

            if result.weights is not None:
                return {sid: float(result.weights[i]) for i, sid in enumerate(strategy_ids)}
            return None

        except ImportError:
            # Phase 4B 未安装
            return None
        except Exception:
            return None


def make_allocator(method: str) -> WeightAllocator:
    """工厂方法：根据方法名创建 allocator。"""
    if method == "equal":
        return EqualWeightAllocator()
    elif method == "inverse_vol":
        return InverseVolWeightAllocator()
    elif method == "ir":
        return IRWeightAllocator()
    elif method == "risk_parity":
        return RiskParityWeightAllocator()
    else:
        raise ValueError(f"Unknown weight method: {method}")


def allocate_portfolio_weights(
    strategy_ids: List[str],
    method: str,
    strategy_metrics: Optional[Dict[str, Dict]] = None,
) -> List[StrategyWeight]:
    """便捷方法：返回 StrategyWeight[]。"""
    allocator = make_allocator(method)
    weights = allocator.allocate(strategy_ids, strategy_metrics)
    return [
        StrategyWeight(strategy_id=sid, weight=w, weight_method=method)
        for sid, w in weights.items()
    ]
