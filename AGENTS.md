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
Implementation — task `021-icf` (design phase: contract being
drafted per task-cycle-design; Tier 3 — schema hard gate +
prompt-bearing extraction surface).

Tasks `001-walking-skeleton` through `020-extract-v2` are complete
(merged) — the EB chain runs end-to-end live behind the thin v1
orchestrator with the prose-first synthesis output shape v2
(ADR 0015), select at standard depth, fail-closed country
filters/groups, IOF schema v2 (`iof_v2`: effect_basis +
study_geography, envelope fencing — ADR 0016), and the pinned
prompt surfaces (`planner_v3`, `extract_iof_v6` + finding vetter,
`synthesise_section_v5`, `synthesise_sections_v2`). 018 trailing
lanes: **C4 demo surface** (codex lane, throwaway `demo-live-run`
branch — never merges) and **D2 rehearsal** (owner-scheduled).

`021-icf` is the promoted pre-eval ICF slice of the owner-adjudicated
sequencing (2026-07-12; criterion: schema/vocabulary/composition
changes land BEFORE evals, prompt/constant tuning after, with eval
cover): `implementation_context_finding` — the second reusable
finding schema (mechanisms, barriers, implementation conditions).
EB synthesis is its first reader; posture pinned at the 020 gate:
separate extraction call/profile, own fingerprint domain, never
invalidates IOF memos; same source-named reference vocabulary so
cross-schema linkage stays reference-mediated via `group`. Then
Slice C (synthesis multi-facet + cost/surface), then the eval slice
with cost as a first-class axis (ICF ground truth authored alongside
IOF's, with/without-ICF composition as an explicit axis). Bedrock
migration, retrieval-boost grammar v2 and all other seams remain
deferred (`docs/deferred.md`).

