"""Writes into a nested **model-typed** attribute build the nested model.

A ``type`` that names a model (Knave's
``abilities.constitution: {type: character_ability}``) is instantiated as a
nested ``GrimoireModel`` when it is supplied at construction. A **write** to
such an attribute — a leaf (``abilities.constitution.bonus``) or the whole slot
(``abilities.constitution``) — did not, storing a plain dict instead. The
nested model's derived fields never computed, and a later dotted write into an
already-built slot raised ``TypeError`` (wyrdbound F57).

These tests are library-only: two models shaped like Knave's
``character → abilities → character_ability``, no engine.
"""

from __future__ import annotations

import pytest

from grimoire_model import (
    AttributeDefinition,
    ModelDefinition,
    clear_registry,
    create_model,
)
from grimoire_model.core.exceptions import ModelValidationError
from grimoire_model.core.model import GrimoireModel


def _ability_attr() -> AttributeDefinition:
    """An attribute whose type is the ``character_ability`` model."""
    return AttributeDefinition(type="character_ability")


@pytest.fixture
def models() -> tuple[ModelDefinition, ModelDefinition]:
    """Register ``character_ability``, ``abilities`` and ``character``."""
    clear_registry()
    ModelDefinition(
        id="character_ability",
        name="Character Ability",
        namespace="knave",
        attributes={
            "bonus": AttributeDefinition(type="int", range="1..10"),
            "defense": AttributeDefinition(type="int", derived="{{ bonus + 10 }}"),
        },
    )
    abilities = ModelDefinition(
        id="abilities",
        name="Abilities",
        namespace="knave",
        attributes={
            "constitution": _ability_attr(),
            "strength": AttributeDefinition(type="character_ability", optional=True),
        },
    )
    character = ModelDefinition(
        id="character",
        name="Character",
        namespace="knave",
        attributes={
            "name": AttributeDefinition(type="str"),
            "abilities": AttributeDefinition(type="abilities"),
            "inventory_capacity": AttributeDefinition(
                type="int", derived="{{ abilities.constitution.defense }}"
            ),
        },
    )
    return abilities, character


class TestDottedWriteIntoUnsetModelTypedAttribute:
    def test_it_builds_the_nested_model(self, models: tuple) -> None:
        _, character_def = models
        character = create_model(
            character_def, {"name": "Wren"}, skip_initial_validation=True
        )

        character["abilities.constitution.bonus"] = 3

        assert isinstance(character["abilities"], GrimoireModel)
        assert isinstance(character["abilities"]["constitution"], GrimoireModel)

    def test_the_nested_derived_field_computes(self, models: tuple) -> None:
        _, character_def = models
        character = create_model(
            character_def, {"name": "Wren"}, skip_initial_validation=True
        )

        character["abilities.constitution.bonus"] = 3

        assert character["abilities"]["constitution"]["defense"] == 13

    def test_the_parent_derived_field_recomputes(self, models: tuple) -> None:
        _, character_def = models
        character = create_model(
            character_def, {"name": "Wren"}, skip_initial_validation=True
        )

        character["abilities.constitution.bonus"] = 4

        assert character["inventory_capacity"] == 14


class TestDottedWriteIntoBuiltModelTypedAttribute:
    def test_it_does_not_raise(self, models: tuple) -> None:
        """Today this raises ``TypeError: value is not a dictionary``."""
        abilities_def, character_def = models
        character = create_model(
            character_def,
            {"name": "Wren", "abilities": {"constitution": {"bonus": 2}}},
            partial=True,
        )

        character["abilities.constitution.bonus"] = 5

        assert character["abilities"]["constitution"]["bonus"] == 5

    def test_it_recomputes_both_levels(self, models: tuple) -> None:
        abilities_def, character_def = models
        character = create_model(
            character_def,
            {"name": "Wren", "abilities": {"constitution": {"bonus": 2}}},
            partial=True,
        )

        character["abilities.constitution.bonus"] = 5

        assert character["abilities"]["constitution"]["defense"] == 15
        assert character["inventory_capacity"] == 15


class TestWholeSlotWrite:
    def test_a_dict_written_to_a_model_typed_slot_builds_it(
        self, models: tuple
    ) -> None:
        _, character_def = models
        character = create_model(
            character_def, {"name": "Wren"}, skip_initial_validation=True
        )

        character["abilities.constitution"] = {"bonus": 6}

        assert isinstance(character["abilities"]["constitution"], GrimoireModel)
        assert character["abilities"]["constitution"]["defense"] == 16
        assert character["inventory_capacity"] == 16


class TestNestedValidation:
    def test_an_out_of_range_nested_write_is_rejected(self, models: tuple) -> None:
        _, character_def = models
        character = create_model(
            character_def, {"name": "Wren"}, skip_initial_validation=True
        )

        with pytest.raises(ModelValidationError):
            character["abilities.constitution.bonus"] = 99

    def test_a_templated_range_in_the_nested_model_resolves(
        self, models: tuple
    ) -> None:
        """A nested attribute whose range is templated (F38) validates on write
        against the nested model's own data."""
        clear_registry()
        ModelDefinition(
            id="pool",
            name="Pool",
            namespace="tmpl",
            attributes={
                "max": AttributeDefinition(type="int"),
                "current": AttributeDefinition(type="int", range="0..{{ max }}"),
            },
        )
        holder = ModelDefinition(
            id="holder",
            name="Holder",
            namespace="tmpl",
            attributes={"pool": AttributeDefinition(type="pool")},
        )
        model = create_model(
            holder, {"pool": {"max": 8, "current": 5}}, skip_initial_validation=True
        )

        model["pool.current"] = 8
        assert model["pool"]["current"] == 8

        with pytest.raises(ModelValidationError):
            model["pool.current"] = 9


class TestNullOnOptionalModelTypedAttribute:
    def test_null_unsets_it(self, models: tuple) -> None:
        clear_registry()
        ModelDefinition(
            id="stat",
            name="Stat",
            namespace="opt",
            attributes={"value": AttributeDefinition(type="int")},
        )
        holder = ModelDefinition(
            id="holder_opt",
            name="Holder",
            namespace="opt",
            attributes={
                "name": AttributeDefinition(type="str"),
                "stat": AttributeDefinition(type="stat", optional=True),
            },
        )
        model = create_model(
            holder, {"name": "x", "stat": {"value": 3}}, skip_initial_validation=True
        )

        model["stat"] = None

        assert "stat" not in model


class TestAnonymousGroupsUnchanged:
    def test_a_leaf_write_into_an_anonymous_group_still_computes(self) -> None:
        """Anonymous groups are plain dicts at runtime (Principle III); this
        must not change."""
        clear_registry()
        model_def = ModelDefinition(
            id="grouped",
            name="Grouped",
            namespace="anon",
            attributes={
                "power": AttributeDefinition(  # type: ignore[arg-type]
                    type="dict",
                    attributes={
                        "score": AttributeDefinition(type="int", range="3..20"),
                        "modifier": AttributeDefinition(
                            type="int", derived="{{ (power.score - 10) // 2 }}"
                        ),
                    },
                )
            },
        )
        model = create_model(model_def, {}, skip_initial_validation=True)

        model["power.score"] = 16

        assert isinstance(model["power"], dict)
        assert not isinstance(model["power"], GrimoireModel)
        assert model["power"] == {"score": 16, "modifier": 3}
