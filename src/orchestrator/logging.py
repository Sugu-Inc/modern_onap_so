"""
Structured logging configuration.

Provides centralized logging setup using structlog for structured logging.
"""

import logging
import sys
from typing import Any

import structlog

from orchestrator.config import settings


def setup_logging() -> structlog.BoundLogger:
    """
    Setup structured logging with structlog.

    Configures processors, formatters, and output based on settings.

    Returns:
        Configured logger instance
    """
    # Configure log level
    log_level = getattr(logging, settings.log_level.upper())

    # Common processors
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Add format-specific processors
    if settings.log_format == "json":
        # JSON output for production
        processors.extend(
            [
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ]
        )
    else:
        # Console-friendly output for development
        processors.extend(
            [
                structlog.dev.set_exc_info,
                structlog.dev.ConsoleRenderer(colors=True),
            ]
        )

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
        level=log_level,
    )

    # Return configured logger
    return structlog.get_logger()


# Global logger instance
logger = setup_logging()
