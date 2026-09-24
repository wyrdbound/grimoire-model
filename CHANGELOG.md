# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-09-24

### Changed (breaking)

- **Python builtins are no longer injected into the expression context.**
  `max`, `min`, `sum`, `len`, `abs` and `round` were added to every
  evaluation context, written over the caller's data. A model attribute named
  `round` or `max` was silently replaced by the builtin function, and
  expressions using the function forms (`sum(xs)`) worked only in Python.
  Use Jinja2 filters instead: `xs | sum`, `xs | sum(attribute='w')`,
  `xs | max`, `xs | min`, `xs | length`, and the `in` operator

## [0.5.0] - 2026-09-24

Presence, defaults and null are now one coherent set of rules: attributes
are required unless `optional: true`; defaults belong only to required
attributes; null on an optional attribute means "no value" and is stored as
absence; and in expressions an unset optional attribute reads as null.

### Changed (breaking)

- **`required` removed; `optional` is the only presence flag.**
  `AttributeDefinition.optional` is now `bool = False`. Passing `required` is
  an error rather than being ignored — ignoring `required: false` would quietly
  turn an optional attribute into a required one. Replace `required=False` with
  `optional=True`, and drop `required=True`, which is the default
- **Defaults belong only to required attributes.** An optional attribute with a
  default now raises: a default is stored when an instance is created and would
  re-apply whenever the attribute is emptied. An explicit `default: null` also
  raises, told apart from an omitted default via `model_fields_set`
- **Null on an optional attribute is no longer stored.** At creation and on
  assignment it unsets the attribute. Null on a required attribute remains a
  validation error

### Added

- **An unset optional attribute reads as null in expressions**, so guards such
  as `{{ slot or 'none' }}` and `{{ slot is none }}` work instead of raising.
  Only declared, optional, non-derived attributes are filled: a misspelled name
  still raises, and a required attribute with no value is still an error
- `unset_as_null(data, attributes)` and `iter_leaf_attributes(attributes)` are
  exported, so code evaluating its own templates against model data (such as a
  flow engine) can apply exactly the same rule
- `ModelDefinition.to_dict()` emits only fields that were set, so a definition
  round-trips through `from_dict()`

### Fixed

- **Nested writes never recomputed their dependents.** After
  `model["power.score"] = 18`, the derived `power.modifier` kept its old value.
  Dependencies are recorded by top-level name and writes now trigger it
- **Nested writes were never validated.** `model["power.score"] = 99` was
  accepted against a range of `3..20`, because `get_attribute_definition` did
  not look inside groups
- **An absent group of optional leaves was reported as a missing required
  field.** A group has no value of its own; its leaves are now checked instead,
  and a missing required leaf is reported by its dotted path
- A derived field depending on an unset optional attribute is computed rather
  than skipped as having a missing dependency
- Removed an unreachable `"$"` key from the model's validation context (the
  0.4.0 cleanup missed this one)


## [0.4.0] - 2026-09-22

### Fixed

- **Anonymous nested attribute groups lost their leaf definitions**: a group
  declared inline with no `type` of its own (`power: {score: ..., modifier: ...}`)
  was stored as an opaque `type: dict` and every leaf definition was discarded,
  because `ModelDefinition.attributes` is typed `Dict[str, AttributeDefinition]`
  and Pydantic dropped the unknown keys. Leaf `derived`, `default`, `range` and
  `enum` were all silently ignored
  - The failure was silent, not loud: a model instantiated successfully with no
    derived leaves computed and out-of-range leaf values accepted
  - `AttributeDefinition` now carries an optional `attributes` map, so a group
    is an attribute that has attributes. Derived registration, defaults,
    validation and range resolution all recurse into groups
  - Validation errors name leaves by full dotted path (`hit_points.current`)
  - The runtime data shape is unchanged: groups remain plain dicts
- **Template expressions in `range` constraints were never resolved**:
  `RangeValidator` parses bounds with `float()` after splitting on `..`, so
  *every* relative range (`"0..{{ max_hp }}"`) failed as an invalid range
  specification. Ranges are now resolved against the current model data in
  `validate()`, after derived fields are computed, so a range may reference a
  derived attribute. An unresolvable range still fails loudly rather than
  becoming a skipped constraint
- **Jinja2 globals leaked into model expressions**: `range`, `dict`,
  `namespace`, `cycler`, `joiner` and `lipsum` were reachable from any
  expression, so a missing or misspelled attribute colliding with one resolved
  to the builtin instead of raising — `{{ range }}` rendered
  `"<class 'range'>"` onto the model. Globals are now cleared on the expression
  environment; filters are unaffected, and an attribute may be named `range`

### Removed

- **Dead `$` support in the derived-field resolver**: `$` is not a valid Jinja2
  identifier, so `{{ $.field }}` fails at parse time and could never have
  rendered. Only dependency extraction pretended to support it, producing graph
  edges for expressions that cannot execute. The `$var` syntax in
  `ModelContextTemplateResolver` is a separate, working feature and is unchanged

## [0.3.3] - 2025-10-12

### Fixed

- **Jinja2 Template Expression Type Preservation**: Fixed issue where Jinja2 template expressions containing `GrimoireModel` objects in data structures (lists, dicts) were being converted to string representations instead of preserving the actual object types
  - Pure expression templates (e.g., `{{ [item] }}`, `{{ inventory + [item] }}`, `{{ {'key': item} }}`) now use Jinja2's `compile_expression()` to preserve object types
  - This fix enables proper TTRPG workflows where items (GrimoireModel objects) can be added to character inventories using template expressions
  - Template expressions with text (e.g., `{{ name }} is level {{ level }}`) continue to work as before, returning strings
  - Arithmetic operations now return proper numeric types (e.g., `{{ 5 * 8 }}` returns `40` as int, not `"40"` as string)
  - Example:
    ```python
    # Previously BROKEN - returned string "[GrimoireModel(...)]"
    result = resolver.resolve_template("{{ inventory + [item] }}", context)
    # Now WORKS - returns actual list [GrimoireModel(...)]
    type(result)  # <class 'list'>
    ```

## [0.3.2] - 2025-10-12

### Added

- **Attribute-Style Access**: GrimoireModel objects now support both dictionary-style and attribute-style access patterns

  - Implemented `__getattr__()` method to enable attribute-style reads (e.g., `model.name`)
  - Implemented `__setattr__()` method to enable attribute-style writes (e.g., `model.name = "value"`)
  - Full compatibility with template engines like Jinja2, Django templates, etc.
  - `getattr()` now returns actual field values instead of defaults for model attributes
  - Both access patterns work seamlessly together - set via dict, read via attribute and vice versa
  - All validation and derived field updates work correctly with attribute access
  - Backward compatible - all existing dictionary-style code continues to work unchanged
  - Benefits:
    - **Template Engine Support**: `{{ model.field }}` syntax works in Jinja2 and other engines
    - **Standard Python Behavior**: Objects work like normal Python objects with dot notation
    - **IDE Support**: Better autocomplete and type checking potential
    - **Debugging**: More natural syntax for inspection (`print(obj.name)`)
    - **Interoperability**: Works with libraries expecting standard attribute access
  - Example:

    ```python
    character = create_model(character_def, {"name": "Hero", "level": 5})

    # All of these now work:
    print(character['name'])       # Dictionary-style (existing)
    print(character.name)          # Attribute-style (NEW)
    print(character.get('name'))   # Dict method (existing)
    print(getattr(character, 'name'))  # getattr (NEW - returns actual value)

    character['level'] = 10        # Dictionary-style assignment (existing)
    character.level = 10           # Attribute-style assignment (NEW)

    # Template engines now work seamlessly:
    template = Template("{{ character.name }} is level {{ character.level }}")
    result = template.render(character=character)
    ```

- **Custom Primitive Type Support**: New primitive type registry for domain-specific primitive types

  - Added `register_primitive_type()` function to register custom primitive types that should be treated as primitives rather than models
  - Custom primitives (e.g., `roll` for dice notation, `duration` for time periods) are now stored as raw values without model instantiation
  - New `PrimitiveTypeRegistry` class with thread-safe registration and management
  - Added global registry functions: `is_primitive_type()`, `unregister_primitive_type()`, `clear_primitive_registry()`
  - Updated `_is_custom_model_type()` to check both built-in and custom registered primitives
  - Supports optional validators for custom primitive types
  - Prevents registration of built-in primitives (int, str, float, bool, list, dict)
  - Example:

    ```python
    from grimoire_model import register_primitive_type

    # Register domain-specific primitive types
    register_primitive_type('roll')      # Dice roll notation
    register_primitive_type('duration')  # Time periods

    # Use in model definitions
    weapon_def = ModelDefinition(
        attributes={
            'damage': AttributeDefinition(type='roll')  # Works like str
        }
    )
    ```

  - Use cases: TTRPG systems (dice rolls, durations), business domains (currency, phone), scientific domains (measurements with units)

## [0.3.1] - 2025-10-11

### Fixed

- **Template Object Preservation**: Fixed `Jinja2TemplateResolver` converting objects to strings for dotted path templates ([#14](https://github.com/wyrdbound/grimoire-model/issues/14))
  - Simple variable references like `{{ outputs.knave }}` now return the actual object instead of string representation
  - Preserves `GrimoireModel` objects and other non-string types when resolving dotted path templates
  - Enhanced resolver to detect simple variable references and bypass Jinja2's string conversion
  - Maintains full Jinja2 functionality for complex template expressions
  - Fixes downstream processing errors where objects were expected but strings were received
  - Critical for object-oriented data flow in GRIMOIRE system flows

## [0.3.0] - 2025-10-10

### Added

- **Create Model Without Validation**: New `create_model_without_validation()` factory function for incremental object building

  - Allows creating GrimoireModel instances without immediate validation, enabling step-by-step construction
  - Added `skip_initial_validation` parameter to `GrimoireModel.__init__()`
  - Derived fields are still computed from available data, but missing dependencies are gracefully skipped
  - Validation can be explicitly called via `validate()` method when object construction is complete
  - Fully backward compatible - existing `create_model()` behavior unchanged
  - Use cases include workflow systems, form builders, data migration, and testing scenarios
  - Example:

    ```python
    # Create with partial data
    character = create_model_without_validation(char_def, {"name": "Hero"})

    # Build incrementally
    character["level"] = 5
    character["class"] = "warrior"

    # Validate when ready
    errors = character.validate()
    ```

## [0.2.3] - 2025-10-10

### Fixed

- Incorrect version number in grimoire-model package

## [0.2.2] - 2025-10-10

### Fixed

- **Nested Model Instantiation**: Fixed nested model types not being automatically instantiated as GrimoireModel objects
  - Custom model types in AttributeDefinition (e.g., `type="stat"`) are now recursively instantiated as GrimoireModel objects
  - Derived fields in nested models are computed correctly at all nesting depths
  - Template resolution now works properly with custom model types at any nesting depth (e.g., `{{ abilities.constitution.bonus }}`)
  - Namespace resolution works across nested models, supporting both same-namespace and cross-namespace references
  - Added comprehensive test coverage for 2-level and 3-level nesting scenarios

## [0.2.1] - 2025-10-01

### Added

- **Dict Type Inference**: Automatic inference of `type: dict` for nested attribute structures
  - When an attribute definition contains nested dictionaries with at least one having a `type` field, the parent attribute automatically infers `type: dict`
  - Allows intuitive nested attribute definitions like:
    ```yaml
    hit_points:
      max: { type: int }
      current: { type: int, range: "0..{{ this.hit_points.max }}" }
    ```
  - Works recursively for deeply nested structures
  - Explicit type declarations always take precedence
  - Empty dicts and dicts without typed nested attributes still require explicit `type` field

## [0.2.0] - 2025-09-12

### Changed

- **BREAKING**: Replaced internal logging system with grimoire-logging for flexible dependency injection
- Updated logging architecture to use grimoire-logging's LoggerProtocol and dependency injection
- Enhanced logging with appropriate INFO, DEBUG, WARNING, and ERROR level messages throughout the system
- Updated license from Proprietary to MIT License
- Updated contributing guidelines to welcome open source contributions

### Added

- Dependency on grimoire-logging package (>=0.1.0) for flexible logging capabilities
- New logging configuration examples (examples/05_logging_configuration.py) demonstrating:
  - Standard Python logging integration
  - Custom logger implementations with emojis and formatting
  - Structured JSON logging for modern logging systems
  - Message filtering and level management
  - Integration patterns with existing logging infrastructure
- Comprehensive logging documentation in LOGGING.md with:
  - Multiple configuration approaches (standard logging, dependency injection, adapters)
  - Integration examples for popular logging frameworks (structlog, loguru, rich)
  - Thread-safe logging management patterns
  - Performance considerations and best practices
- INFO level logging for successful model initialization
- Enhanced DEBUG logging for model registration, derived field computation, and system operations
- Support for runtime logger switching and configuration
- Thread-safe logger management capabilities

### Removed

- Legacy utils/logging.py module (replaced by grimoire-logging integration)

### Technical Changes

- Logger instances now use LoggerProtocol from grimoire-logging
- All logging calls updated to work with grimoire-logging's dependency injection system
- Added inject_logger and clear_logger_injection functions to public API
- Logging namespace remains 'grimoire_model' with hierarchical child loggers

## [0.1.0] - 2025-09-11

### Added

- Initial release of Grimoire Model system
- Dict-like interface with schema validation using Pydantic
- Reactive derived fields with automatic dependency tracking
- Model inheritance system with multiple inheritance support
- Template expressions using Jinja2 for dynamic field content
- Namespace-based model organization and global registry
- Custom validation rules and field validators
- Dependency injection system with pluggable resolvers
- Performance optimizations with batch updates and lazy evaluation
- Comprehensive logging system with configurable levels
- Template resolver for Jinja2-based field expressions
- Derived resolver for automatic field computation
- Path-based utilities for nested data access
- Exception handling with detailed error messages
- Support for Python 3.8+ with type hints
- Complete test suite with high coverage
- Documentation with examples and API reference
- Integration with grimoire-context for game state management

### Technical Features

- Pyrsistent-based immutable data structures
- Thread-safe operations
- YAML configuration support
- Comprehensive error handling and validation
- Modular architecture with pluggable components
