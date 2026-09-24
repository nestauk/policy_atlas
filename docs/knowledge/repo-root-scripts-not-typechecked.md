---
type: Integration quirk
title: Repo-root scripts/*.py are outside the typecheck gate
description: `make typecheck` runs `mypy src tests` from `backend/` (`backend/pyproject.toml` `files = ["src", "tests"]`), so nothing under the repo-root `scripts/` — including the destructive operator script `scripts/ops_remove_scoping_tasks.py` and the rename tooling — is ever typechecked. They are tested (`backend/tests/scripts/`), not typed.
tags: [tooling, mypy, scripts, make-verify, task-044]
timestamp: 2026-09-17
---

# Rule

A script under `scripts/` gets its correctness from `backend/tests/scripts/`, not from mypy. When
a script becomes destructive or long-lived, either add it to mypy's `files` (and accept the
`policy_atlas` import path from the repo root) or write the behavioural test first — the
review stack treats "tested, untyped" as acceptable and "neither" as a finding.

# Why

Found at the 044 review stack by two lanes independently while checking the rollback remedy
(`ops_remove_scoping_tasks.py` — list-only by default, `--apply` guarded, FK order tested end to
end at `tests/scripts/test_ops_remove_scoping_tasks.py`). Adding `scripts/` to the mypy files is
deferred (`docs/deferred.md` § Codebase health).

# Citations

- `backend/pyproject.toml` `[tool.mypy] files`, `backend/Makefile` `typecheck`
- `scripts/ops_remove_scoping_tasks.py`, `backend/tests/scripts/test_ops_remove_scoping_tasks.py`
