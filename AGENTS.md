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
The **structure is deterministic and code-owned** under both shipped strategies —
breadth-preserving allocation across strata, budget arithmetic, **must-includes as the
one hard rule** (bypass the budget, never dropped) — over **cheap pre-extract signals**
(recency, light appraisal tier, origin/upload priority, screen confidence; no
embeddings use — cosine relevance was cut at rev 4, the semantic dimension being
already spent by screening + stratification). `coverage_stratified_v1`
(default, suite path) is deterministic end-to-end; **`llm_rerank_v1`** (live skeleton
path) replaces only the *within-stratum ordering* with bounded batched
schema-constrained judgment calls on contested strata — per-doc scores + reasons under
the repo's **second product prompt** (`select_rerank_v1`, lead-authored), pre-run call
budget, per-doc **fallback to the deterministic composite** (flagged `rank_fallback`,
never dropped); scores order, **never exclude**. Steering enters through the
**selection directive** — a first-class, declarative facade argument (budget ·
must-includes · **soft boosts over columns + tags**, the scoping vocabulary · weight
emphasis; soft = re-weights, never excludes) — designed as the tool-call surface the
future capability agent authors just-in-time at invocation (v3.0 sources it from the
scope context; agent-authored directives, rerank-quality evals, Cohere-class
cross-encoders at the `retrieve` seam, and the capability-run entity are recorded
seams). Realised as the spec's shared strategy-parameterised `select` verb. Durable
output = one run-scoped `selection_result` row per (scope, run) carrying the
**bidirectional rationale** (what was selected and why; aggregate exclusion reasons +
notable flagged exclusions), the executed directive, rerank provenance, and the
deepening-selection **escalation-trigger flags** computed now — the steer-point *pause*
machinery stays a recorded seam. Selection is run-local, never canonical;
`not_selected` is derivable coverage state, never persisted as doc status. Gated
changes riding this slice: schema (`selection_result`, project-scope-guarded; table
count 19 → 20) · public interface (`"select"` registry entry + `run_harness
ranking_backend`, stub default) · **runtime egress: the `select_rerank_v1` generation
surface (titles + abstracts + intent, contested strata only)**. One spec flow-back
rides the slice (components §6 select
realisation: procedure → procedure with bounded generative rerank). `make verify` stays
deterministic and egress-free (stub ranker). Build per
`docs/tasks/010-select/contract.md`. Stay within the contract's scope and stop
conditions; all other capabilities and seams remain deferred (`docs/deferred.md`).