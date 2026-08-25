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

### Phase 7 — The visibility and org invariant (i.1–i.6)
- Assignment (i.2/i.3) syncs the member to its portfolio on **both** fields in one
  rule; i.6 touches neither; the i.4 cascade is the sole writer of
  `portfolio.visibility` — owner-only (colleague and in-org admin 403), includes
  archived members, self-heals an operator-mismatched member `org_id`
  (`test_the_cascade_repairs_a_member_stamped_to_another_organisation`), one
  transaction. Both write paths lock the portfolio row (`for_update` through the
  owner leg only); the one deadlock interleaving is documented and resolves as a
  repeatable no-op.
- `PortfolioUpdate.visibility` = one deterministic path: present → cascade,
  omitted → unchanged, explicit `null` → 422. Splat allow-list unchanged.
- **Property (rubric 22):** hypothesis is not a dependency (not added); instead a
  fixed-seed 90-operation walk over all seven ops through real HTTP, breach check
  in SQL (`IS DISTINCT FROM` for org_id) after every op, non-vacuity asserted.
  Mutation-checked (dropping the i.2 sync or the archived-member cascade fails).
- The i.5-then-i.2 loop's end state pinned (`…ends_org_visible`); the 409 copy
  names "leave the task out of the project"; Phase 10b repeats it in UI copy.
- SSE cascade revocation now tested against the **real** PATCH lever.
- Test repair justified: `test_portfolio_patch_does_not_accept_visibility` →
  `…accepts_visibility_only_as_the_cascade` (its own docstring named the
  condition for replacement; the protected property re-asserted behaviourally).
- `make openapi-sync` also swept up pre-existing description-only drift from
  Phases 4–6 docstrings. verify-fast 2267 green; drift-check OK; frontend green.
- Handed to Phase 8: re-assert the cascade 403 with an out-of-org administrator.

### Phase 8 — Admin read leg, trace, closed-list assertion
- **One seam.** The admin leg is a third disjunct in `_access._read_legs`
  (`admin_read_leg` = `EXISTS(app_user WHERE user_id = :me AND is_admin)`,
  uncorrelated to the row). Row reads, both listings and the SSE tail widened at
  that one line; archived/status filters sit in the caller's `base` select
  *before* any leg, so `include_archived` stays caller-controlled for an admin.
- **Write is untouched.** `own_estate`, `chat_mutable_project` and `own_chat_leg`
  are unchanged, so the admin is not a colleague: project/portfolio mutations 403
  (the leg reached the row, then the owner check refused), every chat path 404
  (no admin leg in the grade at all). Both codes asserted and recorded.
- **Conversation-id router** (§ 4): `write=False` disjoins the admin leg,
  `write=True` keeps the creator/owner predicate alone — the parameter Phase 4
  reserved finally diverges. Admin reads `GET /{id}` and `GET /{id}/turns`
  (planning rows included); `PATCH`/`archive`/`unarchive` 404, this router's
  standing refusal.
- **One-query leg detection.** The graded read selects `own_estate(...)` as a
  boolean column beside the row (`_access._OWN_LEG`, `conversations._OWN_GRADE`);
  a row that came back with it `False` was reached by the admin leg. No second
  round trip and no second copy of the tenancy predicate to drift.
  `may_read_project` returns `ReadCheck(allowed, via_admin)` the same way;
  `listing_scope` returns `ListingScope(predicate, via_admin)` and queries the
  flag only when `scope != "mine"`.
- **Trace shapes, as emitted** (structlog, configured by Phase 0b):
  `admin_read {user_id, kind, row_id}` — one per row, project/portfolio/
  conversation, including the SSE subscribe (which is an ordinary graded read);
  `admin_listing {user_id, kind, scope, owner_email, page, page_size, row_count,
  total_items}` — one per cross-org request, **zero-result included**;
  `admin_stream_read {user_id, kind, row_id}` — one per SSE re-authorisation
  batch, never per frame. Content and grain asserted via `capture_logs`, never
  transport; Phase 12 confirms one of each in CloudWatch.
- **Nothing is emitted for an entitled read** — owner on their own row, colleague
  on an org row, admin on their own row, admin on their own org's row.
- **Closed list at code level** (rubric 16), asserted by walking `api/**/*.py`:
  `routers/_access.py::admin_read_leg` (readers i + ii — both resolve through
  `_read_legs`), `routers/_access.py::_is_admin` (reader iii's 422 gate and
  reader ii's trace decision), `routers/me.py::get_me` (reader iv),
  `contract/tenancy.py::MeOut` (the field declaration, named rather than
  filtered). Plus: no `.values(...)` under `api/` carries the column.
- **Judgment calls, stated rather than left implicit:** (a) the 403 path emits an
  `admin_read` — the leg disclosed the row's existence, and an admin's attempted
  mutations belong in the trail; (b) `owner_email` is logged **verbatim** — it is
  the filter, the log is read by the same ops/admin audience § 3b already scopes
  it to, and an audit line that cannot say what was searched for is not one;
  (c) `admin_listing` fires on admin + `scope=all` whether or not the widening
  changed the page — deciding "did it actually cross an organisation" per row
  costs a second scan and makes the trail depend on that day's data.
- **Volume note for Phase 12 (not a deviation):** `_tail` re-authorises every
  `SSE_POLL_INTERVAL_SECONDS` (default 0.4s), so an *idle admin stream* emits
  ~2.5 `admin_stream_read` lines/second. That is the grain § 3a specifies
  ("one per re-authorisation batch"), implemented as written; if CloudWatch
  volume proves unacceptable, the lever is the poll interval, not the grain.
- **Tests:** `test_admin_leg.py` (12) —
  `…reads_org_visible_and_private_rows_in_a_foreign_organisation` ·
  `…reads_a_null_organisation_row_and_an_ownerless_one` ·
  `test_reads_the_caller_was_already_entitled_to_emit_no_trace_line` ·
  `test_an_administrator_is_refused_every_mutation` ·
  `…cannot_write_through_the_conversation_id_router` ·
  `…listing_spans_organisations_and_emits_one_line_per_request` ·
  `test_scope_mine_is_not_the_admin_leg_and_emits_nothing` ·
  `test_a_zero_result_administrator_search_still_emits_its_line` ·
  `test_a_non_administrators_listing_is_never_traced` ·
  `test_is_admin_defaults_false_on_a_bare_me_provisioned_row` ·
  `test_no_write_under_the_api_can_set_is_admin` ·
  `test_only_the_named_code_sites_read_the_is_admin_flag`.
  `test_sse.py` (+2) — `…traces_the_subscribe_and_every_reauthorisation`
  (grain asserted as an equality against the recorded re-authorisations) ·
  `test_sse_stream_closes_when_the_administrators_flag_is_revoked` (revocation
  event 4, now real; the owner's stream on the same row survives).
  `test_visibility_invariant.py` (+1) —
  `test_the_cascade_is_refused_to_an_out_of_organisation_administrator`
  (Phase 6/7 handoff discharged: reachable, still 403).
- `org_support` gains `ops_set_admin` (the phase-9b grant/revoke row write) and
  `make_conversation`.
- `make openapi-sync` re-run: **description-only** drift from the two listing
  docstrings; no schema change, as expected of a behavioural leg.
  verify-fast **2282 green**; mypy + ruff clean; drift-check OK.
- Handed to Phase 9b: `ops_set_admin` is the seam to swap for the real
  `admin grant` / `admin revoke`, and § 3a's operator-side grant/revoke trace
  (naming operator, subject and direction) is 9b's, not this phase's.

### Phase 8 — Admin leg, trace and the closed-list assertion
- `admin_read_leg` joins `_read_legs` as the third disjunct — the one seam, so item
  routes, listings, and SSE snapshot **and** tail gained it in one edit;
  `own_estate`/`chat_mutable_project` stay admin-free by design, so an admin is
  refused every mutation including chat (403 on graded writes; 404 on the
  conversation-id router, which spends no 403). `_graded_conversation`'s `write`
  parameter finally diverges: the admin leg exists on its read path only.
- Leg detection is one query: the own-grade predicate selected as a boolean column
  beside the row; `via_admin` is its negation; `for_update` paths skip it (owner-
  bounded). `may_read_project` → `ReadCheck`; `listing_scope` → `ListingScope`.
- Trace shapes (all emitted from `_access.py`; `_resolve` emits `admin_read` itself
  so a route cannot forget): `admin_read {user_id, kind, row_id}` per row incl. SSE
  subscribe · `admin_listing {…filter, page, row_count…}` per cross-org request,
  zero-result included, `owner_email` logged verbatim (it is the audit subject) ·
  `admin_stream_read` per SSE re-auth batch, never per frame. **Volume note for
  Phase 12:** an idle admin stream emits ~2.5 trace lines/s at the 0.4s poll —
  the lever is the poll interval, not the grain.
- Judgment: a 403'd admin mutation attempt **does** emit `admin_read` — the leg
  disclosed the row's existence, and attempts belong in the trail.
- Closed list at code level, pinned by AST walk (prose references excluded):
  `_access.admin_read_leg`, `_access._is_admin`, `me.get_me`, `contract.tenancy
  .MeOut`; plus the no-write assertion on the column under `api/`.
- SSE event 4 (admin revoke closing a stream) now real; Phase 7's handoff
  discharged (`test_the_cascade_is_refused_to_an_out_of_organisation_administrator`).
- 15 new tests. verify-fast 2282 green; drift-check OK (description-only drift
  re-synced).

### Phase 9a — Dependency, lock and image plumbing (gates: boto3+stubs, Dockerfile)
- `ops` group (`boto3>=1.43,<2`, `boto3-stubs[cognito-idp]` — same group, boto3
  ships no `py.typed`); `[tool.uv] default-groups = ["dev", "ops"]` is the CI
  change: `uv run` re-syncs to default groups on every invocation, so any
  Makefile/workflow `--group ops` would be silently undone. `uv.lock` +102 lines,
  purely additive. Both Dockerfile `uv sync` lines carry `--no-group ops`, guarded
  permanently by `test_every_uv_sync_excludes_the_ops_group` (infra tests, inside
  root verify).
- Proofs: frozen sync + import · strict-mypy probe inside the checked tree
  (revealed `str`, not `Any`) · `make audit` scans all 8 new packages in-scope
  (125 audited; the only skip is the first-party editable project) · the image's
  exact `uv sync --no-dev --no-group ops --frozen` yields an environment with no
  boto3 where `create_app` imports; `--no-dev` alone ships boto3 (94 vs 86
  packages) — the flag is load-bearing, exactly the contract's predicted failure.
- **Known-unverified (named for the review):** the literal `docker build` image
  check could not run — the Docker daemon on this machine has no registry egress
  (pulls hang; host curl reaches the registries). Re-run on a working machine:
  `docker build --platform linux/amd64 -t pa-img backend/` then
  `docker run --rm pa-img python -c "import boto3"` (expect ModuleNotFoundError)
  and the `create_app` import (expect success). Also: the local BuildKit cache was
  pruned during diagnosis — the next image build here starts cold, and **Phase
  12's deploy work is blocked on daemon networking**.
- Full `make verify` (exit 0, incl. the new hygiene test — infra 46) and
  `make audit` green.

### Phase 9b — Ops CLI (gate: Cognito account creation)
- Eight commands; no password flag exists anywhere; no `AdminDeleteUser` path
  (both structural tests). `user create`: Cognito first (`AdminCreateUser` with
  `DesiredDeliveryMediums=["EMAIL"]` — validated against botocore's own service
  model via Stubber), DB failure keeps the account and prints the enrol
  remediation, existing address says "use enrol". `user enrol`: every owned row
  stamped and privatised **in one transaction** with the upsert, counts reported;
  atomicity pinned (mid-move failure moves nothing, the upsert rolls back too);
  re-enrol re-privatises a deliberately shared row. `de-enrol`: clears org/email/
  admin + `org_id` on their rows — no AWS call, which with grant/revoke resolving
  by DB address keeps operator IAM at exactly `ListUsers` + `AdminCreateUser`.
  `rows assign`: a member project moves its portfolio and siblings (closed set).
- **Environment guard (rubric 26):** STS account vs operator-supplied expected ·
  pool reachability · **the DB leg — the resolved pool must recognise the
  connected database's newest `app_user` subs; subjects-exist-but-none-resolve is
  a hard refusal `--yes` cannot lift** (that case IS prod-tunnel/staging-creds).
  Honest limit, documented: an empty `app_user` degrades to typed confirmation
  (blast radius nil — nobody has signed in there).
- **Concurrency (rubric 27):** all `app_user` writers read `FOR UPDATE`;
  grant-vs-de-enrol races refuse in either commit order because de-enrol clears
  the address grant resolves by. Operator identity on traces = `--operator`
  defaulting to the STS ARN (not $USER, which is spoofable).
- `staging-user`/`prod-user`/`cognito-user` make targets deleted (pinned by
  test); DEPLOYMENT.md § 3 rewritten to the CLI with the `COGNITO_DEFAULT`
  50/day caveat. SSE revocation re-driven through the real CLI de-enrol.
- 45 new tests; verify-fast 2327 green; mypy strict 291 files; ruff clean.
- **Escalation (owner decision):** no CLI path creates an org-less administrator
  (`admin grant` resolves by address, which only `enrol --org` writes). The live
  check's "third admin in neither org" is satisfiable by enrolling the admin
  into a third organisation; alternatives — an org-less enrol mode, or
  grant-by-sub (rejected: bypasses the rubric-27 address-mediated lock).
- Post-033 rename note: `rows assign` reports in code words; the rename slice
  must cover `policy_atlas.ops`.

### Phase 10a — Frontend data plumbing
- `useMe` (staleTime Infinity); `scope`/`portfolio_id` in the query keys;
  `PortfolioDetailView` exact via the `portfolio_id` filter; `PortfoliosView`
  overview keeps one global page raised to the 200 cap — **documented
  approximation** (`PortfolioOut` has no last-task-updated field; >200 active
  projects can mis-order the overview; the detail view is exact); cross-family
  invalidation (portfolio PATCH ↔ project lists, all scopes by prefix); mock API
  gains `/me` (unenrolled default — dark launch), portfolio routes, and
  `portfolio_id` filtering. frontend-verify green (422 tests); `pnpm e2e` 11/11.

### Phase 10b — Chrome and copy
- Switcher (Organisation · Mine) on both list views, hidden entirely when `/me`
  has no organisation — and no `scope` param is sent, so the unenrolled UI is
  byte-identical (rubric 14). Owner column rule:
  `showOwnerColumn = hasSwitcher || any non-owned row` (collapses to false for
  every unenrolled state); null `owner_display` renders "—", and
  "No organisation" on the admin wide list. Account menu (display name,
  CSS-truncated email, organisation, "Administrator") extended in place in
  AppShell. Check-in banner gated on `is_owner` at the one AppShell site that
  covers poll, badge, tab marker and banner (rubric 38). HistoryView verified
  non-owner-readable — no frontend gating existed to remove (rubric 39).
  VisibilityControl ships the binding outcome lines (singular/plural) and the
  i.5 conflict copy; copy strings were lead-authored and wired verbatim.
- frontend-verify green (443 tests, 64 files); e2e 11/11.

### Phase 10c — The read-only affordance matrix
- Component by component (rubric 37): `ProjectSettingsMenu` rename/archive
  hidden · `PlanningPane` + `ChatSidePanel` duplicate — composer disabled with
  "Steering is limited to the project owner." (the one flag also covers retry
  controls and in-transcript options; chips hidden as defense-in-depth) ·
  `PlanCard` — Review kept, Start search hidden · `RunPane` both fresh-run
  buttons · `CheckInCard` hidden entirely · the plan-start block via
  `PlanDocument`'s existing `readOnly` (`hasRun || !isOwner`). Chat surfaces
  stay enabled for colleagues (granted mutations).
- **URL leg:** `/projects/:id` is the only mutation-bearing route; a non-owner
  reaching it by address gets the read-only variant, no redirect; `isOwner`
  fails closed while loading. Pinned by `WorkspaceView.test.tsx`.
- **Live bug closed:** `stream.pendingCheckIn` is ownership-blind SSE state — a
  colleague viewing during a pending check-in saw the full steering card
  (options, free-text steer, Stop analysis) before this phase.
- Findings flagged, not skipped: `RunPane`/`JourneyPane` are currently dead code
  (gated + tested anyway); "plan-start card" resolved to `PlanDocument`'s Start
  block (distinct from `PlanCard`); cosmetic quirk — the settings gear renders
  an empty popover for a non-owner (not a safety issue, left alone).
- frontend-verify green (460 tests, 66 files); e2e 11/11; `fe-api-smoke` is
  CI-only (needs live backend credentials — sandbox denies `.env` reads).

### Phase 11 — Records (spec flow-back)
- `web-api.md`: § Auth boundary rewritten to the three read legs + write grade +
  NULL rule + `/me` + filters + the admin trace; envelope gains 403 `forbidden`
  and 409 `visibility_conflict` (422 reuse stated); Projects/Portfolios sections
  carry the tenancy params, the three read fields, `from_project_id`, the cascade
  and the invariant; Conversations carries the grades, `created_by`, the three
  colleague mutations and the re-keyed cap/sweeper; read models re-headed to the
  read grade; SSE gains the re-authorisation paragraph.
- `data-model.md`: tenancy note under § Entity hierarchy.
- `JUMPBOX.md`: operator IAM (exactly `ListUsers` + `AdminCreateUser`; no
  deletable path; no task-role Cognito permission). `DEPLOYMENT.md`: § 6 ops-CLI
  invocation over the tunnel; § 8 the 033 roll-forward posture, the evidenced
  chat-exposure rationale, and the manual downgrade procedure (the ECS task
  upgrades only).
- `docs/deferred.md`: build seams added (org-less admin CLI gap · PortfolioOut
  last-updated field · admin_stream_read volume · RunPane dead code · ops CLI
  rename coverage); the stale mock-API portfolio entry discharged.
- **ADR 0032 drift check: no drift** — all six decisions match the as-built code
  (two tables/two columns; sub-only identity; three legs with the SQL NULL rule;
  the read-only admin boolean with the structurally asserted four-reader list and
  trace-as-sole-control; entrypoint logging; the invariant + ADR 0031 D4
  amendment). The one sub-decision detail — `cache_logger_on_first_use` dropped —
  is a flagged deviation above, not ADR-level drift.
- okf-validate green (120 concepts, 0 violations).

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
