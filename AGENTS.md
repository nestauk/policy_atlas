# Agent protocol

- Use the commands in the `Makefile`.
- For non-trivial work, plan before editing.
- Write Google-style docstrings (`Args:`/`Returns:`/`Raises:` sections) for public modules,
  classes and functions; keep them concise. Trivial helpers and test functions need none.
- Use `docs/specs/` for product and system intent — **living intent, not golden**. If building shows
  a spec is wrong or improvable, flag it and flow the change back (`docs/specs/README`); don't
  silently obey it or silently deviate.
- Use `docs/tasks/<task-id>/` for per-task artefacts: `contract.md` (scope), `rubric.md`
  (completion criteria, when risk is medium or high), `verification.md` (evidence, or in the PR).
  `<task-id>` is `NNN-slug` (zero-padded, e.g. `001-example-slice`). Templates live in `docs/tasks/_templates/`.
- Do not change schema, auth, dependencies, CI, production config or public interfaces without approval.
- Never edit generated files or secrets.
- Touch only what the task requires.

# Current phase
Implementation — task `005-classify`.

Tasks `001-walking-skeleton`, `002-test-db-split`, `003-source-snapshot`, and `004-screen` are
complete (merged). The active slice adds the `classify` component: per-document evidence-type
classification on the screened-in set, persisting results in `source_classification_result`
(columns: `primary_evidence_type`, `open_tags`) scoped by `screening_scope`.
Build per `docs/tasks/005-classify/contract.md`. Stay within the contract's scope and stop conditions;
all other capabilities and seams remain deferred (`docs/deferred.md`).