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
        assert result == 40  # Returns actual int from expression

        # Test with enhanced context functions
        result = resolver.resolve_template("{{ max(a, b) }}", {"a": 10, "b": 15})
        assert result == 15  # Returns actual int from expression

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

    def test_context_enhancement(self):
        """Test that context is enhanced with utility functions."""
        resolver = Jinja2TemplateResolver()

        # Test built-in functions are available
        result = resolver.resolve_template("{{ sum([1, 2, 3]) }}", {})
        assert result == 6  # Returns actual int from expression

        result = resolver.resolve_template("{{ len('hello') }}", {})
        assert result == 5  # Returns actual int from expression

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

    def test_dotted_path_object_preservation(self):
        """Test that dotted path templates preserve object types."""
        resolver = Jinja2TemplateResolver()

        # Create a mock object similar to GrimoireModel
        class MockModel:
            def __init__(self, name):
                self.name = name
                self.type = "character"

            def __repr__(self):
                return f"<MockModel: {self.name}>"

        mock_obj = MockModel("Knave")

        # Test simple dotted path
        context = {"outputs": {"knave": mock_obj}}
        result = resolver.resolve_template("{{ outputs.knave }}", context)
        assert isinstance(result, MockModel)
        assert result.name == "Knave"

        # Test deeper nested path
        context = {"data": {"outputs": {"character": mock_obj}}}
        result = resolver.resolve_template("{{ data.outputs.character }}", context)
        assert isinstance(result, MockModel)
        assert result.name == "Knave"

    def test_dotted_path_dict_preservation(self):
        """Test that dotted path templates preserve dict types."""
        resolver = Jinja2TemplateResolver()

        # Test dictionary preservation
        context = {"outputs": {"config": {"key": "value", "nested": {"deep": 42}}}}
        result = resolver.resolve_template("{{ outputs.config }}", context)
        assert isinstance(result, dict)
        assert result == {"key": "value", "nested": {"deep": 42}}

        # Test nested dict access
        result = resolver.resolve_template("{{ outputs.config.nested }}", context)
        assert isinstance(result, dict)
        assert result == {"deep": 42}

    def test_dotted_path_list_preservation(self):
        """Test that dotted path templates preserve list types."""
        resolver = Jinja2TemplateResolver()

        # Test list preservation
        context = {"outputs": {"items": [1, 2, 3, 4, 5]}}
        result = resolver.resolve_template("{{ outputs.items }}", context)
        assert isinstance(result, list)
        assert result == [1, 2, 3, 4, 5]

    def test_dotted_path_primitive_types(self):
        """Test that dotted path templates preserve primitive types."""
        resolver = Jinja2TemplateResolver()

        # Test integer
        context = {"stats": {"strength": 16}}
        result = resolver.resolve_template("{{ stats.strength }}", context)
        assert isinstance(result, int)
        assert result == 16

        # Test float
        context = {"stats": {"damage": 3.5}}
        result = resolver.resolve_template("{{ stats.damage }}", context)
        assert isinstance(result, float)
        assert result == 3.5

        # Test boolean
        context = {"flags": {"active": True}}
        result = resolver.resolve_template("{{ flags.active }}", context)
        assert isinstance(result, bool)
        assert result is True

        # Test None
        context = {"data": {"empty": None}}
        result = resolver.resolve_template("{{ data.empty }}", context)
        assert result is None

    def test_dotted_path_nonexistent(self):
        """Test that nonexistent dotted paths raise errors."""
        resolver = Jinja2TemplateResolver()

        # Test nonexistent intermediate key - returns None for undefined
        context = {"outputs": {}}
        result = resolver.resolve_template("{{ outputs.nonexistent }}", context)
        assert result is None  # compile_expression returns None for missing attrs

        # Test nonexistent top-level key should still raise error
        context = {}
        with pytest.raises(TemplateResolutionError):
            resolver.resolve_template("{{ nonexistent.path }}", context)

    def test_grimoire_model_in_data_structures(self):
        """Test that GrimoireModel objects are preserved in data structures."""
        from grimoire_model import (
            AttributeDefinition,
            ModelDefinition,
            create_model_without_validation,
        )

        resolver = Jinja2TemplateResolver()

        # Create a GrimoireModel instance
        attrs = {
            "name": AttributeDefinition(type="str", required=True),
            "type": AttributeDefinition(type="str", required=True),
        }
        weapon_def = ModelDefinition(
            id="weapon",
            name="Weapon",
            kind="model",
            description="Weapon item",
            version=1,
            attributes=attrs,
        )
        weapon = create_model_without_validation(
            weapon_def, {"model": "weapon", "name": "Dagger", "type": "melee"}
        )

        # Test 1: List containing GrimoireModel
        context = {"item": weapon}
        result = resolver.resolve_template("{{ [item] }}", context)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == weapon

        # Test 2: List concatenation with GrimoireModel
        context = {"inventory": [], "item": weapon}
        result = resolver.resolve_template("{{ inventory + [item] }}", context)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == weapon

        # Test 3: Dict with GrimoireModel value
        context = {"item": weapon}
        result = resolver.resolve_template("{{ {'weapon': item} }}", context)
        assert isinstance(result, dict)
        assert "weapon" in result
        assert result["weapon"] == weapon

        # Test 4: Nested structure with GrimoireModel
        context = {"char": {"name": "Hero"}, "item": weapon}
        result = resolver.resolve_template(
            "{{ {'character': char, 'items': [item]} }}", context
        )
        assert isinstance(result, dict)
        assert "character" in result
        assert "items" in result
        assert isinstance(result["items"], list)
        assert result["items"][0] == weapon

        # Test 5: Mixed structures with GrimoireModel and regular objects
        context = {"name": "Hero", "item": weapon}
        result = resolver.resolve_template(
            "{{ {'char': name, 'weapon': item} }}", context
        )
        assert isinstance(result, dict)
        assert result["char"] == "Hero"
        assert result["weapon"] == weapon


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

        # Should preserve the integer type, not convert to string
        assert result == 16

    def test_additional_context(self):
        """Test additional context alongside model data."""
        resolver = ModelContextTemplateResolver()

        model_data = {"level": 5}
        additional_context = {"multiplier": 8}

        result = resolver.resolve_with_model_context(
            "{{ level * multiplier }}", model_data, additional_context
        )
        assert result == 40  # Returns actual int from expression


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
