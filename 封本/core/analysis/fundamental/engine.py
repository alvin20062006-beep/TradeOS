"""
Fundamental Engine (基本盘信息报表引擎)
=====================================

独立引擎，输出 FundamentalReport。

功能:
- 估值分析 (PE/PB/PS/PEG/EV/EBITDA)
- 质量分析 (ROE/ROA/毛利率/净利率/现金流质量)
- 成长分析 (营收/利润/EPS 增长)
- 杠杆/偿债能力 (负债率/流动比率/利息保障)
- 综合基本盘评分 (A/B/C/D)

输入:
  - 理想输入: FundamentalsSnapshot
  - Proxy 输入: MarketBar[] (OHLCV) ← 外部基本面数据暂不完整

输出: FundamentalReport

⚠️ Proxy 标注:
- 当 FundamentalsSnapshot 完整 → 无 proxy 字段
- 当字段缺失 → metadata["ratios"][category][field]["source"] 标注
- metadata["proxy"] = True（若存在任何 proxy 字段）
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

from core.schemas import FundamentalsSnapshot, MarketBar

from .report import generate_report, FundamentalReport


class FundamentalEngine:
    """
    基本盘信息报表引擎.

    独立实现，不继承 AnalysisEngine。
    """

    engine_name = "fundamental"

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    # ─────────────────────────────────────────────────────────────
    # 主入口
    # ─────────────────────────────────────────────────────────────

    def analyze(
        self,
        data: Any,
        prev_data: Optional[Any] = None,
        **kwargs: Any,
    ) -> FundamentalReport:
        """
        执行基本盘分析.

        Args:
            data: FundamentalsSnapshot 或 dict 或 MarketBar[]
            prev_data: 上一期 FundamentalsSnapshot（可选，用于计算增长）

        Returns:
            FundamentalReport
        """
        # 解析输入
        fs = self._parse_input(data)
        prev_fs = self._parse_prev(prev_data) if prev_data is not None else None

        if fs is None:
            return self._empty_report()

        # 生成报表
        return generate_report(fs, prev_fs)

    # ─────────────────────────────────────────────────────────────
    # 输入解析
    # ─────────────────────────────────────────────────────────────

    def _parse_input(self, data: Any) -> Optional[FundamentalsSnapshot]:
        """解析输入为 FundamentalsSnapshot."""
        if data is None:
            return None

        if isinstance(data, FundamentalsSnapshot):
            return data

        if isinstance(data, dict):
            if "fundamentals" in data:
                fd = data["fundamentals"]
                return FundamentalsSnapshot(**fd) if isinstance(fd, dict) else fd
            if "symbol" in data or "pe_ratio" in data or "market_cap" in data:
                return FundamentalsSnapshot(**data)
            if "close" in data and isinstance(data, dict) and "symbol" in data:
                # MarketBar[] proxy → 构建最小 snapshot
                return self._snapshot_from_bars(data)
        elif isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, MarketBar):
                return self._snapshot_from_bars(data)
            if isinstance(first, dict):
                if "close" in first:
                    return self._snapshot_from_bars(data)
                return FundamentalsSnapshot(**first)

        return None

    def _parse_prev(self, data: Any) -> Optional[FundamentalsSnapshot]:
        """解析上一期数据."""
        return self._parse_input(data)

    def _snapshot_from_bars(self, data: Any) -> Optional[FundamentalsSnapshot]:
        """
        ⚠️ 从 MarketBar[] 构建 proxy FundamentalsSnapshot.

        仅有 market_cap（估算）和 beta（proxy）。
        其他基本面字段均为 None。
        """
        bars = data if isinstance(data, list) else [data]
        if not bars:
            return None

        first = bars[0]
        if isinstance(first, MarketBar):
            symbol = first.symbol
            ts = first.timestamp
            close = first.close
        elif isinstance(first, dict):
            symbol = first.get("symbol", "")
            ts = first.get("timestamp", datetime.utcnow())
            close = first.get("close", first.get("price", 100.0))
        else:
            return None

        # ⚠️ proxy: market_cap 估算（假设 1 亿股）
        estimated_shares = 1e8
        estimated_market_cap = close * estimated_shares

        return FundamentalsSnapshot(
            symbol=symbol,
            timestamp=ts,
            market_cap=estimated_market_cap,  # ⚠️ proxy
            beta=None,  # proxy: 需要历史价格数据
        )

    # ─────────────────────────────────────────────────────────────
    # 空报表
    # ─────────────────────────────────────────────────────────────

    def _empty_report(self) -> FundamentalReport:
        """返回空报表."""
        return FundamentalReport(
            symbol="",
            report_date=datetime.utcnow(),
            pe=None, pb=None, ps=None, peg=None,
            ev_ebitda=None, market_cap=None,
            roe=None, roa=None, gross_margin=None, net_margin=None,
            revenue_growth_yoy=None, net_income_growth_yoy=None, eps_growth_yoy=None,
            debt_to_equity=None, current_ratio=None, quick_ratio=None,
            interest_coverage=None,
            dividend_yield=None,
            quality_score=0.0, value_score=0.0, growth_score=0.0,
            red_flags=["no_data"],
            rating="D",
            metadata={
                "proxy": True,
                "error": "no_fundamentals_data",
                "field_sources": {
                    k: "missing"
                    for k in [
                        "pe", "pb", "ps", "peg", "ev_ebitda",
                        "roe", "roa", "gross_margin", "net_margin",
                        "revenue_growth_yoy", "net_income_growth_yoy", "eps_growth_yoy",
                        "debt_to_equity", "current_ratio", "quick_ratio", "interest_coverage",
                        "dividend_yield",
                    ]
                },
            },
        )

    # ─────────────────────────────────────────────────────────────
    # 批量分析
    # ─────────────────────────────────────────────────────────────

    def batch_analyze(
        self,
        data_map: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, FundamentalReport]:
        """批量分析."""
        results = {}
        for symbol, data in data_map.items():
            try:
                results[symbol] = self.analyze(data, **kwargs)
            except Exception:
                results[symbol] = self._empty_report()
                results[symbol].symbol = symbol
        return results

    # ─────────────────────────────────────────────────────────────
    # 生命周期
    # ─────────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        """健康检查."""
        return True
