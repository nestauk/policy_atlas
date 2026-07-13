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
Implementation — task `022-synthesis-refinement` (design step 1 —
contract being drafted; Tier 3). This is Slice C of the
owner-adjudicated pre-eval sequencing (2026-07-12), shipped as
ONE slice with two phases (owner call, 2026-07-14): **Phase 1 —
multi-facet grouping** in the owner's in-component shape (facet
fan-out within one `group` run; `facet` moves to group-row grain —
small schema gate; per-call facet value-list scale is a
first-class design constraint, live-proven limit ~184 values —
`docs/knowledge/facet-partition-value-list-scale-limit.md`).
**Phase 2 — cost + surface**, one prompt-version bump
(cache-prefix engineering, repair-input scoping, tool-return
hygiene, writer read-tool scoping plumbing, pre-synthesise steer
point, id-carrying repair schema, screen-confidence retrieval
boost gate). Contract agenda: the owner-reopened rulings
(grammar-v2 boundary, judge-envelope clamp, unspanned-lane
coverage, 018's writer-envelope metadata A/B queue, effect_basis
judge-envelope candidate, hybrid dimension search build-or-defer,
cross-kind UNION view).

Tasks `001-walking-skeleton` through `021-icf` are complete
(merged) — the EB chain runs end-to-end live behind the thin v1
orchestrator with prose-first synthesis output shape v2 (ADR 0015),
select at standard depth, fail-closed country filters/groups, IOF
schema v2 (ADR 0016), the ICF second finding schema + kind-typed
`query_findings` + kind-spanning membership bridge (ADR 0017), and
the pinned prompt surfaces (`planner_v3`, `extract_iof_v6` +
vetter, `extract_icf_v1` + vetter, `synthesise_section_v5`,
`synthesise_sections_v2`). 018 trailing lanes: **C4 demo surface**
(codex lane, throwaway `demo-live-run` branch — never merges) and
**D2 rehearsal** (owner-scheduled). After 022: the eval slice
(cost as a first-class axis), then Bedrock, then the workspace
cluster. All other seams remain deferred (`docs/deferred.md`).

