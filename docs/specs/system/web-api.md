---
type: System contract
title: Web API
description: The /api/v1 surface — resources, error envelope, pagination, SSE event vocabulary, auth boundary. One schema generates both ends; additive-only evolution.
tags: [system, api, sse, auth, contract]
timestamp: 2026-09-04
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
here — never a parallel version. One recorded break: the task 038 rename
(§ Deprecations, ADR 0036).

## Auth boundary

OIDC/JWT bearer verification on every data route (`Authorization: Bearer`);
`user_id` = token `sub`, the **only** claim any request path reads.
RS256 against the issuer JWKS (Cognito-shaped; dev issuer = local keypair,
prod = Cognito, visibly non-production). Unauthenticated requests get a
uniform `401 unauthenticated` envelope with `WWW-Authenticate: Bearer`.
No cookies; no CSRF machinery by construction. **Tokens never appear in
query strings** — SSE clients authenticate via fetch-stream with the bearer
header.

**Public write exception:** `POST /api/v1/waitlist` is intentionally
unauthenticated (splash-page Request access). Health probes
(`GET /healthz`, `GET /readyz`) also sit outside the bearer boundary.

**Conditionally-public reads (task 037, ADR 0035).** Exactly eleven GET
routes accept a request with **no `Authorization` header**:
`GET /tasks/{id}` plus the read-model routes `funnel` · `landscape` ·
`groups` · `evidence` · `findings` · `sources/{source_id}` · `artefact` ·
`coverage` · `citations/{citation_key}/context` ·
`chunks/{chunk_id}/context`. Anonymous means the raw header is absent —
a present header that does not authenticate (bad token, wrong scheme,
malformed value) is still 401. The anonymous read succeeds only when the
task has `is_public = true` and `status = 'active'`; anything else is
the standard indistinguishable 404. Signed-in callers keep the graded
read first and fall back to the same public check, so a public row is
readable by any authenticated user too — in the **redacted shape**
(`access = "public"`, see § Projects). `is_public` plays no part in
listings, project reads, or the colleague and admin legs; a read
served by the public check is not an admin read and is never traced as
one. `decisions` (History) stays behind the bearer token. The
conformance suite pins this three-class boundary (always-401 ·
conditionally-public · public write).

**Tenancy (task 033, ADR 0033).** Users belong to at most one organisation
(`app_user.org_id`, ops-assigned). Access resolves through one graded
helper with **three read legs and one write grade**:

- **read** = owner ∪ **same-org** (the row's `org_id` is non-NULL and equals
  the caller's, and the row's `visibility` is `org`; archived/status rules
  unchanged) ∪ **admin** (`app_user.is_admin`: any row, any org, any
  visibility, read-only, traced — see below).
- **write** = **owner only**, with exactly one exception: the three chat
  mutations a same-org colleague holds (create a chat on a readable
  task, post a turn to their own conversation, cancel their own turn).
  An admin is not a colleague and holds none of them.
- **The NULL rule:** a row with `org_id IS NULL` is reachable by its owner
  and an admin only; a caller with NULL `org_id` matches no org leg. The
  org leg is a SQL predicate (a correlated `EXISTS` equating the caller's
  `app_user.org_id` to the row's non-NULL `org_id`) — never a Python
  comparison of two loaded values, because `None == None` is `True`.

Not-visible → **404** with an indistinguishable body (BOLA rule: unknown,
cross-org and — where the route excludes them — archived rows are the same
404). Visible-but-not-writable → **403 `forbidden`**.

`GET /api/v1/me` → `{user_id, display_name, email, organisation:
{org_id, name} | null, is_admin}` — provisions the caller's `app_user` row
just-in-time with `ON CONFLICT DO NOTHING` (a once-per-user insert that
never clobbers ops-set fields; ops enrolment is the deliberate
`DO UPDATE`). `get_current_user` stays DB-free and Cognito-free.

Listing filters: `scope=all|mine` (default `all` = owner ∪ org-visible;
for an admin, `all` spans every organisation) on both listings ·
`project_id` on `GET /tasks` · `owner_email` on both listings,
admin-only — a non-admin passing it gets 422 `validation_error`, as does
any value over 254 characters or without an `@` (the value is logged
verbatim into the audit line, so it is bounded and shape-checked first).

**The admin trace.** Reads served by the admin leg — and only those — are
logged: one line per direct row read (`admin_read`), one per cross-org
listing or search request including zero-result searches
(`admin_listing`), one per SSE subscribe and per re-authorisation batch
(`admin_stream_read`). Nothing is emitted for a read the caller was
entitled to anyway. The flag has exactly four readers, asserted
structurally as a closed code-site list (`_access.admin_read_leg` and
`_access._is_admin` — which between them serve the row/listing legs, the
`owner_email` gate and the trace decision — plus `me.get_me` and the
`MeOut` field declaration); no write path reads it, and no HTTP surface
can set it.

## Error envelope

Every non-2xx: `{"error": {"code": <machine string>, "message": <human>,
"details"?: <structured>}}`. Codes are contract; message text is not.
Mapping: 400 `malformed` · 401 `unauthenticated` · **403 `forbidden`**
(visible but not writable — task 033) · 404 `not_found` ·
409 `run_active` | `already_answered` | `capacity` |
`task_agent_turn_in_progress` | `chat_turn_in_progress` | `stale_turn` |
`no_completed_run` | `plan_stale` | **`visibility_conflict`** (setting a
task's visibility while it is in a project — change the project's
visibility, or leave the task out of it) | **`already_registered`**
(waitlist email already present) · 422 `validation_error`
(Pydantic detail list under `details`, assert on `loc`/`type` not `msg`;
also the code for a non-admin passing `owner_email` and for a PATCH body
carrying both `visibility` and `project_ids` — not a third semantic) ·
429 `chat_capacity`
(a distinct code from the 409 run-capacity bound — too many in-flight chat
turns, never a run-slot conflict) · 500 `internal` (opaque).

## Pagination

Unbounded lists (tasks, evidence/sources, findings, decisions) return
`{"data": [...], "pagination": {"page": n, "page_size": n,
"total_items": n, "has_more": bool}}`; `page_size` default 50 (20 for tasks
and projects, the list pages; task 058), **server cap 200**
(`Query(le=200)`). Offset pagination is deliberate at per-task scale;
the additive migration path is an opaque `cursor` param alongside (never a
breaking reshape). Bounded structural reads (plan, funnel, landscape,
artefact, groups) are whole-object.

## Resources

### Waitlist

Splash-page **Request access** intake. Public — no bearer token.

- `POST /api/v1/waitlist` `{email, name, organisation?, role_or_reason,
  website?}` → 201 `{entry_id, email, created_at}`. Email is lower-cased and
  unique (`409 already_registered` on conflict). Organisation is optional;
  blank becomes null. Response omits organisation and role/reason. `website`
  is a honeypot (hidden on the form): any non-empty value gets a fake 201
  and stores nothing. No admin list/export in v1 — ops query the
  `waitlist_entry` table directly. Enrolment into Cognito remains the ops
  CLI path (task 033), not an auto-promote from this table.

### Tasks

- `GET /api/v1/tasks` — paginated, tenancy-scoped (`scope=all|mine`,
  default `all` = own ∪ same-org org-visible; admin `all` spans every
  organisation), `status=active` by default (`?status=archived|all` to
  widen); `project_id` filters to one project's members; `owner_email`
  is admin-only. Each item carries the derived `latest_run` read model
  (`capability_run_id`, `status`, `started_at`, `ended_at`) — **run state
  is never cached on the task row**; the landing card derives
  running/paused/complete/interrupted from it.
- `POST /api/v1/tasks` `{name, question?}` → 201 task, stamped with
  the creator's `org_id` (NULL for an unenrolled creator) and
  `visibility='private'` (the column default — new work is unshared until
  its owner shares it; owner amendment 2026-08-26).
  Task 044: the body also takes `capability` (`evidence_search` default |
  `options_scoping`, written once and never changed), `project_ids[]` and
  `from_task_ids[]`, applied in **one transaction** (C10): the same-project
  rule is checked when a link is written (409 `link_project_mismatch`), the
  pinned source walk must be `succeeded | degraded` (409
  `link_source_unfinished`), the source must be an Evidence search task (409
  `link_source_capability`; review stack 2026-09-17), at most ten
  `from_task_ids` per create (422; an accident guard, owner 2026-09-18), and a failed request leaves no task row.
  A link never widens what the reader can see: `source_task_name` is `null`
  for a source the reader cannot open (ADR 0037 decision 2).
  `TaskOut` carries `capability` and `links[]` (`source_task_id`,
  `source_task_name`, `source_capability_run_id`, `flagged` — true when the
  two tasks no longer share a project; a link is never deleted).
- `POST /api/v1/tasks/{id}/plan/confirm-baseline` `{artefact_id,
  plan_version}` → `PlanOut` (task 044; Options scoping only, 422 on an
  Evidence search task). Writes `baseline_confirmed {artefact_id,
  plan_version}` into the scoping plan as a new approved version through
  the ordinary plan-edit path; idempotent on the same pair (200, no new
  version); 409 `run_active` while any walk is running or paused; 404 if the
  artefact is not a baseline of this task. The plan-scoped record "Confirm
  plan and build longlist" writes after a plan change without a rebuild (a
  steering event needs a walk); task 2 replaces it with the longlist walk's
  opening decision. *([task 045 contract](../tasks/045-scoping-longlist/contract.md), D1, D14, A23.)* The route now also **opens
  the longlist walk** on the confirmed version — a new `capability_run`
  under its own `purpose = longlist` intent record — taking the run
  dispatch lock and pre-insert reservation `POST /runs` holds, and returns
  the opened walk in an **optional** field of `PlanOut`. After a plan
  change the plan document's **Rebuild longlist** posts here on the new
  version; the rebuild is seeded with the existing options, so option ids,
  exclusions and additions survive (owner: "build it now, ids kept").
  `TaskOut` gains `active_run` (any running or paused walk, children
  included) and `has_longlist` (a `longlist_result` row exists): a scoping
  task's readers key on what exists and what is active, never on a single
  latest run; `latest_run` stays as it is for the Evidence search (owner,
  plan review P4: "scoping readers see what exists and what is active").
  `active_run` also carries `stage` (the current public stage key) and
  `stage_label` (the server's copy), taken from the parentless walk so a
  scoping task shows its own stage, not a child search's (task 058, S4).
- `GET /api/v1/tasks/{id}` → task (read grade, or the public leg —
  § Auth boundary). A public-leg read returns the **redacted shape**:
  `access = "public"`, `is_owner = false`, `owner_display = null`,
  `project_ids = []`; graded reads carry `access = "full"`.
- `PATCH /api/v1/tasks/{id}` `{name?, question?, visibility?,
  is_public?}` — partial, owner-only; rename emits a transactional
  `task.renamed` audit event. `visibility` on a task in a project
  is 409 `visibility_conflict`; a body carrying both `visibility` and
  `project_ids` is 422 (the two orderings differ). An explicit
  `null` on a NOT NULL column (`name`, `visibility`, `is_public` — here
  and on `PATCH /projects/{id}`) is 422 rather than a 500; nulls that
  mean something (`question`, `description`, `project_ids`) still work.
  `is_public` (task 037) is orthogonal to `visibility` and to project
  membership — no cascade, no conflict rule; a real flip emits
  `task.shared_publicly` / `task.unshared` in the same
  transaction, and a same-value PATCH emits nothing. Turning it off (or
  archiving) revokes anonymous access on the next request — the public
  leg is a row check, not a token.
- `POST /api/v1/tasks/{id}/archive` → idempotent archive (soft-delete:
  hidden from default listings, rows retained; `task.archived` audit
  event on first archive only). 409 `run_active` while a run is executing
  or parked. There is no hard delete.

**Vocabulary (task 032, ADR 0031; task 038, ADR 0036).** A `task` row is a
**Task** and a `project` row is a **Project** — on screen, on the wire and in
the schema alike since task 038 (until then the rows were `project` and
`portfolio` and only the UI translated). `frontend/src/lib/vocabulary.ts`
remains the one place screen copy is maintained. Nothing below the task row
was re-parented.

Additive fields on the task read shape:
`project_ids` (the projects this task belongs to; empty list is
unassigned — a normal state; a task may belong to many projects,
ADR 0032), `source_count` (Included sources — funnel `relevant` — or `null`
when no run exists. `null` and `0` differ: `null` means the question has not
been asked, `0` means a run asked and none are Included), and — task 033 —
`visibility` (`org|private`), `is_owner` (caller-relative), and
`owner_display` (the owner's `display_name`, else a `sub` rendering,
**never the email**; `null` for ownerless rows). Task 037 adds
`is_public` (the public-sharing flag) and `access` (`full|public`,
caller-relative): `"public"` marks a read served by the public leg and
therefore redacted — it is the one bit the frontend uses to render the
two-tab public view instead of the full shell.

### Projects

A project is a named grouping **above** the task. It holds no plan, no
run and no evidence of its own, and carries a name, a description and an owner
— no status, no lifecycle, no cached counts (ADR 0031).

- `GET /api/v1/projects` — paginated, tenancy-scoped (`scope`,
  `owner_email` — same semantics as tasks). Each item carries a
  `task_count` **derived per read** from members the caller can read in
  their own estate (owner ∪ same-org; never the admin leg), plus the same
  three 033 read fields as tasks (`visibility`, `is_owner`,
  `owner_display`).
- `POST /api/v1/projects` `{name, description?, from_project_id?}` →
  201 project, stamped with the creator's `org_id`. `from_project_id`
  (task 033, amending ADR 0031 decision 4) resolves the source task
  under the **write** grade; the new project inherits that task's
  `visibility` and `org_id` and takes it as its first member, in one
  transaction.
- `GET /api/v1/projects/{id}` → project with its derived `task_count`
  (read grade).
- `PATCH /api/v1/projects/{id}` `{name?, description?, visibility?}` —
  partial, owner-only. `visibility` runs **the cascade**: the project and
  every member task (archived included) take the new value together, in
  one transaction. The cascade is the only writer of
  `project.visibility`; each member is **recomputed**, not assigned — a
  task is org-visible iff *any* project it is in is org-visible (owner
  ruling 2026-08-27), so a member shared with an org-visible project
  stays org-visible when this one goes private.
- `PATCH /api/v1/tasks/{id}` accepts `project_ids` (replace-all). Omit
  to leave membership unchanged; `[]` (or `null`) unassigns every project;
  a list replaces the set. Each id must resolve under the **write** grade
  (404 unreadable, 403 readable-not-owned) before anything is written —
  otherwise the route would be an existence oracle for another owner's rows.
  The task becomes org-visible if any named project is org-visible,
  private otherwise; a set spanning two organisations is refused 409 (a row
  carries one `org_id`). Newly added ids resolve under the
  **colleague-mutation** grade (owner ∪ same-org org-visible, never the
  admin leg — owner ruling 2026-08-27): a colleague may add their own task
  to an org-visible project they did not create; anything outside that
  estate is 404 before any write. Ids the task already belongs to are kept
  without re-resolution, so a membership that later went private never
  locks the owner out of editing their own set. Rename and membership
  writes are not `run_active` conflicts; they serialize on the task row
  lock.

**The visibility/org invariant (task 033, owner call (i); generalised to
many-to-many membership — owner ruling 2026-08-27).** A task in one or
more projects is **org-visible iff any of those projects is
org-visible**, private otherwise, and carries their `org_id` (its projects
span one organisation; a cross-organisation set is refused). A task with
no membership is unconstrained. Deterministic, no prompts: assignment and
the cascade both recompute the member across its whole membership set
(promotion or demotion alike); removal changes neither field. The invariant
spans three tables, so it is enforced in the write paths and pinned by a
property test — no CHECK can express it.

Tenancy scoping matches tasks exactly: an unknown project and an
unreadable one are the same indistinguishable 404.

**Archiving (task 058, owner round 11; gate G3 ratified at the review,
2026-11-09).** A project carries a nullable `archived_at`; the list reads
`status=active` by default (`?status=archived|all` to widen) and orders by
`last_activity_at` (the newest of the project's own `created_at` and its
members' `updated_at`). `ProjectOut` adds `archived_at`, `last_activity_at` and
`solo_task_count` (the caller's own active tasks here that sit in no other
active project). `POST /api/v1/projects/{id}/archive` (owner only,
idempotent) → `{archived_task_count}`: it archives the project and those solo
tasks with it, and skips a task whose walk is running or paused. A
non-owner's `PATCH project_ids` is refused 403 with "Only the task's owner can
change its projects."

### Task Agent turns

- `POST /api/v1/tasks/{id}/task-agent-turns`
  `{message, client_turn_id}` → an `application/x-ndjson` event stream (task
  058, S4, replacing the JSON body: the frontend and backend deploy
  together): `progress` ("Drafting the plan"), `delta` fragments of the
  reply as the planner writes it, then exactly one terminal event,
  `completed {turn: TaskAgentTurnOut}` or `failed {error, turn_index}`. The
  chat route's rules apply: the reservation and every authorisation error
  resolve before the headers (as the JSON envelope); the turn finishes and
  persists whether or not the client stays connected; a connection error
  before the first token is retried once; a replay of a completed turn is one
  `completed` line. A gate decision, an answer or a longlist action is one
  `completed` line. `TaskAgentTurnOut` (and the transcript turn) carries
  `question`, the planner's clarifying question, above its `suggestions`.
  One real planner turn. Every turn is durable in the per-task
  `task_agent_transcript`: its monotonic `turn_index`, assigned when the user
  message is received, is the conversation ordering coordinate;
  `created_at` is display metadata only. `message` caps at 10 000 characters
  (turns are durable and rehydrated into every later planner call). The short
  first transaction follows the owner/run-active gate **under the task row
  lock** and creates a `pending` row; the LLM call runs outside any
  transaction (I2); a second transaction writes its reply, raw planner-state
  snapshot, projected response and suggestions as `completed`. When the turn
  approves a plan, that second transaction re-checks the run fence under the
  task row lock (a run that started during the Task Agent call fails the turn
  with 409 `run_active` — no plan lands under a live walk) and then persists
  the plan, atomically. Planner failure marks the row `failed`; a process
  crash between phases leaves an honest `pending` row.
  `client_turn_id` is caller-minted UUID idempotency durable across API
  restarts: retrying a completed row with the same message returns its stored
  projected response verbatim. Only the latest `turn_index` may be retried;
  it re-runs in place with the same index. A reused id with a different
  message, or a non-latest unfinished retry, → 409 `stale_turn`. A new id
  while a `pending` row is younger than ten minutes → 409
  `task_agent_turn_in_progress`; reading after ten minutes terminally marks the
  pending row `failed`. The process-local per-task turn lock remains a
  belt-and-braces concurrency guard under the one-instance posture.
  A turn while the task's walk is **running** → 409 `run_active`. While the
  walk is **paused**, an Evidence search task still refuses the turn (409
  `run_active`: steering is its sanctioned mid-run plan channel), but an
  **Options scoping** task admits it *(owner ruling 2026-09-09, task 044
  decision D9: the gate is answered in the Task Agent chat; "routing hangs
  on the turn, not on the conversation kind")*: the turn is sorted by the
  gate sort (`gate_sort_v1`) into **question** — answered read-only from the
  paused walk's pinned scope through the shared answer core and rendered
  with citations (`kind: "answer"`, `answer: {...}`); the walk stays paused
  — or **decision** — one of the pending check-in's offered options,
  recorded through the same check-in response transaction as the card
  (`kind: "decision"`, bound to the `capability_run_id`, the `check_in_id`
  and the plan version; the second of a chat and a card answer is 409
  `already_answered`); an instruction is the decision "Change the plan"
  carrying the user's text, which ends the walk `aborted`, keeps the plan
  `approved`, and continues the same transcript row as an ordinary planning
  turn minting a new plan version (one row, two commits). An unsortable
  turn is asked back (`kind: "reply"`); a decision is never inferred from a
  question. The **approving branch** of a turn and `PATCH /plan` stay 409
  `run_active` while a walk is running **or paused**: no plan version lands
  under a live walk, so the fence still guarantees the latest-approved plan
  is the active walk's own lineage (review adjudication, 2026-07-21).
  **Longlist verbs** *([task 045 contract](../tasks/045-scoping-longlist/contract.md), D13; owner: "chat verbs in task 2,
  buttons as the second way")*: while a longlist exists and no walk is
  active, a Task Agent turn on a scoping task is sorted
  (`longlist_verbs_v1`) into **question · add an option · exclude · include
  again · other**. A question goes to the answer core over the union of the
  longlist scope and the option searches' scopes; a verb is confirmed in
  the thread before it is applied, never inferred; *add* mints the option
  *added by you* with a design proposed back (`option_design_v1`) and starts
  its option search (a child walk with no parent); *exclude* takes the
  user's reason. Each applied verb writes the same state the buttons write
  and a History event as the user's turn.
  `TaskAgentTurnOut` / `TaskAgentTranscriptTurnOut` carry the optional
  additive fields `kind` (`reply | answer | decision`), `answer` (the chat's
  citation payload) and `decision` (`option_id`, `label`, `check_in_id`,
  `capability_run_id`, `plan_version`); older rows carry none and read as
  `reply`.
  The draft `plan` mirrors `TaskPlan` field-by-field with every
  field optional while drafting + `steps[]` + `ready`. Planner context
  rehydrates from completed rows in `turn_index` order (each contributes the
  user message then planner reply); the raw `task_agent_state` from the latest
  completed row becomes `previous_draft`. Stored HTTP projections are never
  fed back to the Task Agent. A fresh tracing session id per request is correct:
  conversation quality depends solely on that durable composition.
- `GET /api/v1/tasks/{id}/plan` → the current plan (draft or approved,
  with `version`/`status`), whole-object. It returns the approved plan when
  one exists; otherwise the latest completed transcript row's stored
  `response.plan` without recomputation. It is 404 only when neither exists,
  so drafts survive API restarts.
- `PATCH /api/v1/tasks/{id}/plan` → typed edits to the current plan
  (`question`, `backend_scope`, `search_effort`, `analysis_depth`,
  `steering_mode`, `screening_criteria`, `published_after`/`published_before`,
  `geography`). Omitted fields stay as they are; an empty date or geography
  string clears that constraint. The merged result is re-validated as an
  executable `TaskPlan` and persisted as a new approved version
  (the previous approved row is superseded), with `source_turn_index` set to
  the latest completed Task Agent turn so `POST /runs` is not `plan_stale`.
  409 `run_active` while a walk is running or paused; 404 when there is no
  plan to edit; 422 when the merged plan is not executable. This is the
  document-edit path — it does not go through the Task Agent. On a scoping
  task the plan read and patch bodies also carry `your_options` (*Options
  you already have in mind*, D19) and the default preference "Transferable
  to *Where*" (D22) — task 045.
- `GET /api/v1/tasks/{id}/task-agent-turns` → the owner-scoped durable
  transcript in ascending `turn_index`, paginated in the standard
  `{data, pagination}` envelope. Each row exposes `turn_index`,
  `client_turn_id` (the caller's own idempotency key, returned so a
  reloaded client can retry its incomplete latest turn), `user_message`,
  `reply`, `suggestions`, `status`, `created_at` and
  `completed_at`; pending and failed rows remain visibly incomplete. There
  is no backfill: tasks predating the table simply have zero turns.

### Conversations

A **conversation** is `kind ∈ task_agent | chat`. A task holds **one active
Task Agent conversation** at a time (created with the task or on its first
Task Agent turn; the existing `/task-agent-turns` and `/plan` endpoints below
operate on it and additively expose `conversation_id` — paths and semantics
are unchanged) plus **many chats** (Claude-Projects-style follow-up threads,
user-created, task-scoped, answering across every artefact in the
task — an entry artefact is context, never a scope fence). Chats are
**read-only**: they never mutate a plan, never start a run, never write an
artefact — a question needing new evidence hands off to the planning
conversation as a typed affordance, never a plan mutation from chat.

**Grades (task 033).** Conversations carry `created_by` (the author's
`sub`; NULL on pre-033 rows, which belong to the task owner — the
legacy disjunct `created_by = :me OR (created_by IS NULL AND
owner_user_id = :me)`). A same-org colleague who can read the task
holds exactly three mutations: create a **chat** conversation, post a turn
to **their own** conversation, cancel **their own** turn. On the
conversation-id routes a chat resolves for its creator only and a planning
conversation for the task owner only — anyone else, colleague included,
gets **404**, never 403 (the row's existence is not theirs to learn; this
is what closes the `GET /{cid}/turns` transcript deep link). An admin may
read `GET /{cid}` and `GET /{cid}/turns` (traced) and write nothing here.
The creator's access dies with the task's read grade: de-enrolment or a
visibility flip revokes their own chats too. The per-user pending-turn cap
and its stale-turn sweeper are keyed to the acting user (`created_by`),
not the task owner. Unknown, unreachable, and — except where noted —
archived conversations are the same 404.

- `GET /tasks/{id}/conversations?kind=&status=` — the library read model
  (task read grade + the own-chats filter: each caller sees the
  conversations *they* created, plus legacy NULL rows if they own the
  task), both kinds, newest first, standard `{data, pagination}`
  envelope; each row carries a `latest_turn_preview` (bounded snippet of
  its most recent chat or Task Agent turn, from whichever turn table its
  `kind` reads). Default listing excludes archived rows; `status=archived`
  is the one filter that lists the caller's own archived chats (planning
  conversations are never archived).
- `GET /conversations/{cid}` → `ConversationOut` (`id`, `task_id`, `kind`,
  `title`, `status`, `entry_artefact_id`, `created_at`, `closed_at`,
  `archived_at`) — the deep-link resolver. An archived conversation is 404
  here (as on every route below except the list above and unarchive);
  unarchiving is the one call that resolves it back into reach.
- `POST /tasks/{id}/conversations` `{entry_artefact_id?}` → 201 chat
  conversation with `created_by = sub`, titled `"New chat"` until its first
  turn (kind is always `chat` — Task Agent conversations are
  lifecycle-created, never minted by hand; the request model has no `kind`
  field, so asking for one is 422 by construction). Granted to owner and
  same-org colleague alike on a readable task; takes no lock on the
  task row. `entry_artefact_id` must name an artefact belonging to the
  same task, else 404.
- `PATCH /conversations/{cid}` `{title?, entry_artefact_id?}` — chats only
  (422 on a Task Agent conversation); partial, an explicit `null`
  `entry_artefact_id` clears the entry-context chip; a replacement artefact
  is task-guarded the same as at creation.
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
  - `conversation.titled {conversation_id, title}` — sent once, while the
    first turn's stream is open, when the `chat_title` step's line replaces
    the message's cut as the chat's title (task 058, round 14); never
    terminal. A task's name comes the same way from its confirmed question
    (the `task_title` step), reaching clients as `task.updated {name}`.
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
  `no_completed_run` (the task has never finished a run) · 409
  `run_active` (the task's walk is currently `running` or `paused` —
  finish or park it first) · 429 `chat_capacity` (an owner-wide in-flight
  chat-turn cap, distinct from the run-slot `capacity` code). A generated
  answer is also capped by a fixed output-token ceiling.
- `POST /conversations/{cid}/turns/{turn_id}/cancel` → `CancelTurnOut
  {status}` — the explicit stop signal (bare disconnect does not cancel; see
  above). Owner-scoped, idempotent, keyed to the named pending turn: it stops
  generation, persists whatever prose has streamed so far as `cancelled`,
  and returns the turn's honest current status (already-terminal is a
  no-op read, not an error).
- `GET /tasks/{id}/chunks/{chunk_id}/context?quote=` — the chat-citation
  hover/click read: the same clamped context-window shape as the artefact
  citation-context read above (including short edge-only `previous`/`next`
  snippets), resolved from a chat citation's durable chunk id plus its quote
  (chat citations carry chunk ids, not artefact citation-table ids). An
  ambiguous or unmatched quote is 404, same rule as the artefact seam. Both
  keyings locate the quote with `locate_unique_span` (case, whitespace,
  curly quotes), not a literal unique-substring count.

### Runs

- `POST /api/v1/tasks/{id}/runs` `{}` → 201 run — creates the
  `capability_run` and dispatches the walk off the event loop. Guarded by
  the per-task Postgres row lock: a second active run → 409
  `run_active`; at the executing-walk bound → 409 `capacity` (parked runs
  hold no slot). 400 if no approved-ready plan.
- `GET /api/v1/tasks/{id}/runs` → paginated list (newest first;
  standard `{data, pagination}` envelope — runs accumulate);
  `GET .../runs/{run_id}` → one. Status ∈ `running | paused | succeeded |
  degraded | failed | aborted | interrupted`.
- **Child walks** *([task 045 contract](../tasks/045-scoping-longlist/contract.md), D6 and finding A1)*: an option search
  is a `capability_run` whose `parent_capability_run_id` names the longlist
  walk that asked for it; the parent waits for its children, and a child's
  failure degrades the parent. The longlist walk's and its children's
  progress arrive on the existing run stream (§ SSE).

### Check-ins (steering)

- `GET /api/v1/tasks/{id}/check-ins?status=pending` — **pending is
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
- `POST /api/v1/tasks/{id}/check-ins/{check_in_id}/response` — one per
  check-in; a second → 409 `already_answered` (per-task lock; barrier-
  tested). Body is a tagged union on `kind`:
  - `{"kind": "option", "option_id": ..., "params"?: {...}}` — canonical
    or authored option (authored picks apply Agent attribution).
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
  Check-in kind `baseline_confirm` (task 044; Options scoping only — the
  gate after the baseline, on the scoping lattice only): the render quotes
  the baseline's key assumption and the plan's Settings; `options[]` are
  `confirm_plan` ("Confirm plan and build longlist" → the walk finishes
  `succeeded`; the decision payload records `plan_version` and the baseline
  `artefact_id`; since task 045 (D1) the decision also opens the **longlist
  walk** on the confirmed version under the dispatch lock and reservation,
  and a chat decision carries the opened walk on the decision; the card
  route stays `204` and the thread learns of the walk from the run stream —
  owner, plan review P16a: "card route stays 204") and `change_plan` ("Change the plan" → response `abort`
  with `action: "change_plan"`: the walk ends `aborted`, the plan stays
  `approved` and editable). In unattended mode the point does not pause:
  the runner records `decided_by: standing_default` and flags it for the
  end-of-run review, and opens the longlist walk the same way (task 045,
  finding A2). A decision may also arrive as a Task Agent turn
  (§ Task Agent turns); both land in the same transaction.
  The answer and its `continuation.requested` event commit in one
  transaction; the parked run's **boundary continuation walk** dispatches
  after commit (answers are always accepted; execution may queue at the
  bound). UI renders only server-supplied options; vetting/judge steering
  never surfaces (B2′ relevance-emphasis is in-scope steering and arrives
  as ordinary options).

### Read models (read-grade GETs under `/api/v1/tasks/{id}/…` — task 033: owner, same-org colleague, or admin)

`funnel` · `landscape` (distributions over the screened-in set only) ·
`groups` · `evidence` (paginated source list with status ladder) ·
`findings` (paginated discriminated `profile: iof | icf` records; carries
run-scoped B2′ relevance marks `priority | normal` when the run has them) ·
`sources/{source_id}` (optional dossier: source metadata, tags, and claims
cited by the latest artefact only) · `decisions` (paginated
decision log from `steering_history` + allowlisted events) · `artefact`
(sections, span-anchored claims, citations; the chunk-context read model
clamps context to a character window around the cited span — the 008
seam's named consumer — and only attaches a short `previous`/`next`
snippet when that window hits a chunk edge) · `coverage` (the composed one-line coverage
sentence: stop condition + adequacy, composed server-side). Read models
render honest absence: missing stages are `null`/absent, never faked.

- Artefact `SectionOut.nav_label` (task 032) is an optional short label for the
  contents list, at most 28 characters, produced by the section proposal
  (`synthesise_sections_v4`). Over-length is **rejected at the proposal
  boundary**, never truncated downstream — unlike the title and focus bounds
  beside it, which clamp. There is no backfill: an artefact synthesised before
  the field existed reads `null`, and the client falls back to a shortened
  title. Absence is a normal state, not an error.

- `SectionRole` includes `case_studies` (task 034, ADR 0034): a section
  whose `role` is `case_studies` carries its programme cards in
  `SectionOut.cards` (a list of `CaseStudyCardOut`). Each card holds its
  own `claims` (span-anchored into `card.prose`) and a `result_claim_id`
  for the primary finding. `ArtefactOut.most_relevant_notes` (additive,
  default empty list) carries grounded one-liner notes for the top cited
  sources. `ArtefactOut.full_report_intro` (additive, nullable) carries the
  generated roadmap line for the full-report body; absence is a normal
  state and the client renders nothing in its place.

- `DecisionOut` carries `actor_display` and `actor_is_viewer` (task 058,
  round 10), so History can say who without a second read.

- Evidence rows carry `country` (an ISO country name, or null), `full_text_url`
  (the document's own address once its text was collected) and
  `full_text_status` (`not_attempted` · `queued` · `ingested` · `failed`);
  `CoverageBackendDetailOut.passes` and `CoverageQueryOut.query_id` name the
  search's passes and queries (task 058, rounds 9 to 12).

- The grounding verdict belongs to the claim (task 058, owner round 10):
  `ClaimOut.grounding_tier` and `.grounding_rationale`, moved off
  `CitationOut`. Chat's turn citations keep theirs for now.

- Artefact `ClaimOut.theme` resolves a theme claim's durable characterisation
  or grouping references to named items (`name`, optional `description` and
  `size`; grouping items also carry their `facet` for deep-linking), including
  their resolved member `sources` (`source_id`, `title`) when member identities
  are available. Stale or unresolvable references and member sources are
  omitted, and an empty theme resolution is `null`.

**Longlist routes** *([task 045 contract](../tasks/045-scoping-longlist/contract.md), deliverable 11; Options scoping only)*:
`GET /api/v1/tasks/{id}/longlist` (themes, options, counts, states, the run it
came from; 404 until the first clustering result; `LonglistThemeOut.document_count`,
`OptionDocumentOut.authors` and `.venue`, `OptionProfileOut.acts_on`, and
`ShortlistOut.note_stale`, task 058) · `GET /api/v1/tasks/{id}/options`
(task 058, S4: every option row of the task from the end of the suggest stage,
`{option_id, name, description, origin, state, merged_into_option_id,
search_status, found}`, where `search_status` is `queued` · `searching` ·
`searched` · `failed` from the option's own search and `found` its acquired
count, null until searched; the same read predicate as the longlist; no
provisional flag, the client knows from `has_longlist`; served on the public
leg while the longlist is being built, as the longlist itself is public
read-only: owner, 2026-11-09) ·
`GET /api/v1/tasks/{id}/options/{option_id}` (the option card) ·
`POST /api/v1/tasks/{id}/options` (add by hand — the button's path, the same
handler as the chat verb) · `POST .../options/{option_id}/exclude` and
`.../include` (with the user's reason) · `POST /api/v1/tasks/{id}/shortlist/note`
(owner only: rewrites the shortlist note; 404 on no shortlist, 409 while a walk
runs, 503 when the writer fails; task 058, round 11). Each write is logged as
the user's turn in History (OS ruling 1). `RunOut.stages` (`RunStageOut`) lists
a run's stages with their status and timings (task 058, N23). All additive.

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
never the unfiltered task total or the returned page's length.
Evidence status is still derived server-side in Python task-wide before
filtering and paging (the `funnel_out` precedent — bounded to one
task's rows).

- `GET .../evidence`: `status` (repeatable; any evidence status ladder
  value, plus the aggregate shortcut `Included` = the 7 ladder positions
  reached once a source is screened in — i.e. every status except `found`
  and `screened_out`) · `cited` (bool) · `country` (an ISO country name, or
  `none` for rows without one) · `query` (a coverage query id: the rows that
  search found) · `depth` (`full_text`) · `appraised` (bool) · `theme` (a
  characterisation theme, or a longlist theme id on an Options scoping task)
  (task 058, rounds 9 to 14). An unrecognised `status` value is 422.
- `GET .../findings`: `profile` (`iof | icf`; 422 if unrecognised) ·
  `facet`+`group` (both required together — a facet name and an exact
  group label within it; an unknown facet/group pair returns an empty
  page, not an error) · `group_id` (the group's qualified id,
  `<facet>:gNN`, as an alternative to `facet`+`group` — combining it with
  either is 422; an unknown `group_id` returns an empty page) ·
  `source_id` (the evidence row's source id; no match returns an empty
  page).

### SSE

`GET /api/v1/tasks/{id}/events?cursor=<sequence>` — fetch-stream with
bearer auth (native `EventSource` cannot send headers). Replay-then-tail
with an atomic cutoff: backlog is read to a snapshotted max `event_log`
sequence, the live tail subscribes from `sequence+1` in the same
consistent view (race-tested: no loss, no duplication). Each frame:
`id:` = the `event_log` sequence (the client's reconnect cursor — the
client passes its own `cursor`; `Last-Event-ID` is not relied on),
`event:` = frame type, `data:` = the typed payload. 15 s heartbeat
comments; `X-Accel-Buffering: no`; generator cleanup on disconnect.

**Re-authorisation (task 033).** The snapshot resolves under the read
grade, and the tail re-authorises through the same predicate on every poll
(batches and heartbeats alike), **before** reading the batch — a caller who
loses access mid-stream never receives that interval's events and the
stream closes as a normal end, no error frame. Revocation events that
close an open stream: de-enrolment, a visibility flip on the task, a
project cascade privatising the member, and admin revoke. The owner's
stream never revokes, and archiving does not close it (archived filtering
is not tenancy).

Frame vocabulary (discriminated union, `type` names are contract):

| type | payload (summary) | source |
|---|---|---|
| `run.status` | `{capability_run_id, status}` | walk open/park/finish/interrupt |
| `stage.started` | `{stage, label, blurb}` | component run start |
| `stage.completed` | `{stage, label, summary, seconds, counts: [{value, noun}]}` (`counts` is what the done row shows, in the server's words; task 058) | component terminal |
| `tick` and `run.status` | `tick` carries `capability_run_id` (task 058 review) so a late frame from an earlier run is dropped by the client | |
| `stage.failed` | `{stage, label, reason, skipped}` | component failure/skip |
| `artefact.skeleton` | `{sections: [{index, title, focus, role}]}` in presentation order; `role` is `intro`, `key_findings`, `case_studies` or `section` | synthesise presentation progress |
| `artefact.section_started` | `{index}` | synthesise presentation progress |
| `artefact.section_completed` | `{index, title, prose, citations: [{start, end, n, source_id, title, citation_id, claim_id, chunk_id, quote}], claims: [{claim_id, start, end, tier, rationale}]}` (the judged markers that replace the draft's; task 058). The citation rows commit with the whole report, so `citation_id` cannot be read until then; `chunk_id` (2026-11-09) lets the page read the passage by chunk and quote (`GET .../chunks/{chunk_id}/context?quote=`) while the report is still being written | synthesise presentation progress |
| `checkin.pending` | the full check-in resource | `steering.pause` |
| `checkin.resolved` | `{check_in_id, response, decided_by}` | `steering.decision` |
| `plan.updated` | `{plan, version}` | plan row supersession |
| `task.updated` | `{name?, question?, status?}` | lifecycle audit events |
| `tick` | `{stage?, activity, done, total, unit, section, heartbeat, dropped, ephemeral: true}` (`done`, `total`, `unit` and `section` null when absent) | **ephemeral channel** — never persisted, never state-bearing, no `id:` |
| `artefact.section_delta` | `{index, text, mode: "append" \| "replace", occurred_at, ephemeral: true}` | **ephemeral**: prose appended to the section being written (task 058); display-only, never replayed |
| `artefact.section_revising` | `{index, spans: [{start, end}], occurred_at, ephemeral: true}` | **ephemeral**: the sentences the judge failed, sent before the repair (task 058); display-only, never replayed |
| `artefact.section_sources` | `{index, sources: [{source_id, title}], occurred_at, ephemeral: true}` | **ephemeral**: the sources the writer has read for the section (task 058, round 7) |
| `artefact.section_claim` | `{index, start, end, sources, occurred_at, ephemeral: true}` | **ephemeral**: a cited sentence as the writer's claim closes, shown as a muted provisional marker (task 058, round 7) |
| `artefact.section_card` | `{index, title, prose, occurred_at, ephemeral: true}` | **ephemeral**: a case-study card as it is written (task 058, round 7) |
| `artefact.source_note` | `{source_id, title, note, occurred_at, ephemeral: true}` | **ephemeral**: a source note as it is written (task 058, round 8) |
| `search.query` | `{backend, query, kind, results, occurred_at, ephemeral: true}` | **ephemeral**: a search query as it runs, normalised and bounded (task 058, round 9) |
| `characterise.themes` | `{themes: [{label, description}], stage, occurred_at, ephemeral: true}` | **ephemeral**: the themes as they are found (task 058, round 9) |
| `toc.sketch` | `{boxes: [{key, layer, text}], links: [{key, source, target}], occurred_at, ephemeral: true}` | **ephemeral**: the theory of change's first draft while it is written (task 054, S12) |

`stage` keys are the pinned stable component vocabulary, thirty-four keys
(task 058, S1; task 054's 058 alignment). Evidence search: `acquire`, `screen`,
`classify`, `appraise`, `ingest`, `characterise`, `select`, `extract`, `group`,
`synthesise`. Options scoping: `inherit`, `suggest`, `option_searches`,
`extract_interventions`, `longlist`, `option_profile`, `constrain`, `theme`,
`shortlist`. Theory of change: `toc_draft`, `toc_read` (the draft walk of an
uploaded theory), `toc_item_searches`, `toc_select`, `toc_discover`,
`toc_merge`, `toc_search_new`, `toc_new_link_searches`, `toc_judge`,
`toc_search_again`, `toc_retry_searches`, `toc_figures`, `toc_choose`,
`toc_summarise`, `toc_report`; the check also uses the shared `classify` and
`appraise`. Each fan-out of item searches has its own key and the same label as
the step that runs it. A ToC walk has no plan steps, so its rows come from the
frames alone; frames with the same label render as one row. Labels,
blurbs and the activity text are server-supplied presentation from one table
(`api/stage_vocabulary.py`, task 058 N17) and may change; the client renders
them and keeps no stage copy of its own. A plan step carries a `row` key:
stages that share a row key render as one card row; `acquire` and `screen`
are two rows ("Searching", "Screening"; owner, round 10), `classify` and
`appraise` share "Classifying", so the client decides nothing about rows.

A `tick` (task 058, S2) carries one set of fields for every stage:
`activity` (the line the client shows as it is, in the server's plain
voice), `done` and `total` (integers, null when the stage has no honest
count: no total known before its loop started), `unit` (`documents`,
`batches`, `abstracts`, `searches`, `sections`, `windows`, `options`; null
with no count), `section` (the writer's section line, null outside writing),
`heartbeat` (true when the server repeated the current tick because a model
call is still in flight, every 10 s) and `dropped` (the server's dropped-tick
counter for the task, for the silent-gap measure). Ticks are coalesced to at
most one per task per stage per 500 ms. A client that connects mid-run
receives, after the durable replay, the last tick per stage and the current
section draft as one `artefact.section_delta` with `mode: "replace"`, from
process-local memory that is cleared when the stage or the run ends and
expires after ten minutes. Nothing else internal (module names, model ids,
raw payload keys) is observable. The frontend store must rebuild idempotently from
replay alone — mid-run refresh, server restart with a parked pending
check-in, and reconnect-mid-stream are the tested cases.

`toc.sketch` (task 054, S12) draws the theory of change's first draft while
the model writes it. Each frame carries every box and connection written so
far and replaces the one before: boxes first, then connections, a connection
only after both its boxes. Keys are the model's draft keys (`b1`, `l1`), not
stored ids. An empty frame means the draft is being written again (the stream
failed and the ordinary call runs, or the draft failed its checks and is
retried): the page drops its sketch. The stored graph (`GET /toc`, read when
`toc_draft` completes) replaces the sketch. A reconnect gets the sketch so far
from process-local memory, cleared when the stage ends. Only a draft that
becomes the canvas as written is sketched; a user's own diagram is not.

`artefact.*` frames other than the ephemeral ones (`tick`, the five
`artefact.*` frames marked ephemeral, `search.query`,
`characterise.themes` and `toc.sketch`) are durable presentation/progress records, not partial artefact reads or authoritative
artefact content: whole-section prose is sent for live rendering, while the
report — the artefact of record — is committed only when synthesis completes.
`artefact.section_delta` and `artefact.section_revising` (task 058, S3) are
display-only: the draft a client builds from deltas is never shown as
verified, carries a muted provisional marker per cited sentence as the
writer's claim closes (`artefact.section_claim`), and is replaced by
`artefact.section_completed`, whose judged markers replace the provisional
ones and which stays the record; a replay carries no
deltas, so a store rebuilt from replay holds the completed prose only. The skeleton's display `index` is the identity
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

**Backend mode:** `PA_BACKEND_MODE=live|stub|auto` (default `auto` = presence of the
model route's key variable, `OPENAI_API_KEY` on `openai-direct` and
`AWS_BEARER_TOKEN_BEDROCK` on a Bedrock route, task 053). `live` without that key fails
boot loudly;
missing search keys in live mode are warned at startup (coverage degrades
honestly, never silently).

## Deprecations

Additive changes append here with dates; removals require a documented
deprecation window and never break the generated client within `/api/v1`.

- **2026-11-09 — task 058 at the review (owner-accepted proposals B1 to
  B13), additive.** Six more ephemeral SSE frames (`artefact.section_sources`,
  `artefact.section_claim`, `artefact.section_card`, `artefact.source_note`,
  `search.query`, `characterise.themes`); `tick.capability_run_id`;
  `occurred_at` on the deltas and revisions; the skeleton's `role`;
  `section_completed.citations[]` (with `chunk_id`, added the same day on the
  owner's "fix it at the root": the passage of a finished section's citation
  is readable during the write) and `.claims[]`; the provisional claim
  markers on the draft; `acquire` and `screen` as two rows; `page_size` 20 for
  tasks and projects and `pagination.has_more`; project archiving
  (`archived_at`, `POST /projects/{id}/archive`, `?status=`,
  `last_activity_at`, `solo_task_count`, ordering by activity, the 403
  message); `DecisionOut.actor_display` and `.actor_is_viewer`; evidence rows'
  `country`, `full_text_url`, `full_text_status` and the `country`, `query`,
  `depth`, `appraised`, `theme` filters; `CoverageBackendDetailOut.passes`,
  `CoverageQueryOut.query_id`; the grounding verdict on `ClaimOut`;
  `LonglistThemeOut.document_count`, `OptionDocumentOut.authors` and `.venue`,
  `OptionProfileOut.acts_on`, `RunOut.stages`, `ShortlistOut.note_stale`,
  `POST /tasks/{id}/shortlist/note`; the chat stream's `conversation.titled`
  and names from the question; the options read on the public leg. Nothing
  removed.

- **2026-09-05 — task 038 (ADR 0036), the one break without a window.**
  `/api/v1/projects/**` (the Task) → `/api/v1/tasks/**`; `/api/v1/portfolios/**`
  → `/api/v1/projects/**` (the Project); schemas `Project*` → `Task*`,
  `Portfolio*` → `Project*`; fields `project_id` → `task_id`, `portfolio_id(s)`
  → `project_id(s)`, `from_project_id` → `from_task_id`; SSE frame
  `project.updated` → `task.updated`; wire literal `decided_by`/`authored_by`
  `orchestrator` → `agent` (old stored values read back as `agent`). No
  redirects (owner fork F3): the only consumers are this repo's frontend and
  e2e, regenerated from the same OpenAPI document in the same commit; public
  share links copied before the deploy are regenerated. Rollback: ADR 0036
  § Rollback.
