"""Presence, defaults and null.

The rules, in order of the fixes that introduced them:

- Attributes are required unless ``optional: true``.
- A default belongs only to a required attribute. It is applied when an
  instance is created and stored with it, so it never re-applies to an
  attribute that was deliberately emptied. An optional attribute has no
  default, and ``default: null`` is not a default at all.
- Writing ``null`` to an optional attribute unsets it; nothing is stored.
  ``null`` on a required attribute is a validation error.
- In expressions, a declared attribute with no value reads as ``null``. An
  undeclared name still raises, so a misspelling is never mistaken for an
  empty attribute.
"""

import itertools

import pytest

from grimoire_model import (
    AttributeDefinition,
    ModelDefinition,
    create_model,
    unset_as_null,
)
from grimoire_model.core.exceptions import (
    ConfigurationError,
    ModelValidationError,
    TemplateResolutionError,
)

_ids = itertools.count()


def _model(attributes, validations=None):
    n = next(_ids)
    return ModelDefinition(
        id=f"presence_{n}",
        name="Presence",
        namespace="presence",
        attributes=attributes,
        validations=validations or [],
    )


class TestDefaultRule:
    def test_required_attribute_may_have_a_default(self):
        attr = AttributeDefinition(type="int", default=1)
        assert attr.default == 1

    def test_optional_attribute_may_not_have_a_default(self):
        with pytest.raises(ValueError, match="optional attribute cannot have"):
            AttributeDefinition(type="str", optional=True, default="cloak")

    def test_explicit_null_default_is_rejected(self):
        with pytest.raises(ValueError, match="`default: null`"):
            AttributeDefinition(**{"type": "str", "default": None})

    def test_explicit_null_default_is_rejected_on_optional_too(self):
        with pytest.raises(ValueError, match="`default: null`"):
            AttributeDefinition(**{"type": "str", "optional": True, "default": None})

    def test_rule_applies_to_leaves_of_a_nested_group(self):
        # ModelDefinition reports every invalid attribute as a ConfigurationError.
        with pytest.raises(ConfigurationError, match="optional attribute cannot have"):
            _model({
                "equipped": {
                    "covering": {
                        "type": "str",
                        "optional": True,
                        "default": "cloak",
                    }
                }
            })

    def test_default_is_stored_and_not_reapplied_after_the_value_is_set(self):
        definition = _model({"level": {"type": "int", "default": 1}})
        created = dict(create_model(definition, {}))
        assert created == {"level": 1}
        rebuilt = dict(create_model(definition, {"level": 5}))
        assert rebuilt == {"level": 5}


class TestRoundTrip:
    def test_to_dict_round_trips_optional_defaults_and_groups(self):
        """`to_dict` must not emit fields that were never set.

        Emitting every field writes `default: None` for attributes with no
        default, which reads back as an explicit `default: null`.
        """
        definition = _model({
            "name": {"type": "str"},
            "level": {"type": "int", "default": 1},
            "nickname": {"type": "str", "optional": True},
            "equipped": {"covering": {"type": "str", "optional": True}},
        })
        data = definition.to_dict()
        assert "default" not in data["attributes"]["name"]
        rebuilt = ModelDefinition.from_dict({**data, "id": data["id"] + "_rt"})
        assert rebuilt.attributes["level"].default == 1
        assert rebuilt.attributes["nickname"].optional is True
        assert rebuilt.attributes["equipped"].attributes["covering"].optional is True


class TestUnsetReadsAsNull:
    """A declared optional attribute with no value reads as null in expressions."""

    def test_is_none_guard_works_on_an_unset_optional(self):
        definition = _model({
            "slot": {"type": "str", "optional": True},
            "label": {
                "type": "str",
                "derived": "{{ 'empty' if slot is none else slot }}",
            },
        })
        assert create_model(definition, {})["label"] == "empty"
        assert create_model(definition, {"slot": "sword"})["label"] == "sword"

    def test_truthiness_guard_works_on_an_unset_optional(self):
        definition = _model({
            "slot": {"type": "str", "optional": True},
            "label": {"type": "str", "derived": "{{ slot or 'empty' }}"},
        })
        assert create_model(definition, {})["label"] == "empty"

    def test_unset_leaf_in_a_present_group_reads_as_null(self):
        definition = _model({
            "equipped": {"main_hand": {"type": "str", "optional": True}},
            "label": {"type": "str", "derived": "{{ equipped.main_hand or 'none' }}"},
        })
        assert create_model(definition, {"equipped": {}})["label"] == "none"

    def test_unset_leaf_in_an_absent_group_reads_as_null(self):
        definition = _model({
            "equipped": {"main_hand": {"type": "str", "optional": True}},
            "label": {"type": "str", "derived": "{{ equipped.main_hand or 'none' }}"},
        })
        assert create_model(definition, {})["label"] == "none"

    def test_validation_rule_can_reference_an_unset_optional(self):
        definition = _model(
            {"nickname": {"type": "str", "optional": True}},
            validations=[
                {
                    "expression": "{{ nickname is none or nickname | length <= 12 }}",
                    "message": "Nickname too long",
                }
            ],
        )
        assert dict(create_model(definition, {})) == {}
        with pytest.raises(ModelValidationError, match="Nickname too long"):
            create_model(definition, {"nickname": "Bartholomew the Bold"})

    def test_a_misspelled_name_still_raises(self):
        """Only *declared* attributes read as null; a typo is never empty."""
        definition = _model({
            "slot": {"type": "str", "optional": True},
            "label": {"type": "str", "derived": "{{ slto or 'empty' }}"},
        })
        with pytest.raises(TemplateResolutionError):
            create_model(definition, {})

    def test_a_required_attribute_with_no_value_does_not_read_as_null(self):
        """A missing required attribute is an error, not an empty value."""
        definition = _model({
            "score": {"type": "int"},
            "bonus": {"type": "int", "derived": "{{ score + 1 }}"},
        })
        with pytest.raises((TemplateResolutionError, ModelValidationError)):
            create_model(definition, {})

    def test_reading_as_null_never_stores_null(self):
        definition = _model({
            "slot": {"type": "str", "optional": True},
            "label": {"type": "str", "derived": "{{ slot or 'empty' }}"},
        })
        assert dict(create_model(definition, {})) == {"label": "empty"}


class TestUnsetAsNullHelper:
    def test_fills_only_optional_leaves_and_does_not_mutate(self):
        attributes = _model({
            "name": {"type": "str"},
            "nickname": {"type": "str", "optional": True},
            "equipped": {
                "main_hand": {"type": "str", "optional": True},
                "covering": {"type": "str", "optional": True},
            },
        }).attributes
        data = {"name": "Brann", "equipped": {"covering": "cloak"}}
        view = unset_as_null(data, attributes)
        assert view == {
            "name": "Brann",
            "nickname": None,
            "equipped": {"main_hand": None, "covering": "cloak"},
        }
        assert data == {"name": "Brann", "equipped": {"covering": "cloak"}}


class TestAbsentGroups:
    def test_group_of_optional_leaves_may_be_absent(self):
        definition = _model({
            "equipped": {"main_hand": {"type": "str", "optional": True}}
        })
        assert dict(create_model(definition, {})) == {}

    def test_absent_group_reports_its_missing_required_leaves_by_path(self):
        definition = _model({
            "hit_points": {
                "max": {"type": "int"},
                "note": {"type": "str", "optional": True},
            }
        })
        with pytest.raises(ModelValidationError, match="hit_points.max"):
            create_model(definition, {})
