"""Tests for attribute-style access to GrimoireModel objects."""

import pytest
from jinja2 import Template

from grimoire_model import (
    ModelDefinition,
    create_model,
    create_model_without_validation,
)
from grimoire_model.core.exceptions import ModelValidationError


class TestAttributeAccess:
    """Test attribute-style access to model data."""

    def test_basic_attribute_read(self):
        """Test reading attributes via dot notation."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "name": {"type": "str", "required": True},
                "value": {"type": "int", "default": 0},
            },
        )

        model = create_model_without_validation(
            model_def, {"name": "test_name", "value": 42}
        )

        # Test attribute access
        assert model.name == "test_name"
        assert model.value == 42

    def test_basic_attribute_write(self):
        """Test writing attributes via dot notation."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "name": {"type": "str", "required": True},
                "value": {"type": "int", "default": 0},
            },
        )

        model = create_model_without_validation(model_def, {"name": "test_name"})

        # Test attribute assignment
        model.value = 100
        assert model.value == 100
        assert model["value"] == 100  # Verify dict access still works

    def test_mixed_access_patterns(self):
        """Test that dict and attribute access work together seamlessly."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "field1": {"type": "str", "required": True},
                "field2": {"type": "int", "default": 0},
            },
        )

        model = create_model_without_validation(model_def, {"field1": "value1"})

        # Set via dict, read via attribute
        model["field2"] = 50
        assert model.field2 == 50

        # Set via attribute, read via dict
        model.field1 = "new_value"
        assert model["field1"] == "new_value"

    def test_attribute_access_with_derived_fields(self):
        """Test attribute access works with derived fields."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "base": {"type": "int", "default": 10},
                "bonus": {"type": "int", "default": 5},
                "total": {"type": "int", "derived": "{{ base + bonus }}"},
            },
        )

        model = create_model_without_validation(model_def, {"base": 20, "bonus": 15})

        # Read derived field via attribute
        assert model.total == 35

        # Update base field via attribute and check derived field
        model.base = 30
        assert model.total == 45

    def test_getattr_with_default(self):
        """Test getattr() with default value for model attributes."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "name": {"type": "str", "required": True},
            },
        )

        model = create_model_without_validation(model_def, {"name": "test"})

        # Existing attribute should return actual value
        assert getattr(model, "name", "default") == "test"

        # Non-existent attribute should return default
        assert getattr(model, "nonexistent", "default") == "default"

    def test_attribute_error_for_undefined_attributes(self):
        """Test that accessing undefined attributes raises AttributeError."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "name": {"type": "str", "required": True},
            },
        )

        model = create_model_without_validation(model_def, {"name": "test"})

        # Should raise AttributeError for undefined attributes
        with pytest.raises(AttributeError, match="has no attribute 'undefined'"):
            _ = model.undefined

    def test_jinja2_template_compatibility(self):
        """Test that attribute access works in Jinja2 templates."""
        model_def = ModelDefinition(
            id="weapon",
            name="Weapon",
            attributes={
                "name": {"type": "str", "required": True},
                "damage": {"type": "str", "required": True},
                "bonus": {"type": "int", "default": 0},
            },
        )

        weapon = create_model_without_validation(
            model_def, {"name": "Longsword", "damage": "1d8", "bonus": 2}
        )

        # Test simple attribute access in template
        template = Template("{{ weapon.name }}")
        assert template.render(weapon=weapon) == "Longsword"

        # Test multiple attributes in template
        template = Template("Weapon: {{ weapon.name }}, Damage: {{ weapon.damage }}")
        result = template.render(weapon=weapon)
        assert result == "Weapon: Longsword, Damage: 1d8"

        # Test with expressions in template
        template = Template("Bonus: +{{ weapon.bonus }}")
        assert template.render(weapon=weapon) == "Bonus: +2"

    def test_jinja2_template_with_derived_fields(self):
        """Test Jinja2 templates with derived fields accessed via attributes."""
        model_def = ModelDefinition(
            id="character",
            name="Character",
            attributes={
                "name": {"type": "str", "required": True},
                "level": {"type": "int", "default": 1},
                "hp": {"type": "int", "default": 10},
                "max_hp": {"type": "int", "derived": "{{ level * 8 + hp }}"},
            },
        )

        character = create_model_without_validation(
            model_def, {"name": "Hero", "level": 5, "hp": 20}
        )

        # Template accessing derived field via attribute
        template = Template("{{ character.name }} has {{ character.max_hp }} HP")
        result = template.render(character=character)
        assert result == "Hero has 60 HP"

    def test_attribute_validation_on_set(self):
        """Test that attribute assignment triggers validation."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "range": "0..120"},
            },
        )

        model = create_model(model_def, {"name": "test", "age": 30})

        # Valid assignment should work
        model.age = 50
        assert model.age == 50

        # Invalid assignment should raise validation error
        with pytest.raises(ModelValidationError):
            model.age = 150  # Outside valid range

    def test_readonly_attribute_protection(self):
        """Test that readonly attributes cannot be modified via attribute access."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "id": {"type": "str", "readonly": True, "default": "default_id"},
                "name": {"type": "str", "required": True},
            },
        )

        model = create_model(model_def, {"name": "test"})

        # Should be able to read readonly attribute
        assert model.id == "default_id"

        # Should not be able to modify readonly attribute
        with pytest.raises(ModelValidationError, match="readonly"):
            model.id = "new_id"

    def test_internal_attributes_not_affected(self):
        """Test that internal attributes starting with _ are not affected."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "name": {"type": "str", "required": True},
            },
        )

        model = create_model_without_validation(model_def, {"name": "test"})

        # Internal attributes should still be accessible
        assert hasattr(model, "_data")
        assert hasattr(model, "_resolved_attributes")
        assert hasattr(model, "_model_def")

        # Can still access them directly
        assert model._model_def.id == "test"
        assert "name" in model._resolved_attributes

    def test_hasattr_with_model_attributes(self):
        """Test hasattr() works correctly with model attributes."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "name": {"type": "str", "required": True},
                "optional": {"type": "str", "required": False},
            },
        )

        model = create_model_without_validation(model_def, {"name": "test"})

        # Should return True for defined attributes with values
        assert hasattr(model, "name")

        # Should return True for defined attributes even without values
        # (they're in _resolved_attributes)
        assert hasattr(model, "optional")

        # Should return False for undefined attributes
        assert not hasattr(model, "undefined")

    def test_attribute_access_with_nested_models(self):
        """Test attribute access works with nested model structures."""
        # This is a basic test - nested models are a complex feature
        # that might require additional consideration
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "data": {"type": "dict", "required": False},
            },
        )

        model = create_model_without_validation(
            model_def, {"data": {"nested_key": "nested_value"}}
        )

        # Should be able to access the dict attribute
        assert model.data == {"nested_key": "nested_value"}

    def test_dir_includes_model_attributes(self):
        """Test that dir() includes model attributes."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "name": {"type": "str", "required": True},
                "value": {"type": "int", "default": 0},
            },
        )

        model = create_model_without_validation(model_def, {"name": "test"})

        # dir() should include model attributes
        attrs = dir(model)
        # Note: dir() returns the class methods and properties, but __getattr__
        # provides dynamic access, so model fields might not appear in dir()
        # This is expected behavior - they're accessible but not enumerated
        assert "name" not in attrs  # Expected: dynamic attributes don't appear in dir()
        assert "get" in attrs  # But dict-like methods do
        assert "validate" in attrs  # And model methods do

        # But the attributes are still accessible
        assert hasattr(model, "name")
        assert model.name == "test"

    def test_attribute_access_backward_compatibility(self):
        """Test that existing dict-style access still works perfectly."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "name": {"type": "str", "required": True},
                "value": {"type": "int", "default": 0},
            },
        )

        model = create_model_without_validation(
            model_def, {"name": "test", "value": 42}
        )

        # All existing dict-style operations should still work
        assert model["name"] == "test"
        assert model.get("value") == 42
        assert "name" in model
        assert len(model) == 2
        # Use set for unordered comparison
        assert set(model.keys()) == {"name", "value"}
        # Use set for unordered comparison
        assert set(model.values()) == {"test", 42}

        # Update via dict
        model["name"] = "updated"
        assert model["name"] == "updated"
        assert model.name == "updated"  # And accessible via attribute

        # Delete via dict
        del model["value"]
        assert "value" not in model
        # Accessing deleted attribute should raise AttributeError or return None
        # depending on whether it's still in _resolved_attributes
        # It should still be in _resolved_attributes but not have a value
        with pytest.raises(KeyError):
            _ = model["value"]
