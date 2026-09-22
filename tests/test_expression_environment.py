"""Tests for the expression evaluation environment.

Covers two guarantees that model expressions rely on:

1. The dead ``$`` context key is gone from the derived-field resolver. ``$``
   is not a valid Jinja2 identifier, so ``{{ $.field }}`` could never be
   rendered; only dependency extraction ever pretended to support it.
2. Jinja2's own globals are not reachable from an expression, so a
   misspelled or missing attribute always raises instead of silently
   resolving to a builtin.
"""

import pytest

from grimoire_model import ModelDefinition, create_model
from grimoire_model.core.exceptions import TemplateResolutionError

JINJA_GLOBALS = ["range", "dict", "namespace", "cycler", "joiner", "lipsum"]


class TestDollarRemoved:
    """``$`` is no longer part of the derived-field context."""

    def test_context_has_no_dollar_key(self):
        definition = ModelDefinition(
            id="dollar_ctx",
            name="Dollar",
            namespace="exprenv",
            attributes={
                "score": {"type": "int", "default": 10},
                "doubled": {"type": "int", "derived": "{{ score * 2 }}"},
            },
        )
        model = create_model(definition, {"score": 7})
        context = model._derived_field_resolver._build_template_context()

        assert "$" not in context
        assert context["score"] == 7

    def test_dollar_expression_raises_rather_than_silently_working(self):
        definition = ModelDefinition(
            id="dollar_expr",
            name="DollarExpr",
            namespace="exprenv",
            attributes={
                "score": {"type": "int", "default": 10},
                "doubled": {"type": "int", "derived": "{{ $.score * 2 }}"},
            },
        )
        with pytest.raises(TemplateResolutionError):
            create_model(definition, {"score": 7})


class TestJinjaGlobalsUnavailable:
    """Jinja2 globals must not leak into model expressions."""

    @pytest.mark.parametrize("global_name", JINJA_GLOBALS)
    def test_missing_attribute_named_like_a_global_raises(self, global_name):
        definition = ModelDefinition(
            id=f"global_{global_name}",
            name="Globals",
            namespace="exprenv",
            attributes={
                "present": {"type": "int", "default": 1},
                "out": {"type": "str", "derived": f"{{{{ {global_name} }}}}"},
            },
        )
        with pytest.raises(TemplateResolutionError):
            create_model(definition, {"present": 1})

    def test_attribute_may_be_named_like_a_global(self):
        """An attribute named ``range`` shadows nothing and resolves normally."""
        definition = ModelDefinition(
            id="range_attr",
            name="RangeAttr",
            namespace="exprenv",
            attributes={
                "range": {"type": "int", "default": 30},
                "extended": {"type": "int", "derived": "{{ range + 10 }}"},
            },
        )
        model = create_model(definition, {"range": 30})
        assert model["extended"] == 40

    def test_filters_still_work(self):
        """Clearing globals must not remove filters."""
        definition = ModelDefinition(
            id="filters",
            name="Filters",
            namespace="exprenv",
            attributes={
                "weights": {"type": "list", "default": [1, 2, 3]},
                "total": {"type": "int", "derived": "{{ weights | sum }}"},
                "label": {"type": "str", "derived": "{{ 'orc' | title }}"},
            },
        )
        model = create_model(definition, {"weights": [1, 2, 3]})
        assert model["total"] == 6
        assert model["label"] == "Orc"
