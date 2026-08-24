# Plan: 033-organisations

> **Status:** rev 1 drafted 2026-08-24 · **rev 2.0, 2026-08-24 — rewritten after the
> plan-stage adversarial review** (three lanes: sequencing/verifiability,
> coverage/executor-marks, and Codex on build mechanics). Against [contract.md](contract.md)
> rev 3.0 (**approved**) and the 42-item [rubric.md](rubric.md).
> **Plan approval (step 3 🛑): _pending_.**
>
> **What rev 1 got wrong, in short.** The invariant phase ran *before* the API surface it
> enforces, so four of its five deliverables were unfalsifiable at their own boundary. The
> API phase would have gone **red and stayed red for three phases**, because root
> `make verify` ends in `frontend-verify` and `openapi-sync` breaks a strongly-typed mock
> fixture. The schema phase gated on `verify-fast` against a **binding** task-cycle rule,
> and reds **six** `metadata.tables == 33` assertions plus a `portfolio` column-set equality
> that no phase budgeted. Route consolidation authorised on `conversation.created_by`
> before anything wrote it. `is_admin`'s closed-list assertion sat in a phase where three
> of its four readers did not yet exist, so it would have passed vacuously. **Org stamping
> on create had no phase at all.** And the "gate-first" claim was false: there are six
> gates, not three, and rev 1 called Phase 9 — which the entire live check depends on —
> the safest.
>
> **ADR 0032 moves out of the build.** The task cycle puts the ADR in the design phase
> (conversation A, step 4). Rev 1 scheduled it in build Phase 11, which would have decided
> the **ADR 0031 decision 4 amendment** after ten phases of implementing it.
> **ADR 0032 is written before the build opens**, alongside this plan.

## Ordering, and the honest version of the gate claim

There are **six** approval gates, at positions 1, 2, 3 and three at 10. Reordering puts
the public-API gate third instead of seventh, which is the one that actually mattered:
under rev 1 a refused API gate killed the whole invariant phase.

**The gate at the ops CLI cannot be moved earlier** — it depends on the schema, the API and
the helper. So it is stated as an accepted risk rather than dressed up: **if that gate is
refused, nothing already built is wasted, but the slice loses its acceptance** — there is
no other way to create an organisation, enrol anyone or grant admin, so rubric 14 and
26–30 and the live check all become unreachable. That is the real risk in this plan.

Note also that contract rev 3.0 is **approved** and says each gate "is granted" by it, so
these are re-checks at the point of implementation, not live approvals.

## Verify schedule

**Full `make verify` at Phase 0, 1, 3, 9a and 12.** Phase 1 gets one because the
task-cycle rule makes it mandatory for any schema-touching phase — rev 1 violated that.
Phase 9a gets one because it changes `pyproject.toml`, `uv.lock` and `backend/Dockerfile`,
none of which `verify-fast` exercises. Backend phases between use `verify-fast`; frontend
checkpoints use `make frontend-verify`.

**Additionally, and not covered by `make verify`:** `make audit` (pip-audit) runs at
**9a** — the whole rationale for the `ops` group's shape is audit reachability, and it is a
standalone CI job. `pnpm e2e` (the mock journey) and `fe-api-smoke` run at **10a and
10c** — both are CI jobs outside `make verify`, and Phase 10 rewrites the mock API and puts
seven components into read-only mode, making the journey spec the likeliest casualty in
the slice.

*Repo note for the builder:* `backend/Makefile:60`'s `--ignore=tests/test_ingest_full_text.py`
is a **stale path** — the file moved to `tests/evidence_base/sourcing/` in the 025 hoist, so
pytest silently ignores nothing and `verify-fast` is not as fast as it looks. Do not
"fix" it as a drive-by: correcting the path would start hiding the table-count assertions
this slice must keep seeing.

## Phases

### Phase 0 — Baseline · *fast-worker*
Full `make verify` green, alembic head, and the **route inventory captured from the tree**
(39 decorators across the scoped routers, plus `chat_turns.py`). Evidence for
`verification.md`.

### Phase 1 — Schema, migration and `created_by` writes 🛑 **GATE: schema** · *deep-reasoner*
The two tables, the four columns, the `created_by` backfill, the two org-leg indexes, a
lock timeout. **`created_by` is also written on insert here** (`conversations.py`
`create_conversation` sets eight columns and no author) — three lines, and it makes Phase 4
self-verifying instead of shipping a window where a colleague cannot read back their own
chat while the owner can.
**Existing tests this phase must repair, with written justification per rubric 3:** six
files asserting `len(metadata.tables) == 33` (`test_screen.py`, `test_classify.py`,
`test_appraise.py`, `test_acquire.py`, `test_ingest_full_text.py`, `test_embeddings.py`) and
`test_schema.py`'s `portfolio` column-set **equality** assertion.
**Tests:** up/down roundtrip; backfill correctness; **the rollback-exposure test** (rubric
32). **Full `make verify`.**

### Phase 2 — Access helper: owner and org legs 🛑 **GATE: auth/tenancy semantics** · *deep-reasoner*
One helper, the **owner and same-org** legs and the write grade. The admin leg is
deliberately **not** here (Phase 8). The org leg is a **SQL predicate** — the NULL rule is
the highest-blast-radius mistake in the slice — pinned by the two-NULL-callers test.
404/403 discipline.
**Also ships a unique-org test fixture.** `organisation.name` is `NOT NULL UNIQUE` and the
test DB is shared across the suite (`resource_support.py` already warns about this for
subs); a fixed-name org fixture fails on the second test that uses it, and the symptom
would read as a tenancy bug three phases later.
*Introduce the graded helper alongside `owned_project`/`owned_portfolio` rather than
cutting the signature over in one step — a strict-green boundary between an incompatible
signature and its callers is not practical.*

### Phase 3 — API surface 🛑 **GATE: public API** · *deep-reasoner (was fast-worker)* · **moved from position 7**
`GET /api/v1/me` **with its upsert semantics spelled out** — `ON CONFLICT DO NOTHING`,
because `DO UPDATE` on every sign-in silently clobbers ops-set `display_name`, `email` and
`is_admin`, and a test written from a one-line spec would stay green forever. `scope`
(**default `all`**, stated because a cautious implementer picks `mine` and the feature then
hides behind a switcher), `portfolio_id` and `owner_email` on the listings.
`ProjectOut`/`PortfolioOut` gaining `visibility`, `is_owner`, `owner_display` (**never the
email**). `POST /portfolios {from_project_id}` under the **write** grade. Error envelope
gaining 403 `forbidden` and 409 `visibility_conflict`; **422 `validation_error` — not
403 — for a non-admin passing `owner_email` and for the both-fields PATCH**.
**Portfolio counts move to the tenancy predicate here** (`_task_counts` counts every member
unconditionally today and `list_portfolios`' `total` is a bare owner count — nobody was
told to touch them in rev 1).
**Generated-artifact repairs land in this phase, not later:** `make openapi-sync`
regenerates **`frontend/openapi.json` and `frontend/src/api/gen/types.ts`** (there is no
`backend/openapi.json`), and the new required fields break `frontend/src/mock/fixtures.ts`'s
`mockProject` — typed as exactly `components["schemas"]["ProjectOut"]` — and
`backend/tests/api/test_contract_models.py`'s direct `ProjectOut(...)` construction. Both
are repaired here, or root `make verify` is red for three phases.
*Not mechanical: every ambiguity above is a decision, which is why the gate exists.*
**Full `make verify`** (includes `drift-check` and `frontend-verify`).

### Phase 4 — Route consolidation, signature cutover and org stamping · *fast-worker, spec and grade table from lead*
Route every project-, portfolio- and conversation-scoped site through the graded helper
and **retire the parallel old helper** (19 call sites across ten API modules). Includes the
seven routes on `conversations.py`'s conversation-id router, graded per contract § 4.
**Org stamping on create lands here** — `create_project` and `create_portfolio` stamp
`org_id` from the creator's `app_user.org_id`. Rev 1 lost this entirely; without it every
row created after the migration is invisible to its owner's organisation and the failure
surfaces only at the live check.
**Lock decisions are handed forward explicitly, not inherited.** Six sites pass
`for_update=True` (`projects.py:107`, `planning.py:300`, `planning.py:458`, `runs.py:128`,
`conversations.py:283`, `chat_turns.py:446`). A mechanical rewrite either drops the lock —
run-start and plan-patch stop serialising, and no test fails because concurrency is not
unit-tested — or carries it onto the new read legs, which is the exact defect contract § 4
forbids. **The spec fixes each site's lock explicitly; the worker does not decide.**
**Tests in this phase:** the tenancy matrix per route grade, and rubric 3's check that the
existing cross-owner 404 suite is unmodified. `test_api_conformance.py` builds its case
list off the live route table, so a forgotten route fails automatically — lean on it.

### Phase 5 — Chats, cap, sweeper and locks · *deep-reasoner*
The own-chats filter exactly as specified; the three colleague mutations and nothing more;
**the pending cap and `_expire_stale_pending_turns` re-keyed together** (re-keying one
without the other permanently caps a colleague whose turns die, with no operator lever);
the lock scope decided in Phase 4's spec applied and tested.

### Phase 6 — SSE re-authorisation · *deep-reasoner*
`_tail` re-authorises per batch and closes the stream when access is gone.
**Four revocation events, not three** — de-enrolment, a visibility flip, **an i.4 cascade**
and admin revoke. Rev 1 dropped the cascade, which is the one that leaks a whole portfolio's
events. Three of the four levers are built later, so this phase simulates them by direct DB
mutation **and Phase 9b re-runs this suite against the real levers**.

### Phase 7 — The visibility and org invariant · *deep-reasoner* · **moved from position 6**
i.1–i.6 over **both** `visibility` and `org_id`; the property test across all six paths;
`update_portfolio` barred from writing `visibility` outside the cascade; the corrected i.5
semantics **and its copy string** — "leave the Task out of the Project", never "remove it
first", which was a silent re-exposure loop. Now runs *after* the API it enforces, so every
one of these is testable through HTTP.

### Phase 8 — Admin leg, trace and the closed-list assertion · *deep-reasoner*
The admin read leg, in the helper **and** the listing scope resolver. The closed-list
structural assertion lands **here**, not in Phase 2 — its four readers only all exist once
Phase 3 has shipped, and asserted earlier it passes vacuously against a one-element list.
Trace grain: per row on direct reads, per request on cross-org listings **including a
zero-result search**, per SSE subscribe and re-authorisation.
**`configure_logging()` is wired into the API entrypoint here.** It is called today only in
`runtime/orchestrate.py`; the container starts `uvicorn ... create_app` directly, so
`LOG_FORMAT=json` is **not applied on the API path** and the trace would reach CloudWatch as
unstructured text. The admin leg's only control is this log, so a test asserts the rendered
JSON shape rather than that `log.info` was called.

### Phase 9a — Dependency, lock and image plumbing 🛑 **GATE: `boto3` + `boto3-stubs`, the `Dockerfile` change** · *deep-reasoner*
The `ops` group in `pyproject.toml`, `uv.lock` regenerated **and committed** (an unfrozen
`uv sync` masks a stale lock; `--frozen` then fails in the image build), and **both**
`uv sync` invocations in `backend/Dockerfile` (lines 17 and 21) carrying `--no-group ops` —
miss the second and `boto3` ships in the image while the declaration says otherwise.
Proves, before any command volume lands: frozen install, strict mypy over the import,
**`make audit` seeing the dependency**, and the built image not containing it.
**Full `make verify` plus `make audit`.**

### Phase 9b — Ops CLI 🛑 **GATE: Cognito account creation** · *deep-reasoner*
`org create`; `user create` with `DesiredDeliveryMediums=["EMAIL"]`; **`user enrol`
carrying the person's rows across as `private` in one transaction, reporting the counts**
(owner call (j)); `resync`; single-row assign; de-enrol clearing `org_id` on their rows;
admin grant/revoke **with its own trace record**; the **environment-mismatch guard** and
the **`FOR UPDATE` concurrency guard**; deletion of the `staging-user`, `prod-user` and
`cognito-user` make targets.
**Re-runs Phase 6's SSE suite against the real revocation levers**, and re-runs Phase 7's
invariant property across the three enrolment moves (rubric 29).
*Operator-facing strings — the "use enrol" remediation, the mismatch refusal — are the
CLI's entire safety UX and stay with this phase rather than being deferred to a copy pass.*

### Phase 10a — Frontend data plumbing · *fast-worker* → `make frontend-verify` + `pnpm e2e`
The `/me` hook, `scope` in **every** affected query key, `portfolio_id` in
`PortfolioDetailView` **and in `PortfoliosView`'s list page** (both derive from the same
global 50-row page via `newestTaskUpdateByPortfolio`; rev 1 named only the detail view),
cross-family cache invalidation, and the mock API gaining `/me` **at the commit that first
mounts `useMe`** plus the portfolio routes it has never served.

### Phase 10b — Chrome and copy · *lead for strings, fast-worker for wiring* → `make frontend-verify`
The switcher (**hidden when `/me` returns no organisation** — rubric 14's dark-launch
invariant is a merge gate and it lives here), `owner_display` on rows and cards, the
account menu (including **long-address truncation and a null owning organisation rendered
without a blank line**), the **owner-scoped check-in banner**, `HistoryView` readable with
the project, the admin's "this spans organisations" label, and the visibility-outcome
lines. *Copy is lead-owned and lands before the wiring is called done, so placeholders
cannot ship.*

### Phase 10c — The read-only affordance matrix · *fast-worker from an explicit component list* → `make frontend-verify` + `pnpm e2e` + `fe-api-smoke`
`is_owner=false` renders read-only in: **`AppShell`'s project-settings popover (rename and
archive)** — absent from rev 1's list, and the reason a colleague would see Rename, click,
and get "The project couldn't be renamed" — `PlanningPane` **and its `ChatSidePanel`
duplicate**, `PlanCard`, `RunPane`, `CheckInCard`, the suggestion chips, the plan-start
card and retry controls. Plus **the URL leg**: a non-owner cannot reach a mutation by
address. `LifecycleRoute` gates on run status alone and cannot make a component read-only,
so this is routing work, not a component.
*The failure mode if this slips is a half-done matrix — a surface of buttons that error —
which is worse than not shipping it, so it is its own checkpoint.*

### Phase 11 — Records · *lead*
Spec flow-back (`web-api.md` §§ Auth boundary, Portfolios, Conversations; `data-model.md`;
`JUMPBOX.md` operator IAM; `DEPLOYMENT.md` CLI invocation, the **roll-forward** posture and
the **manual downgrade procedure**, since the ECS task runs `alembic upgrade head` only);
deferred seams; **the AGENTS.md phase pointer**; and **the three privacy-notice
discrepancies quoted verbatim in `verification.md` as an open escalation** to the notice's
owner. ADR 0032 is *not* here — it ships with this plan, before the build.

### Phase 12 — Exit gate · *lead, fast-worker for evidence capture*
Full `make verify`, `make audit`, `make drift-check`, `pnpm e2e`, `fe-api-smoke`; the
built-image check; **the production-scale backfill rehearsal** — representative row counts,
measured DDL and backfill duration, blocker query and lock-timeout result, and a success
budget against the deploy outage window, because otherwise the first real measurement is
the production migration itself; the staging deploy in its pinned five-step order; the live
check; the **DPIA screening and processing-record update recorded**; the log group's
**one-month retention** recorded as the bound on how far an admin-access investigation can
look back; `verification.md` assembled.
**Rollout gate: no enrolment before the frontend is published.** `deploy.sh` scales the
backend up *before* `publish_frontend` and its CloudFront invalidation. Enrolling anyone in
that window activates org listings for clients still running the old bundle — the
half-matrix state Phase 10c exists to prevent. The first organisation is enrolled only
after invalidation completes, as an attended canary.

## Decisions

1. **Gated phases as early as they can honestly go**, and the one that cannot move is
   stated as a risk rather than dressed up (§ Ordering).
2. **Full `make verify` at 0, 1, 3, 9a and 12**, plus `make audit` at 9a and the two CI-only
   frontend jobs at 10a and 10c.
3. **Enumerate from the tree, never from the contract.** `test_api_conformance.py` already
   derives its cases from the live route table; a forgotten route fails on its own.
4. **The helper ships parallel to the old one in Phase 2 and the cutover happens in Phase
   4.** A strict-green boundary between an incompatible signature and its 19 callers is not
   practical, and rev 1 assumed one.
5. **Design-bearing work does not go to `fast-worker`** — and rev 1 had this backwards in
   two places: `/me`'s upsert semantics and the affordance matrix, where the failure is a
   *missing* component rather than a wrong one, were both marked mechanical. Phase 3 is now
   `deep-reasoner`; Phase 10c gets an explicit component list rather than a category.
6. **The security lane runs as three scoped passes** — tenancy boundary, privileged read
   and audit, operator CLI. Scheduled at step 7, not discovered there.

## Risks

- **The live check needs a real deliverable mailbox.** No `EmailConfiguration` on the pool,
  so invitations use the 50-per-day `COGNITO_DEFAULT` sender. **Resolve before Phase 9b.**
- **The migration takes `ACCESS EXCLUSIVE` while the API is at zero.** Mitigated by the
  lock timeout, the blocker preflight and the Phase 12 rehearsal — the rehearsal is the
  real one, and rev 1 named it without assigning it.
- **Phases 4, 8 and 9b are the under-estimated ones**, not Phase 10. Phase 4 must keep
  every route's existing behaviour intact across ten modules; Phase 8 recrosses the same
  surface for trace grain; Phase 9b is a whole operational subsystem. The largest existing
  affected suites are `test_read_models.py` (1,956 lines), `test_chat_turns.py` (1,442) and
  `test_planning_router.py` (1,093).
- **`alembic/` is outside ruff's scope** (`lint` checks `src tests` only), so the new
  migration gets no lint gate. Worth a manual read at Phase 1.
- **`test_migration_roundtrip_screen_stage_and_classify_tags` uses `downgrade -1`.** Once
  033 is head it silently downgrades *033* instead of the revision named in its docstring —
  it stays green while testing the wrong thing. Repair it in Phase 1 with the others.
