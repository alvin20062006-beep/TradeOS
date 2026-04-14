"""
AI Trading Tool - Core Shared Module

Exports shared utilities for all modules.
"""

from ai_trading_tool.core.shared.config import (
    get_config,
    reload_config,
    AppConfig,
    ConfigLoader,
)
from ai_trading_tool.core.shared.logging import (
    get_logger,
    configure_logging,
    get_trading_logger,
    get_execution_logger,
    get_research_logger,
    get_risk_logger,
    get_audit_logger,
    get_strategy_logger,
    log_execution,
)

__all__ = [
    # Config
    "get_config",
    "reload_config",
    "AppConfig",
    "ConfigLoader",
    # Logging
    "get_logger",
    "configure_logging",
    "get_trading_logger",
    "get_execution_logger",
    "get_research_logger",
    "get_risk_logger",
    "get_audit_logger",
    "get_strategy_logger",
    "log_execution",
]
