#!/usr/bin/env python3
"""
Example: Custom Primitive Type Support

This example demonstrates the custom primitive type registry feature
that allows domain-specific primitive types to be treated as primitives
rather than complex model objects.
"""

from grimoire_model import (
    AttributeDefinition,
    ModelDefinition,
    clear_primitive_registry,
    create_model_without_validation,
    register_primitive_type,
)


def example_basic_custom_primitive():
    """Example 1: Basic custom primitive type registration."""
    print("=== Example 1: Basic Custom Primitive Type ===")
    
    # Clear any previously registered types
    clear_primitive_registry()

    # Register 'roll' as a primitive type for dice notation
    register_primitive_type("roll")

    # Define a weapon model with a custom primitive type
    weapon_def = ModelDefinition(
        id="weapon",
        name="Weapon",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "damage": AttributeDefinition(
                type="roll", required=True
            ),  # Custom primitive
        },
    )

    # Create a weapon instance
    weapon = create_model_without_validation(
        weapon_def, {"name": "Longsword", "damage": "1d8"}
    )

    print(f"Weapon: {weapon['name']}")
    print(f"Damage: {weapon['damage']}")  # Stored as-is, like a string
    print(f"Damage type: {type(weapon['damage'])}")
    print()


def example_multiple_custom_primitives():
    """Example 2: Multiple custom primitive types in a model."""
    print("=== Example 2: Multiple Custom Primitive Types ===")
    
    # Clear any previously registered types
    clear_primitive_registry()

    # Register multiple domain-specific primitive types
    register_primitive_type("roll")  # Dice notation
    register_primitive_type("duration")  # Time periods
    register_primitive_type("distance")  # Measurements

    # Define a spell model using custom primitives
    spell_def = ModelDefinition(
        id="spell",
        name="Spell",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "damage": AttributeDefinition(type="roll"),
            "duration": AttributeDefinition(type="duration"),
            "range": AttributeDefinition(type="distance"),
            "description": AttributeDefinition(
                type="str",
                derived="{{ name }} deals {{ damage }} damage, "
                "range {{ range }}, duration {{ duration }}",
            ),
        },
    )

    # Create a spell instance
    fireball = create_model_without_validation(
        spell_def,
        {
            "name": "Fireball",
            "damage": "8d6",
            "duration": "instant",
            "range": "150 feet",
        },
    )

    print(f"Spell: {fireball['name']}")
    print(f"Damage: {fireball['damage']}")
    print(f"Duration: {fireball['duration']}")
    print(f"Range: {fireball['range']}")
    print(f"Description: {fireball['description']}")
    print()


def example_with_validator():
    """Example 3: Custom primitive with validator."""
    print("=== Example 3: Custom Primitive with Validator ===")
    
    # Clear any previously registered types
    clear_primitive_registry()

    # Define a validator for dice roll notation
    def validate_dice_roll(value):
        """Validate dice roll format (e.g., '1d6', '2d10+3')."""
        if not isinstance(value, str):
            return False, "Dice roll must be a string"

        # Simple validation - just check for 'd' character
        if "d" not in value.lower():
            return False, "Dice roll must contain 'd' (e.g., '1d6')"

        return True, None

    # Register with validator
    register_primitive_type("roll", validator=validate_dice_roll)

    print("Registered 'roll' primitive type with validator")
    print(
        "Note: Validators can be used by custom validation logic "
        "(not enforced automatically)"
    )
    print()


def example_built_in_primitives_still_work():
    """Example 4: Built-in primitives work alongside custom ones."""
    print("=== Example 4: Built-in and Custom Primitives Together ===")
    
    # Clear any previously registered types
    clear_primitive_registry()

    # Register custom primitive
    register_primitive_type("roll")

    # Define a character model with both built-in and custom primitives
    character_def = ModelDefinition(
        id="character",
        name="Character",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "level": AttributeDefinition(type="int", default=1),
            "hp": AttributeDefinition(type="float", default=10.0),
            "active": AttributeDefinition(type="bool", default=True),
            "damage": AttributeDefinition(type="roll"),  # Custom primitive
            "max_hp": AttributeDefinition(
                type="float", derived="{{ level * 10.0 + hp }}"
            ),
        },
    )

    # Create character instance
    character = create_model_without_validation(
        character_def,
        {
            "name": "Aragorn",
            "level": 5,
            "hp": 50.5,
            "active": True,
            "damage": "1d8+3",
        },
    )

    print(f"Character: {character['name']}")
    print(f"Level: {character['level']} (type: {type(character['level']).__name__})")
    print(f"HP: {character['hp']} (type: {type(character['hp']).__name__})")
    print(f"Active: {character['active']} (type: {type(character['active']).__name__})")
    print(
        f"Damage: {character['damage']} (custom primitive, type: {type(character['damage']).__name__})"
    )
    print(f"Max HP: {character['max_hp']} (derived)")
    print()


def example_use_cases():
    """Example 5: Common use cases for custom primitive types."""
    print("=== Example 5: Common Use Cases ===")
    print()
    print("Custom primitive types are useful for:")
    print()
    print("1. TTRPG Systems:")
    print("   - roll: Dice notation (1d6, 2d10+3)")
    print("   - duration: Spell duration (1 minute, 1 hour, concentration)")
    print("   - distance: Range/movement (30 feet, 150 feet, touch)")
    print()
    print("2. Business Domains:")
    print("   - currency: Money values ($10.50, EUR 20)")
    print("   - percentage: Rates (15%, 0.15)")
    print("   - phone: Phone numbers (+1-555-0100)")
    print()
    print("3. Scientific Domains:")
    print("   - measurement: Values with units (5.2 kg, 10.5 m)")
    print("   - coordinate: Positions (lat/long, x/y/z)")
    print()
    print("4. Gaming:")
    print("   - score: Points (1000 points)")
    print("   - level: Progression (Level 5)")
    print("   - rarity: Item quality (legendary, epic, rare)")
    print()


def main():
    """Run all examples."""
    print("=" * 70)
    print("Custom Primitive Type Support Examples")
    print("=" * 70)
    print()

    example_basic_custom_primitive()
    example_multiple_custom_primitives()
    example_with_validator()
    example_built_in_primitives_still_work()
    example_use_cases()

    print("=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
