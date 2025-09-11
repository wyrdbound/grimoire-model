"""
Injectable logging utilities for grimoire-model.

This module provides a logger interface that can be injected into components,
allowing users to provide their own logger implementations or use the default.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol


class LoggerProtocol(Protocol):
    """Protocol defining the logger interface for grimoire-model components."""

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        ...

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        ...

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        ...

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message."""
        ...

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a critical message."""
        ...


class StandardLogger:
    """Default logger implementation using Python's standard logging module.

    This adapter allows any Python logger to be used with grimoire-model components.
    """

    def __init__(
        self, logger: logging.Logger | None = None, name: str = "grimoire_model"
    ) -> None:
        """Initialize with an optional Python logger.

        Args:
            logger: Python logger instance. If None, creates a new logger with the
                given name.
            name: Name for the logger if logger is None.
        """
        self._logger = logger or logging.getLogger(name)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        self._logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message."""
        self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a critical message."""
        self._logger.critical(message, *args, **kwargs)


class NullLogger:
    """A no-op logger that discards all log messages.

    Useful for testing or when logging is not desired.
    """

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Discard debug message."""
        pass

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Discard info message."""
        pass

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Discard warning message."""
        pass

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Discard error message."""
        pass

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Discard critical message."""
        pass


def create_default_logger(name: str = "grimoire_model") -> LoggerProtocol:
    """Create a default logger instance.

    Args:
        name: Name for the logger

    Returns:
        A StandardLogger instance using Python's logging module
    """
    return StandardLogger(name=name)


def create_null_logger() -> LoggerProtocol:
    """Create a null logger that discards all messages.

    Returns:
        A NullLogger instance
    """
    return NullLogger()
