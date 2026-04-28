"""
apps/api/routers/analysis.py 鈥?鍒嗘瀽寮曟搸 API 绔偣

POST /analysis/run锛氳Е鍙?Phase 5 鍒嗘瀽锛坰uggestion-only锛屽啓 FeedbackRegistry锛?AI 閫氳繃 API DTO 鎺ュ叆锛岀姝㈢洿鎺ョ粦瀹氭牳蹇?AnalysisSignal銆?"""

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
    瑙﹀彂 Phase 5 鍒嗘瀽寮曟搸銆?
    suggestion-only锛氬彧杈撳嚭 AnalysisSignal锛屼笉鏀?registry 鐪熷€笺€?    AI 鍙€氳繃姝ょ鐐逛骇鐢熷缓璁紝寤鸿缁撴灉鍐欏叆 FeedbackRegistry锛坅ppend-only锛夈€?
    鎺ュ叆锛歝ore.analysis.engine.AnalysisEngine.analyze()
    """
    # 杞崲 DTO 鈫?鏍稿績鍙傛暟
    data = {
        "score": req.score,
        "alpha": req.alpha,
        "confidence": req.confidence,
        "direction": req.direction,
    }

    # 璋冪敤 Phase 5 鏍稿績寮曟搸锛堝唴閮?import锛岄伩鍏嶅惎鍔ㄦ椂寮哄埗鍔犺浇锛?    signal = _call_analysis_engine(req.symbol, data)

    # 鍐?FeedbackRegistry锛坅ppend-only锛?    _log_analysis_feedback(user.id, req, signal)

    # TechnicalSignal.direction 鏄?Direction enum锛岃浆涓哄瓧绗︿覆
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


# 鈹€鈹€ 鍐呴儴璋冪敤 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _call_analysis_engine(symbol: str, data: dict):
    """
    璋冪敤 Phase 5 鎶€鏈垎鏋愬紩鎿庯紙TechnicalEngine锛夈€?
    娉ㄦ剰锛歍echnicalEngine 闇€瑕佺湡瀹?K 绾挎暟鎹紙鑷冲皯 20 鏍?bar锛夈€?    API 棣栨壒鏀寔涓ょ妯″紡锛?    1. 鏈夌湡瀹?bar 鏁版嵁 鈫?璋冪敤 TechnicalEngine
    2. 鏃?bar 鏁版嵁锛堟祴璇?demo锛夆啋 鐩存帴鏋勯€?TechnicalSignal

    鍚庣画鎵╁睍锛氭帴鍏?Phase 1 鏁版嵁灞傦紝閫氳繃 symbol 鑾峰彇鐪熷疄 bar銆?    """
    from core.schemas import TechnicalSignal, Direction, Regime

    # 灏濊瘯鏋勯€?TechnicalSignal锛堢粫杩?TechnicalEngine 鐨?bar 鏍￠獙锛?    # API DTO 浼犲叆鐨?data 宸插寘鍚?symbol/direction/confidence
    direction_str = data.get("direction", "FLAT").upper()
    dir_map = {"LONG": Direction.LONG, "SHORT": Direction.SHORT, "FLAT": Direction.FLAT}
    direction = dir_map.get(direction_str, Direction.FLAT)

    signal = TechnicalSignal(
        engine_name="technical",
        symbol=symbol,
        timestamp=datetime.utcnow(),
        direction=direction,
        confidence=float(data.get("confidence", 0.5)),
        regime=Regime.UNKNOWN,  # API 绔偣榛樿 UNKNOWN锛屽悗缁彲鎵╁睍
        entry_score=float(data.get("score", 0.5)),
        exit_score=float(data.get("score", 0.5)),
    )

    return signal


def _call_live_analysis(req: LiveRunRequest) -> dict:
    from core.data.live import LiveAnalysisOrchestrator

    orchestrator = LiveAnalysisOrchestrator(profile_id=req.profile_id)
    result = orchestrator.run_live_analysis(
        symbol=req.symbol,
        timeframe=req.timeframe,
        market_type=req.market_type,
        lookback=req.lookback,
        start=req.start,
        end=req.end,
        news_limit=req.news_limit,
        profile_id=req.profile_id,
    )
    bars = result["bars"]
    technical = result["signals"]["technical"]

    return {
        "data": {
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "market_type": req.market_type,
            "profile_id": result["profile"].profile_id,
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
    灏嗗垎鏋愮粨鏋滆拷鍔犲埌 FeedbackRegistry锛坅ppend-only锛夈€?    杩欐槸 AI suggestion 鐨勫悎娉曞啓鍏ヨ矾寰勩€?    """
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
        pass  # 瀹¤鏃ュ織澶辫触涓嶉樆鏂富娴佺▼
