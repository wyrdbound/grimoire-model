"""
Logging utilities for wyrdbound-model.

This module provides a centralized logger for the wyrdbound-model library.
Applications can configure this logger using the standard Python logging configuration.
"""

import logging
from typing import Optional

# Library-wide logger
logger = logging.getLogger("wyrdbound_model")

# Set a default level, but applications should configure this
logger.setLevel(logging.INFO)

# If no handlers are configured by the application, add a null handler
# to prevent "No handlers could be found" warnings
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger for the wyrdbound-model library.

    Args:
        name: Optional name to append to the base logger name.
              If provided, creates a child logger like 'wyrdbound_model.core.registry'

    Returns:
        A logger instance that applications can configure.
    """
    if name:
        return logging.getLogger(f"wyrdbound_model.{name}")
    return logger
