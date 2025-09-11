"""Tests for core schema definitions."""

import pytest
from pydantic import ValidationError

from grimoire_model.core.exceptions import ConfigurationError
from grimoire_model.core.schema import (
    AttributeDefinition,
    ModelDefinition,
    ValidationRule,
)


class TestAttributeDefinition:
    """Test AttributeDefinition class."""

    def test_basic_attribute_creation(self):
        """Test creating basic attribute definitions."""
        attr = AttributeDefinition(type="str", required=True)
        assert attr.type == "str"
        assert attr.required is True
        assert attr.computed is False
        assert attr.derived is None

    def test_derived_attribute_creation(self):
        """Test creating derived attribute definitions."""
        attr = AttributeDefinition(
            type="int", derived="{{ level * 2 }}", required=False
        )
        assert attr.type == "int"
        assert attr.derived == "{{ level * 2 }}"
        assert attr.computed is True  # Should be auto-set
        assert attr.required is False

    def test_optional_override(self):
        """Test that optional overrides required."""
        attr = AttributeDefinition(type="str", required=True, optional=True)
        assert attr.required is False  # Should be overridden by optional

    def test_range_validation(self):
        """Test range validation."""
        # Valid range formats
        valid_ranges = ["1..10", "1..", "..10", ">=5", "<=20", ">0", "<100", "=42"]
        for range_val in valid_ranges:
            attr = AttributeDefinition(type="int", range=range_val)
            assert attr.range == range_val

        # Invalid range format should raise error
        with pytest.raises(ValidationError):
            AttributeDefinition(type="int", range="invalid")

    def test_type_validation(self):
        """Test type validation."""
        # Valid basic types
        basic_types = ["int", "str", "float", "bool", "list", "dict", "any"]
        for type_val in basic_types:
            attr = AttributeDefinition(type=type_val)
            assert attr.type == type_val

        # Valid model ID
        attr = AttributeDefinition(type="custom_model_id")
        assert attr.type == "custom_model_id"

        # Invalid type should raise error
        with pytest.raises(ValidationError):
            AttributeDefinition(type="invalid!type")

    def test_computed_attribute_validation(self):
        """Test computed attribute validation."""
        # Computed attribute without derived expression should fail
        with pytest.raises(ValidationError):
            AttributeDefinition(type="int", computed=True)

        # Readonly without default or computed should fail
        with pytest.raises(ValidationError):
            AttributeDefinition(type="str", readonly=True)

        # Readonly with default should pass
        attr = AttributeDefinition(type="str", readonly=True, default="test")
        assert attr.readonly is True

        # Readonly with computed should pass
        attr = AttributeDefinition(type="int", readonly=True, derived="{{ 42 }}")
        assert attr.readonly is True
        assert attr.computed is True


class TestValidationRule:
    """Test ValidationRule class."""

    def test_basic_validation_rule(self):
        """Test creating basic validation rules."""
        rule = ValidationRule(
            expression="{{ level > 0 }}", message="Level must be positive"
        )
        assert rule.expression == "{{ level > 0 }}"
        assert rule.message == "Level must be positive"
        assert rule.severity == "error"  # Default

    def test_validation_rule_severity(self):
        """Test validation rule severity validation."""
        # Valid severities
        for severity in ["error", "warning", "info"]:
            rule = ValidationRule(
                expression="{{ true }}", message="Test", severity=severity
            )
            assert rule.severity == severity

        # Invalid severity should raise error
        with pytest.raises(ValidationError):
            ValidationRule(expression="{{ true }}", message="Test", severity="invalid")

    def test_empty_expression_validation(self):
        """Test that empty expressions are rejected."""
        with pytest.raises(ValidationError):
            ValidationRule(expression="", message="Test")

        with pytest.raises(ValidationError):
            ValidationRule(expression="   ", message="Test")


class TestModelDefinition:
    """Test ModelDefinition class."""

    def test_basic_model_creation(self):
        """Test creating basic model definitions."""
        model = ModelDefinition(id="test_model", name="Test Model")
        assert model.id == "test_model"
        assert model.name == "Test Model"
        assert model.kind == "model"  # Default
        assert model.version == 1  # Default
        assert len(model.extends) == 0
        assert len(model.attributes) == 0

    def test_model_with_attributes(self):
        """Test model with attribute definitions."""
        model = ModelDefinition(
            id="test_model",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "level": {"type": "int", "default": 1},
            },
        )

        assert len(model.attributes) == 2
        assert isinstance(model.attributes["name"], AttributeDefinition)
        assert isinstance(model.attributes["level"], AttributeDefinition)
        assert model.attributes["name"].type == "str"
        assert model.attributes["level"].default == 1

    def test_model_with_inheritance(self):
        """Test model with inheritance."""
        model = ModelDefinition(
            id="child_model", name="Child Model", extends=["parent_model"]
        )
        assert model.extends == ["parent_model"]
        assert model.has_inheritance() is True

    def test_model_id_validation(self):
        """Test model ID validation."""
        # Valid IDs
        valid_ids = ["test", "test_model", "test-model", "TestModel123"]
        for model_id in valid_ids:
            model = ModelDefinition(id=model_id, name="Test")
            assert model.id == model_id

        # Invalid IDs should raise error
        with pytest.raises(ValidationError):
            ModelDefinition(id="", name="Test")

        with pytest.raises(ValidationError):
            ModelDefinition(id="invalid!id", name="Test")

    def test_version_validation(self):
        """Test version validation."""
        # Valid version
        model = ModelDefinition(id="test", name="Test", version=5)
        assert model.version == 5

        # Invalid version should raise error
        with pytest.raises(ValidationError):
            ModelDefinition(id="test", name="Test", version=0)

        with pytest.raises(ValidationError):
            ModelDefinition(id="test", name="Test", version=-1)

    def test_self_inheritance_validation(self):
        """Test that models cannot inherit from themselves."""
        with pytest.raises(ValidationError):
            ModelDefinition(
                id="self_inheriting",
                name="Self Inheriting",
                extends=["self_inheriting"],
            )

    def test_duplicate_parent_validation(self):
        """Test that duplicate parents are not allowed."""
        with pytest.raises(ValidationError):
            ModelDefinition(id="test", name="Test", extends=["parent", "parent"])

    def test_get_attribute(self):
        """Test getting attribute definitions."""
        model = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "name": {"type": "str", "required": True},
            },
        )

        attr = model.get_attribute("name")
        assert attr is not None
        assert attr.type == "str"

        missing_attr = model.get_attribute("missing")
        assert missing_attr is None

    def test_get_required_attributes(self):
        """Test getting required attributes."""
        model = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "required_field": {"type": "str", "required": True},
                "optional_field": {"type": "str", "required": False},
                "computed_field": {"type": "int", "derived": "{{ 42 }}"},
            },
        )

        required_attrs = model.get_required_attributes()
        assert len(required_attrs) == 1
        assert "required_field" in required_attrs

    def test_get_derived_attributes(self):
        """Test getting derived attributes."""
        model = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "normal_field": {"type": "str", "required": True},
                "computed_field": {"type": "int", "derived": "{{ 42 }}"},
            },
        )

        derived_attrs = model.get_derived_attributes()
        assert len(derived_attrs) == 1
        assert "computed_field" in derived_attrs

    def test_to_dict_and_from_dict(self):
        """Test dictionary conversion."""
        original_model = ModelDefinition(
            id="test",
            name="Test Model",
            attributes={
                "name": {"type": "str", "required": True},
                "level": {"type": "int", "default": 1},
            },
        )

        # Convert to dict
        model_dict = original_model.to_dict()
        assert isinstance(model_dict, dict)
        assert model_dict["id"] == "test"
        assert model_dict["name"] == "Test Model"

        # Convert back from dict
        restored_model = ModelDefinition.from_dict(model_dict)
        assert restored_model.id == original_model.id
        assert restored_model.name == original_model.name
        assert len(restored_model.attributes) == len(original_model.attributes)

    def test_invalid_attribute_definition(self):
        """Test handling of invalid attribute definitions."""
        with pytest.raises(ConfigurationError):
            ModelDefinition(
                id="test",
                name="Test",
                attributes={
                    "invalid_attr": {"invalid_field": "not_valid"}  # type: ignore
                },
            )
