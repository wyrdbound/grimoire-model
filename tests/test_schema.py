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
        # Test with invalid type value (should fail validation)
        with pytest.raises(ConfigurationError):
            ModelDefinition(
                id="test",
                name="Test",
                attributes={
                    "invalid_attr": {"type": "invalid!type"}  # type: ignore
                },
            )

    def test_nested_dict_auto_type(self):
        """Test that nested dict attributes automatically get type='dict'."""
        model = ModelDefinition(
            id="character",
            name="Character",
            attributes={
                "name": {"type": "str"},
                "hit_points": {
                    "max": {"type": "int"},
                    "current": {"type": "int"},
                },
            },
        )

        # Check that hit_points was assigned type='dict'
        hit_points_attr = model.attributes["hit_points"]
        assert isinstance(hit_points_attr, AttributeDefinition)
        assert hit_points_attr.type == "dict"

    def test_nested_dict_with_range_template(self):
        """Test nested dict attribute with template expressions in range."""
        model = ModelDefinition(
            id="character",
            name="Character",
            attributes={
                "hit_points": {
                    "max": {"type": "int"},
                    "current": {
                        "type": "int",
                        "range": "0..{{ hit_points.max }}",
                    },
                },
            },
        )

        # Verify the model was created successfully
        assert "hit_points" in model.attributes
        hit_points_attr = model.attributes["hit_points"]
        assert hit_points_attr.type == "dict"

    def test_nested_dict_with_enum(self):
        """Test nested dict attribute with enum constraint."""
        model = ModelDefinition(
            id="character",
            name="Character",
            attributes={
                "gender": {"type": "str", "enum": ["female", "male", "non-binary"]},
                "stats": {
                    "strength": {"type": "int", "range": "1..20"},
                    "dexterity": {"type": "int", "range": "1..20"},
                },
            },
        )

        # Verify both attributes created correctly
        assert model.attributes["gender"].enum == [
            "female",
            "male",
            "non-binary",
        ]
        assert model.attributes["stats"].type == "dict"

    def test_explicit_dict_type_preserved(self):
        """Test that explicit type='dict' is preserved."""
        model = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "explicit_dict": {"type": "dict", "required": False},
            },
        )

        # Verify explicit type is preserved
        assert model.attributes["explicit_dict"].type == "dict"
        assert model.attributes["explicit_dict"].required is False

    def test_deeply_nested_dict_inference(self):
        """Test multiple levels of nested dict attributes."""
        model = ModelDefinition(
            id="character",
            name="Character",
            attributes={
                "stats": {
                    "physical": {
                        "strength": {"type": "int", "range": "1..20"},
                        "dexterity": {"type": "int", "range": "1..20"},
                    },
                    "mental": {
                        "intelligence": {"type": "int", "range": "1..20"},
                        "wisdom": {"type": "int", "range": "1..20"},
                    },
                },
            },
        )

        # Verify that stats is inferred as dict type
        assert model.attributes["stats"].type == "dict"

    def test_empty_dict_requires_explicit_type(self):
        """Test that empty dict {} requires explicit type field."""
        # Empty dict should fail validation (no 'type' field, no typed nested)
        with pytest.raises(ConfigurationError):
            ModelDefinition(
                id="test",
                name="Test",
                attributes={
                    "empty": {},  # No type, no nested typed attributes
                },
            )

    def test_dict_with_only_default_requires_explicit_type(self):
        """Test that dict with only 'default' field requires explicit type."""
        # Has 'default' but no 'type' and no typed nested attributes
        with pytest.raises(ConfigurationError):
            ModelDefinition(
                id="test",
                name="Test",
                attributes={
                    "config": {"default": {"key": "value"}},
                },
            )

    def test_dict_with_only_enum_requires_explicit_type(self):
        """Test that dict with only 'enum' field requires explicit type."""
        # Has 'enum' but no 'type' and no typed nested attributes
        with pytest.raises(ConfigurationError):
            ModelDefinition(
                id="test",
                name="Test",
                attributes={
                    "status": {"enum": ["active", "inactive"]},
                },
            )

    def test_dict_with_untyped_nested_values_requires_explicit_type(self):
        """Test that dict with non-typed nested values requires explicit type."""
        # Nested values without 'type' field should fail
        with pytest.raises(ConfigurationError):
            ModelDefinition(
                id="test",
                name="Test",
                attributes={
                    "config": {
                        "some_key": "some_value",  # Not a typed attribute
                        "another_key": 123,
                    },
                },
            )

    def test_mixed_nested_some_typed_infers_dict(self):
        """Test that at least one typed nested field triggers dict inference."""
        model = ModelDefinition(
            id="test",
            name="Test",
            attributes={
                "metadata": {
                    "created_at": {"type": "str"},
                    # Other fields in the dict that aren't typed are ignored
                },
            },
        )

        # Should infer type='dict' because 'created_at' has a type
        assert model.attributes["metadata"].type == "dict"

    def test_complete_character_model_with_nested_dicts(self):
        """Test the complete character model from the issue."""
        model = ModelDefinition(
            kind="model",
            id="character",
            name="Character",
            description="Character model",
            version=1,
            attributes={
                "name": {"type": "str"},
                "gender": {"type": "str", "enum": ["female", "male", "non-binary"]},
                "xp": {"type": "int", "default": 0, "range": "0..1000"},
                "level": {"type": "int", "default": 1, "range": "1..10"},
                "hit_points": {
                    "max": {"type": "int"},
                    "current": {
                        "type": "int",
                        "range": "0..{{ hit_points.max }}",
                    },
                },
            },
        )

        # Verify the model structure
        assert model.id == "character"
        assert model.attributes["name"].type == "str"
        assert model.attributes["gender"].enum == ["female", "male", "non-binary"]
        assert model.attributes["hit_points"].type == "dict"
