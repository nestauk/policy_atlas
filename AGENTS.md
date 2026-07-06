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
Implementation — task `010-select`.

Tasks `001-walking-skeleton` through `009-characterise` are complete (merged). The active
slice adds **select** — EB component 6, opening the deep terminus: **coverage-aware
stratified selection over the run's characterisation strata** (themes + the counted
`unclustered` stratum), choosing the subset for Tier-1 extraction under a budget.
A **fully deterministic slice** — no prompts, no generation, no new dependencies:
breadth-preserving allocation across strata, within-stratum ranking over **cheap
pre-extract signals** (embedding relevance to the scope intent — the first reader of the
009 chunk vectors — recency, light appraisal tier, origin/upload priority), and
**must-includes as the one hard rule** (bypass the budget, never dropped). Realised as
the spec's shared strategy-parameterised `select` verb with EB's
coverage-aware-stratified strategy as the one shipped implementation. Durable output =
one run-scoped `selection_result` row per (scope, run) carrying the **bidirectional
rationale** (what was selected and why; aggregate exclusion reasons + notable flagged
exclusions) plus the deepening-selection **escalation-trigger flags** computed now
(large/user-nominated-stratum exclusions, thin base) — the steer-point *pause* machinery
stays a recorded seam. Selection is run-local, never canonical; `not_selected` is
derivable coverage state, never persisted as doc status. No new egress front: the one
live call is a single intent-embedding via the 009-approved `EmbeddingBackend`
(stub-covered in the suite; `make verify` stays deterministic and egress-free). Gated
changes riding this slice: schema (`selection_result`, project-scope-guarded; table
count 19 → 20) · public interface (`"select"` registry entry; no new `run_harness`
parameter). Build per `docs/tasks/010-select/contract.md`. Stay within the contract's
scope and stop conditions; all other capabilities and seams remain deferred
(`docs/deferred.md`).