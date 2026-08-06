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
Implementation — task `028-ux-refinement` **design step 1** (2026-08-03,
branch `task/028-ux-refinement`, stacked on `task/027-frontend-uplift`):
interview-driven UX refinement — four internal policy-team interviews on
the 027 build (type scale + copy diet, expandable composer, sequential
plan-building fork, artefact contents-sidebar + progressive disclosure,
key-findings bullets fork, sortable/theme-filterable sources, naming
pass, tab-IA fork). Contract:
`docs/tasks/028-ux-refinement/contract.md`; requirements + owner mock-up:
`docs/tasks/028-ux-refinement/design-inputs.md`.

Tasks `026-infra-deployment` (PR #33, Tier 4 — system **live** at
`v3.policyatlas.uk`), `027-frontend-uplift` (PR #44, Tier 3 — review
stack adjudicated 2026-07-30, 32 fixes re-verified) and
`028-ux-refinement` (PR #45) are **merged to `dev`**.

Search-volume work carries the next two numbers, renumbered 2026-08-06
when `028` was taken by the UX slice on `dev`: `029-search-volume-cap`
(record caps per backend per round; standard/deep wall clocks removed —
was `028-…`) and `030-multi-round-search` (rapid's clock removed, the
runner-orchestrated round loop wired — was `029-…`). Both are plan-only
docs; the code landed on branch `37-hotfix-remove-quota`. ADR numbers
follow: `0028` is the UX slice's, so search-volume work starts at `0029`.

Known operational state: staging's OpenAI quota exhausted
2026-07-28 (runs fail honest-429 until billing tops up). The eval slice
(former 027 draft) stays deferred — contract draft at unpushed
`a5c9708`.

Tasks `001-walking-skeleton` through `025-web-app-foundation` are
complete (merged — 025 is PR #32, 2026-07-21: monorepo hoist
(`backend/` + `frontend/` + `infra/`), schema-first API
(`policy_atlas.api`, RS256/JWKS auth + dev issuer, SSE replay+tail),
runner parking + boundary continuation, React 19 + pnpm frontend on
the Nesta brand layer; spec `docs/specs/system/web-api.md`) — the EB
chain runs end-to-end live behind the
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
surface) stays throwaway — never merges — and is superseded by 025
as evidence. After 026 (infra): co-pilot Q&A + transcript store, then
the eval slice (cost as a first-class axis), then Bedrock, then the
workspace cluster. All other seams remain deferred
(`docs/deferred.md`).

