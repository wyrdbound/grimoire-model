"""
Logging utilities for grimoire-model.

This module provides a centralized logger for the grimoire-model library using
grimoire-logging for flexible dependency injection support.
Applications can inject custom logger implementations or configure standard logging.
"""

from typing import Optional

from grimoire_logging import (  # type: ignore[import-untyped]
    LoggerProtocol,
    clear_logger_injection,
    inject_logger,
)
from grimoire_logging import get_logger as _get_logger  # type: ignore[import-untyped]

# Library-wide logger using grimoire-logging
logger = _get_logger("grimoire_model")


def get_logger(name: Optional[str] = None) -> LoggerProtocol:
    """
    Get a logger for the grimoire-model library.

    Args:
        name: Optional name to append to the base logger name.
              If provided, creates a child logger like 'grimoire_model.core.registry'

    Returns:
        A logger instance that applications can configure through grimoire-logging.
    """
    if name:
        return _get_logger(f"grimoire_model.{name}")
    return logger


# Re-export grimoire-logging functions for convenience
__all__ = ["logger", "get_logger", "inject_logger", "clear_logger_injection"]
