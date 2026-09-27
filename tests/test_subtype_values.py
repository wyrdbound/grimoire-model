"""A value typed as a model accepts that model or any model that extends it.

The GRIMOIRE model specification declares ``inventory: {type: list, of: item}``
and, in the same document, ``weapon`` with ``extends: [item]``: a weapon is an
item. 0.8.0 compared model ids exactly, so a ``weapon`` model was rejected
where an ``item`` was declared (Wyrdbound F62, part C1).

The subtype check is by lineage: a resolved definition records every model it
inherits from (``ModelDefinition.ancestors``), so the check survives a
definition being flattened to ``extends: []`` and rebuilt, which is how
Wyrdbound's ``ModelCatalog`` resolves a system.

A plain mapping carries no type of its own and is still built as the declared
model; accepting subtype *data* needs a type marker the specification does not
yet define (F62, part C2), and is deliberately not guessed here.
"""

import pytest
from pydantic import ValidationError

from grimoire_model import (
    GrimoireModel,
    ModelDefinition,
    ModelValidationError,
    create_model,
    resolve_model_inheritance,
)

NS = "subtypes"


def _define(model_id, attributes, extends=None, namespace=NS):
    return ModelDefinition(
        id=model_id,
        name=model_id,
        namespace=namespace,
        extends=extends or [],
        attributes=attributes,
    )


@pytest.fixture
def defs():
    """Knave's shape: weapon extends [item, breakable]; a grandchild; a stranger."""
    item = _define(
        "item",
        {
            "name": {"type": "str"},
            "weight": {"type": "int", "default": 1},
        },
    )
    breakable = _define("breakable", {"quality": {"type": "int", "default": 3}})
    weapon = _define(
        "weapon",
        {
            "damage": {"type": "str"},
            "hands": {"type": "int", "default": 1},
            "heft": {"type": "int", "derived": "{{ weight * hands }}"},
        },
        extends=["item", "breakable"],
    )
    magic_sword = _define(
        "magic_sword", {"bonus": {"type": "int", "default": 1}}, extends=["weapon"]
    )
    spell = _define("spell", {"name": {"type": "str"}})
    holder = _define(
        "holder",
        {
            "inv": {"type": "list", "of": "item"},
            "weapons": {"type": "list", "of": "weapon", "optional": True},
            "main_hand": {"type": "item", "optional": True},
        },
    )
    return {
        "item": item,
        "breakable": breakable,
        "weapon": weapon,
        "magic_sword": magic_sword,
        "spell": spell,
        "holder": holder,
    }


def _sword(defs):
    return create_model(defs["weapon"], {"name": "Sword", "damage": "1d6"})


class TestLineage:
    def test_resolved_definition_records_every_ancestor(self, defs):
        resolved = resolve_model_inheritance(
            defs["magic_sword"], {m.id: m for m in defs.values()}
        )
        assert resolved.ancestors == ["weapon", "item", "breakable"]
        assert resolved.extends == []

    def test_diamond_records_a_shared_base_once(self):
        base = _define("base", {"a": {"type": "int", "default": 1}})
        left = _define("left", {}, extends=["base"])
        right = _define("right", {}, extends=["base"])
        both = _define("both", {}, extends=["left", "right"])
        resolved = resolve_model_inheritance(
            both, {m.id: m for m in (base, left, right, both)}
        )
        assert resolved.ancestors == ["left", "base", "right"]

    def test_a_model_without_parents_has_no_ancestors(self, defs):
        assert defs["item"].ancestors == []

    def test_is_a_follows_the_lineage(self, defs):
        sword = create_model(
            defs["magic_sword"], {"name": "Glamdring", "damage": "1d8"}
        )
        for model_id in ("magic_sword", "weapon", "item", "breakable"):
            assert sword.is_a(model_id), model_id
        assert not sword.is_a("spell")

    def test_ancestors_cannot_repeat_or_name_the_model_itself(self):
        with pytest.raises(ValidationError):
            ModelDefinition(id="dup", name="d", namespace="bad", ancestors=["x", "x"])
        with pytest.raises(ValidationError):
            ModelDefinition(id="me", name="m", namespace="bad2", ancestors=["me"])


class TestSubtypeValuesAreAccepted:
    def test_list_of_item_holds_a_weapon_model(self, defs):
        holder = create_model(
            defs["holder"],
            {"inv": [_sword(defs), {"name": "Rope"}]},
        )
        sword, rope = holder["inv"]
        assert isinstance(sword, GrimoireModel) and sword.is_a("weapon")
        # The weapon keeps its own attributes and derived fields: nothing is
        # rebuilt as, or cut down to, an item.
        assert sword["damage"] == "1d6"
        assert sword["heft"] == 1
        assert sword["quality"] == 3
        assert rope.model_definition.id == "item"

    def test_list_of_item_holds_a_grandchild(self, defs):
        glamdring = create_model(
            defs["magic_sword"], {"name": "Glamdring", "damage": "1d8"}
        )
        holder = create_model(defs["holder"], {"inv": [glamdring]})
        assert holder["inv"][0]["bonus"] == 1

    def test_whole_list_write_accepts_subtypes(self, defs):
        holder = create_model(defs["holder"], {"inv": []})
        holder["inv"] = [_sword(defs)]
        assert holder["inv"][0].is_a("weapon")

    def test_model_typed_attribute_accepts_a_subtype(self, defs):
        holder = create_model(defs["holder"], {"inv": [], "main_hand": _sword(defs)})
        assert holder["main_hand"]["damage"] == "1d6"

        holder["main_hand"] = create_model(
            defs["magic_sword"], {"name": "Sting", "damage": "1d4"}
        )
        assert holder["main_hand"].is_a("magic_sword")

    def test_dotted_write_into_a_subtype_value_reaches_it(self, defs):
        holder = create_model(defs["holder"], {"inv": [], "main_hand": _sword(defs)})
        holder["main_hand.hands"] = 2
        assert holder["main_hand"]["heft"] == 2

    def test_a_copy_keeps_each_element_type(self, defs):
        holder = create_model(defs["holder"], {"inv": [_sword(defs)]})
        assert holder.copy()["inv"][0].is_a("weapon")


class TestNonSubtypesAreStillRejected:
    def test_an_unrelated_model_is_rejected(self, defs):
        spell = create_model(defs["spell"], {"name": "Sleep"})
        with pytest.raises(ModelValidationError, match="inv\\[0\\]"):
            create_model(defs["holder"], {"inv": [spell]})

    def test_a_parent_is_not_accepted_where_a_child_is_declared(self, defs):
        rope = create_model(defs["item"], {"name": "Rope"})
        with pytest.raises(ModelValidationError, match="weapons\\[0\\]"):
            create_model(defs["holder"], {"inv": [], "weapons": [rope]})

    def test_an_unrelated_model_is_rejected_on_an_attribute(self, defs):
        holder = create_model(defs["holder"], {"inv": []})
        with pytest.raises(ModelValidationError, match="main_hand"):
            holder["main_hand"] = create_model(defs["spell"], {"name": "Sleep"})

    def test_a_plain_mapping_is_built_as_the_declared_model(self, defs):
        """F62 C2, unchanged: data carries no type, so it is an ``item``."""
        with pytest.raises(ModelValidationError, match="damage"):
            create_model(defs["holder"], {"inv": [{"name": "Sword", "damage": "1d6"}]})


class TestFlattenedDefinitionsKeepTheirLineage:
    def test_wyrdbound_style_flatten_and_rebuild(self, defs):
        """``ModelCatalog._flatten``: resolve, dump, drop ``extends``, rebuild."""
        declared = {m.id: m for m in defs.values()}

        def flatten(model_id):
            resolved = resolve_model_inheritance(declared[model_id], declared)
            data = resolved.model_dump(exclude_unset=True)
            data.update(namespace="flat", extends=[])
            return ModelDefinition.model_validate(data)

        flat = {model_id: flatten(model_id) for model_id in declared}
        assert flat["weapon"].extends == []
        assert flat["weapon"].ancestors == ["item", "breakable"]

        sword = create_model(flat["weapon"], {"name": "Sword", "damage": "1d6"})
        holder = create_model(flat["holder"], {"inv": [sword]})
        assert holder["inv"][0]["damage"] == "1d6"

        spell = create_model(flat["spell"], {"name": "Sleep"})
        with pytest.raises(ModelValidationError):
            create_model(flat["holder"], {"inv": [spell]})
