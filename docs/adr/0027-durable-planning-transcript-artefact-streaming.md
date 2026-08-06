# ADR 0027 — Durable planning transcript and live artefact streaming

**Status:** Accepted — 2026-07-28 (owner; 027 plan gate, "Approved").
Contract: `docs/tasks/027-frontend-uplift/contract.md`. Annexes:
`docs/tasks/027-frontend-uplift/rehydration-mapping.md` ·
`docs/tasks/027-frontend-uplift/read-model-additions.md`.

## Context

025 shipped the planner conversation as deliberately process-local state
(honest draft loss on restart; "transcripts are 026" deferred seam) and a
pinned 9-frame SSE vocabulary with no artefact progress events. 027's owner
directives: users' planning chats must not disappear (mid-session or across
restarts), and synthesis sections should stream into the artefact page as
each completes. Both features survived a 21-finding contract-stage and an
18-finding plan-stage adversarial review; the load-bearing refutations
(planner idempotency was restart-broken; a naïve streaming emitter deadlocks
against in-transaction lifecycle events) shaped the decisions below.

## Decisions

1. **One `planning_transcript` table — the planning conversation's durable
   record, not a general chat store.** One row per turn: `project_id`,
   `client_turn_id` (unique per project — the API's retry-returns-same-turn
   promise becomes durable), `turn_index` (monotonic per project, the
   ordering coordinate), `user_message`, **both representations** of the
   planner's output — `planner_state` (raw `PlanDraftWire`, what rehydration
   feeds back) and `response` (the exact projected `PlanningTurnOut`,
   returned verbatim on retry) — status `pending|completed|failed`,
   timestamps. Co-pilot Q&A deliberately brings its own thread/context
   model later (guessing its shape here was refuted as speculative
   non-future-proofing).
2. **Two-phase persistence.** The user message inserts on receipt (short
   transaction, post-authz/409); the reply completes the row in the same
   transaction as `persist_approved_plan` when the turn reaches ready — the
   planner LLM call stays outside any transaction (025 review pin). A crash
   between phases leaves an honest incomplete turn; retry rules: latest-row
   only, in place; fresh `pending` blocks new turns; `pending` > 10 min
   fails on read; non-latest retry → 409 `stale_turn`.
3. **Rehydration is an enumerated mapping** (annex): every
   `_PlanningSession` field has a durable source or a deliberate none
   (trace id fresh per process; the 409 lock survives as a process-local
   registry under the one-instance posture). The `_sessions` cache is
   deleted — rows are the one source of truth; `GET /plan` serves drafts
   from the latest completed row. Supersedes 025's honest-draft-loss pin.
4. **Three additive SSE events stream the artefact** — `artefact.skeleton`
   (presentation-ordered sections; its `index` is the display index and the
   single section identity), `artefact.section_started` (emitted before a
   section's generation begins), `artefact.section_completed` (prose
   travels in the event). Whole-section grain; no partial-artefact read
   path; the artefact read model stays the bounded final object. The
   events are **presentation/progress records** — durable in `event_log`
   (replay-safe: reconnect shows exactly the completed sections), but the
   artefact of record lands only at component commit; terminal paths
   (failed/aborted/interrupted) keep streamed sections visible under an
   explicit drafted-not-final banner.
5. **Component-lifecycle events move to short boundary transactions** — the
   one approved runner-behaviour delta. As-built, `component.started`
   commits only with the component's single long transaction, which (a)
   deadlocks any separate-connection emitter contending for the next event
   sequence and (b) means stage-started is never visible while a stage
   runs. Started now commits before the component transaction opens,
   completed after it commits; a rolled-back component leaves a coherent
   started→failed pair. Regression net: the 025 CLI byte-pins and SSE
   replay/pending suites, unmodified. With no uncommitted event rows held
   mid-synthesise, the `ProgressEmitter` (parameter-passed, own short
   `events.append` transactions under the existing savepoint-retry
   allocator, failure never fails the walk) is safe — proven by a
   contention test.

## Consequences

- Planning conversations survive navigation, restarts and deploys; the
  idempotency promise in `web-api.md` becomes true across restarts
  (§ Planning turns rewritten accordingly).
- The SSE narrow set grows 9 → 12; old clients drop unknown types by
  construction (additive).
- Stage-started becomes genuinely live for every component — a user-visible
  timeline improvement beyond the streaming feature itself.
- The live search card cannot be live (acquire's `search.executed` events
  are in-transaction by design): tick notes during the stage, per-backend
  detail at stage completion — the one demo moment durable architecture
  does not reproduce (owner-accepted at the plan gate).
- Rollback: the migration downgrade drops the table; the lifecycle delta is
  its own revertible commit; everything else is additive.
