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
Implementation — task `025-web-app-foundation` (**BUILD COMPLETE through
step 6, 2026-07-21** — phases 0–I built and committed on
`task/025-web-app-foundation`; `make verify` fully green from the hoisted
monorepo layout (backend suite + mypy strict + ruff + build + audit-paths +
prompt-guard + font-guard + drift-check + frontend
typecheck/lint/vitest/build); `verification.md` complete. **The pinned
I.2 live check RAN 2026-07-21** (~52 min, real browser UI, two dev-issuer
users, restart while parked∧executing, confirm-gate steer, boundary
continuation to a succeeded artefact, rename/archive truth) — narrated log
in docs/tasks/025-web-app-foundation/live-check-log.md; it caught and
fixed five integration gaps (stub-defaulting API deps, double /api client
prefix, dict plan-row in confirm-apply, the unwrapped screen directive
validation branch, missing continuation.claimed SSE frame) plus a test
hermeticity hardening (conftest key scrub + side-effect-free alembic env
loading). **Next: the review stack runs in a FRESH conversation
with `task-cycle-review`** (Tier 4: contract-verifier · /code-review
medium per review-economy pins · security-auditor lane · codex
adversarial · live-trace lane · human deep review) — the build
conversation must not adjudicate its own findings. As-built highlights:
monorepo hoist (`backend/` + `frontend/` + `infra/`); two approved
migrations **plus an owner-approved build-time gate expansion
(`event_log.run_id` nullable, 2026-07-21)**; runner parking + boundary
continuation (WalkParked, `continuation_state` reducer with G1–G5,
`run_plan(resume_from)`, answer→claim→drainer protocol, parity harness);
schema-first API (`policy_atlas.api`) with RS256/JWKS auth + dev issuer,
BOLA-opaque 404s, error envelope, SSE replay+tail from `event_log`, read
models incl. the chunk-context clamp; React 19 + pnpm frontend on the
Nesta brand layer with the demo-validated views, replay-idempotent store,
mock mode + Playwright journey. New durable events (run.parked class):
`run.opened` / `run.finished` / `plan.approved` / pause `render`
persisted. Spec: `docs/specs/system/web-api.md` (new). Sequenced after
025: **026 co-pilot Q&A + the per-user transcript store**; then the eval
slice.)

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

