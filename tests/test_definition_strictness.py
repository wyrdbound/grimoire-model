"""Tests for definition strictness: closed definitions, one basic-type set.

Covers findings R08-R10, R12, R13. Each failing assertion is marked
``xfail(strict=True)`` until its fix task removes the marker.

- R08 (T010): unknown keys in a definition are errors.
- R09 (T011): ``any`` is not a GRIMOIRE type.
- R10 (T011): basic types are matched exactly; ``Int`` is a model id.
- R12 (T013): ``severity`` and ``fields`` are not GRIMOIRE validation fields.
- R13 (T014): ``of`` is a list-only field.
"""

import pytest
from pydantic import ValidationError

from grimoire_model import (
    AttributeDefinition,
    ModelDefinition,
    ValidationRule,
    create_model,
)
from grimoire_model.core.exceptions import ConfigurationError, ModelValidationError


class TestR08ClosedDefinitions:
    """A misspelled key in a definition is an error, not a silent drop."""

    def test_unknown_attribute_key_raises(self):
        with pytest.raises(ValidationError):
            AttributeDefinition(type="str", optinal=True)

    def test_unknown_model_key_raises(self):
        with pytest.raises(ValidationError):
            ModelDefinition(id="r08_t", name="t", attributes={}, validatons=[])

    def test_unknown_validation_rule_key_raises(self):
        with pytest.raises(ValidationError):
            ValidationRule(expression="a", message="m", sevrity="x")

    def test_unknown_key_in_group_raises_naming_the_attribute(self):
        with pytest.raises(ConfigurationError) as excinfo:
            ModelDefinition(
                id="r08_group",
                name="t",
                attributes={"g": {"x": {"type": "int", "rnage": "1..3"}}},
            )
        assert "g" in str(excinfo.value)

    def test_metadata_accepts_free_form_data(self):
        model = ModelDefinition(
            id="r08_metadata",
            name="t",
            metadata={"anything": 1},
        )
        assert model.metadata == {"anything": 1}

    def test_required_still_has_its_explanatory_error(self):
        with pytest.raises(ValidationError, match="`required` is not an attribute"):
            AttributeDefinition(type="str", required=True)


class TestR09AnyRemoved:
    """``any`` is not a GRIMOIRE type; defining one is an error."""

    def test_any_type_raises_naming_basic_types(self):
        with pytest.raises(ValidationError) as excinfo:
            AttributeDefinition(type="any")
        message = str(excinfo.value)
        assert "int" in message
        assert "list" in message


class TestR10ExactTypeCase:
    """Basic types are matched exactly; ``Int`` is treated as a model id."""

    def test_capitalised_basic_type_is_not_type_checked(self):
        definition = ModelDefinition(
            id="r10_int",
            name="t",
            namespace="defstrict",
            attributes={"x": {"type": "Int"}},
        )
        with pytest.raises(ModelValidationError):
            create_model(definition, {"x": "not an int"})


class TestR12SeverityAndFieldsRemoved:
    """``severity`` and ``fields`` are not GRIMOIRE validation fields."""

    @pytest.mark.xfail(strict=True, reason="R12 — fixed by T013")
    def test_severity_raises(self):
        with pytest.raises(ValidationError):
            ValidationRule(expression="a", message="m", severity="warning")

    @pytest.mark.xfail(strict=True, reason="R12 — fixed by T013")
    def test_fields_raises(self):
        with pytest.raises(ValidationError):
            ValidationRule(expression="a", message="m", fields=["a"])


class TestR13OfIsListOnly:
    """``of`` is valid only when ``type`` is ``list``."""

    @pytest.mark.xfail(strict=True, reason="R13 — fixed by T014")
    def test_of_on_non_list_raises(self):
        with pytest.raises(ValidationError):
            AttributeDefinition(type="int", of="str")

    def test_of_on_list_is_accepted(self):
        assert AttributeDefinition(type="list", of="str").of == "str"


class TestR11SpecPrimitives:
    """``roll`` and ``roll_result`` are the spec's basic types (F47)."""

    def test_roll_is_a_string(self):
        definition = ModelDefinition(
            id="r11_roll",
            name="t",
            namespace="defstrict",
            attributes={"dmg": {"type": "roll"}},
        )
        model = create_model(definition, {"dmg": "1d6"})
        assert model["dmg"] == "1d6"
        with pytest.raises(ModelValidationError):
            create_model(definition, {"dmg": 6})

    def test_roll_result_is_not_type_checked(self):
        definition = ModelDefinition(
            id="r11_roll_result",
            name="t",
            namespace="defstrict",
            attributes={"r": {"type": "roll_result"}},
        )
        assert create_model(definition, {"r": {"total": 7}})["r"] == {"total": 7}

        class Arbitrary:
            pass

        value = Arbitrary()
        assert create_model(definition, {"r": value})["r"] is value

    def test_register_roll_and_roll_result_do_not_raise(self):
        from grimoire_model import register_primitive_type
        from grimoire_model.core.primitive_registry import (
            clear_primitive_registry,
        )

        try:
            register_primitive_type("roll")
            register_primitive_type("roll_result")
        finally:
            clear_primitive_registry()

    def test_registered_roll_validator_runs(self):
        from grimoire_model import register_primitive_type
        from grimoire_model.core.primitive_registry import (
            clear_primitive_registry,
        )

        def validate_dice(value):
            if isinstance(value, str) and "d" in value:
                return True, None
            return False, "bad dice"

        try:
            register_primitive_type("roll", validator=validate_dice)
            definition = ModelDefinition(
                id="r11_roll_validator",
                name="t",
                namespace="defstrict",
                attributes={"dmg": {"type": "roll"}},
            )
            assert create_model(definition, {"dmg": "1d6"})["dmg"] == "1d6"
            with pytest.raises(ModelValidationError, match="bad dice"):
                create_model(definition, {"dmg": "1x"})
        finally:
            clear_primitive_registry()

    def test_registered_custom_primitive_validator_runs(self):
        from grimoire_model import register_primitive_type
        from grimoire_model.core.primitive_registry import (
            clear_primitive_registry,
        )

        def validate_dur(value):
            if isinstance(value, str) and value.endswith("s"):
                return True, None
            return False, "duration must end with s"

        try:
            register_primitive_type("dur", validator=validate_dur)
            definition = ModelDefinition(
                id="r11_dur",
                name="t",
                namespace="defstrict",
                attributes={"t": {"type": "dur"}},
            )
            model = create_model(definition, {"t": "5s"})
            assert model["t"] == "5s"
            with pytest.raises(ModelValidationError, match="end with s"):
                create_model(definition, {"t": "5m"})

            with pytest.raises(ModelValidationError, match="end with s"):
                model["t"] = "5m"
        finally:
            clear_primitive_registry()

    def test_primitive_validator_that_raises_is_a_validation_error(self):
        from grimoire_model import register_primitive_type
        from grimoire_model.core.primitive_registry import (
            clear_primitive_registry,
        )

        def explode(value):
            raise RuntimeError("boom")

        try:
            register_primitive_type("boom", validator=explode)
            definition = ModelDefinition(
                id="r11_boom",
                name="t",
                namespace="defstrict",
                attributes={"t": {"type": "boom"}},
            )
            with pytest.raises(ModelValidationError):
                create_model(definition, {"t": "x"})
        finally:
            clear_primitive_registry()
