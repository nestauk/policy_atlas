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
| `make -C infra test` (Phase 6, run by the build) | pass | 119 passed (three new: production retention 35, forwarded range, listener TLS policy; the redirect is an assertion added to an existing test) |
| `make frontend-verify` (Phase 3 frontend, run by the build) | pass | 138 files, 1,991 tests, build OK |
| `make verify` (step-6 exit, all seven phases in the tree) | **claimed pass, not reproducible** | gate 3 as the build recorded it. The review's self-verify gate (below) found one pre-existing test red from Phase 1 onward, so this claim and the gate-2 claim above cannot have been true on the committed tree. Treated as a finding (§ Review findings, contract verifier 1). |
| `make audit` (build) | **fail** | two advisories in dependencies this slice does not touch: `opentelemetry-api` 1.45.1 (CVE-2026-126360, fix 1.45.2) and `tornado` 6.6 (CVE-2026-126347, fix 6.6.1). Not caused by this slice: the same run was red on `dev`. |
| `make audit` (after the owner's go, 2026-11-16) | pass | the owner asked for the fix before the PR: `uv lock --upgrade-package` on both (`opentelemetry-api` 1.45.2, `opentelemetry-sdk` 1.45.2, `opentelemetry-semantic-conventions` 0.66b2, `tornado` 6.6.1; lock file only, no `pyproject.toml` change). The app imports with the new versions. "No known vulnerabilities found." |
| `make verify` (review self-verify gate, run 1, HEAD edee7a0e) | **fail** | 2 failed, 4,821 passed: `test_search_single_pass.py::test_generation_failure_raises_and_harness_records_component_failed` (pinned a plain `RuntimeError`'s message that Q3 now reduces to the class name; missed by the build's Q3 inventory) and `test_runs_router.py::test_a_failed_dispatch_interrupts_only_the_walk_it_minted` (waited on the dispatch reservation, which `create_run` drops as soon as the row exists; passed alone three times). Both tests fixed. |
| `make verify` (run 2, after the two test fixes) | **fail** | 1 failed, 4,822 passed: `test_judge_commits.py::test_a_retried_judge_skips_the_links_it_wrote_and_leaves_no_duplicates`, a file this slice does not touch. Its captured output shows a stray theory-of-change dispatch thread from an earlier test in the same worker colliding on `uq_event_log_task_sequence` before any 064a code ran. Passed in run 1 and three times alone: a pre-existing isolation flake, not this slice's. |
| `make verify` (run 3, after every review fix) | see § Review findings | the full chain, run to the end |
| CI `verify` on the first push (runs 43906305029, 43907597097, 43909350980) | **fail** | 1 failed, 4,829 passed: `test_cors_and_envelope.py::test_healthz_is_async_so_it_needs_no_pool_thread` called `create_app()` bare, which reads `OIDC_JWKS_PATH` from the environment; locally the dev-issuer key file exists, on CI it does not. Fixed by building the app with explicit `Settings` and a throwaway key, like the file's other test. Reproduced locally with the auth variables unset, then green. |
| CI `verify` on the healthz fix (run 43921736642) | **fail** | the healthz test passed; 1 failed, 4,829 passed: `test_check_steps.py::test_an_as_drawn_diagram_gets_found_routes_as_one_suggestion`, the same `uq_event_log_task_sequence` exhaustion as local run 2, in a different ToC test: a check walk's six-child fan-out out-ran the appender's 32 retries on the loaded runner. Pre-existing ceiling (045 sized the bound per writer, the ToC fan-out is wider and never re-checked it); 064a adds no event writer; `dev`'s last twelve CI runs green. Recorded as a seam in `docs/deferred.md` § Security quick wins and in `docs/knowledge/event-log-sequence.md`. |
| CI `verify` on the records commit (run 43921952259, HEAD 5c5b677e) | pass | all four jobs green (verify, audit, mock-journey, fe-api-smoke); the same tree as the failed run plus two documentation files, so the ToC flake above is load-dependent, not deterministic. |
| `make verify` (run 4, after the administrator run-cap exemption) | pass | EXIT 0: backend 4,830 passed, 1 skipped (the new administrator test in the run); infra tests, typecheck, lint, frontend (138 files, 1,992 tests, build OK) and OKF validate green. |

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
    collaborator starting on A's task while A holds three is refused; an administrator
    holding three is admitted (owner ruling 2026-11-16, after the review stack).
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

Step 7 ran on 2026-11-16 in a fresh conversation. Every line of the slice was Claude-written
(see § Review handoff), so the Codex pass anchored the heterogeneous half; the Claude half
was `/code-review` at `medium`. Lanes: contract verifier (pinned Opus, read-only), Codex
adversarial (read-only rescue job `task-mwjblg8k-dwr1kw`), `/code-review medium`,
`/security-review`, the lead's own read of the product diff, and a trace lane (the Q9
`EXPLAIN` re-run). Every finding below was adjudicated by the lead; "adopted" means fixed
on the branch in the review commit.

- **Lead, before any lane (self-verify gate):** `make verify` was red on HEAD (two tests,
  table above). Adopted: both tests fixed. The waitlist honeypot test had lost its proof
  (it relied on a 409 for a second signup, which Q2 removed, so a 201 proved nothing);
  adopted: it now asserts the stored row's name. The Q9 `EXPLAIN` was re-run through the
  real `included_source_count` construct: bitmap index scan on the new index, 1,221 rows
  into the window, 51 rows out, 1.3 ms — the recorded "after" shape.
- **Contract verifier (Opus):** rubric items 1, 3, 4, 8, 9 pass; 2 failed at HEAD (above);
  5 failed at HEAD on the honeypot test; 6 partial (two of four cap cases at
  `start_toc_check`); 7 partial; 10 pending. Nine flagged deviations: all adopted as-is
  except deviation 6 (the two missing cap cases were added rather than waived) and
  deviation 8 (the Q10 refusal, changed below). One unflagged deviation adopted: Q11 reads
  the address range from the VPC lookup, not `network_config.json`, which has no such
  key; the contract's "leftmost X-Forwarded-For" wording also describes uvicorn wrongly
  (it takes the rightmost untrusted address, the right outcome). High: the green-gate
  claims (adopted as a finding, recorded above and in the failure log). Medium: the Q3
  `reason` rule admits library exceptions (`urllib.error.URLError`, `ssl.SSLError`,
  `UnicodeDecodeError` carry one) — adopted: a `reason` counts only when it is a string
  code (ADR 0045 § As built 7); the Q14 test's "other running run" was a child of the
  minted walk, so a regression to "mark the task's latest parentless walk" would have
  passed — adopted: the other row is now a parentless walk on the same task, finished
  before the re-start assertion; ADR 0033 carried no "amended by" note — adopted. Low:
  `web-api.md` said "no write path reads it" beside the new reader, and described
  `user_capacity` as the caller's — adopted; the ToC editor mapped `capacity` but not
  `user_capacity` — adopted (`Editing.tsx`); contract § Out still excluded the quota
  display the banner provides — adopted (wording); pr_draft Q3 omitted the `reason` rule
  — adopted; the pre-064a drift of the 409 code lists — deferred (not this slice's).
- **`/code-review` (medium, 8 findings):** (1) `offboard_user` refused when the `app_user`
  row exists but the Cognito account is gone, leaving public links live with no command
  to finish — **adopted**, convergent with Codex and the verifier's note on deviation 8;
  the database half now runs and the first step says "no Cognito account in the pool"
  (ADR 0045 § As built 4; two tests). (2) A failed first JWKS fetch with no cached keys
  held the 30 s slot, so a blip at boot refused every token for a window — **adopted**
  (§ As built 6; test). (3) The quota count is a read-then-insert with no lock, so two
  parallel creates can both pass — **declined**: the contract accepts it ("the window is
  one request"). (4) The `reason` rule — adopted, as above. (5) `admit_and_mint` with
  `user_cap=None` returned a 409 reading "you already have None runs" — **adopted**: a
  missing `user_cap` with `check_capacity` raises `ValueError` (test). (6) The
  `user_capacity` sentence says "you" while the cap is counted on the owner — **declined**
  for the sentence (write access is owner-only, so nobody sees the mismatch; deferred
  seam), adopted for `web-api.md`. (7) `DEPLOYMENT.md` § ops CLI and `JUMPBOX.md` still
  listed three Cognito permissions, "nothing more", contradicting the offboard paragraph
  — **adopted**, both docs. (8) `safe_error(exc)[:200]` appears at two sites — **declined**:
  two call sites do not earn a parameter.
- **`/security-review`:** no finding at or above the confidence bar. Examined and held:
  the Cognito `ListUsers` filter (both CLI values pass `_require_filter_safe`; the
  database-sourced subject is a verified JWT subject; the filter grammar has no boolean
  operators); JWKS lookup (an unknown key id ends in 401 only; keys are replaced
  wholesale; the failure log carries the class name only); the run cap and quota keyed on
  the owner and the verified subject, all four web creation paths through `create_task`;
  `FORWARDED_ALLOW_IPS` with uvicorn 0.51's range support and nothing reading the client
  address; the waitlist conflict path; the migration's bound parameters.
- **Adversarial review (Codex, read-only):** six major, one minor. (1) `start_toc_check`
  never released its reservation, so a running check counted as a reservation and a row,
  two of a person's three slots — **adopted** (pre-064a on the global cap, material under
  the per-user cap; § As built 5; a test with a real executor shows the release while the
  walk runs and the queued check chaining on the same worker). (2) `create_run` drops its
  reservation after the 10 s wait whether or not the row was written — **deferred**
  (pre-064a; `docs/deferred.md`). (3) The quota's two clocks (API `created_at`, database
  count) — **declined with a deferred note**: same-region NTP hosts, seconds of skew at a
  365-day boundary. (4) A key set with a `keys` list but no usable RSA key overwrote the
  cache with `{}` — **adopted** (§ As built 6; test). (5) Requests for a known key wait on
  the refresh lock while one fetch runs — **declined**: the contract specifies the lock
  across the fetch and this replaces N fetches with one; serving the stale key during the
  fetch is a deferred seam. (6) The offboard reverse case — adopted, as above. Minor: the
  `policy_atlas.` namespace rule trusts `SearchTransportError`, whose message carries the
  search backend's host — **declined**: the rule is the contract's, the host is a public
  API's; noted as a seam.
- **Trace lane:** no live model runs in this slice's evidence; the only run-time
  evidence is the Q9 plan, re-run above through the real construct.
- **`/simplify`:** not run as a separate pass. `/code-review medium` carried the
  cleanup angles (its finding 8 was the one reuse item, declined with a reason), and a
  second same-family pass over the same diff adds nothing (task-cycle-review § Step 7).
- **`/okf validate`:** inside `make verify` (run 3).
- **Convergence:** the offboard reverse case was raised by three reads (code-review,
  Codex, verifier), the `reason` rule by three (lead, code-review, verifier, with Codex's
  namespace variant), the JWKS edge cases by two lanes from different angles. Unique to
  one lane and adopted: the ToC reservation (Codex), the Q14 test's weak "other run"
  (verifier), the `user_cap=None` message (code-review), the IAM doc contradiction
  (code-review). Each lane earned its place.
- **Fake-done check on the review's own fixes:** no test was relaxed; the two red tests
  changed their pinned text to the rule's output with a note, the Q14 test got stricter,
  the honeypot test regained a proof, and every product change carries a test that fails
  without it.
- **Final gate (run 3, the tree this PR carries):** `make verify` **pass**, run to the
  end: backend 4,829 passed, 1 skipped (the two repaired tests, the strengthened Q14
  test, the two added cap cases, the ToC release test, the two JWKS tests, the two
  offboard tests, the `admit_and_mint` test and the `safe_error` case all in the run);
  typecheck, lint, `make -C infra test` (119 passed), frontend chain (138 files, 1,992
  tests, build OK) and `okf-validate` (217 concepts after the step-8 records, 0
  violations) green. The flaky judge test of run 2 passed.
- **Owner change after the stack, before merge (2026-11-16):** administrators are exempt
  from the per-user run cap, as they are from the task quota. One guard in
  `user_at_run_cap` (`runs.py`) through `_is_admin`, so all three start sites inherit it;
  `_is_admin`'s docstring, the closed reader list in `test_admin_leg.py` (reader (vi)),
  ADR 0033 decision 4, ADR 0045 decision 1, the spec, `infra/DEPLOYMENT.md` and the
  programme map say so; the contract's Q7 row is marked superseded. One test added
  (`test_an_administrator_has_no_run_cap`). `make verify` run 4: see § Commands run.

## Rubric status

Updated by the review stack, 2026-11-16.

1. Contract rows Q1 to Q17 true in code: **holds**, with the deviations the stack
   confirmed (Q3 four sites not five; Q7 checked against the owner; Q11's range from the
   VPC lookup; the `reason` rule narrowed to string codes).
2. `make verify` and `make -C infra test`: **holds after the review fixes** (run 3,
   § Review findings); the build's gate claims were not reproducible. The staging live
   checks are **not yet run** (they need the deploy).
3. No gated change beyond the list: **holds** (one index migration, three config keys,
   seven infra settings for six problems since Q13 pins two, the `CMD` and one
   environment variable, one deploy-script check, three codes added and one removed, spec
   and OpenAPI). Three router files outside the contract's "In" list changed to carry a
   setting; no new seam.
4. No generated files edited by hand: **holds** (`make openapi-sync` run twice;
   `make drift-check` OK in the stack).
5. No tests weakened: **holds after the review fixes**. At HEAD the honeypot test had
   lost its proof unannounced (fixed). The reader test gains exactly `routers/tasks.py:
   create_task` and its walk is stricter; three tests (two runner, one search loop)
   changed their expected error text to the Q3 rule's output with a note;
   `test_image_hygiene.py` and `test_service_wiring.py` changed only their pinned values.
6. One failing-on-old-code test per problem: **holds**; the two missing
   `start_toc_check` cases (paused not counted, reservations counted) were added in the
   stack. "Fails on the old code" was demonstrated for Q1 and Q16 and follows by
   construction for the others (new codes, new paths, new index).
7. Evidence recorded with the `EXPLAIN` pair: **holds**; the pair was re-run in the
   stack through the real construct.
8. Deferred seams listed: **holds** (`docs/deferred.md` § Security quick wins, extended
   with the stack's six seams).
9. ADR 0045 accepted and `DEPLOYMENT.md` documents the keys and the command: **holds**;
   ADR 0033 now carries the "amended by" note.
10. Tier 4 review stack: **ran** (§ Review findings). `/simplify` folded into
    `/code-review medium`'s cleanup angles with the justification recorded there.

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
