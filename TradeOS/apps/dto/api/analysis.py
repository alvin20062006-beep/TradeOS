"""
apps/dto/api/analysis.py — 分析引擎 API DTO
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ── 请求 ────────────────────────────────────────────────────

class AnalysisRunRequest(BaseModel):
    """POST /analysis/run 请求。"""

    symbol: str = Field(min_length=1, max_length=16, description="标的代码")
    score: float = Field(default=0.0, ge=-1.0, le=1.0, description="分析评分")
    alpha: float = Field(default=0.0, ge=-1.0, le=1.0, description="Alpha 强度")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="信号置信度")
    direction: str = Field(
        default="FLAT",
        description="信号方向 LONG | SHORT | FLAT",
    )

    @field_validator("direction")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


# ── 响应 ────────────────────────────────────────────────────

class AnalysisSignalView(BaseModel):
    """
    分析信号（展示用 view model）。

    与核心对象 core.schemas.AnalysisSignal 完全解耦，
    仅包含前端展示所需字段。
    """

    signal_id: str
    symbol: str
    direction: str = Field(description="LONG / SHORT / FLAT")
    strength: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime

    model_config = {"str_strip_whitespace": True}


class AnalysisRunResponse(BaseModel):
    """POST /analysis/run 响应。"""

    ok: bool = True
    signal: AnalysisSignalView
    source: str = Field(default="analysis", description="来源模块标识")
