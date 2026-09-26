"""Tests for derived-field ordering, exactness and failure visibility.

Covers findings R25-R30. Each assertion that fails on 0.7.1 is marked
``xfail(strict=True)`` per group until its fix task removes the marker.

- R25 (T026): dependencies by reference path; deterministic recompute order.
- R26 (T027): a recompute failure propagates (and the write rolls back).
- R27 (T028): derived-value conversion is exact; a bad value raises.
- R28 (T029): every observer is called; the first exception re-raises.
- R29 (T030): re-entrant batches; outer end_batch recomputes.
- R30 (T030): get_derived_fields() returns dotted paths.
"""

import os
import subprocess
import sys

import pytest

from grimoire_model import (
    ModelDefinition,
    create_derived_field_resolver,
    create_model,
    create_model_without_validation,
    create_template_resolver,
)
from grimoire_model.core.exceptions import (
    ModelValidationError,
    TemplateResolutionError,
)

_SUBPROCESS_SCRIPT = """
from grimoire_model import ModelDefinition, create_model

d = ModelDefinition(
    id="r25_sub",
    name="t",
    namespace="derived_ord",
    attributes={
        "p": {
            "score": {"type": "int"},
            "mod": {"type": "int", "derived": "{{ p.score // 2 }}"},
        },
        "total": {"type": "int", "derived": "{{ p.mod + 100 }}"},
    },
)
m = create_model(d, {"p": {"score": 10}})
print(m["total"])
m["p.score"] = 20
print(m["total"])
"""


class TestR25Ordering:
    """Nested derived fields compute in dependency order, whatever the seed."""

    def test_order_does_not_depend_on_pythonhashseed(self):
        for seed in range(8):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = str(seed)
            result = subprocess.run(
                [sys.executable, "-c", _SUBPROCESS_SCRIPT],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0, f"seed {seed} failed: {result.stderr}"
            lines = result.stdout.split()
            assert lines == ["105", "110"], f"seed {seed} printed {lines}"

    def test_full_path_dependencies(self):
        definition = ModelDefinition(
            id="r25_deps",
            name="t",
            namespace="derived_ord",
            attributes={
                "p": {
                    "score": {"type": "int"},
                    "mod": {"type": "int", "derived": "{{ p.score // 2 }}"},
                },
                "total": {"type": "int", "derived": "{{ p.mod + 100 }}"},
            },
        )
        model = create_model(definition, {"p": {"score": 10}})
        assert model.get_field_dependencies("total") == {"p.mod"}
        assert model.get_dependent_fields("p.mod") == {"total"}

    def test_chain_across_groups_recomputes_in_order(self):
        definition = ModelDefinition(
            id="r25_chain",
            name="t",
            namespace="derived_ord",
            attributes={
                "a": {"x": {"type": "int", "default": 1}},
                "b": {"y": {"type": "int", "derived": "{{ a.x + 1 }}"}},
                "c": {"type": "int", "derived": "{{ b.y * 2 }}"},
            },
        )
        model = create_model(definition, {})
        model["a.x"] = 5
        assert model["b.y"] == 6
        assert model["c"] == 12


class TestR26RecomputeFailure:
    """A derived recompute failure is not swallowed."""

    def test_division_by_zero_raises_and_rolls_back(self):
        definition = ModelDefinition(
            id="r26_divide",
            name="t",
            namespace="derived_ord",
            attributes={
                "a": {"type": "int", "default": 1},
                "b": {"type": "int", "default": 1},
                "q": {"type": "float", "derived": "{{ a / b }}"},
            },
        )
        model = create_model(definition, {})
        assert model["q"] == 1.0
        with pytest.raises(TemplateResolutionError):
            model["b"] = 0
        assert model["b"] == 1
        assert model["q"] == 1.0


class TestR27ExactConversion:
    """Derived values are converted exactly; a bad value raises."""

    @pytest.mark.xfail(strict=True, reason="R27 — fixed by T028")
    def test_int_of_a_fraction_raises(self):
        definition = ModelDefinition(
            id="r27_frac",
            name="t",
            namespace="derived_ord",
            attributes={
                "s": {"type": "int", "default": 9},
                "mod": {"type": "int", "derived": "{{ (s - 10) / 2 }}"},
            },
        )
        with pytest.raises(ModelValidationError):
            create_model(definition, {"s": 9})

    def test_int_floor_division_gives_minus_one(self):
        definition = ModelDefinition(
            id="r27_floor",
            name="t",
            namespace="derived_ord",
            attributes={
                "s": {"type": "int", "default": 9},
                "mod": {"type": "int", "derived": "{{ (s - 10) // 2 }}"},
            },
        )
        assert create_model(definition, {"s": 9})["mod"] == -1

    def test_int_of_an_integral_float_is_exact(self):
        definition = ModelDefinition(
            id="r27_integral",
            name="t",
            namespace="derived_ord",
            attributes={
                "x": {"type": "float", "default": 4.0},
                "n": {"type": "int", "derived": "{{ x }}"},
            },
        )
        assert create_model(definition, {})["n"] == 4

    @pytest.mark.xfail(strict=True, reason="R27 — fixed by T028")
    def test_int_of_a_non_numeric_raises_and_stores_nothing(self):
        definition = ModelDefinition(
            id="r27_bad_int",
            name="t",
            namespace="derived_ord",
            attributes={
                "s": {"type": "str", "default": "abc"},
                "n": {"type": "int", "derived": "{{ s }}"},
            },
        )
        with pytest.raises(ModelValidationError):
            create_model_without_validation(definition, {})

    @pytest.mark.xfail(strict=True, reason="R27 — fixed by T028")
    def test_bool_of_an_arbitrary_string_raises(self):
        definition = ModelDefinition(
            id="r27_bool",
            name="t",
            namespace="derived_ord",
            attributes={
                "s": {"type": "str", "default": "maybe"},
                "b": {"type": "bool", "derived": "{{ s }}"},
            },
        )
        with pytest.raises(ModelValidationError):
            create_model(definition, {})

    @pytest.mark.xfail(strict=True, reason="R27 — fixed by T028")
    def test_str_of_an_unset_optional_is_none(self):
        definition = ModelDefinition(
            id="r27_str_none",
            name="t",
            namespace="derived_ord",
            attributes={
                "opt": {"type": "str", "optional": True},
                "s": {"type": "str", "derived": "{{ opt }}"},
            },
        )
        assert create_model(definition, {})["s"] is None

    @pytest.mark.xfail(strict=True, reason="R27 — fixed by T028")
    def test_str_of_a_dict_raises(self):
        definition = ModelDefinition(
            id="r27_str_dict",
            name="t",
            namespace="derived_ord",
            attributes={
                "g": {"type": "dict", "default": {"a": 1}},
                "s": {"type": "str", "derived": "{{ g }}"},
            },
        )
        with pytest.raises(ModelValidationError):
            create_model(definition, {})


class TestR28Observers:
    """Every observer runs; the first exception re-raises."""

    @pytest.mark.xfail(strict=True, reason="R28 — fixed by T029")
    def test_second_observer_runs_after_the_first_raises(self):
        from grimoire_model.resolvers.derived import ObservableValue

        observable = ObservableValue("x")
        calls = []

        def first(name, old, new):
            calls.append("first")
            raise RuntimeError("boom")

        def second(name, old, new):
            calls.append("second")

        observable.add_observer(first)
        observable.add_observer(second)

        with pytest.raises(RuntimeError):
            observable.value = 5
        assert calls == ["first", "second"]


class TestR29ReentrantBatches:
    """A nested batch does not discard the outer batch's work."""

    @pytest.mark.xfail(strict=True, reason="R29 — fixed by T030")
    def test_nested_batch_recomputes_both_levels_at_the_outer_end(self):
        definition = ModelDefinition(
            id="r29_nested",
            name="t",
            namespace="derived_ord",
            attributes={
                "a": {"type": "int", "default": 0},
                "a2": {"type": "int", "derived": "{{ a * 2 }}"},
            },
        )
        resolver = create_derived_field_resolver(
            template_resolver=create_template_resolver(), batched=True
        )
        model = create_model(definition, {}, derived_field_resolver=resolver)

        resolver.start_batch()
        model["a"] = 1
        resolver.start_batch()
        model["a"] = 2
        resolver.end_batch()
        model["a"] = 3
        assert model["a2"] == 2  # not recomputed before the outer end_batch
        resolver.end_batch()
        assert model["a2"] == 6


class TestR30DerivedFieldsAreDotted:
    @pytest.mark.xfail(strict=True, reason="R30 — fixed by T030")
    def test_get_derived_fields_includes_group_leaves(self):
        definition = ModelDefinition(
            id="r30_dotted",
            name="t",
            namespace="derived_ord",
            attributes={
                "p": {
                    "s": {"type": "int", "default": 0},
                    "m": {"type": "int", "derived": "{{ p.s }}"},
                },
            },
        )
        model = create_model(definition, {})
        assert "p.m" in model.get_derived_fields()
