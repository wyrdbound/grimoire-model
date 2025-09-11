# Grimoire Model

[![Tests](https://github.com/wyrdbound/grimoire-model/workflows/Tests/badge.svg)](https://github.com/wyrdbound/grimoire-model/actions)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-88%25-green.svg)](htmlcov/index.html)

**Dict-like model system with schema validation, derived fields, and inheritance for the Grimoire tabletop RPG engine.**

Grimoire Model provides a sophisticated, schema-driven model system that combines the familiar dict-like interface with powerful features like automatic field derivation, template-based expressions, model inheritance, and comprehensive validation. Designed to integrate seamlessly with `grimoire-context` for complete game state management.

## ✨ Features

- **📚 Dict-like Interface**: Familiar Python dictionary operations with schema validation
- **🔄 Reactive Derived Fields**: Automatic computation with dependency tracking and batch updates
- **🧬 Model Inheritance**: Multiple inheritance support with automatic namespace-based resolution
- **📝 Template Expressions**: Jinja2-powered field templates for dynamic content
- **🏷️ Namespace Organization**: Global model registry with namespace-based organization
- **🛡️ Schema Validation**: Pydantic-based type checking and custom validation rules
- **🔧 Dependency Injection**: Pluggable resolvers for extensibility
- **⚡ Performance Optimized**: Efficient batch updates and lazy evaluation
- **🎯 grimoire-context Integration**: Seamless interoperability with context management

## 🚀 Quick Start

### Installation

```bash
pip install grimoire-model
```

### Basic Usage

```python
from grimoire_model import ModelDefinition, AttributeDefinition, create_model

# Define a character model schema
character_def = ModelDefinition(
    id="character",
    name="Player Character",
    namespace="rpg",  # Organize models in namespaces
    attributes={
        "name": AttributeDefinition(type="str", required=True),
        "level": AttributeDefinition(type="int", default=1),
        "hp": AttributeDefinition(type="int", default=100),
        "mp": AttributeDefinition(type="int", default=50),

        # Derived fields automatically update when dependencies change
        "max_hp": AttributeDefinition(
            type="int",
            derived="{{ level * 8 + hp }}"
        ),
        "character_summary": AttributeDefinition(
            type="str",
            derived="Level {{ level }} {{ name }} ({{ max_hp }} HP, {{ mp }} MP)"
        )
    }
)

# Create a character instance
character = create_model(character_def, {
    "name": "Aragorn",
    "level": 15,
    "hp": 120,
    "mp": 80
})

# Dict-like interface with automatic derived field updates
print(character['name'])              # "Aragorn"
print(character['max_hp'])            # 240 (15 * 8 + 120)
print(character['character_summary']) # "Level 15 Aragorn (240 HP, 80 MP)"

# Updates trigger automatic recalculation
character['level'] = 20
print(character['max_hp'])            # 280 (20 * 8 + 120, automatically updated)
```

### Global Model Registry

Models are automatically registered in a global registry using namespaces:

```python
from grimoire_model import get_model

# Models auto-register when created
character_def = ModelDefinition(
    id="character",
    namespace="rpg",  # Registered in "rpg" namespace
    # ... attributes ...
)

# Retrieve from anywhere in your application
retrieved_def = get_model("rpg", "character")
new_character = create_model(retrieved_def, {"name": "Hero"})

# Perfect for inheritance - child models automatically find parents
base_def = ModelDefinition(id="base", namespace="rpg", ...)
child_def = ModelDefinition(id="child", namespace="rpg", extends=["base"], ...)
# No manual registry needed - inheritance resolves automatically!
```

### Model Inheritance with Namespaces

```python
from grimoire_model import get_model, clear_registry

# Base entity definition (auto-registered in namespace)
base_entity_def = ModelDefinition(
    id="base_entity",
    name="Base Entity",
    namespace="game",  # Registered in "game" namespace
    attributes={
        "id": AttributeDefinition(type="str", required=True),
        "name": AttributeDefinition(type="str", required=True),
        "description": AttributeDefinition(type="str", default="")
    }
)

# Character extends base entity (automatic inheritance resolution)
character_def = ModelDefinition(
    id="character",
    name="Character",
    namespace="game",  # Same namespace enables automatic inheritance
    extends=["base_entity"],  # Automatically finds base_entity in namespace
    attributes={
        "level": AttributeDefinition(type="int", default=1),
        "hp": AttributeDefinition(type="int", default=100),
        "max_hp": AttributeDefinition(
            type="int",
            derived="{{ level * 8 + hp }}"
        )
    }
)

# Create character with inherited fields (no registry needed!)
character = create_model(
    character_def,
    {
        "id": "char_001",          # From base_entity
        "name": "Legolas",         # From base_entity
        "description": "Elf archer", # From base_entity
        "level": 12,               # From character
        "hp": 96                   # From character
    }
)

print(character['id'])          # "char_001" (inherited)
print(character['name'])        # "Legolas" (inherited)
print(character['max_hp'])      # 192 (derived field)

# Retrieve models from global registry
retrieved_char_def = get_model("game", "character")
another_character = create_model(retrieved_char_def, {
    "id": "char_002",
    "name": "Gimli"
})
```

### Integration with grimoire-context

```python
from grimoire_context import GrimoireContext

# Create context with character model
context = GrimoireContext({
    'party': {
        'leader': character,
        'members': 4
    }
})

# Modify character through context - derived fields update automatically
context = context.set_variable('party.leader.level', 25)
updated_character = context.get_variable('party.leader')

print(updated_character['level'])   # 25
print(updated_character['max_hp'])  # 296 (automatically recalculated)
```

### Batch Updates for Performance

```python
# Batch multiple changes for better performance
character.batch_update({
    'level': 30,
    'hp': 150,
    'mp': 120
})

# All derived fields updated once after batch completion
print(character['max_hp'])  # 390 (30 * 8 + 150)
```

## 📚 Documentation

- **[Logging Configuration](LOGGING.md)** - Configure library logging output and integration

## 📚 Core Concepts

### Model Definitions

Model definitions are schemas that describe the structure, types, and behavior of your data:

```python
model_def = ModelDefinition(
    id="weapon",
    name="Weapon",
    namespace="combat",  # Organize in combat namespace
    description="Combat weapon with damage calculations",
    attributes={
        "name": AttributeDefinition(type="str", required=True),
        "base_damage": AttributeDefinition(type="int", default=1, range="1..50"),
        "enhancement": AttributeDefinition(type="int", default=0, range="0..10"),

        # Derived field with complex logic
        "total_damage": AttributeDefinition(
            type="int",
            derived="{{ base_damage + enhancement * 2 }}"
        ),
        "damage_category": AttributeDefinition(
            type="str",
            derived="{% if total_damage >= 20 %}High{% elif total_damage >= 10 %}Medium{% else %}Low{% endif %}"
        )
    },
    validations=[
        ValidationRule(
            expression="base_damage > 0",
            message="Base damage must be positive"
        )
    ]
)
```

### Template Expressions

Use Jinja2 templates for powerful derived field logic:

```python
# Simple expression
"max_hp": "{{ level * 8 + constitution * 2 }}"

# Conditional logic
"damage_bonus": "{% if strength >= 15 %}{{ (strength - 10) // 2 }}{% else %}0{% endif %}"

# Complex calculations
"skill_modifier": "{{ (skill_level + attribute_bonus - 10) // 2 }}"
```

### Validation Rules

Add custom validation logic to ensure data integrity:

```python
ValidationRule(
    expression="level >= 1 and level <= 100",
    message="Character level must be between 1 and 100"
),
ValidationRule(
    expression="hp > 0 or status == 'dead'",
    message="Living characters must have positive HP"
)
```

## 🔧 API Reference

### Core Classes

#### ModelDefinition

```python
ModelDefinition(
    id: str,                                    # Unique model identifier
    name: str,                                  # Human-readable name
    namespace: str = "default",                 # Namespace for organization and inheritance
    description: str = "",                      # Model description
    attributes: Dict[str, AttributeDefinition], # Field definitions
    extends: List[str] = None,                  # Parent model IDs (resolved in namespace)
    validations: List[ValidationRule] = None    # Validation rules
)
```

#### AttributeDefinition

```python
AttributeDefinition(
    type: str,                    # Data type (str, int, float, bool, list, dict)
    required: bool = False,       # Whether field is required
    default: Any = None,          # Default value
    derived: str = None,          # Template expression for derived fields
    range: str = None,            # Value range constraint (e.g., "1..100")
    enum: List[Any] = None,       # Allowed values
    pattern: str = None,          # Regex pattern for strings
    description: str = ""         # Field description
)
```

#### GrimoireModel

```python
class GrimoireModel(MutableMapping):
    def __init__(
        self,
        model_definition: ModelDefinition,
        data: Dict[str, Any] = None,
        template_resolver: TemplateResolver = None,
        derived_field_resolver: DerivedFieldResolver = None,
        **kwargs
    )

    # Dict-like interface
    def __getitem__(self, key: str) -> Any
    def __setitem__(self, key: str, value: Any) -> None
    def __delitem__(self, key: str) -> None
    def __iter__(self) -> Iterator[str]
    def __len__(self) -> int
    def keys(), values(), items()

    # Batch operations
    def batch_update(self, updates: Dict[str, Any]) -> None

    # Path operations (dot notation)
    def get(self, path: str, default: Any = None) -> Any
    def set(self, path: str, value: Any) -> None
    def has(self, path: str) -> bool
    def delete(self, path: str) -> None
```

### Factory Functions

#### create_model

```python
def create_model(
    model_definition: ModelDefinition,
    data: Dict[str, Any] = None,
    template_resolver_type: str = "jinja2",
    derived_field_resolver_type: str = "batched",
    **kwargs
) -> GrimoireModel
```

Creates a model instance with default resolvers. Inheritance is automatically resolved from the global model registry using namespaces.

### Global Registry Functions

```python
from grimoire_model import register_model, get_model, clear_registry

# Register model manually (usually automatic)
register_model("my_namespace", "my_model", model_definition)

# Retrieve model from registry
model_def = get_model("my_namespace", "my_model")

# Clear all models (useful for testing)
clear_registry()

# Access registry directly for advanced operations
from grimoire_model import get_model_registry
registry = get_model_registry()
registry_dict = registry.get_registry_dict()
all_namespaces = registry.list_namespaces()
```

### Template Resolvers

- `Jinja2TemplateResolver`: Standard Jinja2 template syntax
- `ModelContextTemplateResolver`: Simple `$variable` substitution
- `CachingTemplateResolver`: Cached template compilation for performance

### Derived Field Resolvers

- `BatchedDerivedFieldResolver`: Batches updates for performance
- `DerivedFieldResolver`: Immediate update resolver

## 🧪 Development

### Setup

```bash
git clone https://github.com/wyrdbound/grimoire-model.git
cd grimoire-model
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests with coverage
/Users/justingaylor/src/grimoire-model/.venv/bin/python -m pytest --cov=grimoire_model --cov-report=term

# Run specific test file
/Users/justingaylor/src/grimoire-model/.venv/bin/python -m pytest tests/test_model.py

# Run with verbose output
/Users/justingaylor/src/grimoire-model/.venv/bin/python -m pytest -v

# Generate HTML coverage report
/Users/justingaylor/src/grimoire-model/.venv/bin/python -m pytest --cov=grimoire_model --cov-report=html
# Open htmlcov/index.html in browser
```

_Note: Use the virtual environment in the project root as specified in the development guidelines._

### Code Quality

```bash
# Install development dependencies
source .venv/bin/activate && pip install ruff mypy

# Linting and formatting
source .venv/bin/activate && ruff check .
source .venv/bin/activate && ruff format .

# Type checking
source .venv/bin/activate && mypy src/grimoire_model/

# Run all quality checks
source .venv/bin/activate && ruff check . && mypy src/grimoire_model/
```

### Running Examples

```bash
# Basic usage example
source .venv/bin/activate && python examples/01_basic_usage.py

# Advanced features and inheritance
source .venv/bin/activate && python examples/02_advanced_usage.py

# Inheritance and polymorphism
source .venv/bin/activate && python examples/03_inheritance_polymorphism.py

# Performance and integration testing
source .venv/bin/activate && python examples/04_performance_integration.py
```

## 📋 Requirements

- Python 3.8+
- pydantic >= 2.0.0
- pyrsistent >= 0.19.0
- jinja2 >= 3.1.0
- pyyaml >= 6.0

### Development Dependencies

- pytest >= 7.0.0
- pytest-cov >= 4.0.0
- pytest-mock >= 3.0.0
- hypothesis >= 6.0.0
- mypy >= 1.0.0
- ruff >= 0.1.0

## 🎯 Use Cases

Grimoire Model excels in scenarios requiring structured, validated data with complex relationships:

- **RPG Character Systems**: Stats, levels, equipment with derived values
- **Game Item Management**: Equipment, inventory, crafting systems
- **Rule Engine Data**: Complex game mechanics with interdependent calculations
- **Configuration Systems**: Hierarchical configs with inheritance and validation
- **Dynamic Content**: Template-based content generation with context awareness

## 🏗️ Architecture

The package follows clean architecture principles with clear separation of concerns:

- **Core Layer**: Model definitions, schemas, and the main GrimoireModel class
- **Resolver Layer**: Pluggable template and derived field resolution systems
- **Validation Layer**: Type checking, constraints, and custom validation rules
- **Utils Layer**: Inheritance resolution, path utilities, and helper functions
- **Integration Layer**: grimoire-context compatibility and factory functions

### Key Design Principles

1. **Dependency Injection**: All major components can be swapped via constructor injection
2. **Immutable Operations**: Uses pyrsistent for efficient immutable data structures
3. **Template-Driven**: Jinja2 templates provide powerful expression capabilities
4. **Performance-Focused**: Batch updates and lazy evaluation minimize overhead
5. **Type Safety**: Full type hints and Pydantic integration for runtime validation
6. **Explicit Errors**: Prefers explicit errors over fallbacks to maintain system stability

## 📈 Performance

Current benchmarks (86% test coverage, 184 tests passing):

- **Model Creation**: ~1ms for simple models, ~5ms for complex inheritance
- **Field Updates**: ~0.1ms for direct fields, ~2ms for derived field cascades
- **Batch Updates**: 50-80% faster than individual updates for multiple fields
- **Memory Usage**: ~50KB per model instance (excluding data)
- **Template Resolution**: Cached compilation provides 10x speed improvement

## 🔄 Integration with grimoire-context

Seamless integration is automatically enabled when both packages are installed:

```python
from grimoire_model import create_model, ModelDefinition, AttributeDefinition
from grimoire_context import GrimoireContext

# Models work naturally in contexts
character = create_model(character_def, character_data)
context = GrimoireContext({'player': character})

# Context operations automatically handle model updates
updated_context = context.set_variable('player.level', 25)
updated_character = updated_context['player']

# Derived fields update automatically
print(updated_character['max_hp'])  # Recalculated based on new level
```

## 🚨 Error Handling

The package provides a comprehensive exception hierarchy:

```python
from grimoire_model import (
    GrimoireModelError,           # Base exception
    ModelValidationError,          # Validation failures
    TemplateResolutionError,       # Template processing errors
    InheritanceError,              # Model inheritance issues
    DependencyError,               # Derived field dependency issues
    ConfigurationError             # Setup and configuration errors
)

try:
    character = create_model(character_def, invalid_data)
except ModelValidationError as e:
    print(f"Validation failed: {e}")
    print(f"Field: {e.field_name}")
    print(f"Value: {e.field_value}")
    print(f"Validation rule: {e.validation_rule}")
```

## 🔍 Advanced Features

### Custom Template Resolvers

```python
from grimoire_model.resolvers.template import TemplateResolver

class CustomTemplateResolver(TemplateResolver):
    def resolve_template(self, template: str, context: dict) -> str:
        # Custom template logic
        return processed_template

# Use custom resolver
model = GrimoireModel(
    model_def,
    data,
    template_resolver=CustomTemplateResolver()
)
```

### Custom Validators

```python
from grimoire_model.validation.validators import ValidationEngine

def custom_validator(value, rule_params):
    # Custom validation logic
    return is_valid, error_message

# Register custom validator
engine = ValidationEngine()
engine.register_validator("custom_rule", custom_validator)
```

### Multiple Inheritance

```python
# Multiple parent models (all in same namespace)
combat_def = ModelDefinition(
    id="character",
    namespace="game",  # All parent models must be in same namespace
    extends=["base_entity", "combatant", "spell_caster"],
    attributes={...}
)

# Automatic conflict resolution with left-to-right precedence
# Parents automatically resolved from "game" namespace
```

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for complete terms and conditions.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

If you have questions about the project, please contact: wyrdbound@proton.me

---

**Copyright (c) 2025 The Wyrd One**
