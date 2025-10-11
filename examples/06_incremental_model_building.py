#!/usr/bin/env python3
"""
Incremental Model Building Example for Grimoire Model

This example demonstrates the create_model_without_validation() feature,
which allows building complex objects step-by-step without immediate validation.

Use cases:
- Workflow systems (e.g., tabletop RPG character creation)
- Form builders and UI applications
- Data migration and import
- Testing scenarios
"""

from grimoire_model import (
    ModelDefinition,
    ValidationRule,
    create_model,
    create_model_without_validation,
)


def example_1_basic_incremental_building():
    """Example 1: Basic incremental building."""
    print("\n=== Example 1: Basic Incremental Building ===\n")

    # Define a character model with required fields
    character_def = ModelDefinition(
        id="character",
        name="Character",
        attributes={
            "name": {"type": "str", "required": True},
            "level": {"type": "int", "required": True},
            "class": {"type": "str", "required": True},
        },
    )

    # Traditional approach would fail with missing required fields:
    # character = create_model(character_def, {"name": "Hero"})  # ERROR!

    # With create_model_without_validation, we can build incrementally:
    character = create_model_without_validation(character_def, {"name": "Hero"})
    print(f"Step 1 - Created with name: {character['name']}")

    # Add fields incrementally
    character["level"] = 5
    print(f"Step 2 - Added level: {character['level']}")

    character["class"] = "warrior"
    print(f"Step 3 - Added class: {character['class']}")

    # Validate when ready
    errors = character.validate()
    if not errors:
        print("✓ Character is now valid!")
        print(f"  Final character: {dict(character)}")
    else:
        print(f"✗ Validation errors: {errors}")


def example_2_workflow_system():
    """Example 2: Workflow-based character creation system."""
    print("\n=== Example 2: Workflow System (RPG Character Creation) ===\n")

    # Define a comprehensive character model
    character_def = ModelDefinition(
        id="rpg_character",
        name="RPG Character",
        attributes={
            "name": {"type": "str", "required": True},
            "gender": {"type": "str", "required": True},
            "race": {"type": "str", "required": True},
            "class": {"type": "str", "required": True},
            "level": {"type": "int", "required": True, "default": 1},
            "strength": {"type": "int", "required": True, "range": "3..18"},
            "dexterity": {"type": "int", "required": True, "range": "3..18"},
            "constitution": {"type": "int", "required": True, "range": "3..18"},
            "intelligence": {"type": "int", "required": True, "range": "3..18"},
            "wisdom": {"type": "int", "required": True, "range": "3..18"},
            "charisma": {"type": "int", "required": True, "range": "3..18"},
            # Derived fields
            "hp": {"type": "int", "derived": "{{ level * constitution }}"},
            "stat_total": {
                "type": "int",
                "derived": "{{ strength + dexterity + constitution + "
                "intelligence + wisdom + charisma }}",
            },
        },
    )

    # Simulate a step-by-step character creation workflow
    def workflow_step_1_basic_info():
        """Step 1: Gather basic information."""
        character = create_model_without_validation(character_def, {})
        character["name"] = "Aragorn"
        character["gender"] = "male"
        print("Step 1: Basic info set")
        return character

    def workflow_step_2_choose_race(character):
        """Step 2: Choose race."""
        character["race"] = "human"
        print("Step 2: Race chosen")
        return character

    def workflow_step_3_roll_abilities(character):
        """Step 3: Roll ability scores."""
        character["strength"] = 16
        character["dexterity"] = 14
        character["constitution"] = 15
        character["intelligence"] = 12
        character["wisdom"] = 13
        character["charisma"] = 15
        print("Step 3: Abilities rolled")
        # HP is automatically computed when constitution is set!
        print(f"  Computed HP: {character['hp']}")
        return character

    def workflow_step_4_choose_class(character):
        """Step 4: Choose character class."""
        character["class"] = "ranger"
        print("Step 4: Class chosen")
        return character

    def workflow_step_5_finalize(character):
        """Step 5: Final validation."""
        errors = character.validate()
        if not errors:
            print("✓ Character creation complete!")
            print(f"  Final character: {character['name']}, Level {character['level']}")
            print(f"  Race: {character['race']}, Class: {character['class']}")
            print(f"  HP: {character['hp']}, Total Stats: {character['stat_total']}")
        else:
            print(f"✗ Validation errors: {errors}")
        return character

    # Execute the workflow
    char = workflow_step_1_basic_info()
    char = workflow_step_2_choose_race(char)
    char = workflow_step_3_roll_abilities(char)
    char = workflow_step_4_choose_class(char)
    char = workflow_step_5_finalize(char)


def example_3_derived_fields_with_partial_data():
    """Example 3: Derived fields work with partial data."""
    print("\n=== Example 3: Derived Fields with Partial Data ===\n")

    model_def = ModelDefinition(
        id="computed_model",
        name="Computed Model",
        attributes={
            "base_value": {"type": "int", "required": True},
            "multiplier": {"type": "int", "required": True},
            "bonus": {"type": "int", "default": 0},
            # This derived field depends on base_value and multiplier
            "computed": {
                "type": "int",
                "derived": "{{ base_value * multiplier + bonus }}",
            },
        },
    )

    # Create with only partial data
    model = create_model_without_validation(model_def, {"base_value": 10})
    print(f"Created with base_value: {model['base_value']}")
    print(f"Bonus applied from default: {model['bonus']}")
    print("Note: 'computed' is not yet calculated (missing multiplier)")

    # Add the missing field
    model["multiplier"] = 5
    print(f"\nAdded multiplier: {model['multiplier']}")
    print(f"Computed field now available: {model['computed']}")

    # Validate
    errors = model.validate()
    print(f"Validation: {'✓ Valid' if not errors else f'✗ Errors: {errors}'}")


def example_4_validation_rules():
    """Example 4: Validation rules are checked only when validate() is called."""
    print("\n=== Example 4: Validation Rules ===\n")

    model_def = ModelDefinition(
        id="constrained_model",
        name="Constrained Model",
        attributes={
            "strength": {"type": "int", "required": True},
            "dexterity": {"type": "int", "required": True},
            "intelligence": {"type": "int", "required": True},
            "stat_total": {
                "type": "int",
                "derived": "{{ strength + dexterity + intelligence }}",
            },
        },
        validations=[
            ValidationRule(
                expression="stat_total >= 30",
                message="Total stats must be at least 30",
            )
        ],
    )

    # Create with stats that would fail validation
    character = create_model_without_validation(
        model_def, {"strength": 8, "dexterity": 8, "intelligence": 8}
    )
    print(
        f"Created character with stats: STR={character['strength']}, "
        f"DEX={character['dexterity']}, INT={character['intelligence']}"
    )
    print(f"Total stats: {character['stat_total']}")

    # Validation fails
    errors = character.validate()
    print(f"Validation: {errors}")

    # Fix the stats
    print("\nIncreasing strength to 14...")
    character["strength"] = 14
    print(f"New total stats: {character['stat_total']}")

    # Validation now passes
    errors = character.validate()
    print(f"Validation: {'✓ Valid' if not errors else f'✗ Errors: {errors}'}")


def example_5_form_builder_pattern():
    """Example 5: Form builder pattern."""
    print("\n=== Example 5: Form Builder Pattern ===\n")

    user_def = ModelDefinition(
        id="user_registration",
        name="User Registration",
        attributes={
            "username": {"type": "str", "required": True},
            "email": {
                "type": "str",
                "required": True,
                "pattern": r"^[\w\.-]+@[\w\.-]+\.\w+$",
            },
            "password": {"type": "str", "required": True},
            "age": {"type": "int", "required": True, "range": "18..120"},
            "terms_accepted": {"type": "bool", "required": True},
        },
    )

    # Simulate a multi-step form
    print("Form Step 1: Account Info")
    user = create_model_without_validation(user_def, {})
    user["username"] = "aragorn_ranger"
    user["email"] = "aragorn@gondor.me"
    print(f"  Username: {user['username']}")
    print(f"  Email: {user['email']}")

    print("\nForm Step 2: Password")
    user["password"] = "super_secret_123"
    print("  Password set (hidden)")

    print("\nForm Step 3: Additional Info")
    user["age"] = 87
    user["terms_accepted"] = True
    print(f"  Age: {user['age']}")
    print(f"  Terms accepted: {user['terms_accepted']}")

    # Validate on form submission
    print("\nSubmitting form...")
    errors = user.validate()
    if not errors:
        print("✓ Registration successful!")
        print(f"  Welcome, {user['username']}!")
    else:
        print(f"✗ Registration failed: {errors}")


def example_6_testing_scenario():
    """Example 6: Using in tests with minimal data."""
    print("\n=== Example 6: Testing Scenario ===\n")

    # Define a complex model
    product_def = ModelDefinition(
        id="product",
        name="Product",
        attributes={
            "sku": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "price": {"type": "float", "required": True},
            "quantity": {"type": "int", "required": True},
            "category": {"type": "str", "required": True},
            "total_value": {"type": "float", "derived": "{{ price * quantity }}"},
        },
    )

    # In tests, we often only care about specific fields
    print("Test: Verify total_value calculation")
    test_product = create_model_without_validation(
        product_def, {"price": 10.0, "quantity": 5}
    )
    assert test_product["total_value"] == 50.0
    print("  ✓ Test passed: total_value correctly calculated")

    print("\nTest: Verify price validation")
    test_product2 = create_model_without_validation(product_def, {"price": -5.0})
    # We can test individual fields without needing all required fields
    print(f"  Created test product with price: {test_product2['price']}")
    print("  ✓ Test setup successful with minimal data")


def example_7_comparison_with_traditional():
    """Example 7: Comparison with traditional create_model."""
    print("\n=== Example 7: Comparison with Traditional Approach ===\n")

    character_def = ModelDefinition(
        id="character_comparison",
        name="Character",
        attributes={
            "name": {"type": "str", "required": True},
            "level": {"type": "int", "required": True},
        },
    )

    # Traditional approach - must have all required fields
    print("Traditional approach (create_model):")
    try:
        char1 = create_model(character_def, {"name": "Hero"})
        print("  Created successfully")
    except Exception as e:
        print(f"  ✗ Failed: {type(e).__name__}: {e}")

    # Must provide all required fields upfront
    char1 = create_model(character_def, {"name": "Hero", "level": 5})
    print(f"  ✓ Created with all fields: {dict(char1)}")

    # New approach - incremental building
    print("\nNew approach (create_model_without_validation):")
    char2 = create_model_without_validation(character_def, {"name": "Hero"})
    print(f"  ✓ Created with partial data: {dict(char2)}")
    char2["level"] = 5
    print(f"  ✓ Added missing field: {dict(char2)}")
    errors = char2.validate()
    print(f"  ✓ Validated: {'Valid' if not errors else f'Errors: {errors}'}")


def main():
    """Run all examples."""
    print("=" * 70)
    print("GRIMOIRE MODEL: Incremental Model Building Examples")
    print("=" * 70)

    example_1_basic_incremental_building()
    example_2_workflow_system()
    example_3_derived_fields_with_partial_data()
    example_4_validation_rules()
    example_5_form_builder_pattern()
    example_6_testing_scenario()
    example_7_comparison_with_traditional()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
