# Verification: 065-accounts

Evidence for the accounts programme (steps A, B, C). Build opened 2026-11-17 in the
worktree on `task/065-accounts`; the build and the review stack run in the same session by
the owner's decision (2026-11-17), with the review lanes as fresh agents. Public-safe: no
address ranges, passwords, email addresses or account ids.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline) | pass | 2026-11-17, after rebasing onto 064a head `1182bb11` (the first run failed on `test_healthz_is_async_so_it_needs_no_pool_thread`, which 064a fixed in `2cd648e5`; the worktree has no `backend/.env`). 4829 passed, 1 skipped; infra, drift-check and frontend-verify green. |
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

It proves, in order: the ops host answers `/people` with the pages' `index.html`; it has no
task routes and no `/me` (404); an ops route is 401 without a token and 403 with a token and
no role, and the refused calls create no `app_user` row; with the role (the row write
`ops grant` makes) the route is 200; an organisation is created, its task quota set to 1 and
the operator moved into it on the ops host; `/me` on the api host then shows limit 1, the
first task is admitted and the second refused with `task_quota`; the people list finds the
operator; `ops_action` holds `org.create, org.quota, person.move` for the actor in order;
the ops server log carries `ops.action` lines. The staging checks (contract § Acceptance)
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

## Review findings

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review** (Tier 4):
- **`/simplify`:**

## Rubric status

Filled after the review stack (step 7). Before it: items 1-7, 9-20, 22, 23 hold on the
tests and the local end-to-end run above; items 2 (the staging checks), 8 (the review
stack), 10 (the owner's copy review), 21 (the rollbacks on staging) and the staging half of
23 are pending.

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
