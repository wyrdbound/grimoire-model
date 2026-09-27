"""The `_model` instance tag (GRIMOIRE model spec, grimoire-spec 1.3.0).

"Instances of Derived Models":

1. An instance of a model that extends another model carries `_model`, set to
   its own model id. An instance of a model with no `extends` carries none.
2. `_model` is read-only.
3. `_model` is part of the instance's data: saved, copied and read back with
   the rest, so a weapon stays a weapon.
4. Where a model is declared, `_model` chooses what is built: it must name the
   declared model or a model that extends it. Absent, the declared model is
   built.

"Attribute Names": names beginning with `_` are reserved, at any depth.

Without the tag, a weapon saved in an `of: item` inventory comes back as an
item and its own attributes are rejected (Wyrdbound F62, part C2).
"""

import json
from collections.abc import Mapping
from typing import Any

import pytest

from grimoire_model import (
    ConfigurationError,
    ModelDefinition,
    ModelValidationError,
    create_model,
    create_model_without_validation,
    resolve_model_inheritance,
)

NS = "tagged"


def _define(model_id, attributes, extends=None, namespace=NS):
    return ModelDefinition(
        id=model_id,
        name=model_id,
        namespace=namespace,
        extends=extends or [],
        attributes=attributes,
    )


def _plain(value: Any) -> Any:
    """Model data as plain JSON-able values, as Wyrdbound's model_data does."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


@pytest.fixture
def defs():
    item = _define(
        "item",
        {"name": {"type": "str"}, "weight": {"type": "int", "default": 1}},
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
            "weapon_count": {
                "type": "int",
                "derived": (
                    "{{ inv | selectattr('_model', 'defined')"
                    " | selectattr('_model', 'equalto', 'weapon') | list | length }}"
                ),
            },
        },
    )
    return {m.id: m for m in (item, breakable, weapon, magic_sword, spell, holder)}


SWORD = {"name": "Sword", "damage": "1d6"}


class TestTheTagIsRecorded:
    def test_an_instance_of_a_derived_model_carries_its_id(self, defs):
        sword = create_model(defs["weapon"], dict(SWORD))
        assert sword["_model"] == "weapon"
        assert dict(sword)["_model"] == "weapon"

    def test_a_grandchild_carries_its_own_id(self, defs):
        sting = create_model(defs["magic_sword"], {"name": "Sting", "damage": "1d4"})
        assert sting["_model"] == "magic_sword"

    def test_an_instance_of_a_root_model_carries_none(self, defs):
        rope = create_model(defs["item"], {"name": "Rope"})
        assert "_model" not in rope
        holder = create_model(defs["holder"], {"inv": []})
        assert "_model" not in holder

    def test_a_flattened_definition_is_still_tagged(self, defs):
        """Wyrdbound's ModelCatalog: resolve, dump, extends: [], rebuild."""
        resolved = resolve_model_inheritance(defs["weapon"], defs)
        data = resolved.model_dump(exclude_unset=True)
        data.update(namespace="flat", extends=[])
        flat = ModelDefinition.model_validate(data)
        assert create_model(flat, dict(SWORD))["_model"] == "weapon"

    def test_data_may_already_carry_the_right_tag(self, defs):
        sword = create_model(defs["weapon"], {"_model": "weapon", **SWORD})
        assert sword["_model"] == "weapon"

    def test_a_root_model_tagged_with_itself_stores_no_tag(self, defs):
        rope = create_model(defs["item"], {"_model": "item", "name": "Rope"})
        assert "_model" not in rope

    def test_data_tagged_as_another_model_is_rejected(self, defs):
        with pytest.raises(ModelValidationError, match="names 'magic_sword'"):
            create_model(defs["weapon"], {"_model": "magic_sword", **SWORD})

    def test_a_tag_must_be_a_string(self, defs):
        with pytest.raises(ModelValidationError, match="must be a model id"):
            create_model(defs["weapon"], {"_model": 7, **SWORD})

    def test_the_tag_is_not_an_undeclared_attribute(self, defs):
        assert create_model(defs["weapon"], dict(SWORD)).validate() == []
        partial = create_model_without_validation(defs["weapon"], {"name": "S"})
        assert not [e for e in partial.validate() if "_model" in e]


class TestTheTagIsReadOnly:
    def test_it_cannot_be_written(self, defs):
        sword = create_model(defs["weapon"], dict(SWORD))
        with pytest.raises(ModelValidationError, match="read-only"):
            sword["_model"] = "item"
        assert sword["_model"] == "weapon"

    def test_it_cannot_be_deleted(self, defs):
        sword = create_model(defs["weapon"], dict(SWORD))
        with pytest.raises(ModelValidationError, match="read-only"):
            del sword["_model"]
        assert sword["_model"] == "weapon"

    def test_it_cannot_be_batch_written(self, defs):
        sword = create_model(defs["weapon"], dict(SWORD))
        with pytest.raises(ModelValidationError, match="read-only"):
            sword.batch_update({"hands": 2, "_model": "item"})
        assert sword["hands"] == 1

    def test_it_cannot_be_written_through_a_parent(self, defs):
        holder = create_model(
            defs["holder"],
            {"inv": [], "main_hand": create_model(defs["weapon"], dict(SWORD))},
        )
        with pytest.raises(ModelValidationError, match="read-only"):
            holder["main_hand._model"] = "item"
        assert holder["main_hand"]["_model"] == "weapon"


class TestTheTagChoosesWhatIsBuilt:
    def test_a_tagged_mapping_in_a_list_is_built_as_its_model(self, defs):
        holder = create_model(
            defs["holder"],
            {"inv": [{"_model": "weapon", **SWORD}, {"name": "Rope"}]},
        )
        sword, rope = holder["inv"]
        assert sword.is_a("weapon") and sword["damage"] == "1d6"
        assert sword["heft"] == 1
        assert rope.model_definition.id == "item"

    def test_a_tagged_grandchild_is_built(self, defs):
        holder = create_model(
            defs["holder"],
            {"inv": [{"_model": "magic_sword", "name": "Sting", "damage": "1d4"}]},
        )
        assert holder["inv"][0]["bonus"] == 1

    def test_a_tagged_mapping_on_an_attribute_is_built_as_its_model(self, defs):
        holder = create_model(
            defs["holder"], {"inv": [], "main_hand": {"_model": "weapon", **SWORD}}
        )
        assert holder["main_hand"].is_a("weapon")
        holder["main_hand"] = {
            "_model": "magic_sword",
            "name": "Sting",
            "damage": "1d4",
        }
        assert holder["main_hand"]["_model"] == "magic_sword"

    def test_a_tag_naming_an_unrelated_model_is_rejected(self, defs):
        with pytest.raises(ModelValidationError, match="'spell', which is not 'item'"):
            create_model(defs["holder"], {"inv": [{"_model": "spell", "name": "x"}]})

    def test_a_tag_naming_a_parent_where_a_child_is_declared_is_rejected(self, defs):
        with pytest.raises(ModelValidationError, match="'item', which is not 'weapon'"):
            create_model(
                defs["holder"],
                {"inv": [], "weapons": [{"_model": "item", "name": "Rope"}]},
            )

    def test_a_tag_naming_no_model_is_rejected(self, defs):
        with pytest.raises(ModelValidationError, match="names 'dragon'"):
            create_model(defs["holder"], {"inv": [{"_model": "dragon", "name": "x"}]})

    def test_an_untagged_mapping_is_still_the_declared_model(self, defs):
        with pytest.raises(ModelValidationError, match="damage"):
            create_model(defs["holder"], {"inv": [dict(SWORD)]})


class TestTheTagSurvivesPlainData:
    def test_a_weapon_in_an_item_list_survives_a_json_round_trip(self, defs):
        holder = create_model(
            defs["holder"],
            {"inv": [create_model(defs["weapon"], dict(SWORD)), {"name": "Rope"}]},
        )
        saved = json.loads(json.dumps(_plain(holder)))
        assert saved["inv"][0]["_model"] == "weapon"
        assert "_model" not in saved["inv"][1]

        restored = create_model(defs["holder"], saved)
        assert restored["inv"][0].is_a("weapon")
        assert restored["inv"][0]["damage"] == "1d6"
        assert _plain(restored) == saved

    def test_a_copy_keeps_the_tag(self, defs):
        sword = create_model(defs["weapon"], dict(SWORD))
        assert sword.copy()["_model"] == "weapon"


class TestExpressionsCanReadTheTag:
    def test_a_derived_field_filters_by_model(self, defs):
        holder = create_model(
            defs["holder"],
            {"inv": [{"_model": "weapon", **SWORD}, {"name": "Rope"}]},
        )
        assert holder["weapon_count"] == 1
        holder["inv"] = [{"name": "Rope"}]
        assert holder["weapon_count"] == 0


class TestReservedAttributeNames:
    @pytest.mark.parametrize(
        "attributes",
        [
            {"_model": {"type": "str"}},
            {"_secret": {"type": "int"}},
            {"stats": {"_hidden": {"type": "int"}, "score": {"type": "int"}}},
            {"_meta": {"note": {"type": "str"}}},
        ],
    )
    def test_a_reserved_name_is_a_definition_error(self, attributes):
        with pytest.raises(ConfigurationError, match="reserved"):
            _define("bad", attributes, namespace="reserved")

    def test_an_ordinary_name_like_model_is_allowed(self):
        definition = _define("ok", {"model": {"type": "str"}}, namespace="ordinary")
        assert create_model(definition, {"model": "T-800"})["model"] == "T-800"
