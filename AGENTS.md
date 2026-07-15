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
Implementation — task `024-steering-surface` (design in progress,
2026-07-15). The steering slice: (a) **steering-event persistence** —
check-ins, pauses/steer-points (options + fired triggers), user
decisions (continue / adjust / reselect / abort), rejected
adjustments, refused intents and Unattended auto-resolutions become
durable canonical events so a front-end can rebuild the orchestrated
conversation's decision history from Postgres alone
(execution-orchestration + §9 event-log spine; the run-less-boundary
FK constraint is a named design decision); (b) **free-text steering
interpretation** — a planner-pattern LLM seam that compiles a user's
prose intent at a pause into the bounded steering vocabulary
(option / adjust-delta / mode / nudge / abort), confirm-before-apply,
honest refusal as the fallback, verbatim-text + interpreted-action
provenance (revises 017's one-LLM-call sequencing invariant —
runtime-egress hard gate); (c) **steer-point expansion study** —
design-phase inventory of all EB components for decision-shaping
moments worth surfacing as steer points, ranked in
`docs/tasks/024-steering-surface/steer-point-study.md`; owner
ship-list (contract gate, 2026-07-15): **S0 + S1 + S2**; plus (d) the
**minimal `capability_run` entity** (owner, rev 3 — the walk's durable
identity + `runs.capability_run_id`; the one approved schema
addition). Tier 3 (runtime egress + schema + prompt-bearing surface).
Sequenced next after 024: **025 co-pilot Q&A** (owner, 2026-07-15) —
read-only follow-up answers over collected evidence; then the eval
slice.

Tasks `001-walking-skeleton` through `022-synthesis-refinement` are
complete (merged) — the EB chain runs end-to-end live behind the
thin v1 orchestrator with prose-first synthesis output shape v2
(ADR 0015), select at standard depth, fail-closed country
filters/groups, IOF schema v2 (ADR 0016), the ICF second finding
schema + kind-typed `query_findings` + kind-spanning membership
bridge (ADR 0017), multi-facet grouping on the shared two-stage
clustering engine + the 022 cost/surface work (ADR 0018, −49%
synthesis cost), and the pinned prompt surfaces (`planner_v5`,
`extract_iof_v7` + vetter, `extract_icf_v2` + vetter,
`synthesise_section_v7` (v6 frozen as the cost-harness baseline),
`synthesise_sections_v2`). 018 trailing lanes: **C4 demo surface**
(codex lane, throwaway `demo-live-run` branch — never merges) and
**D2 rehearsal** (owner-scheduled). After 023: the eval slice
(cost as a first-class axis), then Bedrock, then the workspace
cluster. All other seams remain deferred (`docs/deferred.md`).

