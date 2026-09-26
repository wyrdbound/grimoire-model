"""Tests for private storage, independent copies, keywords and hashing.

Covers findings R14, R15, R22, R23. Each assertion that fails on 0.7.1 is
marked ``xfail(strict=True)`` per group until its fix task removes the marker.

- R14 (T017): storage is private; reads return copies; defaults are deep-copied.
- R15 (T016): ``copy()`` is independent (own derived resolver, new id).
- R22 (T018): no silent keywords on the model or the factories.
- R23 (T018): ``GrimoireModel`` is unhashable.
"""

import pytest

from grimoire_model import (
    GrimoireModel,
    ModelDefinition,
    create_model,
)


def _group_model(model_id, namespace="write_tx"):
    return ModelDefinition(
        id=model_id,
        name="Group",
        namespace=namespace,
        attributes={
            "g": {
                "x": {"type": "int", "range": "1..5", "default": 1},
            },
        },
    )


class TestR14PrivateStorage:
    """No code path mutates storage reachable from a previous read."""

    def test_mutating_a_read_dict_does_not_change_the_model(self):
        model = create_model(_group_model("r14_mutate"), {"g": {"x": 1}})
        model["g"]["x"] = 99
        assert model["g.x"] == 1

    def test_a_reference_taken_earlier_is_not_changed_by_a_write(self):
        model = create_model(_group_model("r14_ref"), {"g": {"x": 1}})
        old = model["g"]
        model["g.x"] = 2
        assert old == {"x": 1}

    def test_default_list_is_not_shared_between_instances(self):
        definition = ModelDefinition(
            id="r14_default_list",
            name="Tags",
            namespace="write_tx",
            attributes={"tags": {"type": "list", "default": []}},
        )
        first = create_model(definition, {})
        first["tags"].append("x")

        second = create_model(definition, {})
        assert second["tags"] == []
        assert definition.attributes["tags"].default == []

    def test_appending_to_a_read_list_does_not_change_the_model(self):
        definition = ModelDefinition(
            id="r14_append",
            name="Tags",
            namespace="write_tx",
            attributes={"tags": {"type": "list", "default": [1]}},
        )
        model = create_model(definition, {})
        model["tags"].append(2)
        assert model["tags"] == [1]

    def test_mutating_a_read_nested_model_does_not_change_it(self):
        ModelDefinition(
            id="r14_weapon",
            name="Weapon",
            namespace="write_tx",
            attributes={"name": {"type": "str", "default": "sword"}},
        )
        definition = ModelDefinition(
            id="r14_holder",
            name="Holder",
            namespace="write_tx",
            attributes={"w": {"type": "r14_weapon"}},
        )
        model = create_model(definition, {"w": {"name": "axe"}})
        model["w"]["name"] = "hammer"
        assert model["w"]["name"] == "axe"


class TestR15CopyIsIndependent:
    """A copy has its own derived resolver and instance id."""

    def test_write_to_original_does_not_reach_the_copy(self):
        definition = ModelDefinition(
            id="r15_copy",
            name="Copy",
            namespace="write_tx",
            attributes={
                "a": {"type": "int", "default": 1},
                "b": {"type": "int", "derived": "{{ a * 2 }}"},
            },
        )
        model = create_model(definition, {"a": 1})
        copy = model.copy(a=5)

        model["a"] = 10

        assert model["b"] == 20
        assert copy["b"] == 10

    def test_copy_gets_a_new_instance_id(self):
        definition = ModelDefinition(
            id="r15_id",
            name="Copy",
            namespace="write_tx",
            attributes={"a": {"type": "int", "default": 1}},
        )
        model = create_model(definition, {})
        assert model.copy().instance_id != model.instance_id


class TestR22NoSilentKeywords:
    """Unknown keywords are errors, not silently ignored."""

    @pytest.mark.xfail(strict=True, reason="R22 — fixed by T018")
    def test_typo_keyword_on_the_model_raises(self):
        definition = ModelDefinition(
            id="r22_model",
            name="T",
            namespace="write_tx",
            attributes={"a": {"type": "int", "default": 1}},
        )
        with pytest.raises(TypeError):
            GrimoireModel(definition, {}, skip_initial_validaton=True)

    @pytest.mark.xfail(strict=True, reason="R22 — fixed by T018")
    def test_unknown_factory_keyword_raises(self):
        definition = ModelDefinition(
            id="r22_factory",
            name="T",
            namespace="write_tx",
            attributes={"a": {"type": "int", "default": 1}},
        )
        with pytest.raises(TypeError):
            create_model(definition, {}, derived_field_resolver_type="batched")


class TestR23Unhashable:
    """A mutable mapping must not be hashable."""

    @pytest.mark.xfail(strict=True, reason="R23 — fixed by T018")
    def test_hash_raises_for_a_flat_model(self):
        definition = ModelDefinition(
            id="r23_flat",
            name="Flat",
            namespace="write_tx",
            attributes={"a": {"type": "int", "default": 1}},
        )
        model = create_model(definition, {})
        with pytest.raises(TypeError):
            hash(model)

    def test_hash_raises_for_a_model_holding_a_group(self):
        """Today's hash already raises for any model holding a dict/list."""
        model = create_model(_group_model("r23_hash"), {"g": {"x": 1}})
        with pytest.raises(TypeError):
            hash(model)

    @pytest.mark.xfail(strict=True, reason="R23 — fixed by T018")
    def test_hash_is_disabled_on_the_class(self):
        assert GrimoireModel.__hash__ is None
