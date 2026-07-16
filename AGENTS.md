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
Implementation — task `024-steering-surface` (design in progress;
contract rev 4 rewritten from scratch 2026-07-16, awaiting owner
approval). **The steering slice — state-of-the-art human-in-the-loop
(owner direction; deliberately large, no splitting).** Organising
principle: every decision surfaces in the durable record; the mode
moves the *decider* (user ↔ orchestrator), never visibility. Strands:
(1) durable steering record — steering events on `event_log` + the
`capability_run` walk entity (the one approved schema addition) + the
`steering_history` projection (front-end rebuilds the decision
history from Postgres alone); (2) **one orchestrator, three moments**
(planning turn · free-text router · boundary watch) behind one seam +
`orchestrator_v1` prompt family — router: prose → confirmed
multi-stage bounded deltas; watch: routes/decides per the decider
dial within the full user surface, authors run-specific options,
fail-safe to the deterministic floor; (3) the **steer-point lattice**
P1 (search exception) · P2 (pre-select evidence-base coverage) · P3
(deepening-selection, enriched + preview) · P4 (synthesis shape) over
**widened grammars** (channels B1/B3/B5 + B2′ finding-relevance
annotator; keys D1/D3/D5–D9) with additive-vs-replacement re-run
modes first-class; (4) modes renamed to delegation postures;
Unattended = discretion-is-the-mode with planner-authored standing
instructions. Design record: `docs/tasks/024-steering-surface/`
`steerability-refinement.md` (annex, binds the contract) +
`steer-point-study.md`. Tier 3 (runtime egress + schema +
prompt-bearing surfaces). Build sizing ~3–3.5× the original rev 3
scope. Sequenced after 024: **025 co-pilot Q&A + the per-user
transcript store** (owner, 2026-07-16); then the eval slice.

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

