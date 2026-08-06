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
`planning_turn_in_progress` · 422 `validation_error` (Pydantic detail list
under `details`, assert on `loc`/`type` not `msg`) · 500 `internal` (opaque).

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
