#!/usr/bin/env python3
"""Minimal test case reproducing nested model instantiation issue."""

from grimoire_model import ModelDefinition, AttributeDefinition, create_model, clear_registry


def test_nested_model_issue():
    """Test case showing nested model instantiation issue."""
    clear_registry()
    
    # Level 3: Deepest nested model (stat with derived bonus)
    stat_def = ModelDefinition(
        id="stat",
        name="Stat",
        namespace="test",
        attributes={
            "value": AttributeDefinition(type="int", required=True),
            "bonus": AttributeDefinition(
                type="int",
                derived="{{ (value - 10) // 2 }}"  # D&D style ability modifier
            )
        }
    )
    
    # Level 2: Ability set containing multiple stats
    abilities_def = ModelDefinition(
        id="abilities",
        name="Abilities",
        namespace="test",
        attributes={
            "strength": AttributeDefinition(type="stat", required=False),
            "constitution": AttributeDefinition(type="stat", required=False),
            "dexterity": AttributeDefinition(type="stat", required=False)
        }
    )
    
    # Level 1: Character containing abilities (uses derived field from deep nesting)
    character_def = ModelDefinition(
        id="character",
        name="Character",
        namespace="test",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "abilities": AttributeDefinition(type="abilities", required=False),
            # This should access abilities.constitution.bonus (3 levels deep!)
            "hit_points": AttributeDefinition(
                type="int",
                derived="{{ 10 + abilities.constitution.bonus }}"
            )
        }
    )

    # Test: Individual stat works fine
    stat = create_model(stat_def, {"value": 14})
    print(f"Individual stat bonus: {stat['bonus']}")  # Works: 2
    
    # Test: Nested stats don't work
    abilities = create_model(abilities_def, {
        "constitution": {"value": 14}
    })
    print(f"Constitution type: {type(abilities['constitution'])}")  # <class 'dict'>
    print(f"Constitution keys: {list(abilities['constitution'].keys())}")  # ['value']
    # abilities['constitution']['bonus'] would raise KeyError!
    
    # Test: Deep nesting fails completely
    character_data = {
        "name": "Test Hero",
        "abilities": {"constitution": {"value": 14}}
    }
    
    try:
        character = create_model(character_def, character_data)
        print(f"Character hit_points: {character['hit_points']}")
        # This will fail with template resolution error
    except Exception as e:
        print(f"Error: {e}")
        # TemplateResolutionError: 'dict object' has no attribute 'bonus'


if __name__ == "__main__":
    test_nested_model_issue()
