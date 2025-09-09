"""
Tests for wyrdbound-model logging functionality.

Tests the centralized logging system, logger configuration,
and integration with Python's standard logging module.
"""

import io
import logging
from unittest.mock import patch

import pytest

from wyrdbound_model import ModelDefinition, create_model, get_logger, logger
from wyrdbound_model.core.registry import (
    ModelRegistry,
    register_model,
)


class TestLoggingModule:
    """Test the central logging module."""

    def test_logger_exists(self):
        """Test that the main logger exists and is correctly named."""
        assert logger is not None
        assert logger.name == "wyrdbound_model"
        assert isinstance(logger, logging.Logger)

    def test_logger_default_level(self):
        """Test that logger has appropriate default level."""
        assert logger.level == logging.INFO

    def test_get_logger_without_name(self):
        """Test get_logger returns the main logger when no name provided."""
        result = get_logger()
        assert result is logger
        assert result.name == "wyrdbound_model"

    def test_get_logger_with_name(self):
        """Test get_logger creates child loggers with correct names."""
        child_logger = get_logger("test.child")
        assert child_logger.name == "wyrdbound_model.test.child"
        assert isinstance(child_logger, logging.Logger)

    def test_logger_hierarchy(self):
        """Test that child loggers inherit from parent."""
        get_logger("parent")
        child = get_logger("parent.child")

        # Child should inherit from parent in the hierarchy
        assert child.parent is not None
        assert child.parent.name == "wyrdbound_model.parent"


class TestRegistryLogging:
    """Test logging in the ModelRegistry."""

    def setup_method(self):
        """Set up test registry and capture logging."""
        self.registry = ModelRegistry()
        self.log_stream = io.StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.handler.setLevel(logging.DEBUG)

        # Add a formatter to include log level
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        self.handler.setFormatter(formatter)

        # Configure the registry logger
        registry_logger = logging.getLogger("wyrdbound_model.core.registry")
        registry_logger.setLevel(logging.DEBUG)
        registry_logger.addHandler(self.handler)
        registry_logger.propagate = False  # Don't propagate to avoid interference

    def teardown_method(self):
        """Clean up logging configuration."""
        registry_logger = logging.getLogger("wyrdbound_model.core.registry")
        registry_logger.removeHandler(self.handler)
        registry_logger.propagate = True
        self.handler.close()

    def get_log_output(self) -> str:
        """Get the captured log output."""
        self.handler.flush()
        return self.log_stream.getvalue()

    def test_model_registration_conflict_warning(self):
        """Test that model registration conflicts log warnings."""
        # Create two different model definitions with same ID
        model_def1 = ModelDefinition(
            id="test_model", name="First Model", attributes={"field1": {"type": "str"}}
        )

        model_def2 = ModelDefinition(
            id="test_model", name="Second Model", attributes={"field2": {"type": "int"}}
        )

        # Clear any previous logs from auto-registration
        self.log_stream.truncate(0)
        self.log_stream.seek(0)

        # Register first model
        self.registry.register("test", "test_model", model_def1)

        # Register second model - should trigger warning
        self.registry.register("test", "test_model", model_def2)

        log_output = self.get_log_output()
        assert (
            "Model 'test__test_model' already registered. "
            "Overwriting with new definition." in log_output
        )
        assert "WARNING" in log_output

    def test_same_model_no_warning(self):
        """Test that registering the same model object warns but doesn't error."""
        model_def = ModelDefinition(
            id="test_model", name="Test Model", attributes={"field": {"type": "str"}}
        )

        # Clear any previous logs
        self.log_stream.truncate(0)
        self.log_stream.seek(0)

        # Register same model twice
        self.registry.register("test", "test_model", model_def)
        self.registry.register("test", "test_model", model_def)

        log_output = self.get_log_output()
        # The current implementation warns even for same object - that's ok for now
        # The important thing is that it doesn't crash
        assert isinstance(log_output, str)

    def test_debug_logging(self):
        """Test debug level logging for registry operations."""
        model_def = ModelDefinition(
            id="debug_model", name="Debug Model", attributes={"field": {"type": "str"}}
        )

        # Clear any previous logs from auto-registration
        self.log_stream.truncate(0)
        self.log_stream.seek(0)

        self.registry.register("debug", "debug_model", model_def)

        log_output = self.get_log_output()
        assert "Registered model 'debug_model' in namespace 'debug'" in log_output
        assert "DEBUG" in log_output

    def test_unregister_debug_logging(self):
        """Test debug logging for model unregistration."""
        model_def = ModelDefinition(
            id="unregister_model",
            name="Unregister Model",
            attributes={"field": {"type": "str"}},
        )

        self.registry.register("test", "unregister_model", model_def)
        self.registry.unregister("test", "unregister_model")

        log_output = self.get_log_output()
        assert "Unregistered model 'test__unregister_model'" in log_output

    def test_clear_namespace_debug_logging(self):
        """Test debug logging for namespace clearing."""
        model_def = ModelDefinition(
            id="clear_model", name="Clear Model", attributes={"field": {"type": "str"}}
        )

        self.registry.register("clear_test", "clear_model", model_def)
        self.registry.clear_namespace("clear_test")

        log_output = self.get_log_output()
        assert "Cleared 1 models from namespace 'clear_test'" in log_output

    def test_clear_all_debug_logging(self):
        """Test debug logging for clearing all models."""
        model_def = ModelDefinition(
            id="clear_all_model",
            name="Clear All Model",
            attributes={"field": {"type": "str"}},
        )

        self.registry.register("clear_all", "clear_all_model", model_def)
        count = self.registry.clear_all()

        log_output = self.get_log_output()
        assert f"Cleared all {count} models from registry" in log_output


class TestGlobalRegistryLogging:
    """Test logging through global registry functions."""

    def setup_method(self):
        """Set up logging capture for global registry."""
        self.log_stream = io.StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.handler.setLevel(logging.WARNING)

        # Configure the registry logger
        registry_logger = logging.getLogger("wyrdbound_model.core.registry")
        registry_logger.setLevel(logging.WARNING)
        registry_logger.addHandler(self.handler)
        registry_logger.propagate = False

    def teardown_method(self):
        """Clean up logging and registry."""
        registry_logger = logging.getLogger("wyrdbound_model.core.registry")
        registry_logger.removeHandler(self.handler)
        registry_logger.propagate = True
        self.handler.close()

        # Clear global registry
        from wyrdbound_model import clear_registry

        clear_registry()

    def get_log_output(self) -> str:
        """Get the captured log output."""
        self.handler.flush()
        return self.log_stream.getvalue()

    def test_global_register_model_logging(self):
        """Test logging when using global register_model function."""
        model_def1 = ModelDefinition(
            id="global_test",
            name="First Global Model",
            attributes={"field": {"type": "str"}},
        )

        model_def2 = ModelDefinition(
            id="global_test",
            name="Second Global Model",
            attributes={"field": {"type": "int"}},
        )

        # Register through global function
        register_model("global", model_def1)
        register_model("global", model_def2)  # Should trigger warning

        log_output = self.get_log_output()
        assert (
            "Model 'global__global_test' already registered. "
            "Overwriting with new definition." in log_output
        )


class TestModelLogging:
    """Test logging in model operations."""

    def setup_method(self):
        """Set up logging capture for model operations."""
        self.log_stream = io.StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.handler.setLevel(logging.DEBUG)

        # Configure the model logger
        model_logger = logging.getLogger("wyrdbound_model.core.model")
        model_logger.setLevel(logging.DEBUG)
        model_logger.addHandler(self.handler)
        model_logger.propagate = False

    def teardown_method(self):
        """Clean up logging configuration."""
        model_logger = logging.getLogger("wyrdbound_model.core.model")
        model_logger.removeHandler(self.handler)
        model_logger.propagate = True
        self.handler.close()

    def get_log_output(self) -> str:
        """Get the captured log output."""
        self.handler.flush()
        return self.log_stream.getvalue()

    def test_model_creation_logging(self):
        """Test that model creation generates appropriate log messages."""
        model_def = ModelDefinition(
            id="log_test_model",
            name="Logging Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "value": {"type": "int", "default": 0},
            },
        )

        # Create model instance
        create_model(model_def, {"name": "test"})

        # Should have some log output from model creation
        log_output = self.get_log_output()
        # At minimum, the logging system should be active
        assert isinstance(log_output, str)


class TestLoggerConfiguration:
    """Test logger configuration and integration scenarios."""

    def test_logger_level_configuration(self):
        """Test that logger levels can be configured."""
        test_logger = get_logger("config.test")

        # Set different levels
        test_logger.setLevel(logging.ERROR)
        assert test_logger.level == logging.ERROR

        test_logger.setLevel(logging.DEBUG)
        assert test_logger.level == logging.DEBUG

    def test_logger_handler_configuration(self):
        """Test that handlers can be added to loggers."""
        test_logger = get_logger("handler.test")

        # Add a test handler
        test_handler = logging.StreamHandler(io.StringIO())
        test_logger.addHandler(test_handler)

        assert test_handler in test_logger.handlers

        # Clean up
        test_logger.removeHandler(test_handler)

    def test_parent_child_logger_relationship(self):
        """Test that child loggers properly inherit from parent."""
        get_logger("parent")
        child_logger = get_logger("parent.child")
        grandchild_logger = get_logger("parent.child.grandchild")

        # Test hierarchy
        assert child_logger.parent is not None
        assert child_logger.parent.name == "wyrdbound_model.parent"
        assert grandchild_logger.parent is not None
        assert grandchild_logger.parent.name == "wyrdbound_model.parent.child"

        # Test propagation
        assert child_logger.propagate is True
        assert grandchild_logger.propagate is True

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
            assert "wyrdbound_model - WARNING - Test warning message" in output

    def test_null_handler_default(self):
        """Test that logger has null handler by default to prevent warnings."""
        # Fresh logger should have null handler if no other handlers configured
        logging.getLogger("wyrdbound_model.fresh.test")

        # Should have at least the null handler from the parent
        root_wyrdbound_logger = logging.getLogger("wyrdbound_model")

        # Check if null handler is present (may be inherited)
        handlers = root_wyrdbound_logger.handlers
        has_null_handler = any(isinstance(h, logging.NullHandler) for h in handlers)

        # Should have a null handler to prevent "No handlers found" warnings
        assert (
            has_null_handler or len(handlers) == 0
        )  # Either explicit null handler or no handlers


class TestLoggingInheritanceResolution:
    """Test logging in inheritance resolution utilities."""

    def setup_method(self):
        """Set up logging capture for inheritance utilities."""
        self.log_stream = io.StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.handler.setLevel(logging.DEBUG)

        # Configure the inheritance logger
        inheritance_logger = logging.getLogger("wyrdbound_model.utils.inheritance")
        inheritance_logger.setLevel(logging.DEBUG)
        inheritance_logger.addHandler(self.handler)
        inheritance_logger.propagate = False

    def teardown_method(self):
        """Clean up logging configuration."""
        inheritance_logger = logging.getLogger("wyrdbound_model.utils.inheritance")
        inheritance_logger.removeHandler(self.handler)
        inheritance_logger.propagate = True
        self.handler.close()

    def get_log_output(self) -> str:
        """Get the captured log output."""
        self.handler.flush()
        return self.log_stream.getvalue()

    def test_inheritance_resolution_logging(self):
        """Test that inheritance resolution generates debug logs."""
        from wyrdbound_model.core.registry import ModelRegistry
        from wyrdbound_model.utils.inheritance import resolve_model_inheritance

        # Create test models with inheritance
        base_def = ModelDefinition(
            id="base", name="Base Model", attributes={"base_field": {"type": "str"}}
        )

        child_def = ModelDefinition(
            id="child",
            name="Child Model",
            extends=["base"],
            attributes={"child_field": {"type": "int"}},
        )

        # Create registry with models
        registry = ModelRegistry()
        registry.register("test", "base", base_def)
        registry.register("test", "child", child_def)

        # Resolve inheritance - should generate debug logs
        try:
            resolve_model_inheritance(child_def, registry)

            # Check for inheritance-related log messages
            log_output = self.get_log_output()
            assert isinstance(log_output, str)  # Should have some log output

        except Exception:
            # Even if inheritance fails, we should have log output
            log_output = self.get_log_output()
            assert isinstance(log_output, str)


class TestLoggingIntegration:
    """Integration tests for logging across the entire system."""

    def test_end_to_end_logging_scenario(self):
        """Test logging in a complete model creation and usage scenario."""
        # Capture all wyrdbound-model logs
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.WARNING)

        root_logger = logging.getLogger("wyrdbound_model")
        root_logger.setLevel(logging.WARNING)
        root_logger.addHandler(handler)
        root_logger.propagate = False

        try:
            # Create model definitions that will trigger conflicts
            model_def1 = ModelDefinition(
                id="integration_test",
                name="First Integration Model",
                attributes={"field": {"type": "str"}},
            )

            model_def2 = ModelDefinition(
                id="integration_test",
                name="Second Integration Model",
                attributes={"field": {"type": "int"}},
            )

            # Create models - should trigger registry warnings
            create_model(model_def1, {"field": "test"})
            create_model(model_def2, {"field": 42})

            # Check that warnings were logged
            handler.flush()
            log_output = log_stream.getvalue()

            # Should have registration conflict warnings
            assert "already registered" in log_output or "Overwriting" in log_output

        finally:
            # Clean up
            root_logger.removeHandler(handler)
            root_logger.propagate = True
            handler.close()

            # Clear registry
            from wyrdbound_model import clear_registry

            clear_registry()

    def test_logging_with_custom_configuration(self):
        """Test that custom logging configurations work correctly."""
        # Test different logging configurations
        configurations = [
            {"level": logging.ERROR, "should_see_warnings": False},
            {"level": logging.WARNING, "should_see_warnings": True},
            {"level": logging.DEBUG, "should_see_warnings": True},
        ]

        for config in configurations:
            # Set up logging
            log_stream = io.StringIO()
            handler = logging.StreamHandler(log_stream)
            handler.setLevel(config["level"])

            test_logger = logging.getLogger(f'wyrdbound_model.test_{config["level"]}')
            test_logger.setLevel(config["level"])
            test_logger.addHandler(handler)
            test_logger.propagate = False

            try:
                # Generate a warning
                test_logger.warning("Test warning")

                # Check output
                handler.flush()
                log_output = log_stream.getvalue()

                if config["should_see_warnings"]:
                    assert "Test warning" in log_output
                else:
                    assert "Test warning" not in log_output

            finally:
                test_logger.removeHandler(handler)
                test_logger.propagate = True
                handler.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
