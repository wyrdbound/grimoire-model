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

from grimoire_model import AttributeDefinition, ModelDefinition, create_model
from grimoire_model.core.exceptions import (
    ConfigurationError,
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
