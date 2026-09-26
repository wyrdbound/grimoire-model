# grimoire-model — Feature Task Index

This directory holds the design documents (`NN-<slug>.md`) and execution task
lists (`NN-<slug>-tasks.md`) for `grimoire-model` features. Each task list is
written to be run **one task at a time, in order, by a coding agent that does
not hold the design doc in context**. Every task names its files, restates the
rule it implements, and states its own acceptance check. Do not read ahead; do
not batch.

Documents are numbered because the roadmap is ordered. The number is the build
order, not a priority.

The rules below are **binding on every task in every list in this directory**.
They exist to keep each task small, committed, and cheap — so a long list does
not burn tokens re-fixing lint at the end, and so a session never exhausts its
context mid-list.

---

## The roadmap

| # | Feature | Ships | Tasks |
| --- | --- | --- | --- |
| 01 | [Review Remediation](01-review-remediation.md) | Every defect from the 2026-09-26 full review fixed: expressions that raise, private storage, transactional writes, ordered derived fields, spec-conformant types and inheritance. Released as 0.8.0 | [list](01-review-remediation-tasks.md) |

**Feature 01 builds on the `fixNestedModelWrite` fix (Wyrdbound finding F57),
merged to `main` as `228eaec`.** Its first task, T001 (done), rebased onto
that merge and did nothing else. Several of its tasks extend the F57 write path; none of them
redo or revert it.

The findings register — what is wrong, how to reproduce it, and which task
fixes it — is §3 of [`01-review-remediation.md`](01-review-remediation.md).
Three places where the GRIMOIRE specification and this library disagree are
listed in its §7. They are **raised, not fixed**: the specification is only
changed with Justin's explicit confirmation.

---

## Global rules for the executing agent

1. **Do exactly one task per run.** Do not start the next task until the
   current one is committed.
2. **Do not refactor code outside the task's listed files.** Stage only the
   files that task created or changed.
3. **Do not add libraries.** Pydantic, Jinja2, pyrsistent and grimoire-logging
   are the runtime dependencies (`AGENTS.md`, "Minimal dependencies"). If you
   think you need another, stop and ask.
4. **All Python commands run through `uv`** — `uv sync --extra dev`,
   `uv run …`. No bare `pip`, no bare `python`. This repository does not commit
   a `uv.lock`; do not add one as a side effect of a task (`AGENTS.md` AI
   Guidance §1).
5. **Line length is 88 characters** (ruff `E501`). Imports at the top of the
   file, always.
6. **Every task must end with the quality gate passing:**

   ```bash
   uv run ruff format src/ tests/ && uv run ruff check src/ tests/ --fix && \
   uv run mypy src/ && uv run pytest -q
   ```

   plus the task's stated acceptance check. If it fails, fix it before
   finishing.
7. **Never invent file paths.** Use exactly the paths given.
8. **Never delete or weaken a passing test to make a task pass.** Some existing
   tests encode a behaviour this feature corrects. A task that corrects one
   *says so* and names the test; only then update its assertion, and say so in
   the commit message. If an existing test fails and the task does not name
   it, **stop and ask** — you have found either a bug in your change or a gap
   in the plan.
9. **If a task is ambiguous, stop and ask** rather than guessing.
10. **The GRIMOIRE spec is authoritative and may be wrong.** It lives in the
    `wyrdbound/grimoire` repository (`spec/model_spec.md`). When the spec,
    this library and a shipped system disagree, find out which is right by
    running the code — do not assume the document wins. Record what you find
    in the feature doc's spec-findings section and **propose** a spec change;
    never edit the spec, and never edit the Wyrdbound repository, from a task
    in this directory.
11. **Forward references are notes, not dependencies.** A task may mention a
    later task for orientation; the current task is always completable
    without it. If a task's acceptance check genuinely needs code from a later
    task, that is a **bug in the plan**. Stop and say so; do not pull the later
    task forward and do not weaken the check.
12. **Tests come first.** A test task is done when its tests **fail for the
    stated reason** — a wrong value, a missing raise, a missing name — never a
    syntax or import error in the test file itself. A fix task is done when
    those tests pass and nothing else changed behaviour.
13. **`CHANGELOG.md` is updated in the same commit as every user-visible
    change**, under the `## [Unreleased]` heading, in Keep a Changelog form.
    Breaking changes go under `### Changed (breaking)` or `### Removed
    (breaking)` and say what a caller must now do.
14. **One list, one release.** The version in `pyproject.toml` and
    `src/grimoire_model/__init__.py` is bumped **once, by the list's release
    task**, not per task and not per checkpoint. A version per task would mark
    releases that are never published. `AGENTS.md` AI Guidance §12 ("bump the
    version") is satisfied by that task; where this README and `AGENTS.md`
    disagree on *how* a list is run, this README wins (see Governance).
15. **Commit after each task, then continue.** Once a task passes its
    verification, commit it with a concise Conventional Commits message
    (`fix:`, `test:`, `feat!:`, `chore:` …), then proceed immediately to the
    next task. **Never bundle two tasks into one commit.** In that same
    commit, tick the task's box `[x]` in the list and in its Execution order
    table so later agents can see what is done.
16. **Check context usage after each task.** After the commit lands, check
    context. If it exceeds 200,000 tokens, write a handoff document to
    `planning/handoffs/`, start a fresh session from it, and stop working in
    the current session.

---

## The four rules that are specific to this library

These restate `AGENTS.md`'s principles as they bite during remediation. Each
one is cheap to violate by accident while fixing something else.

### L1 — Fail loudly, never silently

The failure this library must never produce is a model that instantiates, or a
write that succeeds, and is quietly wrong. No fix in this directory may add a
fallback, a `try`/`except` that logs and continues, a skipped constraint, or a
default that papers over a missing value. When in doubt, raise. (`AGENTS.md`
Principle I.)

### L2 — The runtime data shape is a contract

Anonymous groups stay plain dicts; they are never instantiated as models.
Consumers serialize model data, so a change to what `dict(model)` contains is a
breaking change and needs a decision in the feature doc, not a convenience in a
task. (`AGENTS.md` Principle III.)

### L3 — Do not change the injected-resolver protocols

Wyrdbound injects its own template resolver into this library. The
`TemplateResolver` protocols in `resolvers/template.py` and
`resolvers/derived.py` (`resolve_template`, `is_template`,
`extract_variables`) are therefore a public contract. A fix that needs more
from an expression than those methods give goes in a library function, not a
new protocol method.

### L4 — Every public API is thread-safe

`AGENTS.md` AI Guidance §10. A fix that adds shared mutable state adds the lock
that protects it in the same task.

---

## Per-phase definition of done

At each **Checkpoint** in a list, additionally:

- `uv run pytest --cov=grimoire_model` reports a TOTAL of **≥ 90%** (the level
  at 0.7.1).
- Every script in `examples/` runs to completion:
  `for f in examples/0*.py; do uv run python "$f" > /dev/null || echo "FAIL $f"; done`
  prints nothing.
- From the checkpoint that closes derived-field ordering onward, the full suite
  passes under eight hash seeds:
  `for s in 0 1 2 3 4 5 6 7; do PYTHONHASHSEED=$s uv run pytest -q || break; done`.
- `CHANGELOG.md`'s `[Unreleased]` section lists every user-visible change the
  phase made.

---

## Governance

`AGENTS.md` at the repo root is binding on every task in every list here. Where
a task list and this README disagree, this README's execution rules win for
*how* to run the list; `AGENTS.md`'s principles win for *what* the code must
be. If a task appears to require breaking an `AGENTS.md` principle, the task is
wrong: stop and say so.
