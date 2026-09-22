"""Tests for template expressions inside ``range`` constraints.

A relative range such as ``"0..{{ max_hp }}"`` is documented by the GRIMOIRE
model specification. ``RangeValidator`` parses the range with ``float()``, so
before this was fixed *every* templated range failed as an invalid range
specification, whatever syntax it used.
"""

import pytest

from grimoire_model import ModelDefinition, create_model
from grimoire_model.core.exceptions import ModelValidationError


def _definition(model_id, range_spec, extra=None):
    attributes = {
        "max_hp": {"type": "int", "default": 10},
        "current_hp": {"type": "int", "range": range_spec},
    }
    attributes.update(extra or {})
    return ModelDefinition(
        id=model_id, name="Ranged", namespace="tmplrange", attributes=attributes
    )


class TestTemplatedRanges:
    def test_literal_range_still_works(self):
        model = create_model(
            _definition("lit", "0..10"), {"max_hp": 10, "current_hp": 5}
        )
        assert model["current_hp"] == 5

    def test_templated_upper_bound_resolves(self):
        model = create_model(
            _definition("tmpl", "0..{{ max_hp }}"), {"max_hp": 10, "current_hp": 5}
        )
        assert model["current_hp"] == 5

    def test_templated_upper_bound_is_enforced(self):
        with pytest.raises(ModelValidationError):
            create_model(
                _definition("tmpl_hi", "0..{{ max_hp }}"),
                {"max_hp": 10, "current_hp": 11},
            )

    def test_templated_lower_bound_is_enforced(self):
        definition = ModelDefinition(
            id="tmpl_lo",
            name="Ranged",
            namespace="tmplrange",
            attributes={
                "floor": {"type": "int", "default": 5},
                "value": {"type": "int", "range": "{{ floor }}..20"},
            },
        )
        assert create_model(definition, {"floor": 5, "value": 5})["value"] == 5
        with pytest.raises(ModelValidationError):
            create_model(definition, {"floor": 5, "value": 4})

    def test_range_may_reference_a_derived_field(self):
        """Ranges resolve after derived fields are computed."""
        definition = ModelDefinition(
            id="tmpl_derived",
            name="Ranged",
            namespace="tmplrange",
            attributes={
                "base": {"type": "int", "default": 4},
                "max_hp": {"type": "int", "derived": "{{ base * 3 }}"},
                "current_hp": {"type": "int", "range": "0..{{ max_hp }}"},
            },
        )
        model = create_model(definition, {"base": 4, "current_hp": 12})
        assert model["max_hp"] == 12
        with pytest.raises(ModelValidationError):
            create_model(definition, {"base": 4, "current_hp": 13})

    def test_unresolvable_range_raises_rather_than_being_skipped(self):
        """A range that does not resolve to numbers must fail loudly."""
        with pytest.raises(ModelValidationError):
            create_model(
                _definition("bad", "0..{{ nonexistent }}"),
                {"max_hp": 10, "current_hp": 5},
            )

    def test_non_numeric_resolution_raises(self):
        definition = ModelDefinition(
            id="bad_kind",
            name="Ranged",
            namespace="tmplrange",
            attributes={
                "label": {"type": "str", "default": "abc"},
                "value": {"type": "int", "range": "0..{{ label }}"},
            },
        )
        with pytest.raises(ModelValidationError):
            create_model(definition, {"label": "abc", "value": 5})
