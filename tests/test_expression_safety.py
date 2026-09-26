"""Tests for expression safety: raising, sandboxing, data-before-methods.

Covers findings R01-R04 from the 0.7.1 review. Each failing assertion is
marked ``xfail(strict=True)`` until its fix task removes the marker; baseline
assertions that already hold on 0.7.1 are unmarked so a regression is caught.

- R01 (T003): an unresolvable expression raises instead of becoming ``None``.
- R02 (T004): the evaluation environment is sandboxed.
- R03 (T005): ``x.name`` on a mapping means the data at ``name``, not a method.
- R04 (T006): only a single ``{{ expression }}`` keeps its value's type.
"""

import pytest

from grimoire_model import ModelDefinition, create_model
from grimoire_model.core.exceptions import TemplateResolutionError
from grimoire_model.resolvers.template import create_template_resolver

R = create_template_resolver()


class TestR01UnresolvedRaises:
    """An expression that cannot be resolved raises, never becomes None."""

    def test_missing_nested_name_raises(self):
        with pytest.raises(TemplateResolutionError):
            R.resolve_template("{{ g.missing }}", {"g": {"a": 1}})

    def test_dotted_access_into_scalar_raises(self):
        with pytest.raises(TemplateResolutionError):
            R.resolve_template("{{ g.a.b }}", {"g": {"a": 1}})

    def test_misspelled_derived_leaf_fails_create_model(self):
        definition = ModelDefinition(
            id="r01_misspelled",
            name="R01",
            namespace="exprsafe",
            attributes={
                "g": {
                    "x": {"type": "int", "default": 0},
                    "y": {"type": "int", "derived": "{{ g.xx }}"},
                },
            },
        )
        with pytest.raises(TemplateResolutionError):
            create_model(definition, {"g": {"x": 1}})

    def test_present_nested_name_still_returns_value(self):
        assert R.resolve_template("{{ g.a }}", {"g": {"a": 1}}) == 1

    def test_unset_optional_reads_as_none(self):
        definition = ModelDefinition(
            id="r01_optional_none",
            name="R01",
            namespace="exprsafe",
            attributes={
                "opt": {"type": "int", "optional": True},
                "is_none": {"type": "bool", "derived": "{{ opt is none }}"},
            },
        )
        model = create_model(definition, {})
        assert model["is_none"] is True


class TestR02Sandboxed:
    """Model expressions cannot reach Python internals."""

    def test_class_attribute_raises(self):
        with pytest.raises(TemplateResolutionError):
            R.resolve_template("{{ ''.__class__ }}", {})

    def test_subclasses_walk_raises(self):
        with pytest.raises(TemplateResolutionError):
            R.resolve_template("{{ ''.__class__.__mro__[1].__subclasses__() }}", {})

    def test_filters_still_work(self):
        assert R.resolve_template("{{ xs | sum }}", {"xs": [1, 2, 3]}) == 6
        assert R.resolve_template("{{ name | upper }}", {"name": "orc"}) == "ORC"


class TestR03DataBeforeMethods:
    """``x.name`` on a mapping means the data at ``name``."""

    def test_key_shadows_dict_methods(self):
        ctx = {"g": {"items": 3, "keys": 4, "get": 5}}
        assert R.resolve_template("{{ g.items + 1 }}", ctx) == 4
        assert R.resolve_template("{{ g.keys }}", ctx) == 4
        assert R.resolve_template("{{ g.get * 2 }}", ctx) == 10

    def test_model_attribute_named_items(self):
        ModelDefinition(
            id="r03_bag",
            name="Bag",
            namespace="exprsafe",
            attributes={"items": {"type": "list"}},
        )
        parent = ModelDefinition(
            id="r03_parent",
            name="Parent",
            namespace="exprsafe",
            attributes={
                "bag": {"type": "r03_bag"},
                "n": {"type": "int", "derived": "{{ bag.items | length }}"},
            },
        )
        model = create_model(parent, {"bag": {"items": [1, 2]}})
        assert model["n"] == 2

    def test_absent_key_does_not_fall_back_to_method(self):
        with pytest.raises(TemplateResolutionError):
            R.resolve_template("{{ g.values }}", {"g": {}})

    def test_method_call_on_mapping_raises(self):
        """A mapping exposes data, not methods; use filters instead."""
        with pytest.raises(TemplateResolutionError):
            R.resolve_template("{{ g.items() }}", {"g": {}})

    def test_filters_replace_mapping_methods(self):
        ctx = {"g": {"k": 1, "j": 2}}
        assert R.resolve_template("{{ g | items | list }}", ctx) == [
            ("k", 1),
            ("j", 2),
        ]
        assert R.resolve_template("{{ g | length }}", ctx) == 2
        assert R.resolve_template("{{ 'k' in g }}", ctx) is True


class TestR04MixedTemplatesAreStrings:
    """Only a single ``{{ expression }}`` keeps its value's type."""

    @pytest.mark.xfail(strict=True, reason="R04 — fixed by T006")
    def test_text_around_expression_is_a_string(self):
        assert R.resolve_template("[{{ a }}]", {"a": 1}) == "[1]"

    def test_two_expressions_render_to_text(self):
        result = R.resolve_template("{{ a }}, {{ b }}", {"a": 1, "b": 2})
        assert result == "1, 2"
        assert isinstance(result, str)

    def test_single_expression_keeps_type(self):
        assert R.resolve_template("{{ xs }}", {"xs": [1]}) == [1]
