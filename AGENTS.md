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
Implementation — task `025-web-app-foundation` (**design step 1 in
progress, 2026-07-20**: contract drafted, awaiting owner approval).
**The web-app foundation slice — production API + frontend in one
consolidated slice (owner direction, 2026-07-20), replacing the
throwaway `demo-live-run` stack.** Strands: (1) monorepo hoist —
Python project → `backend/`, new `frontend/`, `infra/` reserved
(pinned deferred.md decision; import-neutral, tooling paths only);
(2) production API in `policy_atlas/api/` — schema-first (Pydantic →
OpenAPI → generated TS client, drift-checked in CI), REST + SSE with
durable backlog replay from `event_log` (the demo's in-memory bus
dies); (3) project lifecycle done properly — schema migration (name,
question, lifecycle status, soft-delete, nullable owner) so
rename/delete are real backend semantics, `projects.json` sidecar
dies; (4) steering/check-ins on the durable substrate — pending
check-ins + decision history served from Postgres (`steering_history`,
024), answers through the real steering seam; (5) auth seam shaped
for **AWS Cognito** (owner pin, 2026-07-20) — OIDC/JWT verification
at the API boundary + user-identity threading, dev issuer locally;
Cognito itself lands with the CDK `infra/` slice, not here; (6)
frontend on the demo-validated stack (React 18 + TS strict + Vite +
Tailwind) and views, locked user-facing vocabulary, idempotent
SSE-replay store. Required design inputs: `demo/API.md` +
`demo/RETRO.md` §§2–3 (on `demo-live-run`). Tier 4 (scaffold +
public API + schema + auth + deps + CI). Sequenced after 025:
**026 co-pilot Q&A + the per-user transcript store**; then the eval
slice.

Tasks `001-walking-skeleton` through `024-steering-surface` are
complete (merged) — the EB chain runs end-to-end live behind the
024 steering surface (one orchestrator, three moments: planning turn ·
free-text router · boundary watch; steer-point lattice P1–P4; durable
steering record on `event_log` + `capability_run` + the
`steering_history` projection; ADRs 0020–0023), with prose-first
synthesis output shape v2 (ADR 0015), select at standard depth,
fail-closed country filters/groups, IOF schema v2 (ADR 0016), the ICF
second finding schema + kind-typed `query_findings` + kind-spanning
membership bridge (ADR 0017), multi-facet grouping on the shared
two-stage clustering engine + the 022 cost/surface work (ADR 0018,
−49% synthesis cost), and the pinned prompt surfaces
(`orchestrator_v1` family, `extract_iof_v7` + vetter, `extract_icf_v2`
+ vetter, `synthesise_section_v7` (v6 frozen as the cost-harness
baseline), `synthesise_sections_v2`). 018 trailing lane: **D2
rehearsal** (owner-scheduled); the `demo-live-run` branch (C4 demo
surface) stays throwaway — never merges — and is superseded by this
slice as evidence. After 025: 026 co-pilot Q&A, then the eval slice
(cost as a first-class axis), then Bedrock, then the workspace
cluster. All other seams remain deferred (`docs/deferred.md`).

