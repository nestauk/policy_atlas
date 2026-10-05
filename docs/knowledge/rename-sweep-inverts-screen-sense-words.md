---
type: Convention
title: A code-word sweep inverts prose, identifiers and message strings already written in the screen sense
description: When the code word and the screen word for one entity differ (ADR 0031 era: code `project` = screen Task), comments, docstrings, a few identifiers and — worst — user-facing message strings are written in the screen sense; a code-word sweep turns "a Task inside a Project" into "a Task inside a Task". Pair removed/added lines that name both entities, and grep message strings for doubled words, before the gate.
tags: [rename, vocabulary, sweep, review, task-038]
timestamp: 2026-09-05
---

# Rule

Before a vocabulary sweep closes, run three inversion checks on its diff:

- **Prose:** pair every removed line carrying the old code word (title-case
  too) with its replacement and keep the pairs that also name the *other*
  entity, a container, or a visibility phrase — those were written in the
  screen sense and now read as nonsense. 038 restored 24 such lines.
- **Identifiers:** a name that was already screen-sense (`ProjectPicker`
  picked Projects, `showProjectPrefix`, `COPY.noProject`) inverts to the
  wrong entity; the frontend was protected by never-mapping the exact
  screen words `Task`/`Project`, the backend was not.
- **Message strings:** grep the swept tree for doubled words (`task's task`,
  `out of the task`, `tasks in one`). 038's two 409 messages —
  "leave the task out of the task" — shipped past the build gate because the
  test asserting them was swept in lockstep; three review lanes found them.

# Why

The sweep maps *code* words. Anything written for a reader — comments,
labels, error messages — already used the screen words, so the mapping is
wrong for exactly those lines, and a test that asserts the message is renamed
alongside it and stays green.

# Watch out

- A test swept in lockstep is not a guard: check the assertion's wording
  against the entity it names, not against the code.
- Same family: [stored-json-keys-are-vocabulary-too](stored-json-keys-are-vocabulary-too.md),
  [two-step-rename-needs-ledger-and-anchored-exemptions](two-step-rename-needs-ledger-and-anchored-exemptions.md).

# Citations

- [038-vocabulary-alignment/verification.md](../tasks/038-vocabulary-alignment/verification.md) (§ Phase 3 "Screen-sense prose", § Phase 4 "Screen-sense identifiers", § Review findings R2)
- `backend/src/policy_atlas/api/routers/tasks.py` (the two `visibility_conflict` messages), `backend/tests/api/test_visibility_invariant.py`
