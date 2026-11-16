# Implementation plan: 065-accounts

> Status: **draft 2, awaiting the owner's plan gate.** Draft 1 was reviewed read-only by the
> Codex lane on 2026-11-16 (12 findings: 3 blockers, 8 material, 1 minor; the record stays
> local under `research/`); every finding is folded here (§ Folded findings). Contract:
> [contract.md](contract.md) revision 3, approved 2026-11-16, with the revision 3.1 amendments
> to B1, B6 and B13 that this review produced and that the owner confirms at this gate.
> Rubric: [rubric.md](rubric.md), 23 items. ADR 0046 is written at step 4, after this gate.
> Terms, items (A1 to A4, B1 to B13, C1 to C6) and the eleven live checks are defined in the
> contract and not restated here. Executor routing follows `docs/agentic-ops/harness.md`
> § Agent-side model routing: judgment-bearing build work to `codex` from a machine-verifiable
> brief, mechanical volume to `fast-worker`, frontend to `frontend-designer`, copy and seam
> design to the lead. The build runs in a fresh conversation with task-cycle-build, opening
> on Phase 0.

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

**Base branch.** `task/065-accounts` was rebased onto `task/064a-security-quick-wins` on
2026-11-16 (finding 1), so 064a's `offboard_user`, `user_at_run_cap` and
`tasks_created_since` are present and the migration chain already follows 064a's. The PR
opens after 064a merges to `dev`, with one more rebase then (B8).

## Decisions taken in this plan

- **P1. The ops bundle is built by `scripts/deploy.sh`, not inside the Dockerfile.** The image
  is a CDK `DockerImageAsset` with `backend/` as its build context, so the frontend sources are
  not in the context, and the deploy script already builds the public bundle with the same
  `VITE_*` values. The script runs `pnpm build:ops` before `cdk deploy`; the ops Vite config
  writes straight to `../backend/ops-ui/` (`build.outDir`, `emptyOutDir: true`; gitignored),
  and the Dockerfile copies `ops-ui/` into the image at `/app/ops-ui` through a stage that
  tolerates its absence, so a local image build still succeeds. A deploy gate check fails
  when `backend/ops-ui/index.html` is absent, and `tests/scripts` asserts the built image
  contains `index.html` and the hashed assets (finding 12). *Refines B3's "Node build stage"
  wording to the same outcome with no Node toolchain in the image build.*
- **P2. The ops bundle's API base is same-origin.** `VITE_API_BASE_URL=/api` for the ops build;
  the ops app serves `/api/v1/ops/*` and the pages from one origin, so no cross-origin call
  and no second base-URL variable (B3, B6). The other `VITE_*` values (OIDC authority and
  client id) are the ones the deploy script already exports for the public build.
- **P3. One frontend project, a second entry.** `frontend/ops.html` → `src/ops/main.tsx` reuses
  `AuthProvider`, the generated client shape, `ui/brand` and the Tailwind theme; the ops
  router and views live under `src/ops/`. `vite.ops.config.ts` imports the base config and
  overrides only `build.rollupOptions.input` (`ops.html`) and `build.outDir` (P1), so the
  React compiler and Tailwind plugins are the same objects; `pnpm build:ops` is `tsc -b &&
  vite build --config vite.ops.config.ts`, and `tsconfig.app.json` already includes `src/`,
  so `src/ops/` type-checks in the same build. Vitest's include glob covers `src/ops/` with
  no config change; the public `pnpm build` and `dist/` are untouched (a test asserts no
  ops chunk in `dist/`).
- **P4. The ops database secret carries a full connection string, like the master secret.** CDK
  creates `policy_atlas_v3/ops_db` with the template `{"username": "pa_ops"}` and a generated
  `password` (`exclude_punctuation` so the value is URL-safe; the sync still escapes it). The
  sync is a **separate entrypoint**, `python -m policy_atlas.ops.db_role sync`, that imports
  nothing from `ops.cli` (no `--env`, no Cognito or STS verification; finding 3). It (1) reads
  the whole secret JSON, (2) runs `ALTER ROLE pa_ops LOGIN PASSWORD <literal>` with the
  password quoted by `psycopg.sql.Literal` (bound parameters are not allowed in `ALTER ROLE`),
  (3) builds the ops URL with `sqlalchemy.engine.URL.create` from the master URL's host, port
  and database and the `pa_ops` credentials, (4) writes the **full** JSON back with
  `db_connection_string` added or replaced (`PutSecretValue` replaces the whole value;
  finding 7). It never logs the URL or the password; a test with reserved characters in the
  password asserts both. The **migration task's command** becomes `sh -c "alembic upgrade
  head && python -m policy_atlas.ops.db_role sync"`, its environment gains
  `OPS_DB_SECRET_ARN`, and its task role gets `secretsmanager:GetSecretValue` and
  `PutSecretValue` on that one secret; the synth test pins the command, the variable and the
  two actions. The ops task's `DATABASE_URL` is `ecs.Secret.from_secrets_manager(ops_db_secret,
  field="db_connection_string")`, the same shape as the API's, so `settings.py` is unchanged.
  The field exists before the ops service first starts because the deploy script runs the
  migration task (and so the sync) before it starts the ops service (§ Deploy order).
- **P5. The `pa_ops` grant list is contract B13 revision 3.1**, which follows what the command
  functions do today and no more: column-level `UPDATE`s, the one `DELETE` on
  `project_membership`, schema `USAGE` without `CREATE`, nothing on `capability_run` or
  `alembic_version`, and the trigger that lets the ops login clear `is_admin` and `is_ops`
  but never set them (findings 5, 6). The run-cap check (064a Q7) runs on the API only; the
  ops people list shows tasks created in the last 365 days (a `task` read), not simultaneous
  tasks.
- **P6. The grant list is pinned by a test that logs in as `pa_ops`, not by `SET ROLE`.** The
  test fixture creates the role with `LOGIN` and a password in the worker's test database
  (the compose user may), opens a second engine as `pa_ops`, runs every ops write of the
  conformance suite through it, and asserts each refusal B13 lists with `InsufficientPrivilege`
  (finding 6). Staging check (11) repeats the refusals over the real secret.
- **P7. The quota resolver lives beside `tasks_created_since`** in `routers/common.py`:
  `effective_limits(conn, user_id) -> Limits(task_quota: int | None, runs: int | None)`,
  `None` meaning no limit (0 in the column, or admin for the task quota). The three callers
  (task create, run start, `/me`) replace their direct `settings.*` reads with it; the
  settings values become the resolver's defaults. One test module pins the precedence.
- **P8. Ops routes are thin, and the audit row is inside the transaction while the log line
  is after it.** Each route resolves its target, calls one command function and inserts the
  `ops_action` row through one helper `record_action(conn, actor, action, target, outcome)`;
  the `ops.action` log line is emitted by the route **after** the transaction commits, the
  way the CLI's post-commit admin trace works. Bulk routes take a list of subjects and run
  each subject inside its own savepoint (`conn.begin_nested()`): a failure rolls back that
  savepoint only, records a `failed` outcome row for that subject, and the loop continues
  (finding 8). The conformance test for the loop triggers a real SQL failure (a violated
  constraint), not a command-level refusal. The route module is `routers/ops.py`; the router
  is included only when `settings.service_role == "ops"`.
- **P9. Ops mode is a settings field, not a second factory, and the pages are a fallback, not
  a root mount.** `Settings.service_role: Literal["api", "ops"]` from
  `POLICY_ATLAS_SERVICE_ROLE`. `create_app` picks the router set and the lifespan from it:
  `_lifespan` (unchanged) for `api`, a new `_ops_lifespan` that builds the engine, the HTTP
  client and the authenticator, starts the sweep task when the flag is on, and shuts them
  down. In ops mode the health and `/api/v1/ops/*` routes are registered first, Vite's hashed
  assets are mounted at `/assets` only, and a final `GET /{path:path}` route returns
  `index.html` for any path that does not start with `/api` and 404 for one that does
  (finding 4). Route-order tests cover `/people`, `/assets/x.js`, `/api/v1/ops/organisations`
  and `/api/v1/tasks`. The directory comes from `OPS_UI_DIR` (default `/app/ops-ui`); tests
  point it at a temporary directory, and when it is absent the fallback is not registered.
- **P10. The sweep is a plain asyncio task** in the ops lifespan: `while True: await
  asyncio.sleep(60); await asyncio.to_thread(sweep_once, engine, cognito, settings)`; the
  lifespan's `finally` cancels it and awaits the cancellation before disposing the engine, so
  a stop never leaves a half-run tick. `sweep_once` is a pure function in `ops/sweep.py` that
  takes the clock, so the unit tests call it directly with a fake Cognito and a fixed clock
  and never sleep. The hourly cap is a count of `ops_action` rows with actor `sweep` and
  action `invite` in the last hour, so a restart does not reset it. **Idempotency of the
  terminal outcomes:** before handling a row the sweep looks for an `ops_action` row with
  actor `sweep`, target the waitlist row id and outcome `enrolled_elsewhere`; if one exists
  the row is skipped without a new log line. A `failed` outcome row does not block a retry
  (finding 9). The Requests page derives the orange "Check" state from that terminal row.
  The sweep is not one of the API's lifespan jobs, so web-api.md § Deployment posture's
  one-process rule is untouched; the plan adds a sentence there saying so (Phase 12).
- **P11. The ensure-account command reuses `create_user`'s pieces, not its entry point.**
  `ensure_account_enrolled` calls the existing `_find_sub_by_email`, the Cognito create path
  with `--invite email` semantics, and `_enrol`; it never calls `create_user` itself (whose
  "exists and org given" refusal is the retry case). `create_user` and the CLI are unchanged
  (contract § Terms).
- **P12. Email copy is written by the lead** in Phase 2 as two HTML files; agents never write
  it. The owner reviews the files in a browser at the Phase 2 gate (A2).
- **P13. Regeneration closes every phase that changes a contract model.** `make openapi-sync`
  then `make drift-check` after Phases 4 (quota on `/me`) and 6 (the ops document); the ops
  document's generation is added to both targets in Phase 6.
- **P14. Codex briefs are one seam each** with a file boundary and a named test command
  (§ Briefs). The build conversation dispatches them one at a time, or in parallel where the
  files do not overlap.
- **P15. Staging is the only live environment this slice touches.** Production receives A
  after the PR merges (its SES is ready); B and C reach production in later deploys, C only
  after 064b (C4). The eleven live checks run on staging from the branch deploy the owner
  triggers, as 057 and 058 did.

## Folded findings (Codex, draft 1)

| # | Severity | Folded as |
|---|---|---|
| 1 | blocker | branch rebased onto 064a; P12 of draft 1 (offboard skip) removed; § Context "Base branch" |
| 2 | blocker | § Deploy order: the ops secret and the service exports are checked **after** `cdk deploy`, before stop and migrate; only the allowlist parameter and the bundle are checked before |
| 3 | blocker | P4: separate entrypoint `ops.db_role`; migration task command runs both; synth-pinned |
| 4 | material | P9: routes first, `/assets` mount, final non-`/api` fallback, route-order tests |
| 5 | material | contract B13 revision 3.1 and rubric 23 amended; owner confirms at this gate |
| 6 | material | B13: column grants, `USAGE` without `CREATE`, the set-true trigger, login-as-`pa_ops` test, staging check (11) |
| 7 | material | P4: read-modify-write of the full secret, `URL.create`, quoted literal, reserved-character test, no logging |
| 8 | material | P8: savepoint per subject, log after commit, real SQL-failure test |
| 9 | material | P10: terminal-outcome predicate on `ops_action`; retries for `failed` |
| 10 | material | contract B6 revision 3.1 and rubric 16: the dialog lists every person, the count is typed |
| 11 | material | § Gate map: full after Phases 5, 7 and 9 |
| 12 | minor | P1: one output path, `../backend/ops-ui/`; image test |

The reviewer named four targets it did not cover: the asyncio sweep and the one-process
rule (P10 now states both), the second Vite entry and vitest (P3 now states the config
reuse, `tsc -b` and the include glob), executor routing (unchanged; every `lead` mark below
carries its reason), and draft 1's 064a handling (removed by the rebase).

## Open for the plan gate

1. **Contract revision 3.1** (B1, B6, B13 as amended today) and the two plan refinements P1
   (bundle built by the deploy script) and P5 (grants follow the code). Recommendation:
   accept all; the outcomes the contract names are unchanged, and the database now refuses
   what the contract's prose used to promise.
2. **The ops people list's "Tasks this year" column** reads `task` for every person listed.
   With under a hundred people one grouped query per page load is fine; recommendation: one
   grouped query, no cache, and a `ponytail:` note naming the ceiling.

## Gate map (binding)

| Boundary | Gate | Why |
|---|---|---|
| Build-open | full | baseline (spine) |
| After Phase 1 | infra synth tests + `make verify-fast` | infra only |
| After Phase 2 | fast + owner copy review | files, no code paths |
| After Phase 3 | full | schema (mandatory class) |
| After Phase 4 | full + `drift-check` | commands, resolver, `/me` regeneration |
| After Phase 5 | full | the auth-facing application boundary (finding 11) |
| After Phase 6 | full + `drift-check` | routes; ops OpenAPI document and types |
| After Phase 7 | synth tests + full | IAM, image, service composition (finding 11) |
| After Phase 8 | fast per round | frontend surfaces |
| After Phase 9 | full + `deploy-build-guard-test` | deploy sequencing and the secret path (finding 11) |
| After Phase 10 | full | sweep; last backend phase |
| Phase 11 (staging) | the eleven live checks | contract § Acceptance |
| Step-6 exit | full | exit (spine) |

Only Phases 1, 2 and 8 gate below a full run: infra-only, files-only and frontend rounds.

## Deploy order (binding for Phase 9 and Phase 11)

`scripts/deploy.sh` keeps its stop → migrate → start shape and gains, in this order:
(1) **before `cdk deploy`:** the ops allowlist parameter check (same validator as
Metabase's, parameter name from `pa_config.json`), `pnpm build:ops` into `backend/ops-ui/`
(P1), and the bundle presence check; (2) **`cdk deploy`**, which creates the ops secret, the
ops service and its SSM exports on the first run; (3) **after CDK, before stop:** the ops
secret exists, the ops service and target group are exported (finding 2); (4) stop the API
**and** the ops service; run the migration task, whose command now runs `alembic upgrade
head` and then the `db_role sync` (P4); start the API, then the ops service; (5) the
Metabase single-count invariant extends to the ops service. The downgrade path is the
mirror: stop both, downgrade, start. Rollback for each step is the contract's
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
- codex: one Alembic migration after 064a's head, additive: `app_user.is_ops`,
  `app_user.invited_at`, the four quota override columns with `CHECK (>= 0)`, `ops_action`,
  `organisation_domain`, the two `waitlist_entry` columns, the `pa_ops` role (idempotent `DO`
  block, `NOLOGIN`), the B13 grants and the `app_user` trigger; the downgrade reverses all of
  it (`REVOKE`, drop trigger, `DROP ROLE`). `core/schema.py` tables updated. Done: `alembic
  upgrade head` then `downgrade -1` then `upgrade head` on the test database leaves no diff;
  `make verify` green.
- codex: the P6 privilege test in `tests/ops/test_pa_ops_login.py`: the fixture that creates
  the login, the refusal half now; the positive half (every ops write) is completed in
  Phase 6 when the routes exist.

### Phase 4 — Commands, resolver and `/me` (B11 helper, B12, ensure-account, `set_quota`)
- codex: `ops/commands.py` gains `ensure_account_enrolled` (P11) and `set_quota`; `ops/cli.py`
  gains `ops grant|revoke`, `user quota`, `org quota`, `org domain add|remove`, each with the
  post-commit admin trace where the contract says so; `user offboard` clears `is_ops`. Unit
  tests per B9 and B12 for the command branches and the Cognito-created-then-database-failed
  retry. Done: `pytest tests/ops` green; `grep -n "def create_user" ops/commands.py`
  unchanged by diff.
- codex: `routers/common.py` `effective_limits` (P7) and its three callers; `MeOut.task_quota`
  null for no limit; tests for precedence, zero, admin exemption, clearing. Done: `pytest
  tests/api/test_me_router.py tests/api/test_tasks*.py tests/api/test_run*.py` green.
- fast-worker: `ops/environment.py` and `ops/commands.py` move the `mypy_boto3_cognito_idp`
  imports under `TYPE_CHECKING` (B5); a test imports `policy_atlas.ops.commands` with the stub
  package hidden from `sys.modules`. Done: `make typecheck` green; the test passes.
- Gate: full + `make openapi-sync && make drift-check`.

### Phase 5 — Ops mode (B2)
- codex: `Settings.service_role` (P9); `create_app` picks routers and lifespan by it;
  `_ops_lifespan` per P9 and P10 with the sweep task hook left as a no-op callable until
  Phase 10; the `/assets` mount and the fallback route. Tests per B9's route-table rows, the
  patched-lifespan test (executor constructor and `continuation.startup_sweep` never called
  in ops mode), the route-order tests of P9 from a temporary directory, and `api` mode
  serving no static file. Done: `pytest tests/api/test_service_role.py` green.
- Gate: full.

### Phase 6 — Ops routes and the ops OpenAPI document (B4, B7, B9, C5's read)
- lead: the route list and the request and response models in `api/contract/ops.py` (seam
  design: the shapes the page and the types are generated from). Why lead: seam design.
- codex: `routers/ops.py` per P8, every write through `record_action` and the post-commit
  log; the resend route with the 429 cooldown on `invited_at`; bulk variants of set-quota,
  move, resend, de-enrol and offboard with a savepoint per subject; the requests list with
  the three states (C5, reading the sweep's terminal rows per P10); the ops-role dependency
  and the closed reader list for `is_ops` (asserted like 033's `is_admin` list). Conformance
  tests per B9 (401, 403, 200; no `app_user` row from a non-ops token; one `ops_action` row
  per write and per bulk subject; the loop continues past a real SQL failure). Done: `pytest
  tests/api/test_ops_router.py tests/api/test_api_conformance.py` green.
- codex: `export_openapi.py --mode ops` writing `frontend/openapi-ops.json`; `package.json`
  `gen:ops` → `src/api/gen/types-ops.ts`; `make openapi-sync` and `make drift-check` cover
  both; the public document asserted to contain no `/api/v1/ops` path. Done: `make
  openapi-sync && make drift-check` clean; a test asserts the public document has no ops path.
- codex: complete the positive half of the P6 login test by running the ops conformance
  writes as `pa_ops`, including a de-enrol that clears `is_admin` (allowed) and an attempted
  set to true (refused by the trigger). Done: the test is green both halves.
- Gate: full + `drift-check`.

### Phase 7 — Infrastructure and image (B3, B13 secret)
- codex: `policy_atlas_stack.py` ops service per B3 following the Metabase block (task
  definition with the ops environment and `DATABASE_URL` from the ops secret, service with
  `desired_count` 0, target group, listener rules on host header plus source addresses from
  the new SSM parameter via `metabase_allowlist.py` given the parameter name, A record, the
  SSM exports the deploy script reads), the ops task role's five Cognito actions scoped to
  the pool, the ops secret (P4), the migration task's command, `OPS_DB_SECRET_ARN` and its two
  Secrets Manager actions, the ops `APP_ORIGIN`, and the callback and logout URLs in
  `cognito_auth.py`. `pa_config.json` `ops` and `self_signup` blocks for both environments.
  Synth tests: both task roles (no `cognito-idp` on the API's; exactly five on the ops'), the
  listener rule shape, the callback URLs, the ops `APP_ORIGIN`, the secret template, the
  migration command and its two actions. Done: `pytest infra/tests` green; `cdk synth` for
  both environments succeeds.
- fast-worker: `backend/Dockerfile` copies `ops-ui/` into `/app/ops-ui` through a stage that
  tolerates its absence (P1); `backend/.dockerignore` keeps `ops-ui/` in; `.gitignore` adds
  `backend/ops-ui/`; `tests/scripts` asserts `index.html` in the built image when the
  directory is present. Done: `docker build backend/` succeeds with and without the directory.
- Gate: synth tests + full.

### Phase 8 — Ops pages (B6, B12 forms, C5)
- lead: the section list, the states and every line of copy for the ops pages, from the
  owner's explainer and wireframes (People with multi-select, Add a person, Set a quota with
  the "Simultaneous tasks" warning, Requests with three states, Organisations with the move
  panel, offboard confirmation by address or by count under the full list). Why lead: copy
  and direction.
- frontend-designer: `frontend/ops.html`, `vite.ops.config.ts` (P3), `src/ops/` (router,
  shell, the five views, the confirmation dialog, the "does not have the ops role" state on a
  403), using `types-ops.ts`, the shared auth provider and `ui/brand`; `pnpm build:ops`;
  vitest for each view's states against a mock of the ops routes (`src/ops/mock`). Done:
  `pnpm test` and `pnpm build:ops` green; `pnpm build` output unchanged (no ops chunk in
  `dist/`).
- frontend-designer: one polish pass per task-cycle-build § Step 5b after the lead's review.
- Gate: fast per round.

### Phase 9 — Deploy script and the database login (B3, B13, § Deploy order)
- codex: `ops/db_role.py` with its own `__main__` (P4); unit tests with a fake Secrets
  Manager and the test database, a reserved-character password, and an assertion that no
  log record contains the password or the URL. `scripts/deploy.sh` per § Deploy order, with
  the ops allowlist parameter check mirroring `check_metabase_allowlist_parameter`, the
  `build:ops` step and bundle check before CDK, the secret and export checks after CDK, the
  stop-both-then-start-API-then-ops sequence and the single-count invariant; `tests/scripts`
  extended (the `deploy-build-guard-test` target) for the new order and the first-deploy
  path. Done: `make deploy-build-guard-test` green; `shellcheck scripts/deploy.sh` clean.
- Gate: full + `deploy-build-guard-test`.

### Phase 10 — Sweep (C3, C4, C6)
- codex: `ops/sweep.py` `sweep_once` per P10 and the lifespan hook with cancellation; the
  domain match (exact, lower-cased, no subdomain); stamping; the hourly cap from
  `ops_action`; the three ensure-account outcomes with the terminal-outcome predicate; retry
  after `failed`; actor `sweep` rows. Unit tests per C6 with a fake Cognito and a fixed
  clock, plus "enrolled elsewhere is logged once across two ticks". Conformance: the public
  waitlist response byte-identical for a listed and an unlisted domain. Done: `pytest
  tests/ops/test_sweep.py tests/api/test_waitlist*.py` green; the flag-false test asserts the
  task is never created; a lifespan test asserts the task is cancelled and awaited on exit.
- Gate: full.

### Phase 11 — Staging and the live checks (contract § Acceptance, § Constraints "Rollback")
- lead with the owner: the allowlist parameter and the Nesta organisation and domain row on
  staging (addresses and names never committed); the owner triggers the branch deploy;
  `email.enabled` true, `ops.desired_count` 1, `self_signup.enabled` true on staging only.
  The eleven checks, each with a timestamp in `verification.md`; the invitation's
  `Authentication-Results` header with the address redacted; the deployed task-role policies
  for both services; `psql` as `pa_ops` over the real secret for check (11). Then each
  rollback once (A, B, C) and the re-enable. Why lead: live operations with the owner.

### Phase 12 — Docs and exit
- fast-worker: `docs/deferred.md` (SES entry discharged; admin-surface entry reopened; new
  seams: domains beyond `nesta.org.uk`, the domain table on the ops pages, application-sent
  email, the ops action log on the ops pages); `web-api.md` § Auth boundary, § Waitlist and
  § Deployment posture (the sweep is an ops-service job, not an API one) additive paragraphs;
  `infra/DEPLOYMENT.md` ops section (the allowlist parameter, the secret, the ops address,
  the first ops grant, the first-deploy order).
- lead: ADR 0046 status Accepted with the date (drafted at step 4, confirmed here);
  `verification.md` complete; step-6 exit full verify.

## Briefs (one seam each; the build conversation fills the file list from the phase)

Each Codex brief states: read-only context files, the files it may change, the contract ids,
the done command, and "do not edit `dev`'s or 064a's migrations, generated files or
`create_user`". Frontend briefs go to `frontend-designer` with the lead's copy attached and
`DESIGN.md` named. No brief writes user-facing copy or email copy.

## What the plan does not do

- No change to the public bundle beyond `frontend/public/brand/email-logo.png` (A2).
- No production deploy of B or C in this slice (P15).
- No edit of the domain table from the ops pages, no second domain, no MFA, nothing in the
  contract's Out list.
