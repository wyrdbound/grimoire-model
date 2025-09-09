#!/usr/bin/env python3
"""
Performance and Integration Example for Wyrdbound Model

This example demonstrates:
- Performance considerations
- Integration patterns
- Best practices for large-scale usage
- Benchmarking model operations
"""

import time
import json
from typing import Dict, Any, List
from wyrdbound_model import (
    ModelDefinition, 
    AttributeDefinition, 
    ValidationRule,
    WyrdboundModel
)
from wyrdbound_model.core.model import create_model


def benchmark_operation(name: str, operation, iterations: int = 1000):
    """Simple benchmarking utility."""
    start_time = time.time()
    for _ in range(iterations):
        operation()
    end_time = time.time()
    total_time = end_time - start_time
    avg_time = total_time / iterations
    print(f"{name}: {total_time:.4f}s total, {avg_time:.6f}s avg ({iterations} iterations)")
    return avg_time


def create_complex_game_model():
    """Create a complex game character model for testing."""
    return ModelDefinition(
        id="game_character",
        name="Game Character",
        description="Complex game character with many derived fields",
        attributes={
            # Basic info
            "name": AttributeDefinition(type="str", required=True),
            "class": AttributeDefinition(type="str", default="warrior"),
            "race": AttributeDefinition(type="str", default="human"),
            "level": AttributeDefinition(type="int", default=1, range="1..100"),
            "experience": AttributeDefinition(type="int", default=0),
            
            # Primary stats
            "strength": AttributeDefinition(type="int", default=10, range="1..25"),
            "dexterity": AttributeDefinition(type="int", default=10, range="1..25"),
            "constitution": AttributeDefinition(type="int", default=10, range="1..25"),
            "intelligence": AttributeDefinition(type="int", default=10, range="1..25"),
            "wisdom": AttributeDefinition(type="int", default=10, range="1..25"),
            "charisma": AttributeDefinition(type="int", default=10, range="1..25"),
            
            # Secondary stats (derived)
            "health": AttributeDefinition(
                type="int", 
                derived="{{ (constitution * 5) + (level * 10) }}"
            ),
            "mana": AttributeDefinition(
                type="int", 
                derived="{{ (intelligence * 3) + (level * 5) }}"
            ),
            "stamina": AttributeDefinition(
                type="int", 
                derived="{{ (constitution * 2) + (dexterity * 2) + (level * 3) }}"
            ),
            
            # Combat stats (derived)
            "attack_bonus": AttributeDefinition(
                type="int", 
                derived="{{ (strength // 2) + (level // 4) }}"
            ),
            "defense_bonus": AttributeDefinition(
                type="int", 
                derived="{{ (dexterity // 2) + (constitution // 3) }}"
            ),
            "spell_power": AttributeDefinition(
                type="int", 
                derived="{{ (intelligence * 2) + (level // 2) }}"
            ),
            
            # Skill checks (derived)
            "physical_skills": AttributeDefinition(
                type="int", 
                derived="{{ strength + dexterity + constitution }}"
            ),
            "mental_skills": AttributeDefinition(
                type="int", 
                derived="{{ intelligence + wisdom + charisma }}"
            ),
            
            # Overall ratings (derived from derived fields)
            "combat_rating": AttributeDefinition(
                type="int", 
                derived="{{ attack_bonus + defense_bonus + (health // 10) }}"
            ),
            "total_power": AttributeDefinition(
                type="int", 
                derived="{{ combat_rating + spell_power + (mana // 5) }}"
            ),
            
            # Character summary
            "character_summary": AttributeDefinition(
                type="str",
                derived="{{ name }} the {{ class }} ({{ race }}) - Level {{ level }} | Power: {{ total_power }}"
            )
        },
        validations=[
            ValidationRule(
                expression="level >= 1 and level <= 100",
                message="Character level must be between 1 and 100"
            ),
            ValidationRule(
                expression="physical_skills + mental_skills >= 60",
                message="Total attribute points must be at least 60"
            )
        ]
    )


def main():
    print("=== Wyrdbound Model - Performance and Integration Example ===\n")
    
    # 1. Create model definition
    print("1. Creating Complex Model Definition")
    game_model = create_complex_game_model()
    
    print(f"Model has {len(game_model.attributes)} attributes")
    derived_attrs = game_model.get_derived_attributes()
    print(f"Including {len(derived_attrs)} derived attributes: {derived_attrs}")
    print()
    
    # 2. Performance benchmarks
    print("2. Performance Benchmarks")
    
    # Benchmark model creation
    def create_test_character():
        return create_model(game_model, {
            "name": "Test Character",
            "class": "mage",
            "race": "elf",
            "level": 15,
            "strength": 12,
            "dexterity": 16,
            "constitution": 14,
            "intelligence": 18,
            "wisdom": 15,
            "charisma": 13
        })
    
    print("Model Creation Performance:")
    benchmark_operation("  Regular resolver", create_test_character, 100)
    
    # Benchmark with batched resolver
    def create_test_character_batched():
        return create_model(
            game_model, 
            {
                "name": "Test Character",
                "class": "mage",
                "race": "elf",
                "level": 15,
                "strength": 12,
                "dexterity": 16,
                "constitution": 14,
                "intelligence": 18,
                "wisdom": 15,
                "charisma": 13
            },
            derived_resolver_kwargs={"batched": True}
        )
    
    benchmark_operation("  Batched resolver", create_test_character_batched, 100)
    print()
    
    # 3. Field update performance
    print("3. Field Update Performance")
    character = create_test_character()
    
    def single_update():
        character['level'] = character['level'] + 1
        if character['level'] > 50:
            character['level'] = 15  # Reset
    
    def batch_update():
        new_level = character['level'] + 1
        if new_level > 50:
            new_level = 15
        character.batch_update({
            'level': new_level,
            'strength': character['strength'] + 1 if character['strength'] < 20 else 12
        })
    
    print("Field Updates:")
    benchmark_operation("  Single field update", single_update, 1000)
    
    # Create batched character for batch testing
    batched_character = create_test_character_batched()
    
    def batch_update_batched():
        new_level = batched_character['level'] + 1
        if new_level > 50:
            new_level = 15
        batched_character.batch_update({
            'level': new_level,
            'strength': batched_character['strength'] + 1 if batched_character['strength'] < 20 else 12
        })
    
    benchmark_operation("  Batch update (batched resolver)", batch_update_batched, 1000)
    print()
    
    # 4. Memory usage and model introspection
    print("4. Model Analysis")
    character = create_test_character()
    
    print(f"Character: {character['character_summary']}")
    print(f"Memory footprint: ~{len(str(character))} characters when serialized")
    print(f"Active derived fields: {len(character._derived_field_resolver.derived_fields)}")
    
    # Show dependency analysis
    derived_resolver = character._derived_field_resolver
    print("\nDerived Field Dependencies:")
    derived_list = list(derived_attrs)
    for field_name in derived_list[:5]:  # Show first 5
        deps = derived_resolver.get_field_dependencies(field_name)
        dependents = derived_resolver.get_dependent_fields(field_name)
        print(f"  {field_name}:")
        print(f"    Depends on: {deps}")
        print(f"    Depended by: {dependents}")
    print()
    
    # 5. Integration patterns
    print("5. Integration Patterns")
    
    # Serialization pattern
    print("Serialization Example:")
    character_data = dict(character)
    json_data = json.dumps(character_data, indent=2, default=str)
    print(f"JSON size: {len(json_data)} characters")
    
    # Round-trip test
    restored_data = json.loads(json_data)
    restored_character = create_model(game_model, restored_data)
    print(f"Round-trip successful: {character['character_summary'] == restored_character['character_summary']}")
    print()
    
    # 6. Factory pattern for different character types
    print("6. Factory Pattern Example")
    
    character_templates = {
        "warrior": {
            "class": "warrior",
            "strength": 18,
            "dexterity": 12,
            "constitution": 16,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        },
        "mage": {
            "class": "mage",
            "strength": 8,
            "dexterity": 12,
            "constitution": 10,
            "intelligence": 18,
            "wisdom": 16,
            "charisma": 14
        },
        "rogue": {
            "class": "rogue",
            "strength": 12,
            "dexterity": 18,
            "constitution": 12,
            "intelligence": 14,
            "wisdom": 13,
            "charisma": 16
        }
    }
    
    def create_character_by_class(name: str, character_class: str, level: int = 1) -> WyrdboundModel:
        """Factory function to create characters by class."""
        if character_class not in character_templates:
            raise ValueError(f"Unknown character class: {character_class}")
        
        char_data = character_templates[character_class].copy()
        char_data.update({
            "name": name,
            "level": level
        })
        
        return create_model(game_model, char_data)
    
    # Create different character types
    party = [
        create_character_by_class("Thorin", "warrior", 25),
        create_character_by_class("Gandalf", "mage", 50),
        create_character_by_class("Bilbo", "rogue", 15)
    ]
    
    print("Generated Party:")
    for character in party:
        print(f"  {character['character_summary']}")
        print(f"    Combat Rating: {character['combat_rating']}, Total Power: {character['total_power']}")
    print()
    
    # 7. Best practices summary
    print("7. Best Practices Summary")
    print("✓ Use batched resolver for models with many derived fields")
    print("✓ Use batch_update() for multiple field changes")
    print("✓ Cache model definitions for reuse")
    print("✓ Use factory functions for common model patterns")
    print("✓ Serialize/deserialize through dict() conversion")
    print("✓ Monitor derived field dependencies for performance")
    print("✓ Use validation rules for data integrity")
    print("✓ Consider inheritance for related model types")


if __name__ == "__main__":
    main()
