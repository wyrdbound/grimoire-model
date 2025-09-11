"""Tests for the core GrimoireModel class."""

from unittest.mock import Mock, patch

import pytest

from grimoire_model.core.exceptions import (
    InheritanceError,
    ModelValidationError,
)
from grimoire_model.core.model import GrimoireModel
from grimoire_model.core.schema import (
    ModelDefinition,
    ValidationRule,
)


class TestGrimoireModel:
    """Test GrimoireModel class."""

    def test_model_creation_simple(self):
        """Test creating a simple model."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "required": False, "default": 0},
            },
        )

        model = GrimoireModel(model_def, {"name": "John"})

        assert model["name"] == "John"
        assert model["age"] == 0  # Default value
        assert len(model) == 2

    def test_model_creation_with_validation(self):
        """Test model creation with validation."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "range": "0..120"},
            },
        )

        # Valid data
        model = GrimoireModel(model_def, {"name": "John", "age": 30})
        assert model["name"] == "John"
        assert model["age"] == 30

        # Invalid data should raise validation error
        # Test model properties and accessors
        assert model.model_definition.id == "test_model"
        assert isinstance(model.instance_id, str)
        assert len(model.instance_id) > 0

    def test_model_mutable_mapping_interface(self):
        """Test that model implements MutableMapping interface."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "required": False, "default": 0},
            },
        )

        model = GrimoireModel(model_def, {"name": "John"})

        # Test __getitem__
        assert model["name"] == "John"

        # Test __setitem__
        model["age"] = 30
        assert model["age"] == 30

        # Test __delitem__
        del model["age"]
        assert "age" not in model

        # Test __iter__
        keys = list(model)
        assert "name" in keys

        # Test __len__
        assert len(model) == 1  # Only name after deleting age

        # Test __contains__
        assert "name" in model
        assert "age" not in model

    def test_model_get_method(self):
        """Test dict-like get method."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={"name": {"type": "str", "required": True}},
        )

        model = GrimoireModel(model_def, {"name": "John"})

        assert model.get("name") == "John"
        assert model.get("missing") is None
        assert model.get("missing", "default") == "default"

    def test_model_keys_values_items(self):
        """Test dict-like keys, values, and items methods."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "required": True},
            },
        )

        model = GrimoireModel(model_def, {"name": "John", "age": 30})

        # Test keys
        keys = list(model.keys())
        assert "name" in keys
        assert "age" in keys

        # Test values
        values = list(model.values())
        assert "John" in values
        assert 30 in values

        # Test items
        items = list(model.items())
        assert ("name", "John") in items
        assert ("age", 30) in items

    def test_model_update(self):
        """Test updating model with dict-like update method."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "required": False},
            },
        )

        model = GrimoireModel(model_def, {"name": "John"})

        # Update with dict
        model.update({"age": 30, "name": "Jane"})
        assert model["name"] == "Jane"
        assert model["age"] == 30

        # Update with kwargs
        model.update(age=31)
        assert model["age"] == 31

    def test_model_clear(self):
        """Test clearing model data."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": False},
                "age": {"type": "int", "required": False},
            },
        )

        model = GrimoireModel(model_def, {"name": "John", "age": 30})
        assert len(model) == 2

        model.clear()
        assert len(model) == 0

    def test_model_pop(self):
        """Test popping values from model."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": False},
                "age": {"type": "int", "required": False},
            },
        )

        model = GrimoireModel(model_def, {"name": "John", "age": 30})

        # Pop existing key
        age = model.pop("age")
        assert age == 30
        assert "age" not in model

        # Pop missing key with default
        result = model.pop("missing", "default")
        assert result == "default"

        # Pop missing key without default should raise KeyError
        with pytest.raises(KeyError):
            model.pop("missing")

    def test_model_popitem(self):
        """Test popitem method."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={"name": {"type": "str", "required": False}},
        )

        model = GrimoireModel(model_def, {"name": "John"})

        key, value = model.popitem()
        assert key == "name"
        assert value == "John"
        assert len(model) == 0

        # popitem on empty model should raise KeyError
        with pytest.raises(KeyError):
            model.popitem()

    def test_model_setdefault(self):
        """Test setdefault method."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": False},
                "age": {"type": "int", "required": False},
            },
        )

        model = GrimoireModel(model_def, {"name": "John"})

        # setdefault on existing key
        result = model.setdefault("name", "Jane")
        assert result == "John"  # Existing value
        assert model["name"] == "John"

        # setdefault on missing key
        result = model.setdefault("age", 30)
        assert result == 30
        assert model["age"] == 30

    def test_model_derived_fields(self):
        """Test model with derived fields."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "first_name": {"type": "str", "required": True},
                "last_name": {"type": "str", "required": True},
                "full_name": {"type": "str", "derived": "{{first_name}} {{last_name}}"},
            },
        )

        # Mock the template resolver
        mock_resolver = Mock()
        mock_resolver.resolve_template.return_value = "John Doe"
        mock_resolver.extract_variables.return_value = {"first_name", "last_name"}

        # Create model with mocked template resolver
        model = GrimoireModel(
            model_def,
            {"first_name": "John", "last_name": "Doe"},
            template_resolver=mock_resolver,
        )

        # Derived field should be computed
        assert model["full_name"] == "John Doe"

        # Template resolver should have been called
        mock_resolver.resolve_template.assert_called()

    def test_model_validation_rules(self):
        """Test model with validation rules."""
        validation_rule = ValidationRule(
            expression="{{ age >= 18 }}", message="Must be 18 or older", fields=["age"]
        )

        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "required": True},
            },
            validations=[validation_rule],
        )

        # Valid data should work
        model = GrimoireModel(model_def, {"name": "John", "age": 25})
        assert model["age"] == 25

        # Invalid data should raise validation error
        with pytest.raises(ModelValidationError):
            GrimoireModel(model_def, {"name": "John", "age": 16})

    def test_model_readonly_attributes(self):
        """Test model with readonly attributes."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "id": {"type": "str", "readonly": True, "default": "auto-generated"},
                "name": {"type": "str", "required": True},
            },
        )

        model = GrimoireModel(model_def, {"name": "John"})

        # Readonly field should have default value
        assert model["id"] == "auto-generated"

        # Setting readonly field should raise error
        with pytest.raises(ModelValidationError):
            model["id"] = "new-id"

    def test_model_batch_updates(self):
        """Test batch updates for performance."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "a": {"type": "str", "required": True},
                "b": {"type": "str", "required": True},
                "computed": {"type": "str", "derived": "{{a}} {{b}}"},
            },
        )

        with patch(
            "grimoire_model.core.model.create_template_resolver"
        ) as mock_resolver_creator:
            mock_resolver = Mock()
            mock_resolver.resolve_template.return_value = "value_a value_b"
            mock_resolver.extract_variables.return_value = {"a", "b"}
            mock_resolver_creator.return_value = mock_resolver

            model = GrimoireModel(model_def, {"a": "value_a", "b": "value_b"})

            # Use batch update to minimize recomputation
            model.batch_update({"a": "new_a", "b": "new_b"})

            # Values should be updated
            assert model["a"] == "new_a"
            assert model["b"] == "new_b"

    def test_model_to_dict_behavior(self):
        """Test dict-like behavior (since to_dict method doesn't exist)."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "required": True},
            },
        )

        model = GrimoireModel(model_def, {"name": "John", "age": 30})

        # Convert to dict using dict() constructor
        data_dict = dict(model)
        assert isinstance(data_dict, dict)
        assert data_dict["name"] == "John"
        assert data_dict["age"] == 30

    def test_model_copy(self):
        """Test copying model."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "required": True},
            },
        )

        model = GrimoireModel(model_def, {"name": "John", "age": 30})

        # Test shallow copy
        copied_model = model.copy()
        assert copied_model["name"] == "John"
        assert copied_model["age"] == 30

        # Modifying copy should not affect original
        copied_model["name"] = "Jane"
        assert model["name"] == "John"
        assert copied_model["name"] == "Jane"

    def test_model_equality(self):
        """Test model equality comparison."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={"name": {"type": "str", "required": True}},
        )

        model1 = GrimoireModel(model_def, {"name": "John"})
        model2 = GrimoireModel(model_def, {"name": "John"})
        model3 = GrimoireModel(model_def, {"name": "Jane"})

        assert model1 == model2
        assert model1 != model3
        assert model1 != {"name": "John"}  # Different type

    def test_model_str_repr(self):
        """Test string representation of model."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={"name": {"type": "str", "required": True}},
        )

        model = GrimoireModel(model_def, {"name": "John"})

        str_repr = str(model)
        assert "test_model" in str_repr
        assert "John" in str_repr

        repr_str = repr(model)
        assert "GrimoireModel" in repr_str

    def test_model_validation_on_field_set(self):
        """Test that validation occurs when setting fields."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={"age": {"type": "int", "range": "0..120"}},
        )

        model = GrimoireModel(model_def, {"age": 30})

        # Valid update should work
        model["age"] = 25
        assert model["age"] == 25

        # Invalid update should raise error
        with pytest.raises(ModelValidationError):
            model["age"] = 150

    def test_model_missing_required_field(self):
        """Test handling of missing required fields."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "required": True},
            },
        )

        # Missing required field should raise error
        with pytest.raises(ModelValidationError):
            GrimoireModel(model_def, {"name": "John"})  # Missing age

    def test_model_type_validation(self):
        """Test type validation on field assignment."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "required": True},
            },
        )

        model = GrimoireModel(model_def, {"name": "John", "age": 30})

        # Valid type assignment
        model["name"] = "Jane"
        model["age"] = 25

        # Invalid type assignment should raise error
        with pytest.raises(ModelValidationError):
            model["name"] = 123  # Wrong type

        with pytest.raises(ModelValidationError):
            model["age"] = "not_a_number"  # Wrong type

    def test_model_with_default_values(self):
        """Test model with default values."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "status": {"type": "str", "default": "active"},
                "count": {"type": "int", "default": 0},
            },
        )

        model = GrimoireModel(model_def, {"name": "John"})

        # Default values should be set
        assert model["name"] == "John"
        assert model["status"] == "active"
        assert model["count"] == 0

    def test_model_field_change_tracking(self):
        """Test field change tracking (without callback assignment)."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={"name": {"type": "str", "required": True}},
        )

        model = GrimoireModel(model_def, {"name": "John"})

        # Change field value
        old_value = model["name"]
        model["name"] = "Jane"
        new_value = model["name"]

        # Values should be different
        assert old_value == "John"
        assert new_value == "Jane"

    def test_model_exception_handling(self):
        """Test exception handling in model operations."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={"name": {"type": "str", "required": True}},
        )

        model = GrimoireModel(model_def, {"name": "John"})

        # Test model properties and accessors
        assert model.model_definition.id == "test_model"
        assert isinstance(model.instance_id, str)
        assert len(model.instance_id) > 0

        # Test KeyError for missing field
        with pytest.raises(KeyError):
            _ = model["missing_field"]

    def test_model_property_accessors(self):
        """Test model property accessors."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={"name": {"type": "str", "required": True}},
        )

        model = GrimoireModel(model_def, {"name": "John"})

        # Test model properties and accessors
        assert model.model_definition.id == "test_model"
        assert isinstance(model.instance_id, str)
        assert len(model.instance_id) > 0

    def test_model_validation_failure_during_creation(self):
        """Test validation failure during model creation."""
        model_def = ModelDefinition(
            id="invalid_model",
            name="Invalid Model",
            attributes={"required_field": {"type": "str", "required": True}},
        )

        # Test exception handling
        with pytest.raises(ModelValidationError):
            GrimoireModel(model_def, {})

    def test_delitem_with_dot_path(self):
        """Test __delitem__ with a dot path notation."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={"stats": {"type": "dict"}, "level": {"type": "int"}},
        )

        model = GrimoireModel(
            model_def, {"stats": {"strength": 10, "dexterity": 15}, "level": 5}
        )

        # Test deleting nested attribute using dot notation
        del model["stats.strength"]
        assert "strength" not in model["stats"]
        assert "dexterity" in model["stats"]

        # Test deleting top-level attribute
        del model["level"]
        assert "level" not in model

    def test_model_derived_field_methods(self):
        """Test get_derived_fields, get_field_dependencies, get_dependent_fields
        methods."""
        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "base_damage": {"type": "int"},
                "strength": {"type": "int"},
                "total_damage": {
                    "type": "int",
                    "derived": "{{ base_damage + strength }}",
                },
                "damage_bonus": {"type": "int", "derived": "{{ strength * 2 }}"},
            },
        )

        model = GrimoireModel(model_def, {"base_damage": 10, "strength": 5})

        # Test get_derived_fields
        derived_fields = model.get_derived_fields()
        assert "total_damage" in derived_fields
        assert "damage_bonus" in derived_fields
        assert "base_damage" not in derived_fields

        # Test get_field_dependencies - what fields does total_damage depend on
        deps = model.get_field_dependencies("total_damage")
        assert "base_damage" in deps
        assert "strength" in deps

        # Test get_dependent_fields - what fields depend on strength
        dependents = model.get_dependent_fields("strength")
        assert "total_damage" in dependents
        assert "damage_bonus" in dependents

    def test_model_complex_derived_field_dependencies(self):
        """Test complex derived field dependency chains."""
        model_def = ModelDefinition(
            id="complex_model",
            name="Complex Model",
            attributes={
                "strength": {"type": "int", "required": True},
                "weapon_damage": {"type": "int", "required": True},
                "damage_multiplier": {
                    "type": "float",
                    "derived": "{{ total_damage * 0.1 }}",
                },
                "total_damage": {
                    "type": "int",
                    "derived": "{{ strength + weapon_damage }}",
                },
                "final_damage": {
                    "type": "float",
                    "derived": "{{ total_damage * damage_multiplier }}",
                },
            },
        )

        model = GrimoireModel(model_def, {"strength": 10, "weapon_damage": 5})

        # Test the complex dependency chain works correctly
        assert model["total_damage"] == 15
        assert model["damage_multiplier"] == 1.5  # 15 * 0.1
        assert model["final_damage"] == 22.5  # 15 * 1.5

    def test_batch_update_with_batched_resolver(self):
        """Test batch_update functionality with BatchedDerivedFieldResolver."""
        from grimoire_model.resolvers.derived import BatchedDerivedFieldResolver
        from grimoire_model.resolvers.template import Jinja2TemplateResolver

        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "a": {"type": "int"},
                "b": {"type": "int"},
                "sum": {"type": "int", "derived": "{{ a + b }}"},
                "product": {"type": "int", "derived": "{{ a * b }}"},
            },
        )

        # Create model with batched resolver
        template_resolver = Jinja2TemplateResolver()
        batched_resolver = BatchedDerivedFieldResolver(template_resolver)
        model = GrimoireModel(
            model_def, {"a": 1, "b": 2}, derived_field_resolver=batched_resolver
        )

        # Test batch update
        model.batch_update({"a": 10, "b": 20})

        # Force derived field recomputation
        model.recompute_derived_fields()

        # Verify all fields were updated correctly
        assert model["a"] == 10
        assert model["b"] == 20
        assert int(model["sum"]) == 30  # Convert from string result
        assert int(model["product"]) == 200  # Convert from string result

    def test_model_with_inheritance_resolve_inheritance(self):
        """Test model inheritance resolution with both success and error cases."""
        from grimoire_model import clear_registry

        # Clear registry first
        clear_registry()

        # Test successful inheritance resolution
        # Models will auto-register when created
        ModelDefinition(
            id="base_character",
            name="Base Character",
            namespace="test",
            attributes={
                "name": {"type": "str", "required": True},
                "health": {"type": "int", "default": 100},
            },
        )

        child_model_def = ModelDefinition(
            id="warrior",
            name="Warrior",
            namespace="test",
            extends=["base_character"],
            attributes={
                "strength": {"type": "int", "default": 10},
                "weapon": {"type": "str", "default": "sword"},
            },
        )

        # Test successful inheritance - models auto-registered
        model = GrimoireModel(child_model_def, {"name": "Conan", "strength": 18})

        assert model["name"] == "Conan"
        assert model["health"] == 100  # From base model
        assert model["strength"] == 18  # From child model
        assert model["weapon"] == "sword"  # From child model default

        # Test inheritance error handling - create a model with missing parent
        clear_registry()  # Clear to simulate missing parent

        # Only register the child, not the parent it extends
        broken_child_def = ModelDefinition(
            id="broken_child",
            name="Broken Child",
            namespace="test",
            extends=["missing_parent"],
            attributes={"strength": {"type": "int", "default": 10}},
        )

        with pytest.raises(InheritanceError):
            GrimoireModel(broken_child_def, {"name": "Failed"})

    def test_model_delete_with_dot_path(self):
        """Test delete operation that triggers __delitem__ with dot notation path."""
        model_def = ModelDefinition(
            id="nested_model",
            name="Nested Model",
            attributes={
                "name": {"type": "str", "required": True},
                "stats": {"type": "dict"},
                "config": {"type": "dict"},
            },
        )

        # Create model with nested data
        model = GrimoireModel(
            model_def,
            {
                "name": "Test",
                "stats": {"strength": 10, "agility": 8, "intelligence": 12},
                "config": {
                    "sound": {"volume": 0.8, "muted": False},
                    "graphics": {"resolution": "1920x1080", "fullscreen": True},
                },
            },
        )

        # Verify initial nested data exists
        assert model["stats"]["strength"] == 10
        assert model["config"]["sound"]["volume"] == 0.8

        # Test deleting nested values using dot notation
        # (triggers __delitem__ with dot path)
        del model["stats.strength"]
        assert "strength" not in model["stats"]
        assert model["stats"]["agility"] == 8  # Other values should remain

        # Test deleting deeper nested value
        del model["config.sound.volume"]
        assert "volume" not in model["config"]["sound"]
        assert model["config"]["sound"]["muted"] is False  # Other values should remain
        assert (
            model["config"]["graphics"]["resolution"] == "1920x1080"
        )  # Unrelated nested data should remain

        # Test deleting entire nested section
        del model["config.graphics"]
        assert "graphics" not in model["config"]
        assert "sound" in model["config"]  # Other top-level nested data should remain


class TestCreateModelFactory:
    """Test the create_model factory function."""

    def test_create_model_basic(self):
        """Test basic model creation with factory function."""
        from grimoire_model.core.model import create_model

        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "default": 25},
            },
        )

        model = create_model(model_def, {"name": "Alice"})

        assert isinstance(model, GrimoireModel)
        assert model["name"] == "Alice"
        assert model["age"] == 25  # Default value applied
        assert model.model_definition.id == "test_model"

    def test_create_model_with_template_resolver_type(self):
        """Test factory with different template resolver types."""
        from grimoire_model.core.model import create_model

        model_def = ModelDefinition(
            id="template_model",
            name="Template Model",
            attributes={
                "base": {"type": "int", "required": True},
                "computed": {"type": "str", "derived": "{{ base * 2 }}"},
            },
        )

        # Test with jinja2 resolver (default)
        model1 = create_model(model_def, {"base": 10}, template_resolver_type="jinja2")
        assert model1["computed"] == "20"

        # Test with model_context resolver
        model2 = create_model(
            model_def, {"base": 15}, template_resolver_type="model_context"
        )
        assert model2["computed"] == "30"

    def test_create_model_with_model_registry(self):
        """Test factory with model registry for inheritance."""
        from grimoire_model.core.model import create_model

        base_model_def = ModelDefinition(
            id="base_character",
            name="Base Character",
            attributes={
                "name": {"type": "str", "required": True},
                "health": {"type": "int", "default": 100},
            },
        )

        child_model_def = ModelDefinition(
            id="warrior",
            name="Warrior",
            extends=["base_character"],
            attributes={
                "strength": {"type": "int", "default": 10},
                "weapon": {"type": "str", "default": "sword"},
            },
        )

        model_registry = {"base_character": base_model_def, "warrior": child_model_def}

        model = create_model(
            child_model_def,
            {"name": "Conan", "strength": 18},
            model_registry=model_registry,
        )

        assert model["name"] == "Conan"
        assert model["health"] == 100  # From base model
        assert model["strength"] == 18  # Overridden value
        assert model["weapon"] == "sword"  # Default from child model

    def test_create_model_with_template_resolver_kwargs(self):
        """Test factory with custom template resolver configuration."""
        from grimoire_model.core.model import create_model

        model_def = ModelDefinition(
            id="custom_template_model",
            name="Custom Template Model",
            attributes={
                "value": {"type": "int", "required": True},
                "result": {"type": "str", "derived": "{{ value }}"},
            },
        )

        # Test with custom jinja2 environment kwargs
        template_resolver_kwargs = {
            "autoescape": False,  # Valid Jinja2 Environment parameter
            "trim_blocks": False,  # Override default
        }

        model = create_model(
            model_def,
            {"value": 42},
            template_resolver_type="jinja2",
            template_resolver_kwargs=template_resolver_kwargs,
        )

        assert model["value"] == 42
        assert (
            model["result"] == "42"
        )  # Template result converted to str type as defined

    def test_create_model_with_derived_resolver_kwargs(self):
        """Test factory with custom derived field resolver configuration."""
        from grimoire_model.core.model import create_model

        model_def = ModelDefinition(
            id="batched_model",
            name="Batched Model",
            attributes={
                "a": {"type": "int", "required": True},
                "b": {"type": "int", "required": True},
                "sum": {"type": "str", "derived": "{{ a + b }}"},
                "product": {"type": "str", "derived": "{{ a * b }}"},
            },
        )

        # Test with batched derived field resolver
        derived_resolver_kwargs = {"batched": True}

        model = create_model(
            model_def, {"a": 5, "b": 3}, derived_resolver_kwargs=derived_resolver_kwargs
        )

        assert model["a"] == 5
        assert model["b"] == 3
        assert model["sum"] == "8"
        assert model["product"] == "15"

    def test_create_model_with_additional_kwargs(self):
        """Test factory with additional kwargs passed to GrimoireModel."""
        from grimoire_model.core.model import create_model

        model_def = ModelDefinition(
            id="kwargs_model",
            name="Kwargs Model",
            attributes={"name": {"type": "str", "required": True}},
        )

        # Test with custom instance_id
        custom_instance_id = "custom-test-id-12345"
        model = create_model(
            model_def, {"name": "Test"}, instance_id=custom_instance_id
        )

        assert model["name"] == "Test"
        assert model.instance_id == custom_instance_id

    def test_create_model_no_data(self):
        """Test factory with no initial data (should use defaults)."""
        from grimoire_model.core.model import create_model

        model_def = ModelDefinition(
            id="default_model",
            name="Default Model",
            attributes={
                "name": {"type": "str", "default": "Unknown"},
                "count": {"type": "int", "default": 0},
                "active": {"type": "bool", "default": True},
            },
        )

        model = create_model(model_def)  # No data provided

        assert model["name"] == "Unknown"
        assert model["count"] == 0
        assert model["active"] is True

    def test_create_model_with_validation_error(self):
        """Test factory when validation fails during creation."""
        from grimoire_model.core.exceptions import ModelValidationError
        from grimoire_model.core.model import create_model

        model_def = ModelDefinition(
            id="validation_model",
            name="Validation Model",
            attributes={"required_field": {"type": "str", "required": True}},
        )

        # Should raise validation error for missing required field
        with pytest.raises(ModelValidationError):
            create_model(model_def, {})  # Missing required field

    def test_derived_field_recomputation_on_individual_updates(self):
        """Test that derived fields are recomputed when individual base fields
        are updated."""
        from grimoire_model.core.model import create_model

        # Create a model EXACTLY like the basic usage example
        model_def = ModelDefinition(
            id="character",
            name="Character",
            attributes={
                "name": {"type": "str", "required": True},
                "level": {"type": "int", "default": 1, "range": "1..100"},
                "health": {"type": "int", "default": 100},
                "mana": {"type": "int", "default": 50},
                # Derived fields using templates - this is the complex chain
                "total_resources": {"type": "int", "derived": "{{ health + mana }}"},
                "is_powerful": {"type": "bool", "derived": "{{ level >= 10 }}"},
                "character_summary": {
                    "type": "str",
                    "derived": (
                        "Level {{ level }} {{ name }} "
                        "({{ total_resources }} total resources)"
                    ),
                },
            },
        )

        # Create character EXACTLY like the example
        character2 = create_model(
            model_def, {"name": "Legolas", "level": 8, "health": 90, "mana": 110}
        )

        # Initial values should be correct
        assert character2["health"] == 90
        assert character2["mana"] == 110
        initial_total = character2["total_resources"]
        initial_summary = character2["character_summary"]
        assert initial_total == 200  # 90 + 110
        assert "200 total resources" in initial_summary

        # Update EXACTLY like the example
        character2["level"] = 12  # Level up!
        character2["health"] = 95  # Slight health increase

        # CRITICAL: The derived field should automatically update
        assert character2["health"] == 95
        assert character2["level"] == 12
        updated_total = character2["total_resources"]
        updated_summary = character2["character_summary"]

        # This should be 205 (95 + 110) and now works correctly!
        assert updated_total == 205  # 95 + 110 - fixed!
        assert "205 total resources" in updated_summary

    def test_validation_rules_execution_during_creation(self):
        """Test that ValidationRule expressions are properly executed during
        model creation."""
        from grimoire_model.core.exceptions import ModelValidationError
        from grimoire_model.core.model import create_model

        # Create a model with validation rules like in the basic usage example
        model_def = ModelDefinition(
            id="character",
            name="Character",
            attributes={
                "name": {"type": "str", "required": True},
                "health": {"type": "int", "default": 100},
                "mana": {"type": "int", "default": 50},
            },
            validations=[
                ValidationRule(
                    expression="health > 0",
                    message="Character must have positive health",
                ),
                ValidationRule(
                    expression="mana >= 0",
                    message="Character cannot have negative mana",
                ),
            ],
        )

        # Valid character should work fine
        valid_character = create_model(
            model_def, {"name": "ValidChar", "health": 100, "mana": 50}
        )
        assert valid_character["name"] == "ValidChar"
        assert valid_character["health"] == 100

        # Invalid character with negative health should fail validation
        with pytest.raises(ModelValidationError) as exc_info:
            create_model(
                model_def,
                {
                    "name": "Invalid",
                    "health": -10,  # This should fail validation
                },
            )

        error = exc_info.value
        assert "Character must have positive health" in str(error)

        # Invalid character with negative mana should also fail
        with pytest.raises(ModelValidationError) as exc_info:
            create_model(
                model_def,
                {
                    "name": "Invalid",
                    "health": 100,
                    "mana": -5,  # This should fail validation
                },
            )

        error = exc_info.value
        assert "Character cannot have negative mana" in str(error)

    def test_validation_rules_with_derived_fields(self):
        """Test that validation rules can reference derived fields during
        model creation."""
        from grimoire_model.core.exceptions import ModelValidationError
        from grimoire_model.core.model import create_model

        # Create a model with derived fields and validation rules that reference them
        model_def = ModelDefinition(
            id="character",
            name="Character",
            attributes={
                "name": {"type": "str", "required": True},
                "strength": {"type": "int", "default": 10},
                "dexterity": {"type": "int", "default": 10},
                "intelligence": {"type": "int", "default": 10},
                # Derived field that sums the stats
                "stat_total": {
                    "type": "int",
                    "derived": "{{ strength + dexterity + intelligence }}",
                },
            },
            validations=[
                ValidationRule(
                    expression="stat_total >= 30",
                    message="Total stats must be at least 30",
                )
            ],
        )

        # Valid character with enough stats should work
        valid_character = create_model(
            model_def,
            {"name": "ValidChar", "strength": 12, "dexterity": 10, "intelligence": 8},
        )
        assert valid_character["name"] == "ValidChar"
        assert valid_character["stat_total"] == 30  # 12 + 10 + 8

        # Invalid character with too low stats should fail validation
        with pytest.raises(ModelValidationError) as exc_info:
            create_model(
                model_def,
                {
                    "name": "WeakChar",
                    "strength": 8,
                    "dexterity": 8,
                    "intelligence": 8,  # Total = 24, less than 30
                },
            )

        error = exc_info.value
        assert "Total stats must be at least 30" in str(error)

    def test_model_context_template_resolver(self):
        """Test that model_context template resolver works with $variable syntax."""
        from grimoire_model.core.model import create_model

        # Create a model using model_context template resolver
        model_def = ModelDefinition(
            id="character",
            name="Character",
            attributes={
                "name": {"type": "str", "required": True},
                "level": {"type": "int", "default": 1},
                "power": {"type": "int", "default": 10},
                # Using $variable syntax instead of {{ variable }}
                "display_name": {"type": "str", "derived": "$name (Level $level)"},
                "power_level": {"type": "str", "derived": "Power: $power"},
            },
        )

        # Create model with model_context template resolver
        character = create_model(
            model_def,
            {"name": "Gandalf", "level": 50, "power": 95},
            template_resolver_type="model_context",
        )

        # The derived fields should be properly resolved
        assert character["name"] == "Gandalf"
        assert character["level"] == 50
        assert character["power"] == 95

        # These should resolve the $variable syntax correctly
        assert character["display_name"] == "Gandalf (Level 50)", (
            f"Got: {character['display_name']}"
        )
        assert character["power_level"] == "Power: 95", (
            f"Got: {character['power_level']}"
        )
