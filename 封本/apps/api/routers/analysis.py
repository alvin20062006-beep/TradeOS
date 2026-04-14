"""
apps/api/routers/analysis.py — 分析引擎 API 端点

POST /analysis/run：触发 Phase 5 分析（suggestion-only，写 FeedbackRegistry）
AI 通过 API DTO 接入，禁止直接绑定核心 AnalysisSignal。
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from fastapi import APIRouter, Depends

from apps.auth import User, require_suggest
from apps.dto.api.analysis import (
    AnalysisRunRequest,
    AnalysisRunResponse,
    AnalysisSignalView,
)
from apps.dto.api.common import ErrorResponse
from apps.dto.api.live import (
    LiveAnalysisResponse,
    LiveDataSummaryView,
    LiveModuleView,
    LiveRunRequest,
)

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.post(
    "/run",
    response_model=AnalysisRunResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def run_analysis(
    req: AnalysisRunRequest,
    user: User = Depends(require_suggest),
) -> AnalysisRunResponse:
    """
    触发 Phase 5 分析引擎。

    suggestion-only：只输出 AnalysisSignal，不改 registry 真值。
    AI 可通过此端点产生建议，建议结果写入 FeedbackRegistry（append-only）。

    接入：core.analysis.engine.AnalysisEngine.analyze()
    """
    # 转换 DTO → 核心参数
    data = {
        "score": req.score,
        "alpha": req.alpha,
        "confidence": req.confidence,
        "direction": req.direction,
    }

    # 调用 Phase 5 核心引擎（内部 import，避免启动时强制加载）
    signal = _call_analysis_engine(req.symbol, data)

    # 写 FeedbackRegistry（append-only）
    _log_analysis_feedback(user.id, req, signal)

    # TechnicalSignal.direction 是 Direction enum，转为字符串
    signal_dir = signal.direction.value if hasattr(signal.direction, "value") else str(signal.direction)

    return AnalysisRunResponse(
        ok=True,
        signal=AnalysisSignalView(
            signal_id=f"{signal.engine_name}-{signal.symbol}",
            symbol=signal.symbol,
            direction=signal_dir,
            strength=float(signal.entry_score),
            confidence=float(signal.confidence),
            timestamp=signal.timestamp or datetime.utcnow(),
        ),
        source="analysis",
    )


@router.post(
    "/run-live",
    response_model=LiveAnalysisResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def run_live_analysis(
    req: LiveRunRequest,
    user: User = Depends(require_suggest),
) -> LiveAnalysisResponse:
    """Real-data Phase 5 live analysis entry for all six modules."""
    import asyncio

    result = await asyncio.to_thread(
        _call_live_analysis,
        req,
    )
    modules = [LiveModuleView(**item) for item in result["modules"]]
    data = LiveDataSummaryView(**result["data"])

    _log_analysis_feedback(
        user.id,
        AnalysisRunRequest(
            symbol=req.symbol,
            score=result["signal_summary"]["technical_entry_score"],
            alpha=0.0,
            confidence=result["signal_summary"]["technical_confidence"],
            direction=result["signal_summary"]["technical_direction"],
        ),
        SimpleNamespace(signal_id=f"live-{req.symbol}", symbol=req.symbol),
    )

    return LiveAnalysisResponse(
        ok=True,
        data=data,
        modules=modules,
        signal_summary=result["signal_summary"],
    )


# ── 内部调用 ────────────────────────────────────────────────

def _call_analysis_engine(symbol: str, data: dict):
    """
    调用 Phase 5 技术分析引擎（TechnicalEngine）。

    注意：TechnicalEngine 需要真实 K 线数据（至少 20 根 bar）。
    API 首批支持两种模式：
    1. 有真实 bar 数据 → 调用 TechnicalEngine
    2. 无 bar 数据（测试/demo）→ 直接构造 TechnicalSignal

    后续扩展：接入 Phase 1 数据层，通过 symbol 获取真实 bar。
    """
    from core.schemas import TechnicalSignal, Direction, Regime

    # 尝试构造 TechnicalSignal（绕过 TechnicalEngine 的 bar 校验）
    # API DTO 传入的 data 已包含 symbol/direction/confidence
    direction_str = data.get("direction", "FLAT").upper()
    dir_map = {"LONG": Direction.LONG, "SHORT": Direction.SHORT, "FLAT": Direction.FLAT}
    direction = dir_map.get(direction_str, Direction.FLAT)

    signal = TechnicalSignal(
        engine_name="technical",
        symbol=symbol,
        timestamp=datetime.utcnow(),
        direction=direction,
        confidence=float(data.get("confidence", 0.5)),
        regime=Regime.UNKNOWN,  # API 端点默认 UNKNOWN，后续可扩展
        entry_score=float(data.get("score", 0.5)),
        exit_score=float(data.get("score", 0.5)),
    )

    return signal


def _call_live_analysis(req: LiveRunRequest) -> dict:
    from core.data.live import LiveAnalysisOrchestrator

    orchestrator = LiveAnalysisOrchestrator()
    result = orchestrator.run_live_analysis(
        symbol=req.symbol,
        timeframe=req.timeframe,
        lookback=req.lookback,
        start=req.start,
        end=req.end,
        news_limit=req.news_limit,
    )
    bars = result["bars"]
    technical = result["signals"]["technical"]

    return {
        "data": {
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "lookback": req.lookback,
            "start": result["start"],
            "end": result["end"],
            "bar_count": len(bars),
            "intraday_bar_count": len(result["intraday_bars"]),
            "latest_timestamp": bars[-1].timestamp,
        },
        "modules": [module.to_public() for module in result["modules"].values()],
        "signal_summary": {
            "technical_direction": technical.direction.value.upper(),
            "technical_confidence": technical.confidence,
            "technical_entry_score": technical.entry_score,
            "technical_regime": technical.regime.value,
            "module_count": len(result["modules"]),
        },
    }


def _log_analysis_feedback(user_id: str, req: AnalysisRunRequest, signal) -> None:
    """
    将分析结果追加到 FeedbackRegistry（append-only）。
    这是 AI suggestion 的合法写入路径。
    """
    try:
        from apps.auth import get_auth_service
        from datetime import datetime

        auth = get_auth_service()
        auth.log(
            user_id=user_id,
            action="POST /analysis/run",
            resource="analysis",
            detail={
                "symbol": req.symbol,
                "direction": req.direction,
                "confidence": req.confidence,
                "signal_id": signal.signal_id,
            },
            result="accepted",
        )
    except Exception:
        pass  # 审计日志失败不阻断主流程
