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
**DESIGN COMPLETE — task `033-organisations` is ready to build.** Contract rev 3.0
APPROVED · rubric (42 items) · plan rev 2.0 APPROVED · **ADR 0032 Accepted**
(all 2026-08-24; steps 1–4 done). **Next: open conversation B and run
`task-cycle-build` for steps 5–6.** The review stack (steps 7–10) must then run
in a *third* conversation — the adjudicator of findings must not be the chat
that wrote the code. (branch `task/033-organisations`, cut fresh from `dev`
`b8729a5`): users belong to an organisation and see, by default, their own work
plus their org's org-visible work, read-only, with their own chats on it. A few
ops-assigned administrators read across every organisation for support, writing
nothing, every read traced. Contract: `docs/tasks/033-organisations/contract.md`;
Sixteen phases (0, 0b, 1–12 with 9 and 10 split). The three approval-gated
phases (schema · auth semantics · public API) run **first**, so a refused gate
surfaces before code is built on it; the ops CLI carries three more gates
(`boto3`+stubs, the `Dockerfile` change, Cognito account creation). **Tier 4.** ADR 0032 expected (and must record that it
amends ADR 0031 decision 4).

**Contract-stage adversarial review ran 2026-08-24** across three lanes —
tenancy/authorization, scope/coherence, and Codex as the heterogeneous peer. All
three recommended against approving rev 2.0; the scope lane recommended
splitting into three slices. **Owner ruled: keep one slice, patch every
finding.** Rev 3.0 is that rewrite. The review cost of that decision is recorded
in the contract: **the security lane reads three unrelated threat models and
must be scoped as three passes, not one.**

**What the review found, in four kinds.** (1) *Self-contradictions* — `is_admin`
declared the helper its only reader while two listings must consult it; "write =
owner only, exactly like an org colleague" false in both halves, and taken
literally it would have let an admin post chat turns on any private project in
any organisation, untraced. (2) *Wrong about the world* — `PrivacyView` **§ 3
already claims the email is stored** (it is not, so the live page is inaccurate
today) and **§ 7 already promises permanent Aurora deletion on request**, which
de-enrolment cannot honour; the repo already ships `staging-user`/`prod-user`/
`cognito-user`, which create without enrolling and take a password in argv (this
slice deletes them); the `boto3` non-default group broke `uv sync`, strict mypy
and `pip-audit`; **the downgrade is data-destructive and exposes colleagues'
chats to the Task owner**, because pre-033 code lists every conversation on a
project — so the posture is now **roll forward, not back**. (3) *Design holes* —
no stated NULL-`org_id` rule (and `None == None` is `True` in Python, which would
have exposed every unenrolled user's work to every other one), nothing stamping
`org_id` on new rows, and i.5's stated way out was a no-op loop that silently
re-exposed the row. (4) *Single-owner assumptions baked into existing code* —
seven routes on `conversations.py`'s conversation-id router (including a
transcript by id), SSE that authorises once and streams through revocation, a
stale-turn sweeper keyed to the project owner, and `update_portfolio`'s blind
`.values(**changes)` splat. **Category 4 is why this slice is larger than it
looked: tenancy is not a refactor of ownership checks — it invalidates
assumptions held throughout the request, streaming, sweeping and caching paths.**

**Owner call (j), 2026-08-24 — enrolment carries the person's work, private
(amends (d)):** `user enrol` stamps `org_id` onto every `project` and
`portfolio` the person owns **and sets those rows `visibility='private'`**, in
one transaction with the `app_user` upsert. So **no operator action can ever
expose a row**, and the person sees no change (NULL-`org_id` rows were already
invisible to everyone but them). The invariant survives because a portfolio's
members are always owned by the portfolio's owner, making one person's rows a
closed set. Re-enrolment moves them again and re-privatises anything shared with
the previous org; de-enrolment clears `org_id` on their rows, so an org loses
sight of a departing member's work — **flagged as an owner decision**, since the
alternative (the org retains access) needs ownership transfer, which is Out.
`reassign-rows` is dropped as redundant. **The privacy notice is NOT edited by
this slice** (owner): its three discrepancies ship as a written escalation in
`verification.md` and `docs/deferred.md`, and while they stand the admin leg's
only control is the trace log.

**Owner call (k), 2026-08-24 — structured logging at the API entrypoint.**
Found during the plan review, and it explains a live symptom: **nothing
deployed has ever configured logging.** `configure_logging()` is called only by
`runtime/orchestrate.py`'s `main()`, which runs solely via `__main__` as a local
CLI. The container starts `uvicorn ... api.app:create_app` directly, and runs
execute **in-process** in a `ThreadPoolExecutor` calling `runtime/runner.py` —
there is no separate runner container (infra defines only the backend and the
one-shot migration task). So `LOG_FORMAT=json` has always been inert and
CloudWatch carries no structured output for anything, including the whole
evidence-base pipeline. `orchestrate.py` *is* used by the API, but only as a
library (`deps.py` → `live_planner_and_backends`; `planning.py` → `build_plan`,
`persist_approved_plan`). Fixed in this slice (plan **Phase 0b**) because the
admin trace is the admin leg's only control and an unstructured line is not an
audit trail. **Also to check:** `configure_logging()` sets httpx to WARNING
because httpx logs full URLs at INFO and both search providers carry `api_key`
in the query string — the "inert today" comment assumes the function ran.

**Owner calls carried into rev 3.0:** (a)-(d) from 2026-08-11 (app-owned
ops-assigned membership; read-everything + own chats; per-row `visibility`; no
enrolment backfill) and (e)-(i) from 2026-08-24 — portfolio takes the same
tenancy grades; `is_admin` reads every row in every org including `private`,
read-only; `app_user` stores the Cognito email with an admin `owner_email`
filter; the CLI creates Cognito users but **deleting them is Out**, coupled to
ownership transfer; and the portfolio/project invariant, deterministic with no
prompts. **A standalone rename slice follows 033** (`project` → `task`,
`portfolio` → `project`) and must cover this slice's code.

Task `032-task-lifecycle-ia` is **merged to `dev`** (PR #55, `c6bf772`) — the app
reshaped around one task and one lifecycle, with a named grouping above tasks:
screen word **Task** = the `project` row, screen word **Project** = the new
`portfolio` row. ADR 0031 (Accepted) records the vocabulary split, which stays
open until the workspace-cluster slice. Seams in `docs/deferred.md` § Task
lifecycle IA — note that `src/mock/api.ts` serves no `/api/v1/portfolios`.

Task `031-search-count-honesty` is **merged to `dev`** (PR #51, `23b3dfa`) — one
clear meaning per user-visible source count across the P1 check-in, Where I
looked and the publisher-country charts. Two items were escalated to the owner
in that PR and remain true of it: the **manual browser check was not run**, and
**no non-Claude reviewer read the slice** (the Codex CLI was not installed at
the time, so the family flip did not happen). **Corrected 2026-08-24: `codex`
IS now on PATH**, so the heterogeneous peer lane is available again and later
slices should route review to it — 031's gap stands as history, not as a
standing limitation.

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

Search-volume work is **merged to `dev`** (PR #46, the
`37-hotfix-remove-quota` hotfix) — `029-search-volume-cap` (record caps per
backend per round; standard/deep wall clocks removed) and
`030-multi-round-search` (rapid's clock removed, the runner-orchestrated round
loop wired). It **did not go through the task cycle**: each carries a `plan.md`
and nothing else — no contract, no rubric, no verification, no ADR — so its
`docs/tasks/029-…`/`030-…` directories are leftover plan docs, not the record of
a cycled slice. They collide by name only, with the copilot-chat slice and with
three merged 030 tasks. **Nothing depends on renumbering them**; the live
behaviour is on `dev`. If the record is ever reconstructed it takes the next free
numbers, not `029`/`030`.

Known operational state: staging's OpenAI quota is **healthy** (the
2026-07-28 exhaustion was topped up; corrected here 2026-08-24 — live checks
needing a model route are unblocked). The eval slice (former 027 draft) stays
deferred — contract draft at unpushed `a5c9708`.

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

