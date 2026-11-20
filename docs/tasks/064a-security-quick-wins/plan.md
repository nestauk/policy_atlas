# Implementation plan: 064a-security-quick-wins

> Status: **approved by the owner 2026-11-16 (Karlis Kanders), draft 2**, with § Owner items
> 1 to 4 confirmed the same day and item 5 (the CloudWatch search) deferred to after the
> slice by the owner. Draft 1 was reviewed by two read-only lanes the same day (Codex 10
> findings, Opus 23; records in the gitignored `research/`); every finding is folded here or
> into contract revision 2. ADR:
> [0045](../../adr/0045-per-user-run-cap-task-quota-offboarding.md), Accepted 2026-11-16.
> Contract: [contract.md](contract.md) (revision 2, approved). Rubric:
> [rubric.md](rubric.md). Problems Q1 to Q17 and the terms are defined in the contract and
> not restated here. Executor routing follows `docs/agentic-ops/harness.md` § Agent-side
> model routing and the owner's ruling of 2026-09-04: judgment-bearing build work goes to
> `deep-reasoner`, mechanical volume to `fast-worker`, seam design, live runs and
> owner-facing reads stay with the lead. The build runs in a fresh conversation with
> task-cycle-build, opening on Phase 0.

## Order and why

Backend-only problems first (Q1 to Q3), because they are independent and cheap to review.
Then the auth change on its own (Q16), because it is one file, one lock and one test file,
and it must land whole. Then admission, quota and the dispatch fix together (Q7, Q8, Q14,
Q15), because they share the settings plumbing, the error-code list and `routers/runs.py`.
Then the schema phase (Q9), the only migration and the only mid-build full-verify gate.
Then the ops command (Q10), which touches no API code. Infra and container settings last
(Q4 to Q6, Q11 to Q13, Q17), with their own test suite. Docs and the ADR close the build.

## Decisions taken in this plan

| # | Problem | Decision |
|---|---|---|
| P1 | Q1 | Replace `structlog.processors.dict_tracebacks` with `structlog.processors.ExceptionRenderer(structlog.tracebacks.ExceptionDictTransformer(show_locals=False))` (confirmed against structlog 26.1.0 in `uv.lock`: `show_locals=False` removes the `locals` key). `Settings.database_url` becomes `field(repr=False)`. New `tests/core/test_logging.py`: configure JSON logging, raise inside a function whose local holds a planted string, capture the output, assert no `locals` key in any frame and the planted string absent. |
| P2 | Q2 | `waitlist_entry.insert().values(…).on_conflict_do_nothing(index_elements=["email"])` (the `postgresql` dialect insert); if `rowcount == 0` return the same `WaitlistSignupOut` with a fresh `entry_id`. No `IntegrityError` catch, so the request's transaction is never aborted. Remove `already_registered` from `_CONFLICT_CODES`, `errors.ts`, `WaitlistForm.tsx`'s 409 branch, `mock/api.ts` and `docs/specs/system/web-api.md`; `make openapi-sync`. `tests/api/test_waitlist.py`: duplicate gives 201, one row, and a following statement on the same connection succeeds. |
| P3 | Q3 | `safe_error(exc) -> str` in `runtime/harness.py`: `str(exc)` when `type(exc).__module__.startswith("policy_atlas.")` or `hasattr(exc, "reason")`, else `type(exc).__name__`. Used at `harness.py` lines ~217, ~597 and ~676 and inside `runner.py` `_bounded_error` (~6225, ~6350), each site adding `exc_info=True` to its log call. A `deep-reasoner` lists every `str(exc)` that reaches `events.append` before editing, so the five sites are a verified count, not an assumed one. `tests/runtime/test_harness.py`: the fixture exception classes gain a `reason` attribute where they lack one (the assertions at ~316 and ~455 rely on product-like messages); one new test raises `RuntimeError("SELECT … host=…")` and asserts the payload holds `RuntimeError`. |
| P4 | Q16 | `JwksProvider` gains `_refresh_lock = threading.Lock()`, `_last_refresh_at`, and the module constant `_MIN_REFRESH_INTERVAL_SECONDS = 30`. `get_key`: read the key under no lock; on a miss or an expired cache, `with self._refresh_lock:` re-check (another thread may have refreshed), and refresh only if `monotonic() - _last_refresh_at >= interval`, setting `_last_refresh_at` **before** the network call so a slow fetch holds the slot. `_missing_since` and `_NEGATIVE_CACHE_TTL_SECONDS` are deleted. `refresh`: on `httpx.HTTPError`, `OSError` or `ValueError` keep the old `_keys`, log `log.error("auth.jwks_refresh_failed", error_class=…)`, re-raise only when `_keys` is empty; on success log `log.info("auth.jwks_refreshed", key_count=…)`. `get_current_user` and `get_optional_user` drop `async`; the latter calls the former directly. Tests in `tests/api/test_auth.py` (existing file, or new): forty threads released by a `threading.Barrier` on an unknown key id hit the fake JWKS once; a failing fetch after a good one still verifies a valid token; a key added to the fake JWKS is found after the interval; `inspect.iscoroutinefunction` is false for both dependencies. |
| P5 | Q7 and Q8 settings | `Settings` gains `runs_per_user: int` (`RUNS_PER_USER`, default 3) and `task_quota_per_year: int` (`TASK_QUOTA_PER_YEAR`, default 50). `pa_config.json` gains both keys in `staging` and `prod`; `policy_atlas_stack.py` passes them next to `RUN_EXECUTOR_MAX`; `test_synth.py` and `test_service_wiring.py` pin them. |
| P6 | Q7 | `user_at_run_cap(conn, *, user_id, cap) -> bool` in `routers/common.py`, called under `_dispatch_lock`: `running` = `capability_run` rows with `parentless_walk()`, `executor_walk()`, status `running`, joined to `task` on `task_id` where `task.owner_user_id == user_id`; `reserved` = the tasks in `executor_reservations()`'s set (`_dispatching_tasks - _search_reservations`, exposed as a function returning the set) whose `task.owner_user_id == user_id`, by one `SELECT … WHERE task_id IN (…)`; refuse when `running + reserved >= cap`. The three sites call it right after `executor_full`: `create_run` and `start_toc_check` raise `ApiConflict("user_capacity", "you already have N runs in progress")`; `admit_and_mint` raises `LonglistRefused("user_capacity", …)`, which `http_error` already translates. `admit_and_mint` requires `user_id` when `check_capacity` is true. `user_capacity` joins `_CONFLICT_CODES`, `errors.ts` ("You already have 3 runs in progress. Wait for one to finish.") and `web-api.md`. The resume path in `continuation.py` is read and left uncapped (owner item 1). Tests per site in `test_runs_router.py` and the longlist router tests: three running rows for user A, fourth refused; user B admitted; a `paused` row not counted; two tasks of user A in the reservation set with one running row refused at cap 3. |
| P7 | Q8 | In `create_task`, before the insert: `if not _is_admin(conn, user.user_id) and tasks_created_since(conn, user.user_id, days=365) >= settings.task_quota_per_year: raise ApiConflict("task_quota", …)`. `tasks_created_since` is a four-line count in `routers/common.py` using `func.now() - text("interval '365 days'")`. `test_admin_leg.py` `_IS_ADMIN_READERS` gains `"routers/tasks.py": {"create_task"}`, its comment block and the `_is_admin` docstring gain the fifth reader, ADR 0045 amends ADR 0033 decision 4. `task_quota` joins `_CONFLICT_CODES`, `errors.ts` ("You have reached the limit of 50 tasks per year. Contact the Policy Atlas team if you need more.") and `web-api.md`. `NewTaskView.tsx`'s error branch shows the mapped message for a known code instead of "Try again". **Banner:** `MeOut` gains `task_quota: TaskQuotaOut | None` (`used: int`, `limit: int`); `get_me` fills it with `tasks_created_since` and `settings.task_quota_per_year`, or `None` when `row["is_admin"]` (the flag is already read there, so the reader list does not grow again). `frontend/src/views/QuotaBanner.tsx`, rendered in `AppShell.tsx` directly after `SensitiveInfoBanner`, reads `task_quota` from the `/me` store and shows the contract's sentence when `used >= limit`; no dismiss control; `role="status"`; `print-hide`. The tone and spacing follow `SensitiveInfoBanner` but the colour is the `frontend-designer`'s call, because two red bands stacked read as one. `mock/api.ts` `/me` reply gains the field. Tests in `test_tasks_router.py`: 50 rows refuse the 51st; an admin is admitted; a row with `created_at` 366 days ago is not counted; archived rows are counted. `test_me.py` (or the existing `/me` tests): `used` and `limit` for a user, `null` for an admin. `QuotaBanner.test.tsx`: renders at the limit, not below it, not for `null`. A SQL snippet for the pre-deploy count per user goes in `DEPLOYMENT.md`. |
| P8 | Q14 and Q15 | `create_run` passes `capability_run_id=uuid.uuid4()` to `_dispatch_run` (the parameter exists; `run_plan` and `_await_new_run` accept it). In `_dispatch_run`'s `except Exception` branch, after the log line: `continuation.mark_interrupted_best_effort(engine, task_id=task_id, capability_run_id=capability_run_id)` when the id is not `None`; no lookup by task. `confirm_expired` joins `_CONFLICT_CODES`, `errors.ts` ("This confirmation has expired. Review the latest check-in and confirm again.") and `web-api.md`. Tests: a `run_plan` stub that raises leaves that id `interrupted` and a different `running` row on the same task untouched, and a second start is admitted; the check-in route returns 409 with `confirm_expired` where it returned 500. |
| P9 | Q9 | `effective_screen_rows`: `partition_by=(task_id, evidence_scope_id, task_source_snapshot_id)`. No signature change, no caller change (22 call sites stay as they are). Migration after `f5a1c8e93b27`, modelled on `a3d8f6c1e2b4_document_store_expand.py` lines 123 to 152: inside `autocommit_block()`, drop an invalid leftover index if present, then `CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ssr_task_scope_snapshot ON source_screening_result (task_id, evidence_scope_id, task_source_snapshot_id)`; downgrade `DROP INDEX CONCURRENTLY IF EXISTS` in the same block. `schema.py` declares the same `Index`. Tests: the migration round-trip; a parity test on a two-task fixture with several generations and stages asserting the subquery's rows are identical before and after the partition change. Verification: `EXPLAIN ANALYZE` of `included_source_count` on the dev database seeded to a few thousand rows, before and after, showing the task filter applied below the window node and the index used. |
| P10 | Q10 | `commands.offboard_user(conn, cognito, *, pool_id, email=None, sub=None) -> Offboarding`: resolve the person (by `sub`, or by stored email, or by Cognito email lookup when there is no `app_user` row, using the existing resolvers); call `admin_disable_user` then `admin_user_global_sign_out`; if there is an `app_user` row and it has an `org_id` or `is_admin`, call `de_enrol_user`, else skip with a reported reason; `UPDATE task SET is_public = false WHERE owner_user_id = … AND is_public`; return counts and the steps taken. When `is_admin` was cleared, the CLI emits the same admin trace line as `admin revoke`. Cognito first, so a database failure leaves a disabled account that a rerun completes; the docstring and `DEPLOYMENT.md` say so. `cli.py` adds `user offboard (--email | --sub)` through the CLI's existing confirmation hook; `test_ops_structure.py`'s command list gains it. Tests in `tests/ops/test_ops_commands.py` with the fake Cognito client: the rubric's Q10 list. |
| P11 | Q4 | `policy_atlas_stack.py`: health check `path="/healthz"`. `app.py`: `async def healthz`. `scripts/deploy.sh`: after `services-stable`, one `curl --fail https://<api>/readyz` with a short retry loop, failing the deploy when it never returns 200. Synth assertion for the path; `inspect.iscoroutinefunction(healthz)` in the app tests. |
| P12 | Q5, Q6, Q12, Q13 | `policy_atlas_stack.py`: both CloudFront behaviours `viewer_protocol_policy=REDIRECT_TO_HTTPS`; `minimum_protocol_version=SecurityPolicyProtocol.TLS_V1_2_2021` on the distribution (explicit pin of today's default). `cognito_auth.py`: `min_length=12`, `deletion_protection=True`. `network_stack.py`: `ssl_policy=elbv2.SslPolicy.RECOMMENDED_TLS` on the HTTPS listener. Synth assertions for each; `test_synth.py` lines ~296 and ~999 update their pinned values. |
| P13 | Q11 | Dockerfile `CMD` becomes `["uvicorn", "policy_atlas.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "125", "--proxy-headers", "--no-server-header"]`. `policy_atlas_stack.py` sets `FORWARDED_ALLOW_IPS` in the container environment to the VPC CIDR the network stack already exposes (uvicorn reads that variable). Line assertion in `tests/ops/test_dockerfile_lines.py`; synth assertion for the variable. |
| P14 | Q17 | `db_config.json` gains `backup_retention_days` (staging 7, prod 35); `database_stack.py` reads it where it reads the instance sizes. Synth assertions for both environments: the suite loads staging only today, so a production synth case is added for this value. CDK applies a retention change in place. |
| P15 | Docs | `infra/DEPLOYMENT.md`: the three config keys, `FORWARDED_ALLOW_IPS`, the post-stable readiness check, `user offboard` with the 60-minute token and open-stream notes, the pre-deploy quota count, the H-06 CloudWatch search. `docs/deferred.md`: update the lines Q6, Q10 and Q17 make stale (~2302, ~2315 to 2319, ~2330); add the token and stream window, spend caps, quota display, H-02 body limits, continuation uncapped. ADR 0045 "Per-user run cap, task quota with admin exemption, offboarding": records Q7, Q8, Q10 and Q14's up-front run id, amends ADR 0033 decision 4. `docs/specs/system/web-api.md`: the 409 list. One `docs/specs/log.md` line. |
| P16 | Gates | Full `make verify` at build-open (gate 1), end of Phase 4 (schema, gate 2) and step-6 exit (gate 3, plus `make audit`). Phases 1, 2, 3 and 5 gate on `make verify-fast`; Phase 6 on `make -C infra test` plus the Dockerfile line test. Phases 1 to 3 share no files with Phase 4, which is why they take the fast gate. |

## Phases

| Phase | Problems | Work | Executor | Gate |
|---|---|---|---|---|
| 0 | — | Build-open baseline: `make verify`, `make -C infra test`, seed the dev database and record the Q9 `EXPLAIN ANALYZE` "before". | lead (one command whose output the owner reads) | full verify |
| 1 | Q1, Q2, Q3 | P1, P2, P3 with tests. | `fast-worker` for P1 and P2 (exact spec); `deep-reasoner` for P3 (site inventory and test fixture judgment) | verify-fast |
| 2 | Q16 | P4: the provider, both dependencies, the threaded test. | `deep-reasoner` (auth path, lock discipline) | verify-fast |
| 3 | Q7, Q8, Q14, Q15 | P5, P6, P7, P8: settings, config, stack env, the two counts at three sites, the up-front run id, three error codes, `/me` quota field, frontend strings and the new-task error branch, spec list, tests. The seam (names and signatures above) is designed here; implementation delegated. | `deep-reasoner` for the backend (three admission sites must agree; multi-file); `frontend-designer` for `QuotaBanner.tsx`, the `AppShell` slot, the new-task error branch and their vitest files (the only user-facing surface of the slice) | verify-fast |
| 4 | Q9 | P9: partition key, migration, schema index, parity test. | `deep-reasoner` | **full verify** |
| 5 | Q10 | P10: command, CLI wiring, trace, tests. | `deep-reasoner` (Cognito ordering, the three resolution cases) | verify-fast |
| 6 | Q4, Q5, Q6, Q11, Q12, Q13, Q17 | P11 to P14: settings, Dockerfile line, environment variable, deploy-script check, synth and line assertions. | `fast-worker` | `make -C infra test` + Dockerfile line test |
| 7 | docs | P15. | lead (owner-facing prose and the ADR) | step-6 exit: full verify + `make audit` |
| staging | all | Push to `dev`, wait for the staging deploy, run the contract's live checks and the pre-deploy quota count, record in `verification.md`. | lead | — |

Every `lead` mark: Phase 0 is one command whose output the owner reads; Phase 7 is
owner-facing prose and a decision record; the staging check needs the owner's accounts.

## Risks and how the plan meets them

- **Q7 parallel starts.** Draft 1 counted rows only, so N simultaneous starts by one user
  were admitted N times. P6 counts the reservation set under the lock as well, which is the
  same window the global cap uses.
- **Q7 longlist path.** Draft 1 missed `admit_and_mint`. P6 names the three sites and tests
  each.
- **Q8 clock.** The count uses the database clock in SQL, never the API host's. The test
  fixes `created_at` explicitly.
- **Q8 at deploy.** Someone already at or over 50 tasks in the past year is blocked the
  moment the slice lands. The pre-deploy count makes that visible before the deploy; the
  owner rules per person (owner item 2).
- **Q9 result change.** `task_id` is constant within a `(evidence_scope_id,
  task_source_snapshot_id)` partition (`fk_ssr_scope_task`), so adding it to the partition
  key changes no ranking. The parity test proves it; the plan push-down is what `EXPLAIN`
  must show.
- **Q16 key rotation.** With a 30-second floor, a token signed by a brand-new key fails for
  at most 30 s after first sight; the frontend already refreshes and retries once on a 401.
- **Q16 thread pool.** Making both dependencies synchronous moves every authenticated
  request's token check onto the 40-thread pool. Warm checks are sub-millisecond; the lock
  is held only across the refresh decision and the fetch. `/healthz` goes the other way
  (P11) so the health check needs no pool thread at all.
- **Q14 ownership.** Only the id this dispatch minted is marked. No task lookup, because the
  reservation is dropped once the row exists and another surface can start a walk in that
  gap.
- **Q11 forwarded addresses.** Trusting `*` would let a client set the logged address by
  writing the leftmost `X-Forwarded-For` entry. The VPC range trusts only the load
  balancer. Nothing in the API makes decisions on the client address, so a wrong value is a
  logging defect, not an access defect.
- **Q4 behaviour change.** With `/healthz`, a database outage no longer replaces the
  container; runs survive a short outage. The deploy-time readiness call restores the one
  check the old path gave for free.
- **Q10 resolution.** Three cases: enrolled (full path), already de-enrolled (Cognito plus
  public links, de-enrol skipped), no `app_user` row (Cognito only). Each is reported and
  tested.

## Owner items at the plan gate

1. **Continuation stays uncapped.** Resuming a paused walk after a check-in has no capacity
   check today and the plan adds none, because the person's decision is already committed
   when the resume runs. Confirm.
2. **Users already over the task quota** (ruled 2026-11-16): they see the quota banner and
   are refused new tasks; no other treatment. The pre-deploy count only tells the owner
   who that is. A per-user allowance column is out of scope for this slice.
3. **Rolling 365 days**, not a calendar year. Confirm.
4. **`already_registered` removed** with no announcement; the splash form is the only
   client. Confirm.
5. **Checking the old logs for leaked secrets** (H-06 step 4; owner, 2026-11-16: done
   after this slice, not inside it). The logging fix stops new leaks; it does nothing
   about log lines already stored. CloudWatch keeps them for 30
   days. Someone with console access runs one Logs Insights query on each environment's
   log group for `locals`, `api_key`, `password` and `dbadmin`. If a secret value shows up,
   the database password and the provider keys are rotated. The lead writes the query into
   `DEPLOYMENT.md`; the owner runs it once and records the result in `verification.md`.
