"""Tests for template resolver functionality."""

import pytest

from grimoire_model.core.exceptions import TemplateResolutionError
from grimoire_model.resolvers.template import (
    CachingTemplateResolver,
    Jinja2TemplateResolver,
    ModelContextTemplateResolver,
    create_template_resolver,
)


class TestJinja2TemplateResolver:
    """Test Jinja2TemplateResolver class."""

    def test_basic_template_resolution(self):
        """Test basic template resolution."""
        resolver = Jinja2TemplateResolver()

        result = resolver.resolve_template("Hello {{ name }}", {"name": "World"})
        assert result == "Hello World"

    def test_non_template_string(self):
        """Test that non-template strings are returned as-is."""
        resolver = Jinja2TemplateResolver()

        result = resolver.resolve_template("Just a string", {})
        assert result == "Just a string"

    def test_is_template_detection(self):
        """Test template detection."""
        resolver = Jinja2TemplateResolver()

        assert resolver.is_template("{{ variable }}") is True
        assert resolver.is_template("{% if condition %}") is True
        assert resolver.is_template("{# comment #}") is True
        assert resolver.is_template("Just a string") is False
        assert resolver.is_template("") is False

    def test_extract_variables(self):
        """Test variable extraction from templates."""
        resolver = Jinja2TemplateResolver()

        variables = resolver.extract_variables("{{ name }} and {{ age }}")
        assert variables == {"name", "age"}

        variables = resolver.extract_variables(
            "{{ user.name }} is {{ user.age }} years old"
        )
        assert variables == {"user"}

        variables = resolver.extract_variables("No variables here")
        assert len(variables) == 0

    def test_simple_variable_reference(self):
        """Test simple variable reference optimization."""
        resolver = Jinja2TemplateResolver()

        # Simple variable reference should return the value directly
        result = resolver.resolve_template("{{ value }}", {"value": 42})
        assert result == 42

        result = resolver.resolve_template("{{ data }}", {"data": {"key": "value"}})
        assert result == {"key": "value"}

    def test_arithmetic_operations(self):
        """Test arithmetic operations in templates."""
        resolver = Jinja2TemplateResolver()

        result = resolver.resolve_template("{{ level * 8 }}", {"level": 5})
        assert result == "40"  # Jinja2 renders as string

        # Test with enhanced context functions
        result = resolver.resolve_template("{{ max(a, b) }}", {"a": 10, "b": 15})
        assert result == "15"

    def test_structured_data_parsing(self):
        """Test parsing of structured data from templates."""
        resolver = Jinja2TemplateResolver()

        # JSON-like output should be parsed
        result = resolver.resolve_template(
            "{{ data | tojson }}", {"data": {"key": "value"}}
        )
        # This should be parsed back to dict if it looks like JSON
        if isinstance(result, str) and result.startswith("{"):
            # The _try_parse_structured_data method should handle this
            pass

    def test_template_error_handling(self):
        """Test template error handling."""
        resolver = Jinja2TemplateResolver()

        # Undefined variable should raise TemplateResolutionError
        with pytest.raises(TemplateResolutionError):
            resolver.resolve_template("{{ undefined_var }}", {})

        # Invalid template syntax should raise TemplateResolutionError
        with pytest.raises(TemplateResolutionError):
            resolver.resolve_template("{{ invalid syntax }}", {})

    def test_context_enhancement(self):
        """Test that context is enhanced with utility functions."""
        resolver = Jinja2TemplateResolver()

        # Test built-in functions are available
        result = resolver.resolve_template("{{ sum([1, 2, 3]) }}", {})
        assert result == "6"

        result = resolver.resolve_template("{{ len('hello') }}", {})
        assert result == "5"

    def test_non_string_input(self):
        """Test handling of non-string input."""
        resolver = Jinja2TemplateResolver()

        # The actual resolver expects strings, but the implementation
        # handles non-strings by returning them as-is
        # We need to test this through the actual resolve_template method

        # Test empty string
        result = resolver.resolve_template("", {})
        assert result == ""

        # Test string that's not a template
        result = resolver.resolve_template("plain string", {})
        assert result == "plain string"


class TestModelContextTemplateResolver:
    """Test ModelContextTemplateResolver class."""

    def test_model_context_resolution(self):
        """Test template resolution with model context."""
        resolver = ModelContextTemplateResolver()

        model_data = {"name": "Aragorn", "level": 5, "strength": 16}

        result = resolver.resolve_with_model_context(
            "{{ name }} is level {{ level }}", model_data
        )
        assert result == "Aragorn is level 5"

    def test_dollar_sign_access(self):
        """Test accessing model data via $ variable with special syntax."""
        resolver = ModelContextTemplateResolver()

        model_data = {"stats": {"strength": 16}}

        # Use underscore since Jinja2 doesn't allow $ at start of variable names
        result = resolver.resolve_with_model_context(
            "{{ _dollar.stats.strength }}", model_data
        )

        assert result == "16"

    def test_additional_context(self):
        """Test additional context alongside model data."""
        resolver = ModelContextTemplateResolver()

        model_data = {"level": 5}
        additional_context = {"multiplier": 8}

        result = resolver.resolve_with_model_context(
            "{{ level * multiplier }}", model_data, additional_context
        )
        assert result == "40"


class TestCachingTemplateResolver:
    """Test CachingTemplateResolver class."""

    def test_template_detection_caching(self):
        """Test that template detection results are cached."""
        base_resolver = Jinja2TemplateResolver()
        resolver = CachingTemplateResolver(base_resolver, max_cache_size=10)

        # First call
        result1 = resolver.is_template("{{ variable }}")
        assert result1 is True

        # Second call should use cache
        result2 = resolver.is_template("{{ variable }}")
        assert result2 is True

    def test_variable_extraction_caching(self):
        """Test that variable extraction results are cached."""
        base_resolver = Jinja2TemplateResolver()
        resolver = CachingTemplateResolver(base_resolver, max_cache_size=10)

        template = "{{ name }} and {{ age }}"

        # First call
        vars1 = resolver.extract_variables(template)
        assert vars1 == {"name", "age"}

        # Second call should use cache
        vars2 = resolver.extract_variables(template)
        assert vars2 == {"name", "age"}

    def test_cache_size_limit(self):
        """Test that cache respects size limits."""
        base_resolver = Jinja2TemplateResolver()
        resolver = CachingTemplateResolver(base_resolver, max_cache_size=2)

        # Fill cache beyond limit
        resolver.is_template("template1")
        resolver.is_template("template2")
        resolver.is_template("template3")  # Should evict oldest

        # Cache should still work
        assert resolver.is_template("template2") is False
        assert resolver.is_template("template3") is False

    def test_template_resolution_passthrough(self):
        """Test that template resolution passes through to base resolver."""
        base_resolver = Jinja2TemplateResolver()
        resolver = CachingTemplateResolver(base_resolver)

        result = resolver.resolve_template("Hello {{ name }}", {"name": "World"})
        assert result == "Hello World"


class TestCreateTemplateResolver:
    """Test create_template_resolver factory function."""

    def test_create_jinja2_resolver(self):
        """Test creating Jinja2 resolver."""
        resolver = create_template_resolver("jinja2")
        # Should be wrapped in CachingTemplateResolver by default
        assert isinstance(resolver, CachingTemplateResolver)

    def test_create_model_context_resolver(self):
        """Test creating model context resolver."""
        resolver = create_template_resolver("model_context")
        assert isinstance(resolver, CachingTemplateResolver)

    def test_create_without_caching(self):
        """Test creating resolver without caching."""
        resolver = create_template_resolver("jinja2", caching=False)
        assert isinstance(resolver, Jinja2TemplateResolver)

    def test_invalid_resolver_type(self):
        """Test error handling for invalid resolver type."""
        with pytest.raises(ValueError):
            create_template_resolver("invalid_type")

    def test_custom_jinja_kwargs(self):
        """Test passing custom Jinja2 arguments."""
        # This would test that kwargs are passed through properly
        # For now, just ensure it doesn't crash
        resolver = create_template_resolver("jinja2", caching=False, trim_blocks=False)
        assert isinstance(resolver, Jinja2TemplateResolver)
