---
type: Integration quirk
title: Parallel mypy runs sharing one .mypy_cache can report phantom errors in files nobody edited
description: Five delegated agents ran mypy at once on the 064a build and the shared backend/.mypy_cache produced a false attr-defined error in an unchanged conftest.py. Clear the cache before believing an error in a file nobody touched; one typecheck at a time per checkout.
tags: [mypy, tooling, parallel-agents, cache, integration-quirk]
generated:
  by: process:okf-migrate
  at: 2026-11-16
sources:
  - resource: "../tasks/064a-security-quick-wins/verification.md"
    title: "[task 064a verification](../tasks/064a-security-quick-wins/verification.md) \u00a7 Review handoff, build incidents."
  - resource: "backend/Makefile"
    title: "`backend/Makefile` typecheck target."
---

# Rule

mypy's incremental cache (`backend/.mypy_cache`) is not safe under concurrent writers.
When several agents in one checkout run `mypy` at the same time, one run can read a
cache file another is half-writing and report an error that the source does not contain.
On the 064a build the symptom was `attr-defined` in `tests/conftest.py`, a file no phase
had touched; `rm -rf backend/.mypy_cache` and one clean run made it go away.

So: an error in a file nobody edited, during a parallel build, is a cache artefact until
proven otherwise — clear the cache and re-run before anyone "fixes" the file. Delegated
build briefs should leave the typecheck to the lead's gate (`make verify-fast` or
`make verify`), one run at a time per checkout, rather than each agent running its own.

Related: the per-checkout isolation that `make test` gives the database
([parallel-agent-test-databases](parallel-agent-test-databases.md)) has no mypy
equivalent; `MYPY_CACHE_DIR` per agent would be one.
