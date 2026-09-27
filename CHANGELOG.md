# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **The `_model` instance tag** (GRIMOIRE model spec, grimoire-spec 1.3.0,
  "Instances of Derived Models"). An instance of a model that extends another
  model records its own model id in its data under `_model`; an instance of a
  model with no `extends` carries none. The tag is set when the instance is
  built and is read-only (writing or deleting it raises). Where a model is
  declared, a mapping's `_model` chooses what is built: it must name the
  declared model or one that extends it, and a mapping without it is built as
  the declared model. So a weapon saved in an `of: item` inventory as plain
  data comes back as a weapon (Wyrdbound F62, part C2). Expressions can read
  it: `{{ inv | selectattr('_model', 'defined') | selectattr('_model',
  'equalto', 'weapon') | list }}`.

### Changed (breaking)

- **Instances of derived models carry `_model` in their data.** `dict(model)`,
  and anything serialized from it, now includes `_model: <id>` for an instance
  of any model with ancestors (flattened definitions included, via
  `ModelDefinition.ancestors`). Instances of root models are unchanged. Stored
  data containing such instances changes shape by that one key.
- **Attribute names beginning with `_` are reserved.** A definition declaring
  one, as a leaf or as a group, raises `ConfigurationError`. Rename it.

## [0.8.1] - 2026-09-26

### Fixed

- **A value typed as a model accepts a model that extends it.** 0.8.0 compared
  model ids exactly, so a `weapon` model (`extends: [item]`) was rejected in an
  `inventory: {type: list, of: item}` list, and as the value of a
  `type: item` attribute: *"must be a model of type 'item', got 'weapon'"*.
  The specification's own model example declares exactly that inventory next
  to exactly that weapon. A `GrimoireModel` is now accepted where its own model
  or any model it inherits from (directly or through its parents) is declared,
  and is kept as it is: a weapon in an inventory keeps its own attributes and
  derived fields. An unrelated model, or a parent where a child is declared, is
  still rejected. A plain mapping carries no type of its own and is still
  built as the declared model, so subtype *data* (a dict with `damage` under
  `of: item`) is still an undeclared-attribute error. Found by Wyrdbound (F62,
  part C1); a regression introduced by 0.8.0's R32/R33.

### Added

- **`ModelDefinition.ancestors`**, the ids of every model a definition inherits
  from, transitively, in `extends` order with each id once.
  `resolve_model_inheritance` records it on the flattened definition it
  returns, so lineage survives a definition being dumped, given
  `extends: []` and rebuilt (as Wyrdbound's `ModelCatalog` does). It is a
  library field, not a GRIMOIRE one; a definition may not list itself or
  repeat an id.
- **`GrimoireModel.is_a(model_id)`**: whether the model is `model_id` or
  inherits from it.

## [0.8.0] - 2026-09-26

### Removed (breaking)

- **`register_with_grimoire_context` is gone**, along with `__meta__` and the
  import-time auto-registration that called it. `grimoire-context` has no
  `register_dict_like_type`, so the function never did anything, and the
  `except Exception: pass` around it was a bare silent failure. `__meta__`
  duplicated `pyproject.toml` and had drifted. (R48)
- **`pyyaml` is no longer a dependency.** It was a runtime dependency but
  imported nowhere. (R47)
- **`ValidationRule.severity` and `ValidationRule.fields` are gone.** Neither
  is in the GRIMOIRE specification. `fields` was never read, and `severity`
  silently behaved as `error` (a `warning` rule failed instantiation like any
  other). Every rule is an error. Passing either key now raises a
  `pydantic.ValidationError` naming the reason; a caller that passed
  `fields=[...]` must simply drop it. (R12)

### Changed (breaking)

- **Model instantiation logs at `debug`; a template failure is raised, not
  logged.** Building a model logged an `info` line per instance, and every
  template resolution failure logged an `error` even when the caller handled it
  (`validate()`, incremental builds). The exception carries the message, so the
  `logger.error` is gone. (R50)
- **Python floor is 3.10.** `requires-python = ">=3.10"`, classifiers 3.10–3.12,
  mypy and ruff targets 3.10, CI and release matrices 3.10–3.12, README badge
  and Requirements 3.10+. The package did not import on 3.8 (`Mapping[str, Any]`
  evaluated at definition time); 3.9 is end-of-life and current mypy rejects it
  as a target. Callers on 3.8/3.9 must upgrade Python. (R46, D14)
- **The registry-analysis helpers accept a namespaced registry.**
  `validate_model_registry`, `check_inheritance_conflicts`,
  `build_inheritance_graph` and `find_inheritance_cycles` accept a
  `ModelRegistry` or a dict (plain id-keyed or namespaced) and resolve parents
  through the same namespace-local lookup as inheritance, instead of assuming
  id-keyed dicts. (R45)
- **Resolution registers nothing; duplicate registration is explicit.**
  `resolve_model_inheritance` builds the flattened definition with
  `model_copy(update=…)`, which does not register it, so resolving inheritance
  no longer writes a `default__<id>` entry. `ModelRegistry.register` treats an
  equal definition under an existing key as a no-op and raises `ValueError` for
  a different one (its documented contract), instead of silently overwriting.
  (R42)
- **Lookup is namespace-local; the registry is injectable.** A parent, a
  model-typed attribute and an `of` model type resolve in the requesting
  model's namespace first; another namespace is used only when exactly one has
  the id, and an ambiguous id raises naming every candidate key. `GrimoireModel`,
  `create_model` and `create_model_without_validation` take
  `registry=ModelRegistry()` (default: the global one), and nested models
  inherit it. `resolve_model_inheritance(definition, plain_dict)` keeps working.
  (R41, D10)
- **`extends` is resolved later-parent-wins, with real depth and full cycle
  detection.** Per the spec (`model_spec.md`, Inheritance Rules 4), "later
  models override fields from earlier ones": resolved(M) = merge of resolved(P1)
  … resolved(Pn) in `extends` order, then M's own attributes, each later source
  replacing an earlier attribute of the same name. The previous order was the
  reverse, so the earlier parent won. Validations accumulate in the same order,
  de-duplicated. A child of several parents that declare the same attribute now
  resolves by the spec's order. (R40, D11)
- **`max_depth` bounds the longest `extends` path, not the number of models
  visited; any reachable cycle raises.** A model with many parents each
  extending one base no longer trips the depth limit, and a cycle among a
  model's ancestors raises `InheritanceError` naming the cycle's ids in order
  (previously it was skipped). (R43, R44)
- **`pattern` is a full match.** `PatternValidator` uses `re.fullmatch`, so
  `pattern: "[a-z]+"` rejects `abc123!` (it previously used `re.match`, which
  anchors only the start). A caller whose pattern relied on prefix matching must
  anchor it or add the trailing wildcard. `pattern` is a library extension, not
  spec. (R37, D9)
- **One error per missing required attribute, and `enabled_validators=[]` runs
  none.** `TypeValidator` no longer reports a `None` value, so a missing
  required attribute is named once by `RequiredValidator`. `validate_field`
  treats `enabled_validators=None` as "all" and `[]` as "none". (R38, R39)
- **One range parser for numbers and lengths.** Every documented range form
  (`a..b`, `a..`, `..b`, `>=a`, `<=b`, `>a`, `<b`, `=a`, with optional spaces)
  is parsed by one function; `RangeValidator` (numbers) and `LengthValidator`
  (`len()` of `str`/`list`/`dict`) both use it. An unparseable range is now an
  error for every type, not a skipped check (previously `>=2` on a list and
  `a..b` on a string were silently ignored). A length bound must be a whole
  number. (R36)
- **A nested model inherits its parent's validation mode.** An incremental
  parent (`create_model_without_validation`) builds its nested models —
  top-level, group leaf, list element — incrementally too. A validated parent's
  `validate()` now includes each nested model's errors, prefixed with the path
  to it (`abilities.con.defense: ...`, `inv[0].w: ...`). (R35)
- **A model-typed attribute inside an anonymous group is built.** Construction
  walks every leaf (not just top-level attributes), so a model-typed leaf in a
  group gets its defaults, derived fields and validation; and a dotted write
  through a group into that model descends into it (F57's mechanism, reached
  through groups). (R34)
- **`of` is enforced, and model-typed list elements become models.** For
  `type: list, of: <basic type>`, each element is validated with an indexed
  path (`xs[1]`). For `type: list, of: <model id>`, each mapping element is
  built as that model (defaults, derived fields, validation), an element that
  is already a `GrimoireModel` of that id is kept, and anything else is
  rejected with `name[i]` in the error. Applies on build and on every write of
  the list. This changes what `dict(model)` holds for such lists — a data-shape
  change (D16); a serializer that deep-copies mappings (as Wyrdbound's does)
  treats them like nested models. (R33)
- **Groups and model-typed attributes must hold mappings.** An anonymous group
  given a non-mapping is an error (build and write), and a model-typed
  attribute must hold a mapping (built into the model) or a `GrimoireModel` of
  that type. A model of a different id raises. The model enforces this itself,
  keeping `TypeValidator` context-free (Principle IV). (R31, R32)
- **Batches are re-entrant; `get_derived_fields()` returns dotted paths.**
  `BatchedDerivedFieldResolver` keeps a depth counter: a `start_batch()` inside
  a batch no longer clears the outer batch's pending work, and only the
  outermost `end_batch()` recomputes. `get_derived_fields()` now returns every
  derived leaf's dotted path (`power.modifier`), not just top-level names.
  (R29, R30)
- **Every derived-field observer runs; the first exception re-raises.**
  `ObservableValue` no longer swallows an observer exception and logs it. All
  observers are called (over a copy, so one that removes itself does not skip
  the next); the first exception raised is re-raised afterwards. (R28)
- **Derived-value conversion is exact.** A derived `int` accepts an `int`, an
  integral `float` (`4.0`) or a string that parses to one — `{{ (s - 10) / 2 }}`
  with `s == 9` now raises instead of truncating to `0`; use `//`, `| round |
  int` or `| int`. `float` accepts numbers and numeric strings. `bool` accepts a
  bool or exactly `true/false/1/0/yes/no/on/off` (any case); anything else
  raises. `str` accepts scalars (not a dict or list). `None` stays `None` for
  every type. A bad value raises `ModelValidationError` naming the field and is
  never stored unconverted. (R27)
- **A derived recompute failure propagates.** `_update_dependent_fields` no
  longer catches every exception and logs it: a recompute failure raises
  `TemplateResolutionError`, and the write's transaction rolls back (R16). In an
  incremental model, a derived field whose dependency is no longer available is
  removed rather than left stale. `compute_all_derived_fields(
  skip_on_missing_dependencies=True)` skips only on a missing dependency; any
  other failure raises. (R26)
- **Derived-field dependencies use full reference paths.** A library function,
  `extract_reference_paths`, parses an expression with Jinja2 and returns every
  maximal dotted path (`p.mod`, `abilities.strength.bonus`, `xs`); the derived
  resolver records these, not top-level names, so nested derived fields
  compute in a deterministic dependency order instead of one that followed
  `PYTHONHASHSEED`. Two paths overlap when equal or one is a dotted prefix of
  the other; the topological sort breaks ties by sorted path. The injected
  resolver protocol is unchanged. (R25, D4)
- **Every public API on a model is thread-safe.** A per-model `threading.RLock`
  (re-entrant, so derived callbacks and nested writes re-enter) is held by
  every public read and write, `validate`, `copy`, `batch_update`,
  `__iter__` (over a snapshot of the keys), `__len__` and `__contains__`. The
  global `ValidationEngine`'s registration methods take a lock, and
  `validate_field` iterates a snapshot of the validators. (R24)
- **Undeclared keys are errors.** A key that is not declared is reported by
  `validate()`, and a write to an undeclared path raises
  `ModelValidationError`; a model built with one raises. Checked at the model
  root and inside anonymous groups, by full dotted path. A path into a nested
  *model* is that model's business; a `type: dict` attribute has no declared
  interior, so its keys are free-form. A misspelled key (`strenght`) is no
  longer stored silently. (R21, D6)
- **Derived attributes are not writable; `del` follows the write rules.**
  Writing a derived attribute raises `ModelValidationError` at any path.
  `del model[key]` unsets an optional attribute (exactly `model[key] = None`) and
  recomputes dependents; a required, readonly or derived attribute raises
  `ModelValidationError`; an undeclared or absent key raises `KeyError`. A
  dotted `del` into a plain `type: dict` attribute (no leaf definitions) is
  undeclared, so it raises; remove a key with a whole-value write. Readonly is
  now decided by the attribute definition at the full path, so a readonly leaf
  in a group can no longer be written. (R18, R19, R20)
- **`batch_update` is one transaction.** It stages every write, recomputes
  derived fields once, then validates every written leaf against the recomputed
  data, every recomputed derived field, and the model-level rules. A failure
  restores the model and raises. Before, each field was validated against stale
  derived values (so a valid batch could be rejected) and fields written before
  a failing one stayed written. (R17)
- **A write is a transaction.** A write now validates, applies, recomputes
  dependents, then validates every derived field it recomputed against its own
  constraints and — for a model built with validation — the model-level
  `validations`. A failure restores the model exactly and raises
  `ModelValidationError`, so a write can no longer leave a derived field out of
  range or a model-level rule broken. An incremental model
  (`create_model_without_validation`) checks the leaf and the recomputed derived
  fields; whole-model rules remain for an explicit `validate()`. Callers that
  relied on a write succeeding and reporting the violation at the next
  `validate()` now see the error at the write. (R16, D3)
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
