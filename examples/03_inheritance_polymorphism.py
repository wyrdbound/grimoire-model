#!/usr/bin/env python3
"""
Inheritance Polymorphism Example for Grimoire Model

This example demonstrates advanced inheritance and polymorphism features:
- Multi-level inheritance chains (base_entity → item → weapon)
- Polymorphic behavior where subclasses can be treated as parent types
- Converting between inheritance levels while preserving data
- Validation at different inheritance levels
"""

from grimoire_model import (
    AttributeDefinition,
    ModelDefinition,
    ValidationRule,
    clear_registry,
)
from grimoire_model.core.model import create_model


def main():
    print("=== Grimoire Model - Inheritance Polymorphism Example ===\n")

    # 1. Create inheritance chain: base_entity → item → weapon
    print("1. Creating Multi-Level Inheritance Chain")

    # Clear registry for clean start
    clear_registry()

    # Base Entity model (root of hierarchy)
    base_entity_def = ModelDefinition(
        id="base_entity",
        name="Base Entity",
        namespace="demo",  # Using demo namespace
        description="Base entity with common properties",
        attributes={
            "id": AttributeDefinition(type="str"),
            "name": AttributeDefinition(type="str"),
            "description": AttributeDefinition(type="str", default=""),
            "created_at": AttributeDefinition(type="str", default="2024-01-01"),
        },
    )

    # Item model extending base_entity
    item_def = ModelDefinition(
        id="item",
        name="Item",
        namespace="demo",  # Same namespace for inheritance
        description="Generic item extending base entity",
        extends=["base_entity"],
        attributes={
            # Item-specific attributes
            "value": AttributeDefinition(type="int", default=0, range="0..10000"),
            "weight": AttributeDefinition(type="float", default=1.0),
            "rarity": AttributeDefinition(
                type="str",
                default="common",
                enum=["common", "uncommon", "rare", "epic", "legendary"],
            ),
            "stackable": AttributeDefinition(type="bool", default=False),
            # Derived fields for items
            "value_per_weight": AttributeDefinition(
                type="float", derived="{{ value / weight if weight > 0 else 0 }}"
            ),
            "item_summary": AttributeDefinition(
                type="str",
                derived="{{ name }} ({{ rarity }}): {{ value }}gp, {{ weight }}kg",
            ),
        },
        validations=[
            ValidationRule(
                expression="value >= 0", message="Item value cannot be negative"
            ),
            ValidationRule(
                expression="weight > 0", message="Item weight must be positive"
            ),
        ],
    )

    # Weapon model extending item
    weapon_def = ModelDefinition(
        id="weapon",
        name="Weapon",
        namespace="demo",  # Same namespace for inheritance
        description="Weapon extending item",
        extends=["item"],
        attributes={
            # Weapon-specific attributes
            "damage": AttributeDefinition(type="int", default=1, range="1..50"),
            "damage_type": AttributeDefinition(
                type="str",
                default="slashing",
                enum=[
                    "slashing",
                    "piercing",
                    "bludgeoning",
                    "fire",
                    "ice",
                    "lightning",
                ],
            ),
            "critical_chance": AttributeDefinition(
                type="float", default=0.05, range="0.0..1.0"
            ),
            "durability": AttributeDefinition(type="int", default=100, range="0..100"),
            "weapon_type": AttributeDefinition(
                type="str",
                enum=["sword", "axe", "bow", "staff", "dagger"],
            ),
            # Weapon-specific derived fields
            "damage_per_weight": AttributeDefinition(
                type="float", derived="{{ damage / weight if weight > 0 else 0 }}"
            ),
            "effective_damage": AttributeDefinition(
                type="float", derived="{{ damage * (1 + critical_chance) }}"
            ),
            "weapon_summary": AttributeDefinition(
                type="str",
                derived="{{ name }} ({{ weapon_type }}): {{ damage }} {{ damage_type }} damage, {{ durability }}% durability",
            ),
        },
        validations=[
            ValidationRule(
                expression="damage > 0", message="Weapon damage must be positive"
            ),
            ValidationRule(
                expression="durability >= 0",
                message="Weapon durability cannot be negative",
            ),
        ],
    )

    print(
        f"Created inheritance chain: {base_entity_def.id} → {item_def.id} → {weapon_def.id}"
    )
    print()

    # 2. Models auto-registered in namespace
    print("2. Models Auto-Registered")
    print(
        "All models automatically registered in 'demo' namespace for inheritance resolution"
    )
    print()

    # 3. Create a weapon instance (full inheritance)
    print("3. Creating a Weapon Instance")
    excalibur_data = {
        # Base entity fields
        "id": "weapon_001",
        "name": "Excalibur",
        "description": "The legendary sword of King Arthur",
        "created_at": "2024-12-01",
        # Item fields
        "value": 5000,
        "weight": 3.5,
        "rarity": "legendary",
        "stackable": False,
        # Weapon fields
        "damage": 25,
        "damage_type": "slashing",
        "critical_chance": 0.15,
        "durability": 98,
        "weapon_type": "sword",
    }

    excalibur_weapon = create_model(weapon_def, excalibur_data)

    print("Weapon created with full inheritance:")
    print(f"  Name: {excalibur_weapon['name']} (from base_entity)")
    print(f"  Value: {excalibur_weapon['value']}gp (from item)")
    print(f"  Damage: {excalibur_weapon['damage']} (from weapon)")
    print(f"  Item Summary: {excalibur_weapon['item_summary']} (item derived field)")
    print(
        f"  Weapon Summary: {excalibur_weapon['weapon_summary']} (weapon derived field)"
    )
    print(
        f"  Effective Damage: {excalibur_weapon['effective_damage']:.1f} (weapon derived field)"
    )
    print()

    # 4. Demonstrate polymorphism - items and weapons together
    print("4. Polymorphic Behavior - Treating Weapons as Items")

    # Each object is built from its own most specific definition, so no subtype
    # data is discarded. A weapon's data goes through the weapon model; a plain
    # item's through the item model. Both inherit the item attributes, so code
    # written against an item works for either.
    a_potion = create_model(
        item_def,
        {
            "id": "item_001",
            "name": "Health Potion",
            "description": "Restores 50 HP",
            "value": 25,
            "weight": 0.2,
            "rarity": "common",
            "stackable": True,
        },
    )

    inventory = [a_potion, excalibur_weapon]
    print("Inventory (weapons and items read through the item interface):")
    for i, entry in enumerate(inventory, 1):
        print(f"  {i}. {entry['item_summary']}")
        print(f"     value/weight: {entry['value_per_weight']:.1f}gp/kg")
    print()

    # 5. Validation at different levels
    print("5. Validation at Different Inheritance Levels")

    # Test item-level validation
    print("Testing item-level validation:")
    try:
        create_model(
            item_def,
            {
                "id": "item_bad",
                "name": "Broken Item",
                "value": 10,
                "weight": -1.0,  # Invalid weight
            },
        )
        print("  ✗ Validation should have failed!")
    except Exception as e:
        print(f"  ✓ Item validation correctly failed: {str(e).split('|')[1].strip()}")

    # Test weapon-level validation
    print("\nTesting weapon-level validation:")
    try:
        invalid_weapon_data = dict(excalibur_weapon)
        invalid_weapon_data["damage"] = 0  # Invalid damage
        create_model(weapon_def, invalid_weapon_data)
        print("  ✗ Validation should have failed!")
    except Exception as e:
        print(f"  ✓ Weapon validation correctly failed: {str(e).split('|')[1].strip()}")
    print()

    # 6. A weapon keeps its subtype data
    print("6. A Weapon Keeps Its Subtype Data")

    restored_weapon = create_model(weapon_def, dict(excalibur_weapon))
    print("Restored weapon from its own data:")
    print(f"  Name: {restored_weapon['name']}")
    print(f"  Damage: {restored_weapon['damage']} {restored_weapon['damage_type']}")
    print(f"  Weapon Type: {restored_weapon['weapon_type']}")
    print(f"  Effective Damage: {restored_weapon['effective_damage']:.1f}")
    print(f"  Weapon Summary: {restored_weapon['weapon_summary']}")

    print("\n  Data preservation check:")
    print(f"    Original weapon damage: {excalibur_weapon['damage']}")
    print(f"    Restored weapon damage: {restored_weapon['damage']}")
    print(f"    Match: {excalibur_weapon['damage'] == restored_weapon['damage']}")
    print()

    # 7. Practical use case - inventory system
    print("7. Practical Use Case - Inventory System")

    ring_data = {
        "id": "item_002",
        "name": "Ring of Power",
        "description": "Increases magical power",
        "value": 1500,
        "weight": 0.1,
        "rarity": "epic",
        "stackable": False,
    }

    dagger_data = {
        "id": "weapon_002",
        "name": "Silver Dagger",
        "description": "A swift and deadly blade",
        "value": 150,
        "weight": 0.8,
        "rarity": "uncommon",
        "stackable": False,
        "damage": 8,
        "damage_type": "piercing",
        "critical_chance": 0.25,
        "durability": 95,
        "weapon_type": "dagger",
    }

    # Each from its own definition: item data through `item`, weapon data
    # through `weapon`. Both inherit the item interface.
    inventory_items = [
        a_potion,
        create_model(item_def, ring_data),
        create_model(weapon_def, dagger_data),
    ]

    print("Inventory (all read as items):")
    total_value = 0
    total_weight = 0

    for i, item in enumerate(inventory_items, 1):
        print(f"  {i}. {item['item_summary']}")
        total_value += item["value"]
        total_weight += item["weight"]

    print("\nInventory totals:")
    print(f"  Total value: {total_value}gp")
    print(f"  Total weight: {total_weight:.1f}kg")

    # The weapon entry is still a weapon, with its subtype data intact
    combat_dagger = inventory_items[2]
    print("\nThe dagger entry keeps its weapon data:")
    print(f"  Damage: {combat_dagger['damage']}")
    print(f"  Weapon Type: {combat_dagger['weapon_type']}")
    print(f"  Weapon Summary: {combat_dagger['weapon_summary']}")


if __name__ == "__main__":
    main()
