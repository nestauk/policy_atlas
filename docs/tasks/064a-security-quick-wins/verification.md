# Verification: 064a-security-quick-wins

Evidence for the slice. Problems Q1 to Q17 are defined in [contract.md](contract.md); the
decisions in [ADR 0045](../../adr/0045-per-user-run-cap-task-quota-offboarding.md).
Public-safe: no secrets, no production data; the `EXPLAIN` output is from the local
development database.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline, HEAD 700e754c) | pass | gate 1 |
| `make -C infra test` (baseline) | pass | 116 passed |
| `make verify` (gate 2, after Phases 1, 2, 4, 5) | pass | one run covered the four phases; they were then committed by path |
| `make -C infra test` (Phase 6, run by the build) | pass | 119 passed (three new: production retention 35, forwarded range, redirect) |
| `make frontend-verify` (Phase 3 frontend, run by the build) | pass | 138 files, 1,991 tests, build OK |
| `make verify` (step-6 exit, all seven phases in the tree) | pass | gate 3; includes the infra suite and the frontend chain |
| `make audit` | **fail** | two advisories in dependencies this slice does not touch: `opentelemetry-api` 1.45.1 (CVE-2026-126360, fix 1.45.2) and `tornado` 6.6 (CVE-2026-126347, fix 6.6.1). Dependency changes are gated; left for the owner. Not caused by this slice: the same run is red on `dev`. |

## Checks beyond the build

- **Named tests, one per problem** (all run against the `policy_atlas_test` database):
  - Q1 `tests/core/test_logging.py`: no `locals` key in any frame of a JSON error log and
    the planted string absent; `repr(Settings)` hides the database URL. Fails on the old
    code (checked by swapping HEAD's `logging.py` back in: 1 failed).
  - Q2 `tests/api/test_waitlist.py`: the same email twice gives 201 twice and one row.
  - Q3 `tests/runtime/test_harness.py` (one case per harness site) and
    `tests/runtime/test_runner.py` (the backstop): a `RuntimeError("SELECT … host=…")`
    persists as `RuntimeError` only; a product-shaped exception keeps its message and reason.
  - Q9 `tests/core/test_migration_064a_ssr_index.py` (round trip and the invalid-index
    recovery) and `tests/evidence_search/assess/test_screen_partition_parity.py` (two
    tasks, two scopes each, two generations, both stages, failed rows: identical row sets).
  - Q10 `tests/ops/test_ops_commands.py`: disable then global sign-out in that order;
    public tasks made private, others untouched; already de-enrolled handled; no
    `app_user` row is Cognito-only; a Cognito failure leaves the database untouched; an
    administrator's offboarding carries the revoke trace; the CLI reaches the command.
  - Q16 `tests/api/test_jwks_provider.py`: forty threads behind a barrier on unknown key
    ids cause one fetch (fails on the old code: 40); a failed refresh keeps the old keys
    and a valid token still verifies; a new key is found after the window; neither
    dependency is a coroutine function.
  - Q7 `tests/api/test_runs_router.py`, `test_longlist_start.py`, `test_shortlist_start.py`:
    at `create_run` and `admit_and_mint` all four cases (fourth start refused, another
    user admitted, paused not counted, two reservations plus one row refused at 3); at
    `start_toc_check` refused for A and admitted for B (the counting is shared code); a
    collaborator starting on A's task while A holds three is refused.
  - Q8 `tests/api/test_tasks_router.py`: the 51st task in a year refused with
    `task_quota` at the real default of 50; an administrator admitted; a row 366 days old
    not counted; archived rows counted. `test_me_router.py`: `used` and `limit` for a
    user, `null` for an administrator. `test_admin_leg.py`: the reader list gains
    `routers/tasks.py: create_task`. Frontend `QuotaBanner.test.tsx`: shows at and above
    the limit, not below, not for `null`; `NewTaskView.test.tsx`: the `task_quota`
    sentence for the code, the fallback otherwise.
  - Q14 `tests/api/test_runs_router.py`: a `run_plan` stub that writes the minted row and
    a running child, then raises, leaves only the minted id `interrupted`, the child
    `running`, and a second start is admitted.
  - Q15 `tests/api/test_check_ins_router.py`: the expired confirmation returns 409
    `confirm_expired`.
  - Q4 `tests/api/test_cors_and_envelope.py`: `/healthz` is a coroutine function; synth
    pins the health path. Q5, Q6, Q12, Q13, Q17 `infra/tests/unit/test_synth.py`:
    `redirect-to-https` on both behaviours, `TLSv1.2_2021`, `MinimumLength` 12,
    `DeletionProtection` ACTIVE, listener `ELBSecurityPolicy-TLS13-1-2-2021-06`,
    retention 7 on staging and 35 on a production synth. Q11
    `tests/ops/test_dockerfile_lines.py` (the three flags) and the synth tests
    (`FORWARDED_ALLOW_IPS`).
- **Q9 `EXPLAIN ANALYZE` pair** on the local development database (PostgreSQL 17.11,
  39,682 `source_screening_result` rows across 87 tasks; the `included_source_count`
  query for the task with the most rows, 1,221):

  | | Before | After |
  |---|---:|---:|
  | Scan | Seq Scan, all 39,682 rows | Bitmap Index Scan on `ix_ssr_task_scope_snapshot`, 1,221 rows |
  | Sort | external merge, 3,032 kB on disk | quicksort, 153 kB in memory |
  | Rows into the window | 39,682 | 1,221 |
  | Execution time | 37.1 ms | 2.0 ms |
  | Result | 51 | 51 |

  The task filter sits below the window node in the "after" plan (`Index Cond: task_id =
  …`), which is what the partition-key change was for. Full plans in the build
  transcript; the shape is what matters.

## End-to-end command

The contract pins the live check to **staging after the deploy** (about 25 minutes, the
owner's accounts), so no local end-to-end run was bought for this slice beyond the test
suite and the `EXPLAIN` pair above. The local thread driven was:

```bash
cd backend && DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test" \
  uv run pytest -n 2 tests/core/test_logging.py tests/api/test_waitlist.py \
  tests/runtime/test_harness.py tests/runtime/test_runner.py tests/api/test_jwks_provider.py \
  tests/core/test_migration_064a_ssr_index.py tests/evidence_search/assess/test_screen_partition_parity.py \
  tests/ops tests/api/test_runs_router.py tests/api/test_tasks_router.py tests/api/test_me_router.py \
  tests/api/test_check_ins_router.py tests/api/test_admin_leg.py tests/api/test_cors_and_envelope.py \
  tests/ops/test_dockerfile_lines.py -q
cd backend && uv run alembic upgrade head   # local dev database, then the EXPLAIN pair
make -C infra test
```

The staging checks to run after the deploy, from contract § Acceptance checks:

```bash
curl -I http://v3.policyatlas.uk                      # Q5: 301 to https://
curl -sI https://api.v3.policyatlas.uk/healthz        # Q11: no server: header
for i in $(seq 50); do curl -s -o /dev/null -H "Authorization: Bearer $(python3 -c 'import base64,json,os;h=base64.urlsafe_b64encode(json.dumps({"alg":"RS256","kid":os.urandom(8).hex()}).encode()).rstrip(b"=").decode();print(h+".e30.x")')" https://api.v3.policyatlas.uk/api/v1/me; done   # Q16: at most two auth.jwks_refreshed lines in 10 s
```

plus the console reads (Q4 target group healthy on `/healthz`, Q13 listener policy, Q12
and Q17 on production), the pre-deploy quota count from `DEPLOYMENT.md` § 4, a password
reset refusing 11 characters (Q6), the same waitlist email twice (Q2), a fourth run
refused (Q7), the quota banner and refusal for a seeded tester and none for an
administrator (Q8), and `user offboard` on a staging test account followed by a refused
sign-in (Q10). Results go in this section when run.

## Diff summary

- **Phase 1 (Q1 to Q3, commit 7e5ad3be).** `core/logging.py` renders tracebacks with
  `ExceptionDictTransformer(show_locals=False)`; `Settings.database_url` is
  `field(repr=False)`. `routers/waitlist.py` inserts with `ON CONFLICT DO NOTHING` and
  always answers 201; `already_registered` is gone from the conflict codes, the splash form,
  the mock API and the spec. `runtime/harness.py` gains `safe_error`; the three harness
  sites and the runner's `_bounded_error` use it, each logging the full exception with
  `exc_info=True`.
  - *Deviation, flagged:* the contract counted five `str(exc)` sites that reach the event
    log. The build's inventory found **four** (three in `harness.py`, one runner backstop
    through `_record_failure_backstop`); two more runner sites write to the server log only
    and now also pass through `_bounded_error`. The `ClassName: ` prefix on the synthesise
    site is gone, so product exceptions show their message alone. Two runner tests that
    raised a plain `RuntimeError` on purpose now expect `"RuntimeError"`, each with a
    one-line note.
- **Phase 2 (Q16, commit 4c4f5e56).** `JwksProvider` refreshes at most once per 30 s
  under a lock claimed before the network call; the per-key negative cache is gone; a
  failed refresh keeps the old keys and logs `auth.jwks_refresh_failed` (class name only,
  no URL); `get_current_user` and `get_optional_user` are plain functions. The existing
  test named "negatively cached" still passes, now because of the window.
- **Phase 4 (Q9, commit 4232b245).** `effective_screen_rows` partitions by `task_id`
  first; migration `b1e7c3a9d5f2` builds the index `CONCURRENTLY` with invalid-index
  recovery; `schema.py` declares the same index.
- **Phase 5 (Q10, commit df6478c1).** `commands.offboard_user` and `user offboard
  (--email | --sub)`: Cognito disable and global sign-out first, then de-enrol only if
  still enrolled or an administrator, then `task.is_public = false` for the person's
  tasks; the three resolution cases are reported in the steps. An administrator's removal
  emits the same trace as `admin revoke`. Two choices the contract left open: no Cognito
  account at all refuses with "Nothing was changed"; a Cognito failure is raised as an
  `OpsError` chained to the original, not a raw traceback.
- **Phase 3 (Q7, Q8, Q14, Q15).** `Settings` gains `runs_per_user` and
  `task_quota_per_year`; both keys in `pa_config.json` and the container environment.
  `user_at_run_cap` and `executor_reservation_tasks` live in `routers/runs.py` next to
  `executor_full` (`common.py` cannot import the reservation sets without a cycle); the
  three sites call it after the global check and before their own reservation, passing
  the task's owner. `admit_and_mint` gains `user_cap`; `open_longlist_walk` and
  `open_shortlist_walk` carry it, so five routes in `check_ins.py`, `longlist.py` and
  `task_agent.py` gained a `settings` dependency. `tasks_created_since` in `common.py`
  uses `make_interval` with the day count as a bound parameter. `create_task` refuses at
  the quota unless `_is_admin`; `get_me` fills `task_quota`. `create_run` mints the run
  id up front (the `existing_ids` lookup became dead code and was removed);
  `_dispatch_run` marks only that id interrupted. `confirm_expired` and the two new
  codes join `_CONFLICT_CODES`. Frontend: three sentences in `errors.ts`, the new-task
  error card uses `actionFailedNotice`, `QuotaBanner.tsx` (yellow tint, the
  `ReconnectingBanner` treatment, since DESIGN.md allows a solid fill only on the safety
  banner) after `SensitiveInfoBanner` in `AppShell.tsx`, `/me` fixtures gain the field.
  - *Deviations, flagged:* (1) the cap is checked against the task owner, not the
    caller (ADR 0045 § As built 1); (2) the reader-list walk also counts `_is_admin`
    calls outside `access.py` (§ As built 2); (3) the error sentences carry no numbers
    and `useCreateTask` invalidates `/me` (§ As built 3); (4) `start_toc_check` has two
    cap cases rather than four; (5) three router files outside the contract's list
    changed to carry the setting to `admit_and_mint`.
- **Phase 6 (Q4 to Q6, Q11 to Q13, Q17).** Stack: `/healthz`, `REDIRECT_TO_HTTPS` on
  both behaviours, `TLS_V1_2_2021`, `FORWARDED_ALLOW_IPS = vpc.vpc_cidr_block` (the VPC
  is created by the network stack, so there is no config value to read; under synth the
  lookup yields a placeholder). Cognito: 12 characters, deletion protection. Listener:
  `RECOMMENDED_TLS`. Database: retention from `db_config.json`. Dockerfile `CMD` adds the
  three flags. `app.py`: `healthz` is `async def`. `deploy.sh`: ten `/readyz` tries after
  `services-stable`. `test_image_hygiene.py` pinned the old `CMD` and changed with it.
- **Docs.** `DEPLOYMENT.md` (readiness check, pre-deploy quota count, the H-06 log
  search, three environment variables, `user offboard`, rollback notes, the per-user cap
  in the capacity paragraph), `docs/deferred.md` (three stale lines and § Security quick
  wins), `web-api.md` (409 list, `/me`, five readers), `docs/specs/log.md`, ADR 0045
  § As built, `pr_draft.md`.

## Review findings

_Added after the review stack (step 7)._

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review:**
- **`/simplify`:**
- **`/okf validate`:**

## Rubric status

1. Contract rows Q1 to Q17 true in code: **holds**, with the flagged deviations above
   (Q3 four sites not five; Q7 checked against the owner).
2. `make verify` and `make -C infra test`: **holds locally**; the staging live checks
   are **not yet run** (they need the deploy).
3. No gated change beyond the list: **holds** (one index migration, three config keys,
   six infra settings, the `CMD` and one environment variable, one deploy-script check,
   three codes added and one removed, spec and OpenAPI). Three router files outside the
   contract's "In" list changed to carry a setting; no new seam.
4. No generated files edited by hand: **holds** (`make openapi-sync` run twice).
5. No tests weakened: **holds**; the reader test gains exactly `routers/tasks.py:
   create_task` and its walk is stricter; two runner tests changed their expected error
   text with a note; `test_image_hygiene.py` and `test_service_wiring.py` changed only
   their pinned values.
6. One failing-on-old-code test per problem: **holds** for the tests listed above; "fails
   on the old code" was demonstrated for Q1 and Q16 and follows by construction for the
   others (new codes, new paths, new index).
7. Evidence recorded with the `EXPLAIN` pair: **holds**.
8. Deferred seams listed: **holds** (`docs/deferred.md` § Security quick wins).
9. ADR 0045 accepted and `DEPLOYMENT.md` documents the keys and the command: **holds**.
10. Tier 4 review stack: **not yet run** (step 7, fresh conversation).

## Intent & assumptions

- The Q9 partition change is behaviour-preserving because `fk_ssr_scope_task` ties each
  scope to one task; the parity test is the proof, the `EXPLAIN` pair the benefit.
- Offboarding treats project `visibility` as tenancy, not a public link, and leaves it
  alone (owner, 2026-11-16: "unless they are shared with the organisation").

## Known unverified items

- `AdminUserGlobalSignOut` on an already disabled account is assumed to succeed (the
  offboard rerun path depends on it); confirmed at the Q10 staging check, not before.
- The operator's IAM policy must allow `cognito-idp:AdminDisableUser` and
  `AdminUserGlobalSignOut`; the CLI runs from the operator's own credentials, so no infra
  change was made. Checked at the staging run.

## Public safety

Logs and plans above carry no secrets or user text. The Q1 test uses a planted fake
value. The `EXPLAIN` output is local.

## Review handoff (step-7/8 inputs)

- **Executor provenance (family flip):** Q1, Q2 `fast-worker`; Q3, Q9, Q10, Q16 and the
  Phase 3 backend `deep-reasoner`; frontend `frontend-designer`; Phase 6 `fast-worker`;
  docs, the `EXPLAIN` pair, the stray-format recovery and the commits: the lead.
- **Adjudication items:** the Q3 site count (four, not five); the dropped `ClassName: `
  prefix; the Q10 refusal choices above; the `test_unknown_kid_is_negatively_cached…` name
  now describing a window, not a negative cache (rename or leave).
- **Build incidents:** a `fast-worker` ran `ruff format` over `api/` with a stray line
  length and reformatted 29 files it did not own; the lead confirmed by syntax-tree
  comparison that every one was identical to HEAD apart from formatting and restored
  them. Five concurrent mypy runs corrupted `.mypy_cache` (a phantom `attr-defined`
  error in an unchanged `conftest.py`); clearing the cache fixed it.
- **Knowledge candidates:**
  - A pytest run outside `make test` must set `DATABASE_URL` to the `*_test` database or
    conftest refuses; every delegated agent hit this once. Worth a line in AGENTS.md.
  - Parallel mypy runs sharing one `.mypy_cache` can produce phantom errors in untouched
    files; clear the cache before believing an error in a file nobody edited.
  - A window function's partition key can include a column that is constant within the
    partition at no cost to the result, and doing so lets PostgreSQL push an equality
    filter on that column below the window node (37 ms to 2 ms here).
  - A per-key negative cache does not bound fetches when the attacker chooses the key;
    the bound has to be on the fetch itself (one per interval, under a lock claimed
    before the call).
  - uvicorn's `--proxy-headers` with `FORWARDED_ALLOW_IPS=*` lets the client write the
    logged address; trust the VPC range only.

## Deferred work

Listed in [docs/deferred.md](../../deferred.md) § Security quick wins (task 064a seams).
