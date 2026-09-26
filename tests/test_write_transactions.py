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
    ValidationRule,
    create_model,
    create_model_without_validation,
)
from grimoire_model.core.exceptions import ModelValidationError
from grimoire_model.resolvers.template import create_template_resolver


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

    def test_typo_keyword_on_the_model_raises(self):
        definition = ModelDefinition(
            id="r22_model",
            name="T",
            namespace="write_tx",
            attributes={"a": {"type": "int", "default": 1}},
        )
        with pytest.raises(TypeError):
            GrimoireModel(definition, {}, skip_initial_validaton=True)

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

    def test_hash_is_disabled_on_the_class(self):
        assert GrimoireModel.__hash__ is None


def _write_model(model_id, namespace="write_tx"):
    """A model with a derived attribute and a range on it."""
    return ModelDefinition(
        id=model_id,
        name="Write",
        namespace=namespace,
        attributes={
            "a": {"type": "int", "default": 1},
            "b": {"type": "int", "range": "0..10", "derived": "{{ a * 2 }}"},
        },
    )


class TestR16WriteIsATransaction:
    """A write either leaves the model valid or leaves it untouched."""

    def test_a_recomputed_derived_field_out_of_its_range_rolls_back(self):
        model = create_model(_write_model("r16_range"), {"a": 1})
        with pytest.raises(ModelValidationError):
            model["a"] = 50
        assert dict(model) == {"a": 1, "b": 2}

    def test_a_model_level_rule_is_checked_on_write(self):
        definition = ModelDefinition(
            id="r16_rule",
            name="Rule",
            namespace="write_tx",
            attributes={
                "a": {"type": "int", "default": 1},
                "b": {"type": "int", "default": 2},
            },
            validations=[
                ValidationRule(expression="{{ a <= b }}", message="a must not exceed b")
            ],
        )
        model = create_model(definition, {"a": 1, "b": 2})
        with pytest.raises(ModelValidationError):
            model["a"] = 50
        assert model["a"] == 1

    def test_incremental_model_allows_a_valid_leaf_write(self):
        definition = ModelDefinition(
            id="r16_incremental",
            name="Inc",
            namespace="write_tx",
            attributes={
                "name": {"type": "str"},
                "n": {"type": "int", "default": 1},
                "d": {"type": "int", "range": "0..10", "derived": "{{ n * 2 }}"},
            },
        )
        model = create_model_without_validation(definition, {})
        model["n"] = 3
        assert model["d"] == 6

    def test_incremental_model_checks_a_recomputed_derived_range(self):
        definition = ModelDefinition(
            id="r16_inc_range",
            name="IncRange",
            namespace="write_tx",
            attributes={
                "name": {"type": "str"},
                "n": {"type": "int", "default": 1},
                "d": {"type": "int", "range": "0..10", "derived": "{{ n * 2 }}"},
            },
        )
        model = create_model_without_validation(definition, {})
        with pytest.raises(ModelValidationError):
            model["n"] = 50


class TestR17BatchIsOneTransaction:
    """``batch_update`` validates against recomputed data and is atomic."""

    def _pool(self, model_id, namespace="write_tx"):
        return ModelDefinition(
            id=model_id,
            name="Pool",
            namespace=namespace,
            attributes={
                "level": {"type": "int", "default": 1},
                "hp": {
                    "max": {"type": "int", "derived": "{{ level * 10 }}"},
                    "cur": {"type": "int", "range": "0..{{ hp.max }}", "default": 0},
                },
            },
        )

    def test_batch_against_recomputed_derived_succeeds(self):
        from grimoire_model import create_derived_field_resolver

        resolver = create_derived_field_resolver(
            template_resolver=create_template_resolver(),
            batched=True,
        )
        model = create_model(self._pool("r17_ok"), {}, derived_field_resolver=resolver)
        model.batch_update({"level": 10, "hp.cur": 50})
        assert model["hp.cur"] == 50
        assert model["hp.max"] == 100

    def test_batch_is_atomic_on_a_failing_field(self):
        definition = ModelDefinition(
            id="r17_atomic",
            name="Atomic",
            namespace="write_tx",
            attributes={
                "a": {"type": "int", "default": 0},
                "b": {"type": "int", "range": "0..5", "default": 0},
            },
        )
        model = create_model(definition, {})
        with pytest.raises(ModelValidationError):
            model.batch_update({"a": 2, "b": 99})
        assert model["a"] == 0


class TestR18DerivedNotWritable:
    def test_writing_a_derived_attribute_raises(self):
        definition = ModelDefinition(
            id="r18_derived",
            name="Derived",
            namespace="write_tx",
            attributes={
                "a": {"type": "int", "default": 1},
                "b": {"type": "int", "derived": "{{ a + 1 }}"},
            },
        )
        model = create_model(definition, {"a": 1})
        with pytest.raises(ModelValidationError):
            model["b"] = 100
        assert model["b"] == 2


class TestR19Delete:
    def test_deleting_a_readonly_attribute_raises(self):
        definition = ModelDefinition(
            id="r19_ro",
            name="RO",
            namespace="write_tx",
            attributes={"id": {"type": "str", "readonly": True, "default": "x"}},
        )
        model = create_model(definition, {})
        with pytest.raises(ModelValidationError):
            del model["id"]

    def test_deleting_a_required_attribute_raises(self):
        model = create_model(_write_model("r19_req"), {"a": 1})
        with pytest.raises(ModelValidationError):
            del model["a"]

    def test_deleting_a_derived_attribute_raises(self):
        model = create_model(_write_model("r19_derived"), {"a": 1})
        with pytest.raises(ModelValidationError):
            del model["b"]

    def test_deleting_an_optional_attribute_unsets_it(self):
        definition = ModelDefinition(
            id="r19_opt",
            name="Opt",
            namespace="write_tx",
            attributes={
                "opt": {"type": "int", "optional": True},
                "doubled": {"type": "int", "derived": "{{ (opt or 0) * 2 }}"},
            },
        )
        model = create_model(definition, {"opt": 5})
        del model["opt"]
        assert "opt" not in model
        assert model["doubled"] == 0


class TestR20ReadonlyLeafInGroup:
    def test_a_readonly_group_leaf_cannot_be_written(self):
        definition = ModelDefinition(
            id="r20_group",
            name="Group",
            namespace="write_tx",
            attributes={
                "g": {"k": {"type": "str", "readonly": True, "default": "a"}},
            },
        )
        model = create_model(definition, {})
        with pytest.raises(ModelValidationError):
            model["g.k"] = "b"


class TestR21UndeclaredKeys:
    @pytest.mark.xfail(strict=True, reason="R21 — fixed by T023")
    def test_undeclared_key_on_build_raises(self):
        definition = ModelDefinition(
            id="r21_build",
            name="T",
            namespace="write_tx",
            attributes={"strength": {"type": "int"}},
        )
        with pytest.raises(ModelValidationError, match="strenght"):
            create_model(definition, {"strength": 1, "strenght": 5})

    @pytest.mark.xfail(strict=True, reason="R21 — fixed by T023")
    def test_undeclared_key_on_write_raises(self):
        definition = ModelDefinition(
            id="r21_write",
            name="T",
            namespace="write_tx",
            attributes={"strength": {"type": "int"}},
        )
        model = create_model(definition, {"strength": 1})
        with pytest.raises(ModelValidationError, match="dexterity"):
            model["dexterity"] = 1

    @pytest.mark.xfail(strict=True, reason="R21 — fixed by T023")
    def test_undeclared_key_in_a_group_raises_naming_the_path(self):
        definition = ModelDefinition(
            id="r21_group",
            name="T",
            namespace="write_tx",
            attributes={"g": {"x": {"type": "int"}}},
        )
        with pytest.raises(ModelValidationError, match="g.y"):
            create_model(definition, {"g": {"x": 1, "y": 2}})

    @pytest.mark.xfail(strict=True, reason="R21 — fixed by T023")
    def test_validate_reports_an_undeclared_key(self):
        definition = ModelDefinition(
            id="r21_validate",
            name="T",
            namespace="write_tx",
            attributes={"strength": {"type": "int"}},
        )
        model = create_model_without_validation(
            definition, {"strength": 1, "dexterity": 3}
        )
        assert any("dexterity" in error for error in model.validate())
