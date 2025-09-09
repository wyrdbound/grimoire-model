"""Test fixtures and utilities for wyrdbound-model tests."""

import pytest

from wyrdbound_model import AttributeDefinition, ModelDefinition, ValidationRule


@pytest.fixture
def simple_model_def():
    """Simple model definition for testing."""
    return ModelDefinition(
        id="simple_test_model",
        name="Simple Test Model",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "level": AttributeDefinition(type="int", default=1),
            "score": AttributeDefinition(type="float", default=0.0),
            "active": AttributeDefinition(type="bool", default=True),
        },
    )


@pytest.fixture
def character_model_def():
    """Character model definition with derived fields."""
    return ModelDefinition(
        id="character",
        name="Player Character",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "level": AttributeDefinition(type="int", default=1, range="1..20"),
            "strength": AttributeDefinition(type="int", default=10, range="3..18"),
            "dexterity": AttributeDefinition(type="int", default=10, range="3..18"),
            "constitution": AttributeDefinition(type="int", default=10, range="3..18"),
            "hit_points": AttributeDefinition(type="int", default=8),
            "max_hit_points": AttributeDefinition(
                type="int",
                derived="{{ level * 8 + (constitution - 10) * level // 2 }}",
                computed=True,
            ),
            "armor_class": AttributeDefinition(
                type="int", derived="{{ 10 + (dexterity - 10) // 2 }}", computed=True
            ),
        },
        validations=[
            ValidationRule(
                expression="{{ hit_points <= max_hit_points }}",
                message="Hit points cannot exceed maximum hit points",
            )
        ],
    )


@pytest.fixture
def inheritance_parent_model():
    """Parent model for inheritance testing."""
    return ModelDefinition(
        id="base_entity",
        name="Base Entity",
        attributes={
            "id": AttributeDefinition(type="str", required=True),
            "name": AttributeDefinition(type="str", required=True),
            "description": AttributeDefinition(type="str", default=""),
            "created_at": AttributeDefinition(type="str", default=""),
        },
    )


@pytest.fixture
def inheritance_child_model():
    """Child model for inheritance testing."""
    return ModelDefinition(
        id="character_entity",
        name="Character Entity",
        extends=["base_entity"],
        attributes={
            "level": AttributeDefinition(type="int", default=1),
            "experience": AttributeDefinition(type="int", default=0),
            "class_name": AttributeDefinition(type="str", default="fighter"),
        },
    )


@pytest.fixture
def model_registry(
    inheritance_parent_model, inheritance_child_model, character_model_def
):
    """Model registry for inheritance testing."""
    return {
        "base_entity": inheritance_parent_model,
        "character_entity": inheritance_child_model,
        "character": character_model_def,
    }


@pytest.fixture
def sample_character_data():
    """Sample character data for testing."""
    return {
        "name": "Aragorn",
        "level": 5,
        "strength": 16,
        "dexterity": 14,
        "constitution": 15,
        "hit_points": 35,
    }


@pytest.fixture
def enum_model_def():
    """Model with enum validation."""
    return ModelDefinition(
        id="enum_test",
        name="Enum Test Model",
        attributes={
            "alignment": AttributeDefinition(
                type="str",
                enum=[
                    "lawful_good",
                    "chaotic_good",
                    "neutral_good",
                    "lawful_neutral",
                    "true_neutral",
                    "chaotic_neutral",
                    "lawful_evil",
                    "neutral_evil",
                    "chaotic_evil",
                ],
                default="true_neutral",
            ),
            "size": AttributeDefinition(
                type="str",
                enum=["tiny", "small", "medium", "large", "huge", "gargantuan"],
                default="medium",
            ),
        },
    )


@pytest.fixture
def pattern_model_def():
    """Model with pattern validation."""
    return ModelDefinition(
        id="pattern_test",
        name="Pattern Test Model",
        attributes={
            "email": AttributeDefinition(
                type="str",
                pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                required=True,
            ),
            "phone": AttributeDefinition(
                type="str",
                pattern=r"^\+?1?-?\.?\s?\(?(\d{3})\)?[-\.\s]?(\d{3})[-\.\s]?(\d{4})$",
                required=False,
            ),
        },
    )
