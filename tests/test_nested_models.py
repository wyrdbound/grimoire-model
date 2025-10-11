"""Tests for nested model instantiation functionality."""

import pytest

from grimoire_model import (
    AttributeDefinition,
    ModelDefinition,
    clear_registry,
    create_model,
)
from grimoire_model.core.exceptions import ModelValidationError
from grimoire_model.core.model import GrimoireModel


class TestNestedModelInstantiation:
    """Test automatic instantiation of nested model types."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_registry()

    def test_two_level_nesting_with_derived_fields(self):
        """Test 2-level nesting: model → nested model with derived field."""
        # Define nested model with derived field
        stat_def = ModelDefinition(  # noqa: F841 (auto-registers)
            id="stat",
            name="Stat",
            namespace="test",
            attributes={
                "value": AttributeDefinition(type="int", required=True),
                "bonus": AttributeDefinition(
                    type="int", derived="{{ (value - 10) // 2 }}"
                ),
            },
        )

        # Define parent model that uses the nested model type
        character_def = ModelDefinition(
            id="character",
            name="Character",
            namespace="test",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "constitution": AttributeDefinition(type="stat", required=False),
                "hit_points": AttributeDefinition(
                    type="int", derived="{{ 10 + constitution.bonus }}"
                ),
            },
        )

        # Create character with nested stat data
        character_data = {"name": "Hero", "constitution": {"value": 14}}

        character = create_model(character_def, character_data)

        # Verify nested model is instantiated as GrimoireModel
        assert isinstance(character["constitution"], GrimoireModel)
        assert character["constitution"]["value"] == 14
        assert character["constitution"]["bonus"] == 2  # (14-10)//2 = 2

        # Verify parent's derived field can access nested derived field
        assert character["hit_points"] == 12  # 10 + 2

    def test_three_level_nesting_deep_derived_access(self):
        """Test 3-level nesting: model → nested → deeply nested model."""
        # Level 3: Deepest nested model
        stat_def = ModelDefinition(  # noqa: F841 (auto-registers)
            id="stat",
            name="Stat",
            namespace="test",
            attributes={
                "value": AttributeDefinition(type="int", required=True),
                "bonus": AttributeDefinition(
                    type="int", derived="{{ (value - 10) // 2 }}"
                ),
            },
        )

        # Level 2: Container for multiple stats
        abilities_def = ModelDefinition(  # noqa: F841 (auto-registers)
            id="abilities",
            name="Abilities",
            namespace="test",
            attributes={
                "strength": AttributeDefinition(type="stat", required=False),
                "constitution": AttributeDefinition(type="stat", required=False),
                "dexterity": AttributeDefinition(type="stat", required=False),
            },
        )

        # Level 1: Top-level model accessing deeply nested derived fields
        character_def = ModelDefinition(
            id="character",
            name="Character",
            namespace="test",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "abilities": AttributeDefinition(type="abilities", required=False),
                "hit_points": AttributeDefinition(
                    type="int", derived="{{ 10 + abilities.constitution.bonus }}"
                ),
            },
        )

        # Create with 3-level nested data
        character_data = {
            "name": "Hero",
            "abilities": {"constitution": {"value": 14}},
        }

        character = create_model(character_def, character_data)

        # Verify 3-level nesting is properly instantiated
        assert isinstance(character["abilities"], GrimoireModel)
        assert isinstance(character["abilities"]["constitution"], GrimoireModel)
        assert character["abilities"]["constitution"]["value"] == 14
        assert character["abilities"]["constitution"]["bonus"] == 2

        # Verify deep derived field access works
        assert character["hit_points"] == 12

    def test_mixed_primitive_and_model_types(self):
        """Test model with both primitive types and nested model types."""
        stat_def = ModelDefinition(  # noqa: F841 (auto-registers)
            id="stat",
            name="Stat",
            namespace="test",
            attributes={
                "value": AttributeDefinition(type="int", required=True),
                "bonus": AttributeDefinition(
                    type="int", derived="{{ (value - 10) // 2 }}"
                ),
            },
        )

        mixed_def = ModelDefinition(
            id="mixed",
            name="Mixed",
            namespace="test",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "level": AttributeDefinition(type="int", required=True),
                "tags": AttributeDefinition(type="list", required=False),
                "stats": AttributeDefinition(type="dict", required=False),
                "primary_stat": AttributeDefinition(type="stat", required=False),
            },
        )

        data = {
            "name": "Test",
            "level": 5,
            "tags": ["tag1", "tag2"],
            "stats": {"str": 10, "dex": 12},
            "primary_stat": {"value": 16},
        }

        model = create_model(mixed_def, data)

        # Verify primitives are unchanged
        assert model["name"] == "Test"
        assert model["level"] == 5
        assert model["tags"] == ["tag1", "tag2"]
        assert model["stats"] == {"str": 10, "dex": 12}

        # Verify nested model is instantiated
        assert isinstance(model["primary_stat"], GrimoireModel)
        assert model["primary_stat"]["value"] == 16
        assert model["primary_stat"]["bonus"] == 3

    def test_nested_model_already_instantiated(self):
        """Test that already-instantiated nested models are not re-instantiated."""
        stat_def = ModelDefinition(
            id="stat",
            name="Stat",
            namespace="test",
            attributes={
                "value": AttributeDefinition(type="int", required=True),
                "bonus": AttributeDefinition(
                    type="int", derived="{{ (value - 10) // 2 }}"
                ),
            },
        )

        character_def = ModelDefinition(
            id="character",
            name="Character",
            namespace="test",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "stat": AttributeDefinition(type="stat", required=False),
            },
        )

        # Pre-instantiate the nested model
        stat = create_model(stat_def, {"value": 14})
        character_data = {"name": "Hero", "stat": stat}

        character = create_model(character_def, character_data)

        # Should be the same instance (or at least the same values)
        assert isinstance(character["stat"], GrimoireModel)
        assert character["stat"]["value"] == 14
        assert character["stat"]["bonus"] == 2

    def test_nested_model_with_none_value(self):
        """Test that None values for optional nested models are preserved."""
        stat_def = ModelDefinition(  # noqa: F841 (auto-registers)
            id="stat",
            name="Stat",
            namespace="test",
            attributes={
                "value": AttributeDefinition(type="int", required=True),
            },
        )

        character_def = ModelDefinition(
            id="character",
            name="Character",
            namespace="test",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "stat": AttributeDefinition(type="stat", required=False),
            },
        )

        character_data = {"name": "Hero", "stat": None}
        character = create_model(character_def, character_data)

        assert character["stat"] is None

    def test_nested_model_missing_optional(self):
        """Test that missing optional nested models don't cause errors."""
        stat_def = ModelDefinition(  # noqa: F841 (auto-registers)
            id="stat",
            name="Stat",
            namespace="test",
            attributes={
                "value": AttributeDefinition(type="int", required=True),
            },
        )

        character_def = ModelDefinition(
            id="character",
            name="Character",
            namespace="test",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "stat": AttributeDefinition(type="stat", required=False),
            },
        )

        character_data = {"name": "Hero"}
        character = create_model(character_def, character_data)

        # Should work without the optional nested model
        assert character["name"] == "Hero"
        assert "stat" not in character

    def test_cross_namespace_model_types(self):
        """Test nested models can be referenced across namespaces."""
        # Define model in one namespace
        stat_def = ModelDefinition(  # noqa: F841 (auto-registers)
            id="stat",
            name="Stat",
            namespace="common",
            attributes={
                "value": AttributeDefinition(type="int", required=True),
                "bonus": AttributeDefinition(
                    type="int", derived="{{ (value - 10) // 2 }}"
                ),
            },
        )

        # Reference it from another namespace
        character_def = ModelDefinition(
            id="character",
            name="Character",
            namespace="game",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "stat": AttributeDefinition(type="stat", required=False),
            },
        )

        character_data = {"name": "Hero", "stat": {"value": 14}}
        character = create_model(character_def, character_data)

        # Should find the model across namespaces
        assert isinstance(character["stat"], GrimoireModel)
        assert character["stat"]["bonus"] == 2

    def test_multiple_nested_models_same_type(self):
        """Test multiple attributes using the same nested model type."""
        stat_def = ModelDefinition(  # noqa: F841 (auto-registers)
            id="stat",
            name="Stat",
            namespace="test",
            attributes={
                "value": AttributeDefinition(type="int", required=True),
                "bonus": AttributeDefinition(
                    type="int", derived="{{ (value - 10) // 2 }}"
                ),
            },
        )

        character_def = ModelDefinition(
            id="character",
            name="Character",
            namespace="test",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "strength": AttributeDefinition(type="stat", required=False),
                "dexterity": AttributeDefinition(type="stat", required=False),
                "constitution": AttributeDefinition(type="stat", required=False),
            },
        )

        character_data = {
            "name": "Hero",
            "strength": {"value": 16},
            "dexterity": {"value": 14},
            "constitution": {"value": 12},
        }

        character = create_model(character_def, character_data)

        # All should be instantiated as separate GrimoireModel instances
        assert isinstance(character["strength"], GrimoireModel)
        assert isinstance(character["dexterity"], GrimoireModel)
        assert isinstance(character["constitution"], GrimoireModel)

        assert character["strength"]["bonus"] == 3  # (16-10)//2
        assert character["dexterity"]["bonus"] == 2  # (14-10)//2
        assert character["constitution"]["bonus"] == 1  # (12-10)//2

    def test_nested_model_update_triggers_parent_derived_fields(self):
        """Test updating nested model triggers parent derived fields."""
        stat_def = ModelDefinition(  # noqa: F841 (auto-registers)
            id="stat",
            name="Stat",
            namespace="test",
            attributes={
                "value": AttributeDefinition(type="int", required=True),
                "bonus": AttributeDefinition(
                    type="int", derived="{{ (value - 10) // 2 }}"
                ),
            },
        )

        character_def = ModelDefinition(
            id="character",
            name="Character",
            namespace="test",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "constitution": AttributeDefinition(type="stat", required=False),
                "hit_points": AttributeDefinition(
                    type="int", derived="{{ 10 + constitution.bonus }}"
                ),
            },
        )

        character_data = {"name": "Hero", "constitution": {"value": 14}}
        character = create_model(character_def, character_data)

        assert character["hit_points"] == 12  # 10 + 2

        # Update the nested model's value
        character["constitution"]["value"] = 18

        # Parent's derived field should update (once we trigger recomputation)
        character.recompute_derived_fields()
        assert character["hit_points"] == 14  # 10 + 4

    def test_primitive_types_not_instantiated(self):
        """Test that primitive types are not treated as model types."""
        model_def = ModelDefinition(
            id="test",
            name="Test",
            namespace="test",
            attributes={
                "int_field": AttributeDefinition(type="int", required=False),
                "str_field": AttributeDefinition(type="str", required=False),
                "float_field": AttributeDefinition(type="float", required=False),
                "bool_field": AttributeDefinition(type="bool", required=False),
                "list_field": AttributeDefinition(type="list", required=False),
                "dict_field": AttributeDefinition(type="dict", required=False),
            },
        )

        data = {
            "int_field": 42,
            "str_field": "test",
            "float_field": 3.14,
            "bool_field": True,
            "list_field": [1, 2, 3],
            "dict_field": {"key": "value"},
        }

        model = create_model(model_def, data)

        # All should remain as primitive types
        assert model["int_field"] == 42
        assert model["str_field"] == "test"
        assert model["float_field"] == 3.14
        assert model["bool_field"] is True
        assert model["list_field"] == [1, 2, 3]
        assert model["dict_field"] == {"key": "value"}

    def test_unregistered_model_type_raises_error(self):
        """Test that referencing an unregistered model type raises an error."""
        # Don't register the "unknown_model" type
        model_def = ModelDefinition(
            id="test",
            name="Test",
            namespace="test",
            attributes={
                "name": AttributeDefinition(type="str", required=True),
                "unknown": AttributeDefinition(type="unknown_model", required=False),
            },
        )

        # Should raise ModelValidationError for invalid type
        data = {"name": "Test", "unknown": {"value": 42}}
        with pytest.raises(ModelValidationError) as exc_info:
            create_model(model_def, data)

        assert "Invalid model type 'unknown_model'" in str(exc_info.value)
