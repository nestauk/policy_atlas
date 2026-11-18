# Verification: 065-accounts

Evidence for the accounts programme (steps A, B, C). Build opened 2026-11-17 in the
worktree on `task/065-accounts`; the build and the review stack run in the same session by
the owner's decision (2026-11-17), with the review lanes as fresh agents. Public-safe: no
address ranges, passwords, email addresses or account ids.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline) | pass | 2026-11-17, after rebasing onto 064a head `1182bb11` (the first run failed on `test_healthz_is_async_so_it_needs_no_pool_thread`, which 064a fixed in `2cd648e5`; the worktree has no `backend/.env`). 4829 passed, 1 skipped; infra, drift-check and frontend-verify green. |
| `make verify` (after the review fixes, on `8d858fca`) | pass | 2026-11-17: 4946 passed, 1 skipped, 71 warnings in 380.37s (0:06:20); infra 133 passed; drift-check OK; frontend 2044 tests, both builds. A run just before it failed on `tests/theory_of_change/test_check_steps.py::test_choose_keeps_the_conditions_rule_and_counts_what_it_skipped`, green alone and outside this slice (the second timing-sensitive theory-of-change test seen under a loaded run; recorded, not fixed here). |
| `make verify` (step-6 exit) | pass | 2026-11-17 on `232bd7a6`: backend 4935 passed, 1 skipped; infra 133 passed; drift-check OK (both documents, the browser smoke); frontend 2027 tests, build and ops build. A first run failed on `tests/theory_of_change/test_progress.py::test_the_automatic_chain_posts_no_draft_landed_line` while the local end-to-end servers ran alongside; the test is outside this slice, untouched by it, and green alone and on the rerun (a timing-sensitive test under load; recorded, not fixed here). |
| `make openapi-sync && make drift-check` | pass | 2026-11-17 (Phase 6, and inside the exit verify). |
| `make -C infra test` | pass | 2026-11-17 (Phase 7): 133 passed. |
| `make deploy-build-guard-test` | pass | 2026-11-17 (Phase 9): the build guard, the migration waiter and the new deploy-order harness. |
| `aws sesv2 get-account` (both profiles) | blocked | SSO tokens expired on 2026-11-17; the owner signs in and the build re-runs it. Both accounts had production access on 2026-11-16 (contract fact 1). |

## Checks beyond the build

- **Deterministic tests** — filled per phase below.
- **AI evals** — none; the slice runs no inference.
- **Manual / browser / API** — the staging checks below.

## Staging live checks (contract § Acceptance; Phase 11, with the owner)

| # | Check | When | Result |
|---|---|---|---|
| 1 | Ops-page "create person" sends an invitation from `no-reply@v3.policyatlas.uk`, DKIM pass, person signs in | | pending |
| 2 | Resend sends again; a second resend within the hour is 429 | | pending |
| 3 | A `nesta.org.uk` request gets an invitation within two minutes and shows "invited"; an unlisted address is a plain row with the same form response | | pending |
| 4 | `https://ops.v3.policyatlas.uk` refused from a non-allowlisted address | | pending |
| 5 | Non-ops signed-in person sees "does not have the ops role"; 403 on every ops route; `/api/v1/me` on the ops host is 404; `https://v3.policyatlas.uk/ops` is the public not-found page; public bundle has no ops code | | pending |
| 6 | Deployed task-role policies: no `cognito-idp` on the API's; the five on the ops service's | | pending |
| 7 | Each action above has an `ops_action` row | | pending |
| 8 | Task quota 0 hides the quota band; quota 1 refuses the second task with `task_quota` | | pending |
| 9 | Full-chain smoke: a normal task run completes | | pending |
| 10 | Each rollback (A, B, C) exercised once | | pending |
| 11 | As `pa_ops`: `DELETE FROM app_user` and `SELECT FROM capability_run` refused | | pending |

## End-to-end command

Local, against real servers (an ops-mode server serving the built pages on port 8002, an
api-mode server on port 8003, one `*_test` database), run 2026-11-17 and green:

```
docker compose exec -T db createdb -U policy_atlas policy_atlas_e2e_test
docker compose exec -T db psql -U policy_atlas -d policy_atlas_e2e_test -c "CREATE EXTENSION IF NOT EXISTS vector"
(cd frontend && pnpm build:ops)
DATABASE_URL=postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_e2e_test bash scripts/ops_e2e_local.sh
```

The ops server runs on the `pa_ops` login (set by the master login for the run). It proves, in
order: the ops host answers `/people` with the pages' `index.html`; it has no task routes and
no `/me` (404); an ops route is 401 without a token and 403 with a token and no role; a nested
bundle file is served and the host refuses framing; the refused calls create no `app_user` row; with the role (the row write
`ops grant` makes) the route is 200; an organisation is created, its task quota set to 1 and
the operator moved into it on the ops host; `/me` on the api host then shows limit 1, the
first task is admitted and the second refused with `task_quota`; the people list finds the
operator; `ops_action` holds `org.create, org.quota, person.move` for the actor in order;
the ops server's database login is `pa_ops`; the ops server log carries `ops.action` lines.
The staging checks (contract § Acceptance)
are Phase 11 with the owner and are still pending above.

## Build notes (filled per phase)

- **Executor routing.** Codex ran Phases 1-2, 3, 4, 5, 6, 7, 9 and 10 from the plan's briefs; its sandbox cannot reach Postgres or Docker, so every database-backed test was run by the lead, and the database-backed tests of Phases 4 and 6 were written by Claude agents with database access (a deviation from the plan's `codex` marks, justified by the sandbox). The frontend (Phase 8) went to the `frontend-designer` agent as planned.
- **Phase 3 gate.** The first full run failed on 26 tests, all cascading from one cause: the 064a index test stamps the version back without downgrading the new revision, so a worker's database kept 065's objects under an older stamp. The test now steps down to its own revision first. Table counts moved from 52 to 54.
- **Phase 4 deviation (minor, flagged).** The resolver keeps the owner's 064a ruling that administrators are exempt from the run cap as well as the task quota (contract § Terms names only the task quota; the 064a review of 2026-11-16 added the run cap). `tests/api/test_runs_router.py::test_an_administrator_has_no_run_cap` still holds.
- **Phase 7.** `docker build backend/` succeeded without `backend/ops-ui/` and, with a stub bundle present, the image listed `/app/ops-ui/index.html` and `/app/ops-ui/assets/app-abc.js` (2026-11-17). The plan's image test is a text pin on the Dockerfile; the live build is this record.
- **Phase 9.** The deploy script skips the ops bundle build on a bootstrap (no OIDC exports exist before the first deploy) and builds it on every update.

## Diff summary

Twelve commits on `task/065-accounts` after the design-phase exit, one per plan phase
(Phases 5 and 6 together). What changed and why:

- **A. Email (Phases 1-2).** `infra/infra/cognito_auth.py` takes the `email` block from
  `pa_config.json`; with `enabled` true the pool sends through the environment's own SES
  identity (ARN built in the pool's account and region; nothing creates an identity) and
  carries the invitation and verification templates from `infra/email/` with the sign-in
  and logo URLs substituted at synth. `enabled` is false in both environments today.
  The logo PNG is the fold mark under `frontend/public/brand/`.
- **B. Schema (Phase 3).** Migration `c6d4e2f1a9b8`: `app_user.is_ops`, `invited_at`, the
  four quota overrides with `CHECK (>= 0)`, `ops_action`, `organisation_domain`, the two
  waitlist stamp columns, the `pa_ops` role with exactly the B13 grants, and the trigger
  that refuses the ops login setting `is_admin` or `is_ops` to true.
- **B. Commands and resolver (Phase 4).** `ensure_account_enrolled`, `resend_invitation`,
  `move_user`, `set_ops`, `set_quota`, `add_domain`, `remove_domain`, `record_action`,
  `approve_request`; de-enrol and offboard clear `is_ops`; new CLI commands. `effective_limits`
  is the one reader of the override columns; task create, every run-cap site and `/me` call
  it. The Cognito type stubs moved under `TYPE_CHECKING` (B5).
- **B. Ops mode and routes (Phases 5-6).** `POLICY_ATLAS_SERVICE_ROLE=ops` selects a lifespan
  with no executor, sweep, drainer or ingest consumer; the ops router (thin routes, one
  command, one audit row in the transaction, one log line after commit; savepoint per bulk
  subject); the pages' static fallback; the ops OpenAPI document and its generated types.
- **B. Infrastructure and image (Phase 7).** The ops service, its secret, the allowlisted
  listener rules, the A record, the five Cognito actions on the ops task role only, the
  migration task's sync step, SSM exports; the Dockerfile copies `backend/ops-ui/`.
- **B. Pages (Phase 8).** `frontend/ops.html`, `vite.ops.config.ts`, `src/ops/` (shell, five
  views, mock, tests), `pnpm build:ops` into `backend/ops-ui/`; the public bundle has no ops
  code (a test pins it).
- **B. Deploy (Phase 9).** `ops/db_role.py` and the `deploy.sh` order (plan § Deploy order).
- **C. Sweep (Phase 10).** `ops/sweep.py`.
- **Docs (Phase 12).** `docs/deferred.md`, `web-api.md`, `infra/DEPLOYMENT.md`.

**Deviations, all minor and flagged:**

- Administrators are exempt from the run cap as well as the task quota in the resolver
  (the 064a ruling; contract § Terms names only the task quota).
- The plan's `tests/scripts` image test is a text pin on the Dockerfile plus the recorded
  manual build (Phase 7 note above), not a Docker build inside the suite.
- Plan P2's `VITE_API_BASE_URL=/api` for the ops build is not used: the ops client always
  calls the page's own origin, and the generated paths already carry `/api/v1`, so the deploy
  script sets no base for that build.
- The ops bundle is built by `scripts/deploy.sh` (plan P1), not a Node stage in the
  Dockerfile (contract B3's wording); the outcome is the same and the plan recorded it.
- The database-backed tests of Phases 4 and 6 were written by Claude agents, not Codex
  (its sandbox cannot reach Postgres); the plan's routing is otherwise followed.
- `test_migration_064a_ssr_index.py` steps down to its own revision before stamping, because
  a revision now follows it. Table-count pins moved from 52 to 54.
- The web "enrol or move" calls a new `move_user` (the person's row is addressed by subject,
  so no Cognito lookup is needed) rather than `enrol_user`, which B4 names. § Terms said
  "one function is added"; the build adds `ensure_account_enrolled`, `resend_invitation`,
  `approve_request`, `move_user`, `set_ops`, `set_quota`, `add_domain`, `remove_domain` and
  `record_action`, all listed in the Phase 4 and 6 commits.
- After the review stack: `pa_ops` holds no INSERT on `organisation_domain` or
  `waitlist_entry` (narrower than B13's wording; nothing inserts there from the ops host),
  and the trigger guards INSERT as well as UPDATE. The CLI's quota commands write an
  `ops_action` row (rubric 22 read literally), with the operator's verified AWS principal as
  the actor. "Only the resolver reads the override columns" (rubric 22) is read as "no
  limit decision outside the resolver"; the ops-host list projections display the columns.
- One 064a test was removed with reason: `test_admit_and_mint_fails_loudly_without_a_user_cap`
  pinned a guard that treated a missing cap as a wiring error; 065 makes `None` a value (no
  cap), and the guard gave an administrator a 500. Its replacement is
  `test_an_administrator_with_no_run_cap_confirms_a_baseline`.

## Review findings

Step 7 ran in this session on fresh lanes (owner's decision, 2026-11-17). Codex's
workspace was out of credits, so the adversarial lane ran on a fresh Claude reasoning agent;
a family-diverse Codex pass is pending a refill (recorded under Known unverified items).

- **Security lane** (fresh agent, OWASP sweep): no critical or high. Adopted: M1 a
  request the sweep can never fulfil is now terminal (`refused`) instead of retried every
  minute, and failed attempts count against the hourly budget; M2 (the safe half) an
  existing account is enrolled without its stored name being overwritten; L1 the privilege
  trigger also guards INSERT; L2 the Requests page no longer puts an address in the page
  URL; L3 an address with `<`, `>`, `&` or whitespace is refused before Cognito; L4 the
  create-person route lower-cases and shape-checks the address; L5 a bulk failure shows a
  generic message unless it is a refusal; I4 the ops host now serves files under the
  bundle's sub-folders (fonts). Accepted and recorded: M3 the abuse ceiling as the ADR
  states it (owner may lower `max_per_hour` on production); I2 one Cognito client serves
  both hosts; I3 an ops-role holder can offboard the last operator (recovery is the CLI;
  noted in the pages' script); I5 no password rotation. Escalated to the owner: M2's other
  half, whether sweep-created accounts should take the form's name at all (contract C3 says
  yes; see § Owner decisions).
- **Adversarial review** (fresh agent): 1 blocker, 4 major, 9 minor. Adopted: (1) the
  longlist admission guard that raised on a missing cap is gone, with a test for an
  administrator and a cap of 0; (2) the INSERT trigger (convergent with L1); (3) the
  no-rename fix (convergent with M2); (4) terminal refusals and the budget counting
  failures (convergent with M1); (5) the deploy order: the login sync no longer fails the
  migration task, the secret gate and the ops start run after the API is up and the public
  frontend is published; (6) convergent with L4, plus Cognito refusals on create and
  approve map to 409 `ops_refused`; (7) both quota fields are required (nullable) so a
  missing field cannot clear an override; (8) convergent with L2; (10) the task-role synth
  test handles a single-string Action and a `*`, and the local end-to-end run now serves
  the ops routes as `pa_ops`; (11) `pa_ops` loses the two INSERT grants no code uses
  (`organisation_domain`, `waitlist_entry`); (12) the downgrade sets NOLOGIN before the
  drop; (14) the ops build unsets `VITE_MOCK`, a bootstrap starts from an empty bundle
  directory, bulk actions act on visible ticked rows only. Recorded in ADR 0046's
  consequences, not changed: (9) Cognito calls happen before the commit, so a rolled-back
  write can leave a sent email or a disabled account with a `failed` row; (12) the
  password travels in `ALTER ROLE` as a literal; (13) the sweep assumes one ops instance
  (`desired_count` is 0 or 1 by the deploy script). (15) stale cap reads outside the lock
  are harmless.
- **Design lane** (`frontend-designer`, read-only, with screenshots): six material fixes
  adopted (empty states, the missing organisation error line, Cancel in the bulk quota
  dialog, focus return on dialog close, `aria-describedby` on help and warnings, fixed
  column widths), eleven polish items adopted, six wording rulings adopted, six items
  declined and recorded in the pages' script. The fixes landed in the agent polish round
  (ops tests 35 → 52); screenshots of the changed pages at 1280 and 400 are in the session
  scratchpad (`ops-shots/r3/`). The **owner pass** of the second polish round is pending:
  the owner looks at the pages on staging in Phase 11.
- **Fixes applied, then re-verified:** every adopted item above is in the tree; the slice
  suites (341 backend tests across the slice's modules), the infra suite, the deploy
  harness, the local end-to-end run (now serving the ops routes as `pa_ops`, and checking a
  nested bundle file and the framing header) and the full `make verify` ran green after
  them (see § Commands run). No fix relaxed, skipped or deleted a test except the one
  recorded in § Diff summary.
- **Contract verifier** (fresh agent, ran drift-check, the infra suite and 306 slice tests):
  twelve findings. Adopted: 1 the INSERT trigger (convergent, three lanes); 2 the ops
  service's `desired_count` is now template-pinned at 0 like the API's, and the deploy script
  scales it last; 3 convergent with L4 and adversarial 6; 4 convergent with M1; 5 the three
  stale document sentences (the SES entry said "discharged" while `email.enabled` is false,
  the waitlist spec still said no auto-promote, "accounts" where the cap counts invitations);
  7 the grants are now read back from the catalogue and compared to the list, the downgrade
  sets NOLOGIN before the drop, the resend runs as `pa_ops` in the positive test, and the
  migration test no longer asserts a cluster-wide property another worker can change; 8 the
  task-role test pins the pool-ARN scope and catches a shared policy; 9 and 11 recorded as
  deviations and in ADR 0046's amendment; 12 the ops container carries the quota and pool
  settings, `require_cognito` is gone, the ops engine hides parameters, the ops host refuses
  framing. Rulings: 6 the reader rule means no limit decision outside the resolver (display
  reads on the ops host are fine), and the CLI's quota commands now write an audit row; 10
  convergent with the design lane; 12's "half-run tick" and bundle test are accepted as
  documented. Its per-item table at the time (items 1, 11, 13, 14, 22, 23 "partly") is
  superseded by the fixes above; the rubric status below is after them.
- **`/code-review` (medium, 15 findings):** adopted: the template desired count (convergent),
  the lower-cased address (convergent), the INSERT trigger (convergent), a Check row's note
  takes the first of two rows sharing an address instead of raising, an operator cannot
  de-enrol or offboard their own account from a bulk action, the ops container's quota
  settings (convergent), `inferDefaults` excludes administrators for the run default, the
  fallback serves nested bundle files (convergent), endless sweep retries (convergent), typed
  `NotFound` refusals instead of message-prefix matching, the 365-day predicate shared with
  the quota, a quota field that is not a whole number is refused instead of cleared, the
  sync logs the error class, the sweep reads the domain the way the SQL filter does.
  Declined with reason: the per-person `effective_limits` query in the people list (one
  query per row, under a hundred rows, the plan accepted it). A first run was pointed at
  the wrong HEAD (the main checkout's 064b branch) and its eight findings are not this
  slice's; discarded.
- **`/simplify`:** not run; the code review's cleanup angles and the adjudication above
  cover it, and a second same-family pass adds nothing.

## Owner decisions raised by the stack

1. **Sweep-created accounts and the form's name (security M2, adversarial 3).** Contract C3
   enrols an existing unenrolled account and creates a new one with the waitlist row's name.
   The stack showed that anyone can type a colleague's address with any name: the name is
   now never written onto an existing account (fixed), but a new account still takes the
   form's name, and a de-enrolled person is re-enrolled by a stranger's request. Options:
   (a) keep C3 as written (the organisation is right by domain; an operator can rename from
   the CLI); (b) derive the name from the address and keep the form's name on the waitlist
   row for the operator; (c) leave any address that already has an account for an operator
   (`check`), creating only new ones. Recommendation: (b) for new accounts and (a)'s
   auto-enrol kept, because de-enrol is not a lockout (offboard is) and the person can be
   renamed. Until the owner rules, the code does (a) with the no-rename fix.
   **Owner ruling (2026-11-18): (a).** A new account takes the name typed on the form. The
   code already does this; nothing changed.
2. **`max_per_hour` on production** (security M3): 20 is the contract's default; the
   security lane suggests 5 for the first weeks. Config only. **Owner ruling (2026-11-18):
   5 on production** (`infra/pa_config.json`); staging keeps 20.

## Owner pass 1 on the ops pages (2026-11-18)

The owner looked at the pages on the local ops server. Changes, with the rulings in
`ops-pages-copy.md` § Owner pass 1:

- Copy: Add a person's help line and sender address removed, two sentences reworded; the
  quota side panel is "Currently applied limits" with "<label>: <facts>" rows.
- The organisation picker is a search popover that can create an organisation (all forms).
- A failed load or action says what failed ("Could not load the organisations.") with an
  inline "Try again" link; the second, separate button is gone.
- "Ops" beside the wordmark is set in the wordmark's type, not a chip.
- **Removed: "Move a task or project to another organisation"** and everything built only
  for it: the `POST /api/v1/ops/rows/assign` route, its contract models (`RowAssign`,
  `AssignmentOut`), the panel, its mock and tests, and the `pa_ops` grant on
  `task.updated_at` (only that route wrote it). The CLI `rows assign` command stays
  (it runs on the master login). This narrows contract B6 and B13: a flagged deviation by
  owner ruling.

## Rubric status

After the review stack and its fixes (2026-11-17):

| # | Status |
|---|---|
| 1 | Holds for A1-A5, B1-B13, C1-C6 on the tests, the end-to-end run and the stack's fixes; the staging-only parts of A2, B3 and C3 are in item 2 |
| 2 | `make verify`, `openapi-sync`, `drift-check` and the infra suite pass; the eleven staging checks are pending (Phase 11, with the owner) |
| 3 | Holds: nothing gated changed beyond § Constraints |
| 4 | Holds: no range, password or real person in the diff or the quoted logs; the pages' mock uses fictional people at the real domains, gated behind `VITE_MOCK` and absent from the bundle |
| 5 | Holds: one test removed with reason (§ Diff summary); pins changed are justified there |
| 6 | Holds: this record |
| 7 | Holds: `docs/deferred.md` updated; knowledge records are step 8's |
| 8 | Holds, with one gap: the adversarial lane ran on Claude because Codex's workspace is out of credits; a Codex pass follows when credits return |
| 9 | Holds (synth tests) |
| 10 | Holds apart from the owner's browser review of the two templates (pending) |
| 11 | Holds: no HTTP writer; INSERT and UPDATE refused by the trigger; closed reader list; trace; offboard clears it |
| 12 | Holds (route-table and patched-lifespan tests) |
| 13 | Holds: both task roles synth-pinned with the pool-ARN scope; listener rules; the deploy order with both services stopped; the ops service template-pinned at 0; the image proved by a build |
| 14 | Holds (route tests; one audit row and one line per write; 429 inside the hour; no row from a non-ops token; the address lower-cased) |
| 15 | Holds |
| 16 | Holds (second entry, own shell, generated types, both documents in drift-check, the no-role state, bulk actions with one row each, the two typed confirmations) |
| 17 | Holds; ADR 0046 amended today with the stack's consequences |
| 18 | Holds |
| 19 | Holds; a request the sweep can never fulfil is terminal (refused) rather than retried |
| 20 | Holds; the ceiling now counts failed attempts too, and the ADR says so |
| 21 | Pending (staging, Phase 11) |
| 22 | Holds; the reader rule read as "no limit decision outside the resolver"; the CLI writes an audit row |
| 23 | Holds locally (the exact grant pin from the catalogue, the login test, the sync, the deploy order); the staging half (check 11) pending |

## Intent & assumptions

- The ops pages' copy is the lead's script (`ops-pages-copy.md`) with the build rulings
  appended; the owner has not yet reviewed the email templates in a browser (A2) or the
  pages on staging.
- `email.enabled`, `ops.desired_count` and `self_signup.enabled` are off in both
  environments until the owner switches them on staging (Phase 11).
- The ops allowlist parameter `/policy_atlas_v3/ops/allowed_cidrs` must exist before the
  first deploy of this branch; the deploy guide says how.

## Known unverified items

- Everything in the staging table above, including DKIM on a real message, the deployed
  task-role policies, the allowlist from outside, the rollbacks and the `pa_ops` refusals over
  the real secret.
- `aws sesv2 get-account` on both profiles (SSO sign-in needed).
- A Codex adversarial pass (workspace out of credits on 2026-11-17).
- The owner's pass of the second polish round, on staging.
- `shellcheck` is not installed on this machine; `bash -n` and the two deploy harnesses ran.
- The frontend-designer agent's craft skills named in its definition are not installed on
  this machine; it worked from the `frontend-design` plugin skill, `DESIGN.md` and `PRODUCT.md`.

## Public safety

No address range, password, email address or account id is in the committed diff or in
the logs quoted here. The test addresses are `example.test` or UUID-suffixed. The deploy
script and the sync log names and counts, never values. Screenshots of the mock live only in
the session scratchpad.

## Review handoff (step-7/8 inputs)

- **Executor provenance (family flip):** Codex wrote Phases 1-2, 3, 5, 6, 7, 9, 10 and the
  Phase 4 product code; Claude agents wrote the Phase 4 and 6 database tests, the Phase 8
  pages and the Phase 12 docs; the lead wrote the contract models, the email copy, the pages
  script, the e2e script and the fixes named in the build notes.
- **Adjudication items:** the five deviations in the diff summary; the agent's note that
  `DESIGN.md` has no red button, orange chip tone or relative dates and the ops pages use
  all three on the script's authority.
- **Diff scoping:** `frontend/openapi-ops.json` and `src/api/gen/types-ops.ts` are generated.
- **Knowledge candidates:**
  - A test that stamps Alembic back without downgrading breaks every later migration test
    on that worker once a newer revision exists; step down to the revision first.
  - Codex's sandbox cannot reach Postgres or Docker: brief it for code and typecheck/lint,
    and give database-backed tests to an agent that can run them.
  - Tests that commit fixed subjects or addresses collide on a kept database and on a
    shared worker; UUID-suffix them, and give a module that reads a whole table (the
    sweep) its own listed domain and an autouse cleanup.
  - The Cognito `UserInvitationConfig` and `UserVerificationConfig` render only with the
    SES sender in CDK; the default sender keeps CDK's built-in verification template.
  - A FastAPI yield dependency declared before `get_conn` tears down after it, which is
    how a log line can be emitted only after the commit.
  - `str(engine.url)` hides the password; use `render_as_string(hide_password=False)`.
  - The worktree has no `backend/.env`; run make targets with
    `COMPOSE_PROJECT_NAME=policy_atlas` so docker compose finds the shared database.
  - Postgres collation ignores spaces at the first level, so an `ORDER BY display_name`
    is not Python's `sorted`.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md): self-signup domains beyond
`nesta.org.uk`, the domain table on the ops pages, application-sent email, the ops action
log on the pages. Not in this slice, noted by the build: a single-person read route, the
settings defaults reported by a route (the pages infer "default · n" from a person with no
override), an assign route that accepts either kind of id, `action_id` on the single-object
responses, and the revision-2 explainer's cohorts and feature control (a later task).
