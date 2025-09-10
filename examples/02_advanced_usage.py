#!/usr/bin/env python3
"""
Advanced Usage Example for Wyrdbound Model

This example demonstrates advanced features including:
- Model inheritance
- Complex derived fields with dependencies
- Batch updates
- Different template resolver types
- Custom validation rules
"""

from wyrdbound_model import (
    ModelDefinition, 
    AttributeDefinition, 
    ValidationRule,
    WyrdboundModel,
    clear_registry
)
from wyrdbound_model.core.model import create_model


def main():
    print("=== Wyrdbound Model - Advanced Usage Example ===\n")
    
    # 1. Create base model definitions for inheritance
    print("1. Creating Inheritance Hierarchy")
    
    # Clear registry to start fresh
    clear_registry()
    
    # Base Entity model
    base_entity_def = ModelDefinition(
        id="base_entity",
        name="Base Entity",
        namespace="game",  # Using namespace for organization
        description="Base entity with common properties",
        attributes={
            "id": AttributeDefinition(type="str", required=True),
            "name": AttributeDefinition(type="str", required=True),
            "description": AttributeDefinition(type="str", default=""),
            "created_at": AttributeDefinition(type="str", default="2024-01-01"),
            "tags": AttributeDefinition(type="list", default=[])
        }
    )
    
    # Character model inheriting from base entity
    character_def = ModelDefinition(
        id="character",
        name="Character",
        namespace="game",  # Same namespace for easy reference
        description="RPG character extending base entity",
        extends=["base_entity"],
        attributes={
            # Core stats
            "level": AttributeDefinition(type="int", default=1, range="1..100"),
            "experience": AttributeDefinition(type="int", default=0),
            "strength": AttributeDefinition(type="int", default=10, range="1..20"),
            "dexterity": AttributeDefinition(type="int", default=10, range="1..20"),
            "intelligence": AttributeDefinition(type="int", default=10, range="1..20"),
            
            # Resources
            "health": AttributeDefinition(type="int", default=100),
            "mana": AttributeDefinition(type="int", default=50),
            
            # Equipment
            "equipment": AttributeDefinition(type="dict", default={}),
            
            # Derived fields with complex dependencies
            "stat_total": AttributeDefinition(
                type="int",
                derived="{{ strength + dexterity + intelligence }}"
            ),
            "health_bonus": AttributeDefinition(
                type="int", 
                derived="{{ (level - 1) * 5 + strength * 2 }}"
            ),
            "max_health": AttributeDefinition(
                type="int", 
                derived="{{ health + health_bonus }}"
            ),
            "mana_bonus": AttributeDefinition(
                type="int", 
                derived="{{ (level - 1) * 3 + intelligence * 3 }}"
            ),
            "max_mana": AttributeDefinition(
                type="int", 
                derived="{{ mana + mana_bonus }}"
            ),
            "combat_rating": AttributeDefinition(
                type="int", 
                derived="{{ (strength * 2 + dexterity + level) // 2 }}"
            ),
            "character_sheet": AttributeDefinition(
                type="str",
                derived="{{ name }} (Lvl {{ level }}): STR {{ strength }}, DEX {{ dexterity }}, INT {{ intelligence }} | HP: {{ max_health }}, MP: {{ max_mana }}"
            )
        },
        validations=[
            ValidationRule(
                expression="level >= 1",
                message="Character level must be at least 1"
            ),
            ValidationRule(
                expression="experience >= 0",
                message="Experience cannot be negative"
            ),
            ValidationRule(
                expression="stat_total >= 30",
                message="Total stats must be at least 30"
            )
        ]
    )
    
    # Weapon model
    weapon_def = ModelDefinition(
        id="weapon",
        name="Weapon",
        namespace="game",  # All models in same namespace
        description="Weapon item",
        extends=["base_entity"],
        attributes={
            "damage": AttributeDefinition(type="int", default=1, range="1..50"),
            "weapon_type": AttributeDefinition(type="str", default="sword"),
            "rarity": AttributeDefinition(type="str", default="common"),
            
            # Derived weapon properties
            "damage_rating": AttributeDefinition(
                type="str",
                derived="{% if damage >= 20 %}Devastating{% elif damage >= 15 %}High{% elif damage >= 10 %}Moderate{% else %}Low{% endif %}"
            ),
            "weapon_summary": AttributeDefinition(
                type="str",
                derived="{{ name }} ({{ weapon_type }}) - {{ damage }} damage ({{ damage_rating }})"
            )
        }
    )
    
    # 2. Models automatically registered with namespace "game"
    print("2. Models Auto-Registered")
    print("   Models are automatically registered in the 'game' namespace")
    print("   This enables inheritance resolution without manual registry management")
    
    # 3. Create instances with inheritance
    print("3. Creating Instances with Inheritance")
    
    # Create a character using inheritance
    character = create_model(
        character_def,
        {
            "id": "char_001",
            "name": "Thorin Oakenshield",
            "description": "Dwarf warrior king",
            "level": 25,
            "strength": 18,
            "dexterity": 14,
            "intelligence": 12,
            "experience": 15000,
            "tags": ["dwarf", "king", "warrior"]
        }
    )
    
    print("Character created with inheritance:")
    print(f"  ID: {character['id']} (from base_entity)")
    print(f"  Name: {character['name']} (from base_entity)")
    print(f"  Description: {character['description']} (from base_entity)")
    print(f"  Level: {character['level']} (from character)")
    print(f"  Stats: STR {character['strength']}, DEX {character['dexterity']}, INT {character['intelligence']}")
    print(f"  Stat Total: {character['stat_total']} (derived)")
    print(f"  Max Health: {character['max_health']} (derived from multiple fields)")
    print(f"  Max Mana: {character['max_mana']} (derived from multiple fields)")
    print(f"  Combat Rating: {character['combat_rating']} (derived)")
    print(f"  Full Sheet: {character['character_sheet']}")
    print()
    
    # Create weapons
    excalibur = create_model(
        weapon_def,
        {
            "id": "weapon_001",
            "name": "Excalibur",
            "description": "Legendary sword of kings",
            "damage": 25,
            "weapon_type": "sword",
            "rarity": "legendary"
        }
    )
    
    print("Weapon created:")
    print(f"  Summary: {excalibur['weapon_summary']}")
    print(f"  Damage Rating: {excalibur['damage_rating']}")
    print()
    
    # 4. Demonstrate batch updates
    print("4. Batch Update Example")
    print("Before level up:")
    print(f"  Level: {character['level']}")
    print(f"  Max Health: {character['max_health']}")
    print(f"  Max Mana: {character['max_mana']}")
    print(f"  Combat Rating: {character['combat_rating']}")
    
    # Use batch updates for better performance
    character.batch_update({
        'level': 30,  # Level up
        'strength': 20,  # Max strength
        'intelligence': 15,  # Increase intelligence
        'experience': 25000  # More experience
    })
    
    print("\nAfter batch level up:")
    print(f"  Level: {character['level']}")
    print(f"  Max Health: {character['max_health']} (auto-updated)")
    print(f"  Max Mana: {character['max_mana']} (auto-updated)")
    print(f"  Combat Rating: {character['combat_rating']} (auto-updated)")
    print(f"  Updated Sheet: {character['character_sheet']}")
    print()
    
    # 5. Alternative template resolver
    print("5. Using Model Context Template Resolver")
    
    # Create a model with model_context resolver for different syntax
    alternative_char_def = ModelDefinition(
        id="alt_character",
        name="Alternative Character",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "level": AttributeDefinition(type="int", default=1),
            "power": AttributeDefinition(type="int", default=10),
            
            # Using different template syntax
            "display_name": AttributeDefinition(
                type="str",
                derived="$name (Level $level)"
            ),
            "power_level": AttributeDefinition(
                type="str", 
                derived="Power: $power"
            )
        }
    )
    
    alt_character = create_model(
        alternative_char_def,
        {
            "name": "Gandalf",
            "level": 50,
            "power": 95
        },
        template_resolver_type="model_context"
    )
    
    print("Character with model_context resolver:")
    print(f"  Display Name: {alt_character['display_name']}")
    print(f"  Power Level: {alt_character['power_level']}")
    print()
    
    # 6. Complex validation example
    print("6. Complex Validation Examples")
    
    # This should pass validation
    try:
        valid_character = create_model(
            character_def,
            {
                "id": "char_002",
                "name": "Valid Character",
                "level": 10,
                "strength": 15,
                "dexterity": 12,
                "intelligence": 8,  # Total stats = 35, which is >= 30
                "experience": 5000
            }
        )
        print(f"✓ Valid character created: {valid_character['name']}")
        print(f"  Stat total: {valid_character['stat_total']} (passes validation)")
    except Exception as e:
        print(f"✗ Unexpected validation error: {e}")
    
    # This should fail validation
    try:
        invalid_character = create_model(
            character_def,
            {
                "id": "char_003",
                "name": "Invalid Character",
                "level": 10,
                "strength": 5,
                "dexterity": 5,
                "intelligence": 5,  # Total stats = 15, which is < 30
                "experience": 5000
            }
        )
        print(f"✗ Invalid character should not have been created: {invalid_character['name']}")
    except Exception as e:
        print(f"✓ Expected validation error: {e}")
    
    print()
    
    # 7. Working with nested data
    print("7. Working with Nested Equipment Data")
    
    # Add equipment to character
    character['equipment'] = {
        "weapon": {
            "name": "Orcrist", 
            "damage": 15,
            "type": "sword"
        },
        "armor": {
            "name": "Mithril Shirt",
            "defense": 20,
            "type": "chainmail"
        },
        "accessories": [
            {"name": "Ring of Power", "effect": "+5 to all stats"},
            {"name": "Cloak of Elvenkind", "effect": "Stealth bonus"}
        ]
    }

    print("Equipment added:")
    print(f"  Weapon: {character['equipment']['weapon']['name']}")
    print(f"  Armor: {character['equipment']['armor']['name']}")
    print(f"  Accessories: {len(character['equipment']['accessories'])} items")
    
    # Access nested data
    weapon_damage = character.get("equipment.weapon.damage", 0)
    armor_defense = character.get("equipment.armor.defense", 0)
    print(f"  Weapon damage: {weapon_damage}")
    print(f"  Armor defense: {armor_defense}")
    
    # 8. Inheritance Polymorphism Example
    print("\n8. Inheritance Polymorphism: Weapon as Item")
    
    # Create a deeper inheritance chain: base_entity -> item -> weapon
    item_def = ModelDefinition(
        id="item",
        name="Item",
        namespace="game",  # Same namespace for inheritance resolution
        description="Base item type that extends entity",
        extends=["base_entity"],
        attributes={
            "weight": AttributeDefinition(type="float", default=1.0, range="0.1..100.0"),
            "value": AttributeDefinition(type="int", default=1, range="1..10000"),
            "durability": AttributeDefinition(type="int", default=100, range="0..100"),
            "stackable": AttributeDefinition(type="bool", default=False),
            
            # Derived item properties
            "value_per_weight": AttributeDefinition(
                type="float",
                derived="{{ value / weight }}"
            ),
            "condition": AttributeDefinition(
                type="str", 
                derived="{% if durability >= 80 %}Excellent{% elif durability >= 60 %}Good{% elif durability >= 40 %}Fair{% elif durability >= 20 %}Poor{% else %}Broken{% endif %}"
            )
        },
        validations=[
            ValidationRule(
                expression="weight > 0",
                message="Item weight must be positive"
            ),
            ValidationRule(
                expression="value > 0", 
                message="Item value must be positive"
            )
        ]
    )
    
    # Enhanced weapon definition extending item (not base_entity directly)
    enhanced_weapon_def = ModelDefinition(
        id="enhanced_weapon",
        name="Enhanced Weapon",
        namespace="game",  # Same namespace for inheritance resolution
        description="Weapon that extends item",
        extends=["item"],  # Now extends item instead of base_entity
        attributes={
            "damage": AttributeDefinition(type="int", default=1, range="1..50"),
            "weapon_type": AttributeDefinition(type="str", default="sword"),
            "attack_speed": AttributeDefinition(type="float", default=1.0, range="0.5..3.0"),
            "critical_chance": AttributeDefinition(type="float", default=0.05, range="0.0..1.0"),
            
            # Weapon-specific derived properties
            "dps": AttributeDefinition(
                type="float",
                derived="{{ damage * attack_speed }}"
            ),
            "damage_rating": AttributeDefinition(
                type="str",
                derived="{% if damage >= 20 %}Legendary{% elif damage >= 15 %}Epic{% elif damage >= 10 %}Rare{% else %}Common{% endif %}"
            ),
            "weapon_summary": AttributeDefinition(
                type="str",
                derived="{{ name }} ({{ weapon_type }}) - {{ damage }} dmg, {{ dps }} DPS ({{ damage_rating }})"
            )
        },
        validations=[
            ValidationRule(
                expression="damage > 0",
                message="Weapon damage must be positive"
            ),
            ValidationRule(
                expression="attack_speed > 0",
                message="Attack speed must be positive"
            )
        ]
    )
    
    # All models automatically registered in "game" namespace for inheritance resolution
    print("Created inheritance chain: base_entity -> item -> enhanced_weapon")
    print("  All models auto-registered in 'game' namespace")
    
    # Create a weapon instance with full weapon data
    print("\nCreating a weapon...")
    excalibur = create_model(
        enhanced_weapon_def,
        {
            # base_entity fields
            "id": "excalibur_001", 
            "name": "Excalibur",
            "description": "The legendary sword of King Arthur",
            "tags": ["legendary", "sword", "artifact"],
            
            # item fields  
            "weight": 3.5,
            "value": 10000,
            "durability": 95,
            "stackable": False,
            
            # weapon fields
            "damage": 25,
            "weapon_type": "sword", 
            "attack_speed": 1.2,
            "critical_chance": 0.15
        }
    )
    
    print(f"Weapon created: {excalibur['weapon_summary']}")
    print(f"  Entity ID: {excalibur['id']} (from base_entity)")
    print(f"  Item value: {excalibur['value']} gold, weight: {excalibur['weight']} lbs (from item)")
    print(f"  Item condition: {excalibur['condition']} (derived from item)")
    print(f"  Weapon DPS: {excalibur['dps']} (derived from weapon)")
    
    # Now demonstrate polymorphism: treat weapon as an item
    print("\nPolymorphism: Treating weapon as item...")
    
    def process_item_inventory(item_data, item_model_def):
        """Function that expects an item but can handle any item subtype."""
        # Create item instance from the data - this validates as an item
        item_instance = create_model(item_model_def, item_data)
        
        print(f"  Processing item: {item_instance['name']}")
        print(f"    Value per weight: {item_instance['value_per_weight']:.2f} gold/lb")
        print(f"    Condition: {item_instance['condition']}")
        print(f"    Validation passed as item: ✓")
        
        return item_instance
    
    # Extract just the raw data from our weapon
    weapon_raw_data = dict(excalibur)
    print(f"  Raw weapon data has {len(weapon_raw_data)} fields: {list(weapon_raw_data.keys())}")
    
    # Process it as an item (polymorphism in action)
    item_view = process_item_inventory(weapon_raw_data, item_def)
    
    # The item view has item properties but the underlying data retains weapon info
    print(f"  Item view shows: {item_view['name']} worth {item_view['value']} gold")
    print(f"  But raw data still contains weapon info: damage={weapon_raw_data.get('damage', 'N/A')}")
    
    # Convert back to weapon - all weapon features are preserved!
    print("\nConverting back to weapon...")
    restored_weapon = create_model(enhanced_weapon_def, weapon_raw_data)
    
    print(f"Restored weapon: {restored_weapon['weapon_summary']}")
    print(f"  All weapon features preserved: damage={restored_weapon['damage']}, DPS={restored_weapon['dps']}")
    print(f"  All item features preserved: value={restored_weapon['value']}, condition={restored_weapon['condition']}")
    print(f"  All entity features preserved: ID={restored_weapon['id']}, tags={restored_weapon['tags']}")
    
    # Demonstrate that validation works at each level
    print("\nValidation works at each inheritance level:")
    try:
        # This should fail item validation (negative weight)
        create_model(item_def, {
            "id": "bad_item",
            "name": "Bad Item", 
            "weight": -1.0,  # Invalid!
            "value": 100
        })
    except Exception as e:
        print(f"  ✓ Item validation caught negative weight: {str(e).split('|')[1].split(']')[0]}]")
    
    try:
        # This should fail weapon validation (negative damage)
        create_model(enhanced_weapon_def, {
            "id": "bad_weapon",
            "name": "Bad Weapon",
            "weight": 2.0,
            "value": 100, 
            "damage": -5  # Invalid!
        })
    except Exception as e:
        print(f"  ✓ Weapon validation caught negative damage: {str(e).split('|')[1].split(']')[0]}]")
    
    print("\n✓ Inheritance polymorphism working perfectly!")
    print("  - Weapon can be treated as item in item contexts")
    print("  - All weapon-specific data is preserved in the underlying dict")
    print("  - Can convert back to weapon with full functionality")
    print("  - Validation works appropriately at each inheritance level")


if __name__ == "__main__":
    main()
