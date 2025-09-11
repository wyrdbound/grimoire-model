"""Tests for derived field dependency management."""

from typing import Set
from unittest.mock import Mock

import pytest

from grimoire_model.core.exceptions import DependencyError, TemplateResolutionError
from grimoire_model.resolvers.derived import (
    BatchedDerivedFieldResolver,
    DependencyInfo,
    DerivedFieldResolver,
    ObservableValue,
    create_derived_field_resolver,
)


class MockTemplateResolver:
    """Mock template resolver for testing."""

    def __init__(self, template_map=None, variable_map=None):
        """Initialize with optional template and variable mappings."""
        self.template_map = template_map or {}
        self.variable_map = variable_map or {}

    def resolve_template(self, template_str: str, context: dict) -> str:
        """Resolve template using predefined mappings."""
        if template_str in self.template_map:
            return self.template_map[template_str]

        # Simple variable substitution for testing
        result = template_str
        for key, value in context.items():
            if isinstance(value, dict):
                continue  # Skip nested objects for simple substitution
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    def extract_variables(self, template_str: str) -> Set[str]:
        """Extract variable names from template."""
        if template_str in self.variable_map:
            return self.variable_map[template_str]

        # Simple regex-based extraction for testing
        import re

        variables = set()

        # Find {{variable}} patterns
        pattern = r"\{\{([^}]+)\}\}"
        for match in re.finditer(pattern, template_str):
            var_name = match.group(1).strip()
            variables.add(var_name)

        return variables


class TestObservableValue:
    """Test ObservableValue class."""

    def test_initialization(self):
        """Test observable value initialization."""
        obs = ObservableValue("test", 42)
        assert obs.field_name == "test"
        assert obs.value == 42
        assert len(obs._observers) == 0

    def test_add_observer(self):
        """Test adding observers."""
        obs = ObservableValue("test", 42)
        observer1 = Mock()
        observer2 = Mock()

        obs.add_observer(observer1)
        obs.add_observer(observer2)

        assert len(obs._observers) == 2
        assert observer1 in obs._observers
        assert observer2 in obs._observers

    def test_remove_observer(self):
        """Test removing observers."""
        obs = ObservableValue("test", 42)
        observer = Mock()

        obs.add_observer(observer)
        obs.remove_observer(observer)

        assert len(obs._observers) == 0

    def test_notify_observers(self):
        """Test observer notification via value setter."""
        obs = ObservableValue("test", 42)
        observer1 = Mock()
        observer2 = Mock()

        obs.add_observer(observer1)
        obs.add_observer(observer2)

        obs.value = 100

        observer1.assert_called_once_with("test", 42, 100)
        observer2.assert_called_once_with("test", 42, 100)
        assert obs.value == 100

    def test_set_value_no_change(self):
        """Test that observers are notified even when value is the same."""
        obs = ObservableValue("test", 42)
        observer = Mock()
        obs.add_observer(observer)

        obs.value = 42  # Same value

        # Observer should still be called
        observer.assert_called_once_with("test", 42, 42)


class TestDependencyInfo:
    """Test DependencyInfo class."""

    def test_initialization(self):
        """Test dependency info initialization."""
        dep = DependencyInfo("computed_field", "{{base_field}}", {"base_field"})

        assert dep.field_name == "computed_field"
        assert dep.expression == "{{base_field}}"
        assert dep.dependencies == {"base_field"}

    def test_default_dependencies(self):
        """Test default empty dependencies."""
        dep = DependencyInfo("computed_field", "{{base_field}}")

        assert dep.field_name == "computed_field"
        assert dep.expression == "{{base_field}}"
        assert dep.dependencies == set()


class TestDerivedFieldResolver:
    """Test DerivedFieldResolver class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.template_resolver = MockTemplateResolver()
        self.resolver = DerivedFieldResolver(self.template_resolver)
        self.test_data = {}
        self.resolver.set_model_data_accessor(self.test_data)

    def test_initialization(self):
        """Test resolver initialization."""
        assert self.resolver.template_resolver == self.template_resolver
        assert len(self.resolver.derived_fields) == 0
        assert len(self.resolver.observable_values) == 0

    def test_register_derived_field(self):
        """Test registering derived fields."""
        variable_map = {"{{first_name}} {{last_name}}": {"first_name", "last_name"}}
        self.template_resolver.variable_map = variable_map

        self.resolver.register_derived_field(
            "full_name", "{{first_name}} {{last_name}}"
        )

        assert "full_name" in self.resolver.derived_fields
        dep = self.resolver.derived_fields["full_name"]
        assert dep.field_name == "full_name"
        assert dep.expression == "{{first_name}} {{last_name}}"
        assert "first_name" in dep.dependencies
        assert "last_name" in dep.dependencies

    def test_dependency_extraction(self):
        """Test dependency extraction from templates."""
        variable_map = {"Hello {{name}}, you are {{age}} years old": {"name", "age"}}
        self.template_resolver.variable_map = variable_map

        dependencies = self.resolver._extract_dependencies(
            "Hello {{name}}, you are {{age}} years old"
        )

        assert "name" in dependencies
        assert "age" in dependencies

    def test_compute_derived_field(self):
        """Test computing derived fields."""
        template_map = {"{{first_name}} {{last_name}}": "John Doe"}
        variable_map = {"{{first_name}} {{last_name}}": {"first_name", "last_name"}}

        self.template_resolver.template_map = template_map
        self.template_resolver.variable_map = variable_map

        self.test_data.update({"first_name": "John", "last_name": "Doe"})

        self.resolver.register_derived_field(
            "full_name", "{{first_name}} {{last_name}}"
        )
        result = self.resolver.compute_derived_field("full_name")

        assert result == "John Doe"
        assert self.test_data["full_name"] == "John Doe"

    def test_compute_all_derived_fields(self):
        """Test computing all derived fields in order."""
        template_map = {
            "{{first_name}} {{last_name}}": "John Doe",
            "Hello {{full_name}}": "Hello John Doe",
        }
        variable_map = {
            "{{first_name}} {{last_name}}": {"first_name", "last_name"},
            "Hello {{full_name}}": {"full_name"},
        }

        self.template_resolver.template_map = template_map
        self.template_resolver.variable_map = variable_map

        self.test_data.update({"first_name": "John", "last_name": "Doe"})

        self.resolver.register_derived_field(
            "full_name", "{{first_name}} {{last_name}}"
        )
        self.resolver.register_derived_field("greeting", "Hello {{full_name}}")

        self.resolver.compute_all_derived_fields()

        assert self.test_data["full_name"] == "John Doe"
        assert self.test_data["greeting"] == "Hello John Doe"

    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        variable_map = {"{{b}}": {"b"}, "{{c}}": {"c"}, "{{a}}": {"a"}}
        self.template_resolver.variable_map = variable_map

        self.resolver.register_derived_field("a", "{{b}}")
        self.resolver.register_derived_field("b", "{{c}}")
        self.resolver.register_derived_field("c", "{{a}}")

        with pytest.raises(DependencyError) as exc_info:
            self.resolver.compute_all_derived_fields()

        assert "Circular dependency detected" in str(exc_info.value)

    def test_set_field_value(self):
        """Test setting field values and triggering updates."""
        template_map = {"{{first}} {{last}}": "John Doe"}
        variable_map = {"{{first}} {{last}}": {"first", "last"}}

        self.template_resolver.template_map = template_map
        self.template_resolver.variable_map = variable_map

        self.resolver.register_derived_field("full_name", "{{first}} {{last}}")

        # Set initial values
        self.resolver.set_field_value("first", "John")
        self.resolver.set_field_value("last", "Doe")

        assert self.test_data["first"] == "John"
        assert self.test_data["last"] == "Doe"
        assert self.test_data["full_name"] == "John Doe"

    def test_unregister_derived_field(self):
        """Test unregistering derived fields."""
        variable_map = {"{{base}}": {"base"}}
        self.template_resolver.variable_map = variable_map

        self.resolver.register_derived_field("computed", "{{base}}")
        assert "computed" in self.resolver.derived_fields

        self.resolver.unregister_derived_field("computed")
        assert "computed" not in self.resolver.derived_fields

    def test_get_field_dependencies(self):
        """Test getting field dependencies."""
        variable_map = {"{{first_name}} {{last_name}}": {"first_name", "last_name"}}
        self.template_resolver.variable_map = variable_map

        self.resolver.register_derived_field(
            "full_name", "{{first_name}} {{last_name}}"
        )

        deps = self.resolver.get_field_dependencies("full_name")
        assert "first_name" in deps
        assert "last_name" in deps

    def test_get_dependent_fields(self):
        """Test getting dependent fields."""
        variable_map = {
            "{{first_name}} {{last_name}}": {"first_name", "last_name"},
            "Hello {{full_name}}": {"full_name"},
        }
        self.template_resolver.variable_map = variable_map

        self.resolver.register_derived_field(
            "full_name", "{{first_name}} {{last_name}}"
        )
        self.resolver.register_derived_field("greeting", "Hello {{full_name}}")

        dependents = self.resolver.get_dependent_fields("full_name")
        assert "greeting" in dependents

    def test_template_resolution_error(self):
        """Test handling template resolution errors."""
        # Create a mock that raises an error
        error_resolver = Mock()
        error_resolver.extract_variables.return_value = {"base"}
        error_resolver.resolve_template.side_effect = Exception("Template error")

        resolver = DerivedFieldResolver(error_resolver)
        resolver.set_model_data_accessor({})
        resolver.register_derived_field("computed", "{{base}}")

        with pytest.raises(TemplateResolutionError) as exc_info:
            resolver.compute_derived_field("computed")

        assert "Failed to compute derived field" in str(exc_info.value)

    def test_field_change_callback(self):
        """Test field change callback functionality."""
        callback_mock = Mock()
        self.resolver.set_field_change_callback(callback_mock)

        template_map = {"{{base}}": "computed_value"}
        variable_map = {"{{base}}": {"base"}}

        self.template_resolver.template_map = template_map
        self.template_resolver.variable_map = variable_map

        self.test_data["base"] = "test"

        self.resolver.register_derived_field("computed", "{{base}}")
        self.resolver.compute_derived_field("computed")

        callback_mock.assert_called_once_with("computed", "computed_value")

    def test_nested_field_paths(self):
        """Test handling of nested field paths."""
        # Test setting nested values
        self.resolver._set_nested_value(self.test_data, "user.name", "John")
        assert self.test_data["user"]["name"] == "John"

        # Test getting nested values
        value = self.resolver._get_nested_value(self.test_data, "user.name")
        assert value == "John"

        # Test missing nested path
        value = self.resolver._get_nested_value(self.test_data, "user.age", "default")
        assert value == "default"


class TestBatchedDerivedFieldResolver:
    """Test BatchedDerivedFieldResolver class."""

    def setup_method(self):
        """Set up test fixtures."""
        template_map = {
            "{{a}}": "computed_a",
            "{{b}}": "computed_b",
            "{{computed_a}} {{computed_b}}": "final_result",
        }
        variable_map = {
            "{{a}}": {"a"},
            "{{b}}": {"b"},
            "{{computed_a}} {{computed_b}}": {"computed_a", "computed_b"},
        }

        self.template_resolver = MockTemplateResolver(template_map, variable_map)
        self.resolver = BatchedDerivedFieldResolver(self.template_resolver)
        self.test_data = {}
        self.resolver.set_model_data_accessor(self.test_data)

    def test_batched_updates(self):
        """Test batched field updates."""
        self.resolver.register_derived_field("computed_a", "{{a}}")
        self.resolver.register_derived_field("computed_b", "{{b}}")
        self.resolver.register_derived_field("final", "{{computed_a}} {{computed_b}}")

        # Start batching
        self.resolver.start_batch()

        # Set multiple fields
        self.resolver.set_field_value("a", "value_a")
        self.resolver.set_field_value("b", "value_b")

        # Fields should be set but derived fields not computed yet
        assert self.test_data["a"] == "value_a"
        assert self.test_data["b"] == "value_b"
        assert "computed_a" not in self.test_data

        # End batching - derived fields should be computed
        self.resolver.end_batch()

        assert self.test_data["computed_a"] == "computed_a"
        assert self.test_data["computed_b"] == "computed_b"
        assert self.test_data["final"] == "final_result"

    def test_non_batched_mode(self):
        """Test normal (non-batched) operation."""
        self.resolver.register_derived_field("computed", "{{base}}")

        # Without batching, derived fields should update immediately
        self.resolver.set_field_value("base", "test_value")

        assert self.test_data["base"] == "test_value"
        assert self.test_data["computed"] == "test_value"  # Template should be resolved


class TestFactoryFunction:
    """Test factory function."""

    def test_create_basic_resolver(self):
        """Test creating basic derived field resolver."""
        resolver_mock = Mock()
        resolver = create_derived_field_resolver(resolver_mock)

        assert isinstance(resolver, DerivedFieldResolver)
        assert not isinstance(resolver, BatchedDerivedFieldResolver)

    def test_create_batched_resolver(self):
        """Test creating batched derived field resolver."""
        resolver_mock = Mock()
        resolver = create_derived_field_resolver(resolver_mock, batched=True)

        assert isinstance(resolver, BatchedDerivedFieldResolver)
