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
- Agent-side model routing: the lead (Fable 5) plans, judges, synthesizes; delegate volume via the
  pinned agents in `.claude/agents/` — `deep-reasoner` (Opus) for reasoning offload, `fast-worker`
  (Sonnet) for mechanical sweeps and search — and Codex for the heterogeneous peer (review/rescue).
  **Prompt-bearing work (product prompts, judge rubrics, eval criteria) is lead-only — never
  delegated to a weaker model.** Details: `docs/agentic-ops/harness.md` § Agent-side model routing.
- Deterministic work (date math, parsing, counting, format conversion) runs as a script or command,
  not in latent space — if the same question twice must give the same answer, compute it.
- Do not change schema, auth, dependencies, CI, production config or public interfaces without approval.
- Never edit generated files or secrets.
- Touch only what the task requires.

# Current phase
Implementation — task `007-acquire`.

Tasks `001-walking-skeleton`, `002-test-db-split`, `003-source-snapshot`, `004-screen`,
`005-classify`, and `006-appraise` are complete (merged). The active slice adds the `acquire`
component (EB front edge): metadata-only acquisition through the `search` seam — a
`SearchBackend` protocol with **fixture-backed OpenAlex and Overton backends** (academic +
grey literature, the two v3.0 backends the spec names) replaying sanitized fixtures derived
from dev-time-recorded real responses — authentic structure, fabricated values (zero runtime
egress; live HTTP backends stay behind the egress gate). Acquired
results ingest as text-in-hand snapshots (`origin="acquired"`, `text_basis="abstract_only"`),
every search call emits a per-backend `search.executed` governance event, and each acquire run
writes a `search_coverage_record` row. Two approved schema gates ride this slice: the
`screening_scope` → `evidence_scope` rename and the new `search_coverage_record` table. Build
per `docs/tasks/007-acquire/contract.md`. Stay within the contract's scope and stop conditions;
all other capabilities and seams remain deferred (`docs/deferred.md`).