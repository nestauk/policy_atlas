---
type: System contract
title: Web API
description: The /api/v1 surface — resources, error envelope, pagination, SSE event vocabulary, auth boundary. One schema generates both ends; additive-only evolution.
tags: [system, api, sse, auth, contract]
timestamp: 2026-07-21
---

# System contract — Web API (`/api/v1`)

Successor to `demo/API.md` (point-in-time evidence, branch `demo-live-run`).
Canonical source of truth for shapes is the Pydantic contract package
(`policy_atlas.api.contract`) — OpenAPI is generated from it, the TypeScript
client from the OpenAPI document, and CI fails on drift. This spec records
the *intent*: resource semantics, invariants, and the evolution rule. On
conflict, code wins and this file is updated in the same change.

Binding decisions inherited from the 025 contract § API design pins:
resource-oriented URLs (no verbs) · one error envelope · pagination from day
one with a server page-size cap · PATCH partial updates · snake_case JSON ·
typed discriminated unions for SSE/check-in variants · Hyrum hygiene
(internal names surface only as pinned `stage` keys) · `/api/v1` is a
namespace; evolution is additive-only, removals via documented deprecation
here — never a parallel version.

## Auth boundary

OIDC/JWT bearer verification on every data route (`Authorization: Bearer`);
`user_id` = token `sub`. RS256 against the issuer JWKS (Cognito-shaped;
dev issuer = local keypair, visibly non-production). Unauthenticated:
`/healthz` (liveness, process-only) and `/readyz` only. Ownership is strict
per-owner: another owner's resource — and an unknown or archived one — is
**404** with an indistinguishable body (BOLA rule; 403 is reserved for
future role failures within an owned scope). 401 carries
`WWW-Authenticate: Bearer`. No cookies; no CSRF machinery by construction.
**Tokens never appear in query strings** — SSE clients authenticate via
fetch-stream with the bearer header.

## Error envelope

Every non-2xx: `{"error": {"code": <machine string>, "message": <human>,
"details"?: <structured>}}`. Codes are contract; message text is not.
Mapping: 400 `malformed` · 401 `unauthenticated` · 404 `not_found` ·
409 `run_active` | `already_answered` | `capacity` |
`planning_turn_in_progress` | `chat_turn_in_progress` | `stale_turn` |
`no_completed_run` | `plan_stale` · 422 `validation_error` (Pydantic detail
list under `details`, assert on `loc`/`type` not `msg`) · 429 `chat_capacity`
(a distinct code from the 409 run-capacity bound — too many in-flight chat
turns, never a run-slot conflict) · 500 `internal` (opaque).

## Pagination

Unbounded lists (projects, evidence/sources, findings, decisions) return
`{"data": [...], "pagination": {"page": n, "page_size": n,
"total_items": n}}`; `page_size` default 50, **server cap 200**
(`Query(le=200)`). Offset pagination is deliberate at per-project scale;
the additive migration path is an opaque `cursor` param alongside (never a
breaking reshape). Bounded structural reads (plan, funnel, landscape,
artefact, groups) are whole-object.

## Resources

### Projects

- `GET /api/v1/projects` — paginated, owner-scoped, `status=active` by
  default (`?status=archived|all` to widen). Each item carries the derived
  `latest_run` read model (`capability_run_id`, `status`, `started_at`,
  `ended_at`) — **run state is never cached on the project row**; the
  landing card derives running/paused/complete/interrupted from it.
- `POST /api/v1/projects` `{name, question?}` → 201 project.
- `GET /api/v1/projects/{id}` → project.
- `PATCH /api/v1/projects/{id}` `{name?, question?}` — partial; rename
  emits a transactional `project.renamed` audit event.
- `POST /api/v1/projects/{id}/archive` → idempotent archive (soft-delete:
  hidden from default listings, rows retained; `project.archived` audit
  event on first archive only). 409 `run_active` while a run is executing
  or parked. There is no hard delete.

### Planning turns

- `POST /api/v1/projects/{id}/planning-turns`
  `{message, client_turn_id}` → `{reply, plan, suggestions[]}` — one real
  planner turn. Every turn is durable in the per-project
  `planning_transcript`: its monotonic `turn_index`, assigned when the user
  message is received, is the conversation ordering coordinate;
  `created_at` is display metadata only. `message` caps at 10 000 characters
  (turns are durable and rehydrated into every later planner call). The short
  first transaction follows the owner/run-active gate **under the project row
  lock** and creates a `pending` row; the LLM call runs outside any
  transaction (I2); a second transaction writes its reply, raw planner-state
  snapshot, projected response and suggestions as `completed`. When the turn
  approves a plan, that second transaction re-checks the run fence under the
  project row lock (a run that started during the planner call fails the turn
  with 409 `run_active` — no plan lands under a live walk) and then persists
  the plan, atomically. Planner failure marks the row `failed`; a process
  crash between phases leaves an honest `pending` row.
  `client_turn_id` is caller-minted UUID idempotency durable across API
  restarts: retrying a completed row with the same message returns its stored
  projected response verbatim. Only the latest `turn_index` may be retried;
  it re-runs in place with the same index. A reused id with a different
  message, or a non-latest unfinished retry, → 409 `stale_turn`. A new id
  while a `pending` row is younger than ten minutes → 409
  `planning_turn_in_progress`; reading after ten minutes terminally marks the
  pending row `failed`. The process-local per-project turn lock remains a
  belt-and-braces concurrency guard under the one-instance posture.
  A turn while the project's walk is running or parked → 409 `run_active`:
  steering is the sanctioned mid-run plan channel, and the fence guarantees
  the latest-approved plan is always the active walk's own lineage
  (review adjudication, 2026-07-21).
  The draft `plan` mirrors `OrchestrationPlan` field-by-field with every
  field optional while drafting + `steps[]` + `ready`. Planner context
  rehydrates from completed rows in `turn_index` order (each contributes the
  user message then planner reply); the raw `planner_state` from the latest
  completed row becomes `previous_draft`. Stored HTTP projections are never
  fed back to the planner. A fresh tracing session id per request is correct:
  conversation quality depends solely on that durable composition.
- `GET /api/v1/projects/{id}/plan` → the current plan (draft or approved,
  with `version`/`status`), whole-object. It returns the approved plan when
  one exists; otherwise the latest completed transcript row's stored
  `response.plan` without recomputation. It is 404 only when neither exists,
  so drafts survive API restarts.
- `GET /api/v1/projects/{id}/planning-turns` → the owner-scoped durable
  transcript in ascending `turn_index`, paginated in the standard
  `{data, pagination}` envelope. Each row exposes `turn_index`,
  `client_turn_id` (the caller's own idempotency key, returned so a
  reloaded client can retry its incomplete latest turn), `user_message`,
  `reply`, `suggestions`, `status`, `created_at` and
  `completed_at`; pending and failed rows remain visibly incomplete. There
  is no backfill: projects predating the table simply have zero turns.

### Conversations

A **conversation** is `kind ∈ planning | chat`. A project holds **one active
planning conversation** at a time (created with the project or on its first
planning turn; the existing `/planning-turns` and `/plan` endpoints below
operate on it and additively expose `conversation_id` — paths and semantics
are unchanged) plus **many chats** (Claude-Projects-style follow-up threads,
user-created, project-scoped, answering across every artefact in the
project — an entry artefact is context, never a scope fence). Chats are
**read-only**: they never mutate a plan, never start a run, never write an
artefact — a question needing new evidence hands off to the planning
conversation as a typed affordance, never a plan mutation from chat. All
routes below are owner-scoped under the standard BOLA rule (unknown,
cross-owner, and — except where noted — archived conversations are 404).

- `GET /projects/{id}/conversations?kind=&status=` — the library read model,
  both kinds, newest first, standard `{data, pagination}` envelope; each row
  carries a `latest_turn_preview` (bounded snippet of its most recent chat or
  planning turn, from whichever turn table its `kind` reads). Default
  listing excludes archived rows; `status=archived` is the one filter that
  lists an owner's own archived chats (planning conversations are never
  archived).
- `GET /conversations/{cid}` → `ConversationOut` (`id`, `project_id`, `kind`,
  `title`, `status`, `entry_artefact_id`, `created_at`, `closed_at`,
  `archived_at`) — the deep-link resolver. An archived conversation is 404
  here (as on every route below except the list above and unarchive);
  unarchiving is the one call that resolves it back into reach.
- `POST /projects/{id}/conversations` `{entry_artefact_id?}` → 201 chat
  conversation, titled `"New chat"` until its first turn (kind is always
  `chat` — planning conversations are lifecycle-created, never minted by
  hand). `entry_artefact_id` must name an artefact belonging to the same
  project, else 404.
- `PATCH /conversations/{cid}` `{title?, entry_artefact_id?}` — chats only
  (422 on a planning conversation); partial, an explicit `null`
  `entry_artefact_id` clears the entry-context chip; a replacement artefact
  is project-guarded the same as at creation.
- `POST /conversations/{cid}/archive` / `.../unarchive` — chats only (422 on
  planning), idempotent either direction.
- `GET /conversations/{cid}/turns` — an active owned chat's durable turns,
  ascending `turn_index`, standard paginated envelope; each row carries
  `claims[]` (claim spans over the answer prose, each mapping to
  `citations[]` as durable ids), the per-claim `enrichment` state, the
  zero-citation `warning_not_evidence_checked` marker, a typed `handoff`, and
  `stopped_before_evidence_check` for a cancelled row.
- `POST /conversations/{cid}/turns` `{message, client_turn_id}` — **the turn
  stream**. Reservation (ownership, eligibility, idempotency, capacity,
  validation) happens in one transaction before any response bytes; every
  error from reservation is the standard `ErrorEnvelope`, never a stream
  event. `message` caps at 10 000 characters. Response is `application/
  x-ndjson`, one JSON object per line, a discriminated union on `type`:
  - `progress {label}` — a user-facing read-tool activity label before that
    tool runs (e.g. "Searching the evidence…"), never a fake token.
  - `delta {text}` — a provider-neutral prose fragment.
  - `completed {turn}` — the one successful terminal event: the durable
    `ChatTurnOut` row, citation floor already applied.
  - `failed {error, turn_id}` — the one failure terminal event. A failure
    after headers have committed is always a stream event, never an
    `ErrorEnvelope` — the envelope only covers pre-header rejections above.
  - `cancelled {turn}` — the one explicit-stop terminal event; the row's
    `stopped_before_evidence_check` is set, its citation markers are inert
    (the terminal citation floor never ran on a stopped generation).

  Exactly one terminal event (`completed | failed | cancelled`) arrives per
  still-connected accepted request. A client that disconnects without
  calling cancel is **not** a stop signal: the server finishes generation
  and commits `completed` server-side regardless: the answer is waiting on
  the next `GET .../turns` read, never lost. Async grounding-judge
  enrichment (per-claim `{verdict, weakly_grounded, rationale}`) runs after
  the stream closes and compare-and-sets onto the already-completed row —
  never a second stream, picked up by re-reading the turn.
  **Idempotency and retry** key on `client_turn_id`: a completed row replays
  its stored terminal payload verbatim (a fresh one-line `completed` stream,
  no re-generation); a `failed` or `cancelled` row re-runs in place, and only
  for the conversation's latest turn. Error vocabulary: 409 `stale_turn`
  (same id bound to a different message, or a retry attempted on a
  non-latest turn) · 409 `chat_turn_in_progress` (a new `client_turn_id`
  while this conversation already has a `pending` row; a `pending` row older
  than ten minutes is first terminally expired to `failed`) · 409
  `no_completed_run` (the project has never finished a run) · 409
  `run_active` (the project's walk is currently `running` or `paused` —
  finish or park it first) · 429 `chat_capacity` (an owner-wide in-flight
  chat-turn cap, distinct from the run-slot `capacity` code). A generated
  answer is also capped by a fixed output-token ceiling.
- `POST /conversations/{cid}/turns/{turn_id}/cancel` → `CancelTurnOut
  {status}` — the explicit stop signal (bare disconnect does not cancel; see
  above). Owner-scoped, idempotent, keyed to the named pending turn: it stops
  generation, persists whatever prose has streamed so far as `cancelled`,
  and returns the turn's honest current status (already-terminal is a
  no-op read, not an error).
- `GET /projects/{id}/chunks/{chunk_id}/context?quote=` — the chat-citation
  hover/click read: the same clamped context-window shape as the artefact
  citation-context read above, resolved from a chat citation's durable chunk
  id plus its quote (chat citations carry chunk ids, not artefact
  citation-table ids). An ambiguous or unmatched quote is 404, same rule as
  the artefact seam.

### Runs

- `POST /api/v1/projects/{id}/runs` `{}` → 201 run — creates the
  `capability_run` and dispatches the walk off the event loop. Guarded by
  the per-project Postgres row lock: a second active run → 409
  `run_active`; at the executing-walk bound → 409 `capacity` (parked runs
  hold no slot). 400 if no approved-ready plan.
- `GET /api/v1/projects/{id}/runs` → paginated list (newest first;
  standard `{data, pagination}` envelope — runs accumulate);
  `GET .../runs/{run_id}` → one. Status ∈ `running | paused | succeeded |
  degraded | failed | aborted | interrupted`.

### Check-ins (steering)

- `GET /api/v1/projects/{id}/check-ins?status=pending` — **pending is
  derived AND answerable**: the `steering.pause` of the latest run without
  its decision, and only while that walk's status is `paused` (a walk the
  orphan sweep interrupted never presents an unanswerable card); at most
  one by construction. Decided pauses are history (`?status=all`, paginated
  in the standard envelope, served from the `steering_history` projection,
  never transport memory). A check-in carries: `check_in_id` (the pause event
  id), `kind`, `boundary`, `component`, `stage`, the deterministic
  `render` (content of record — there is no LLM prose wrap), server-
  supplied `options[]` (`{id, label, description, requires_user_input,
  suggested}`), `triggers[]`, and the affordance flags
  (`segment_reentry_allowed`, `rerun_component`).
- `POST /api/v1/projects/{id}/check-ins/{check_in_id}/response` — one per
  check-in; a second → 409 `already_answered` (per-project lock; barrier-
  tested). Body is a tagged union on `kind`:
  - `{"kind": "option", "option_id": ..., "params"?: {...}}` — canonical
    or authored option (authored picks apply orchestrator attribution).
  - `{"kind": "free_text", "text": ...}` → **202 with the compiled
    fan-out render + `confirm_token`** (router confirm gate — nothing
    applies unconfirmed; ~half of live free-text steers mis-compiled
    before this gate).
  - `{"kind": "free_text_confirm", "confirm_token": ..., "apply": bool}`
    → applies (or discards) the compiled deltas as the decision.
  - `{"kind": "abort"}` — mirrors the runner's in-process abort: the plan
    flips to `abandoned` and a `run.finished{status: aborted}` event commits
    in the same transaction, so SSE/replay see the terminal transition.
  A confirm token lost to restart/eviction → 409 `confirm_expired`
  (recompile to proceed).
  The answer and its `continuation.requested` event commit in one
  transaction; the parked run's **boundary continuation walk** dispatches
  after commit (answers are always accepted; execution may queue at the
  bound). UI renders only server-supplied options; vetting/judge steering
  never surfaces (B2′ relevance-emphasis is in-scope steering and arrives
  as ordinary options).

### Read models (owner-scoped GETs under `/api/v1/projects/{id}/…`)

`funnel` · `landscape` (distributions over the screened-in set only) ·
`groups` · `evidence` (paginated source list with status ladder) ·
`findings` (paginated discriminated `profile: iof | icf` records; carries
run-scoped B2′ relevance marks `priority | normal` when the run has them) ·
`sources/{source_id}` (optional dossier: source metadata, tags, and claims
cited by the latest artefact only) · `decisions` (paginated
decision log from `steering_history` + allowlisted events) · `artefact`
(sections, span-anchored claims, citations; the chunk-context read model
clamps context to a character window around the cited span — the 008
seam's named consumer) · `coverage` (the composed one-line coverage
sentence: stop condition + adequacy, composed server-side). Read models
render honest absence: missing stages are `null`/absent, never faked.

- Artefact `ClaimOut.theme` resolves a theme claim's durable characterisation
  or grouping references to named items (`name`, optional `description` and
  `size`; grouping items also carry their `facet` for deep-linking), including
  their resolved member `sources` (`source_id`, `title`) when member identities
  are available. Stale or unresolvable references and member sources are
  omitted, and an empty theme resolution is `null`.

The C.1 additions enrich these records additively: coverage exposes public
backend names and post-run query detail; evidence exposes effective-screen
detail; finding profiles carry their stored typed fields and grounding; and
artefact claims/sections/chunk context expose their durable presentation
detail. Collection filter query parameters land separately in C.2, so C.1
keeps existing paginated-list parameters unchanged.

The C.2 additions add collection filters to `evidence` and `findings`, on
top of the existing `page`/`page_size`. All filter params are optional,
repeatable where noted, and combinable; every filtered response's
`total_items` is collection-true — it reflects the filtered collection,
never the unfiltered project total or the returned page's length.
Evidence status is still derived server-side in Python project-wide before
filtering and paging (the `funnel_out` precedent — bounded to one
project's rows).

- `GET .../evidence`: `status` (repeatable; any evidence status ladder
  value, plus the aggregate shortcut `Included` = the 7 ladder positions
  reached once a source is screened in — i.e. every status except `found`
  and `screened_out`) · `cited` (bool). An unrecognised `status` value is
  422.
- `GET .../findings`: `profile` (`iof | icf`; 422 if unrecognised) ·
  `facet`+`group` (both required together — a facet name and an exact
  group label within it; an unknown facet/group pair returns an empty
  page, not an error) · `group_id` (the group's qualified id,
  `<facet>:gNN`, as an alternative to `facet`+`group` — combining it with
  either is 422; an unknown `group_id` returns an empty page) ·
  `source_id` (the evidence row's source id; no match returns an empty
  page).

### User feedback

Two human-authored, LLM-free write paths. Both are owner-scoped and stored in
`user_feedback`; nothing in the pipeline reads either back.

- `PATCH .../sources/{source_id}` — body `{not_relevant: bool}`, returns
  `{source_id, not_relevant}`. Sets or clears the caller's "not relevant"
  flag on one source, idempotent in both directions. A `source_id` outside
  the project is the usual indistinguishable 404. **Feedback only**: the flag
  surfaces as the additive `not_relevant` field on `evidence` rows and the
  source dossier, and never moves a source on the evidence status ladder,
  out of selection, or out of the artefact's citations.
- `POST .../issue-reports` — body `{body, page_path?}`, returns
  `{feedback_id, created_at}` (201). Free text, 1–4000 characters after
  whitespace stripping (a blank report is 422). No model is invoked and there
  is no reply surface: the report is recorded, not answered.

### SSE

`GET /api/v1/projects/{id}/events?cursor=<sequence>` — fetch-stream with
bearer auth (native `EventSource` cannot send headers). Replay-then-tail
with an atomic cutoff: backlog is read to a snapshotted max `event_log`
sequence, the live tail subscribes from `sequence+1` in the same
consistent view (race-tested: no loss, no duplication). Each frame:
`id:` = the `event_log` sequence (the client's reconnect cursor — the
client passes its own `cursor`; `Last-Event-ID` is not relied on),
`event:` = frame type, `data:` = the typed payload. 15 s heartbeat
comments; `X-Accel-Buffering: no`; generator cleanup on disconnect.

Frame vocabulary (discriminated union, `type` names are contract):

| type | payload (summary) | source |
|---|---|---|
| `run.status` | `{capability_run_id, status}` | walk open/park/finish/interrupt |
| `stage.started` | `{stage, label, blurb}` | component run start |
| `stage.completed` | `{stage, label, summary, seconds}` | component terminal |
| `stage.failed` | `{stage, label, reason, skipped}` | component failure/skip |
| `artefact.skeleton` | `{sections: [{index, title, focus}]}` in presentation order | synthesise presentation progress |
| `artefact.section_started` | `{index}` | synthesise presentation progress |
| `artefact.section_completed` | `{index, title, prose}` | synthesise presentation progress |
| `checkin.pending` | the full check-in resource | `steering.pause` |
| `checkin.resolved` | `{check_in_id, response, decided_by}` | `steering.decision` |
| `plan.updated` | `{plan, version}` | plan row supersession |
| `project.updated` | `{name?, question?, status?}` | lifecycle audit events |
| `tick` | `{stage?, note, ephemeral: true}` | **ephemeral channel** — never persisted, never state-bearing, no `id:` |

`stage` keys are the pinned stable component vocabulary (`acquire`,
`screen`, `classify`, `appraise`, `characterise`, `select`, `extract`,
`group`, `synthesise`); labels/blurbs are server-supplied presentation and
may change. Nothing else internal (module names, model ids, raw payload
keys) is observable. The frontend store must rebuild idempotently from
replay alone — mid-run refresh, server restart with a parked pending
check-in, and reconnect-mid-stream are the tested cases.

`artefact.*` frames are durable presentation/progress records, not partial
artefact reads or authoritative artefact content: whole-section prose is sent
for live rendering, while the evidence-base artefact of record is committed
only when synthesis completes. The skeleton's display `index` is the identity
used by every artefact frame; it includes key findings first (although that
section is generated last) and conclusions last. An empty key-findings pass
still closes its slot with `artefact.section_completed` and empty prose.
Stage lifecycle events commit at phase boundaries: `stage.started` commits
before its component transaction opens and `stage.completed` commits after it,
so a tail sees real in-flight work and a rolled-back component retains its
started→failed trail.

## Deployment posture (v1)

One API instance, one worker process: pause-unblocking and the live tail
are process-local; durable replay covers reconstruction, not cross-instance
live delivery. Cross-instance steering/live-tail (LISTEN/NOTIFY or pub-sub)
is a recorded deferred seam for the infra slice. Startup: orphan sweep
(executing walks that died → `interrupted`; claimed-but-unexecuted
continuations re-execute — the claim window is recoverable; parked runs
untouched; a running walk with no event attachment is interrupted, never a
boot failure), then the continuation drainer (requested-but-unclaimed
continuations redispatch with the same key-driven backends as the request
path).

**Hard deploy invariant (review adjudication, 2026-07-21):** the sweep has
no instance-ownership lease, so deploys must fully stop the old process
(hard-kill — default SIGTERM lets the walk executor drain-run) **before**
booting the new one; overlapping instances would interrupt each other's
live walks. The lease belongs to the cross-instance seam (infra slice).

**Backend mode:** `PA_BACKEND_MODE=live|stub|auto` (default `auto` =
`OPENAI_API_KEY` presence). `live` without the core key fails boot loudly;
missing search keys in live mode are warned at startup (coverage degrades
honestly, never silently).

## Deprecations

None. (Additive changes append here with dates; removals require a
documented deprecation window and never break the generated client within
`/api/v1`.)
