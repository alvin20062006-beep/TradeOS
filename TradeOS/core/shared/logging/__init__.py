"""
Unified Logging System for TradeOS

Provides structured logging with JSON output for production,
text output for development, and per-module level control.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import structlog
from structlog.types import Processor

from core.shared.config import get_config


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# LOG LEVELS
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# STRUCTLOG PROCESSORS
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def add_timestamp(logger, method_name, event_dict):
    """Add ISO timestamp to log entries."""
    from datetime import datetime
    event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return event_dict


def rename_event_key(logger, method_name, event_dict):
    """Rename 'event' to 'message' for clarity."""
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


def add_log_level(logger, method_name, event_dict):
    """Add log level to event dict."""
    event_dict["level"] = method_name.upper()
    return event_dict


def add_service_info(logger, method_name, event_dict):
    """Add service identification."""
    event_dict["service"] = "ai-trading-tool"
    event_dict["version"] = "0.1.0"
    return event_dict


def add_execution_context(logger, method_name, event_dict):
    """Add execution context (symbol, decision_id, etc.) if present."""
    # Extract common trading context
    for key in ["symbol", "decision_id", "order_id", "strategy", "regime"]:
        if key in event_dict:
            event_dict[f"ctx_{key}"] = event_dict.pop(key)
    return event_dict


def filter_by_level(logger, method_name, event_dict):
    """Filter logs by configured level."""
    cfg = get_config()
    level = LOG_LEVELS.get(cfg.logging.level, logging.INFO)
    
    if method_name == "warning":
        return event_dict if level <= logging.WARNING else None
    elif method_name == "error":
        return event_dict if level <= logging.ERROR else None
    elif method_name == "critical":
        return event_dict if level <= logging.CRITICAL else None
    
    return event_dict


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# FORMATTING
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def get_console_renderer():
    """Get console (text) renderer for development."""
    from structlog.dev import ConsoleRenderer
    
    return ConsoleRenderer(
        colors=True,
        exception_formatter=structlog.dev.plain_traceback,
        force_colors=False,
    )


def get_json_renderer():
    """Get JSON renderer for production."""
    return structlog.processors.JSONRenderer()


def get_markdown_renderer():
    """Get markdown renderer for logging to files."""
    from structlog.dev import ConsoleRenderer
    
    return ConsoleRenderer(
        colors=False,
        exception_formatter=structlog.dev.plain_traceback,
        force_colors=False,
    )


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# LOGGING CONFIGURATION
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def configure_logging(
    level: Optional[str] = None,
    format_type: Optional[str] = None,
    log_dir: Optional[Path] = None,
) -> structlog.BoundLogger:
    """
    Configure structlog with appropriate processors and renderers.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format_type: Output format (json, text, markdown)
        log_dir: Directory for log files
    
    Returns:
        Configured structlog logger
    """
    # Get config
    cfg = get_config()
    
    level = level or cfg.logging.level
    format_type = format_type or cfg.logging.format
    log_dir = log_dir or cfg.logging.log_dir or Path("logs")
    
    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine renderer
    if format_type == "json":
        renderer = get_json_renderer()
    elif format_type == "markdown":
        renderer = get_markdown_renderer()
    else:
        renderer = get_console_renderer()
    
    # Build processor chain
    processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        add_execution_context,
        rename_event_key,
    ]
    
    if format_type == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(get_console_renderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=LOG_LEVELS.get(level.upper(), logging.INFO),
    )
    
    # Set specific levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # File logging for production
    if format_type == "json" or format_type == "markdown":
        file_handler = logging.FileHandler(log_dir / "ai-trading-tool.log")
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logging.getLogger().addHandler(file_handler)
    
    return structlog.get_logger()


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# LOGGERS
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured structlog logger
    
    Example:
        logger = get_logger(__name__)
        logger.info("Processing", symbol="AAPL", quantity=100)
    """
    logger = structlog.get_logger(name)
    
    # Attach config-based level filtering
    cfg = get_config()
    logger = logger.bind(log_level=cfg.logging.level)
    
    return logger


# Specialized loggers for different components
def get_trading_logger() -> structlog.BoundLogger:
    """Logger for trading operations."""
    return get_logger("trading")


def get_execution_logger() -> structlog.BoundLogger:
    """Logger for order execution."""
    return get_logger("execution")


def get_research_logger() -> structlog.BoundLogger:
    """Logger for research operations."""
    return get_logger("research")


def get_risk_logger() -> structlog.BoundLogger:
    """Logger for risk events."""
    return get_logger("risk")


def get_audit_logger() -> structlog.BoundLogger:
    """Logger for audit events."""
    return get_logger("audit")


def get_strategy_logger(strategy_name: str) -> structlog.BoundLogger:
    """Logger for a specific strategy."""
    return get_logger(f"strategy.{strategy_name}")


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# CONTEXT MANAGERS
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

class log_execution:
    """Context manager for logging execution blocks."""
    
    def __init__(
        self,
        logger: structlog.BoundLogger,
        operation: str,
        **context,
    ):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = __import__("time").time()
        self.logger.info(
            f"{self.operation}_start",
            **self.context,
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = __import__("time").time() - self.start_time
        
        if exc_type is not None:
            self.logger.error(
                f"{self.operation}_failed",
                duration_ms=round(duration * 1000),
                error=str(exc_val),
                error_type=exc_type.__name__,
                **self.context,
            )
        else:
            self.logger.info(
                f"{self.operation}_completed",
                duration_ms=round(duration * 1000),
                **self.context,
            )
        
        return False  # Don't suppress exceptions

