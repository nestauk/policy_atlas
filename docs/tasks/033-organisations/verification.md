# Verification: 033-organisations

> **Status: IN PROGRESS — build phase (steps 5–6).** Assembled incrementally at each
> phase commit; complete only at the Phase 12 exit gate.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, Phase 0) | pass | Third run; see the baseline note below. |
| `make verify` (Phase 0b in tree) | pass | Backend 2170 passed · typecheck · lint · frontend build green. |

**Baseline note (Phase 0).** The first two full-verify runs were red (45, then 4
failures) from *test contention*, not the tree: a delegated agent ran pytest against the
shared `policy_atlas_test` database while the main suite was mid-run. A quiet-machine
run of the affected subset on the clean tree passed (294/294). The remaining 4
order-dependent failures were caused by Phase 0b itself and fixed (see Deviations).

## Phase evidence

### Phase 0 — Baseline
- Full `make verify` green (see above). Alembic head confirmed `b3c7d914e0a2` — the one
  revision never referenced as a `down_revision`.
- Route inventory captured from the tree: **39 route decorators**;
  `conversations.py` mounts two routers (`/api/v1/conversations` ×7 routes,
  `/api/v1/projects` ×2); `chat_turns.py` has no router (service module).
  Evidence: [route-inventory.md](route-inventory.md).

### Phase 0b — Structured logging at the API entrypoint (owner call (k))
- `create_app` calls `configure_logging()` first; test
  `test_create_app_configures_json_logging_and_httpx_guard` asserts the **rendered JSON
  shape** under `LOG_FORMAT=json` (event, key, level, timestamp) and the httpx
  WARNING guard on the deployed path.
- **Staging httpx INFO check (rubric 15a): pending — scheduled with the Phase 12 live
  checks.**

### Phase 1 — Schema, migration and `created_by` writes (gate: schema)
- Migration `a4f1c8e3b6d2` (sole head, off `b3c7d914e0a2`): `organisation`, `app_user`,
  `org_id`+`visibility` on `project`/`portfolio` with CHECKs and the two org-leg
  indexes, `conversation.created_by` backfilled from the owning project's owner.
  `lock_timeout='5s'` set in both directions (no value named anywhere in the repo;
  5s chosen and commented against the runbook's blocker preflight).
- `create_conversation` writes `created_by` on insert.
- **Full `make verify` green** (2172 backend · mypy 267 files · ruff · infra 45 ·
  drift-check OK · frontend 61 files/407 tests · build ✓). Named tests:
  `test_migration_roundtrip_organisation_tenancy`,
  `test_downgrade_erases_chat_authorship_exposing_colleague_chats` (rubric 32 — also
  proves a re-upgrade misattributes the colleague's chat to the owner, so re-upgrade
  does not undo the exposure).
- Test repairs, justified inline: six `metadata.tables` counts 33→35; the portfolio
  column-set equality gains the two columns; **the `downgrade -1` roundtrip test had
  been vacuous for fifteen revisions** — repaired to name its revision explicitly.
- Handed forward: `planning.py` also creates `conversation` rows and does not yet set
  `created_by` — Phase 4/5 decides deliberately (contract grades planning
  conversations by project ownership, so it is not load-bearing there).

### Phase 2 — Access helper: owner and org legs (gate: auth semantics)
- `_access.py`: `accessible_project`/`accessible_portfolio` → `Access(row, is_owner)`.
  Org leg = one SQL predicate (correlated `EXISTS` equating `app_user.org_id` to the
  row's non-NULL `org_id`; explicit `.correlate()` — without it SQLAlchemy renders a
  cross join that would match any org). Write = owner only. `for_update` requires
  `write=True` (`ValueError` otherwise), and locks are issued through the owner leg
  alone — a colleague path cannot lock the owner's row, pinned structurally by
  `test_locking_can_only_ever_land_on_the_callers_own_row`.
- NULL rule pinned: `test_two_unenrolled_callers_cannot_see_each_others_null_org_rows`
  (both flavours: NULL `org_id` row in `app_user`, and no `app_user` row at all), plus
  the compiled-SQL structural pin `test_org_read_leg_is_a_correlated_sql_predicate`.
- 403 `forbidden` branch added to the envelope handler (contract § 8 text; inert until
  Phase 4 wires routes). 16 named tests; verify-fast gate green (2188 backend, mypy,
  ruff). Old helpers and all routes untouched.
- Handed forward to Phase 4/5: the six `for_update=True` sites; `conversations.py:283`
  and `chat_turns.py:446` are chat paths that must move or drop the project-row lock
  once colleagues can reach them — the helper's guard raises loudly if missed.

### Phase 3 — API surface (gate: public API)
- `GET /api/v1/me` (`ON CONFLICT DO NOTHING`; named tests for idempotency,
  non-clobbering, single-row provisioning) · `scope=all|mine` (default `all`) +
  `portfolio_id` + `owner_email` on the listings · `ProjectOut`/`PortfolioOut` gain
  `visibility`, `is_owner`, `owner_display` (all required; never the email; `null`
  for ownerless rows — the placeholder glyph is a frontend decision) · project PATCH
  `visibility` with 409 in-portfolio and both-fields 422 · `POST /portfolios
  {from_project_id}` under the write grade, inheriting `visibility` and `org_id` ·
  org stamping on both creates (**pulled forward from Phase 4** — without it this
  phase's own listings would be wrong) · counts bound to `own_estate`
  (owner ∪ same-org, admin-free).
- **Full `make verify` green** (backend 2221 collected · drift-check OK · frontend
  61 files/407 · build ✓). 32 named tests across `test_me_router.py` and
  `test_tenancy_api_surface.py`.
- **Bug found mid-phase:** `app_user.email` has no unique constraint and § 3b
  expects stale addresses, so the `owner_email` filter resolves via
  `owner_user_id IN (SELECT …)` instead of `scalar_one_or_none` (which would 500 on
  a duplicate address).
- **Sequencing notes (minor deviations, resolved within the contract):**
  `PortfolioUpdate` has no `visibility` — the i.4 cascade (Phase 7) is its sole
  writer; the splat is replaced by an explicit `_PATCHABLE_COLUMNS` allow-list.
  `update_project` cut over to the graded helper early (the colleague-403 test
  requires it); the remaining item routes stay owner-only until Phase 4, so a
  colleague's listing temporarily shows rows the detail route 404s — closed by
  Phase 4 in the same PR.

### Phase 4 — Route consolidation and signature cutover
- All 19 sites route through the graded helper per the lead's binding grade table;
  reads = read grade, mutations = write grade (colleague 403 / outsider 404). The
  conversation-id router's five lifecycle routes and `GET /{id}/turns` resolve via
  `_graded_conversation` (chat = creator with the legacy-NULL disjunct; planning =
  project owner; always 404 — `write` kept as the Phase 8 seam). The transcript
  deep-link leak is closed
  (`test_conversation_id_router_closes_the_deep_link_leak_for_a_colleague`).
- Locks kept exactly per spec: `planning.py` ×2, `create_run`,
  `create_conversation`, `update_project`, `archive_project_route` (the plan's
  six-site lock list undercounted — the archive route also locked; covered by the
  grade table's "keep any current lock" rule and flagged).
- `owned_portfolio` and `_owned_conversation` retired; `owned_project` retained
  with exactly one caller (`chat_turns.py:446` — Phase 5 re-keys it). Final
  `owner_user_id` grep audited hit-by-hit: helper, display projections, create
  stamping, own-chats predicates, and the two Phase-5 turn routes only.
- **Deviation flagged (lead call):** the own-chats filter on `list_conversations`
  landed here with the grade widening, not in Phase 5 as the plan split it —
  widening the listing without the filter would have exposed the owner's
  conversations to colleagues mid-branch and forced double-testing.
- **Spec/code finding:** `planning.py` and `chat_turns.py` each have a private
  `_phase_one_turn` — same name, different functions; no entanglement.
- verify-fast green: 2240 passed, mypy 276 files, ruff. Cross-owner 404 suite
  unmodified (rubric 3). 19 new tests in `test_route_grades.py`.
- Executor note: the fast-worker run died once on a transient API error before
  editing and was resumed with context intact; total agent spend was
  well above typical for a "mechanical" phase — the grade table made it
  executable, but the volume was deep-reasoner-sized (plan risk confirmed).

### Phase 5 — Chats, cap, sweeper and locks
- The three colleague mutations and nothing more: chat creation on a readable
  project via a new `chat_mutable_project` grade (wider than write, narrower than
  read — resolves through `own_estate`, so Phase 8's admin leg can never reach chat
  creation structurally); turn POST and cancel under the own-conversation rule
  (`own_chat_leg`, one shared definition — no drifted copies). Planning-kind
  refusal is 422 by construction: `ConversationCreate` has no `kind` field and
  `extra="forbid"`.
- **Cap and sweeper re-keyed together** to `created_by` (scope preserved: one
  allowance of 2 pending turns per person across their estate; constant renamed
  `_USER_PENDING_CAP`). The named consequence (N members → 2N concurrent turns on
  one owner's project) recorded at the check.
- **Locks:** create-conversation's project lock removed (it protected only the
  planning partial index, which chats cannot collide with); turn POST moved to
  `FOR UPDATE OF conversation` — the bare join lock would have re-locked the
  owner's project row. **Finding:** the old project lock never actually protected
  the `run_active` fence (`create_run` commits before its executor inserts the
  running row), so that fence was already best-effort and is unchanged.
- **Leak found by the phase and fixed by the lead:** `_graded_conversation` never
  required the project to be reachable, so a de-enrolled colleague could still
  read their own chat's transcript (with the owner's evidence base in it) on a
  foreign project. Fixed with `own_estate(project, user_id)` in the resolver, plus
  `with_for_update(of=conversation)` (the helper's bare `FOR UPDATE` also locked
  the joined project row on a creator's archive path). Pinned by extending
  `test_de_enrolment_kills_a_colleagues_chat_mutations` to the two read routes.
- The phase mutation-tested its claims (reverting each key/lock/grade fails its
  named test). `owned_project` fully retired. 10 new named tests; verify-fast
  green (2249 backend, mypy, ruff).

### Phase 6 — SSE re-authorisation
- `_tail` re-authorises through `may_read_project` — a boolean ask of the same
  `_read_legs` the snapshot resolves through; no second tenancy predicate exists.
  Re-auth runs **before** the batch read (a revoked caller never receives the
  interval's events); heartbeats re-authorise too, so a revoked stream dies within
  one poll interval. No archived filter on re-auth — archiving must not kill the
  owner's own stream mid-frame. Cost: one statement, two index probes per poll.
- **Event 4 (admin revoke) holds by construction:** Phase 8's admin leg lands
  inside `_read_legs`, which snapshot and tail share — pinned by
  `test_sse_reauthorisation_resolves_through_the_same_legs_as_the_snapshot`
  (monkeypatched recording delegate + verdict flip).
- Five named tests (de-enrolment, org→private, cascade-shaped flip, owner
  survival, the structural pin); anti-vacuity mutation run recorded (all five
  fail with the re-auth short-circuited). verify-fast green (2254, mypy, ruff).
- Handed to Phase 8: the trace wants "one line per SSE re-authorisation" and the
  matched leg — `may_read_project` returns a bare bool today; Phase 8 widens it.
- Handed to Phase 9b: `_colleague_stream_closes_on`'s `revoke` callback is the
  single seam to swap for real CLI levers.

## Diff summary

(Assembled per phase; final pass at Phase 12.)

- Phase 0b: `create_app` wires `configure_logging()`; one new test.

## Deviations flagged (minor, resolved within the contract's vocabulary)

1. **`cache_logger_on_first_use=True` dropped from `configure_logging()`** (Phase 0b).
   The contract pins "one call, nothing else about logging changes". The one call was
   not shippable as-is: with caching on, any test that builds an app freezes every
   module-level logger's config, and `structlog.testing.capture_logs()` — used by 5
   assertions in `test_ingest_full_text.py` — silently stops intercepting for every
   suite that runs later. Four ingest tests failed order-dependently. Caching off makes
   the entrypoint call safe process-wide; the cost is one config lookup per log call.

## Intent & assumptions

## Known unverified items

- Staging httpx INFO line check (rubric 15a) — deferred to Phase 12 live checks.

## Public safety

Nothing sensitive added so far: no real subs, no addresses, no org names.

## Review handoff (step-7/8 inputs)

Executor provenance so far: Phase 0 route inventory — fast-worker; Phase 0b — fast-worker
(lead root-caused and fixed the capture_logs interaction); Phase 1 — deep-reasoner.

- **Knowledge candidates** (running list, one bullet per durable-seeming lesson):
  - `structlog.configure(cache_logger_on_first_use=True)` and
    `structlog.testing.capture_logs()` are mutually exclusive across a test suite: once
    any code path configures with caching and a module-level logger fires, capture_logs
    in *later* tests silently sees nothing. Symptom: order-dependent failures in suites
    alphabetically after the configuring one.
  - Delegated agents must never run pytest while another suite is mid-run — the test
    database is shared and the collision presents as dozens of scattered, unreproducible
    failures. Serialize all DB-touching test runs across agents; the delegation brief
    must say so explicitly.
  - A red baseline at build-open is not always the tree: check Docker/Postgres first
    (`make setup`), then contention, before reading test bodies.
  - `alembic downgrade -1` in a roundtrip test rots silently: once any newer migration
    lands, `-1` reverts *that* instead of the revision the test is about, and the
    assertions pass vacuously. Name the target revision explicitly. (Found wrong for
    fifteen revisions in `test_migration_roundtrip_screen_stage_and_classify_tags`.)
  - A single-file `mypy tests/core/test_schema.py` run poisons `.mypy_cache` and the
    next full run reports a spurious `attr-defined` error; `rm -rf backend/.mypy_cache`
    clears it. Pre-existing harness quirk.
  - Alembic roundtrip tests run on their own connection, so the `conn` fixture's
    rollback cannot clean their seeds — commit outside the fixture and delete in
    `finally`, then verify zero residue.

## Deferred work

(Collected at Phase 11 into docs/deferred.md.)
