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
Implementation — task `019-folding-pass` (contract + plan APPROVED
2026-07-12, all five gate decisions decided — build per
`docs/tasks/019-folding-pass/plan.md`).

Tasks `001-walking-skeleton` through `018-dress-rehearsal` are
complete (merged) — the EB chain runs end-to-end live behind the thin
v1 orchestrator with the prose-first synthesis output shape v2
(ADR 0015), refreshed models, and the refine-replay loop's pinned
prompt surfaces (`planner_v2`, `extract_iof_v5` + finding vetter,
`synthesise_section_v5`, `synthesise_sections_v2`). Two 018 remainder
steps run in parallel on their own lanes, outside 019's scope:
**C4 demo surface** (codex lane, throwaway `demo-live-run` branch —
never merges) and **D1/D2** (measured-band re-seed + live rehearsal,
owner-scheduled).

`019-folding-pass` is **pre-eval Slice A** of the owner-adjudicated
sequencing (2026-07-12; criterion: schema/vocabulary/composition
changes land BEFORE evals, prompt/constant tuning after, with eval
cover): search-response caching (cache-before-throttle), embed-pass
429/batch robustness, fail-closed country-filter allowlists +
deterministic country-group expansion (planner capability-line half
is lead-only, replay-evidenced), Langfuse thread-context propagation,
coverage-record stop/attribution grain (gated one-line CHECK
migration), `_discover_themes` rejection-detail persistence,
`bind_contextvars`/`exc_info` + `pytest-socket` riders, and the gated
`is_retracted`-at-screening eligibility decision. Slices B (extract
schema bump) and C (synthesis multi-facet + cost/surface) follow,
then the eval slice with cost as a first-class axis. Build per
`docs/tasks/019-folding-pass/contract.md`; stay within its scope and
stop conditions. Bedrock migration, retrieval-boost grammar v2 and
all other seams remain deferred (`docs/deferred.md`).

