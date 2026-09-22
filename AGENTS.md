# Developer Guide & AI Guidance

This document is the authoritative governance and quick-reference guide for
working on the grimoire-model codebase. It binds all code, review, and
planning. Where a section uses MUST / MUST NOT, compliance is not optional;
SHOULD carries a stated rationale and requires justification to deviate.

`grimoire-model` is a **dict-like model system** with schema validation,
derived fields, inheritance and template expressions. It is the runtime half
of a GRIMOIRE model definition: the spec says what a model means, this library
instantiates one and tells you whether the data is valid.

## AI Guidance

Always remember the following points as you are working on this code base:

1. **Use `uv`** for dependency management and command execution
   (`uv sync --extra dev`, `uv run …`). If a project `.venv` exists and is
   usable, `source .venv/bin/activate` works too, but `uv` is the reference
   path. This repository does not currently commit a `uv.lock`; adding one
   would make installs reproducible and is worth raising, but do not add it
   as a side effect of another change.
2. **Prefer explicit errors over fallbacks** when a fallback would mask an
   issue. We want to fix issues so we can have a stable system.
3. **Follow good software development practices** (like SOLID).
4. **Simpler is better.**
5. **Provide functionality in a clear and maintainable manner.** Avoid
   special-cases or hack fixes simply to get around issues.
6. **Do NOT make bandaid fixes** that break the rearchitecture goals for the
   library. Always respect the architectural boundaries.
7. **After all code changes, run the quality gate** until it is clean:
   `uv run ruff format src/ tests/ && uv run ruff check src/ tests/ --fix &&
   uv run mypy src/ && uv run pytest -q`.
8. **Avoid lines longer than 88 characters** (E501 ruff check).
9. **This is a model library.** It should be predictable, well-typed and have
   minimal dependencies. Don't add features that compromise those.
10. **Thread safety is critical** — all public APIs must be thread-safe and
    work correctly in concurrent environments.
11. **Tests accompany every behavioural change.** A fix without a test that
    fails before it is not finished.
12. **Update `CHANGELOG.md`** for every user-visible change, following Keep a
    Changelog, and bump the version in both `pyproject.toml` and
    `src/grimoire_model/__init__.py`.

## Repository Structure

| Path | What it is |
| --- | --- |
| `core/schema.py` | `ModelDefinition`, `AttributeDefinition`, the registry |
| `core/model.py` | `GrimoireModel` — instantiation, defaults, validation entry |
| `resolvers/derived.py` | Derived fields, dependency tracking, batching |
| `resolvers/template.py` | Jinja2 expression evaluation |
| `validation/validators.py` | Field validators and the validation engine |
| `utils/inheritance.py` | `extends` resolution |

## Core Principles

### I. Fail loudly, never silently

The failure this library must never produce is a model that instantiates
successfully and is quietly wrong. That has happened: leaf definitions inside
an anonymous nested group were dropped, so derived leaves silently did not
compute and declared ranges silently did not apply. Nothing raised.

A constraint that cannot be evaluated MUST become an error, never a skipped
check. An expression that cannot be resolved MUST raise, never render empty
or fall back to a builtin. When in doubt, raise.

### II. Expressions use bare names, and nothing else is in scope

Derived, `range` and `validations` expressions are evaluated against the model
instance. Attributes are referenced by **bare name**, with root-relative
dotted paths for nested attributes, inside `{{ }}`.

Jinja2's globals (`range`, `dict`, `namespace`, `cycler`, `joiner`, `lipsum`)
are cleared from the evaluation environment. They are a hazard rather than a
feature here: a misspelled attribute colliding with one resolved to the
builtin instead of raising, and both `range` and `dict` are plausible
attribute names. Filters live in `env.filters` and are unaffected.

Do not add an instance prefix. `$` was tried and removed — it is not a valid
Jinja2 identifier, so `{{ $.field }}` cannot parse. `this.` is not supported
and is not in the specification.

### III. A group is an attribute that has attributes

An anonymous nested group declared inline with no `type` of its own is
represented by `AttributeDefinition.attributes`. This mirrors the YAML shape
1:1 and needs no synthesized model names or registry entries.

Groups remain **plain dicts** at runtime; they are not instantiated as nested
`GrimoireModel` objects. Consumers serialize model data, so the data shape is
part of the contract — changing it is a breaking change, not an internal
detail.

Anything that walks attributes MUST recurse into groups: derived registration,
defaults, validation, range resolution. A new traversal that forgets to
recurse reintroduces Principle I's failure.

### IV. Validators stay context-free

A validator receives a value, a field name and an attribute definition. It
does not receive model data or a template resolver.

Where a constraint needs the model — a relative range like
`"0..{{ max_hp }}"` — the *model* resolves it and hands the validator a
concrete constraint. This keeps validators simple and testable, and it means
resolution happens once, in a place that knows derived fields have already
been computed.

### V. Derived fields batch at commit boundaries

Derived fields recompute on write with dependency tracking and topological
ordering. Writing several inputs to one derived field MUST be batched
(`BatchedDerivedFieldResolver.start_batch()` / `end_batch()`), or observers
see inconsistent intermediate states and the same field recomputes repeatedly.

## Engineering Standards

- **Explicit errors over fallbacks.** Silent failures are prohibited.
- **Type hints on all public APIs.** `mypy src/` MUST pass with no errors.
- **Docstrings on all public modules, classes and functions.**
- **88 character lines** (E501).
- **Imports at the top.** PEP 8, always.
- **Thread safety** on all public APIs.
- **Backward compatibility** of the runtime data shape (Principle III).
- **Minimal dependencies.** Pydantic, Jinja2 and pyrsistent earn their place;
  a new dependency needs a stated reason.

## Quality Checks

```bash
uv run ruff format src/ tests/
uv run ruff check src/ tests/ --fix
uv run mypy src/
uv run pytest -q
```

Run them iteratively until clean, before every commit.

## Governance

`AGENTS.md` is binding on all work in this repository.

The GRIMOIRE specification lives in the `wyrdbound/grimoire` repository and is
authoritative for what a model definition means. It is also ours and it has
had real bugs: where the spec, this library and the shipped systems disagree,
establish what is true by running the code rather than assuming the document
wins — then file the finding and propose a spec change. **Never change the
specification without Justin's explicit confirmation.**
