"""
Field validators and validation rules for grimoire-model package.

Provides a comprehensive validation system with built-in validators for common
data types and constraints, plus support for custom validation rules.
"""

import re
import threading
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Tuple

from ..core.schema import BASIC_TYPES, AttributeDefinition


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
            if not attr_def.optional and not attr_def.computed:
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
            elif attr_def.of is not None and attr_def.of in BASIC_TYPES:
                # A primitive `of`: validate each element with indexed paths
                # (R33). A model-typed `of` is built and checked by the model.
                element_def = AttributeDefinition(type=attr_def.of)
                for index, element in enumerate(value):
                    errors.extend(
                        self.validate(element, f"{field_name}[{index}]", element_def)
                    )
        elif expected_type == "dict":
            if not isinstance(value, dict):
                errors.append(
                    f"Field '{field_name}' must be a dictionary, got "
                    f"{type(value).__name__}"
                )
        elif expected_type == "roll":
            # The spec's dice-notation basic type: a string like "1d6". A
            # validator registered for `roll` also runs (below).
            if not isinstance(value, str):
                errors.append(
                    f"Field '{field_name}' must be a roll (a string), got "
                    f"{type(value).__name__}"
                )
        elif expected_type == "roll_result":
            # The result of rolling: its shape belongs to the dice library,
            # so it is not type-checked here. A registered validator still runs.
            pass
        else:
            # A model-typed attribute is checked by the model (R32); a
            # registered custom primitive's validator runs below.
            pass

        # A validator registered for the type (a custom primitive, or the
        # spec's `roll`/`roll_result`) is called with the value.
        errors.extend(self._validate_registered_primitive(value, field_name, attr_def))

        return errors

    @staticmethod
    def _validate_registered_primitive(
        value: Any, field_name: str, attr_def: AttributeDefinition
    ) -> List[str]:
        """Call a registered primitive's validator, if its type has one.

        The contract is the one documented on ``register_primitive_type``:
        the validator receives the value and returns
        ``(is_valid, error_message)``. A validator that raises is a validation
        error, not a crash. An unregistered type name is a model id; the model
        rejects it if it cannot be resolved.
        """
        from ..core.primitive_registry import get_default_primitive_registry

        registry = get_default_primitive_registry()
        if not registry.is_registered(attr_def.type):
            return []

        validator = registry.get_validator(attr_def.type)
        if validator is None:
            return []

        try:
            is_valid, message = validator(value)
        except Exception as exc:  # noqa: BLE001 - reported as a validation error
            return [f"Field '{field_name}' failed validation: {exc}"]

        if is_valid:
            return []
        return [f"Field '{field_name}': {message}"]

    def get_name(self) -> str:
        """Get the validator name."""
        return "type"


_RANGE_RE = re.compile(
    r"^\s*(?:(?P<lo>[-+]?\d+(?:\.\d+)?)\s*\.\.\s*(?P<hi>[-+]?\d+(?:\.\d+)?)?"
    r"|\.\.\s*(?P<hi_only>[-+]?\d+(?:\.\d+)?)"
    r"|>=\s*(?P<ge>[-+]?\d+(?:\.\d+)?)"
    r"|>\s*(?P<gt>[-+]?\d+(?:\.\d+)?)"
    r"|<=\s*(?P<le>[-+]?\d+(?:\.\d+)?)"
    r"|<\s*(?P<lt>[-+]?\d+(?:\.\d+)?)"
    r"|=\s*(?P<eq>[-+]?\d+(?:\.\d+)?))\s*$"
)


def parse_range(spec: str) -> Tuple[Optional[float], Optional[float], bool, bool]:
    """Parse every documented range form into bounds and inclusivity.

    Accepts ``a..b``, ``a..``, ``..b``, ``>=a``, ``<=b``, ``>a``, ``<b``, ``=a``
    (with optional spaces). Returns ``(lower, upper, lower_inclusive,
    upper_inclusive)``; a bound is ``None`` when unbounded. Raises
    ``ValueError`` on anything else, so an unparseable range is an error for
    every type (R36).
    """
    match = _RANGE_RE.match(spec)
    if match is None:
        raise ValueError(f"Invalid range specification: {spec!r}")

    groups = match.groupdict()
    if groups["lo"] is not None:
        lower = float(groups["lo"])
        upper = float(groups["hi"]) if groups["hi"] else None
        return lower, upper, True, True
    if groups["hi_only"] is not None:
        return None, float(groups["hi_only"]), True, True
    if groups["ge"] is not None:
        return float(groups["ge"]), None, True, True
    if groups["gt"] is not None:
        return float(groups["gt"]), None, False, True
    if groups["le"] is not None:
        return None, float(groups["le"]), True, True
    if groups["lt"] is not None:
        return None, float(groups["lt"]), True, False
    return float(groups["eq"]), float(groups["eq"]), True, True


def _fmt(bound: float) -> Any:
    """Format a numeric bound: an int when it is whole, else the float."""
    return int(bound) if float(bound).is_integer() else bound


def _range_errors(
    value: float, field_name: str, spec: str, length_mode: bool
) -> List[str]:
    """Errors for ``value`` against ``spec``; unit names differ by mode."""
    lower, upper, lower_inc, upper_inc = parse_range(spec)
    noun = "length" if length_mode else "value"
    shown = int(value) if float(value).is_integer() else value
    errors: List[str] = []

    # An exact range (`=a`, stored as lower == upper) is one equality check.
    if lower is not None and upper is not None and lower == upper:
        if value != lower:
            errors.append(
                f"Field '{field_name}' {noun} {shown} must equal {_fmt(lower)}"
            )
        return errors

    if lower is not None:
        if lower_inc:
            if value < lower:
                errors.append(
                    f"Field '{field_name}' {noun} {shown} is below minimum "
                    f"{_fmt(lower)}"
                )
        elif value <= lower:
            errors.append(
                f"Field '{field_name}' {noun} {shown} must be greater than "
                f"{_fmt(lower)}"
            )
    if upper is not None:
        if upper_inc:
            if value > upper:
                errors.append(
                    f"Field '{field_name}' {noun} {shown} is above maximum "
                    f"{_fmt(upper)}"
                )
        elif value >= upper:
            errors.append(
                f"Field '{field_name}' {noun} {shown} must be less than {_fmt(upper)}"
            )
    return errors


class RequiredValidator(FieldValidator):
    """Validates that required fields are present and not None."""

    def validate(
        self, value: Any, field_name: str, attr_def: AttributeDefinition
    ) -> List[str]:
        """Validate that required fields are present."""
        if not attr_def.optional and not attr_def.computed:
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

        try:
            return _range_errors(float(value), field_name, attr_def.range, False)
        except ValueError:
            return [
                f"Invalid range specification for field '{field_name}': "
                f"{attr_def.range}"
            ]

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

        # A range on a str/list/dict is a length constraint (R36). Parsed by the
        # same parser the numeric validator uses; an unparseable range is an
        # error, not skipped. A length bound must be a whole number.
        if attr_def.range and attr_def.type in ["str", "list", "dict"]:
            try:
                lower, upper, lower_inc, upper_inc = parse_range(attr_def.range)
                for bound in (lower, upper):
                    if bound is not None and not float(bound).is_integer():
                        raise ValueError("a length bound must be a whole number")
                errors.extend(
                    _range_errors(float(length), field_name, attr_def.range, True)
                )
                del lower, upper, lower_inc, upper_inc
            except ValueError:
                errors.append(
                    f"Invalid range specification for field '{field_name}': "
                    f"{attr_def.range}"
                )

        return errors

    def get_name(self) -> str:
        """Get the validator name."""
        return "length"


class ValidationEngine:
    """Main validation engine that coordinates all field validators."""

    def __init__(self):
        self.validators: Dict[str, FieldValidator] = {}
        self._lock = threading.RLock()
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
        with self._lock:
            self.validators[validator.get_name()] = validator

    def unregister_validator(self, name: str) -> None:
        """Unregister a field validator."""
        with self._lock:
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
        with self._lock:
            validators_to_run = enabled_validators or list(self.validators.keys())
            # A snapshot of the validator objects, so a concurrent
            # register/unregister cannot change the set mid-iteration.
            selected = [
                self.validators[name]
                for name in validators_to_run
                if name in self.validators
            ]

        for validator in selected:
            field_errors = validator.validate(value, field_name, attr_def)
            errors.extend(field_errors)

        return errors

    def _validate_group(
        self,
        data: Mapping[str, Any],
        attributes: Dict[str, AttributeDefinition],
        prefix: str,
        enabled_validators: Optional[List[str]] = None,
    ) -> List[str]:
        """Validate the leaves of an anonymous nested group.

        Errors name the leaf by its full dotted path (``hit_points.current``)
        so two groups sharing a leaf name stay distinguishable.
        """
        errors: List[str] = []

        # Present leaves, plus any key that is not declared at this depth.
        for name, value in data.items():
            if name not in attributes:
                errors.append(f"Undeclared attribute '{prefix}.{name}'")
                continue
            attr_def = attributes[name]
            path = f"{prefix}.{name}"
            if attr_def.attributes:
                if isinstance(value, dict):
                    errors.extend(
                        self._validate_group(
                            value, attr_def.attributes, path, enabled_validators
                        )
                    )
                continue
            errors.extend(
                self.validate_field(value, path, attr_def, enabled_validators)
            )

        # Absent leaves
        for name, attr_def in attributes.items():
            if name in data or attr_def.attributes:
                continue
            errors.extend(
                self.validate_field(
                    None, f"{prefix}.{name}", attr_def, enabled_validators
                )
            )

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

        # Validate existing fields, reporting any key that is not declared.
        for field_name, value in data.items():
            if field_name not in attributes:
                all_errors.append(f"Undeclared attribute '{field_name}'")
                continue
            attr_def = attributes[field_name]

            # Anonymous nested group: validate its leaves, not the group.
            # A group has no value of its own, so validating it as a
            # `dict` would check nothing its author declared. A group whose
            # value is not a mapping is an error (R31).
            if attr_def.attributes:
                if isinstance(value, Mapping):
                    all_errors.extend(
                        self._validate_group(
                            value,
                            attr_def.attributes,
                            field_name,
                            enabled_validators,
                        )
                    )
                else:
                    all_errors.append(
                        f"Field '{field_name}' must be a group (a mapping), got "
                        f"{type(value).__name__}"
                    )
                continue

            field_errors = self.validate_field(
                value, field_name, attr_def, enabled_validators
            )
            all_errors.extend(field_errors)

        # Check for missing required fields
        for field_name, attr_def in attributes.items():
            if field_name not in data:
                # An absent group has no value of its own to be missing: check
                # its leaves instead, so a group of optional leaves may be
                # absent and a missing required leaf is named by its path.
                if attr_def.attributes:
                    all_errors.extend(
                        self._validate_group(
                            {}, attr_def.attributes, field_name, enabled_validators
                        )
                    )
                    continue
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
