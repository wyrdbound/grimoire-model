"""Tests for inheritance resolution and model lookup.

Covers findings R40-R45. Each assertion that fails on 0.7.1 is marked
``xfail(strict=True)`` per group until its fix task removes the marker.

- R40 (T039): later parents win.
- R41 (T041): namespace-local lookup, injectable registry.
- R42 (T042): resolution registers nothing; duplicates are explicit.
- R43, R44 (T040): real depth; every cycle.
- R45 (T043): registry-analysis helpers accept namespaced registries.
"""

import pytest

from grimoire_model import (
    ModelDefinition,
    ModelRegistry,
    clear_registry,
    create_model,
    resolve_model_inheritance,
)
from grimoire_model.core.exceptions import InheritanceError, ModelValidationError
from grimoire_model.core.registry import get_default_registry
from grimoire_model.utils.inheritance import (
    check_inheritance_conflicts,
    validate_model_registry,
)


class TestR40LaterParentsWin:
    @pytest.fixture(autouse=True)
    def _clean(self):
        clear_registry()
        yield
        clear_registry()

    def _parent(self, model_id, value):
        return ModelDefinition(
            id=model_id,
            name=model_id,
            namespace="inh",
            attributes={"x": {"type": "str", "default": value}},
        )

    def test_later_parent_wins(self):
        self._parent("pb", "B")
        self._parent("pc", "C")
        kid = ModelDefinition(
            id="kid",
            name="Kid",
            namespace="inh",
            extends=["pb", "pc"],
            attributes={},
        )
        assert create_model(kid, {})["x"] == "C"

    def test_reversed_order(self):
        self._parent("pb2", "B")
        self._parent("pc2", "C")
        kid = ModelDefinition(
            id="kid2",
            name="Kid",
            namespace="inh",
            extends=["pc2", "pb2"],
            attributes={},
        )
        assert create_model(kid, {})["x"] == "B"

    def test_child_beats_both(self):
        self._parent("pb3", "B")
        self._parent("pc3", "C")
        kid = ModelDefinition(
            id="kid3",
            name="Kid",
            namespace="inh",
            extends=["pb3", "pc3"],
            attributes={"x": {"type": "str", "default": "K"}},
        )
        assert create_model(kid, {})["x"] == "K"

    def test_diamond_later_sibling_wins(self):
        self._parent("base", "BASE")
        ModelDefinition(
            id="l",
            name="L",
            namespace="inh",
            extends=["base"],
            attributes={"x": {"type": "str", "default": "L"}},
        )
        ModelDefinition(
            id="r",
            name="R",
            namespace="inh",
            extends=["base"],
            attributes={"x": {"type": "str", "default": "R"}},
        )
        diamond = ModelDefinition(
            id="d",
            name="D",
            namespace="inh",
            extends=["l", "r"],
            attributes={},
        )
        assert create_model(diamond, {})["x"] == "R"

    def test_validations_accumulate_once(self):
        from grimoire_model import ValidationRule

        ModelDefinition(
            id="va",
            name="VA",
            namespace="inh",
            attributes={"a": {"type": "int", "default": 1}},
            validations=[ValidationRule(expression="a > 0", message="a positive")],
        )
        ModelDefinition(
            id="vb",
            name="VB",
            namespace="inh",
            extends=["va"],
            attributes={},
            validations=[ValidationRule(expression="a > 0", message="a positive")],
        )
        child = ModelDefinition(
            id="vc",
            name="VC",
            namespace="inh",
            extends=["vb"],
            attributes={},
        )
        resolved = resolve_model_inheritance(
            child, get_default_registry().get_registry_dict()
        )
        assert len(resolved.validations) == 1


class TestR41NamespaceLocalLookup:
    @pytest.fixture(autouse=True)
    def _clean(self):
        clear_registry()
        yield
        clear_registry()

    def test_parent_resolves_in_the_models_own_namespace(self):
        ModelDefinition(
            id="item",
            name="QS Item",
            namespace="qs",
            attributes={"cost": {"type": "int", "default": 1}},
        )
        ModelDefinition(
            id="item",
            name="Knave Item",
            namespace="knave",
            attributes={"slot_cost": {"type": "int", "default": 1}},
        )
        weapon = ModelDefinition(
            id="weapon",
            name="Weapon",
            namespace="knave",
            extends=["item"],
            attributes={"dmg": {"type": "int", "default": 1}},
        )
        model_def = resolve_model_inheritance(weapon, get_default_registry())
        assert "slot_cost" in model_def.attributes
        assert "cost" not in model_def.attributes

    def test_unique_cross_namespace_match_resolves(self):
        """A unique cross-namespace match resolves (a fallback that stays)."""
        ModelDefinition(
            id="stat",
            name="QS Stat",
            namespace="qs",
            attributes={"v": {"type": "int", "default": 1}},
        )
        holder = ModelDefinition(
            id="knave_holder",
            name="Holder",
            namespace="knave",
            attributes={"s": {"type": "stat"}},
        )
        model = create_model(holder, {"s": {"v": 3}})
        assert model["s"]["v"] == 3

    def test_ambiguous_cross_namespace_match_raises(self):
        ModelDefinition(
            id="stat",
            name="A Stat",
            namespace="nsa",
            attributes={"v": {"type": "int", "default": 1}},
        )
        ModelDefinition(
            id="stat",
            name="B Stat",
            namespace="nsb",
            attributes={"v": {"type": "int", "default": 2}},
        )
        holder = ModelDefinition(
            id="knave_holder2",
            name="Holder",
            namespace="knave",
            attributes={"s": {"type": "stat"}},
        )
        with pytest.raises(ModelValidationError) as excinfo:
            create_model(holder, {"s": {"v": 3}})
        message = str(excinfo.value)
        assert "nsa__stat" in message
        assert "nsb__stat" in message

    def test_injectable_registry(self):
        """Lookups use the passed registry, not the global one (D10)."""
        ModelDefinition(
            id="thing",
            name="Thing",
            namespace="local",
            attributes={"v": {"type": "int", "default": 1}},
        )
        holder = ModelDefinition(
            id="holder_inj",
            name="Holder",
            namespace="local",
            attributes={"t": {"type": "thing"}},
        )
        # A different `thing`, built under its own source namespace so it does
        # not collide in the global registry, then registered as `local/thing`
        # in the injected one.
        injected_thing = ModelDefinition(
            id="thing",
            name="Thing (injected)",
            namespace="local_injected",
            attributes={"v": {"type": "int", "default": 99}},
        )
        registry = ModelRegistry()
        registry.register("local", "thing", injected_thing)
        registry.register("local", "holder_inj", holder)

        model = create_model(holder, {"t": {}}, registry=registry)
        assert model["t"]["v"] == 99

    def test_plain_dict_still_works(self):
        """Rule 6: a plain id-keyed dict still resolves inheritance."""
        item = ModelDefinition(
            id="item_plain",
            name="Item",
            namespace="plain",
            attributes={"name": {"type": "str", "default": "x"}},
        )
        child = ModelDefinition(
            id="child_plain",
            name="Child",
            namespace="plain",
            extends=["item_plain"],
            attributes={},
        )
        resolved = resolve_model_inheritance(child, {"item_plain": item})
        assert "name" in resolved.attributes


class TestR42NoRegistration:
    @pytest.fixture(autouse=True)
    def _clean(self):
        clear_registry()
        yield
        clear_registry()

    def test_resolution_does_not_register_a_default_model(self):
        ModelDefinition(
            id="item",
            name="Item",
            namespace="knave",
            attributes={"slot_cost": {"type": "int", "default": 1}},
        )
        weapon = ModelDefinition(
            id="weapon",
            name="Weapon",
            namespace="knave",
            extends=["item"],
            attributes={"dmg": {"type": "int", "default": 1}},
        )
        create_model(weapon, {})
        assert get_default_registry().get("default", "weapon") is None


class TestR43Depth:
    @pytest.fixture(autouse=True)
    def _clean(self):
        clear_registry()
        yield
        clear_registry()

    def test_ten_siblings_each_extending_one_base(self):
        ModelDefinition(
            id="base_depth",
            name="Base",
            namespace="inh",
            attributes={"z": {"type": "int", "default": 1}},
        )
        for i in range(10):
            ModelDefinition(
                id=f"sib{i}",
                name=f"Sib{i}",
                namespace="inh",
                extends=["base_depth"],
                attributes={},
            )
        kid = ModelDefinition(
            id="many_parents",
            name="Many",
            namespace="inh",
            extends=[f"sib{i}" for i in range(10)],
            attributes={},
        )
        assert create_model(kid, {})["z"] == 1

    def test_a_chain_of_exactly_max_depth_builds(self):
        ModelDefinition(
            id="leaf_md",
            name="Leaf",
            namespace="inh",
            attributes={"z": {"type": "int", "default": 1}},
        )
        previous = "leaf_md"
        for depth in range(9):
            model_id = f"level{depth}_md"
            ModelDefinition(
                id=model_id,
                name=model_id,
                namespace="inh",
                extends=[previous],
                attributes={},
            )
            previous = model_id
        top = ModelDefinition(
            id="top_md",
            name="Top",
            namespace="inh",
            extends=[previous],
            attributes={},
        )
        assert create_model(top, {})["z"] == 1

    def test_one_deeper_than_max_depth_raises(self):
        ModelDefinition(
            id="leaf_deep",
            name="Leaf",
            namespace="inh",
            attributes={"z": {"type": "int", "default": 1}},
        )
        previous = "leaf_deep"
        for depth in range(11):
            model_id = f"deep{depth}"
            ModelDefinition(
                id=model_id,
                name=model_id,
                namespace="inh",
                extends=[previous],
                attributes={},
            )
            previous = model_id
        top = ModelDefinition(
            id="top_deep",
            name="Top",
            namespace="inh",
            extends=[previous],
            attributes={},
        )
        with pytest.raises(InheritanceError, match="depth"):
            create_model(top, {})


class TestR44Cycles:
    @pytest.fixture(autouse=True)
    def _clean(self):
        clear_registry()
        yield
        clear_registry()

    def test_a_cycle_among_ancestors_raises(self):
        ModelDefinition(
            id="cy1",
            name="1",
            namespace="inh",
            extends=["cy2"],
            attributes={},
        )
        ModelDefinition(
            id="cy2",
            name="2",
            namespace="inh",
            extends=["cy1"],
            attributes={},
        )
        cyc = ModelDefinition(
            id="cyc",
            name="C",
            namespace="inh",
            extends=["cy1"],
            attributes={},
        )
        with pytest.raises(InheritanceError, match="cy1"):
            create_model(cyc, {})


class TestR45NamespacedHelpers:
    @pytest.fixture(autouse=True)
    def _clean(self):
        clear_registry()
        yield
        clear_registry()

    def test_validate_model_registry_accepts_a_namespaced_dict(self):
        ModelDefinition(
            id="base_h",
            name="Base",
            namespace="nsa",
            attributes={"z": {"type": "int", "default": 1}},
        )
        ModelDefinition(
            id="child_h",
            name="Child",
            namespace="nsb",
            extends=["base_h"],
            attributes={},
        )
        registry = get_default_registry()
        assert validate_model_registry(registry) == []
        assert validate_model_registry(registry.get_registry_dict()) == []

    def test_it_reports_a_missing_parent(self):
        ModelDefinition(
            id="orphan_h",
            name="Orphan",
            namespace="nsa",
            extends=["nowhere_h"],
            attributes={},
        )
        errors = validate_model_registry(get_default_registry())
        assert any("nowhere_h" in error for error in errors)

    def test_check_inheritance_conflicts_accepts_namespaced_keys(self):
        ModelDefinition(
            id="base_c",
            name="Base",
            namespace="nsa",
            attributes={"z": {"type": "int", "default": 1}},
        )
        child = ModelDefinition(
            id="child_c",
            name="Child",
            namespace="nsb",
            extends=["base_c"],
            attributes={},
        )
        assert (
            check_inheritance_conflicts(
                child, get_default_registry().get_registry_dict()
            )
            == []
        )
