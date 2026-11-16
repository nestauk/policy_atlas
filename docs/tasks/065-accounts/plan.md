# Implementation plan: 065-accounts

> Status: **draft 1, awaiting the plan-stage adversarial review and the owner's plan gate.**
> Contract: [contract.md](contract.md) revision 3, approved 2026-11-16 (B13 included). Rubric:
> [rubric.md](rubric.md), 23 items. ADR 0046 is written at step 4, after this gate. Terms,
> items (A1 to C6, B12, B13) and the eleven live checks are defined in the contract and not
> restated here. Executor routing follows `docs/agentic-ops/harness.md` § Agent-side model
> routing: judgment-bearing build work to `codex` from a machine-verifiable brief, mechanical
> volume to `fast-worker`, frontend to `frontend-designer`, copy and seam design to the lead.
> The build runs in a fresh conversation with task-cycle-build, opening on Phase 0.

## Context

Three deployable steps, each with its own switch, built in the order they must land
(contract § Goal, § Constraints "Ordering"):

| Step | Switch | What the user sees after it | Phases |
|---|---|---|---|
| A. Email through SES, on brand | `email.enabled` | invitations and resets arrive from `no-reply@` our domain, in our template | 1, 2 |
| B. Ops service and pages | `ops.desired_count` | operators manage accounts, organisations, quotas and requests at `https://ops.<domain>` | 3 to 9 |
| C. Self-signup for `nesta.org.uk` | `self_signup.enabled` | a Nesta address on the request form gets an invitation within two minutes | 10 |

Phase order inside B: schema first (3), then the commands and the resolver that both the CLI
and the routes call (4), then the ops-mode application (5), then the routes and their
OpenAPI document (6), then infrastructure and image (7), then the ops pages (8), then the
deploy script and the database login (9). Each phase ends with its tests green, so the next
phase builds on verified seams. C comes last because the sweep lives in the ops service and
calls the ensure-account command.

The worktree branches from `dev`, which does not yet carry 064a. Two things wait for the 064a
merge and are done at the PR, not before: the migration chain rebase (B8) and the
`user offboard` route and bulk action (B4, B6), which call 064a's `offboard_user`. Until then
the offboard route is built against the command's signature on the 064a branch and its test
is marked to run once the merge lands (P12).

## Decisions taken in this plan

- **P1. The ops bundle is built by `scripts/deploy.sh`, not inside the Dockerfile.** The image
  is a CDK `DockerImageAsset` with `backend/` as its build context, so the frontend sources are
  not in the context, and the deploy script already builds the public bundle with the same
  `VITE_*` values. The script runs `pnpm build:ops` into `backend/ops-ui/` (gitignored) before
  `cdk deploy`, and the Dockerfile copies `ops-ui/` into the image at `/app/ops-ui`. A deploy
  gate check fails when the directory is absent, and the Dockerfile copies it from a stage so
  a local image build without the bundle still succeeds with an empty directory. *This refines
  B3's "Node build stage" wording to the same outcome with no Node toolchain in the image
  build; flagged for the plan gate as a minor contract refinement.*
- **P2. The ops bundle's API base is same-origin.** `VITE_API_BASE_URL=/api` for the ops build;
  the ops app serves `/api/v1/ops/*` and the pages from one origin, so no cross-origin call
  and no second base-URL variable (B3, B6).
- **P3. One frontend project, a second entry.** `frontend/ops.html` → `src/ops/main.tsx` reuses
  `AuthProvider`, the generated client shape, `ui/brand` and the Tailwind theme; the ops
  router and views live under `src/ops/`. `pnpm build:ops` is `vite build --config
  vite.ops.config.ts` with `build.outDir = dist-ops` and the `ops.html` input; the public
  `pnpm build` is untouched. Vitest covers `src/ops/` in the existing run.
- **P4. The ops database secret carries a full connection string, like the master secret.** CDK
  creates `policy_atlas_v3/ops_db` with a generated `password` and the template
  `{"username": "pa_ops"}`. The deploy step `python -m policy_atlas.ops db-role sync`, run by
  the migration task with the master login, (1) sets `LOGIN` and the password on `pa_ops`,
  (2) composes the ops URL from the master URL's host and database with the `pa_ops`
  credentials, and (3) writes it to the secret's `db_connection_string` field. The ops task's
  `DATABASE_URL` is `ecs.Secret.from_secrets_manager(ops_db_secret, field=
  "db_connection_string")`, the same shape as the API's, so `settings.py` is unchanged. The
  migration task role gets `secretsmanager:GetSecretValue` and `PutSecretValue` on that one
  secret (synth-pinned). Order holds because the deploy script runs the sync before it starts
  the ops service (B13; § Deploy order).
- **P5. The `pa_ops` grant list is what the command functions do today, no wider.** Read from
  `ops/commands.py` (064a branch): `SELECT, INSERT, UPDATE` on `app_user`, `organisation`,
  `organisation_domain`, `waitlist_entry`; `SELECT, INSERT` on `ops_action`; `SELECT` and
  `UPDATE (org_id, visibility, is_public, updated_at)` on `task`; `SELECT` and `UPDATE
  (org_id, visibility)` on `project`; `SELECT, DELETE` on `project_membership` (the
  cross-owner severing in `_sever_cross_owner_memberships`). `SELECT` on `capability_run` is
  **not** granted: the run-cap check (064a Q7) runs on the API only, and the ops people list
  shows tasks created in the last 365 days (a `task` read), not runs in progress. *B13's text
  says "no `DELETE` anywhere" and "`UPDATE (org_id)`"; the commands already delete membership
  rows and update three more columns, so the grant follows the code. Flagged for the plan
  gate as a contract correction; the contract's intent (nothing beyond what the ops writes
  need) holds.*
- **P6. The grant list is pinned by a test, not by prose.** A test in `tests/ops/` runs the
  migration, then `SET ROLE pa_ops` on a connection and asserts: every ops write in the
  conformance suite succeeds; `DELETE FROM app_user`, `DELETE FROM task`, `SELECT FROM
  capability_run` and `UPDATE task SET title` are refused with `InsufficientPrivilege`. The
  test database user is a superuser (compose), so `SET ROLE` works there; on RDS the master
  user owns the role and the deploy step sets the password.
- **P7. The quota resolver lives beside `tasks_created_since`** in `routers/common.py`:
  `effective_limits(conn, user_id) -> Limits(task_quota: int | None, runs: int | None)`,
  `None` meaning no limit (0 in the column, or admin for the task quota). The three callers
  (task create, run start, `/me`) replace their direct `settings.*` reads with it; the
  settings values become the resolver's defaults. One test module pins the precedence.
- **P8. Ops routes are thin.** Each route resolves its target, opens the transaction, calls
  one command function, inserts the `ops_action` row and logs, in that order, in one helper
  `record_action(conn, actor, action, target, outcome)` used by every route and by the sweep.
  Bulk routes take a list of subjects and loop that helper per subject, collecting outcomes;
  one failure is recorded and the loop continues (B6). The route module is `routers/ops.py`;
  the router is included only when `settings.service_role == "ops"`.
- **P9. Ops mode is a settings field, not a second factory.** `Settings.service_role:
  Literal["api", "ops"]` from `POLICY_ATLAS_SERVICE_ROLE`. `create_app` picks the router set
  and the lifespan from it: `_lifespan` (unchanged) for `api`, a new `_ops_lifespan` that
  builds the engine, the HTTP client and the authenticator, starts the sweep task when the
  flag is on, and shuts them down. The static mount is `StaticFiles(directory=/app/ops-ui,
  html=True)` at `/` with a catch-all that returns `index.html` for non-`/api` paths, added
  only in ops mode and only when the directory exists (tests run without it and assert the
  catch-all from a temporary directory).
- **P10. The sweep is a plain asyncio task** in the ops lifespan: `while True: await
  asyncio.sleep(60); await asyncio.to_thread(sweep_once, engine, cognito, settings)`.
  `sweep_once` is a pure function in `ops/sweep.py` that takes the clock, so the unit tests
  call it directly with a fake Cognito and a fixed clock and never sleep. The hourly cap is a
  count of `ops_action` rows with actor `sweep` and action `invite` in the last hour, so a
  restart does not reset it.
- **P11. The ensure-account command reuses `create_user`'s pieces, not its entry point.**
  `ensure_account_enrolled` calls the existing `_find_sub_by_email`, the Cognito create path
  with `--invite email` semantics, and `_enrol`; it never calls `create_user` itself (whose
  "exists and org given" refusal is the retry case). `create_user` and the CLI are unchanged
  (contract § Terms).
- **P12. Offboard waits for 064a.** The route and the bulk action call `offboard_user` from
  064a. In this worktree the function does not exist, so the route module imports it lazily
  and the conformance test for offboard is skipped with the reason "needs 064a merge" until
  the rebase at the PR, where the skip is removed and the test must pass before the PR opens.
  Everything else in B is independent of 064a.
- **P13. Email copy is written by the lead** in Phase 2 as two HTML files; agents never write
  it. The owner reviews the files in a browser at the Phase 2 gate (A2).
- **P14. Regeneration closes every phase that changes a contract model.** `make openapi-sync`
  then `make drift-check` after Phases 4 (quota on `/me`) and 6 (the ops document); the ops
  document's generation is added to both targets in Phase 6.
- **P15. Codex briefs are one seam each** with a file boundary and a named test command
  (§ Briefs). The build conversation dispatches them one at a time, or in parallel where the
  files do not overlap.
- **P16. Staging is the only live environment this slice touches.** Production receives A
  after the PR merges (its SES is ready); B and C reach production in later deploys, C only
  after 064b (C4). The eleven live checks run on staging from the branch deploy the owner
  triggers, as 057 and 058 did.

## Open for the plan gate

1. **P1** (ops bundle built by the deploy script, copied into the image) and **P5** (the
   grant list follows the code, including `DELETE` on `project_membership`) refine the
   contract's B3 and B13 wording. Recommendation: accept both; the outcomes the contract
   names are unchanged.
2. **Bulk offboard confirmation.** The wireframe confirms a single offboard by typing the
   address. For a bulk offboard, recommendation: type the number of people ("3") instead,
   since typing every address is unworkable.
3. **The ops people list's "Tasks this year" column** reads `task` for every person listed.
   With under a hundred people one query per page load is fine; recommendation: one grouped
   query, no cache, and a `ponytail:` note naming the ceiling.

## Gate map (binding)

| Boundary | Gate | Why |
|---|---|---|
| Build-open | full | baseline (spine) |
| After Phase 1 | infra synth tests + `make verify-fast` | infra only |
| After Phase 2 | fast + owner copy review | files, no code paths |
| After Phase 3 | full | schema (mandatory class) |
| After Phase 4 | full + `drift-check` | commands, resolver, `/me` regeneration |
| After Phase 5 | fast | app factory and lifespan; no schema |
| After Phase 6 | full + `drift-check` | routes; ops OpenAPI document and types |
| After Phase 7 | synth tests + fast | infra and image |
| After Phase 8 | fast per round | frontend surfaces |
| After Phase 9 | fast + `deploy-build-guard-test` | deploy script and db-role |
| After Phase 10 | full | sweep touches schema readers; last backend phase |
| Phase 11 (staging) | the eleven live checks | contract § Acceptance |
| Step-6 exit | full | exit (spine) |

Phases 5 and 7 share no schema or reader contact with their neighbours and gate on fast;
Phase 1 is infra only and gates on the synth tests. Everything else carries a full run.

## Deploy order (binding for Phase 9 and Phase 11)

`scripts/deploy.sh` keeps its stop → migrate → start shape and gains four things, in this
order: (1) gate checks: the ops allowlist parameter (same validator as Metabase's, parameter
name from `pa_config.json`), the ops database secret exists, `backend/ops-ui/` is present;
(2) before `cdk deploy`: `pnpm build:ops` with `VITE_API_BASE_URL=/api` and the same OIDC
values; (3) stop the API **and** the ops service, run migrations, then `db-role sync` in the
same migration task definition with the sync command, then start the API, then the ops
service; (4) the Metabase single-count invariant extends to the ops service. The downgrade
path is the mirror: stop both, downgrade, start. Rollback for each step is the contract's
(§ Constraints) and each is exercised once in Phase 11.

## Phases

### Phase 0 — Build-open
- `make verify` green on `task/065-accounts` (full). Confirm `aws sesv2 get-account` on both
  profiles shows production access (lead, inline, two commands).
- lead: open `verification.md` from the template with the eleven live checks as rows.

### Phase 1 — Pool email through SES (A1, A3, A4)
- codex: `infra/infra/cognito_auth.py` reads the `email` block from `pa_config.json` (four
  keys, `enabled` false in both environments at first) and sets `UserPoolEmail.with_ses(
  ses_region, from_email, from_name, ses_verified_domain)` only when enabled; the SES
  identity ARN is built from the domain in the pool's own account and region; nothing creates
  an identity. Synth tests for both states (A3). Done: `pytest infra/tests` green with the
  new cases; `grep -c SESIdentity infra/` is 0.
- fast-worker: `infra/DEPLOYMENT.md` section per A4, from the lead's bullet list.

### Phase 2 — Branded templates (A2, A3)
- lead: `infra/email/invitation.html`, `infra/email/verification.html` and the two subjects,
  product voice, `{username}` and `{####}` in place, logo at `/brand/email-logo.png`
  (frontend-designer supplies the PNG under `frontend/public/brand/`). Why lead: copy.
- codex: `cognito_auth.py` reads the files at synth and sets `user_invitation` and
  `user_verification` on the pool only with `email.enabled` true; synth tests extend A3
  (placeholders present, absent when disabled). Done: synth green; `email.enabled` flipped
  true in a scratch config renders both templates in the synthesised pool.
- Gate: owner opens the two HTML files and approves the copy (A2).

### Phase 3 — Schema (B1, B4, B11, B12, B13, C1, C2)
- codex: one Alembic migration after the worktree's head (`f9c6e3b8d4a2`), additive:
  `app_user.is_ops`, `app_user.invited_at`, the four quota override columns with
  `CHECK (>= 0)`, `ops_action`, `organisation_domain`, the two `waitlist_entry` columns, the
  `pa_ops` role (idempotent `DO` block, `NOLOGIN`) and the P5 grants; the downgrade reverses
  all of it including `DROP ROLE` (after `REVOKE`). `core/schema.py` tables updated. Done:
  `alembic upgrade head` then `downgrade -1` then `upgrade head` on the test database leaves
  no diff; `make verify` green.
- codex: the P6 privilege test in `tests/ops/test_pa_ops_grants.py` (the positive half is
  completed in Phase 6 when the routes exist; the negative half passes now).

### Phase 4 — Commands, resolver and `/me` (B11 helper, B12, ensure-account, `set_quota`)
- codex: `ops/commands.py` gains `ensure_account_enrolled` (P11) and `set_quota`; `ops/cli.py`
  gains `ops grant|revoke`, `user quota`, `org quota`, `org domain add|remove`, each with the
  post-commit admin trace where the contract says so; `user offboard` clears `is_ops` (a
  one-line change rebased onto 064a at the PR, P12). Unit tests per B9 and B12 for the
  command branches and the Cognito-created-then-database-failed retry. Done: `pytest
  tests/ops` green; `grep -n "def create_user" ops/commands.py` unchanged by diff.
- codex: `routers/common.py` `effective_limits` (P7) and its three callers; `MeOut.task_quota`
  null for no limit; tests for precedence, zero, admin exemption, clearing. Done: `pytest
  tests/api/test_me_router.py tests/api/test_tasks*.py tests/api/test_run*.py` green.
- fast-worker: `ops/environment.py` and `ops/commands.py` move the `mypy_boto3_cognito_idp`
  imports under `TYPE_CHECKING` (B5); a test imports `policy_atlas.ops.commands` with the stub
  package hidden from `sys.modules`. Done: `make typecheck` green; the test passes.
- Gate: full + `make openapi-sync && make drift-check`.

### Phase 5 — Ops mode (B2)
- codex: `Settings.service_role` (P9); `create_app` picks routers and lifespan by it;
  `_ops_lifespan` per P9 with the sweep task hook left as a no-op callable until Phase 10;
  the static mount and catch-all. Tests per B9's route-table rows, the patched-lifespan test
  (executor constructor and `continuation.startup_sweep` never called in ops mode), the
  catch-all from a temporary directory, and `api` mode serving no static file. Done:
  `pytest tests/api/test_service_role.py` green; `make verify-fast` green.

### Phase 6 — Ops routes and the ops OpenAPI document (B4, B7, B9, C5's read)
- lead: the route list and the request and response models in `api/contract/ops.py` (seam
  design: the shapes the page and the types are generated from). Why lead: seam design.
- codex: `routers/ops.py` per P8, every write through `record_action`; the resend route with
  the 429 cooldown on `invited_at`; bulk variants of set-quota, move, resend, de-enrol and
  offboard (offboard per P12); the requests list with the three states (C5); the ops-role
  dependency and the closed reader list for `is_ops` (asserted like 033's `is_admin` list).
  Conformance tests per B9 (401, 403, 200; no `app_user` row from a non-ops token; one
  `ops_action` row per write and per bulk subject; the loop continues past a failure).
  Done: `pytest tests/api/test_ops_router.py tests/api/test_api_conformance.py` green.
- codex: `export_openapi.py --mode ops` writing `frontend/openapi-ops.json`; `package.json`
  `gen:ops` → `src/api/gen/types-ops.ts`; `make openapi-sync` and `make drift-check` cover
  both; the public document asserted to contain no `/api/v1/ops` path. Done: `make
  openapi-sync && make drift-check` clean; a test asserts the public document has no ops path.
- codex: complete the positive half of the P6 grant test by running the ops conformance
  writes as `pa_ops`. Done: the test is green both halves.
- Gate: full + `drift-check`.

### Phase 7 — Infrastructure and image (B3, B13 secret)
- codex: `policy_atlas_stack.py` ops service per B3 following the Metabase block (task
  definition with the ops environment and the ops database secret, service with
  `desired_count` 0, target group, listener rules on host header plus source addresses from
  the new SSM parameter via `metabase_allowlist.py` given the parameter name, A record), the
  ops task role's five Cognito actions scoped to the pool, the migration task role's two
  Secrets Manager actions on the ops secret (P4), the ops `APP_ORIGIN`, and the callback and
  logout URLs in `cognito_auth.py`. `pa_config.json` `ops` and `self_signup` blocks for both
  environments. Synth tests: both task roles (no `cognito-idp` on the API's; exactly five on
  the ops'), the listener rule shape, the callback URLs, the ops `APP_ORIGIN`, the secret
  template. Done: `pytest infra/tests` green; `cdk synth` for both environments succeeds.
- fast-worker: `backend/Dockerfile` copies `ops-ui/` into `/app/ops-ui` through a stage that
  tolerates its absence (P1); `backend/.dockerignore` keeps `ops-ui/` in; `.gitignore` adds
  `backend/ops-ui/`. Done: `docker build backend/` succeeds with and without the directory.
- Gate: synth tests + fast.

### Phase 8 — Ops pages (B6, B12 forms, C5)
- lead: the section list, the states and every line of copy for the ops pages, from the
  owner's explainer and wireframes (People with multi-select, Add a person, Set a quota with
  the "Simultaneous tasks" warning, Requests with three states, Organisations with the move
  panel, offboard confirmation by typing). Why lead: copy and direction.
- frontend-designer: `frontend/ops.html`, `vite.ops.config.ts`, `src/ops/` (router, shell,
  the five views, the confirmation dialog, the "does not have the ops role" state on a 403),
  using `types-ops.ts`, the shared auth provider and `ui/brand`; `pnpm build:ops`; vitest for
  each view's states against a mock of the ops routes (`src/ops/mock`). Done: `pnpm test` and
  `pnpm build:ops` green; `pnpm build` output unchanged (no ops chunk in `dist/`).
- frontend-designer: one polish pass per task-cycle-build § Step 5b after the lead's review.
- Gate: fast per round.

### Phase 9 — Deploy script and the database login (B3, B13, § Deploy order)
- codex: `ops/db_role.py` and the CLI command `db-role sync` (P4: `ALTER ROLE ... LOGIN
  PASSWORD`, compose the URL, `PutSecretValue`); a unit test with a fake Secrets Manager and
  the test database. `scripts/deploy.sh` per § Deploy order, with the ops allowlist parameter
  check mirroring `check_metabase_allowlist_parameter`, the secret check, the bundle check,
  the `build:ops` step, the stop-both-then-start-API-then-ops sequence and the single-count
  invariant; `tests/scripts` extended (the `deploy-build-guard-test` target). Done: `make
  deploy-build-guard-test` green; `shellcheck scripts/deploy.sh` clean.
- Gate: fast + `deploy-build-guard-test`.

### Phase 10 — Sweep (C3, C4, C6)
- codex: `ops/sweep.py` `sweep_once` per P10 and the lifespan hook; the domain match (exact,
  lower-cased, no subdomain); stamping; the hourly cap from `ops_action`; the three
  ensure-account outcomes; retry on failure; actor `sweep` rows. Unit tests per C6 with a
  fake Cognito and a fixed clock. Conformance: the public waitlist response byte-identical
  for a listed and an unlisted domain. Done: `pytest tests/ops/test_sweep.py
  tests/api/test_waitlist*.py` green; the flag-false test asserts the task is never created.
- Gate: full.

### Phase 11 — Staging and the live checks (contract § Acceptance, § Constraints "Rollback")
- lead with the owner: the allowlist parameter and the Nesta organisation and domain row on
  staging (addresses and names never committed); the owner triggers the branch deploy;
  `email.enabled` true, `ops.desired_count` 1, `self_signup.enabled` true on staging only.
  The eleven checks, each with a timestamp in `verification.md`; the invitation's
  `Authentication-Results` header with the address redacted; the deployed task-role policies
  for both services; `psql` as `pa_ops` for check (11). Then each rollback once (A, B, C) and
  the re-enable. Why lead: live operations with the owner.

### Phase 12 — Docs and exit
- fast-worker: `docs/deferred.md` (SES entry discharged; admin-surface entry reopened; new
  seams: domains beyond `nesta.org.uk`, the domain table on the ops pages, application-sent
  email, the ops action log on the ops pages); `web-api.md` § Auth boundary and § Waitlist
  additive paragraphs; `infra/DEPLOYMENT.md` ops section (the allowlist parameter, the
  secret, the ops address, the first ops grant).
- lead: ADR 0046 status Accepted with the date (drafted at step 4, confirmed here);
  `verification.md` complete; step-6 exit full verify.

## Briefs (one seam each; the build conversation fills the file list from the phase)

Each Codex brief states: read-only context files, the files it may change, the contract ids,
the done command, and "do not edit `dev`'s migrations, generated files or `create_user`".
Frontend briefs go to `frontend-designer` with the lead's copy attached and `DESIGN.md`
named. No brief writes user-facing copy or email copy.

## What the plan does not do

- No change to the public bundle beyond `frontend/public/brand/email-logo.png` (A2).
- No production deploy of B or C in this slice (P16).
- No edit of the domain table from the ops pages, no second domain, no MFA, nothing in the
  contract's Out list.
