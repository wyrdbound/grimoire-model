# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed (breaking)

- **No silent keywords; `GrimoireModel` is unhashable.** `GrimoireModel.__init__`
  no longer accepts `**kwargs`, and `create_model` /
  `create_model_without_validation` accept only their documented arguments
  (`template_resolver_type`, `template_resolver`, `derived_field_resolver`,
  `instance_id`, `skip_initial_validation`, `template_resolver_kwargs`,
  `derived_resolver_kwargs`). An unknown keyword now raises `TypeError` naming
  it; before, a typo like `skip_initial_validaton=True` was silently ignored.
  `GrimoireModel.__hash__` is `None` (a mutable mapping must not be hashable;
  the old hash already raised for any model holding a dict or list). (R22, R23)
- **Storage is private; reads return copies.** No code path mutates a dict or
  list reachable from a previous `_data`: a dotted write (including the derived
  resolver's own nested writes) copies the containers on its path and shares
  everything else. `__getitem__` (and so `get`, `values`, `items`, attribute
  access) returns a `deepcopy` of a `dict`/`list` value and an independent
  `copy()` of a nested model, so a write through a value read earlier no longer
  reaches the model. `_apply_defaults` stores a `deepcopy` of the definition's
  default, so a mutable default is no longer shared by every instance. Callers
  that did `model["inventory"].append(x)` must write a new whole value or use a
  dotted path. (R14, D2)

### Removed (breaking)

- **`ValidationRule.severity` and `ValidationRule.fields` are gone.** Neither
  is in the GRIMOIRE specification. `fields` was never read, and `severity`
  silently behaved as `error` (a `warning` rule failed instantiation like any
  other). Every rule is an error. Passing either key now raises a
  `pydantic.ValidationError` naming the reason; a caller that passed
  `fields=[...]` must simply drop it. (R12)

### Changed (breaking)

- **`copy()` is independent.** A copy builds its own derived-field resolver (of
  the same kind — batched stays batched) and gets a new instance id. Previously
  it shared the original's resolver, so a later write to the original
  recomputed the copy's derived fields and left the original's stale. The copy
  is built in the original's validation mode. (R15)
- **`of` is a list-only field.** The spec defines it as the element type of a
  `list`; on any other type it is now a definition error rather than silently
  ignored. (R13)
- **`roll` and `roll_result` are basic types, and primitive validators run.**
  The spec's dice types (`model_spec.md`, "Basic Types") were resolved as model
  ids, and a validator passed to `register_primitive_type` was stored but never
  called. `roll` values must be strings; `roll_result` is not type-checked
  (its shape is the dice library's). A validator registered for any primitive
  — including `roll`/`roll_result` and custom types — is now called with the
  value and returns `(is_valid, message)`; a `False` result is a validation
  error, and a validator that raises is a validation error, not a crash.
  `register_primitive_type("roll")` and `("roll_result")` keep working; the six
  Python basic types are still refused. (R11)
- **One basic-type set, exact case; `any` removed.** A single `BASIC_TYPES`
  constant in `core/schema.py` (`int str float bool list dict`, plus `roll`
  and `roll_result` from T012) is used by the schema, model nesting, the
  primitive registry and `TypeValidator`. `type: any` is rejected at
  definition time naming the basic types (it was never instantiable with a
  value). `Int` (wrong case) is now a model id, so it fails loudly when it
  cannot be resolved instead of skipping type checks. (R09, R10)
- **Definitions are closed.** `AttributeDefinition`, `ModelDefinition` and
  `ValidationRule` reject unknown keys (`extra="forbid"`). A misspelled key
  such as `optinal: true`, `rnage: "1..3"` or `validatons:` is now a
  `pydantic.ValidationError` (or `ConfigurationError` inside a model), never a
  silent drop that leaves the attribute required and unconstrained. Free-form
  data belongs in `ModelDefinition.metadata`. `required` keeps its explanatory
  error. (R08)
- **Nothing but the model's data is in scope in an expression.** The derived
  and validation contexts no longer carry an instance-id key, so
  `{{ model.name }}` (or `{{ <instance_id>.name }}`) raises instead of
  resolving. An attribute named `model` is now an ordinary dependency, and an
  attribute named `round`, `max`, `sum`, `len`, `int` or `str` is tracked and
  recomputes dependents on write (they were wrongly skipped as builtins).
  (R05, R06)
- **A mixed template renders to text and stays text.** Only a template that is
  exactly one `{{ expression }}` keeps its value's type; `"[{{ a }}]"` with
  `a == 1` is the string `"[1]"`, not the list `[1]`. Rendered output was
  previously re-parsed with `json.loads` / `ast.literal_eval`, so text that
  merely looked like a literal changed type. (R04)
- **A mapping exposes its data, not its methods, in an expression.** In
  `x.name`, `name` is looked up as a key on a `dict` or `GrimoireModel` before
  anything else, so an attribute named `items`, `keys`, `values`, `get`,
  `copy`, `pop` or `update` is reachable. A name that is not a key is
  undefined, so `{{ g.values }}` and `{{ g.items() }}` raise rather than
  resolving to a bound method (a silent, wrong value). Use filters:
  `g | items | list`, `g | length`, `'k' in g`. (R03)
- **The expression environment is sandboxed.** Model definitions are content;
  once distributed they are third-party input. A plain Jinja2 `Environment`
  let an expression walk to arbitrary Python classes
  (`{{ ''.__class__.__mro__[1].__subclasses__() }}`). The resolver now builds a
  `jinja2.sandbox.SandboxedEnvironment`; filters are unchanged. (R02)
- **An expression that cannot be resolved raises.** A pure-expression template
  (`{{ ... }}`) was compiled with Jinja2's default `undefined_to_none=True`, so
  `{{ g.missing }}` — a misspelled nested leaf — returned `None` and the model
  instantiated, quietly wrong. Such an expression now raises
  `TemplateResolutionError`. An unset optional attribute still reads as `None`
  (that comes from `unset_as_null`, not from the undefined handling). (R01)

### Fixed

- **A write into a nested model-typed attribute builds the nested model.** An
  attribute whose `type` names a model (Knave's
  `abilities.constitution: {type: character_ability}`) was instantiated as a
  nested model only when supplied at construction. A write — a leaf
  (`model["abilities.constitution.bonus"] = 3`) or the whole slot
  (`model["abilities.constitution"] = {"bonus": 3}`) — stored a plain `dict`
  instead, so the nested model's derived fields never computed and a later
  dotted write into a built attribute raised
  `TypeError: Cannot access key ...: value is not a dictionary`. A dotted write
  now descends into (or builds) the nested model, and a whole-slot write builds
  it; both recompute the nested derived fields and the parent's dependants.
  Anonymous nested groups are unchanged: they remain plain dicts

- **`CachingTemplateResolver` is a real, thread-safe LRU.** It passed
  non-string inputs to its caches, raising `TypeError` where the wrapped
  resolver returns `False`; its "LRU" evicted oldest-inserted rather than
  least-recently-used; and it mutated two dicts with no lock. Non-strings now
  bypass the cache, the caches are `OrderedDict`s with `move_to_end` on a hit,
  and one lock guards both. (R07)

## [0.7.1] - 2026-09-25

### Fixed

- **A write to an attribute with a templated range works.** `validate()`
  resolved ranges such as `"0..{{ max_hp }}"` against the current data, but a
  single write (`model["current_hp"] = 5`, `model["hit_points.current"] = 3`)
  validated the raw range, so every such write failed as an invalid range
  specification, in range or not. The write now resolves the attribute's own
  range first; out-of-range values are still rejected

## [0.7.0] - 2026-09-24

### Removed (breaking)

- **`ModelContextTemplateResolver` and the `model_context` resolver type.**
  It resolved a `$var` substitution syntax that the GRIMOIRE specification
  does not have, and added `get_field` / `has_field` template globals that
  returned placeholders. `create_template_resolver("model_context")` and
  `create_model(..., template_resolver_type="model_context")` now raise
  `ValueError`; `"jinja2"` is the only resolver type. The base resolver no
  longer aliases a `"$"` context key to `_dollar`. Write derived expressions
  as Jinja2: `"{{ name }} (Level {{ level }})"`, not `"$name (Level $level)"`

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
