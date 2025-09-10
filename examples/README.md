# Wyrdbound Model Examples

This directory contains comprehensive examples demonstrating the capabilities of the wyrdbound-model package, from basic usage to advanced inheritance and polymorphism patterns.

## Running the Examples

Make sure you have the wyrdbound-model package installed and its dependencies:

```bash
# Install the package in development mode
pip install -e .

# Run any example
python examples/01_basic_usage.py
python examples/02_advanced_usage.py
python examples/03_inheritance_polymorphism.py
python examples/04_performance_integration.py
```

## Examples Overview

### 1. Basic Usage (`01_basic_usage.py`)

This example covers the fundamental features of wyrdbound-model:

- **Model Definition Creation**: Defining models with attributes, types, defaults, and validation
- **Basic Derived Fields**: Simple template-based computed fields
- **Factory Function Usage**: Using `create_model()` for convenient model instantiation
- **Dict-like Interface**: Working with models as mutable dictionaries
- **Validation**: Field validation and required field checking
- **Model Introspection**: Examining model properties and data

**Key Concepts Demonstrated:**

- `ModelDefinition` and `AttributeDefinition` classes
- Template syntax for derived fields using Jinja2
- Default values and field requirements
- Validation rules and error handling
- Model comparison and serialization

### 2. Advanced Usage (`02_advanced_usage.py`)

This example showcases advanced features for complex applications:

- **Model Inheritance**: Creating hierarchical model definitions
- **Complex Derived Fields**: Multi-level dependencies between computed fields
- **Namespace Organization**: Using namespaces for automatic model organization and inheritance resolution
- **Batch Updates**: Efficient bulk field updates
- **Alternative Template Resolvers**: Using different template syntaxes
- **Complex Validation**: Multi-field validation rules
- **Nested Data Handling**: Working with structured data and dot-notation access

**Key Concepts Demonstrated:**

- Model inheritance with `extends` property
- Derived field dependency chains
- `namespace` parameter for automatic model registration and inheritance resolution
- `batch_update()` for performance optimization
- Model context resolver with `$variable` syntax
- Nested attribute access patterns

### 3. Inheritance Polymorphism (`03_inheritance_polymorphism.py`)

This example demonstrates advanced inheritance and polymorphism capabilities:

- **Multi-Level Inheritance**: Creating complex inheritance chains (base_entity → item → weapon)
- **Polymorphic Behavior**: Treating subclass instances as parent types
- **Data Preservation**: Converting between inheritance levels while maintaining all data
- **Level-Specific Validation**: Validation rules that apply at different inheritance levels
- **Practical Use Cases**: Real-world scenarios like inventory management systems
- **Feature Preservation**: How specialized features are maintained during polymorphic operations

**Key Concepts Demonstrated:**

- Three-level inheritance chain design
- Polymorphic model behavior and type flexibility
- Converting weapons to items while preserving weapon data
- Validation at each inheritance level
- Inventory system implementation patterns
- Data integrity during polymorphic transformations

### 4. Performance and Integration (`04_performance_integration.py`)

This example focuses on performance considerations and real-world integration patterns:

- **Performance Benchmarking**: Measuring model operation performance across different scenarios
- **Batched vs Regular Resolvers**: Comparing performance characteristics of different resolver types
- **Complex Model Analysis**: Understanding model structure and dependency relationships
- **Serialization Patterns**: JSON serialization and deserialization for data persistence
- **Factory Patterns**: Creating reusable model templates and character generators
- **Integration Strategies**: Best practices for using wyrdbound-model in larger applications

**Key Concepts Demonstrated:**

- Performance benchmarking techniques and optimization strategies
- Batched derived field resolver benefits for complex models
- Model introspection and dependency analysis
- Factory pattern implementation for character generation
- JSON serialization strategies for data persistence
- Production-ready integration patterns and best practices

## Common Patterns

### Model Definition Pattern

```python
from wyrdbound_model import ModelDefinition, AttributeDefinition, ValidationRule

model_def = ModelDefinition(
    id="my_model",
    name="My Model",
    namespace="my_app",  # Organize models in namespaces
    attributes={
        "field1": AttributeDefinition(type="str", required=True),
        "field2": AttributeDefinition(type="int", default=0),
        "computed": AttributeDefinition(type="str", derived="{{ field1 }}_{{ field2 }}")
    },
    validations=[
        ValidationRule(expression="field2 >= 0", message="Field2 must be non-negative")
    ]
)
```

### Factory Function Pattern

```python
from wyrdbound_model.core.model import create_model

# Basic usage
model = create_model(model_def, {"field1": "value"})

# With batched resolver for performance
model = create_model(
    model_def,
    {"field1": "value"},
    derived_resolver_kwargs={"batched": True}
)

# With inheritance (auto-resolved via namespaces)
model = create_model(
    child_model_def,  # Inherits from parent automatically
    {"field1": "value"}
)
```

### Batch Update Pattern

```python
# Efficient bulk updates
model.batch_update({
    "field1": "new_value",
    "field2": 42,
    "field3": True
})
```

### Global Registry and Namespace Pattern

```python
from wyrdbound_model import get_model, clear_registry

# Models automatically register when created with namespaces
character_def = ModelDefinition(
    id="character",
    namespace="rpg",  # Registered in "rpg" namespace
    attributes={...}
)

# Retrieve models from global registry
retrieved_def = get_model("rpg", "character")

# Use retrieved model definition
character = create_model(retrieved_def, {"name": "Hero"})

# Clear namespace for testing or reset
clear_registry()  # Clear all namespaces
# Or clear specific namespace (not shown - would be clear_namespace("rpg"))
```

### Inheritance Pattern

```python
# Parent model (auto-registered in namespace)
parent_def = ModelDefinition(
    id="parent",
    namespace="my_app",
    attributes={
        "common_field": AttributeDefinition(type="str", required=True)
    }
)

# Child model (automatically finds parent in same namespace)
child_def = ModelDefinition(
    id="child",
    namespace="my_app",  # Same namespace for inheritance resolution
    extends=["parent"],
    attributes={
        "specific_field": AttributeDefinition(type="int", default=0)
    }
)
```

## Error Handling

The examples also demonstrate proper error handling for common scenarios:

- **Validation Errors**: When data doesn't meet validation rules
- **Required Field Errors**: When required fields are missing
- **Type Errors**: When field values have incorrect types
- **Template Errors**: When derived field templates fail to resolve
- **Inheritance Errors**: When model inheritance cannot be resolved

## Inheritance and Polymorphism Patterns

Based on the inheritance polymorphism example, consider these design patterns:

### Inheritance Chain Design

```python
# Base entity (common properties)
base_def = ModelDefinition(
    id="base_entity",
    namespace="game",  # Organize in namespace
    attributes={
        "id": AttributeDefinition(type="str", required=True),
        "name": AttributeDefinition(type="str", required=True)
    }
)

# Intermediate level (shared domain concepts)
item_def = ModelDefinition(
    id="item",
    namespace="game",  # Same namespace for inheritance
    extends=["base_entity"],
    attributes={
        "value": AttributeDefinition(type="int", default=0),
        "weight": AttributeDefinition(type="float", default=1.0)
    }
)

# Specific implementation (specialized behavior)
weapon_def = ModelDefinition(
    id="weapon",
    namespace="game",  # Same namespace for inheritance
    extends=["item"],
    attributes={
        "damage": AttributeDefinition(type="int", required=True),
        "weapon_type": AttributeDefinition(type="str", required=True)
    }
)
```

### Polymorphic Usage Pattern

```python
# Create specialized instance (inheritance auto-resolved)
weapon = create_model(weapon_def, {
    "id": "sword_001",
    "name": "Excalibur",
    "value": 1000,
    "weight": 3.0,
    "damage": 25,
    "weapon_type": "sword"
})

# Use polymorphically as item
def process_item(item_data):
    print(f"Item: {item_data['name']}, Value: {item_data['value']}")
    # Weapon-specific data still available in underlying dict
    if 'damage' in item_data:
        print(f"  (This item is actually a weapon with {item_data['damage']} damage)")

process_item(weapon)  # Works seamlessly

# Convert back to specialized type when needed
restored_weapon = create_model(weapon_def, dict(weapon))
```

### Factory Pattern for Character Generation

```python
def create_character_factory(model_def):
    """Create a factory function for generating characters of a specific class."""

    class_stats = {
        "warrior": {"strength": 16, "constitution": 14, "dexterity": 12},
        "mage": {"intelligence": 16, "wisdom": 14, "constitution": 10},
        "rogue": {"dexterity": 16, "intelligence": 14, "strength": 10}
    }

    def create_character(name: str, character_class: str, level: int = 1):
        base_data = {
            "name": name,
            "class": character_class,
            "level": level,
            **class_stats.get(character_class, {})
        }
        return create_model(model_def, base_data)

    return create_character

# Usage
character_factory = create_character_factory(character_def)
warrior = character_factory("Conan", "warrior", 5)
mage = character_factory("Gandalf", "mage", 10)
```

### Performance Benchmarking Pattern

```python
def benchmark_operation(name: str, operation, iterations: int = 1000):
    """Simple benchmarking utility for model operations."""
    start_time = time.time()
    for _ in range(iterations):
        operation()
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / iterations
    print(f"{name}: {avg_time:.6f}s avg ({iterations} iterations)")
    return avg_time

# Compare different approaches
benchmark_operation("Regular resolver", lambda: create_model(model_def, data))
benchmark_operation("Batched resolver", lambda: create_model(
    model_def, data, derived_resolver_kwargs={"batched": True}
))
```

## Performance Considerations

For optimal performance with complex inheritance and polymorphism:

1. **Use Batched Resolver**: For models with many derived fields
2. **Organize with Namespaces**: Use meaningful namespaces to organize related models
3. **Strategic Inheritance**: Design inheritance chains to minimize deep nesting
4. **Batch Updates**: When updating multiple related fields
5. **Global Registry**: Leverage automatic registration for model reuse across your application

## Integration with Other Systems

These examples show patterns for integrating wyrdbound-model with:

- **JSON APIs**: Serialization and deserialization patterns
- **Database Systems**: Data modeling and validation with inheritance
- **Game Engines**: Character, item, and equipment management
- **Inventory Systems**: Polymorphic item handling and categorization
- **Configuration Systems**: Dynamic configuration with validation
- **Web Applications**: Form validation and hierarchical data processing
- **RPG Systems**: Character sheets, equipment, and game mechanics

## Real-World Use Cases Demonstrated

1. **Character Management** (Basic): Player stats, derived attributes, validation
2. **Complex Game Systems** (Advanced): Multi-level inheritance, equipment, nested data
3. **Inventory Management** (Polymorphism): Items that can be weapons, armor, consumables
4. **Performance Optimization** (Integration): Benchmarking, batching, factory patterns
5. **Equipment Systems**: Polymorphic behavior where weapons are items with special properties
6. **Game Mechanics**: Damage calculations, stat bonuses, equipment effects
7. **Data Persistence**: JSON serialization for save/load functionality
8. **Character Generation**: Factory patterns for procedural character creation

Each example is self-contained and can be run independently to explore specific features.
