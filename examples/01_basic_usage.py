#!/usr/bin/env python3
"""
Basic Usage Example for Grimoire Model

This example demonstrates the fundamental features of the grimoire-model package:
- Creating model definitions
- Instantiating models with validation
- Working with derived fields
- Using the factory function
"""

from grimoire_model import (
    AttributeDefinition,
    GrimoireModel,
    ModelDefinition,
    ValidationRule,
    get_model,
)
from grimoire_model.core.model import create_model


def main():
    print("=== Grimoire Model - Basic Usage Example ===\n")

    # 1. Define a simple character model
    print("1. Creating a Character Model Definition")
    character_def = ModelDefinition(
        id="character",
        name="Character",
        namespace="rpg",  # Organize models in namespaces
        description="A basic RPG character",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "level": AttributeDefinition(type="int", default=1, range="1..100"),
            "health": AttributeDefinition(type="int", default=100),
            "mana": AttributeDefinition(type="int", default=50),
            # Derived fields using templates
            "total_resources": AttributeDefinition(
                type="int", derived="{{ health + mana }}"
            ),
            "is_powerful": AttributeDefinition(
                type="bool", derived="{{ level >= 10 }}"
            ),
            "character_summary": AttributeDefinition(
                type="str",
                derived="Level {{ level }} {{ name }} ({{ total_resources }} total resources)",
            ),
        },
        validations=[
            ValidationRule(
                expression="health > 0", message="Character must have positive health"
            ),
            ValidationRule(
                expression="mana >= 0", message="Character cannot have negative mana"
            ),
        ],
    )

    print(f"Model ID: {character_def.id}")
    print(f"Required attributes: {character_def.get_required_attributes()}")
    print(f"Derived attributes: {character_def.get_derived_attributes()}\n")

    # 2. Create a character using the model definition
    print("2. Creating Character Instances")

    # Using the constructor directly
    character1 = GrimoireModel(
        character_def, {"name": "Aragorn", "level": 15, "health": 120, "mana": 80}
    )

    print(f"Character 1: {character1['name']}")
    print(f"  Level: {character1['level']}")
    print(f"  Health: {character1['health']}")
    print(f"  Mana: {character1['mana']}")
    print(f"  Total Resources: {character1['total_resources']} (derived)")
    print(f"  Is Powerful: {character1['is_powerful']} (derived)")
    print(f"  Summary: {character1['character_summary']} (derived)")
    print()

    # 3. Using the factory function
    print("3. Using Factory Function")
    character2 = create_model(
        character_def, {"name": "Legolas", "level": 8, "health": 90, "mana": 110}
    )

    print(f"Character 2: {character2['name']}")
    print(f"  Summary: {character2['character_summary']}")
    print(f"  Is Powerful: {character2['is_powerful']}")
    print()

    # 4. Demonstrate mutable dict-like interface
    print("4. Dict-like Operations")
    print(f"Before level up - Level: {character2['level']}")
    character2["level"] = 12  # Level up!
    character2["health"] = 95  # Slight health increase

    print(f"After level up - Level: {character2['level']}")
    print(f"  Is Powerful: {character2['is_powerful']} (automatically updated)")
    print(f"  New Summary: {character2['character_summary']} (automatically updated)")
    print()

    # 5. Working with defaults
    print("5. Using Default Values")
    character3 = create_model(character_def, {"name": "Gimli"})
    print(f"Character 3 with defaults: {character3['name']}")
    print(f"  Level: {character3['level']} (default)")
    print(f"  Health: {character3['health']} (default)")
    print(f"  Mana: {character3['mana']} (default)")
    print(f"  Total Resources: {character3['total_resources']} (derived from defaults)")
    print()

    # 6. Demonstrate validation
    print("6. Validation Examples")
    try:
        invalid_character = create_model(
            character_def,
            {
                "name": "Invalid",
                "health": -10,  # This should fail validation
            },
        )
    except Exception as e:
        print(f"Validation error (expected): {e}")

    try:
        no_name_character = create_model(
            character_def,
            {
                "level": 5  # Missing required 'name' field
            },
        )
    except Exception as e:
        print(f"Required field error (expected): {e}")

    print()

    # 7. Model introspection
    print("7. Model Introspection")
    print(f"Model definition ID: {character1.model_definition.id}")
    print(f"Available keys: {list(character1.keys())}")
    print(f"Model data as dict: {dict(character1)}")
    print(f"Character 1 == Character 1: {character1 == character1}")
    print(f"Character 1 == Character 2: {character1 == character2}")
    print()

    # 8. Demonstrate global registry and namespaces
    print("8. Global Registry and Namespaces")
    print("Models are automatically registered when created with namespaces!")

    # Retrieve model from global registry
    retrieved_model = get_model("rpg", "character")
    if retrieved_model:
        print(f"Retrieved from registry: {retrieved_model.name}")
        print(f"Same model definition: {retrieved_model is character_def}")

        # Show that you can now reference models across your application
        another_character = create_model(
            retrieved_model, {"name": "Boromir", "level": 10}
        )
        print(f"Created using retrieved model: {another_character['name']}")
        print(f"Summary: {another_character['character_summary']}")
    else:
        print("Model not found in registry (this shouldn't happen!)")


if __name__ == "__main__":
    main()
