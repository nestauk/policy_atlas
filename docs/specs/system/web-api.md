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
  planner turn. `client_turn_id` (UUID, caller-minted) makes double-submit
  idempotent (the same turn is returned, not re-run). A concurrent turn on
  the same project → 409 `planning_turn_in_progress` (per-project lock).
  A turn while the project's walk is running or parked → 409 `run_active`:
  steering is the sanctioned mid-run plan channel, and the fence guarantees
  the latest-approved plan is always the active walk's own lineage
  (review adjudication, 2026-07-21).
  The draft `plan` mirrors `OrchestrationPlan` field-by-field with every
  field optional while drafting + `steps[]` + `ready`; planner session
  state is process-local and bounded — an in-flight draft conversation is
  lost on restart, honestly (the approved plan object is durable).
- `GET /api/v1/projects/{id}/plan` → the current plan (draft or approved,
  with `version`/`status`), whole-object.

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
`findings` (paginated; carries run-scoped B2′ relevance marks
`priority | normal` when the run has them) · `decisions` (paginated
decision log from `steering_history` + allowlisted events) · `artefact`
(sections, span-anchored claims, citations; the chunk-context read model
clamps context to a character window around the cited span — the 008
seam's named consumer) · `coverage` (the composed one-line coverage
sentence: stop condition + adequacy, composed server-side). Read models
render honest absence: missing stages are `null`/absent, never faked.

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
