# Review Remediation — tests first, then the fix, for every finding

**Status:** In progress. T001 done (rebased onto `main` at `9b76519`, F57
merged). T002 next.
**Source design:** `planning/features/01-review-remediation.md` (§N and RNN
references below are into that document; §3 is the findings register).
Execution rules: `planning/features/README.md`. Governance: `AGENTS.md`.
**Companion spec:** `wyrdbound/grimoire` `spec/model_spec.md`. Where this list
and the spec disagree, **stop and ask**; do not silently follow either.
**Scope:** R01–R50 fixed, each behind a test that fails on 0.7.1; released as
0.8.0.
**Deferred:** `uv.lock`, validation warnings, spec changes. See §Deferred at
the end.

---

## How to execute this list

This list is written to be run **one task at a time by a model that does not
hold the design doc in context**. Every task names its files, restates the rule
it implements, and states its own acceptance check. Do not read ahead; do not
batch.

### Progress tracking — mandatory

**Check the box** (`- [x]`) on every task the moment it is done, and keep the
`**Status:**` header current. This file is the shared ledger: an agent picking
it up mid-way reads the status header and the checked boxes to know where work
stopped. A task is "done" only when its commit is in the repo; check the box in
the same commit, never before. One task → one checkbox → one commit.

### Per-task definition of done

1. The named file(s) exist with the described content, and nothing else
   changed.
2. `uv run ruff format src/ tests/ && uv run ruff check src/ tests/ --fix &&
   uv run mypy src/` pass.
3. `uv run pytest -q` passes — except that a **test task** is done when its new
   tests **fail for the stated reason** (a wrong value, a missing raise), never
   an import or syntax error, and every other test still passes. Mark the new
   tests `@pytest.mark.xfail(strict=True, reason="RNN — fixed by TNNN")` so
   the suite stays green; the fix task removes the marker.
4. The task's stated acceptance check passes.
5. A fix task adds its line to `CHANGELOG.md` under `## [Unreleased]`
   (README rule 13).

### Per-phase definition of done

At each **Checkpoint**, additionally (README "Per-phase definition of done"):

- `uv run pytest --cov=grimoire_model` TOTAL ≥ 90%.
- Every `examples/0*.py` runs.
- From Checkpoint 4 onward, the suite passes under `PYTHONHASHSEED` 0–7.
- **No version bump.** The version changes once, in T049 (README rule 14).

### Format

`[ID] [P?] [Story] Description`

- **[P]** — parallelizable: different files, no dependency on an unfinished
  task.
- **[Story]** — US1…US7 below.

### User stories

| | |
| --- | --- |
| **US1** | An expression that cannot be resolved raises; expressions are sandboxed and see only the model's data. |
| **US2** | A definition means exactly what it says: misspelled keys and unknown types are errors. |
| **US3** | A model's storage is private and every write is all-or-nothing. |
| **US4** | Derived fields compute in dependency order, exactly, and never go stale silently. |
| **US5** | Every value matches its declared type — groups, nested models, list elements. |
| **US6** | Inheritance and type lookup follow the spec and stay in the model's namespace. |
| **US7** | The package installs where it says it does and documents what it ships. |

### Path conventions

| Thing | Path |
| --- | --- |
| Expression evaluation | `src/grimoire_model/resolvers/template.py` |
| Derived fields, batching, observers | `src/grimoire_model/resolvers/derived.py` |
| Model instance, reads, writes | `src/grimoire_model/core/model.py` |
| Definitions, basic types | `src/grimoire_model/core/schema.py` |
| Model registry | `src/grimoire_model/core/registry.py` |
| Primitive registry | `src/grimoire_model/core/primitive_registry.py` |
| Validators | `src/grimoire_model/validation/validators.py` |
| Inheritance | `src/grimoire_model/utils/inheritance.py` |
| Package surface | `src/grimoire_model/__init__.py` |
| New test files (one per phase) | `tests/test_expression_safety.py`, `tests/test_definition_strictness.py`, `tests/test_write_transactions.py`, `tests/test_derived_ordering.py`, `tests/test_type_validation.py`, `tests/test_inheritance_resolution.py` |
| Changelog | `CHANGELOG.md` (`## [Unreleased]`) |

Test isolation: **nothing clears the global registries between tests** —
`tests/conftest.py` has no autouse fixture, and every `ModelDefinition`
registers itself on construction. New tests use model ids and namespaces no
other test uses, so a result never depends on what another test registered.
T042 adds the autouse clean-up, because it makes a conflicting re-registration
an error.

---

## The ten rules that must never be broken

Restate these to yourself before any task. Every one is a failure a
plausible-looking fix makes.

1. **Fail loudly** (README L1). No fix adds a fallback, a catch-and-log, a
   skipped check, or a default that hides a missing value. Several findings
   (R01, R26, R28, R36) *are* such code; removing it is the fix.
2. **Tests first, and they must fail for the right reason.** A test that fails
   on an `ImportError` proves nothing about the defect.
3. **Groups stay plain dicts** (README L2, `AGENTS.md` Principle III). Only the
   data-shape change D16 (list elements of a model type become models) is
   sanctioned; make no other.
4. **Do not change the resolver protocols** (README L3). Wyrdbound injects a
   resolver implementing `resolve_template`, `is_template`,
   `extract_variables` and nothing more.
5. **`register_primitive_type("roll")` and `("roll_result")` keep working.**
   Wyrdbound calls them at every system load.
6. **`resolve_model_inheritance(definition, plain_id_keyed_dict)` keeps
   working.** Wyrdbound's `ModelCatalog` calls it that way.
7. **`create_model_without_validation` keeps working** for partial data: an
   incremental model is validated leaf by leaf until the caller calls
   `validate()` (design D3).
8. **Do not redo or revert F57.** T001 brings it in; T034 extends it.
9. **Thread safety is not optional** (README L4). Shared mutable state added by
   a task is locked by that task.
10. **Never edit the GRIMOIRE spec or the Wyrdbound repository.** Divergences go
    to design §7 and the release commit message.

### And four traps with named victims

- **The shallow-snapshot trap.** `dict(self._data)` copies one level. Anything
  below it — every group dict, every list — is shared with every earlier
  snapshot, every value a caller was handed, and the definition's defaults.
  Rolling back a write (T020) is only correct once T017 has made storage
  copy-on-write. Do T017 before T020; that is why they are in that order.
- **The lucky-seed trap.** R25 passes under most hash seeds on a given
  machine. Running the suite once proves nothing: T025's test runs the build
  in subprocesses under several `PYTHONHASHSEED` values, and every checkpoint
  from 4 on loops the whole suite.
- **The incremental-model trap.** Running model-level `validations` on every
  write (T020) breaks `create_model_without_validation`, whose whole purpose is
  to be incomplete. Validated models get whole-model checks; incremental models
  get leaf and recomputed-derived checks (rule 7).
- **The old-test trap.** A few existing tests assert a behaviour this list
  corrects (named in the task that corrects it). Change exactly those, say so
  in the commit, and stop and ask about any other failure (README rule 8).

---

## Phase 0 — Ground truth

**Purpose:** start from `main` with the F57 fix merged.

- [x] **T001** Rebase this branch onto `main` after `fixNestedModelWrite` is
  merged. Files: none beyond what the rebase brings (this directory, which
  already exists on this branch).

  **Blocked until** `main` contains the F57 fix (the commit subject "fix: build
  a nested model when writing through a model-typed attribute", and
  `tests/test_nested_model_writes.py`). If it is not on `main`, **stop and
  ask** — do not cherry-pick it, and do not start T002 on a base without it:
  T034 and every write-path task build on it.
  *Accept:* `git log main..HEAD` shows only this directory's commits;
  `tests/test_nested_model_writes.py` exists and passes; the quality gate is
  clean; `uv run pytest -q` passes.

---

## Phase 1 — Expressions raise, are sandboxed, and see only data

**Purpose:** US1. The expression layer stops returning `None` for mistakes,
stops exposing Python internals, and resolves data before methods.

- [ ] **T002** [US1] Write `tests/test_expression_safety.py` (TDD) for R01–R04.
  Use `create_template_resolver()` and small models. Assert:
  - **R01:** `resolve_template("{{ g.missing }}", {"g": {"a": 1}})` raises
    `TemplateResolutionError`; so does `{{ g.a.b }}` with `{"g": {"a": 1}}`. A
    model whose derived `y = {{ g.xx }}` (with `g.x` declared) fails
    `create_model` with `TemplateResolutionError`. `{{ g.a }}` still returns
    `1` as an `int`, and `{{ opt is none }}` for an unset optional attribute
    still returns `True` (Principle VI).
  - **R02:** `{{ ''.__class__ }}` and
    `{{ ''.__class__.__mro__[1].__subclasses__() }}` raise; `{{ xs | sum }}`
    and `{{ name | upper }}` still work.
  - **R03:** with `{"g": {"items": 3, "keys": 4, "get": 5}}`,
    `{{ g.items + 1 }}` → `4`, `{{ g.keys }}` → `4`, `{{ g.get * 2 }}` → `10`.
    A model `bag` with `items: list` held by a parent whose derived
    `n = {{ bag.items | length }}` builds with `n == 2` for `[1, 2]`. A key
    that is absent still raises (it does not fall back to the dict method):
    `{{ g.values }}` with `{"g": {}}` raises.
  - **R04:** `resolve_template("[{{ a }}]", {"a": 1})` → the string `"[1]"`;
    `"{{ a }}, {{ b }}"` → a string; `"{{ xs }}"` with `xs = [1]` → the list.
  *Accept:* each group of assertions fails on 0.7.1 for the reason in design
  §3.1 (R01 returns `None`; R02 renders; R03 `TypeError` from a method; R04 a
  list), marked `xfail(strict=True)` per group.

- [ ] **T003** [US1] Fix R01. Files: `src/grimoire_model/resolvers/template.py`,
  `tests/test_expression_safety.py`, `CHANGELOG.md` only.

  Rule: an expression that cannot be resolved raises; it never becomes `None`
  (`AGENTS.md` Principle I). Compile pure expressions with
  `undefined_to_none=False` and treat a `jinja2.Undefined` result as a
  resolution error, raised as `TemplateResolutionError`. The pre-check of
  top-level names and the `except ValueError: pass` fallback to rendering
  exist only to paper over this; remove them if the tests pass without them,
  and keep them only with a comment saying what they still catch.

  Unset optional attributes must still read as `None` — that comes from
  `unset_as_null` putting `None` in the context, not from `undefined_to_none`,
  and the Principle VI tests in `tests/test_presence_and_defaults.py` must
  still pass unchanged.
  *Accept:* T002's R01 tests pass with the `xfail` removed; the full suite
  passes.

- [ ] **T004** [US1] Fix R02. Files: `src/grimoire_model/resolvers/template.py`,
  `tests/test_expression_safety.py`, `CHANGELOG.md` only.

  Build the environment from `jinja2.sandbox.SandboxedEnvironment` (design
  D15). Keep `self.env.globals.clear()` and its comment — sandboxing does not
  remove globals. Filters are unchanged. Do not add a switch to turn the
  sandbox off; a caller who wants an unsandboxed environment injects their own
  resolver.
  *Accept:* T002's R02 tests pass; `tests/test_expression_environment.py`
  passes unchanged.

- [ ] **T005** [US1] Fix R03. Files: `src/grimoire_model/resolvers/template.py`,
  `tests/test_expression_safety.py`, `CHANGELOG.md` only.

  Rule: in an expression, `x.name` on a mapping means the data at `name`.
  Subclass the sandboxed environment and override `getattr(obj, attribute)`:
  if `obj` is a `collections.abc.Mapping` (this covers `dict` and
  `GrimoireModel`) and `attribute in obj`, return `obj[attribute]`; otherwise
  defer to the sandbox's `getattr`, which keeps its safety checks. Do not
  special-case method names; the rule is "key first", not a deny-list.

  The resolver's fast path (`_check_simple_variable`) already looks keys up
  first, so after this fix the two paths agree. Leave it in place.
  *Accept:* T002's R03 tests pass; `{{ g.items() }}` on a dict with no `items`
  key still calls the method (assert it, so the fallback is proven).

- [ ] **T006** [US1] Fix R04. Files: `src/grimoire_model/resolvers/template.py`,
  `tests/test_expression_safety.py`, `tests/test_template_resolver.py`,
  `CHANGELOG.md` only.

  Rule: only a template that is exactly one `{{ expression }}` keeps its
  value's type; any other template renders to a string and stays a string.
  Delete `_try_parse_structured_data` and its call. Never recover a type by
  parsing rendered text.

  `tests/test_template_resolver.py` may assert the old re-parsing (a rendered
  `"[…]"` or `"{…}"` coming back as a list or dict). That is the behaviour
  being corrected: change those assertions to the string, and name each one
  in the commit message. Record the change under `### Changed (breaking)`.
  *Accept:* T002's R04 tests pass; `grep -n "literal_eval\|json.loads"
  src/grimoire_model/resolvers/template.py` prints nothing.

- [ ] **T007** [US1] Fix R05 and R06. Files:
  `src/grimoire_model/resolvers/derived.py`, `src/grimoire_model/core/model.py`,
  `tests/test_expression_safety.py`, `CHANGELOG.md` only.

  Rule (`AGENTS.md` Principle II): nothing is in scope but the model's data,
  and every name an expression uses is a dependency. Write the tests first in
  `tests/test_expression_safety.py` and see them fail:
  - an attribute named each of `round`, `max`, `sum`, `len`, `int`, `str` is a
    dependency: writing it recomputes a derived field that uses it;
  - `{{ model.name }}` raises in a model built by `create_model` (no attribute
    `model` declared), and in one built with an explicit `instance_id`,
    `{{ <that id> }}` is not in scope — use an id that is a valid identifier;
  - an attribute named `model` is a dependency.

  Then: delete the builtin-name skip list and the `instance_id` skip in
  `DerivedFieldResolver._extract_dependencies`; build
  `DerivedFieldResolver._build_template_context` and
  `GrimoireModel._build_validation_context` from `unset_as_null(data, …)`
  alone, with no instance-id key. `instance_id` stays a constructor argument
  (it is public) and is used only for logging.
  *Accept:* the new tests pass; `grep -n '"round"' src/grimoire_model/resolvers/derived.py`
  prints nothing.

- [ ] **T008** [P] [US1] Fix R07. Files:
  `src/grimoire_model/resolvers/template.py`, `tests/test_template_resolver.py`,
  `CHANGELOG.md` only.

  Tests first: `CachingTemplateResolver.is_template(["x"])` returns `False`
  (as the wrapped resolver does) and `extract_variables(None)` returns
  `set()`; with `max_cache_size=2`, touching `a`, `b`, `a`, then adding `c`
  evicts `b`, not `a`; 8 threads calling `is_template` and `extract_variables`
  on 500 distinct strings each finish with no exception.

  Then: non-`str` inputs bypass the cache; the caches are
  `collections.OrderedDict` with `move_to_end` on hit (a real LRU); one
  `threading.Lock` guards both caches.
  *Accept:* the new tests pass.

**Checkpoint 1.** Per-phase gate. No version bump (README rule 14).

---

## Phase 2 — Definitions mean what they say

**Purpose:** US2. A typo in a definition is an error, and the basic types are
the spec's, spelled one way.

- [ ] **T009** [US2] Write `tests/test_definition_strictness.py` (TDD) for R08,
  R09, R10, R12, R13. Assert:
  - **R08:** each of `AttributeDefinition(type="str", optinal=True)`,
    `ModelDefinition(id="t", name="t", attributes={}, validatons=[])`, and
    `ValidationRule(expression="a", message="m", sevrity="x")` raises
    `pydantic.ValidationError`; an attribute dict with an unknown key inside a
    `ModelDefinition` raises `ConfigurationError` naming the attribute, at any
    group depth (`{"g": {"x": {"type": "int", "rnage": "1..3"}}}`).
    `metadata={"anything": 1}` on a `ModelDefinition` is still accepted.
  - **R09:** `AttributeDefinition(type="any")` raises, and the message names
    the spec's basic types.
  - **R10:** `{"x": {"type": "Int"}}` does not accept `"not an int"`: either
    the definition raises or instantiation does — assert that
    `create_model(d, {"x": "not an int"})` raises.
  - **R12:** `ValidationRule(expression="a", message="m", severity="warning")`
    and `ValidationRule(..., fields=["a"])` raise.
  - **R13:** `AttributeDefinition(type="int", of="str")` raises;
    `AttributeDefinition(type="list", of="str")` does not.
  *Accept:* each fails on 0.7.1 for the reason in design §3.2, marked
  `xfail(strict=True)`.

- [ ] **T010** [US2] Fix R08. Files: `src/grimoire_model/core/schema.py`,
  `tests/test_definition_strictness.py`, `tests/test_schema.py`,
  `CHANGELOG.md` only.

  Set `model_config = ConfigDict(extra="forbid")` on `AttributeDefinition`,
  `ModelDefinition` and `ValidationRule` (design D5). Keep
  `reject_required_field` and its message: `required` is the one unknown key
  that deserves an explanation. Make sure the group conversion in
  `ModelDefinition.validate_attributes` / `_convert_group` does not lose the
  error's attribute path.

  **Before starting, check Input gap 2** (Wyrdbound passes declarations as
  parsed). If it is not closed, stop and ask.

  `tests/test_schema.py` may construct definitions with keys that are now
  unknown. If so, those tests relied on the silent drop; correct the fixture
  (not the assertion), and list each one in the commit message. Record under
  `### Changed (breaking)`.
  *Accept:* T009's R08 tests pass; the full suite passes.

- [ ] **T011** [US2] Fix R09 and R10. Files: `src/grimoire_model/core/schema.py`,
  `src/grimoire_model/core/model.py`,
  `src/grimoire_model/core/primitive_registry.py`,
  `src/grimoire_model/validation/validators.py`,
  `tests/test_definition_strictness.py`, `CHANGELOG.md` only.

  Define one constant in `core/schema.py`:
  `BASIC_TYPES = frozenset({"int", "str", "float", "bool", "list", "dict"})`
  (T012 adds `roll` and `roll_result`). Use it — and only it — in
  `AttributeDefinition.validate_type`, `GrimoireModel._is_custom_model_type`
  (no `.lower()`), `PrimitiveTypeRegistry.register`'s built-in check (no
  `.lower()`), and `TypeValidator`. `any` is not in it: an `any` attribute is a
  definition error whose message lists `BASIC_TYPES` (design D7). A name that
  differs from a basic type only in case is treated as a model id, and fails as
  one — loudly — when resolved.
  *Accept:* T009's R09 and R10 tests pass; `grep -rn '"any"'
  src/grimoire_model` prints nothing; `grep -rn '\.lower()' src/grimoire_model/core`
  prints nothing type-related.

- [ ] **T012** [US2] Fix R11 (Wyrdbound F47). Files:
  `src/grimoire_model/core/schema.py`,
  `src/grimoire_model/core/primitive_registry.py`,
  `src/grimoire_model/validation/validators.py`,
  `tests/test_definition_strictness.py`, `tests/test_primitive_registry.py`,
  `CHANGELOG.md` only.

  Tests first: `{"dmg": {"type": "roll"}}` instantiates with `"1d6"` and
  rejects `6`; `{"r": {"type": "roll_result"}}` accepts a dict and an arbitrary
  object; `register_primitive_type("roll")` and
  `register_primitive_type("roll_result")` do not raise (rule 5), and a
  validator registered for `roll` that returns `(False, "bad dice")` makes
  `"1d"` fail with `"bad dice"` in the errors; a validator registered for a
  custom primitive `dur` is called on build and on write, and `(True, None)`
  passes.

  Then: add `roll` and `roll_result` to `BASIC_TYPES` as the spec's
  non-Python basic types. `roll` values must be `str`; `roll_result` values are
  not type-checked (their shape is the dice library's). `PrimitiveTypeRegistry`
  refuses to register the six Python basic types, but **allows** a validator to
  be registered for `roll` and `roll_result`. `TypeValidator` calls a
  registered primitive's validator with the value; the contract is the one
  already documented in `register_primitive_type`'s docstring —
  `(is_valid, error_message)` — and a `False` result becomes an error naming
  the field. A validator that raises is a validation error, not a crash.
  *Accept:* the new tests pass; `examples/07_custom_primitive_types.py` runs.

- [ ] **T013** [US2] Fix R12. Files: `src/grimoire_model/core/schema.py`,
  `tests/test_definition_strictness.py`, `tests/test_schema.py`,
  `CHANGELOG.md` only.

  **Check Input gap 3 first.** Remove `ValidationRule.severity`, its
  validator, and `ValidationRule.fields` (design D8). With T010's
  `extra="forbid"`, passing either is now an error; override that error for
  these two keys with a message saying GRIMOIRE validations have no severity
  and that every rule is an error. Tests in `tests/test_schema.py` that assert
  severity validation are testing a removed field: delete those assertions,
  and name them in the commit. Record under `### Removed (breaking)`.
  *Accept:* T009's R12 tests pass; `grep -rn "severity" src/` prints nothing.

- [ ] **T014** [P] [US2] Fix R13. Files: `src/grimoire_model/core/schema.py`,
  `tests/test_definition_strictness.py`, `CHANGELOG.md` only.

  Rule (`model_spec.md`: "`of`: Element type for list attributes"): `of` is
  valid only when `type` is `list`. Update the field's description, which
  says "list/dict".
  *Accept:* T009's R13 tests pass.

**Checkpoint 2.** Per-phase gate. Run Wyrdbound's model tests against this
branch if Input gap 2 said to (`uv run pytest engine/tests/unit/test_model_translation.py`
in Wyrdbound with this branch installed editable); record the result in the
checkpoint commit message. Do not change Wyrdbound.

---

## Phase 3 — Storage is private and writes are transactions

**Purpose:** US3. Nothing outside the model can change its data, and a write
either leaves the model valid or leaves it untouched.

- [ ] **T015** [US3] Write `tests/test_write_transactions.py` (TDD), part 1:
  storage, `copy()`, keywords, hashing — R14, R15, R22, R23. Assert:
  - **R14:** (a) `m["g"]["x"] = 99` does not change `m["g.x"]`; (b) a value
    read before a write is unchanged by the write (`old = m["g"]; m["g.x"] = 2;
    old == {"x": 1}`); (c) with `tags: {type: list, default: []}`, appending
    to one instance's `m["tags"]` changes neither a new instance nor the
    definition's default; (d) `m["tags"].append(1)` does not change
    `m["tags"]`; (e) for a model-typed attribute, `m["w"]["name"] = "x"` does
    not change `m["w.name"]`.
  - **R15:** with `b = {{ a * 2 }}`: `c = m.copy(a=5); m["a"] = 10` → `m["b"]
    == 20`, `c["b"] == 10`; `c.instance_id != m.instance_id`.
  - **R22:** `GrimoireModel(d, {}, skip_initial_validaton=True)` and
    `create_model(d, {}, derived_field_resolver_type="batched")` raise
    `TypeError`.
  - **R23:** `hash(m)` raises `TypeError` for any model, and
    `GrimoireModel.__hash__ is None`.
  *Accept:* each fails on 0.7.1 for the reason in design §3.3, `xfail(strict)`.

- [ ] **T016** [US3] Fix R15. Files: `src/grimoire_model/core/model.py`,
  `tests/test_write_transactions.py`, `CHANGELOG.md` only.

  `copy(**overrides)` builds the new model with a **new** derived-field
  resolver of the same class as the original's (batched stays batched), the
  same template resolver (it is stateless apart from its lock-protected cache),
  and a new instance id (design D12). The copy is built in the original's
  validation mode (a copy of an incremental model is incremental).
  *Accept:* T015's R15 tests pass.

- [ ] **T017** [US3] Fix R14 (Wyrdbound F36). Files:
  `src/grimoire_model/core/model.py`, `src/grimoire_model/resolvers/derived.py`,
  `tests/test_write_transactions.py`, `CHANGELOG.md` only.

  Two rules (design §4.3, D2):
  1. **Copy-on-write.** No code path mutates a dict or list reachable from a
     previous `_data`. A dotted write builds new containers along its path and
     shares everything else. This includes `DerivedFieldResolver`'s own writes
     into its data view (`_set_nested_value`, `_remove_value`): either they
     copy along the path too, or the resolver stops writing into shared data
     and the model owns every write through `_on_derived_field_changed`.
     Choose one and say which in the commit.
  2. **Reads return copies.** `__getitem__` (and so `get`, `values`, `items`,
     attribute access) returns `copy.deepcopy` of a `dict` or `list` value and
     an independent copy of a nested `GrimoireModel`. Scalars are returned as
     they are. Internal reads — contexts, validation — do not go through
     `__getitem__`.

  `_apply_defaults` stores `copy.deepcopy(attr_def.default)`. A nested
  model is copied with `copy()`, which T016 made independent.

  Existing tests that mutate a value they read and expect the model to
  change (`m["inventory"].append(x)`) encode R14: rewrite them as dotted or
  whole-value writes, and name each in the commit. `### Changed (breaking)`.
  *Accept:* T015's R14 tests pass; `tests/test_nested_model_writes.py` passes
  unchanged.

- [ ] **T018** [P] [US3] Fix R22 and R23. Files:
  `src/grimoire_model/core/model.py`, `tests/test_write_transactions.py`,
  `CHANGELOG.md` only.

  Remove `**kwargs` from `GrimoireModel.__init__`. In `create_model` and
  `create_model_without_validation`, keep `**kwargs` only for the keys they
  document (`template_resolver_kwargs`, `derived_resolver_kwargs`) plus the
  named `GrimoireModel` parameters, passed explicitly; any other key raises
  `TypeError` naming it. Set `__hash__ = None` on `GrimoireModel` and delete
  the `__hash__` method (design D13). Both are `### Changed (breaking)`.
  *Accept:* T015's R22 and R23 tests pass; `examples/` all run.

- [ ] **T019** [US3] Write `tests/test_write_transactions.py` part 2: the write
  rules — R16, R17, R18, R19, R20, R21. Assert, on models built with
  `create_model` unless stated:
  - **R16:** with `b: {type: int, range: "0..10", derived: "{{ a * 2 }}"}`,
    `m["a"] = 50` raises `ModelValidationError` and leaves `m == {a: 1, b: 2}`.
    With rule `{{ a <= b }}`, `m["a"] = 50` raises and `m["a"]` is unchanged.
    In a model from `create_model_without_validation` missing a required
    attribute, a valid leaf write succeeds (rule 7) but a write that breaks a
    recomputed derived field's range raises.
  - **R17:** with `hp.max = {{ level * 10 }}` and `hp.cur: range
    "0..{{ hp.max }}"`, `batch_update({"level": 10, "hp.cur": 50})` succeeds;
    `batch_update({"a": 2, "b": 99})` with `b: 0..5` raises and leaves `a`
    unchanged — for both the default and a `BatchedDerivedFieldResolver`.
  - **R18:** `m["b"] = 100` on derived `b` raises; `m["b"]` is unchanged.
  - **R19:** `del m["id"]` on a readonly `id` raises; `del m["a"]` on a
    required `a` raises; `del m["b"]` on derived `b` raises; `del m["opt"]` on
    an optional attribute unsets it and recomputes its dependents exactly as
    `m["opt"] = None` does.
  - **R20:** `m["g.k"] = "b"` on a readonly leaf `g.k` that has a value raises.
  - **R21:** `create_model(d, {"strength": 1, "strenght": 5})` raises naming
    `strenght`; `m["dexterity"] = 1` raises; an undeclared key inside a group
    (`{"g": {"x": 1, "y": 2}}` with only `g.x` declared) raises naming `g.y`;
    `validate()` on an incremental model holding an undeclared key reports it.
  *Accept:* each fails on 0.7.1 for the reason in design §3.3, `xfail(strict)`.

- [ ] **T020** [US3] Fix R16: a single write is a transaction. Files:
  `src/grimoire_model/core/model.py`, `src/grimoire_model/resolvers/derived.py`,
  `tests/test_write_transactions.py`, `CHANGELOG.md` only.

  **Requires T017** (the shallow-snapshot trap). `_set_with_validation`:
  1. snapshot `_data` (a `pmap` reference is enough once storage is
     copy-on-write) and whatever state the derived resolver keeps;
  2. validate the written leaf (as today, templated range resolved first);
  3. apply the write and recompute dependents;
  4. validate every derived field the write recomputed against its own
     definition, and — only for a model built with validation — run the
     model-level `validations` (design D3, rule 7);
  5. on any failure, restore the snapshot in both places and raise
     `ModelValidationError` carrying every error.

  Record, on the model, whether it was built with validation. Do not add a
  public API for it.
  *Accept:* T019's R16 tests pass; `tests/test_nested_model_writes.py` passes.

- [ ] **T021** [US3] Fix R17: `batch_update` is one transaction. Files:
  `src/grimoire_model/core/model.py`, `tests/test_write_transactions.py`,
  `CHANGELOG.md` only.

  Snapshot once; apply every write without per-field validation; recompute
  derived fields once (batched resolver: `start_batch`/`end_batch`; plain
  resolver: `compute_all_derived_fields`); then validate every written leaf
  against the *recomputed* data (templated ranges resolved now), every
  recomputed derived field, and model-level rules as in T020. Any failure
  restores the snapshot and raises with every error. Readonly and derived
  targets are rejected before anything is applied.
  *Accept:* T019's R17 tests pass.

- [ ] **T022** [US3] Fix R18, R19, R20. Files: `src/grimoire_model/core/model.py`,
  `tests/test_write_transactions.py`, `CHANGELOG.md` only.

  - A write to a derived attribute (at any path) raises `ModelValidationError`
    saying it is derived. The derived resolver's own writes do not go through
    `_set_with_validation` and are unaffected.
  - Readonly is decided by the attribute's definition at the full path: a
    readonly leaf that already has a value (`has_nested_value`) cannot be
    written.
  - `__delitem__(key)`: optional → exactly `self[key] = None`; required,
    readonly or derived → `ModelValidationError`; undeclared or absent →
    `KeyError` (the `MutableMapping` contract).
  *Accept:* T019's R18, R19, R20 tests pass.

- [ ] **T023** [US3] Fix R21: undeclared keys are errors. Files:
  `src/grimoire_model/core/model.py`,
  `src/grimoire_model/validation/validators.py`,
  `tests/test_write_transactions.py`, `tests/test_model.py`, `CHANGELOG.md`
  only.

  **Check Input gap 2 first** (design D6). `ValidationEngine.validate_data`
  and `_validate_group` report every key that is not declared, by full dotted
  path. Writes to an undeclared path raise before anything is applied. A path
  that passes *into* a nested model (a model-typed attribute) is checked by
  that model, not by the parent. Existing tests that build models with
  undeclared keys relied on the silent acceptance: correct their fixtures and
  list them in the commit. `### Changed (breaking)`.
  *Accept:* T019's R21 tests pass; every example runs.

- [ ] **T024** [US3] Fix R24: thread safety. Files:
  `src/grimoire_model/core/model.py`,
  `src/grimoire_model/validation/validators.py`,
  `tests/test_write_transactions.py`, `CHANGELOG.md` only.

  Test first: 8 threads, each writing 300 successive values to its own
  field of one model, with `sys.setswitchinterval(1e-6)` (restore the old
  interval in `finally`); repeat 30 times; every field ends at its last
  value. A second test: one thread writes while another calls `validate()` and
  iterates `dict(m)` 1,000 times — no exception. (During the review, 0.7.1 lost
  one final value in 240 fields over 30 trials. The race is rare: if the test
  passes on 0.7.1 on your machine, raise the trial count until it fails, and
  record the number in the test's docstring. A test that has never failed does
  not prove the lock.)

  Then: one `threading.RLock` per model (created first in `__init__`, before
  anything can be read), held by every public read and write, `validate`,
  `copy`, `batch_update`, `__iter__` (iterate over a snapshot of the keys),
  `__len__` and `__contains__`. It must be re-entrant: derived callbacks and
  nested writes re-enter. Give `ValidationEngine.register_validator` and
  `unregister_validator` a lock, and have `validate_field` iterate over a
  snapshot of the validators.
  *Accept:* the new tests pass three times in a row.

**Checkpoint 3.** Per-phase gate.

---

## Phase 4 — Derived fields compute in order, exactly, loudly

**Purpose:** US4.

- [ ] **T025** [US4] Write `tests/test_derived_ordering.py` (TDD) for R25–R30.
  Assert:
  - **R25:** a helper runs a small script in a subprocess
    (`sys.executable -c …`) that builds `p.mod = {{ p.score // 2 }}`,
    `total = {{ p.mod + 100 }}` from `{"p": {"score": 10}}` and prints
    `total`, then writes `p.score = 20` and prints `total` again; run it with
    `PYTHONHASHSEED` 0 through 7 and assert every run prints `105` then `110`.
    Also, in-process: `get_field_dependencies("total") == {"p.mod"}` and
    `get_dependent_fields("p.mod") == {"total"}`, and a chain across groups
    (`a.x` → `b.y = {{ a.x + 1 }}` → `c = {{ b.y * 2 }}`) recomputes in order
    on a write to `a.x`.
  - **R26:** with `q = {{ a / b }}`, `m["b"] = 0` raises and leaves `b == 1`,
    `q == 1.0`.
  - **R27:** `int` derived `{{ (s - 10) / 2 }}` with `s = 9` raises (not
    integral) while `{{ (s - 10) // 2 }}` gives `-1`; `int` derived from
    `4.0` gives `4`; `int` derived from `"abc"` raises and nothing is stored;
    `bool` derived from `"maybe"` raises; `str` derived from an unset optional
    attribute gives `None`, not `"None"`; `str` derived from a dict raises.
  - **R28:** of two observers on an `ObservableValue`, the first raising
    `RuntimeError`, the second is still called and the write raises the
    `RuntimeError`.
  - **R29:** nested `start_batch()`/`end_batch()` recomputes both inner and
    outer writes' dependents at the outer `end_batch()`, and not before.
  - **R30:** `get_derived_fields()` includes `p.mod`.
  *Accept:* each fails on 0.7.1 for the reason in design §3.4, `xfail(strict)`
  (the R25 subprocess test must fail on at least one seed; if it does not on
  your machine, widen the seed range and record it).

- [ ] **T026** [US4] Fix R25: dependencies by reference path. Files:
  `src/grimoire_model/resolvers/template.py`,
  `src/grimoire_model/resolvers/derived.py`, `tests/test_derived_ordering.py`,
  `tests/test_template_resolver.py`, `CHANGELOG.md` only.

  Add a module-level function to `resolvers/template.py`:
  `extract_reference_paths(expression: str) -> Set[str]`. It parses with a
  plain `jinja2.Environment` (Principle II: the syntax is Jinja2 whatever
  resolver is injected) and returns, for every `Name` node that is a free
  variable, the maximal dotted path formed by the `Getattr` nodes — and
  `Getitem` nodes with a constant string key — directly above it:
  `{{ p.mod + 1 }}` → `{"p.mod"}`; `{{ xs | map(attribute='w') | sum }}` →
  `{"xs"}`; `{{ a['b'].c }}` → `{"a.b.c"}`; `{{ a[i] }}` → `{"a", "i"}`. Test
  it directly in `tests/test_template_resolver.py`.

  `DerivedFieldResolver` records these paths as dependencies (design D4). It
  does **not** add a method to the injected resolver's protocol (rule 4).
  Two paths *overlap* when they are equal or one is a dotted prefix of the
  other (`p` and `p.mod` overlap; `p.mod` and `p.modifier` do not). Derived
  field D depends on derived field E when one of D's dependencies overlaps E's
  path. A write to path W triggers every derived field with a dependency
  overlapping W. The topological sort orders by these edges and breaks ties by
  sorted path, so the order never depends on `set` iteration. A derived field
  never depends on itself.
  *Accept:* T025's R25 tests pass; the suite passes under `PYTHONHASHSEED`
  0–7.

- [ ] **T027** [US4] Fix R26. Files: `src/grimoire_model/resolvers/derived.py`,
  `tests/test_derived_ordering.py`, `CHANGELOG.md` only.

  Remove the `except Exception` in `_update_dependent_fields`; a recompute
  failure propagates as `TemplateResolutionError`, and T020's transaction
  rolls the write back. When a dependent's dependency is unavailable — which,
  after T022, only happens in an incremental model — remove the dependent's
  value from the data rather than keeping the old one. In
  `compute_all_derived_fields(skip_on_missing_dependencies=True)`, only a
  missing dependency is a reason to skip; any other failure raises.
  *Accept:* T025's R26 tests pass; `tests/test_model.py`'s incremental tests
  and `examples/06_incremental_model_building.py` pass unchanged.

- [ ] **T028** [US4] Fix R27. Files: `src/grimoire_model/resolvers/derived.py`,
  `tests/test_derived_ordering.py`, `tests/test_derived_resolver.py`,
  `CHANGELOG.md` only.

  Replace `_convert_value_to_type` with the exact rules in design §4.4. A
  value that cannot be converted raises `ModelValidationError` naming the
  field, the expression and the value — never returned unconverted.

  `tests/test_derived_resolver.py` may assert truncation (`"15.7"` → `15`) or
  `bool` of arbitrary strings. That is the behaviour being corrected: change
  those assertions to expect the raise, and name them in the commit.
  `### Changed (breaking)`: an `int` derived field whose expression yields a
  fraction now raises — use `//`, `| round | int`, or `| int` explicitly.
  *Accept:* T025's R27 tests pass.

- [ ] **T029** [P] [US4] Fix R28. Files:
  `src/grimoire_model/resolvers/derived.py`, `tests/test_derived_ordering.py`,
  `CHANGELOG.md` only.

  `ObservableValue.value`'s setter calls every observer; if any raised, it
  re-raises the first exception after the last observer has run. Delete the
  `logger.error`. Iterate over a copy of the observer list, so an observer
  that removes itself does not skip the next one.
  *Accept:* T025's R28 test passes.

- [ ] **T030** [P] [US4] Fix R29 and R30. Files:
  `src/grimoire_model/resolvers/derived.py`, `src/grimoire_model/core/model.py`,
  `tests/test_derived_ordering.py`, `CHANGELOG.md` only.

  `BatchedDerivedFieldResolver` keeps a depth counter: `start_batch`
  increments it and clears nothing; `end_batch` decrements it and recomputes
  only when it reaches zero; `end_batch` with no open batch is a no-op (as
  today). `GrimoireModel.get_derived_fields()` returns every derived leaf's
  dotted path (use `iter_leaf_attributes`).
  *Accept:* T025's R29 and R30 tests pass.

**Checkpoint 4.** Per-phase gate, including the `PYTHONHASHSEED` 0–7 loop from
now on.

---

## Phase 5 — Values match their declared types

**Purpose:** US5.

- [ ] **T031** [US5] Write `tests/test_type_validation.py` (TDD) for R31–R39.
  Assert:
  - **R31:** `{"g": 5}` for a group `g` raises on build and on
    `m["g"] = 5`.
  - **R32:** `{"w": 5}` for `w: {type: weapon}` raises on build and write; a
    `GrimoireModel` of a *different* model id raises; one of `weapon` is
    accepted.
  - **R33:** `xs: {type: list, of: int}` rejects `["a"]` with an error naming
    `xs[0]`, and accepts `[1, 2]`; `inv: {type: list, of: item}` with `item`
    declaring `w: int` and `dbl = {{ w * 2 }}` turns `[{"w": 2}]` into one
    `GrimoireModel` with `dbl == 4`, rejects `[{"w": "heavy"}]` naming
    `inv[0]`, and a write `m["inv"] = [{"w": 3}]` builds and validates the same
    way.
  - **R34:** a model `abil` (`bonus: int`, `defense = {{ bonus + 10 }}`) as a
    leaf inside a group (`abilities: {con: {type: abil}}`): building from
    `{"abilities": {"con": {"bonus": 3}}}` gives `m["abilities.con.defense"]
    == 13`, and then `m["abilities.con.bonus"] = 4` gives `14`.
  - **R35:** `create_model_without_validation(d, {"w": {}})` for an optional
    `w: {type: sword}` whose `name` is required succeeds, and `validate()` then
    reports `name`.
  - **R36:** `xs: {type: list, range: ">=2"}` rejects `[]`; `s: {type: str,
    range: "..3"}` rejects `"abcd"`; `s: {type: str, range: "a..b"}` is a
    reported invalid range, not a pass.
  - **R37:** `pattern: "[a-z]+"` rejects `"abc123!"` and accepts `"abc"`.
  - **R38:** a missing required `a` produces exactly one error.
  - **R39:** `validate_field_value("x", "f", AttributeDefinition(type="int"),
    enabled_validators=[])` returns `[]`.
  *Accept:* each fails on 0.7.1 for the reason in design §3.5, `xfail(strict)`.

- [ ] **T032** [US5] Fix R31 and R32. Files:
  `src/grimoire_model/validation/validators.py`,
  `src/grimoire_model/core/model.py`, `tests/test_type_validation.py`,
  `CHANGELOG.md` only.

  A group's value must be a `Mapping`; anything else is an error naming the
  group. A model-typed attribute's value must be a `Mapping` (built into the
  model) or a `GrimoireModel` whose `model_definition.id` is that type (after
  inheritance: its own id); anything else is an error naming the attribute and
  the expected model. Checked on build and write. `TypeValidator` no longer
  passes unknown types silently: it receives enough to know an attribute is
  model-typed, or the model checks model-typed attributes itself — keep
  validators context-free (`AGENTS.md` Principle IV) and say which in the
  commit.
  *Accept:* T031's R31 and R32 tests pass.

- [ ] **T033** [US5] Fix R33: enforce `of`. Files:
  `src/grimoire_model/core/model.py`,
  `src/grimoire_model/validation/validators.py`,
  `tests/test_type_validation.py`, `CHANGELOG.md` only.

  **Check Input gap 7 first** (design D16 changes the data shape). For a
  `list` with `of`: a basic-type `of` validates each element with the type
  rules, errors named `name[i]`; a model-id `of` builds each `Mapping`
  element as that model (same template resolver, the parent's validation
  mode), keeps an element that is already a `GrimoireModel` of that id, and
  rejects anything else, errors named `name[i]` or `name[i].leaf`. Applies on
  build and on every write of the list. Resolve the model id the same way a
  model-typed attribute is resolved today (T041 later makes that
  namespace-local for all three uses at once).
  *Accept:* T031's R33 tests pass; every example runs.

- [ ] **T034** [US5] Fix R34: model-typed leaves inside groups. Files:
  `src/grimoire_model/core/model.py`, `tests/test_type_validation.py`,
  `CHANGELOG.md` only.

  **Requires T001** (F57 on `main`). Build model-typed attributes wherever
  they are declared, including inside anonymous groups — walk with
  `iter_leaf_attributes`, not `_resolved_attributes.items()`. Extend F57's
  dotted-write descent (`_model_typed_attribute`, `_nested_model` and the
  branch in `_set_with_validation`) so a path that passes through groups to a
  model-typed leaf descends into that model, and so does a whole-value write
  of a mapping to such a leaf. Do not change what F57 does for a top-level
  model-typed attribute, and do not instantiate the groups themselves (rule 3).
  *Accept:* T031's R34 tests pass; `tests/test_nested_model_writes.py`
  passes unchanged.

- [ ] **T035** [US5] Fix R35. Files: `src/grimoire_model/core/model.py`,
  `tests/test_type_validation.py`, `CHANGELOG.md` only.

  Every nested model — top-level attribute, group leaf, list element — is
  built in its parent's validation mode: an incremental parent builds
  incremental children. A validated parent's `validate()` includes each
  nested model's `validate()` errors, prefixed with the path to it.
  *Accept:* T031's R35 test passes.

- [ ] **T036** [US5] Fix R36: one range parser. Files:
  `src/grimoire_model/validation/validators.py`, `tests/test_type_validation.py`,
  `tests/test_validators.py`, `CHANGELOG.md` only.

  Add one private parser in `validators.py` that turns every documented range
  form (`a..b`, `a..`, `..b`, `>=a`, `<=b`, `>a`, `<b`, `=a`, with optional
  spaces) into bounds and inclusivity, and raises on anything else. Use it in
  `RangeValidator` (numbers) and `LengthValidator` (`len()` of `str`, `list`,
  `dict`). An unparseable range is an error for every type; `LengthValidator`'s
  `except: pass` goes. A length bound must be a whole number.
  *Accept:* T031's R36 tests pass; `tests/test_validators.py` passes (update
  any assertion that expected an unparseable length range to be ignored, and
  name it in the commit).

- [ ] **T037** [P] [US5] Fix R37, R38, R39. Files:
  `src/grimoire_model/validation/validators.py`, `tests/test_type_validation.py`,
  `tests/test_validators.py`, `CHANGELOG.md` only.

  **Check Input gap 4 first.** `PatternValidator` uses `re.fullmatch` (design
  D9) and says so in its docstring. `TypeValidator` returns no error for
  `None`; `RequiredValidator` alone reports a missing required value.
  `validate_field` treats `enabled_validators=None` as "all" and `[]` as
  "none". Record the `pattern` change under `### Changed (breaking)`.
  *Accept:* T031's R37–R39 tests pass.

**Checkpoint 5.** Per-phase gate.

---

## Phase 6 — Inheritance and lookup follow the spec

**Purpose:** US6.

- [ ] **T038** [US6] Write `tests/test_inheritance_resolution.py` (TDD) for
  R40–R45. Assert:
  - **R40:** `pb.x` default `"B"`, `pc.x` default `"C"`, `kid extends [pb,
    pc]` → `x == "C"`; `kid2 extends [pc, pb]` → `"B"`; the child's own
    attribute beats both; with a diamond (`l, r extends [base]`, `d extends
    [l, r]`), `r`'s override of a `base` attribute wins. Validations: every
    rule from every ancestor applies, once.
  - **R41:** in namespaces `qs` and `knave`, each with its own `item` (`qs`
    registered first), `knave.weapon extends [item]` has `slot_cost` and not
    `cost`; a `knave` model with `s: {type: stat}` where only `qs` has `stat`
    resolves it (unique match); with `stat` in two other namespaces and none in
    `knave`, building raises an error naming both candidates. With
    `registry=ModelRegistry()` passed to `create_model`, lookups use that
    registry and the global one is untouched.
    `resolve_model_inheritance(defn, {"item": item_defn})` (a plain dict)
    still works (rule 6).
  - **R42:** after instantiating `knave.weapon`, `get_default_registry()`
    contains no `default__weapon`; registering a *different* definition under
    an existing key raises `ValueError`; re-registering an equal definition
    does not.
  - **R43:** a model extending ten parents, each extending one base, builds;
    a linear chain of exactly `max_depth` levels builds; one deeper raises.
  - **R44:** `cy1 ↔ cy2`, `cyc extends [cy1]` raises `InheritanceError`
    naming the cycle.
  - **R45:** `validate_model_registry(get_default_registry())` and
    `validate_model_registry(get_default_registry().get_registry_dict())` on a
    healthy two-namespace registry return `[]`, and report a real missing
    parent.
  *Accept:* each fails on 0.7.1 for the reason in design §3.6, `xfail(strict)`.

- [ ] **T039** [US6] Fix R40: later parents win. Files:
  `src/grimoire_model/utils/inheritance.py`,
  `tests/test_inheritance_resolution.py`, `tests/test_utils.py`,
  `CHANGELOG.md` only.

  **Check Input gap 6 first.** Rule (`model_spec.md`, Inheritance Rules 4):
  "Later models override fields from earlier ones." resolved(M) = merge of
  resolved(P1) … resolved(Pn) in `extends` order, then M's own attributes;
  each later source replaces an earlier attribute of the same name.
  Validations accumulate in the same order, de-duplicated by (expression,
  message). Remove the "C3 linearization" claims from the docstrings. Any
  existing test asserting earlier-wins encodes the bug: change it and name it
  in the commit. `### Changed (breaking)`.
  *Accept:* T038's R40 tests pass.

- [ ] **T040** [US6] Fix R43 and R44. Files:
  `src/grimoire_model/utils/inheritance.py`,
  `tests/test_inheritance_resolution.py`, `CHANGELOG.md` only.

  `max_depth` bounds the length of the longest `extends` path from the model,
  not the number of models visited. Any cycle reachable from the model raises
  `InheritanceError` with the cycle's ids in order.
  *Accept:* T038's R43 and R44 tests pass.

- [ ] **T041** [US6] Fix R41 (Wyrdbound F35): namespace-local lookup,
  injectable registry. Files: `src/grimoire_model/core/model.py`,
  `src/grimoire_model/core/registry.py`,
  `src/grimoire_model/utils/inheritance.py`,
  `tests/test_inheritance_resolution.py`, `CHANGELOG.md` only.

  **Check Input gap 5 first.** One lookup function in `core/registry.py`,
  used for `extends` parents, model-typed attributes and `of` model types:
  look in the requesting model's namespace; if absent, use another namespace
  only when exactly one has the id; if several do, raise naming every
  candidate key (design D10). Replace the three suffix scans
  (`ModelRegistry.resolve_extends`, `_find_model_in_registry` for
  `ModelRegistry` inputs, `GrimoireModel._resolve_model_type`).
  `_find_model_in_registry` keeps accepting a plain id-keyed dict (rule 6).
  `GrimoireModel`, `create_model` and `create_model_without_validation` take
  `registry: Optional[ModelRegistry] = None` (default: the global registry),
  and nested models inherit their parent's registry.
  *Accept:* T038's R41 tests pass.

- [ ] **T042** [US6] Fix R42. Files: `src/grimoire_model/core/schema.py`,
  `src/grimoire_model/core/registry.py`,
  `src/grimoire_model/utils/inheritance.py`,
  `tests/test_inheritance_resolution.py`, `tests/test_registry.py`,
  `tests/conftest.py`, `CHANGELOG.md` only.

  Many existing tests construct a different `ModelDefinition` under the same
  id in the `default` namespace (`character`, for one). Today the second
  silently overwrites the first; after this task it raises. **First**, add an
  autouse fixture to `tests/conftest.py` that clears the default model
  registry and the default primitive registry after every test, and check the
  suite still passes with only that change. A test that still fails after that
  constructs two different definitions under one key *within itself*: give the
  second its own id or namespace, and name it in the commit.

  **Check Input gap 8 first.** The flattened definition built by
  `resolve_model_inheritance` keeps the child's `namespace` and is **not**
  registered. Choose the mechanism (for example `model_copy(update=…)`, which
  does not run `model_post_init`, or a private construction path) and say
  which in the commit. `ModelRegistry.register`: an equal definition under an
  existing key is a no-op; a different one raises `ValueError`, as its
  docstring already says. Tests in `tests/test_registry.py` asserting the
  overwrite-with-warning encode the bug: change them and name them.
  `### Changed (breaking)`.
  *Accept:* T038's R42 tests pass.

- [ ] **T043** [P] [US6] Fix R45. Files:
  `src/grimoire_model/utils/inheritance.py`,
  `tests/test_inheritance_resolution.py`, `CHANGELOG.md` only.

  `validate_model_registry`, `check_inheritance_conflicts`,
  `build_inheritance_graph` and `find_inheritance_cycles` accept a
  `ModelRegistry` or a dict (normalised by `_normalize_registry`), and look
  models up through the T041 lookup, never by raw key.
  *Accept:* T038's R45 tests pass; `tests/test_utils.py` passes.

**Checkpoint 6.** Per-phase gate.

---

## Phase 7 — The package tells the truth, and ships

**Purpose:** US7.

- [ ] **T044** [P] [US7] Fix R46: the Python floor. Files: `pyproject.toml`,
  `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `README.md`
  (badge and Requirements only), `CHANGELOG.md` only.

  **Check Input gap 9 first.** `requires-python = ">=3.10"`; classifiers
  3.10–3.12 only; `[tool.mypy] python_version = "3.10"`; `[tool.ruff]
  target-version = "py310"` (do **not** apply the `UP` fixes this unlocks in
  this task — that is a refactor outside its files; if `ruff check` then
  fails on `UP` rules, add those rule codes to `ignore` with a comment and
  stop to ask whether to modernise in a separate task); CI and release test
  matrices `["3.10", "3.11", "3.12"]`; README badge and Requirements say 3.10+.
  `### Changed (breaking)`.
  *Accept:* `uv run --python 3.10 pytest -q` passes; `uv run mypy src/` prints
  no `python_version` warning.

- [ ] **T045** [P] [US7] Fix R47 and R48. Files: `pyproject.toml`,
  `src/grimoire_model/__init__.py`, `CHANGELOG.md` only.

  Remove `pyyaml` from `dependencies`. Remove `__meta__`,
  `register_with_grimoire_context`, and the import-time `try`/`except
  Exception: pass` that calls it — `grimoire-context` has no
  `register_dict_like_type`, so the function has never done anything.
  `### Removed (breaking)` for `register_with_grimoire_context`.
  *Accept:* `grep -rn "yaml\|__meta__\|register_with_grimoire_context" src/
  pyproject.toml` prints nothing; `uv sync --extra dev` and every example
  run.

- [ ] **T046** [P] [US7] Fix R50: logging levels. Files:
  `src/grimoire_model/core/model.py`, `src/grimoire_model/resolvers/template.py`,
  `tests/test_logging.py`, `CHANGELOG.md` only.

  Model instantiation logs at `debug`. A template resolution failure is raised,
  not logged — the exception carries the message; delete the `logger.error`.
  Add a test that building 100 models and one failing `validate()` emit no
  record at `info` or above.
  *Accept:* the new test passes; `tests/test_logging.py` passes.

- [ ] **T047** [US7] Fix R49: documentation matches code. Files: `README.md`,
  `LOGGING.md`, `examples/*.py`, `examples/README.md` only.

  Walk every code block and API signature in `README.md` against `src/`:
  remove `set`, `has`, `delete` and `derived_field_resolver_type`; document
  `registry=`, `extract_reference_paths`, the write rules (transactions,
  derived and readonly, `del`), copy-on-read, `of`, `roll`/`roll_result`,
  strict definitions, and the `extends` order; drop "immutable operations".
  Run every README Python block that is self-contained. Fix any example this
  list broke. Do not change library code in this task; if documentation and
  code disagree in a way this list did not intend, stop and ask.
  *Accept:* every `examples/0*.py` runs; every API named in `README.md` exists
  (list what you checked in the commit message).

- [ ] **T048** [US7] Reconcile `AGENTS.md` with the code. Files: `AGENTS.md`
  only.

  Correct the Repository Structure table (it omits `core/registry.py`,
  `core/primitive_registry.py`, `core/exceptions.py`, `utils/paths.py`,
  `logging.py`). Add what this list made true, where a principle already
  implies it: storage is copy-on-write and reads return copies (Principle I);
  a write is a transaction (Principle V/VI); definitions are closed; lookup is
  namespace-local. **Do not add new principles and do not weaken existing
  ones.** If the code now diverges from a principle, the code is wrong: stop
  and say so.
  *Accept:* every path, command and name in `AGENTS.md` exists (verify each by
  running or grepping; list them in the commit message).

- [ ] **T049** [US7] Release 0.8.0. Files: `pyproject.toml`,
  `src/grimoire_model/__init__.py`, `CHANGELOG.md`, this file only.

  Set the version to `0.8.0` in both files (README rule 14). Rename
  `## [Unreleased]` to `## [0.8.0] - <today>` and add a fresh empty
  `## [Unreleased]` above it. Run the full per-phase gate one last time,
  including the `PYTHONHASHSEED` 0–7 loop and every example. Set this file's
  `**Status:**` to complete.

  In the commit message, list for Justin: the Wyrdbound findings this release
  resolves (F35, F36, F47; and F57 if it ships in this release), the design §7
  spec findings (S1–S3), and every `### Changed (breaking)` / `### Removed
  (breaking)` entry. Do not publish; releasing is Justin's.
  *Accept:* `uv run python -c "import grimoire_model as g;
  print(g.__version__)"` prints `0.8.0`; the gate is green.

**Checkpoint 7.** Per-phase gate. End of list.

---

## Execution order

| Done | Task | Phase | [P] | Story | Fixes |
| --- | --- | --- | --- | --- | --- |
| [x] | T001 | 0 | | — | (rebase onto F57) |
| [ ] | T002 | 1 | | US1 | tests R01–R04 |
| [ ] | T003 | 1 | | US1 | R01 |
| [ ] | T004 | 1 | | US1 | R02 |
| [ ] | T005 | 1 | | US1 | R03 |
| [ ] | T006 | 1 | | US1 | R04 |
| [ ] | T007 | 1 | | US1 | R05, R06 |
| [ ] | T008 | 1 | P | US1 | R07 |
| [ ] | T009 | 2 | | US2 | tests R08–R10, R12, R13 |
| [ ] | T010 | 2 | | US2 | R08 |
| [ ] | T011 | 2 | | US2 | R09, R10 |
| [ ] | T012 | 2 | | US2 | R11 |
| [ ] | T013 | 2 | | US2 | R12 |
| [ ] | T014 | 2 | P | US2 | R13 |
| [ ] | T015 | 3 | | US3 | tests R14, R15, R22, R23 |
| [ ] | T016 | 3 | | US3 | R15 |
| [ ] | T017 | 3 | | US3 | R14 |
| [ ] | T018 | 3 | P | US3 | R22, R23 |
| [ ] | T019 | 3 | | US3 | tests R16–R21 |
| [ ] | T020 | 3 | | US3 | R16 |
| [ ] | T021 | 3 | | US3 | R17 |
| [ ] | T022 | 3 | | US3 | R18, R19, R20 |
| [ ] | T023 | 3 | | US3 | R21 |
| [ ] | T024 | 3 | | US3 | R24 |
| [ ] | T025 | 4 | | US4 | tests R25–R30 |
| [ ] | T026 | 4 | | US4 | R25 |
| [ ] | T027 | 4 | | US4 | R26 |
| [ ] | T028 | 4 | | US4 | R27 |
| [ ] | T029 | 4 | P | US4 | R28 |
| [ ] | T030 | 4 | P | US4 | R29, R30 |
| [ ] | T031 | 5 | | US5 | tests R31–R39 |
| [ ] | T032 | 5 | | US5 | R31, R32 |
| [ ] | T033 | 5 | | US5 | R33 |
| [ ] | T034 | 5 | | US5 | R34 |
| [ ] | T035 | 5 | | US5 | R35 |
| [ ] | T036 | 5 | | US5 | R36 |
| [ ] | T037 | 5 | P | US5 | R37, R38, R39 |
| [ ] | T038 | 6 | | US6 | tests R40–R45 |
| [ ] | T039 | 6 | | US6 | R40 |
| [ ] | T040 | 6 | | US6 | R43, R44 |
| [ ] | T041 | 6 | | US6 | R41 |
| [ ] | T042 | 6 | | US6 | R42 |
| [ ] | T043 | 6 | P | US6 | R45 |
| [ ] | T044 | 7 | P | US7 | R46 |
| [ ] | T045 | 7 | P | US7 | R47, R48 |
| [ ] | T046 | 7 | P | US7 | R50 |
| [ ] | T047 | 7 | | US7 | R49 |
| [ ] | T048 | 7 | | US7 | (AGENTS.md) |
| [ ] | T049 | 7 | | US7 | (release 0.8.0) |

---

## Deferred, and why each is out

| Thing | Why |
| --- | --- |
| `uv.lock`, and `uv` instead of `pip` in CI | `AGENTS.md` §1: raise it, do not do it as a side effect. Raised in design §9. |
| Validation warnings | D8 removes an unimplemented `severity`; building warnings is a feature. |
| GRIMOIRE spec changes | README rule 10. S1–S3 go to Justin via T049's commit message. |
| Wyrdbound changes | Never from this repository. Its pin moves after it runs its own suite against 0.8.0. |
| Modernising syntax for Python 3.10 (`X \| Y`, builtin generics) | T044 raises the floor; a repo-wide `UP` refactor is its own task if wanted. |
| Performance work on transactional writes | Design §8. Measure first, in a later feature. |

---

## Input gaps to close before starting

1. **~~F57 merged~~ — closed.** `fixNestedModelWrite` is on `main`
   (`228eaec`, changelog `9b76519`); T001 rebased onto it. Its CHANGELOG entry
   is under `[Unreleased]`, so it ships inside 0.8.0 unless Justin cuts a
   0.7.2 first — if he does, T049 leaves that section as released.
2. **Closed definitions and undeclared keys (D5, D6).** Wyrdbound's
   `translate_model` hands GRIMOIRE attribute declarations to
   `ModelDefinition.model_validate` as parsed. Confirm that no attribute in
   `knave-1e` or `wyrdbound-quickstart-1e` carries a key outside
   `type default range enum derived of optional description`, and that no
   flow writes an undeclared path. **Ask before T010 and T023.**
3. **Removing `severity` and `fields` (D8).** Confirm, or say to implement
   warnings instead. **Ask before T013.**
4. **`pattern` as a full match (D9).** Confirm. **Ask before T037.**
5. **Cross-namespace fallback (D10).** Unique-match fallback (proposed) or no
   cross-namespace lookup at all. **Ask before T041.**
6. **`extends` order (D11).** Check whether any shipped system model has two
   parents declaring the same attribute; if so, its resolved shape changes.
   **Ask before T039.**
7. **List elements become models (D16).** A data-shape change (README L2) for
   `inventory: {type: list, of: item}` in both systems. Confirm Wyrdbound's
   state serialization handles `GrimoireModel` list elements as it handles
   nested models. **Ask before T033.**
8. **Duplicate registration raises (R42).** Wyrdbound re-registers on system
   reload through a scratch namespace it clears; confirm nothing registers a
   *different* definition under a live key. **Ask before T042.**
9. **Python floor 3.10 (D14).** Confirm. **Ask before T044.**
10. **Approving this feature approves F35, F36 and F47's library changes**,
    each recorded in Wyrdbound as "not changed without Justin's go-ahead".
    Say so explicitly, or name the ones to hold back.
