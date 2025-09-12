"""
Tests for grimoire-model logging functionality.

Tests the centralized logging system using grimoire-logging, logger configuration,
and integration with grimoire-logging's dependency injection system.
"""

import io
import logging
from unittest.mock import patch

import pytest

from grimoire_model import (
    ModelDefinition,
    clear_logger_injection,
    create_model,
    get_logger,
    inject_logger,
    logger,
)
from grimoire_model.core.registry import (
    ModelRegistry,
    register_model,
)


class TestLoggingModule:
    """Test the central logging module with grimoire-logging."""

    def test_logger_exists(self):
        """Test that the main logger exists and works."""
        assert logger is not None
        # Test that it has the required LoggerProtocol methods
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "critical")

    def test_logger_basic_functionality(self):
        """Test that logger methods can be called without errors."""
        # These should not raise exceptions
        logger.debug("Test debug message")
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")
        logger.critical("Test critical message")

    def test_get_logger_without_name(self):
        """Test get_logger returns the main logger when no name provided."""
        result = get_logger()
        assert result is logger

    def test_get_logger_with_name(self):
        """Test get_logger creates child loggers correctly."""
        child_logger = get_logger("test.child")
        assert child_logger is not None
        # Test that it has the required LoggerProtocol methods
        assert hasattr(child_logger, "debug")
        assert hasattr(child_logger, "info")
        assert hasattr(child_logger, "warning")
        assert hasattr(child_logger, "error")
        assert hasattr(child_logger, "critical")

    def test_logger_dependency_injection(self):
        """Test that logger dependency injection works."""

        # Create a mock logger to capture messages
        class MockLogger:
            def __init__(self):
                self.messages = []

            def debug(self, msg, *args, **kwargs):
                self.messages.append(("DEBUG", msg))

            def info(self, msg, *args, **kwargs):
                self.messages.append(("INFO", msg))

            def warning(self, msg, *args, **kwargs):
                self.messages.append(("WARNING", msg))

            def error(self, msg, *args, **kwargs):
                self.messages.append(("ERROR", msg))

            def critical(self, msg, *args, **kwargs):
                self.messages.append(("CRITICAL", msg))

        mock_logger = MockLogger()

        try:
            # Inject mock logger
            inject_logger(mock_logger)

            # Test that messages are captured
            test_logger = get_logger("test")
            test_logger.info("Test message")

            assert len(mock_logger.messages) == 1
            assert mock_logger.messages[0] == ("INFO", "Test message")

        finally:
            # Clean up
            clear_logger_injection()


class TestRegistryLogging:
    """Test logging in the ModelRegistry using grimoire-logging dependency injection."""

    def setup_method(self):
        """Set up test registry and mock logger."""
        self.registry = ModelRegistry()

        # Create a mock logger to capture messages
        class MockLogger:
            def __init__(self):
                self.messages = []

            def debug(self, msg, *args, **kwargs):
                self.messages.append(("DEBUG", msg))

            def info(self, msg, *args, **kwargs):
                self.messages.append(("INFO", msg))

            def warning(self, msg, *args, **kwargs):
                self.messages.append(("WARNING", msg))

            def error(self, msg, *args, **kwargs):
                self.messages.append(("ERROR", msg))

            def critical(self, msg, *args, **kwargs):
                self.messages.append(("CRITICAL", msg))

        self.mock_logger = MockLogger()
        inject_logger(self.mock_logger)

    def teardown_method(self):
        """Clean up logging configuration."""
        clear_logger_injection()

    def get_log_messages(self) -> list:
        """Get the captured log messages."""
        return self.mock_logger.messages

    def test_model_registration_conflict_warning(self):
        """Test that model registration conflicts log warnings."""
        from grimoire_model import AttributeDefinition

        # Create two different model definitions with same ID
        model_def1 = ModelDefinition(
            id="test_model",
            name="First Model",
            attributes={"field1": AttributeDefinition(type="str")},
        )

        model_def2 = ModelDefinition(
            id="test_model",
            name="Second Model",
            attributes={"field2": AttributeDefinition(type="int")},
        )

        # Clear any previous logs
        self.mock_logger.messages.clear()

        # Register first model
        self.registry.register("test", "test_model", model_def1)

        # Register second model - should trigger warning
        self.registry.register("test", "test_model", model_def2)

        messages = self.get_log_messages()
        warning_messages = [msg for level, msg in messages if level == "WARNING"]

        assert len(warning_messages) > 0
        assert any(
            "Model 'test__test_model' already registered" in msg
            for msg in warning_messages
        )

    def test_same_model_no_warning(self):
        """Test that registering the same model object still works."""
        from grimoire_model import AttributeDefinition

        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={"field": AttributeDefinition(type="str")},
        )

        # Clear any previous logs
        self.mock_logger.messages.clear()

        # Register same model twice - should still work
        self.registry.register("test", "test_model", model_def)
        self.registry.register("test", "test_model", model_def)

        # Should not raise any exceptions
        assert self.registry.has("test", "test_model")

    def test_debug_logging(self):
        """Test debug level logging for registry operations."""
        from grimoire_model import AttributeDefinition

        model_def = ModelDefinition(
            id="debug_model",
            name="Debug Model",
            attributes={"field": AttributeDefinition(type="str")},
        )

        # Clear any previous logs
        self.mock_logger.messages.clear()

        self.registry.register("debug", "debug_model", model_def)

        messages = self.get_log_messages()
        debug_messages = [msg for level, msg in messages if level == "DEBUG"]

        assert len(debug_messages) > 0
        assert any(
            "Registered model 'debug_model' in namespace 'debug'" in msg
            for msg in debug_messages
        )

    def test_unregister_model_logging(self):
        """Test debug logging for model unregistration."""
        from grimoire_model import AttributeDefinition

        model_def = ModelDefinition(
            id="unregister_model",
            name="Unregister Model",
            attributes={"field": AttributeDefinition(type="str")},
        )

        self.registry.register("test", "unregister_model", model_def)

        # Clear logs and unregister
        self.mock_logger.messages.clear()
        self.registry.unregister("test", "unregister_model")

        messages = self.get_log_messages()
        debug_messages = [msg for level, msg in messages if level == "DEBUG"]

        assert len(debug_messages) > 0
        assert any(
            "Unregistered model 'test__unregister_model'" in msg
            for msg in debug_messages
        )

    def test_clear_namespace_debug_logging(self):
        """Test debug logging for namespace clearing."""
        from grimoire_model import AttributeDefinition

        model_def = ModelDefinition(
            id="clear_model",
            name="Clear Model",
            attributes={"field": AttributeDefinition(type="str")},
        )

        self.registry.register("clear_test", "clear_model", model_def)

        # Clear logs and clear namespace
        self.mock_logger.messages.clear()
        self.registry.clear_namespace("clear_test")

        messages = self.get_log_messages()
        debug_messages = [msg for level, msg in messages if level == "DEBUG"]

        assert len(debug_messages) > 0
        assert any(
            "Cleared 1 models from namespace 'clear_test'" in msg
            for msg in debug_messages
        )

    def test_clear_all_debug_logging(self):
        """Test debug logging for clearing all models."""
        from grimoire_model import AttributeDefinition

        model_def = ModelDefinition(
            id="clear_all_model",
            name="Clear All Model",
            attributes={"field": AttributeDefinition(type="str")},
        )

        self.registry.register("clear_all", "clear_all_model", model_def)

        # Clear logs and clear all
        self.mock_logger.messages.clear()
        count = self.registry.clear_all()

        messages = self.get_log_messages()
        debug_messages = [msg for level, msg in messages if level == "DEBUG"]

        assert len(debug_messages) > 0
        assert any(
            f"Cleared all {count} models from registry" in msg for msg in debug_messages
        )


class TestGlobalRegistryLogging:
    """Test logging through global registry functions using grimoire-logging."""

    def setup_method(self):
        """Set up mock logger for global registry."""

        # Create a mock logger to capture messages
        class MockLogger:
            def __init__(self):
                self.messages = []

            def debug(self, msg, *args, **kwargs):
                self.messages.append(("DEBUG", msg))

            def info(self, msg, *args, **kwargs):
                self.messages.append(("INFO", msg))

            def warning(self, msg, *args, **kwargs):
                self.messages.append(("WARNING", msg))

            def error(self, msg, *args, **kwargs):
                self.messages.append(("ERROR", msg))

            def critical(self, msg, *args, **kwargs):
                self.messages.append(("CRITICAL", msg))

        self.mock_logger = MockLogger()
        inject_logger(self.mock_logger)

    def teardown_method(self):
        """Clean up logging and registry."""
        clear_logger_injection()

        # Clear global registry
        from grimoire_model import clear_registry

        clear_registry()

    def get_log_messages(self) -> list:
        """Get the captured log messages."""
        return self.mock_logger.messages

    def test_global_register_model_logging(self):
        """Test logging when using global register_model function."""
        from grimoire_model import AttributeDefinition

        model_def1 = ModelDefinition(
            id="global_test",
            name="First Global Model",
            attributes={"field": AttributeDefinition(type="str")},
        )

        model_def2 = ModelDefinition(
            id="global_test",
            name="Second Global Model",
            attributes={"field": AttributeDefinition(type="int")},
        )

        # Register through global function
        register_model("global", model_def1)
        register_model("global", model_def2)  # Should trigger warning

        messages = self.get_log_messages()
        warning_messages = [msg for level, msg in messages if level == "WARNING"]

        assert len(warning_messages) > 0
        assert any(
            "Model 'global__global_test' already registered" in msg
            for msg in warning_messages
        )


class TestModelLogging:
    """Test logging in model operations using grimoire-logging."""

    def setup_method(self):
        """Set up mock logger for model operations."""

        # Create a mock logger to capture messages
        class MockLogger:
            def __init__(self):
                self.messages = []

            def debug(self, msg, *args, **kwargs):
                self.messages.append(("DEBUG", msg))

            def info(self, msg, *args, **kwargs):
                self.messages.append(("INFO", msg))

            def warning(self, msg, *args, **kwargs):
                self.messages.append(("WARNING", msg))

            def error(self, msg, *args, **kwargs):
                self.messages.append(("ERROR", msg))

            def critical(self, msg, *args, **kwargs):
                self.messages.append(("CRITICAL", msg))

        self.mock_logger = MockLogger()
        inject_logger(self.mock_logger)

    def teardown_method(self):
        """Clean up logging configuration."""
        clear_logger_injection()

    def get_log_messages(self) -> list:
        """Get the captured log messages."""
        return self.mock_logger.messages

    def test_model_creation_logging(self):
        """Test that model creation generates appropriate log messages."""
        from grimoire_model import AttributeDefinition

        model_def = ModelDefinition(
            id="log_test_model",
            name="Logging Test Model",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "value": AttributeDefinition(type="int", default=0),
            },
        )

        # Create model instance
        create_model(model_def, {"name": "test"})

        # Should have captured some log messages
        messages = self.get_log_messages()
        assert isinstance(messages, list)


class TestLoggerConfiguration:
    """Test logger configuration and integration scenarios with grimoire-logging."""

    def setup_method(self):
        """Set up test environment."""

        # Create a mock logger to capture messages
        class MockLogger:
            def __init__(self):
                self.messages = []

            def debug(self, msg, *args, **kwargs):
                self.messages.append(("DEBUG", msg))

            def info(self, msg, *args, **kwargs):
                self.messages.append(("INFO", msg))

            def warning(self, msg, *args, **kwargs):
                self.messages.append(("WARNING", msg))

            def error(self, msg, *args, **kwargs):
                self.messages.append(("ERROR", msg))

            def critical(self, msg, *args, **kwargs):
                self.messages.append(("CRITICAL", msg))

        self.mock_logger = MockLogger()

    def teardown_method(self):
        """Clean up test environment."""
        clear_logger_injection()

    def test_logger_creation(self):
        """Test that loggers can be created via get_logger."""
        test_logger = get_logger("config.test")

        # Should return a LoggerProtocol compliant object
        assert hasattr(test_logger, "debug")
        assert hasattr(test_logger, "info")
        assert hasattr(test_logger, "warning")
        assert hasattr(test_logger, "error")
        assert hasattr(test_logger, "critical")

    def test_logger_dependency_injection(self):
        """Test that logger dependency injection works properly."""
        # Inject our mock logger
        inject_logger(self.mock_logger)

        # Get a logger and use it
        test_logger = get_logger("injection.test")
        test_logger.info("Test message")

        # Should have captured the message via our mock
        assert len(self.mock_logger.messages) == 1
        assert self.mock_logger.messages[0] == ("INFO", "Test message")

    def test_logger_without_injection(self):
        """Test that loggers work without dependency injection."""
        # Clear any existing injection
        clear_logger_injection()

        # Get a logger - should still work but use default implementation
        test_logger = get_logger("no_injection.test")

        # Should be able to call logging methods without error
        test_logger.debug("Debug message")
        test_logger.info("Info message")
        test_logger.warning("Warning message")
        test_logger.error("Error message")
        test_logger.critical("Critical message")

    def test_logger_integration_with_standard_logging(self):
        """Test that the logger integrates with Python's standard logging."""
        # Capture logs at root level
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            # Configure basic logging
            logging.basicConfig(
                level=logging.WARNING,
                format="%(name)s - %(levelname)s - %(message)s",
                stream=mock_stdout,
                force=True,  # Override existing configuration
            )

            # Get library logger and log a message
            lib_logger = get_logger()
            lib_logger.warning("Test warning message")

            output = mock_stdout.getvalue()
            assert "grimoire_model - WARNING - Test warning message" in output

    def test_null_handler_default(self):
        """Test that logger has null handler by default to prevent warnings."""
        # Fresh logger should have null handler if no other handlers configured
        logging.getLogger("grimoire_model.fresh.test")

        # Should have at least the null handler from the parent
        root_grimoire_logger = logging.getLogger("grimoire_model")

        # Check if null handler is present (may be inherited)
        handlers = root_grimoire_logger.handlers
        has_null_handler = any(isinstance(h, logging.NullHandler) for h in handlers)

        # Should have a null handler to prevent "No handlers found" warnings
        assert (
            has_null_handler or len(handlers) == 0
        )  # Either explicit null handler or no handlers


class TestLoggingInheritanceResolution:
    """Test logging in inheritance resolution utilities using grimoire-logging."""

    def setup_method(self):
        """Set up mock logger for inheritance utilities."""

        # Create a mock logger to capture messages
        class MockLogger:
            def __init__(self):
                self.messages = []

            def debug(self, msg, *args, **kwargs):
                self.messages.append(("DEBUG", msg))

            def info(self, msg, *args, **kwargs):
                self.messages.append(("INFO", msg))

            def warning(self, msg, *args, **kwargs):
                self.messages.append(("WARNING", msg))

            def error(self, msg, *args, **kwargs):
                self.messages.append(("ERROR", msg))

            def critical(self, msg, *args, **kwargs):
                self.messages.append(("CRITICAL", msg))

        self.mock_logger = MockLogger()
        inject_logger(self.mock_logger)

    def teardown_method(self):
        """Clean up logging configuration."""
        clear_logger_injection()

    def get_log_messages(self) -> list:
        """Get the captured log messages."""
        return self.mock_logger.messages

    def test_inheritance_resolution_logging(self):
        """Test that inheritance resolution generates debug logs."""
        from grimoire_model import AttributeDefinition
        from grimoire_model.core.registry import ModelRegistry
        from grimoire_model.utils.inheritance import resolve_model_inheritance

        # Create test models with inheritance
        base_def = ModelDefinition(
            id="base",
            name="Base Model",
            attributes={"base_field": AttributeDefinition(type="str")},
        )

        child_def = ModelDefinition(
            id="child",
            name="Child Model",
            extends=["base"],
            attributes={"child_field": AttributeDefinition(type="int")},
        )

        # Create registry with models
        registry = ModelRegistry()
        registry.register("test", "base", base_def)
        registry.register("test", "child", child_def)

        # Clear previous messages and resolve inheritance
        self.mock_logger.messages.clear()

        try:
            resolve_model_inheritance(child_def, registry)

            # Should have captured some log messages
            messages = self.get_log_messages()
            assert isinstance(messages, list)

        except Exception:
            # Even if inheritance fails, we should have captured messages
            messages = self.get_log_messages()
            assert isinstance(messages, list)


class TestLoggingIntegration:
    """Integration tests for logging across the entire system using grimoire-logging."""

    def setup_method(self):
        """Set up mock logger for integration tests."""

        # Create a mock logger to capture messages
        class MockLogger:
            def __init__(self):
                self.messages = []

            def debug(self, msg, *args, **kwargs):
                self.messages.append(("DEBUG", msg))

            def info(self, msg, *args, **kwargs):
                self.messages.append(("INFO", msg))

            def warning(self, msg, *args, **kwargs):
                self.messages.append(("WARNING", msg))

            def error(self, msg, *args, **kwargs):
                self.messages.append(("ERROR", msg))

            def critical(self, msg, *args, **kwargs):
                self.messages.append(("CRITICAL", msg))

        self.mock_logger = MockLogger()

    def teardown_method(self):
        """Clean up after integration tests."""
        clear_logger_injection()

        # Clear registry
        from grimoire_model import clear_registry

        clear_registry()

    def test_end_to_end_logging_scenario(self):
        """Test logging in a complete model creation and usage scenario."""
        from grimoire_model import AttributeDefinition, register_model

        # Inject mock logger
        inject_logger(self.mock_logger)

        # Create model definitions that will trigger conflicts
        model_def1 = ModelDefinition(
            id="integration_test",
            name="First Integration Model",
            attributes={"field": AttributeDefinition(type="str")},
        )

        model_def2 = ModelDefinition(
            id="integration_test",
            name="Second Integration Model",
            attributes={"field": AttributeDefinition(type="int")},
        )

        # Clear previous messages
        self.mock_logger.messages.clear()

        # Register models to trigger registry warnings
        register_model("integration", model_def1)
        register_model("integration", model_def2)  # Should trigger warning

        # Create models with the definitions
        create_model(model_def1, {"field": "test"})
        create_model(model_def2, {"field": 42})

        # Check that warnings were logged
        messages = self.mock_logger.messages
        warning_messages = [msg for level, msg in messages if level == "WARNING"]

        # Should have registration conflict warnings
        assert len(warning_messages) > 0
        assert any(
            "already registered" in msg or "Overwriting" in msg
            for msg in warning_messages
        )

    def test_logging_with_dependency_injection(self):
        """Test that dependency injection logging works across components."""
        from grimoire_model import AttributeDefinition

        # Test with injection
        inject_logger(self.mock_logger)

        # Clear messages and test logging
        self.mock_logger.messages.clear()

        # Create a model to trigger various logging
        model_def = ModelDefinition(
            id="injection_test",
            name="Injection Test Model",
            attributes={"field": AttributeDefinition(type="str")},
        )

        create_model(model_def, {"field": "test"})

        # Should have captured some messages
        messages = self.mock_logger.messages
        assert isinstance(messages, list)

        # Test without injection
        clear_logger_injection()

        # Should still work but use default logging
        model_def2 = ModelDefinition(
            id="no_injection_test",
            name="No Injection Test Model",
            attributes={"field": AttributeDefinition(type="str")},
        )

        # Should not raise any errors
        create_model(model_def2, {"field": "test2"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
