# Grimoire Model Package Development Plan

## Overview

Create a standalone `grimoire-model` Python package that extracts model functionality from `grimoire-systems` into a reusable, dependency-injectable component that integrates seamlessly with `grimoire-context`.

## AI Guidance

Always remember the following points as you are working on this code base:

1. Use the virtual env in the project root (`source .venv/bin/activate && <your_command>`)

2. Prefer explicit errors over fallbacks when fallbacks would mask issues. We want to fix issues so we can have a stable system.

3. Follow good software development practices (like SOLID).

4. Simpler is better.

5. Remember that the purpose of this package is to provide a flexible and reusable model implementation for the Grimoire engine. Avoid adding special-cases or hack fixes simply to get around issues.

6. Do NOT make bandaid fixes that break the rearchitecture goals for Grimoire Context. Always respect the architectural boundaries.

7. After all code changes, run `ruff check src/ tests/ --fix`, `ruff format src/ tests/`, and `mypy src/ tests/` to ensure code quality is retained in an interative manner.

8. Avoid making lines longer than 88 characters (E501 ruff check).

## Package Structure

```
grimoire-model/
├── src/
│   └── grimoire_model/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── model.py              # GrimoireModel main class
│       │   ├── schema.py             # ModelDefinition, AttributeDefinition
│       │   └── exceptions.py         # Custom exceptions
│       ├── resolvers/
│       │   ├── __init__.py
│       │   ├── template.py           # TemplateResolver interface & impl
│       │   └── derived.py            # DerivedFieldResolver interface & impl
│       ├── validation/
│       │   ├── __init__.py
│       │   ├── validators.py         # Field validators
│       │   └── rules.py              # Validation rule engine
│       └── utils/
│           ├── __init__.py
│           ├── inheritance.py        # Model inheritance resolution
│           └── paths.py              # Dot notation path utilities
├── tests/
│   ├── __init__.py
│   ├── test_model.py
│   ├── test_schema.py
│   ├── test_resolvers.py
│   ├── test_validation.py
│   └── fixtures/
│       └── sample_models.yaml
├── pyproject.toml
├── README.md
└── LICENSE

```

## Core Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.8"
pydantic = "^2.0"
pyrsistent = "^0.19.0"
jinja2 = "^3.1.0"
pyyaml = "^6.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.0"
pytest-cov = "^4.0"
ruff = "^0.1.0"
mypy = "^1.0"
```

## Phase 1: Core Foundation (Week 1)

### 1.1 Project Setup

- [x] Initialize Poetry project structure
- [x] Configure pyproject.toml with dependencies
- [x] Set up basic CI/CD pipeline
- [x] Create initial package structure

### 1.2 Schema Definition System

**Priority: High**

Create the foundational schema system based on existing GRIMOIRE model definitions:

**Files:**

- `core/schema.py` - ModelDefinition, AttributeDefinition classes
- `core/exceptions.py` - Custom exception classes

**Key Features:**

- Pydantic-based schema definitions
- Support for nested attributes
- Type validation and constraints
- Derived field definitions
- Validation rule definitions

### 1.3 Basic Model Class

**Priority: High**

**Files:**

- `core/model.py` - GrimoireModel class

**Key Features:**

- Dict-like interface (MutableMapping)
- Pydantic integration for validation
- Immutable operations using pyrsistent
- Dependency injection points for resolvers

## Phase 2: Resolver System (Week 2)

### 2.1 Template Resolver Interface & Implementation

**Priority: High**

**Files:**

- `resolvers/template.py`

**Key Features:**

- Abstract TemplateResolver protocol
- Jinja2-based default implementation
- Context management for template variables
- Error handling and logging

### 2.2 Derived Field Resolver

**Priority: High**

**Files:**

- `resolvers/derived.py`

**Key Features:**

- DerivedFieldResolver implementation
- Dependency graph management
- Topological sorting for computation order
- Observable pattern for field changes
- Circular dependency prevention

### 2.3 Integration Points

**Priority: Medium**

- Dependency injection system
- Resolver lifecycle management
- Context passing between resolvers

## Phase 3: Advanced Features (Week 3)

### 3.1 Model Inheritance System

**Priority: High**

**Files:**

- `utils/inheritance.py`

**Key Features:**

- `extends` field resolution
- Multiple inheritance support
- Attribute override handling
- Conflict resolution strategies

### 3.2 Validation Engine

**Priority: Medium**

**Files:**

- `validation/validators.py`
- `validation/rules.py`

**Key Features:**

- Field-level validation
- Cross-field validation rules
- Custom validation rule execution
- Expression evaluation for validation

### 3.3 Path Utilities

**Priority: Medium**

**Files:**

- `utils/paths.py`

**Key Features:**

- Dot notation path parsing
- Nested value access/modification
- Path validation and normalization

## Phase 4: Integration & Testing (Week 4)

### 4.1 GrimoireContext Integration

**Priority: High**

**Key Features:**

- Seamless integration with grimoire-context
- Dict-like behavior compatibility
- Immutability preservation
- Context value updates triggering model changes

### 4.2 Comprehensive Testing

**Priority: High**

**Test Coverage:**

- Unit tests for all components (>90% coverage)
- Integration tests with grimoire-context
- Performance tests for large models
- Edge case and error condition testing

### 4.3 Documentation & Examples

**Priority: Medium**

**Deliverables:**

- Complete API documentation
- Usage examples and tutorials
- Migration guide from grimoire-systems
- Performance optimization guide

## API Design

### Core GrimoireModel Interface

```python
from grimoire_model import GrimoireModel, ModelDefinition
from grimoire_model.resolvers import TemplateResolver, DerivedFieldResolver

# Create model with dependency injection
model = GrimoireModel(
    model_definition=character_model_def,
    data={'name': 'Aragorn', 'hp': 100},
    template_resolver=custom_template_resolver,
    derived_field_resolver=custom_derived_resolver,
    model_registry=all_model_definitions
)

# Dict-like interface
model['level'] = 5  # Triggers validation and derived field updates
current_hp = model['hp']
del model['temporary_buff']

# Context integration
context = GrimoireContext({'character': model})
context.set_variable('character.xp', 1000)  # Updates model and triggers deriveds
```

### Dependency Injection Points

```python
class GrimoireModel(MutableMapping):
    def __init__(
        self,
        model_definition: ModelDefinition,
        data: Dict[str, Any] = None,
        template_resolver: Optional[TemplateResolver] = None,
        derived_field_resolver: Optional[DerivedFieldResolver] = None,
        model_registry: Optional[Dict[str, ModelDefinition]] = None,
        **kwargs
    ):
        # Initialize with injected dependencies
```

## Inheritance Resolution Strategy

### Multiple Inheritance Support

```python
# Base models
base_entity = ModelDefinition(id="base_entity", attributes={...})
combat_entity = ModelDefinition(id="combat_entity", attributes={...})

# Child model with multiple inheritance
character = ModelDefinition(
    id="character",
    extends=["base_entity", "combat_entity"],
    attributes={...}
)

# Resolution order: character -> base_entity -> combat_entity
resolved_model = resolve_inheritance(character, model_registry)
```

### Conflict Resolution

1. **Attribute Override**: Child attributes override parent attributes
2. **Method Resolution Order**: Left-to-right precedence in extends array
3. **Validation Merge**: Combine validation rules from all parents
4. **Derived Field Dependencies**: Maintain dependency graph across inheritance

## Error Handling Strategy

### Exception Hierarchy

```python
class GrimoireModelError(Exception):
    """Base exception for grimoire-model package."""

class ModelValidationError(GrimoireModelError):
    """Raised when model validation fails."""

class TemplateResolutionError(GrimoireModelError):
    """Raised when template resolution fails."""

class InheritanceError(GrimoireModelError):
    """Raised when model inheritance resolution fails."""

class DependencyError(GrimoireModelError):
    """Raised when derived field dependencies cannot be resolved."""
```

### Error Context

- Detailed error messages with field paths
- Context information for debugging
- Suggestions for fixing common issues
- Preservation of original error chain

## Performance Considerations

### Optimization Strategies

1. **Lazy Loading**: Load model definitions only when needed
2. **Caching**: Cache resolved inheritance chains and compiled templates
3. **Incremental Updates**: Only recompute affected derived fields
4. **Memory Efficiency**: Use structural sharing with pyrsistent
5. **Batching**: Batch multiple field updates to reduce overhead

### Performance Targets

- Model creation: < 1ms for simple models
- Field updates: < 0.1ms for non-derived fields
- Derived field computation: < 5ms for complex dependency graphs
- Memory usage: < 100KB per model instance (excluding data)

## Migration Strategy

### From grimoire-systems

1. **Extract Existing Code**: Copy and adapt existing implementation
2. **Dependency Injection**: Replace hard-coded dependencies with injection
3. **API Compatibility**: Maintain backward compatibility where possible
4. **Incremental Migration**: Support gradual migration from old to new system

### Migration Tools

- Automated code migration scripts
- Compatibility layer for existing code
- Migration validation tools
- Documentation and examples

## Testing Strategy

### Test Categories

1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Cross-component interaction testing
3. **Performance Tests**: Benchmarking and optimization validation
4. **Compatibility Tests**: grimoire-context integration testing
5. **Regression Tests**: Ensure existing functionality remains intact

### Test Data

- GRIMOIRE model definitions from grimoire-systems
- Edge cases and error conditions
- Performance test datasets
- Real-world usage scenarios

## Documentation Plan

### User Documentation

1. **Quick Start Guide**: Basic usage examples
2. **API Reference**: Complete class and method documentation
3. **Advanced Usage**: Complex scenarios and best practices
4. **Integration Guide**: Using with grimoire-context
5. **Migration Guide**: Moving from grimoire-systems

### Developer Documentation

1. **Architecture Overview**: System design and patterns
2. **Extension Points**: How to customize and extend
3. **Contributing Guide**: Development setup and guidelines
4. **Performance Guide**: Optimization techniques and benchmarks

## Release Strategy

### Version 0.1.0 (MVP)

- Core model functionality
- Basic template and derived field resolution
- Essential validation features
- grimoire-context integration

### Version 0.2.0 (Enhanced)

- Complete inheritance system
- Advanced validation rules
- Performance optimizations
- Comprehensive documentation

### Version 1.0.0 (Production Ready)

- Full feature parity with grimoire-systems
- Extensive testing and documentation
- Production-grade performance
- Stable API guarantee

## Success Criteria

### Functional Requirements

- [x] Models behave as dict-like objects
- [x] Full GRIMOIRE schema support
- [x] Derived field automatic computation
- [x] Model inheritance resolution
- [x] Seamless grimoire-context integration

### Quality Requirements

- [x] > 90% test coverage
- [x] Type safety with mypy
- [x] Performance targets met
- [x] Comprehensive documentation
- [x] Clean, maintainable code

### Integration Requirements

- [x] Drop-in replacement for grimoire-systems model functionality
- [x] No breaking changes to grimoire-context API
- [x] Backward compatibility with existing model definitions
- [x] Clear migration path from existing codebase

## Risk Mitigation

### Technical Risks

- **Complex Inheritance**: Comprehensive testing and clear documentation
- **Performance Issues**: Continuous benchmarking and optimization
- **API Compatibility**: Extensive compatibility testing
- **Dependency Management**: Minimal external dependencies, clear versioning

### Project Risks

- **Scope Creep**: Clear phase boundaries and deliverables
- **Timeline Pressure**: Prioritized feature development
- **Integration Complexity**: Early and continuous integration testing
- **Quality Issues**: Automated testing and code review processes

## Conclusion

This plan provides a structured approach to creating the `grimoire-model` package that extracts and enhances the model functionality from `grimoire-systems` while maintaining compatibility with `grimoire-context`. The phased approach ensures steady progress while managing complexity and risk.

The dependency injection design allows for flexibility and testability, while the comprehensive testing and documentation strategy ensures quality and maintainability. The performance considerations and optimization strategies ensure the package can handle real-world usage scenarios efficiently.
