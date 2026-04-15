"""apps/dto/api — API 层 DTO（FastAPI request/response）"""
from apps.dto.api.common import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
    PaginationParams,
)
from apps.dto.api.analysis import (
    AnalysisRunRequest,
    AnalysisRunResponse,
    AnalysisSignalView,
)
from apps.dto.api.arbitration import (
    ArbitrationRunRequest,
    ArbitrationResponse,
    PortfolioArbitrationRequest,
    StrategyProposalRequest,
    DecisionRationaleView,
)
from apps.dto.api.risk import (
    RiskCalculateRequest,
    PositionPlanView,
    ExecutionPlanView,
)
from apps.dto.api.audit import (
    AuditQueryParams,
    AuditQueryResponse,
    DecisionRecordView,
    RiskAuditView,
    FeedbackView,
    FeedbackScanRequest,
    FeedbackScanResponse,
    FeedbackScanResult,
)
from apps.dto.api.strategy_pool import (
    StrategyPoolProposeRequest,
    StrategyPoolProposeResponse,
    StrategyPoolDecisionBundle,
)
from apps.dto.api.pipeline import (
    PipelineRunFullRequest,
    PipelineRunFullResponse,
    PipelinePhaseResult,
    PipelineDecisionView,
    PipelinePlanView,
)
from .live import (
    LiveAnalysisResponse,
    LiveDataSummaryView,
    LiveModuleView,
    LivePipelineResponse,
    LiveRunRequest,
)

__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "PaginatedResponse",
    "PaginationParams",
    "AnalysisRunRequest",
    "AnalysisRunResponse",
    "AnalysisSignalView",
    "ArbitrationRunRequest",
    "ArbitrationResponse",
    "PortfolioArbitrationRequest",
    "StrategyProposalRequest",
    "DecisionRationaleView",
    "RiskCalculateRequest",
    "PositionPlanView",
    "ExecutionPlanView",
    "AuditQueryParams",
    "AuditQueryResponse",
    "DecisionRecordView",
    "RiskAuditView",
    "FeedbackView",
    "FeedbackScanRequest",
    "FeedbackScanResponse",
    "FeedbackScanResult",
    "StrategyPoolProposeRequest",
    "StrategyPoolProposeResponse",
    "StrategyPoolDecisionBundle",
    "PipelineRunFullRequest",
    "PipelineRunFullResponse",
    "PipelinePhaseResult",
    "PipelineDecisionView",
    "PipelinePlanView",
    "LiveRunRequest",
    "LiveDataSummaryView",
    "LiveModuleView",
    "LiveAnalysisResponse",
    "LivePipelineResponse",
]
