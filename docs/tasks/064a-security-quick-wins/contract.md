# Task contract: 064a-security-quick-wins

First slice of the [064 security hardening programme](../064-security-hardening/programme.md).
Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status:** approved, revision 2. Contract approved (before planning): 2026-11-16 · owner.
> Adversarial review 2026-11-16: Codex 10 findings, Opus 23 (records in the gitignored
> `research/`); every finding is folded into revision 2 or listed under plan § Owner items.
> Revision 2 changes the admission sites (Q7), the offboard semantics (Q10), the Q9 shape and
> the Q11 trust rule; revision 2 approved by the owner 2026-11-16, with the quota banner added
> the same day. ·
> Plan approved (before implementation): 2026-11-16 · owner (draft 2) · ADR:
> [0045](../../adr/0045-per-user-run-cap-task-quota-offboarding.md), Accepted 2026-11-16.

## Goal

Close the seventeen review findings that each need a small, local change, so that the API
stops leaking user text and secrets into logs and the browser, one user cannot take the
whole server or create tasks without limit, an outsider cannot freeze sign-in, the waitlist
stops confirming who signed up, the site is always encrypted with current TLS, the health
check no longer depends on the database, a failed run does not stay "running", and an
operator can actually remove a person's access.

## Deliverable

One pull request on `task/064a-security-quick-wins` into `dev` that lands Q1 to Q17 below,
with tests, the new config keys in `infra/pa_config.json` and `infra/db_config.json`, the
index migration, the `user offboard` command, and the deployment notes. After the staging
deploy, one manual check per item that has a visible effect (§ Acceptance checks).

## Terms

| Term | Meaning |
|---|---|
| **Review id** (`H-06`, `M-30`, …) | The id in the 2026-10-19 project review. Kept so the programme map can be matched to the review. |
| **Q1 to Q17** | The seventeen problems of this slice, numbered below. The rubric and the plan use these numbers. |
| **JWKS** | JSON Web Key Set: Cognito's list of public keys that verify sign-in tokens. `api/auth.py` `JwksProvider` caches it for 5 minutes. |
| **Key id** (`kid`) | The field in a token header that names which JWKS key signed it. Anyone can write a token header, so a key id is untrusted input. |
| **Locals** | The local variables of each stack frame. structlog's `dict_tracebacks` processor writes them into every JSON error log (`show_locals=True` by default in structlog 26.1). |
| **Event log** | The `event_log` table (`core/events.py`). The progress stream (SSE) reads it and shows some payload fields to the browser. |
| **Admission** | The check in `api/routers/runs.py` that decides whether a new run may start: `active_parentless_walk` (one run per task) and `executor_full` (global cap, `run_executor_max`). |
| **Parentless executor walk** | A `capability_run` row with no parent and status `running` that occupies an executor worker. Child runs of a scoping walk and option-search runs do not count (`routers/common.py` `parentless_walk`, `executor_walk`). |
| **Paused** | A run waiting at a check-in has status `paused`. It is not `running` and does not count toward any cap. |
| **Task quota** | The number of task rows a user may create in a rolling window. Counted on `task.owner_user_id` and `task.created_at`, all capabilities, archived rows included. |
| **Admin** | `app_user.is_admin`. ADR 0033 makes it read-only and names every code site that reads it; a test asserts the list. |
| **Effective screen rows** | The subquery in `evidence_search/assess/screen.py` that picks the current screening result per document with a window function. |
| **Offboard** | De-enrol plus disable the Cognito account, revoke its refresh tokens and remove public links. |

## Read first

- [ADR 0033](../../adr/0033-organisation-tenancy-and-global-admin-read.md) § admin read legs
  (Q8 adds an admin exemption; the reader list must stay closed).
- `api/routers/runs.py` admission block and `routers/common.py` walk predicates (Q7).
- `api/routers/tasks.py` `create_task` (Q8).
- `evidence_search/assess/screen.py` `effective_screen_rows` and its three callers (Q9).
- `ops/commands.py` `de_enrol_user` and `ops/cli.py` user commands (Q10).
- `infra/infra/policy_atlas_stack.py` target group and CloudFront behaviours;
  `infra/infra/cognito_auth.py` password policy; `infra/tests/unit/test_synth.py` (Q4 to Q6).
- `core/logging.py` (Q1); `runtime/harness.py` the two `str(exc)` sites (Q3).
- `api/auth.py` `JwksProvider.get_key` and `refresh`, `get_current_user` (Q16).
- `api/routers/runs.py` `_dispatch_run` `except` branch; `api/app.py` startup and
  `api/routers/check_ins.py` for the existing `mark_interrupted_best_effort` calls (Q14).
- `backend/Dockerfile` `CMD` (Q11); `infra/infra/network_stack.py` HTTPS listener and
  `infra/infra/database_stack.py` backup props, `infra/db_config.json` (Q13, Q17).
- `api/longlist_start.py` `admit_and_mint` (the third admission site, Q7);
  `api/continuation.py` resume path (read to confirm it stays uncapped).
- `docs/specs/system/web-api.md` § error codes (Q2, Q7, Q8, Q15 change the 409 list).
- `frontend/src/views/NewTaskView.tsx` error branch and `frontend/src/mock/api.ts` waitlist
  reply (Q8, Q2). `scripts/deploy.sh` post-stable check (Q4).
- The existing tests that pin old values and must change on purpose:
  `infra/tests/unit/test_synth.py` (health path, password length, backup retention),
  `infra/tests/unit/test_service_wiring.py` (environment variable set),
  `backend/tests/ops/test_ops_structure.py` (CLI command list),
  `backend/tests/api/test_waitlist.py`, `backend/tests/api/test_admin_leg.py` reader list.

## The problems

| # | Review | Today | Required |
|---|---|---|---|
| **Q1** | H-06 | `core/logging.py` uses `dict_tracebacks`; JSON error logs carry every frame's locals, so user text and the first 80 characters of any secret in a local reach CloudWatch. | Render tracebacks without locals. `Settings.database_url` gets `repr=False`. A test proves no `locals` key and no planted secret value appears in a JSON error log. |
| **Q2** | M-30 | `POST /api/v1/waitlist` returns `409 already_registered` for a known email, so anyone can test whether an address is on the list. | A duplicate email gets the same `201` body as a new one and writes no row, through `INSERT … ON CONFLICT DO NOTHING` (catching `IntegrityError` inside the request's transaction would leave it aborted). The frontend's 409 branch, the mock API's 409 reply and the `already_registered` conflict code are removed; `docs/specs/system/web-api.md` and `openapi.json` follow. |
| **Q3** | M-11 | `runtime/harness.py` writes `str(exc)` into `component.failed` payloads at two sites and a third site at line 676; the runner backstop `_bounded_error` (`runner.py` ~6225 and ~6350) stores 200 raw characters. The stream shows these. Library messages can contain SQL, host names and provider ids. | One helper, used at all five sites. An exception keeps its message when its class is defined under `policy_atlas.` or it carries a `reason` attribute (the 013 structured-rejection rule); any other exception is reduced to its class name. The full exception is logged server-side with `exc_info=True` at the same site. Test fixtures that define their own exception classes carry `reason`, or the test is adjusted with a written note. |
| **Q4** | H-16 | The load balancer health check hits `/readyz`, which needs a free thread and a database connection within 5 s. Under load or a short database outage ECS replaces the only container and kills every run. | The target group checks `/healthz`, and `/healthz` becomes `async def` so it needs no pool thread either. `/readyz` stays for diagnosis, and `scripts/deploy.sh` calls it once after the service is stable, because the health check no longer proves the database secret works. |
| **Q5** | M-04 | CloudFront behaviours have no `viewer_protocol_policy`, so `http://` serves the app unencrypted on a first visit. | Both behaviours set `REDIRECT_TO_HTTPS`. |
| **Q6** | M-13 (part) | Cognito password minimum length is 8. | 12. Applies when a user next sets a password; existing passwords are unchanged. |
| **Q7** | H-17 | `executor_full` counts only the global total; one user can hold all 10 slots. | A per-user cap, `runs_per_user` (3 in both environments). Counted under `_dispatch_lock` as the user's running parentless executor walks (joined to `task.owner_user_id`) **plus** the user's tasks in the reservation set that will occupy a worker, because the run row is written after the lock is released. Refused with `409 user_capacity`. Applies at the three new-walk admission sites: `create_run` and `start_toc_check` in `routers/runs.py`, and `admit_and_mint` in `api/longlist_start.py`. Resuming a paused walk after a check-in has no capacity check today and gains none (the decision is already recorded; refusing would strand it). Applies to admins too. |
| **Q8** | H-04 (part) | Nothing limits how many tasks a user creates. | `task_quota_per_year` (50 in both environments): at `create_task`, count the caller's task rows with `created_at` in the last 365 days by the database clock; at or above the quota refuse with `409 task_quota`. Admins are exempt through the existing `_is_admin` helper. That call makes `create_task` a named entry in the closed reader list of ADR 0033 (the structural test matches the name `is_admin` in any scope), so the test's list, the `_is_admin` docstring and ADR 0033 decision 4 are amended deliberately by ADR 0045. The new-task page shows the mapped message (today it ignores the error code). `GET /api/v1/me` gains `task_quota: {used, limit} | null` (`null` when the caller is exempt), computed in `get_me`, which already reads `is_admin`. A **quota banner** renders in the same slot as the sensitive-data banner (`AppShell.tsx`) whenever `used >= limit`: "You have reached your usage quota of 50 tasks. Contact your Policy Atlas administrator to request more." It is not dismissible, because the state persists until a task ages out or an administrator acts. A person already over 50 when the slice lands sees the banner and is refused new tasks; nothing else happens to them. Before each deploy, verification runs the count per user so the owner knows who will see it. Two parallel creates by one user can both pass the count; accepted, the window is one request. |
| **Q9** | H-14 | `effective_screen_rows` partitions by scope and snapshot and only its callers filter by task, so PostgreSQL ranks every task's rows for every call; the task list calls it once per row every 15 s. No index starts with `task_id`. | `task_id` becomes the first column of `partition_by`. PostgreSQL then pushes a caller's `task_id` filter below the window function on its own, so none of the 22 call sites changes and the result set cannot change (`fk_ssr_scope_task` ties each scope to one task). One migration adds an index on `source_screening_result (task_id, evidence_scope_id, task_source_snapshot_id)`, built and dropped `CONCURRENTLY` following the `a3d8f6c1e2b4` precedent, including its invalid-index recovery. `EXPLAIN ANALYZE` for `included_source_count` before and after, on a local database seeded with at least two tasks and a few thousand screening rows, is recorded in verification. |
| **Q10** | M-02 | `user de-enrol` changes the database only. The Cognito account stays active and tokens stay valid; public links stay public. | `user offboard (--email | --sub)`: Cognito `AdminDisableUser` and `AdminUserGlobalSignOut` first, then the database: de-enrol **only if** the person is still enrolled or holds the admin flag (the plain `de_enrol_user` refuses an already de-enrolled person, which is M-02's main case), then `is_public = false` on the person's tasks (`project` has no public-link column; its `visibility` is tenancy and is left alone). A person with a Cognito account but no `app_user` row is handled Cognito-only and reported as such. When the admin flag is cleared the command emits the same admin trace as `admin revoke`. Uses the CLI's existing confirmation hook. An access token already issued stays valid for up to 60 minutes and an open progress stream outlives it; the deployment doc says so. |
| **Q11** | M-21 | Uvicorn closes idle connections after 5 s while the load balancer keeps them 120 s, so some requests get a 502. Uvicorn ignores the forwarded headers and sends `server: uvicorn`. | The Dockerfile `CMD` adds `--timeout-keep-alive 125 --proxy-headers --no-server-header`. The trusted proxy range is **not** `*`: uvicorn takes the leftmost `X-Forwarded-For` entry from a trusted proxy, and the client writes that entry. The container environment sets `FORWARDED_ALLOW_IPS` to the VPC address range from `network_config.json`, which uvicorn reads, so only the load balancer's addresses are trusted. |
| **Q12** | M-17 | The Cognito user pool has `RemovalPolicy.RETAIN` but no deletion protection. A CDK change that replaces the pool would create an empty one and strand every user. | `deletion_protection=True` on the pool. |
| **Q13** | L-01 | The load balancer HTTPS listener uses the default TLS policy. CloudFront already synthesises `TLSv1.2_2021` by default. | Listener `ssl_policy=RECOMMENDED_TLS`. The distribution pins `minimum_protocol_version=TLS_V1_2_2021` explicitly so the default cannot drift; the synth test asserts both. The live check reads the listener policy in the console, not `openssl`, whose own build may refuse old protocols. |
| **Q14** | H-11 | `_dispatch_run` only logs when a run fails between pipeline steps. The row stays `running`, the task refuses new runs with `409 run_active`, the slot stays taken until a restart. | `create_run` mints the run id before dispatch (`capability_run_id=uuid4()`), as the queued theory-of-change path and `admit_and_mint` already do; `_dispatch_run` and `_await_new_run` accept it today. The `except` branch calls `continuation.mark_interrupted_best_effort` with **that id only**. No lookup by task: the reservation is dropped once the row exists, and another surface can start a walk in that gap. |
| **Q15** | L-22 | `ApiConflict("confirm_expired", …)` is raised in `check_ins.py` but the code is not in `_CONFLICT_CODES`, so the user gets a 500. | `confirm_expired` joins `_CONFLICT_CODES` and `errors.ts`. |
| **Q16** | H-01, M-20 | A token header with a new random key id makes the API download Cognito's key list again, for every request, with no sign-in, and the download blocks the event loop. The negative cache is per key id, so a fresh id each time defeats it. If a download fails, the old keys are dropped and every user is signed out until the next success. | `JwksProvider` refreshes at most once per 30 s in total, whatever the key id, under a `threading.Lock` that claims the refresh slot before any network call, so forty worker threads missing at once cause one fetch; a miss inside the window raises at once. The per-id negative cache goes. A failed refresh keeps the previous keys and logs `auth.jwks_refresh_failed` as an error; a successful one logs `auth.jwks_refreshed` at info. `get_current_user` **and** `get_optional_user` become plain `def` (the second awaits the first today), so FastAPI runs them on the worker pool instead of the event loop. |
| **Q17** | M-16 | Aurora keeps automatic backups for 7 days in both environments. | `backup_retention_days` in `infra/db_config.json`: staging 7, production 35. |

One number per problem, one invariant per problem. Q7 and Q8 are two problems because one
bounds load and the other bounds count. Q16 bundles H-01 and M-20 because both are the
same ten lines in `JwksProvider.get_key` and `refresh`, with one test file.

## Scope / Out of scope

- **In:** `core/logging.py`, `api/settings.py`, `api/auth.py`, `api/app.py` (conflict
  codes), `api/routers/waitlist.py`, `api/routers/runs.py`, `api/routers/common.py`,
  `api/routers/tasks.py`, `runtime/harness.py`, `evidence_search/assess/screen.py` and its
  callers, `ops/commands.py`, `ops/cli.py`, one Alembic revision after `f5a1c8e93b27`,
  `backend/Dockerfile` (`CMD` only), `infra/pa_config.json`, `infra/db_config.json`,
  `infra/infra/policy_atlas_stack.py`, `infra/infra/cognito_auth.py`,
  `infra/infra/network_stack.py`, `infra/infra/database_stack.py`, `infra/DEPLOYMENT.md`,
  `api/longlist_start.py`, `scripts/deploy.sh` (one post-stable check),
  `docs/specs/system/web-api.md` (the 409 code list), `docs/deferred.md` (the lines Q6, Q10
  and Q17 make stale), `frontend/src/views/splash/WaitlistForm.tsx`,
  `frontend/src/views/NewTaskView.tsx` (error branch only), `frontend/src/mock/api.ts`
  (waitlist and `/me` replies), `frontend/src/lib/errors.ts`, `api/routers/me.py` and
  `api/contract/tenancy.py` (`MeOut.task_quota`), a new `frontend/src/views/QuotaBanner.tsx`
  rendered from `AppShell.tsx` beside `SensitiveInfoBanner`, `make openapi-sync` output,
  tests for each.
- **Out:** WAF, CAPTCHA, CSP, MFA, threat protection, SES (064b to 064d). Spend caps and a
  usage table. Request body size limits (H-02). Any change to the de-enrol semantics of ADR
  0033. A quota display in the frontend (the error message is enough for this slice). The
  Cognito feature tier.

## Constraints & approval gates

- **Schema:** one migration, index only, downgrade drops the index. No data moves.
- **Auth / tenancy:** Q8 adds the first admin-only behaviour that is not a read, and a
  fifth named entry (`routers/tasks.py: create_task`) in the closed `is_admin` reader list.
  ADR 0045 records both and amends ADR 0033 decision 4 ("only four places"); the structural
  test's list, its comment block and the `_is_admin` docstring change with it, on purpose.
  Q10 is the first ops command that writes to Cognito; it runs from the operator's
  credentials, not from the API.
- **Programme rule, applied and waived:** `task_quota_per_year`, `runs_per_user` and
  `backup_retention_days` are per-environment keys. The health path, HTTPS redirect,
  password length, server flags, pool deletion protection and TLS policies have one right
  value in every environment and are hard-coded on purpose; `FORWARDED_ALLOW_IPS` is
  derived from the existing per-environment network config.
- **Production config:** two new keys in `infra/pa_config.json` for both environments
  (`task_quota_per_year`, `runs_per_user`), passed as `TASK_QUOTA_PER_YEAR` and
  `RUNS_PER_USER` to the container; one new key in `infra/db_config.json`
  (`backup_retention_days`, staging 7, production 35). The synth test pins them. Q4, Q5,
  Q6, Q12, Q13 and Q17 change live infrastructure settings. Q11 changes the container
  command.
- **Public interface:** three 409 codes added (`user_capacity`, `task_quota`,
  `confirm_expired`); one removed (`already_registered`). `frontend/src/lib/errors.ts`
  maps the added ones. `MeOut` gains the optional `task_quota` object; additive, so no
  client breaks.
- **Dependencies, CI, egress:** none.
- **Rollback:** every change reverts by redeploying the previous image and CDK state. The
  migration downgrade drops the index only. The password policy change cannot be undone for
  users who already set a 12-character password, which is harmless. Lowering the backup
  retention again discards the older backups. Pool deletion protection must be turned off
  before any deliberate pool replacement.

## Public / private boundary

All artefacts are public-safe. The Q1 test uses planted fake values, never a real secret.
Verification records `EXPLAIN` output from the local database, not from production.

## Model route

n/a. No inference.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves.** No new column, flag or label beyond the index.
- **Flag, don't drop.** Q3 keeps the structured `reason`; only the raw message changes.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when an approval gate above is hit again (for example a second migration
turns out to be needed), when the ADR 0033 reader test cannot stay closed without a new
reader, or when the `EXPLAIN` for Q9 shows the index is not used.

## Acceptance checks

- `make verify` green; `make -C infra test` green.
- Tests, one per problem (Q1 to Q17), listed in the plan.
- **Live check on staging after the deploy** (about 25 minutes):
  - Q4: the target group shows healthy with the new path.
  - Q5: `curl -I http://v3.policyatlas.uk` returns a 301 to `https://`.
  - Q11: `curl -sI https://api.v3.policyatlas.uk/healthz` carries no `server:` header, and
    an API log line shows the tester's public address as the client.
  - Q13: the listener's security policy in the console reads the recommended TLS policy.
  - Q16: 50 requests with a fake token carrying random key ids in 10 s produce at most two
    `auth.jwks_refreshed` lines in the logs, and a real sign-in still works during them.
  - Q12, Q17: the console shows pool deletion protection on and 35-day retention on the
    production cluster after the production deploy.
  - Q8, before each deploy: the per-user task count for the last 365 days on that
    environment, with anyone at or over 50 listed for the owner.
- **Operator step from H-06, not code:** after Q1 is live, search the existing CloudWatch
  logs of both environments for `"locals"`, `api_key`, `password` and `dbadmin`. If a secret
  value appears, rotate the database password and the provider keys. Recorded in
  verification as done or not done.
  - Q6: a password reset refuses 11 characters.
  - Q2: the same waitlist email twice gives 201 twice and one row.
  - Q7: a tester with three running runs is refused a fourth with the mapped message.
  - Q8: an admin creates a task with no quota message and sees no banner; a tester whose
    count is set to the limit (by the quota value on staging or by seeded rows) sees the
    banner, is refused a new task with the mapped message, and `/me` reports `used` and
    `limit`.
  - Q10: `user offboard` on a staging test account, then sign-in is refused at Cognito.
- Production follows at the next release with the same checks except Q10.

## Verification evidence expected

Command results, the staging check notes, the `EXPLAIN ANALYZE` pair for Q9, the diff
summary, and the ADR link, in `verification.md`.

## Risk tier & review focus

**Tier 4** (migration, production config, auth-adjacent behaviour). Review stack: contract
verifier, `/code-review`, `/security-review`, adversarial review of contract and plan,
simplification pass, human deep review. Focus: the two admission sites agree (Q7), the
quota cannot be bypassed by another creation path (Q8; the only API path is `create_task`,
the runtime CLI path has no owner), the Q9 filter changes no result set, Q10 cannot
leave an account half-removed without saying so, Q16 cannot make a real key rotation fail
(a genuinely new Cognito key must still be picked up within the refresh window; the
frontend retries once on a 401), Q7 counts reservations as well as rows so parallel starts
cannot pass, and Q14 never marks a run interrupted that another dispatch owns.
