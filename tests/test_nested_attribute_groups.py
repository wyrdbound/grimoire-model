"""Tests for anonymous nested attribute groups.

A model may declare a group inline, with no ``type`` of its own::

    power:
      score:    { type: int, range: "3..20" }
      modifier: { type: int, derived: "{{ (power.score - 10) // 2 }}" }

Before this was fixed the group was stored as an opaque ``type: dict`` and
every leaf definition was discarded, so leaf ``derived``, ``default``,
``range`` and ``enum`` were silently ignored. The model still instantiated --
it failed open, producing a character sheet that was quietly wrong.
"""

import pytest

from grimoire_model import ModelDefinition, create_model
from grimoire_model.core.exceptions import ModelValidationError


def _character(model_id, namespace="nested"):
    return ModelDefinition(
        id=model_id,
        name="Character",
        namespace=namespace,
        attributes={
            "name": {"type": "str", "default": "Unnamed"},
            "power": {
                "score": {"type": "int", "range": "3..20"},
                "modifier": {
                    "type": "int",
                    "derived": "{{ (power.score - 10) // 2 }}",
                },
            },
            "hit_points": {
                "max": {"type": "int", "range": "1.."},
                "current": {"type": "int", "range": "0..{{ hit_points.max }}"},
            },
        },
    )


class TestLeafDefinitionsRetained:
    def test_group_keeps_its_leaf_definitions(self):
        definition = _character("retain")
        power = definition.attributes["power"]

        assert power.type == "dict"
        assert power.attributes is not None
        assert set(power.attributes) == {"score", "modifier"}
        assert power.attributes["score"].range == "3..20"
        assert power.attributes["modifier"].derived == "{{ (power.score - 10) // 2 }}"


class TestLeafDerived:
    def test_derived_leaf_is_computed(self):
        model = create_model(
            _character("derived_leaf"),
            {"power": {"score": 16}, "hit_points": {"max": 12, "current": 12}},
        )
        assert model["power"]["modifier"] == 3

    def test_derived_leaf_is_negative_when_it_should_be(self):
        model = create_model(
            _character("derived_neg"),
            {"power": {"score": 9}, "hit_points": {"max": 12, "current": 12}},
        )
        assert model["power"]["modifier"] == -1


class TestLeafConstraints:
    def test_leaf_range_is_enforced(self):
        with pytest.raises(ModelValidationError):
            create_model(
                _character("leaf_range"),
                {"power": {"score": 99}, "hit_points": {"max": 12, "current": 12}},
            )

    def test_leaf_relative_range_is_enforced(self):
        with pytest.raises(ModelValidationError):
            create_model(
                _character("leaf_rel_range"),
                {"power": {"score": 16}, "hit_points": {"max": 12, "current": 999}},
            )

    def test_leaf_enum_is_enforced(self):
        definition = ModelDefinition(
            id="leaf_enum",
            name="Character",
            namespace="nested",
            attributes={
                "traits": {
                    "bearing": {"type": "str", "enum": ["tall", "short"]},
                },
            },
        )
        assert create_model(definition, {"traits": {"bearing": "tall"}})
        with pytest.raises(ModelValidationError):
            create_model(definition, {"traits": {"bearing": "enormous"}})

    def test_leaf_default_is_applied(self):
        definition = ModelDefinition(
            id="leaf_default",
            name="Character",
            namespace="nested",
            attributes={
                "equipped": {
                    "covering": {"type": "str", "default": "cloak"},
                },
            },
        )
        model = create_model(definition, {"equipped": {}})
        assert model["equipped"]["covering"] == "cloak"


class TestNamedNestedModelsUnaffected:
    def test_named_nested_model_still_works(self):
        ModelDefinition(
            id="stat",
            name="Stat",
            namespace="nested_named",
            attributes={
                "value": {"type": "int", "required": True},
                "bonus": {"type": "int", "derived": "{{ (value - 10) // 2 }}"},
            },
        )
        character = ModelDefinition(
            id="named_char",
            name="Character",
            namespace="nested_named",
            attributes={
                "constitution": {"type": "stat", "required": False},
                "hit_points": {
                    "type": "int",
                    "derived": "{{ 10 + constitution.bonus }}",
                },
            },
        )
        model = create_model(character, {"constitution": {"value": 14}})
        assert model["constitution"]["bonus"] == 2
        assert model["hit_points"] == 12
