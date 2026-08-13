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
Build — task `031-search-count-honesty` **step 5** (contract + plan approved
2026-08-13, branch `task/031-search-count-honesty`, based on `dev`): fix
mixed-grain source counts across the P1 check-in, Where I looked, and the
publisher-country charts (deep search makes the defects obvious). Contract:
`docs/tasks/031-search-count-honesty/contract.md`; plan:
`docs/tasks/031-search-count-honesty/plan.md`; rubric alongside. Tier 2.

Task `029-copilot-chat` is **merged to `dev`** (PR #47, `5f2e9b1`) — the unified
conversation model: a project holds many conversations, Claude-Projects-style.
Follow-up **chats** (read-only, project-scoped, answering across artefacts;
streamed NDJSON turns with claim-grained citations, deterministic floors + async
judge enrichment; tool scope `search_chunks` · `lookup` · `query_findings`, no
`search`) and **planning conversations** (one per plan lineage, closing with its
run's terminal transaction — supersedes 027's rolling thread; row-grain audit
chain conversation → plan → run → artefact). ADR 0029 (Accepted); API surface:
`docs/specs/system/web-api.md` § Conversations.

Tasks 001–028 are merged (2026-08-06 merge day: dev = #33 → #44 → #45 =
`c501022`); system **live** at `v3.policyatlas.uk`.

Search-volume work carries two plan-only docs, renumbered 2026-08-06 when
`028` was taken by the UX slice on `dev`: `029-search-volume-cap` (record
caps per backend per round; standard/deep wall clocks removed — was
`028-…`) and `030-multi-round-search` (rapid's clock removed, the
runner-orchestrated round loop wired — was `029-…`). Their code is **merged to
`dev`** (PR #46, the `37-hotfix-remove-quota` hotfix). **Numbering collision
still to settle:** `029` and ADR `0029` belong to the copilot-chat slice, and
`031` is now this count-honesty slice — so if the search-volume docs are
renumbered they need `032`/`033`, not `031`/`032`. No ADRs written for them yet.

Known operational state: staging's OpenAI quota exhausted 2026-07-28 (runs
fail honest-429 until billing tops up). The eval slice (former 027 draft)
stays deferred — contract draft at unpushed `a5c9708`.

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

