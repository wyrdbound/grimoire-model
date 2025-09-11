"""Tests for validation functionality."""

import pytest
from pydantic import ValidationError

from grimoire_model.core.schema import AttributeDefinition
from grimoire_model.validation.validators import (
    EnumValidator,
    LengthValidator,
    PatternValidator,
    RangeValidator,
    RequiredValidator,
    TypeValidator,
    ValidationEngine,
    get_validation_engine,
    validate_field_value,
    validate_model_data,
)


class TestTypeValidator:
    """Test TypeValidator class."""

    def test_integer_validation(self):
        """Test integer type validation."""
        validator = TypeValidator()
        attr_def = AttributeDefinition(type="int", required=True)

        # Valid integers
        errors = validator.validate(42, "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate(-10, "test_field", attr_def)
        assert len(errors) == 0

        # Invalid types
        errors = validator.validate("not_int", "test_field", attr_def)
        assert len(errors) == 1
        assert "must be an integer" in errors[0]

        errors = validator.validate(3.14, "test_field", attr_def)
        assert len(errors) == 1

        # Bool should not be considered int
        errors = validator.validate(True, "test_field", attr_def)
        assert len(errors) == 1

    def test_float_validation(self):
        """Test float type validation."""
        validator = TypeValidator()
        attr_def = AttributeDefinition(type="float", required=True)

        # Valid numbers
        errors = validator.validate(3.14, "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate(
            42, "test_field", attr_def
        )  # int should be valid for float
        assert len(errors) == 0

        # Invalid types
        errors = validator.validate("not_float", "test_field", attr_def)
        assert len(errors) == 1
        assert "must be a number" in errors[0]

    def test_string_validation(self):
        """Test string type validation."""
        validator = TypeValidator()
        attr_def = AttributeDefinition(type="str", required=True)

        # Valid strings
        errors = validator.validate("hello", "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate("", "test_field", attr_def)
        assert len(errors) == 0

        # Invalid types
        errors = validator.validate(42, "test_field", attr_def)
        assert len(errors) == 1
        assert "must be a string" in errors[0]

    def test_boolean_validation(self):
        """Test boolean type validation."""
        validator = TypeValidator()
        attr_def = AttributeDefinition(type="bool", required=True)

        # Valid booleans
        errors = validator.validate(True, "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate(False, "test_field", attr_def)
        assert len(errors) == 0

        # Invalid types
        errors = validator.validate(1, "test_field", attr_def)
        assert len(errors) == 1
        assert "must be a boolean" in errors[0]

    def test_list_validation(self):
        """Test list type validation."""
        validator = TypeValidator()
        attr_def = AttributeDefinition(type="list", required=True)

        # Valid lists
        errors = validator.validate([1, 2, 3], "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate([], "test_field", attr_def)
        assert len(errors) == 0

        # Invalid types
        errors = validator.validate("not_list", "test_field", attr_def)
        assert len(errors) == 1
        assert "must be a list" in errors[0]

    def test_dict_validation(self):
        """Test dict type validation."""
        validator = TypeValidator()
        attr_def = AttributeDefinition(type="dict", required=True)

        # Valid dicts
        errors = validator.validate({"key": "value"}, "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate({}, "test_field", attr_def)
        assert len(errors) == 0

        # Invalid types
        errors = validator.validate("not_dict", "test_field", attr_def)
        assert len(errors) == 1
        assert "must be a dictionary" in errors[0]

    def test_any_type_validation(self):
        """Test 'any' type validation."""
        validator = TypeValidator()
        attr_def = AttributeDefinition(type="any", required=True)

        # Any type should be valid
        for value in [42, "string", True, [1, 2], {"key": "value"}, None]:
            errors = validator.validate(value, "test_field", attr_def)
            if value is None:
                # None handling depends on required field logic
                continue
            assert len(errors) == 0

    def test_none_value_handling(self):
        """Test None value handling for required fields."""
        validator = TypeValidator()

        # Required field with None should produce error
        required_attr = AttributeDefinition(type="str", required=True)
        errors = validator.validate(None, "test_field", required_attr)
        assert len(errors) == 1
        assert "cannot be None" in errors[0]

        # Optional field with None should be OK
        optional_attr = AttributeDefinition(type="str", required=False)
        errors = validator.validate(None, "test_field", optional_attr)
        assert len(errors) == 0

        # Computed field with None should be OK
        computed_attr = AttributeDefinition(
            type="str", required=True, derived="computed_value"
        )
        errors = validator.validate(None, "test_field", computed_attr)
        assert len(errors) == 0


class TestRequiredValidator:
    """Test RequiredValidator class."""

    def test_required_field_validation(self):
        """Test required field validation."""
        validator = RequiredValidator()

        # Required field with None should fail
        required_attr = AttributeDefinition(type="str", required=True)
        errors = validator.validate(None, "test_field", required_attr)
        assert len(errors) == 1
        assert "is missing" in errors[0]

        # Required field with value should pass
        errors = validator.validate("value", "test_field", required_attr)
        assert len(errors) == 0

        # Optional field with None should pass
        optional_attr = AttributeDefinition(type="str", required=False)
        errors = validator.validate(None, "test_field", optional_attr)
        assert len(errors) == 0

        # Computed field should pass even if required and None
        computed_attr = AttributeDefinition(
            type="str", required=True, derived="computed_value"
        )
        errors = validator.validate(None, "test_field", computed_attr)
        assert len(errors) == 0


class TestRangeValidator:
    """Test RangeValidator class."""

    def test_range_validation(self):
        """Test numeric range validation."""
        validator = RangeValidator()

        # Test min..max format
        attr_def = AttributeDefinition(type="int", range="1..10")

        errors = validator.validate(5, "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate(0, "test_field", attr_def)
        assert len(errors) == 1
        assert "below minimum" in errors[0]

        errors = validator.validate(15, "test_field", attr_def)
        assert len(errors) == 1
        assert "above maximum" in errors[0]

    def test_open_ranges(self):
        """Test open range validation."""
        validator = RangeValidator()

        # Test min.. format
        attr_def = AttributeDefinition(type="int", range="5..")
        errors = validator.validate(10, "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate(3, "test_field", attr_def)
        assert len(errors) == 1

        # Test ..max format
        attr_def = AttributeDefinition(type="int", range="..10")
        errors = validator.validate(5, "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate(15, "test_field", attr_def)
        assert len(errors) == 1

    def test_comparison_operators(self):
        """Test comparison operator ranges."""
        validator = RangeValidator()

        # Test >= operator
        attr_def = AttributeDefinition(type="int", range=">=5")
        errors = validator.validate(5, "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate(3, "test_field", attr_def)
        assert len(errors) == 1

        # Test > operator
        attr_def = AttributeDefinition(type="int", range=">5")
        errors = validator.validate(6, "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate(5, "test_field", attr_def)
        assert len(errors) == 1

    def test_non_numeric_values(self):
        """Test that non-numeric values are ignored."""
        validator = RangeValidator()
        attr_def = AttributeDefinition(type="str", range="1..10")

        # String values should not trigger range validation
        errors = validator.validate("hello", "test_field", attr_def)
        assert len(errors) == 0

    def test_invalid_range_specification(self):
        """Test handling of invalid range specifications."""

        # Invalid range should be caught at AttributeDefinition creation
        with pytest.raises(ValidationError):
            AttributeDefinition(type="int", range="invalid_range")


class TestEnumValidator:
    """Test EnumValidator class."""

    def test_enum_validation(self):
        """Test enumeration validation."""
        validator = EnumValidator()
        attr_def = AttributeDefinition(type="str", enum=["red", "green", "blue"])

        # Valid enum values
        errors = validator.validate("red", "test_field", attr_def)
        assert len(errors) == 0

        # Invalid enum value
        errors = validator.validate("yellow", "test_field", attr_def)
        assert len(errors) == 1
        assert "not in allowed values" in errors[0]

    def test_enum_with_none(self):
        """Test enum validation with None values."""
        validator = EnumValidator()
        attr_def = AttributeDefinition(type="str", enum=["red", "green", "blue"])

        # None value should be ignored by enum validator
        errors = validator.validate(None, "test_field", attr_def)
        assert len(errors) == 0

    def test_enum_type_conversion(self):
        """Test that values are converted to strings for enum comparison."""
        validator = EnumValidator()
        attr_def = AttributeDefinition(type="int", enum=["1", "2", "3"])

        # Integer should be converted to string for comparison
        errors = validator.validate(1, "test_field", attr_def)
        assert len(errors) == 0

        errors = validator.validate(4, "test_field", attr_def)
        assert len(errors) == 1


class TestPatternValidator:
    """Test PatternValidator class."""

    def test_pattern_validation(self):
        """Test regex pattern validation."""
        validator = PatternValidator()
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        attr_def = AttributeDefinition(type="str", pattern=email_pattern)

        # Valid email
        errors = validator.validate("test@example.com", "email", attr_def)
        assert len(errors) == 0

        # Invalid email
        errors = validator.validate("invalid-email", "email", attr_def)
        assert len(errors) == 1
        assert "does not match pattern" in errors[0]

    def test_pattern_with_non_string(self):
        """Test pattern validation with non-string values."""
        validator = PatternValidator()
        attr_def = AttributeDefinition(type="str", pattern=r"^\d+$")

        # Non-string values should be ignored
        errors = validator.validate(123, "test_field", attr_def)
        assert len(errors) == 0

    def test_invalid_regex_pattern(self):
        """Test handling of invalid regex patterns."""
        validator = PatternValidator()
        attr_def = AttributeDefinition(type="str", pattern="[invalid_regex")

        errors = validator.validate("test", "test_field", attr_def)
        assert len(errors) == 1
        assert "Invalid regex pattern" in errors[0]


class TestLengthValidator:
    """Test LengthValidator class."""

    def test_string_length_validation(self):
        """Test string length validation."""
        validator = LengthValidator()
        attr_def = AttributeDefinition(type="str", range="5..10")

        # Valid length
        errors = validator.validate("hello", "test_field", attr_def)
        assert len(errors) == 0

        # Too short
        errors = validator.validate("hi", "test_field", attr_def)
        assert len(errors) == 1
        assert "below minimum" in errors[0]

        # Too long
        errors = validator.validate("this is too long", "test_field", attr_def)
        assert len(errors) == 1
        assert "above maximum" in errors[0]

    def test_list_length_validation(self):
        """Test list length validation."""
        validator = LengthValidator()
        attr_def = AttributeDefinition(type="list", range="2..5")

        # Valid length
        errors = validator.validate([1, 2, 3], "test_field", attr_def)
        assert len(errors) == 0

        # Too short
        errors = validator.validate([1], "test_field", attr_def)
        assert len(errors) == 1

        # Too long
        errors = validator.validate([1, 2, 3, 4, 5, 6], "test_field", attr_def)
        assert len(errors) == 1

    def test_non_collection_types(self):
        """Test that non-collection types are ignored."""
        validator = LengthValidator()
        attr_def = AttributeDefinition(type="int", range="5..10")

        # Integer values should not trigger length validation
        errors = validator.validate(42, "test_field", attr_def)
        assert len(errors) == 0


class TestValidationEngine:
    """Test ValidationEngine class."""

    def test_field_validation(self):
        """Test single field validation."""
        engine = ValidationEngine()
        attr_def = AttributeDefinition(type="str", required=True)

        # Valid field
        errors = engine.validate_field("hello", "test_field", attr_def)
        assert len(errors) == 0

        # Invalid field
        errors = engine.validate_field(None, "test_field", attr_def)
        assert len(errors) > 0

    def test_data_validation(self):
        """Test full data validation."""
        engine = ValidationEngine()
        attributes = {
            "name": AttributeDefinition(type="str", required=True),
            "age": AttributeDefinition(type="int", range="0..120"),
        }

        # Valid data
        data = {"name": "John", "age": 30}
        errors = engine.validate_data(data, attributes)
        assert len(errors) == 0

        # Invalid data
        data = {"age": 150}  # Missing name, invalid age
        errors = engine.validate_data(data, attributes)
        assert len(errors) >= 2  # At least name missing and age out of range

    def test_validator_registration(self):
        """Test custom validator registration."""
        from grimoire_model.validation.validators import FieldValidator

        engine = ValidationEngine()

        # Register custom validator
        class CustomValidator(FieldValidator):
            def get_name(self):
                return "custom"

            def validate(self, value, field_name, attr_def):
                if value == "forbidden":
                    return [f"Field {field_name} has forbidden value"]
                return []

        custom_validator = CustomValidator()
        engine.register_validator(custom_validator)

        # Test custom validator is used
        attr_def = AttributeDefinition(type="str")
        errors = engine.validate_field("forbidden", "test", attr_def, ["custom"])
        assert len(errors) == 1
        assert "forbidden value" in errors[0]


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_validate_field_value(self):
        """Test validate_field_value convenience function."""
        attr_def = AttributeDefinition(type="str", required=True)

        errors = validate_field_value("hello", "test_field", attr_def)
        assert len(errors) == 0

        errors = validate_field_value(None, "test_field", attr_def)
        assert len(errors) > 0

    def test_validate_model_data(self):
        """Test validate_model_data convenience function."""
        attributes = {
            "name": AttributeDefinition(type="str", required=True),
        }

        errors = validate_model_data({"name": "John"}, attributes)
        assert len(errors) == 0

        errors = validate_model_data({}, attributes)  # Missing required field
        assert len(errors) > 0

    def test_get_validation_engine(self):
        """Test get_validation_engine function."""
        engine = get_validation_engine()
        assert isinstance(engine, ValidationEngine)
