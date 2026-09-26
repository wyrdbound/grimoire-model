"""Tests for type validation: groups, nested models, lists and ranges.

Covers findings R31-R39. Each assertion that fails on 0.7.1 is marked
``xfail(strict=True)`` per group until its fix task removes the marker.

- R31, R32 (T032): groups and model-typed attributes must hold mappings.
- R33 (T033): ``of`` is enforced.
- R34 (T034): a model-typed attribute inside a group is built.
- R35 (T035): nested models inherit the parent's validation mode.
- R36 (T036): one range parser for numbers and lengths.
- R37, R38, R39 (T037): full-match pattern; one missing-required error;
  ``enabled_validators=[]`` runs none.
"""

import pytest

from grimoire_model import (
    AttributeDefinition,
    GrimoireModel,
    ModelDefinition,
    create_model,
    create_model_without_validation,
)
from grimoire_model.core.exceptions import ModelValidationError
from grimoire_model.validation.validators import validate_field_value


class TestR31GroupsHoldMappings:
    def test_building_a_group_from_a_non_mapping_raises(self):
        definition = ModelDefinition(
            id="r31_group",
            name="t",
            namespace="type_val",
            attributes={"g": {"x": {"type": "int"}}},
        )
        with pytest.raises(ModelValidationError):
            create_model(definition, {"g": 5})

    def test_writing_a_non_mapping_to_a_group_raises(self):
        """A group's value is validated on write like any other field."""
        definition = ModelDefinition(
            id="r31_group_write",
            name="t",
            namespace="type_val",
            attributes={"g": {"x": {"type": "int"}}},
        )
        model = create_model(definition, {"g": {"x": 1}})
        with pytest.raises(ModelValidationError):
            model["g"] = 5


class TestR32ModelTypedHoldMappings:
    def _models(self, suffix):
        ModelDefinition(
            id=f"weapon_{suffix}",
            name="Weapon",
            namespace="type_val",
            attributes={"name": {"type": "str", "default": "sword"}},
        )
        ModelDefinition(
            id=f"other_{suffix}",
            name="Other",
            namespace="type_val",
            attributes={"name": {"type": "str", "default": "other"}},
        )
        return ModelDefinition(
            id=f"holder_{suffix}",
            name="Holder",
            namespace="type_val",
            attributes={"w": {"type": f"weapon_{suffix}"}},
        )

    def test_building_a_model_typed_attribute_from_a_non_mapping_raises(self):
        definition = self._models("build")
        with pytest.raises(ModelValidationError):
            create_model(definition, {"w": 5})

    def test_a_model_of_a_different_id_raises(self):
        definition = self._models("wrong")
        other = create_model(
            ModelDefinition(
                id="other_wrong",
                name="Other",
                namespace="type_val",
                attributes={"name": {"type": "str", "default": "other"}},
            ),
            {},
        )
        with pytest.raises(ModelValidationError):
            create_model(definition, {"w": other})

    def test_a_model_of_the_same_id_is_accepted(self):
        definition = self._models("same")
        weapon = create_model(
            ModelDefinition(
                id="weapon_same",
                name="Weapon",
                namespace="type_val",
                attributes={"name": {"type": "str", "default": "sword"}},
            ),
            {},
        )
        model = create_model(definition, {"w": weapon})
        assert model["w"]["name"] == "sword"

    def test_writing_a_non_mapping_to_a_model_typed_attribute_raises(self):
        definition = self._models("write")
        model = create_model(definition, {"w": {"name": "sword"}})
        with pytest.raises(ModelValidationError):
            model["w"] = 5


class TestR33ListOf:
    @pytest.mark.xfail(strict=True, reason="R33 — fixed by T033")
    def test_primitive_of_validates_elements(self):
        definition = ModelDefinition(
            id="r33_int",
            name="t",
            namespace="type_val",
            attributes={"xs": {"type": "list", "of": "int"}},
        )
        assert create_model(definition, {"xs": [1, 2]})["xs"] == [1, 2]
        with pytest.raises(ModelValidationError, match=r"xs\[0\]"):
            create_model(definition, {"xs": ["a"]})

    @pytest.mark.xfail(strict=True, reason="R33 — fixed by T033")
    def test_model_of_builds_elements(self):
        ModelDefinition(
            id="item_r33",
            name="Item",
            namespace="type_val",
            attributes={
                "w": {"type": "int"},
                "dbl": {"type": "int", "derived": "{{ w * 2 }}"},
            },
        )
        definition = ModelDefinition(
            id="r33_inv",
            name="Inv",
            namespace="type_val",
            attributes={"inv": {"type": "list", "of": "item_r33"}},
        )
        model = create_model(definition, {"inv": [{"w": 2}]})
        element = model["inv"][0]
        assert isinstance(element, GrimoireModel)
        assert element["dbl"] == 4

        with pytest.raises(ModelValidationError, match=r"inv\[0\]"):
            create_model(definition, {"inv": [{"w": "heavy"}]})

    @pytest.mark.xfail(strict=True, reason="R33 — fixed by T033")
    def test_a_write_of_a_model_list_builds_and_validates(self):
        ModelDefinition(
            id="item_r33w",
            name="Item",
            namespace="type_val",
            attributes={
                "w": {"type": "int"},
                "dbl": {"type": "int", "derived": "{{ w * 2 }}"},
            },
        )
        definition = ModelDefinition(
            id="r33_inv_w",
            name="Inv",
            namespace="type_val",
            attributes={"inv": {"type": "list", "of": "item_r33w"}},
        )
        model = create_model(definition, {"inv": []})
        model["inv"] = [{"w": 3}]
        assert model["inv"][0]["dbl"] == 6


class TestR34ModelTypedLeafInGroup:
    def _definition(self):
        ModelDefinition(
            id="abil_r34",
            name="Ability",
            namespace="type_val",
            attributes={
                "bonus": {"type": "int"},
                "defense": {"type": "int", "derived": "{{ bonus + 10 }}"},
            },
        )
        return ModelDefinition(
            id="r34_char",
            name="Char",
            namespace="type_val",
            attributes={"abilities": {"con": {"type": "abil_r34"}}},
        )

    @pytest.mark.xfail(strict=True, reason="R34 — fixed by T034")
    def test_the_nested_model_is_built_on_construction(self):
        model = create_model(
            self._definition(),
            {"abilities": {"con": {"bonus": 3}}},
            skip_initial_validation=True,
        )
        assert model["abilities"]["con"]["defense"] == 13

    @pytest.mark.xfail(strict=True, reason="R34 — fixed by T034")
    def test_a_dotted_write_descends_into_it(self):
        model = create_model(
            self._definition(),
            {"abilities": {"con": {"bonus": 3}}},
            skip_initial_validation=True,
        )
        model["abilities.con.bonus"] = 4
        assert model["abilities"]["con"]["defense"] == 14


class TestR35NestedInheritsValidationMode:
    @pytest.mark.xfail(strict=True, reason="R35 — fixed by T035")
    def test_incremental_parent_builds_incremental_children(self):
        ModelDefinition(
            id="sword_r35",
            name="Sword",
            namespace="type_val",
            attributes={"name": {"type": "str"}},
        )
        definition = ModelDefinition(
            id="holder_r35",
            name="Holder",
            namespace="type_val",
            attributes={"w": {"type": "sword_r35", "optional": True}},
        )
        model = create_model_without_validation(definition, {"w": {}})
        assert any("name" in error for error in model.validate())


class TestR36OneRangeParser:
    @pytest.mark.xfail(strict=True, reason="R36 — fixed by T036")
    def test_length_range_ge_on_a_list(self):
        definition = ModelDefinition(
            id="r36_list",
            name="t",
            namespace="type_val",
            attributes={"xs": {"type": "list", "range": ">=2", "default": []}},
        )
        assert create_model(definition, {"xs": [1, 2]})
        with pytest.raises(ModelValidationError):
            create_model(definition, {})

    def test_length_range_on_a_string(self):
        """A ``min..max`` length range is enforced on a string."""
        definition = ModelDefinition(
            id="r36_str",
            name="t",
            namespace="type_val",
            attributes={"s": {"type": "str", "range": "..3"}},
        )
        assert create_model(definition, {"s": "abc"})
        with pytest.raises(ModelValidationError):
            create_model(definition, {"s": "abcd"})

    @pytest.mark.xfail(strict=True, reason="R36 — fixed by T036")
    def test_an_unparseable_range_is_an_error_not_a_pass(self):
        definition = ModelDefinition(
            id="r36_bad",
            name="t",
            namespace="type_val",
            attributes={"s": {"type": "str", "range": "a..b"}},
        )
        with pytest.raises(ModelValidationError):
            create_model(definition, {"s": "anything"})


class TestR37Pattern:
    @pytest.mark.xfail(strict=True, reason="R37 — fixed by T037")
    def test_pattern_is_a_full_match(self):
        definition = ModelDefinition(
            id="r37_pattern",
            name="t",
            namespace="type_val",
            attributes={"code": {"type": "str", "pattern": "[a-z]+"}},
        )
        assert create_model(definition, {"code": "abc"})
        with pytest.raises(ModelValidationError):
            create_model(definition, {"code": "abc123!"})


class TestR38OneMissingRequiredError:
    @pytest.mark.xfail(strict=True, reason="R38 — fixed by T037")
    def test_a_missing_required_field_produces_one_error(self):
        definition = ModelDefinition(
            id="r38_req",
            name="t",
            namespace="type_val",
            attributes={"a": {"type": "int"}},
        )
        errors = create_model_without_validation(definition, {}).validate()
        assert len(errors) == 1


class TestR39EnabledValidatorsEmpty:
    @pytest.mark.xfail(strict=True, reason="R39 — fixed by T037")
    def test_empty_list_runs_no_validators(self):
        assert (
            validate_field_value(
                "x", "f", AttributeDefinition(type="int"), enabled_validators=[]
            )
            == []
        )
