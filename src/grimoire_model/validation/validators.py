"""
Field validators and validation rules for grimoire-model package.

Provides a comprehensive validation system with built-in validators for common
data types and constraints, plus support for custom validation rules.
"""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..core.schema import AttributeDefinition


class FieldValidator(ABC):
    """Abstract base class for field validators."""

    @abstractmethod
    def validate(
        self, value: Any, field_name: str, attr_def: AttributeDefinition
    ) -> List[str]:
        """Validate a field value.

        Args:
            value: The value to validate
            field_name: Name of the field being validated
            attr_def: Attribute definition for the field

        Returns:
            List of validation error messages (empty if valid)
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get the validator name."""
        pass


class TypeValidator(FieldValidator):
    """Validates field types according to attribute definitions."""

    def validate(
        self, value: Any, field_name: str, attr_def: AttributeDefinition
    ) -> List[str]:
        """Validate that the value matches the expected type."""
        if value is None:
            if attr_def.required and not attr_def.computed:
                return [f"Required field '{field_name}' cannot be None"]
            return []

        expected_type = attr_def.type
        errors = []

        # Handle basic types
        if expected_type == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(
                    f"Field '{field_name}' must be an integer, got "
                    f"{type(value).__name__}"
                )
        elif expected_type == "float":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(
                    f"Field '{field_name}' must be a number, got {type(value).__name__}"
                )
        elif expected_type == "str":
            if not isinstance(value, str):
                errors.append(
                    f"Field '{field_name}' must be a string, got {type(value).__name__}"
                )
        elif expected_type == "bool":
            if not isinstance(value, bool):
                errors.append(
                    f"Field '{field_name}' must be a boolean, got "
                    f"{type(value).__name__}"
                )
        elif expected_type == "list":
            if not isinstance(value, list):
                errors.append(
                    f"Field '{field_name}' must be a list, got {type(value).__name__}"
                )
        elif expected_type == "dict":
            if not isinstance(value, dict):
                errors.append(
                    f"Field '{field_name}' must be a dictionary, got "
                    f"{type(value).__name__}"
                )
        elif expected_type == "any":
            # Any type is always valid
            pass
        else:
            # Assume it's a model reference or custom type
            # In a full implementation, this would validate against model registry
            pass

        return errors

    def get_name(self) -> str:
        """Get the validator name."""
        return "type"


class RequiredValidator(FieldValidator):
    """Validates that required fields are present and not None."""

    def validate(
        self, value: Any, field_name: str, attr_def: AttributeDefinition
    ) -> List[str]:
        """Validate that required fields are present."""
        if attr_def.required and not attr_def.computed:
            if value is None:
                return [f"Required field '{field_name}' is missing"]
        return []

    def get_name(self) -> str:
        """Get the validator name."""
        return "required"


class RangeValidator(FieldValidator):
    """Validates numeric ranges according to attribute definitions."""

    def validate(
        self, value: Any, field_name: str, attr_def: AttributeDefinition
    ) -> List[str]:
        """Validate that numeric values fall within specified ranges."""
        if value is None or attr_def.range is None:
            return []

        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return []  # Type validation is handled by TypeValidator

        errors = []
        range_spec = attr_def.range

        try:
            # Parse range specification
            if ".." in range_spec:
                # Range format: "min..max", "min..", or "..max"
                parts = range_spec.split("..")
                min_val = None if parts[0] == "" else float(parts[0])
                max_val = None if parts[1] == "" else float(parts[1])

                if min_val is not None and value < min_val:
                    errors.append(
                        f"Field '{field_name}' value {value} is below minimum {min_val}"
                    )
                if max_val is not None and value > max_val:
                    errors.append(
                        f"Field '{field_name}' value {value} is above maximum {max_val}"
                    )

            elif ">=" in range_spec:
                min_val = float(range_spec.replace(">=", "").strip())
                if value < min_val:
                    errors.append(
                        f"Field '{field_name}' value {value} is below minimum {min_val}"
                    )

            elif "<=" in range_spec:
                max_val = float(range_spec.replace("<=", "").strip())
                if value > max_val:
                    errors.append(
                        f"Field '{field_name}' value {value} is above maximum {max_val}"
                    )

            elif ">" in range_spec:
                min_val = float(range_spec.replace(">", "").strip())
                if value <= min_val:
                    errors.append(
                        f"Field '{field_name}' value {value} must be greater than "
                        f"{min_val}"
                    )

            elif "<" in range_spec:
                max_val = float(range_spec.replace("<", "").strip())
                if value >= max_val:
                    errors.append(
                        f"Field '{field_name}' value {value} must be less than "
                        f"{max_val}"
                    )

            elif "=" in range_spec:
                exact_val = float(range_spec.replace("=", "").strip())
                if value != exact_val:
                    errors.append(
                        f"Field '{field_name}' value {value} must equal {exact_val}"
                    )

        except (ValueError, IndexError):
            errors.append(
                f"Invalid range specification for field '{field_name}': {range_spec}"
            )

        return errors

    def get_name(self) -> str:
        """Get the validator name."""
        return "range"


class EnumValidator(FieldValidator):
    """Validates that values are within allowed enumeration values."""

    def validate(
        self, value: Any, field_name: str, attr_def: AttributeDefinition
    ) -> List[str]:
        """Validate that the value is in the allowed enumeration."""
        if value is None or attr_def.enum is None:
            return []

        errors = []
        allowed_values = attr_def.enum

        # Convert value to string for comparison (enum values are stored as strings)
        str_value = str(value)

        if str_value not in allowed_values:
            errors.append(
                f"Field '{field_name}' value '{value}' is not in allowed "
                f"values: {allowed_values}"
            )

        return errors

    def get_name(self) -> str:
        """Get the validator name."""
        return "enum"


class PatternValidator(FieldValidator):
    """Validates string patterns using regular expressions."""

    def validate(
        self, value: Any, field_name: str, attr_def: AttributeDefinition
    ) -> List[str]:
        """Validate that string values match the specified pattern."""
        if value is None or attr_def.pattern is None:
            return []

        if not isinstance(value, str):
            return []  # Type validation is handled by TypeValidator

        errors = []
        pattern = attr_def.pattern

        try:
            if not re.match(pattern, value):
                errors.append(
                    f"Field '{field_name}' value '{value}' does not match "
                    f"pattern '{pattern}'"
                )
        except re.error as e:
            errors.append(
                f"Invalid regex pattern for field '{field_name}': {pattern} ({e})"
            )

        return errors

    def get_name(self) -> str:
        """Get the validator name."""
        return "pattern"


class LengthValidator(FieldValidator):
    """Validates length constraints for strings and collections."""

    def validate(
        self, value: Any, field_name: str, attr_def: AttributeDefinition
    ) -> List[str]:
        """Validate length constraints."""
        if value is None:
            return []

        # Only validate length for strings, lists, and dicts
        if not isinstance(value, (str, list, dict)):
            return []

        errors = []
        length = len(value)

        # Check if range constraint applies to length
        if attr_def.range and attr_def.type in ["str", "list", "dict"]:
            range_spec = attr_def.range

            try:
                if ".." in range_spec:
                    parts = range_spec.split("..")
                    min_len = None if parts[0] == "" else int(parts[0])
                    max_len = None if parts[1] == "" else int(parts[1])

                    if min_len is not None and length < min_len:
                        errors.append(
                            f"Field '{field_name}' length {length} is below "
                            f"minimum {min_len}"
                        )
                    if max_len is not None and length > max_len:
                        errors.append(
                            f"Field '{field_name}' length {length} is above "
                            f"maximum {max_len}"
                        )

            except (ValueError, IndexError):
                # Not a valid length range, skip
                pass

        return errors

    def get_name(self) -> str:
        """Get the validator name."""
        return "length"


class ValidationEngine:
    """Main validation engine that coordinates all field validators."""

    def __init__(self):
        self.validators: Dict[str, FieldValidator] = {}
        self._register_default_validators()

    def _register_default_validators(self) -> None:
        """Register default validators."""
        default_validators = [
            RequiredValidator(),
            TypeValidator(),
            RangeValidator(),
            EnumValidator(),
            PatternValidator(),
            LengthValidator(),
        ]

        for validator in default_validators:
            self.register_validator(validator)

    def register_validator(self, validator: FieldValidator) -> None:
        """Register a field validator."""
        self.validators[validator.get_name()] = validator

    def unregister_validator(self, name: str) -> None:
        """Unregister a field validator."""
        if name in self.validators:
            del self.validators[name]

    def validate_field(
        self,
        value: Any,
        field_name: str,
        attr_def: AttributeDefinition,
        enabled_validators: Optional[List[str]] = None,
    ) -> List[str]:
        """Validate a single field value.

        Args:
            value: The value to validate
            field_name: Name of the field
            attr_def: Attribute definition
            enabled_validators: List of validator names to use (None = all)

        Returns:
            List of validation error messages
        """
        errors = []
        validators_to_run = enabled_validators or list(self.validators.keys())

        for validator_name in validators_to_run:
            if validator_name in self.validators:
                validator = self.validators[validator_name]
                field_errors = validator.validate(value, field_name, attr_def)
                errors.extend(field_errors)

        return errors

    def validate_data(
        self,
        data: Dict[str, Any],
        attributes: Dict[str, AttributeDefinition],
        enabled_validators: Optional[List[str]] = None,
    ) -> List[str]:
        """Validate all fields in a data dictionary.

        Args:
            data: The data to validate
            attributes: Attribute definitions for validation
            enabled_validators: List of validator names to use (None = all)

        Returns:
            List of all validation error messages
        """
        all_errors = []

        # Validate existing fields
        for field_name, value in data.items():
            if field_name in attributes:
                attr_def = attributes[field_name]
                field_errors = self.validate_field(
                    value, field_name, attr_def, enabled_validators
                )
                all_errors.extend(field_errors)

        # Check for missing required fields
        for field_name, attr_def in attributes.items():
            if field_name not in data:
                # Use None value to trigger required validation
                field_errors = self.validate_field(
                    None, field_name, attr_def, enabled_validators
                )
                all_errors.extend(field_errors)

        return all_errors


# Global validation engine instance
_validation_engine = ValidationEngine()


def get_validation_engine() -> ValidationEngine:
    """Get the global validation engine instance."""
    return _validation_engine


def validate_field_value(
    value: Any,
    field_name: str,
    attr_def: AttributeDefinition,
    enabled_validators: Optional[List[str]] = None,
) -> List[str]:
    """Convenience function to validate a single field value."""
    return _validation_engine.validate_field(
        value, field_name, attr_def, enabled_validators
    )


def validate_model_data(
    data: Dict[str, Any],
    attributes: Dict[str, AttributeDefinition],
    enabled_validators: Optional[List[str]] = None,
) -> List[str]:
    """Convenience function to validate all model data."""
    return _validation_engine.validate_data(data, attributes, enabled_validators)
