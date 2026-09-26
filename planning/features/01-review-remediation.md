# Review Remediation — make grimoire-model fail loudly again

**Status:** Designed. Not started. Blocked on the `fixNestedModelWrite` merge
(Wyrdbound finding F57); see the task list's T001.
**Companion specs:** `planning/features/README.md` (execution rules, L1–L4);
`AGENTS.md` (binding); the GRIMOIRE model specification,
`wyrdbound/grimoire` `spec/model_spec.md`; Wyrdbound's
`planning/features/02-spec-findings.md` (findings F35, F36, F47 and F57 concern
this library).
**Touches:** `src/grimoire_model/**`, `tests/**`, `examples/`, `README.md`,
`LOGGING.md`, `AGENTS.md`, `CHANGELOG.md`, `pyproject.toml`,
`.github/workflows/`.
**Does not touch:** the GRIMOIRE specification, the Wyrdbound repository,
`grimoire-context`, or the F57 fix on `fixNestedModelWrite` (it is merged
first and built on, never redone). If a task in this feature edits another
repository, the task is wrong.

---

## 1. Problem

A full review of `grimoire-model` 0.7.1 (`main` at `488625f`, reviewed
2026-09-26) found **50 defects**. Every one in §3 was reproduced by running
code against 0.7.1, not inferred from reading it; the reproduction is given
with each.

They cluster. The library's first principle — *a model that instantiates
successfully and is quietly wrong is the failure this library must never
produce* (`AGENTS.md` Principle I) — is violated in roughly twenty places:

- **Expressions.** A misspelled nested name evaluates to `None` instead of
  raising. An attribute named `round` or `max` is never tracked as a
  dependency. `{{ bag.items }}` reaches the dict method, not the data. The
  evaluation environment is not sandboxed, so model definitions — third-party
  content once GRIMOIRE systems are distributed — can reach
  `''.__class__.__mro__[1].__subclasses__()`.
- **Definitions.** A misspelled key (`optinal: true`, `rnage: "1..3"`,
  `validatons:`) is silently dropped, so an attribute its author meant to be
  optional is required and a declared range does not exist.
- **Storage and writes.** Reads hand out the model's live dicts, so a write
  through them bypasses validation, and a reference taken earlier changes under
  its holder. `default: []` is one list shared by every instance. `copy()`
  shares its derived-field resolver with the original, so writes to the
  original recompute *into the copy*. A write can leave the model violating a
  derived field's range or a model-level `validations` rule; `batch_update`
  validates against stale derived values and is not atomic; derived fields are
  writable; `del` removes readonly and required attributes and leaves their
  dependents stale; undeclared keys are accepted.
- **Derived fields.** Nested derived fields compute in an order that depends on
  `PYTHONHASHSEED`: the same model builds on one run and raises on the next. A
  derived field that fails to recompute on write keeps its old value
  silently. `int` conversion truncates toward zero, so a D&D-style
  `(score - 10) / 2` gives `0` for a 9, not `-1`.
- **Types.** A group or model-typed attribute given `5` is accepted. `list`'s
  `of` is ignored entirely. The spec's own basic types `roll` and
  `roll_result` are unknown. Length constraints written as `>=2` are silently
  skipped.
- **Inheritance.** `extends` precedence is the reverse of the spec's. Parents
  and model types are resolved from whichever namespace was registered first.
  Resolving inheritance registers a flattened copy in the `default` namespace.
- **Packaging.** The package declares Python 3.8+, and fails to import on 3.8.

None of these is exotic. Several are exactly the failure modes `AGENTS.md`
already names as having happened once (Principles I, II, VI). The fix is not a
rearchitecture: it is making each path do what the principles already say.

## 2. What we are building on

- **State at review:** 369 tests passing, 90% line coverage, ruff and mypy
  clean, all seven `examples/` running. The suite is green because it does not
  test the failures below — each task in the list adds the test that would
  have caught its defect.
- **In flight:** `fixNestedModelWrite` (`8b76af2`) fixes Wyrdbound F57 — a
  dotted write through a **top-level** model-typed attribute now builds and
  descends into the nested model. It does not reach a model-typed attribute
  **inside an anonymous group** (R34), nor list elements (R33). Both extend its
  mechanism; neither replaces it.
- **Open Wyrdbound findings folded in:** F35 (cross-namespace parent lookup,
  silent duplicate registration) → R41, R42. F36 (live storage from
  `__getitem__`) → R14. F47 (`roll` treated as a model id; primitive
  validators never called) → R11. Each was recorded as "not changed without
  Justin's go-ahead"; **approving this feature is that go-ahead**, and the
  choices it needs are listed as decisions in §6.
- **Wyrdbound is the main consumer.** Its `ModelCatalog`
  (`engine/src/wyrdbound_engine/systems/models.py`) passes GRIMOIRE attribute
  declarations to `ModelDefinition.model_validate` as parsed, calls
  `resolve_model_inheritance` with a plain id-keyed dict, and registers `roll`
  and `roll_result` with `register_primitive_type`. All three must keep
  working; §6 says how each decision affects it.

## 3. Findings register

Severity: **High** — silently wrong data, a security exposure, or a
nondeterministic failure. **Medium** — wrong behaviour that raises, or wrong
only on a plausible edge. **Low** — hygiene, drift or noise.

Reproductions assume `from grimoire_model import *` and a definition built with
`ModelDefinition(id=…, name=…, attributes=…)`; `R` is
`create_template_resolver()`.

### 3.1 Expressions (`resolvers/template.py`, dependency extraction)

| # | Finding | Sev. | Reproduction on 0.7.1 | Task |
| --- | --- | --- | --- | --- |
| R01 | A missing nested name evaluates to `None`. The pure-expression path uses `compile_expression`, whose default `undefined_to_none=True` turns a `StrictUndefined` result into `None`; the pre-check only looks at top-level names. | High | `R.resolve_template("{{ g.missing }}", {"g": {"a": 1}})` → `None`. A derived `{{ g.xx }}` (misspelled leaf) stores `y: None` and the model instantiates. | T003 |
| R02 | The Jinja2 environment is not sandboxed. Model definitions are content; an expression can walk to arbitrary classes. | High | `R.resolve_template("{{ ''.__class__.__mro__[1].__subclasses__() \| length }}", {})` → `520`. | T004 |
| R03 | Dotted access prefers Python attributes over data. Jinja2's `getattr` finds `dict.items` / `GrimoireModel.items` before the key, and the resolver's fast path finds the key — so the two paths disagree. Attributes named `items`, `keys`, `values`, `get`, `copy`, `pop`, `update`, `validate` are unreachable in expressions. | High | `{{ g.items }}` with `{"g": {"items": 3}}` → `3`, but `{{ g.items + 1 }}` → `TypeError` (method + int). A nested model with `items: list` and derived `{{ bag.items \| length }}` fails to build. | T005 |
| R04 | A mixed template's rendered text is re-parsed with `json.loads` / `ast.literal_eval`, so text that looks like a literal changes type. | Medium | `R.resolve_template("[{{ a }}]", {"a": 1})` → the list `[1]`, not the string `"[1]"`. | T006 |
| R05 | Dependency extraction skips the names `sum max min len abs round int float str bool` — a leftover from the builtin injection removed in 0.6.0. An attribute with one of those names is never a dependency. | High | `round: int`, `y: {derived: "{{ round * 2 }}"}`; set `round` 1 → 5; `y` stays `2`. | T007 |
| R06 | An undocumented instance prefix is in scope. The derived context carries `{instance_id: data}`, and `create_model` builds the derived resolver with `instance_id="model"`, so `{{ model.name }}` resolves. The same name is then dropped from dependency tracking. Principle II: "Do not add an instance prefix." | Medium | `n2: {derived: "{{ model.name }}"}` computes. With an attribute named `model`, `y = {{ model + 1 }}` stays `2` after `model` 1 → 5. | T007 |
| R07 | `CachingTemplateResolver` mutates two dicts with no lock (L4), raises `TypeError` on an unhashable input where the wrapped resolver returns `False`, and its "LRU" is FIFO. | Low | `R.is_template(["x"])` → `TypeError: unhashable type: 'list'`. | T008 |

### 3.2 Definitions (`core/schema.py`)

| # | Finding | Sev. | Reproduction on 0.7.1 | Task |
| --- | --- | --- | --- | --- |
| R08 | Unknown keys in a definition are ignored (Pydantic's default `extra="ignore"`) on `AttributeDefinition`, `ModelDefinition` and `ValidationRule`. Only `required` is special-cased. | High | `{"slot": {"type": "str", "optinal": True}, "lvl": {"type": "int", "rnage": "1..3"}}` with `validatons=[…]` defines cleanly: `slot` is required, `lvl` has no range, the rules are gone; `{"lvl": 99}` instantiates. | T010 |
| R09 | `type: any` passes schema validation and `TypeValidator`, but instantiation treats `any` as a model id. `any` is not a GRIMOIRE type. | Medium | `{"x": {"type": "any"}}` with `{"x": 3}` → `ModelValidationError: Invalid model type 'any'`. | T011 |
| R10 | Basic type names are compared case-insensitively in one place (`_is_custom_model_type` lowercases) and exactly in another (`TypeValidator`), so `Int` is neither a model nor type-checked. | Medium | `{"x": {"type": "Int"}}` accepts `{"x": "not an int"}`. | T011 |
| R11 | The spec's basic types `roll` and `roll_result` (`model_spec.md`, "Basic Types") are resolved as model ids, and a validator passed to `register_primitive_type` is stored but never called. Wyrdbound F47. | High | `{"dmg": {"type": "roll"}}` with `"1d6"` → `Invalid model type 'roll'`. `register_primitive_type("dur", validator=lambda v: (False, "never"))` then `{"t": 5}` instantiates. | T012 |
| R12 | `ValidationRule.severity` is ignored — a `"warning"` rule fails instantiation like an error — and `ValidationRule.fields` is never read. Neither is in the spec. | Medium | A rule with `severity: "warning"` that evaluates false → `ModelValidationError` at `create_model`. | T013 |
| R13 | `of` is accepted on any type; the spec defines it for lists only. | Low | `{"d": {"type": "int", "of": "str"}}` defines cleanly. | T014 |

### 3.3 Storage and writes (`core/model.py`)

| # | Finding | Sev. | Reproduction on 0.7.1 | Task |
| --- | --- | --- | --- | --- |
| R14 | Storage is not private. `_data` is a `pmap`, but its values are the model's own mutable dicts and lists: `__getitem__` hands them out (F36), dotted writes mutate them in place, and `_apply_defaults` stores the definition's default object itself. | High | (a) `m["g"]["x"] = 99` against `range: 1..5` is accepted. (b) `old = m["g"]; m["g.x"] = 2` changes `old`. (c) `default: []`: `m1["tags"].append("x")`; a new instance starts with `["x"]`, and so does the definition's default. | T017 |
| R15 | `copy()` passes the original's derived-field resolver and instance id to the copy. The resolver is re-pointed at the copy's data and callback, so the original's later writes recompute into the copy and the original's derived fields go stale. | High | `b = {{ a * 2 }}`; `c = m.copy(a=5)`; `m["a"] = 10` → `m` is `{a: 10, b: 2}`, `c` is `{a: 5, b: 20}`. | T016 |
| R16 | A write validates only the written leaf. Derived fields it recomputes are not checked against their own constraints, and model-level `validations` are not run. | High | `b: {range: "0..10", derived: "{{ a * 2 }}"}`; `m["a"] = 50` succeeds, `b` is 100. With rule `a <= b`, `m["a"] = 50` succeeds and `validate()` then reports the violation. | T020 |
| R17 | `batch_update` validates each field in turn against *stale* derived values, and is not atomic: fields written before a failing one stay written. | High | `hp.max = {{ level * 10 }}`, `hp.cur: range "0..{{ hp.max }}"`: `batch_update({"level": 10, "hp.cur": 50})` raises "above maximum 10". `batch_update({"a": 2, "b": 99})` with `b: 0..5` raises and leaves `a == 2`. | T021 |
| R18 | Derived attributes are writable. The written value stands until something triggers a recompute. | High | `m["b"] = 100` where `b = {{ a + 1 }}` → stored. | T022 |
| R19 | `__delitem__` bypasses every rule: it deletes readonly attributes (which can then be rewritten) and required attributes, and does not recompute dependents. | High | `del m["id"]; m["id"] = "changed"` succeeds on a readonly `id`. `del m["a"]` leaves `b = {{ a + 1 }}` at its old value. | T022 |
| R20 | Readonly is checked with `key in self._data`, which is never true for a dotted key, so a readonly leaf in a group is writable. | Medium | `g.k: {readonly: true, default: "a"}`; `m["g.k"] = "b"` succeeds. | T022 |
| R21 | Undeclared attributes are accepted on build and write, and `validate()` does not report them — a misspelling is stored silently. | High | `create_model(d, {"strength": 1, "strenght": 5})`; `m["dexterity"] = "x"`; `validate()` → `[]`. | T023 |
| R22 | `GrimoireModel.__init__(**kwargs)` accepts and ignores any keyword, and the factories forward theirs to it. The README documents a `derived_field_resolver_type` argument that does not exist; passing it is silently ignored. | Medium | `create_model(d, {}, skip_initial_validaton=True)` (typo) runs validation. | T018 |
| R23 | `GrimoireModel` defines `__hash__` on a mutable mapping (its hash changes when it is written), and the hash raises for any model holding a dict or list. | Medium | `hash(create_model(d, {"g": {"a": 1}}))` → `TypeError: unhashable type: 'dict'`. | T018 |
| R24 | No public API on a model is thread-safe (`AGENTS.md` AI Guidance §10). Every write is read-copy-replace of `_data` with no lock. | High | 8 threads × 300 writes to distinct fields, `sys.setswitchinterval(1e-6)`: a final value is lost in about 1 of 240 fields. | T024 |

### 3.4 Derived fields (`resolvers/derived.py`)

| # | Finding | Sev. | Reproduction on 0.7.1 | Task |
| --- | --- | --- | --- | --- |
| R25 | Dependencies are recorded by top-level name only, so the topological sort cannot order derived fields relative to nested derived fields. Order then follows `set` iteration — i.e. `PYTHONHASHSEED`. | High | `p.mod = {{ p.score // 2 }}`, `total = {{ p.mod + 100 }}`, `create_model(d, {"p": {"score": 10}})`: builds under `PYTHONHASHSEED=0`, raises `'dict object' has no attribute 'mod'` under `PYTHONHASHSEED=1`. | T026 |
| R26 | `_update_dependent_fields` catches every exception from a recompute and logs it at debug level; the dependent keeps its old value. A dependent whose dependency has gone missing is skipped, also keeping its old value. | High | `q = {{ a / b }}`; `m["b"] = 0` succeeds and `q` stays `1.0`. | T027 |
| R27 | Derived-value conversion is lossy and silent. `int` truncates toward zero (`int(-0.5) == 0`); `str` stringifies `None` and containers; `bool` maps any unrecognised string to `False`; a failed conversion stores the raw value unvalidated. | High | `mod = {{ (s - 10) / 2 }}` (`int`) with `s = 9` → `0` (floor is `-1`). `i: int = {{ s }}`; `m["s"] = "abc"` → stores `i = "abc"`. | T028 |
| R28 | `ObservableValue` catches every observer exception and logs it; a failing observer is invisible to the writer. Observers are Wyrdbound's commit channel. | Medium | An observer that raises: the write succeeds and nothing propagates. | T029 |
| R29 | `start_batch()` clears pending updates, so a batch started inside a batch discards the outer batch's work. | Medium | `start_batch(); write a; start_batch(); write b; end_batch(); end_batch()` → `a2` (derived from `a`) never recomputes. | T030 |
| R30 | `GrimoireModel.get_derived_fields()` returns top-level names only (Principle III: anything that walks attributes must recurse into groups). | Low | `p.m = {{ p.s }}` → `get_derived_fields()` is `set()`. | T030 |

### 3.5 Types and validation (`validation/validators.py`, `core/model.py`)

| # | Finding | Sev. | Reproduction on 0.7.1 | Task |
| --- | --- | --- | --- | --- |
| R31 | An anonymous group given a non-mapping is accepted: the validator only descends into dict values and `continue`s past anything else. | High | `g: {x: {type: int}}` with `{"g": 5}` instantiates. | T032 |
| R32 | A model-typed attribute given a non-mapping is accepted: `TypeValidator` passes every non-basic type, and nesting only builds from dicts. | High | `w: {type: weapon}` with `{"w": 5}` instantiates. | T032 |
| R33 | `of` is ignored: list elements are never validated, and elements of a model type are never built (no defaults, no derived fields). | High | `xs: {type: list, of: int}` accepts `["a", None]`; `inv: {type: list, of: item}` keeps `{"w": "heavy"}` as a plain dict with `item.w: int` and a derived field missing. | T033 |
| R34 | A model-typed attribute **inside an anonymous group** is never built. `_instantiate_nested_models` walks top-level attributes only, and F57's write path descends from a top-level head only. | High | `abilities: {con: {type: abil}}` with `abil.defense = {{ bonus + 10 }}` → `{"abilities": {"con": {"bonus": 3}}}`, no `defense`. | T034 |
| R35 | Incremental building fails for nested models: `create_model_without_validation` builds nested models *with* validation. | Medium | Optional `w: {type: sword}` (`sword.name` required); `create_model_without_validation(d, {"w": {}})` → `ModelValidationError` for `name`. | T035 |
| R36 | `LengthValidator` understands only `min..max`; any other range form on a `str`, `list` or `dict` — and any unparseable range — is skipped, because `RangeValidator` ignores non-numbers. | High | `xs: {type: list, range: ">=2"}` accepts `[]`; `s: {type: str, range: "a..b"}` accepts anything. | T036 |
| R37 | `pattern` uses `re.match`, which anchors only the start: a prefix match passes. | Medium | `pattern: "[a-z]+"` accepts `"abc123!"`. | T037 |
| R38 | A missing required attribute is reported twice (`RequiredValidator` and `TypeValidator`). | Low | `validate()` → `["Required field 'a' is missing", "Required field 'a' cannot be None"]`. | T037 |
| R39 | `enabled_validators=[]` runs every validator (`[] or all`). | Low | `validate_field_value("x", "f", AttributeDefinition(type="int"), enabled_validators=[])` → a type error. | T037 |

### 3.6 Inheritance and lookup (`utils/inheritance.py`, `core/registry.py`)

| # | Finding | Sev. | Reproduction on 0.7.1 | Task |
| --- | --- | --- | --- | --- |
| R40 | `extends` precedence is inverted. The spec: "Later models override fields from earlier ones" (`model_spec.md`, Inheritance Rules 4). The library applies parents in reverse, so the **earlier** parent wins. The docstring's "C3 linearization" is a breadth-first walk. | High | `pb.x` default `"B"`, `pc.x` default `"C"`, `kid: extends [pb, pc]` → `x == "B"`. | T039 |
| R41 | Parents, and model types of attributes, are found by key suffix across every namespace, first registered wins (F35). | High | `qs.item` then `knave.item` registered; `knave.weapon extends [item]` gets `qs.item` (`cost`, not `slot_cost`). A `knave` model's `type: stat` resolves `qs.stat`. | T041 |
| R42 | Resolving inheritance constructs a flattened `ModelDefinition`, which registers itself — in the `default` namespace, whatever the child's namespace — overwriting any real `default` model of that id. Duplicate registration overwrites with a warning although `register`'s docstring says it raises (F35). | Medium | After instantiating `knave.weapon`, the registry holds `knave__weapon` **and** `default__weapon`. | T042 |
| R43 | `max_depth` counts processed nodes, not depth. | Medium | A model extending ten parents, each extending one base (depth 2), → "Maximum inheritance depth (10) exceeded". | T040 |
| R44 | Only a cycle through the model being resolved is detected; a cycle among its ancestors is skipped. | Medium | `cy1 ↔ cy2`, `cyc extends [cy1]` → `cyc` instantiates. | T040 |
| R45 | `validate_model_registry`, `check_inheritance_conflicts`, `build_inheritance_graph` and `find_inheritance_cycles` assume id-keyed dicts; given the registry's namespaced keys they report every parent unknown or raise. | Low | `validate_model_registry(get_default_registry().get_registry_dict())` → `KeyError`. | T043 |

### 3.7 Packaging, documentation, hygiene

| # | Finding | Sev. | Reproduction on 0.7.1 | Task |
| --- | --- | --- | --- | --- |
| R46 | `requires-python = ">=3.8"` (and classifiers, README badge), but the package does not import on 3.8 (`Mapping[str, Any]` evaluated at definition time). CI tests 3.11–3.12 only. mypy's `python_version = "3.9"` is rejected by current mypy. | Medium | Python 3.8: `import grimoire_model` → `TypeError: 'ABCMeta' object is not subscriptable`. | T044 |
| R47 | `pyyaml` is a runtime dependency and is imported nowhere. | Low | `grep -rn yaml src/` finds only `__meta__`. | T045 |
| R48 | `__init__.py`'s `__meta__` duplicates `pyproject.toml` and has drifted (no `grimoire-logging`; lists `black`). The import-time auto-registration calls `GrimoireContext.register_dict_like_type`, which does not exist in `grimoire-context`, inside a bare `except Exception: pass`. | Low | `grep register_dict_like_type` in `grimoire-context/src` → nothing. | T045 |
| R49 | `README.md` documents APIs that do not exist (`set`, `has`, `delete`, `derived_field_resolver_type="batched"`), types `enum` as `List[Any]` (it is `List[str]`), and claims immutable storage (R14). | Medium | Compare README "API Reference" to `core/model.py`. | T047 |
| R50 | Logging is noisy at the wrong levels: `info` for every model instantiated, `error` for every template failure, including those the caller handles (`validate()`, incremental builds). | Low | Build 1,000 models → 1,000 `info` lines. | T046 |

## 4. The fixes

### 4.1 Expressions raise, are sandboxed, and see only data (US1)

- **An unresolvable expression raises** (R01). Evaluate pure expressions with
  `undefined_to_none=False` and treat an `Undefined` result as a resolution
  error. The top-level-names pre-check and its render fallback become
  unnecessary.
- **The environment is a `jinja2.sandbox.SandboxedEnvironment`** (R02), with
  globals still cleared. Filters are unchanged.
- **Data before methods** (R03). The environment overrides `getattr` so that,
  for a `Mapping` (plain dict or `GrimoireModel`), `x.name` looks up the key
  first and falls back to attribute access only when there is no such key.
  The fast path and the Jinja2 path then agree by construction.
- **Mixed templates are strings** (R04). Only a template that is exactly one
  `{{ expression }}` keeps its value's type; anything else renders to text and
  stays text. This is the rule Wyrdbound already adopted (its F34).
- **Nothing is in scope but the model's data** (R05, R06). The derived and
  validation contexts contain the data and nothing else — no instance-id key.
  Dependency extraction keeps every name the expression references.
- **The caching wrapper is locked, passes non-strings through, and is a real
  LRU** (R07).

### 4.2 Definitions mean what they say (US2)

- **Definitions are closed** (R08): `extra="forbid"` on `AttributeDefinition`,
  `ModelDefinition` and `ValidationRule`. `required` keeps its explanatory
  error. Free-form data belongs in `ModelDefinition.metadata`, which exists for
  it.
- **One basic-type set** (R09, R10): a single `BASIC_TYPES` constant in
  `core/schema.py` — `int str float bool list dict roll roll_result`, exact
  case — used by the schema, nesting, the primitive registry and
  `TypeValidator`. `any` is removed (D7).
- **Spec primitives are built in, and primitive validators run** (R11). `roll`
  is a string; `roll_result` is not type-checked (its shape belongs to the
  dice library). A validator registered for any primitive — including `roll`
  and `roll_result` — is called with the value and returns
  `(is_valid, message)`; a false result is a validation error.
  `register_primitive_type("roll")` keeps working.
- **`severity` and `fields` are removed from `ValidationRule`** (R12, D8).
- **`of` is a list-only field** (R13).

### 4.3 Storage is private; writes are transactions (US3)

- **Copy-on-write storage** (R14). No code path mutates a dict or list that is
  reachable from a previous `_data`; a dotted write copies the containers on
  its path. Reads return copies (D2). Defaults are deep-copied when applied.
- **`copy()` is independent** (R15, D12): a fresh derived-field resolver of the
  same kind and a new instance id.
- **A write is a transaction** (R16, D3). `_set_with_validation` takes a
  snapshot (cheap once storage is copy-on-write), applies the write,
  recomputes dependents, then validates: the written leaf; every derived field
  the write recomputed, against its own constraints; and — for a model that was
  built with validation — the model-level `validations`. Any failure restores
  the snapshot (data and the resolver's view) and raises
  `ModelValidationError`.
- **`batch_update` is one transaction** (R17): stage every write, recompute
  once, validate once, commit or restore.
- **The write rules** (R18–R20): writing a derived attribute raises; readonly is
  checked by definition for any path; `del model[key]` unsets an optional
  attribute (exactly `model[key] = None`) and raises for a required, readonly
  or derived one.
- **Undeclared keys are errors** (R21, D6): on build, on write, and in
  `validate()`, at every group depth. A path into a nested *model* is that
  model's business.
- **No silent keywords, no hash** (R22, R23, D13).
- **Thread safety** (R24): a per-model `threading.RLock` around every public
  read, write, `validate`, `copy` and iteration (iteration walks a snapshot).
  The global `ValidationEngine`'s registration methods take a lock.

### 4.4 Derived fields compute in order, exactly, loudly (US4)

- **Dependencies by full path** (R25, D4). A library function in
  `resolvers/template.py` parses an expression with Jinja2 and returns every
  maximal dotted reference path (`p.mod`, `abilities.strength.bonus`, `xs`).
  Derived field D depends on derived field E when their paths overlap — one is
  equal to, or a dotted prefix of, the other. A write to a path triggers every
  derived field whose dependencies overlap it. The injected resolver's
  `extract_variables` is untouched (L3).
- **Recompute failures propagate** (R26) and, through §4.3, roll the write
  back. In an incremental model, a derived field whose dependency is no longer
  available is removed, never left stale.
- **Exact conversion** (R27): `int` accepts an `int`, an integral `float`
  (`4.0`), or a string that parses to one; anything else raises. `float`
  accepts numbers and numeric strings. `bool` accepts `bool` and exactly
  `true/false/1/0/yes/no/on/off` (any case); anything else raises. `str`
  accepts scalars. `None` stays `None` for every type.
- **Observers** (R28): every observer is called; if any raised, the first
  exception is re-raised after the last observer has run.
- **Re-entrant batches** (R29): a depth counter; only the outermost
  `end_batch()` recomputes. **`get_derived_fields()`** returns dotted paths
  (R30).

### 4.5 Values match their declared types (US5)

- **Groups hold mappings; model-typed attributes hold mappings or models of
  that type** (R31, R32), on build and write.
- **`of` is enforced** (R33): primitive elements are validated with indexed
  paths (`xs[1]`); model-typed elements are built as models (defaults, derived
  fields, validation), exactly as a top-level model-typed attribute is (D16).
- **Models inside groups are built** (R34) on build, and a dotted write through
  a group into a model-typed leaf descends into it — F57's mechanism, reached
  through groups.
- **Nested models inherit the parent's validation mode** (R35).
- **One range parser** (R36) shared by the numeric and length validators,
  accepting every documented form (`a..b`, `a..`, `..b`, `>=`, `<=`, `>`, `<`,
  `=`); an unparseable range is an error for every type.
- **`pattern` is a full match** (R37, D9). One message per missing required
  attribute (R38). `enabled_validators=[]` runs none (R39).

### 4.6 Inheritance and lookup follow the spec (US6)

- **Later parents win** (R40, D11): resolved(M) = merge(resolved(P1), …,
  resolved(Pn), own(M)), depth-first in `extends` order; validations accumulate
  in the same order, de-duplicated.
- **Real depth, every cycle** (R43, R44).
- **Namespace-local lookup, injectable registry** (R41, D10): `GrimoireModel`
  and both factories accept `registry=` (default: the global one). Parents,
  model-typed attributes and `of` model types resolve in the model's own
  namespace first; another namespace is used only when exactly one namespace
  has the id, and an ambiguous id raises naming every candidate.
  `resolve_model_inheritance(definition, plain_dict)` keeps working.
- **Resolution registers nothing; duplicates are explicit** (R42): the
  flattened definition is built without registering; `register` of a
  *different* definition under an existing key raises `ValueError` (its
  docstring's contract), and of an equal one is a no-op.
- **The registry-analysis helpers accept namespaced registries** (R45).

### 4.7 The package tells the truth (US7)

Python floor 3.10 everywhere it is stated, and tested (R46, D14); `pyyaml`
removed (R47); `__meta__` and the dead auto-registration removed (R48);
logging levels corrected (R50); README, examples, `LOGGING.md` and `AGENTS.md`
reconciled with the code (R49); released as 0.8.0 (D1).

## 5. What must ship

1. Every finding R01–R50 fixed, each with a test that fails on 0.7.1 for the
   reason in §3.
2. The full suite green under eight `PYTHONHASHSEED` values, coverage ≥ 90%,
   all examples running, the quality gate clean.
3. `CHANGELOG.md` 0.8.0 section listing every change, with every breaking one
   saying what a caller must now do.
4. `README.md`, `LOGGING.md`, `AGENTS.md` and `examples/` matching the code.
5. The §7 spec findings, and the list of Wyrdbound findings this release
   resolves, in the release commit message for Justin to carry across.

## 6. Decisions

| # | Decision | Rationale | Effect on Wyrdbound |
| --- | --- | --- | --- |
| D1 | One release, **0.8.0**, at the end of the list. | Many fixes are breaking; in 0.x a minor bump records that. One version per task would mark releases nobody publishes. | Pin `>=0.8.0` after running its suite. |
| D2 | **Reads return copies**: containers deep-copied, nested models as independent copies. Writes go through dotted paths. | F36's proposal ("a read-only view or a copy"). A copy is the simpler of the two and keeps `list`/`dict` types for serializers; recursive read-only views would change types. Internal reads (contexts, validation) do not go through `__getitem__` and pay nothing. | Already writes through dotted paths (its T016). |
| D3 | **Writes are transactions.** Validated models check model-level `validations` on every write; incremental models (`create_model_without_validation`) check the leaf and the derived fields the write recomputed, and leave whole-model rules to an explicit `validate()`. | Principle I. Incremental building must stay possible, and a rule over required attributes cannot pass mid-build. | Invalid writes now raise at the write, not at the next `validate()`. |
| D4 | **Dependencies by reference path, extracted by a library function** that parses Jinja2 directly. | Principle II fixes the syntax as Jinja2, so parsing it is not resolver-specific; the protocol stays as Wyrdbound implements it (L3). | None. |
| D5 | **Definitions are closed** (`extra="forbid"`). | Principle I: `optinal: true` silently making an attribute required is the worst kind of wrong. | Its `translate_model` passes GRIMOIRE attribute declarations through as parsed. **Confirm no shipped system carries keys outside the spec's attribute fields** before T010 (Input gap 2). |
| D6 | **Undeclared data keys are errors.** | Principle VI already says a misspelling must raise in expressions; storage should agree. | Confirm no flow writes an undeclared path (its golden transcripts will show it). |
| D7 | **Basic types are exactly the spec's**; exact case; `any` removed. | `any` has never been instantiable with a value (R09), so no working caller depends on it. | Its `SPEC_PRIMITIVES` registration keeps working and becomes redundant. |
| D8 | **`severity` and `fields` removed** from `ValidationRule`. | Not GRIMOIRE; `fields` never read; `severity` silently treated as `error`. Implementing warnings is a feature nobody has asked for. | Passes only `expression` and `message`. |
| D9 | **`pattern` is a full match.** | "Matches the pattern" reads as the whole value; `re.match` accepts `abc123!` for `[a-z]+`. `pattern` is a library extension, not spec. | No shipped system uses `pattern`. |
| D10 | **Lookup is namespace-local**, falling back to another namespace only on a unique match; ambiguity raises. Registry injectable. | F35's proposal, made deterministic. Refusing all cross-namespace references would break single-namespace callers that rely on the fallback today. | `ModelCatalog` already flattens per system; injectable registry removes its scratch-namespace workaround. |
| D11 | **`extends`: later wins**, per the spec. | Spec text is unambiguous; the current order is the reverse. | Its `ModelCatalog` resolves through this function. **Check whether any shipped model has two parents declaring the same attribute** (Input gap 6). |
| D12 | **`copy()` gets a new instance id.** | Two live models claiming one identity is how the shared-resolver bug (R15) happened. | Check any use of `copy()` that relies on the id. |
| D13 | **`GrimoireModel` is unhashable** (`__hash__ = None`). | A mutable mapping must not be hashable; today's hash already raises for any non-flat model. | None expected. |
| D14 | **Python floor 3.10**; CI tests 3.10, 3.11, 3.12. | 3.8 does not import; 3.9 is end-of-life and current mypy rejects it as a target. | Uses 3.12. |
| D15 | **Sandboxed environment by default.** | Model definitions are third-party content once systems are distributed (Wyrdbound feature 12). | Already sandboxes its own resolver. |
| D16 | **List elements of a model type are `GrimoireModel`s**, like top-level model-typed attributes already are. | `of` otherwise means nothing (R33). This changes what `dict(model)` holds for such lists — a data-shape change (L2), recorded here deliberately. | Knave's and the quickstart's `inventory: {type: list, of: item}` will hold models; its serializer must treat them as it treats nested models (Input gap 7). |

## 7. Spec findings to raise

Found while reviewing; **not** changed by this feature (README rule 10). Each
goes to Justin, and to Wyrdbound's `02-spec-findings.md` if he agrees.

- **S1 — The spec's own example uses group-relative names.** `model_spec.md`
  "Example": `abilities.strength.defense: { derived: "{{ bonus + 10 }}" }`
  inside an anonymous group. Principle II and the library resolve names from
  the model root, so the example raises `'bonus' is undefined` (reproduced).
  Proposed: change the example to `{{ abilities.strength.bonus + 10 }}`, or
  make it a `character_ability` model as Knave does.
- **S2 — `kind` must be exactly `"model"`** (spec, Validation Rules 2); the
  library accepts `entity`, `component`, `system`, `enum`, `interface` and any
  identifier. Proposed: decide whether the library should enforce the spec
  here; not changed by this feature.
- **S3 — Library extensions the spec does not mention:** `readonly`,
  `computed`, `pattern`, `description` on attributes; `namespace`, `tags`,
  `metadata` on models. Proposed: document them in the spec as
  implementation extensions, or mark them so in the README.

## 8. What this is not

- **Not a rearchitecture.** Each fix makes an existing path do what
  `AGENTS.md` already says. No new resolver kinds, no new public concepts
  beyond `registry=` and the reference-path function.
- **Not a performance project.** Transactional writes validate more than
  before. That is the point; a measured regression is a later feature.
- **Not a spec change** (§7).
- **Not the F57 fix.** It merges first; R34 extends it.

## 9. Deferred

| Thing | Why not now |
| --- | --- |
| `uv.lock` and `uv` in CI | `AGENTS.md` §1 says raise it, and not as a side effect. It is raised here; it is a separate, one-task decision for Justin. |
| Warnings as a validation severity | D8 removes an unimplemented field; building warnings is a feature, not a fix. |
| Group-level `optional` in the anonymous-group shorthand | Whether an inline group can itself be optional is a spec question, not a defect found here. |
| Enforcing `kind: model` | S2 — a spec decision first. |
| Performance benchmarks for transactional writes | §8. |
