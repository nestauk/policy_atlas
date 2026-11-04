# Verification: 057-queued-ingest

Evidence for the slice, filled phase by phase during the build (step 6) and completed at the
step-6 exit. Public-safe: run ids and counts only; no URLs, report text, keys or traces.
Contract: [contract.md](contract.md) (revision 4). Plan: [plan.md](plan.md). Rubric:
[rubric.md](rubric.md). Measurement scripts: `scripts/stage_walls.py` (per-stage wall from
the database and the server logs) and `scripts/step_timeouts.py` (per-step timeouts from
Langfuse), both built in Phase 0 with offline tests under `backend/tests/scripts/`.

## Commands run

| Gate | Command | Result | Notes |
|---|---|---:|---|
| Build-open (gate 1), 2026-11-03 | `make verify` on `e0553f85` | pass | backend 3,888 passed, 1 skipped (7 min 6 s); infra 95 passed; frontend 943 passed; lint, typecheck, okf-validate, build green |
| End of Phase 2 (gate 4), 2026-11-03 | `make verify` on the tree holding Phase 2 plus Phase 3 in progress and the width constants | pass after one fix | backend 4,017 passed, 1 failed (`test_option_searches_run_at_width_four`: seeded 8 options against the new width of 10; generalised to the configured width + 2), 1 skipped (16 min 43 s under a concurrent backfill); infra 95; the fixed test re-run green on its own database |
| End of Phases 3, 4a and the Phase 5 infra (gates 5 and 6), 2026-11-03 | `make verify` on the whole tree | pass | backend 4,058 passed, 1 skipped (10 min 29 s); infra 113 passed; frontend 943 passed; lint, typecheck, format, okf-validate, build green. One run gated the three commits because the phases were built in parallel in one tree. |
| End of Phase 4b (gate 7), 2026-11-03 | `make verify` on the whole tree | pass | backend 4,086 passed, 1 skipped (11 min 14 s); infra 113; frontend 943; lint, typecheck, format, okf-validate, build, audit green |
| Step-6 exit (gate 8), 2026-11-03 | `make verify` then `make audit` on the final tree | pass after one test-timing fix | first run: backend 1 failed (`test_adaptive_pool_converges_under_a_quota_and_never_splits_for_throttling`, timing-flaky fake; deviation 22), 4,085 passed; second run after the fix: backend 4,086 passed, 1 skipped (6 min 51 s); infra 113 passed; frontend 943 passed; lint, typecheck, okf-validate (192 concepts), build green; `make audit`: no known vulnerabilities |
| Owner rulings after the exit (gate 8 again), 2026-11-03 | `make verify` on the tree with the timeouts at n ≥ 30 / floor 15, the markup rules and the probe brief | pass after one re-pin | first run: backend 1 failed (`test_parse_worker_output_is_byte_identical_serial_and_concurrent`: the digest moved on a significance-star line; the rule fixed and the digest re-pinned, § Owner rulings), 4,092 passed; second run: backend 4,095 passed, 1 skipped (11 min 28 s); infra 113; frontend 943; lint, typecheck, okf-validate, build green |
| Review open (step 7), 2026-11-03 | `make verify` on `fb06cd72` (the `--round-to` commit had no gate row) | pass after one re-run | backend 1 failed (`test_the_invariant_holds_after_every_operation_in_a_deterministic_walk`: a 401 at step 67, the walk's 60 s bearer tokens expired in a 29-minute run at a load average of 110 to 195 beside probe 3 and four reviewer agents), 4,094 passed, 1 skipped; alone the walk passes in 9.8 s (F21 raises the test tokens to 600 s); infra 113; frontend 943; lint, typecheck, okf-validate (192), build green |
| Review fixes, first run, 2026-11-03 | `make verify` on the tree with F1 to F21 | fail, two findings | backend 2 failed: `test_acquire_module_has_no_http_client` (the package-wide import guard, which F6's `import socket` tripped; the guard now allows that one import and the module's own guard forbids constructing a socket) and `test_hung_parse_does_not_hold_back_a_concurrent_one` (timing; passed alone in 17 s; the run's load average was 85 to 145), 4,115 passed, 1 skipped (11 min 53 s) |
| Review fixes, second run (the step-7 exit), 2026-11-03 | `make verify` on the final reviewed tree, then `make audit` | pass with one lane re-run | backend 4,117 passed, 1 skipped (14 min 53 s); infra 113; typecheck (459 files), lint, okf-validate (199 concepts), eval-check, audit-paths (211 files), prompt-guard, font-guard, drift-check green; frontend: one test timed out at 5 s under a load spike (`SourcesView.test.tsx`, "keeps Origin a plain, non-sortable header", unchanged on this branch), the lane re-run alone (`make frontend-verify`): 88 files, 943 passed, build green; `make audit`: no known vulnerabilities |
| Review fix F22 (the output caps, on the owner's go), 2026-11-03 | `make verify` on the tree with F22 | pass after the prompt-hash re-pin | backend 4,117 passed, 1 skipped (9 min 34 s); okf-validate (199), eval-check, infra 113, audit-paths (211) green; `prompt-guard` failed on the two prompt files' hashes (a constant and a comment changed, no prompt text; re-pinned with `--update`; the diff is commit `bd574c66`); then `prompt-guard` (41 unchanged), font-guard, drift-check and frontend-verify (88 files, 943 passed, build) green |
| Owner rulings applied (6: in-process threads 10; 7: the function's egress rules), 2026-11-04 | `make verify` on the tree with the rulings | pass | backend 4,117 passed, 1 skipped (8 min 60 s); okf-validate (199), typecheck (459 files), lint, eval-check, infra 113 (the egress test extended), audit-paths, prompt-guard (41 unchanged), font-guard, drift-check, frontend 88 files / 943 passed, build green. Rulings 1, 2, 3, 4, 5, 8 and 10 changed records only (contract N8 and N9, spec S5, rubric 13, ADR 0043, two deferred seams closed). |
| PR tree: dev merged in (`f0018c4e`, production on the bedrock route), 2026-11-04 | `make verify` on the merged tree | pass | backend 4,117 passed, 1 skipped (9 min 26 s); okf-validate (200), typecheck (459 files), lint, eval-check, infra 113, audit-paths, prompt-guard (41 unchanged), font-guard, drift-check, frontend 88 files / 943 passed, build green. The merge resolved two conflicts by keeping both sides (`pa_config.json`: production `model_route = bedrock` with `ingest_mode = in_process`; `DEPLOYMENT.md`: the route row from dev plus the two ingest rows). |
| End of Phase 0 and Phase 1 (gates 2 and 3), 2026-11-03 | `make verify` on the tree holding both phases | pass after one fix | backend 4,004 passed, 1 skipped (6 min 0 s); lint, typecheck, format green; infra: 1 failed (`test_dockerignore_covers_gitignored_backend_content`: the `**/` bytecode patterns no longer matched the gitignore lines literally; both forms kept), then `make -C infra test` 95 passed. One full run gated both commits because the two phases were built in parallel in one tree. |

## Phase 0: build-open, measurement tools, dev image

### The anatomy reproduced

`scripts/stage_walls.py` run with the ten bedrock run ids of the 2026-11-02 anatomy and the
saved server logs reproduces the anatomy's Table 2 (bedrock) exactly:

| component | n | median s | max s | min s | share of median total |
|---|---|---|---|---|---|
| acquire | 10 | 63 | 112 | 54 | 4% |
| screen_abstract | 10 | 51 | 249 | 28 | 3% |
| classify | 10 | 41 | 250 | 23 | 2% |
| appraise | 10 | 1 | 1 | 0 | 0% |
| ingest_full_text | 10 | 729 | 1141 | 485 | 41% |
| screen_full | 10 | 35 | 166 | 22 | 2% |
| characterise | 10 | 29 | 146 | 15 | 2% |
| select | 10 | 21 | 68 | 16 | 1% |
| synthesise | 10 | 519 | 970 | 331 | 29% |
| total | 10 | 1786 | 2169 | 1352 | |
| outside | 10 | 3 | 5 | 3 | 0% |

Command (from the repo root, `DATABASE_URL` from `backend/.env`):

```
uv run --project backend python scripts/stage_walls.py --run-id <id> ... --route bedrock --logs <log folder> --out <file>
```

### Per-step timeouts derived from Langfuse (plan P1, contract D12)

`scripts/step_timeouts.py` over every Bedrock generation since 2026-11-02 (22,259
observations fetched; 3,594 non-Bedrock rows skipped). Healthy = no ERROR level and
shorter than today's client timeout. Proposed = max(5, ceil(2 × p99)), only when n ≥ 100.

| step | n healthy | p99 s | proposed timeout_s | today s | decision |
|---|---|---|---|---|---|
| classify_document | 4739 | 5.3 | 11 | 60 | set |
| screen_abstract | 7876 | 3.3 | 7 | 60 | set |
| screen_full | 921 | 3.9 | 8 | 60 | set |
| extract_interventions | 1415 | 16.4 | 33 | 60 | set |
| synthesise_write_block_summary | 254 | 2.7 | 6 | 120 | set |
| synthesise_judge_summary | 277 | 2.3 | 5 | 120 | set |
| synthesise_section_turn (with repair_claims) | 424 | 11.0 | 23 | 120 | set |
| judge_grounding | 254 | 19.8 | 40 | 120 | set |
| option_profile_place_sentences | 111 | 17.1 | 35 | 60 | set |
| select_rerank | 85 | 11.7 | | 60 | keep, n < 100 |
| search_generate_queries | 95 | 3.5 | | 60 | keep, n < 100 |
| longlist_assign | 71 | 22.6 | | 60 | keep, n < 100 |
| option_profile_line | 65 | 41.7 | | 60 | keep, n < 100 |
| characterise_assign | 57 | 12.7 | | 60 | keep, n < 100 |
| every other step | < 40 | | | today's value | keep, n < 100 |
| chat | | | | 120 | keep, exempt (streamed) |

Nine steps get a Bedrock override; the rest keep today's literal, now written into
`[steps.<name>] timeout_s` so no step falls back to the SDK default. The full table with
every row is the script's output (`--format md`); the TOML lines come from `--format toml`.

Command:

```
set -a; source backend/.env; set +a
python3 scripts/step_timeouts.py --cache <scratch>/langfuse-obs-since-1102.json
python3 scripts/step_timeouts.py --from-cache <scratch>/langfuse-obs-since-1102.json --format toml
```

### Build-open fixed-question runs (the like-for-like "before")

Three fresh Evidence search runs on bedrock, 2026-11-03 02:46 to 03:34 UTC, served from a
separate checkout of `e0553f85` so edits in the working tree could not reach the running
server. The server allows two walks at once (`RUN_EXECUTOR_MAX = 2`), so the obesity run
started when the zonal run ended and overlapped only the NEET run. Per-stage walls in
seconds from `stage_walls.py` with the server log:

| run | question | status | total | acquire | screen_abstract | classify | ingest_full_text | screen_full | characterise | select | synthesise |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 30d59394 | NEET | succeeded | 2119 | 65 | 60 | 101 | 1009 | 39 | 16 | 15 | 806 |
| 1b5de879 | zonal pricing | succeeded | 1493 | 55 | 39 | 97 | 939 | 46 | 27 | 27 | 258 |
| 212724e0 | childhood obesity | degraded | 1229 | 72 | 71 | 67 | 757 | 105 | 16+19 | skipped | 119 |
| median | | | 1493 | 65 | 60 | 97 | 939 | 46 | 27 | 21 | 258 |

Ingest split from the server log (A = fetch and parse to the first embedding request,
B = embedding, C = tail):

| run | ingest wall | A fetch+parse | B embedding | C | embed requests | throttle sleeps (n / s) |
|---|---|---|---|---|---|---|
| 30d59394 | 1009 | 258 | 749 | 2 | 64 | 32 / 97 |
| 1b5de879 | 939 | 278 | 659 | 2 | 53 | 33 / 108 |
| 212724e0 | 757 | 235 | 522 | 1 | 160 | 0 / 0 |

Notes read from the saved results:
- The two runs that embedded at the same time shared the Cohere token allowance (32 and
  33 throttle sleeps each); the run that embedded alone saw none. Embedding is 65 to 75% of
  the ingest wall in all three, as the anatomy found.
- The obesity run ended `degraded`: theme discovery (characterise) failed twice with
  "theme description exceeds 240 chars" (a wire check on the model's output; a
  pre-existing flake unrelated to this slice), so select was skipped and the report was
  short (synthesise 119 s). Its synthesise wall is not comparable; the ingest and screen
  walls are.
- Saved results: `stage-walls-phase0-baseline.{md,json}` and the server log in the
  session scratchpad (not committed: the log holds publisher URLs).

### G9: dev and CI Postgres image moved to `pgvector/pgvector:pg17`

Compose has no named volume and Postgres 17 cannot open a 16 data directory, so the dev
database was dumped (`pg_dumpall`, 7.4 GB including about 33 stale test databases; a
custom-format dump of `policy_atlas` alone, 1.8 GB, was what got restored with
`pg_restore --no-owner`, exit 0, empty error log). Exact row counts before and after:

| table | pg16 | pg17 |
|---|---|---|
| capability_run | 499 | 499 |
| runs | 2087 | 2087 |
| event_log | 116248 | 116248 |
| source_snapshot | 17221 | 17221 |
| chunk | 119196 | 119196 |
| chunk_embedding | 245979 | 245979 |
| task_source_snapshot | 15958 | 15958 |
| task | 118 | 118 |

Now PostgreSQL 17.11 with pgvector 0.8.7 (`CREATE EXTENSION vector` done in `policy_atlas`;
the migration version stays `152a234e2391`). `tests/conftest.py` creates the extension in
each worker's test database and the `reset-test-db` target does the same; the three
migration tests that create scratch databases are untouched (the Phase 2 migration creates
the extension itself). The stale test databases were not restored. The old `c4-demo`
worktree no longer exists. Two agentic-ops documents that said "plain `postgres:16`, no
pgvector" were updated. `make test-fast` on the new image: 3,946 passed, 1 skipped.

## Phase 1: timeouts, widths, judge effort, image, matcher

### N14, quote-side markup (`qv_v2`) — built, tests green

- New `core/markup.py` holds the one markup rule (E6 rule "a") as `strip_markup` (text in,
  text out; Phase 4a's parser uses it) and `markup_deletions` (the exact spans to delete; the
  verifier uses it). A test pins that the two agree on every fixture line.
- `quote_verify._build_norm` deletes markup spans like soft hyphens, on both the quote and
  the chunk; a `<br>` becomes one space. Verifier version `qv_v2`. The case-fold round-trip
  guard in `locate_unique_span` now re-normalises in place (the old guard re-normalised the
  raw slice alone, which no longer recognises a slice cut through a link).
- Tests: `tests/core/test_markup.py` (6) and
  `tests/evidence_search/extract/test_quote_verify_markup.py` (11); 514 extract and
  synthesis tests green; `make prompt-guard` unchanged (41 files).
- **Re-pinned test expectations (values only):** the verifier version string in two tests;
  the IOF, ICF and interventions extraction fingerprint hashes (the verifier version is one
  of their inputs; re-computing with `qv_v1` returns every old hash, so nothing else moved).
- **Build-flagged for the owner (adjudication items):**
  1. The fingerprint change means stored extractions are not reused: the next run on each
     document re-extracts and pays that model cost once more. Right behaviour (anchors can
     differ under `qv_v2`); not named in the contract or plan.
  2. A verbatim quote cut through an emphasis pair (`see _Table 1` from `see _Table 1_ for`)
     matched under `qv_v1` and fails under `qv_v2`, because a lone `_` is not markup. No
     `qv_v1` fallback was built. Parse profile v2 (Phase 4a) removes markup from new chunks,
     so this only affects old-profile snapshots.
  3. A quote copied with its markup now grades `normalised`, not `exact` (as soft hyphens do).
- Inherited E6 quirks, pinned by tests: `\*literal\*` becomes `\literal\`; `**pro**gramme`
  becomes `*pro*gramme`.

### N10c, D12: the step-timeout seam — built, tests green

- `Step.timeout_s` is required on every `[steps]` entry (56 steps carry today's literal:
  60 s, 120 s for the synthesis writer, judge, group, extract and vetter steps and chat,
  30 s for the source note and intro); `StepException.timeout_s` is an optional override;
  `Route.timeout_for(step)`. The nine Bedrock overrides from the Phase 0 table sit under
  `[routes.bedrock.steps]`; `openai-direct` keeps today's values exactly.
- Every OpenAI client is built with `max_retries=0` and no client-level timeout; the
  timeout travels per request through `openai_kwargs(..., timeout_s)`. One traced retry
  lives in `tracing.traced_attempts`: step, attempt and a shared `logical_call_id` are
  stamped on the generation before the request goes out; a failed attempt is marked
  `ERROR`; the retry fires once on timeout, connection error, 429 (Retry-After honoured,
  capped at 30 s) or 5xx. Confirmed against the installed Langfuse SDK (4.15.4) that
  metadata merges per key and that `level`/`status_message` mark the span.
- All 58 OpenAI call sites pass their step; 23 `traced_call` generation sites switched to
  `traced_attempts`; sites with a caller retry loop keep the loop and get the one traced
  retry too (worst case 2 × budget attempts instead of 3 ×; see
  the call-site table the sweep worked from, kept in the session scratchpad only since 2026-11-04). Both boto3 clients get `read_timeout=60` and
  botocore retries off; the OpenAI embedding client keeps its own loop (now also retrying
  timeouts, connection errors and 5xx) with a 30 s request timeout.
- **Flagged deviation (minor, within the contract's vocabulary):** chat. The tool turn and
  the final structured parse are wrapped (one traced retry each; they send nothing to the
  user); the prose stream stays exempt. The outer `chat:call` observation that used to be
  a generation is now a span, and the tokens and cost sit once on the inner generations
  (which keep the name `chat:call`). The stream's own tokens were never recorded before
  either, so nothing is lost; a Langfuse saved view filtering on name plus type
  `generation` now matches the inner calls.
- Tests: `tests/core/test_traced_attempts.py` (15), `tests/core/test_step_timeout_sites.py`
  (a source scan with Python's parser: every builder, every helper call, every generation
  opened through `traced_attempts`; the exemptions are the wrapper itself and the Claude
  boto3 `converse` call), `tests/core/test_model_routes.py` updated (the bedrock route now
  has timeout-only step exceptions; no route overrides a model).
- **Code-only prompt-hash re-pin:** `ranking.py`, `theme_grouping.py`, `finding_vetter.py`,
  `group_clustering.py`, `grounding_judge.py` (builder argument lines, `timeout_s=`,
  `step=`, the `_STAGE_STEP` dict, one rewritten comment). The full diff is the Phase 1 commit
  `8bc43872` (the file once committed beside this record was removed on 2026-11-04; git holds it); no prompt text changed
  (`make prompt-guard`: 41 files unchanged after the re-pin).

### Measurement round (a): step timeouts alone (commit `8bc43872`; widths and judge unchanged)

Three fresh runs, 2026-11-03 04:08 to 05:05 UTC, same shape as the baseline (NEET and
zonal together, obesity when a slot freed). All three `succeeded`.

| run | question | total | acquire | screen_abstract | classify | ingest_full_text | screen_full | characterise | select | synthesise |
|---|---|---|---|---|---|---|---|---|---|---|
| fd1325c5 | NEET | 1717 | 63 | 50 | 78 | 942 | 48 | 87 | 28 | 438 |
| 0a755648 | zonal pricing | 1698 | 55 | 31 | 35 | 985 | 43 | 21 | 20 | 371 |
| f581a92c | childhood obesity | 1623 | 86 | 49 | 38 | 592 | 45 | 37 | 22 | 257 + 600 |
| median | | 1698 | 63 | 49 | 38 | 942 | 45 | 37 | 22 | 438 |

| run | ingest wall | A fetch+parse | B embedding | embed requests | throttle sleeps (n / s) |
|---|---|---|---|---|---|
| fd1325c5 | 942 | 172 | 769 | 82 | 87 / 425 |
| 0a755648 | 985 | 252 | 731 | 92 | 90 / 432 |
| f581a92c | 592 | 211 | 379 | 95 | 11 / 37 |

Per-step attempts cut and retried (`model_call.retry` in the server log; every retry was
attempt 1 after a timeout unless stated):

| step | timeout_s | retries | retry outcome |
|---|---|---|---|
| classify_document | 11 | 12 | all recovered; all 12 fired inside three seconds (04:11:10 to 04:11:13) while both runs classified at once |
| judge_grounding | 40 | 7 | all recovered |
| synthesise_propose_sections | 120 (kept) | 2 | one recovered; one retry also stalled, so the synthesise component failed and the runner re-ran it (obesity: 257 s lost, then 600 s) |
| synthesise_section_turn | 23 | 2 | recovered (one connection error, one timeout) |
| screen_full | 8 | 1 | recovered |
| characterise_discover | 60 (kept) | 1 | recovered |
| synthesise_judge_summary | 5 | 1 | recovered |
| synthesise_write_block_summary | 6 | 1 | recovered |

Read from the saved results:
- 27 stalls caught, 26 recovered on the one retry. No tightened step had a retry that was
  also slow, so no step is raised (the contract's "too tight" signal is a slow retry; the
  classify burst recovered at once and classify's wall halved, 97 → 38 s median).
- **Components that retried because every attempt was cut: 1, not 0.** The step is
  `synthesise_propose_sections`, which kept today's 120 s (n = 30, below the 100-call
  floor), so it is not a tightened timeout: two consecutive 120 s stalls on a 4 s step.
  Which step raised the error is an inference from the retry timing (the component's
  failure event carries only `APITimeoutError`). Adjudication item for the review: the
  contract's remedy for a too-tight step (raise once) does not apply; the lever that would
  is a second retry on once-per-run steps, which the contract does not include.
- Synthesise medians are noisy at n = 3 (section counts differ per run): NEET 806 → 438 s,
  zonal 258 → 371 s. The attribution this round supports is the stall cost: a stall now
  costs the step's timeout plus one retry instead of 120 s.
- Ingest is not this lever's: the two concurrent runs saw 87 and 90 throttle sleeps (425
  and 432 s of waiting) against 32 and 33 in the baseline pair, so the allowance in force
  at this hour was lower or more contended; the run that embedded alone saw 11.
- Saved: `stage-walls-phase1a.{md,json}`, `phase1a-retries.txt` and the server log in the
  session scratchpad (the log holds publisher URLs; not committed).

### Measurement round (b): pool widths (commit `8bc43872` plus the widths commit `528250f7`; judge at medium)

Four runs, 2026-11-03 05:56 to 06:56 UTC: NEET and zonal together, obesity when zonal ended,
the scoping question when NEET ended. All `succeeded`.

| run | question | total | acquire | screen_abstract | classify | ingest_full_text | screen_full | characterise | select | synthesise |
|---|---|---|---|---|---|---|---|---|---|---|
| 9f479f3d | NEET | 1757 | 64 | 28 | 21 | 1051 | 47 | 30 | 23 | 494 |
| 2a09a491 | zonal pricing | 1495 | 55 | 25 | 20 | 872 | 46 | 27 | 22 | 371 |
| 62f27acb | childhood obesity | 1987 | 72 | 30 | 22 | 689 | 48 | 33 | 25 | 403 + 649 |
| median | | 1757 | 64 | 28 | 21 | 872 | 47 | 30 | 23 | 494 |

Screen stage 1 and classify, the lever's stages, across the rounds (medians):

| stage | baseline (width 12) | round (a) (width 12) | round (b) (width 48) |
|---|---|---|---|
| screen_abstract | 60 | 49 | 28 |
| classify | 97 | 38 | 21 |

Bedrock 429s: none. The 59 HTTP 429 lines in the log are 28 OpenAlex search retries (the
width-4 logs of 2026-11-02 show 27 to 42 per scoping walk, so not new) and 31 publisher
fetch retries (E5's finding; not this lever's). Ingest split: NEET 327 + 721, zonal
275 + 595, obesity 280 + 406 (73, 55 and 16 throttle sleeps).

**Options scoping (N10a, N10b), task 3840aabb:** baseline run 613 s, longlist walk 1,190 s,
total 1,804 s; the option-search fan-out of 10 children ran in a 326 s window (child median
322 s, max 326 s) against the anatomy's 357 s window at width 4 (10 children of about
144 s in waves). The children ran about twice as long each at width 10 (they share the
same provider and search backends), so the window gained 31 s, not the 3× the width
promised. No scoping model call over 300 s (N10a confirmed: the longest was `agent:suggest`
at 60.4 s, a step timeout; 1,171 generations in the session). **Peak database connections
during the fan-out: not sampled** (the sampler followed the baseline run instead of the
walk run); the Postgres log shows at least 13 distinct client connections writing inside
the window, consistent with 1 + 10 per walk plus the API pool. Re-sampled in round (c),
which carries the scoping question again with the sampler on the walk run.

Retries (99, all attempt 1, all recovered except one): screen_abstract 29 (22 timeouts,
7 connection errors), classify 18, extract_interventions 13, judge_grounding 10,
longlist_assign 6, screen_full 4, three synthesis steps 3 each (section_turn also 3
connection errors), option_profile_place_sentences 3, four others 1. At width 48 about
5% of screen and classify calls hit their 7 s and 11 s cutoffs against about 1% at width
12 (the p99 was measured at width 12); every one recovered on the retry, so by the
contract's rule neither step is raised; noted for the review as the cost of the pair
(about 2 × 5% of those calls).

**Components that retried because every attempt was cut: 1 (obesity's first synthesise
attempt, 403 s lost).** Read from the retry log inside that attempt's window: the last
cut was `judge_grounding` at 06:44:28 (40 s), and the component failed 42 s later, so
the judge's retry was also cut at 40 s. That is the contract's "too tight" signal (a slow
retry): **`judge_grounding` is raised once, 40 → 80 s**, applied with the judge's effort
change in round (c), which re-measures it. Round (a)'s cut component was a different
step (`synthesise_propose_sections`, kept at 120 s; no raise, n < 100).

### Measurement round (c): the grounding judge at low effort, timeout 80 s (commit `c83c3d50` cherry-picked on Phase 1 plus widths)

Five runs, 2026-11-03 07:13 to 08:11 UTC (NEET and zonal together, obesity when NEET ended,
the scoping question when zonal ended). All `succeeded`; no degraded, failed or skipped
events.

| run | question | total | acquire | screen_abstract | classify | ingest_full_text | screen_full | characterise | select | synthesise |
|---|---|---|---|---|---|---|---|---|---|---|
| 83e3fa3a | NEET | 1815 | 62 | 21 | 19 | 1235 | 56 | 26 | 23 | 374 |
| 42e70520 | zonal pricing | 1852 | 60 | 22 | 20 | 1164 | 58 | 30 | 88 | 420 |
| 11d3481c | childhood obesity | 1411 | 71 | 20 | 18 | 757 | 50 | 24 | 91 | 350 |
| median | | 1815 | 62 | 21 | 19 | 1164 | 56 | 26 | 88 | 374 |

Ingest split: NEET 281 + 952 (91 throttle sleeps, 450 s), zonal 403 + 759 (82 / 378 s),
obesity 197 + 552 (0). The embedding allowance was again shared by the two concurrent runs;
not this lever's. `select` ran 88 and 91 s on two runs (six `select_rerank` retries at 60
s); provider noise at that hour, not a changed step.

**The judge (N15, D14), `judge:grounding` generations from Langfuse:**

| round, effort | session | calls | median s | p99 s | total s | cut at the timeout |
|---|---|---|---|---|---|---|
| (b) medium, 40 s | NEET | 20 | 9.2 | 36.2 | 226 | 1 |
| (b) medium | zonal | 11 | 12.8 | 18.2 | 130 | 0 |
| (b) medium | obesity | 30 | 11.6 | 40.3 | 502 | 7 |
| (c) low, 80 s | NEET | 17 | 4.1 | 68.8 | 154 | 1 |
| (c) low | zonal | 17 | 4.2 | 80.2 | 222 | 2 |
| (c) low | obesity | 12 | 4.8 | 6.8 | 56 | 0 |

Calls that did not stall: median 3.9 to 4.8 s at low against 8.9 to 12.8 s at medium (E3
measured 11.5 → 5.4 s); the slowest healthy call 9.0 s against 19.4 s. Synthesise median
494 → 374 s. The three calls cut at 80 s are stalls (a healthy low-effort call never
exceeded 9 s), each recovered on the one retry, and no component failed this round. The 80
s value is therefore loose rather than tight; once 100 traced low-effort calls exist the
derivation would give about 2 × 9 = 18 s. Left at 80 s (the contract's "raise once"; a
later re-derivation is a step-8 or owner item).

**Unsupported-claim counts (rubric 31):** the database keeps only the verdicts after the
one repair pass, and every report in rounds (b) and (c) ends with 0 unsupported claims
there (claims judged: 107 / 100 / 77 in (b), 92 / 84 / 74 in (c)); sections that needed a
repair were 5/11, 3/10, 3/10 in (b) and 5/10, 7/8, 3/9 in (c). The judge's first-pass
verdicts live only in its trace outputs; their counts per session are being read (numbers
only) and are recorded below against E3's spread (26 at low against 33 and 28 at medium per
157 claims). **The owner's content read of one report after (c) is an owner item** (run ids
above; the reports are in the app).

**Options scoping (second run, for the connection peak):** baseline 429 s, walk 1,050 s
(round (b): 613 and 1,190 s); 9 option-search children this time (suggest proposed 9) in a
434 s window, child median 431 s. **Peak database connections during the fan-out: 12**
(07:55:25 UTC, inside the window; every sample in the window read 11 or 12, with the
obesity Evidence search run going at the same time; 3 to 6 outside the window). Within the
budget's 1 + 10 per walk plus the API pool. Sampled every 7 s on the walk run.

Retries this round: 121 (all attempt 1; screen_abstract 70 with 63 timeouts and 7
connection errors, classify 9, extract_interventions 8, option_profile_line 7,
select_rerank 6, screen_full 4, judge_grounding 4, eleven others 1 or 2); 173 Cohere
throttle lines; no Bedrock 429s (the 88 HTTP 429 lines are OpenAlex and publisher
fetches). Saved: `stage-walls-phase1c*.{md,json}`, `phase1c-judge-calls.txt`,
`phase1c-unsupported-claims.txt`, `phase1c-connections.txt`, `phase1c-retries.txt`.

### Measurement round (d): the schema's binary vector writes (Phase 2 commit `a911aa4e` plus the widths and judge changes; dev database at rev2, so every unit wrote the JSON vector, `embedding` and `tokens`)

Three runs, 2026-11-03 08:16 to 09:04 UTC. NEET and zonal `succeeded`; **obesity `failed`**.

| run | question | status | total | acquire | screen_abstract | classify | ingest_full_text | screen_full | characterise | select | synthesise |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7aa2dd57 | NEET | succeeded | 1537 | 69 | 19 | 14 | 931 | 43 | 20 | 19 | 360 |
| 062f756a | zonal pricing | succeeded | 1263 | 54 | 18 | 10 | 767 | 33 | 148 | 21 | 208 |
| 0ead0762 | childhood obesity | failed | 1479 | 64 | 10 | 17 | 718 | 51 | 46 | 28 | 257 + 285 (both attempts failed) |
| median | | | 1479 | 64 | 18 | 14 | 767 | 43 | 46 | 21 | 360 |

Fewer documents landed this round (92, 63 and 110 ingested; 6,715, 3,734 and 8,279 units
against 8,334 to 9,490 in round (c)), so the ingest and total walls are not like-for-like.
Ingest split: NEET 152 + 779 (73 sleeps, 326 s), zonal 186 + 580 (60 / 322 s), obesity
171 + 546 (7 / 24 s).

**The lever's own signal, the embedding loop's overhead** (B wall minus the summed
request-to-response time minus the throttle sleeps; read from log timestamps with the same
arithmetic on rounds (b), (c) and (d); rounds (b) and (c) wrote the JSON column only, (d)
wrote all three columns):

| round | per-run overhead (s) | median overhead (s) | median ms per unit | median gap response → next request (ms) |
|---|---|---|---|---|
| (b), JSON only | 60.4, 58.8, 51.0 | 58.8 | 7.8 | 533 |
| (c), JSON only | 37.4, 34.9, 107.3 | 37.4 | 4.5 | 373 |
| (d), JSON + binary + tokens | 39.8, 17.2, 36.9 | 36.9 | 4.6 | 328 |

Read from the saved results: writing the two extra columns cost nothing measurable (4.5
against 4.6 ms a unit); the spread between (b) and (c), with identical writes, is wider
than any write effect. E10's 17 to 45 s of JSON write overhead per run sits inside the
17 to 107 s range seen here; this loop timer is not a clean write timer (it absorbs the
other run's contention in the same process). The JSON column's cost goes with rev3 (the
column is dropped), measured in the next round.

**The failed run (obesity):** first synthesise attempt: `judge_grounding` stalled to its
80 s cut and its one retry stalled too (component failed at 08:58:39); the runner's
second attempt: a judge stall recovered, then a `synthesise_section_turn` connection
error whose retry stalled at 23 s (component failed at 09:03:24; run failed). Zonal's
`characterise:assign` had two connection errors then two 60 s cuts and was saved by its
caller's budget (characterise 148 s). Retries this round: 16 (classify 4, judge 3,
section_turn 3, characterise_assign 3, propose_sections 2, screen_full 1; half of them
connection errors). Across rounds (a) to (d), the judge stalled on 3 of about 45 calls per
round at low effort (6%), and a stall-then-stall on one step cost a synthesise attempt in
three of four rounds and a whole run in this one.

**Deviation taken (D12, flagged for the review and the owner):** `MODEL_CALL_ATTEMPTS`
2 → 3 (commit `f908e9f7`): the call and two traced retries instead of one, the attempt
count the SDK gave before this task, now traced. At 4 to 6% stalls per call a single retry
leaves about 0.3% of calls, and so about 5% of runs with 15 judge calls, to a failed
component; a third attempt at the step's timeout (5 to 80 s) is cheap. Rounds (e) to (g)
measure with it.

**First-pass judge verdicts (rubric 31), read from the judge's trace outputs, counts
only:**

| round, effort | question | judge calls counted | claims judged | unsupported | share |
|---|---|---|---|---|---|
| (b) medium | NEET | 19 | 107 | 7 | 6.5% |
| (b) medium | zonal | 11 | 100 | 0 | 0.0% |
| (b) medium | obesity | 23 (incl. the failed first synthesise attempt's 42 claims, 4 unsupported) | 124 | 10 | 8.1% |
| (c) low | NEET | 16 | 95 | 9 | 9.5% |
| (c) low | zonal | 15 | 87 | 14 | 16.1% |
| (c) low | obesity | 12 | 76 | 5 | 6.6% |

Totals: medium 17 of 331 (5.1%; 13 of 289 without the failed attempt), low 28 of 258
(10.9%). On these live runs the low-effort judge marked **more** claims unsupported than
the medium one, the opposite of E3's lean (26 at low against 33 and 28 at medium per 157
claims); the runs are not on the same claims, and the repair pass cleared all but one
verdict in both rounds. **The owner's content read decides (D14); recorded as such.**

### N13, G8: compiled bytecode — measured

One `RUN python -m compileall -q /app/.venv /app/src` line after the venv copy; the
`.dockerignore` bytecode patterns gained `**/` so the laptop's `.pyc` files stay out (the
"before" image carried 205 of the laptop's `cpython-313` files, useless to Python 3.12; the
"after" image holds 6,731 `cpython-312` files of its own). Cold import of the parser stack
in a fresh amd64 container, five containers each, on the laptop while a measurement round
ran:

| image | `ingest_full_text` import, five values (s) | median |
|---|---|---|
| before (`e0553f85`) | 21.19, 9.95, 9.76, 7.67, 12.06 | 9.95 |
| after (this task) | 5.87, 3.86, 3.57, 2.97, 2.81 | 3.57 |
| after, `ops.ingest_worker` (the handler) | 2.82, 3.17, 3.32, 7.23, 5.39 | 3.32 |

An interleaved repeat (before and after alternating) gave medians 8.24 s and 3.79 s. Image
size 697 → 846 MB listed (163 → 196 MB content). E4's laptop figure was 7.7 → 3.8 s.

**Second Dockerfile change, outside G8's "one change" — flagged for the owner's ruling at
the PR:** `chmod 755 /app` after `useradd`. `useradd --create-home` makes `/app` private
(mode 700, owner `app`), and AWS Lambda runs a container image as its own user, not the
image's `USER`; under the emulator as uid 1000 the function never started
(`Runtime.InvalidEntrypoint`, `permission denied` on `python`, with or without a
read-only root). Without this line the function fails on its first staging start. The
line is one word of permission, reversible, and the API container is unaffected (it runs
as `app`).

### D5: the handler under the Lambda Runtime Interface Emulator (amd64)

Image `pa-057-after` (the working tree) under `aws-lambda-rie` 1.38, read-only root,
`/tmp` 512 MB, a stub Secrets Manager answering `GetSecretValue` once at cold start, a
scratch database migrated to head, one `queued` link row:

- **As the image's own user (uid 999):** the brief's local fixture server was refused (the
  live fetcher blocks private addresses, as it should: `fetch_live.blocked`, the row ended
  `fetch_failed` / `blocked`, no snapshot). With the committed fixture's public source (one
  CC-BY PDF from PLOS, one public fetch) the first invocation returned
  `{"batchItemFailures": []}`, the row became `ingested` with `full_text_snapshot_id` set,
  `ingested_by_run_id` and `fetched_from` on the link row, the snapshot's `body_hash` equal
  to the sha256 of the committed fixture file, `parse_profile = pymupdf4llm_v2`,
  `segmentation_policy = pymupdf4llm_struct_v2`, metadata keys exactly `content_type`,
  `parse_profile`, `segmentation_policy`, `source_kind`, 3 chunks (61,040 characters); the
  parse process ran under the read-only root. The second delivery returned
  `{"batchItemFailures": []}` and logged `fulltext.not_queued` (idempotent). Logs are JSON;
  the redaction grep found no connection string, no `SecretString`, no query string (URLs
  are scheme, host and path). Cold start 5.5 s with a blocked fetch (init 3.6 s); 21.0 s with
  the real fetch and parse (15.7 s of it the parse of an amd64 image on this Mac under
  contention, not representative of Lambda); warm invocation 46 to 79 ms.
- **As uid 1000 (how Lambda runs it):** failed before the Dockerfile change above
  (`Runtime.InvalidEntrypoint`); after it, with the same read-only root and `/tmp`, the
  rebuilt image (`/app` now `drwxr-xr-x`) started, the first invocation ingested the same
  PDF (3 chunks, `pymupdf4llm_v2`, the four metadata keys, the link row's breadcrumbs), the
  second delivery was a no-op, the stub Secrets Manager was called once, the redaction grep
  found nothing. Cold start 18.0 s (init 3.8 s; the parse 11.4 s of it on this Mac), warm
  32 ms. The handler module's cold import on the rebuilt image: 2.45 s median (five
  containers). Scratch database and containers cleaned up; the two images stay until the
  step-6 exit.

## Phase 2: schema and the deploy waiter (D2, G9, G10, P5, P14, P17)

### Migrations rev1 `a3d8f6c1e2b4` (expand) and rev2 `b7e2c4a9d1f3` (backfill) — built, tests green

- `alembic/env.py` runs one transaction per revision. rev1 is online-safe: nullable columns
  only, the status check re-added `NOT VALID` then validated, both indexes built
  `CONCURRENTLY IF NOT EXISTS` in an autocommit block (an index left `INVALID` by a crashed
  build is dropped first), a 10 s lock timeout on the catalogue transaction. rev2 is data
  only: keyset-paged batches of 2,000 rows, commit per batch, resumable on
  `embedding IS NULL`, a second pass if rows were written behind it, refuses offline mode.
- `schema.py`: a `Vector(1536)` user-defined type bound as `CAST(... AS vector(1536))` (no
  client library, G3); `chunk_embedding.embedding`, `tokens text[]`, `vector` nullable; the
  three snapshot columns and the unique partial store-key index; the two link-row columns;
  `queued` in the status check. `core/tokens.py` holds the product tokeniser
  (`word_tokens`), imported by the retriever.
- `embed_pending_chunks` now writes all three columns (`vector` JSON, `embedding`, sorted
  `tokens`); tests assert the three agree in SQL.
- Tests (`tests/core/test_migration_057_document_store.py`): round trip up, down (JSON
  rebuilt from the binary column at float32 precision; `queued` rows back to
  `not_attempted`; old check restored) and up again; rev1 rerun on a database that has it;
  an `INVALID` index rebuilt; rev2 resume after an injected crash on the second batch;
  frozen tokens SQL equals `core.tokens` on 30 strings; `queued` admitted, `queued` with a
  snapshot or an error refused; the vector type round-trips 1536 floats. Whole backend
  suite on the agent's own database: 4,013 passed, 1 skipped.
- rev2 timing on a 10,000-unit scratch table: 11 s (about 1.1 ms per row).
- **Dev database (271,993 `chunk_embedding` rows, 2026-11-03 05:08 to 05:57 UTC):** rev1 1.3 s;
  rev2 about 49 minutes under heavy contention (a full verify suite with eight workers and
  two agents' test runs shared the laptop's Docker Postgres; the wait event was disk
  reads). Measured alone it ran at about 14,000 rows a minute, so about 20 minutes
  uncontended on this laptop. The production writer holds about 1.7 × these rows on
  Aurora storage (figure in the gitignored ops note), which is why the online pre-run is
  the recommended path. After rev2: 0 rows with a null `embedding`, 0 with null `tokens`.
- **rev3 `0914321f8de4` (drop the JSON column) — built, tests green, not yet applied to the
  dev database** (the Phase 1 measurement rounds serve older code that still writes the
  JSON column; rev3 goes on the dev database at the SQL-retrieval round). It runs a frozen
  copy of rev2's fill in autocommit batches, then in one transaction under an access
  exclusive lock (10 s lock timeout) one more fill pass, the "no row without an embedding"
  check (two counts: fillable rows the fill missed, and rows with JSON null / non-array,
  each with its own message; nothing dropped on failure) and the drop. Downgrade re-adds
  the column, rebuilds the JSON at float32 and sets it NOT NULL (a database downgraded to
  rev2 is stricter than a fresh one there; harmless, since that code always wrote it).
  `embedding` stays nullable (not in scope). Tests: the chain round-trips pre → rev2 →
  rev3 → rev2 → pre → head; rows written by old code after the pre-run are filled before
  the drop; a row with no embedding stops the drop with the counts in the message and the
  rerun succeeds after the fix; the frozen copy is pinned identical to rev2's. The code
  writes `embedding` and `tokens` only (no `vector` key); `schema.py` has no JSON column;
  `DEPLOYMENT.md`'s release note gains the third revision in Phase 5.
- **Flagged (minor, plan wording corrected):** the tokens SQL follows the product rule
  exactly (match `[0-9A-Za-z]+` on the original text, then lower-case each word, distinct,
  sorted), not plan P5's "lower then match `[0-9a-z]+`": the two differ on U+212A (Kelvin
  sign) and U+0130 (dotted capital I), and parity with the Python retriever is the point.
  `tokens` holds distinct words in sorted order.
- **Flagged for the owner (plan P14):** the pre-run of rev1 and rev2 before the deploy
  cannot go through the ECS migration task, whose task definition holds the image running
  today (without these revisions; the new definition is registered only as the deploy
  stops the service). `infra/DEPLOYMENT.md` § 4 therefore documents the pre-run over the
  § 6 tunnel from a checkout of the release commit (`DATABASE_URL=<tunnel-url> uv run
  alembic upgrade b7e2c4a9d1f3`), the same shape as the manual downgrade in § 8.
- **Carried into Phase 3:** rows the old image writes between the pre-run and the deploy
  have only the JSON column, so rev3 must run the same backfill (copied frozen, not
  imported) before it asserts no null `embedding` and drops the JSON column; SQLAlchemy
  writes `vector=None` as JSON `null`, so the code must pass `sa.null()` once the JSON write
  stops; both revisions treat JSON `null` as missing.
- Carried into Phase 4a: rev1 does not fill `ingested_by_run_id` and `fetched_from` from
  snapshot metadata; the per-document function writes them.
- Refused downgrades under per-revision transactions leave the revisions above the
  refusal undone and committed; two existing tests that assumed all-or-nothing now
  upgrade back to head in their cleanup; `DEPLOYMENT.md` § 8 says so for operators.

### Deploy waiter (G10, P14)

`scripts/deploy.sh`: `wait_for_migration_task` polls `describe-tasks` every 15 s until the
task is `STOPPED`, bounded by `MIGRATION_WAIT_MAX_S` (default 5,400 s; the deploy role
lasts 7,200 s), failing loudly with the stopped reason and exit code; a failed describe
call counts as one poll. Shell check `scripts/test_deploy_migration_wait.sh` (five cases,
nine checks) runs as a prerequisite of the existing deploy-build guard, so CI runs it with
no workflow change.

### Connection budget (N5, P17)

Exact account figures stay in the gitignored ops-facts note (plan § Owner items 7); the
arithmetic in scale words: the writer's connection limit is in the low hundreds with a few
dozen in use; worst case = today's use + the API pool (15 + 10 overflow) + 10 runs × (1
component connection + 10 option-search children at width 10) + 20 functions (one
connection each, held only for the store lookup and the one write) + the migration task,
which comes to under half the limit. If a later reading does not fit, `max_concurrency`
on the event-source mapping drops first, then `OPTION_SEARCH_WIDTH`. The Lambda concurrency
quota is in the hundreds on both accounts, ample for a cap of 20.

## Phase 3: retrieval in SQL (N8, D7, P7)

### The SQL retriever — built, synthetic parity green against both retrievers

- `RetrievalScope` is now a frozen record (docs metadata, document → text snapshot, the
  per-document text basis, a connection factory, `task_tags`, a unit count for
  provenance); `build_retrieval_scope(..., connect=)` loads documents and snapshot ids
  only. `ChunkRetriever.search` runs one statement (`CHUNK_SEARCH_SQL`): both legs cut to
  `CANDIDATE_POOL_PER_LEG` with the Python tie-break (unit id; a uuid sorts like its text
  form), reciprocal-rank fusion with `RRF_K`, best unit per chunk (vector-pool order first,
  then word-pool order, as the Python dictionary fill did), joined to `chunk` for content,
  sequence and the matched unit's offsets. Zero or negative cosines drop out (`distance <
  1`; pgvector returns NaN for a zero vector, and NaN < 1 is false), matching the Python
  `score > 0.0` rule. Python keeps the query embedding and cache, the filters (as the
  allowed document set), the soft prior and clamp, the sort by (-score, chunk id), the
  reranker seam, the cut to 8, windowing and provenance (prior factors for the returned
  chunks only; owner ruling). Synthesis passes a factory that lends its component
  connection; chat passes `engine.connect` (one short read per search). The in-memory
  scope load, the Python scoring, `RETRIEVAL_UNIT_CAP`, `RetrievalUnitCapError` and the
  three places that caught it (synthesise, chat scope, longlist turns with its
  "too many documents" reply) are deleted.
- **Committed synthetic corpus** (`tests/evidence_search/synthesis/data/retrieval_synthetic/`):
  40 chunks, 44 units, 9 documents, 10 snapshots in 2 scopes, stub vectors chosen so no two
  cosines are within 1e-6; 25 cases covering filters, every boost and the clamp, selection
  on and off, empty legs, the multi-scope precedence rule, ties inside a leg, between
  units of one chunk and between chunks, windowing of oversized chunks, and the pool cut.
  The frozen expected output was generated from the Python retriever; the test was green
  against both retrievers before the Python one was deleted, and three deliberate breaks
  of the SQL (best-unit tie-break, leg tie-break direction, positive-cosine filter) each
  failed it.
- **Scratch parity:** on a scratch corpus (about 21,000 units, random vectors) the SQL
  retriever matched the HEAD Python retriever on 40 of 40 queries, same top 8 in order.
- **Recorded real-query parity on the dev corpus (`scripts/retrieval_parity.py`, read-only,
  2026-11-03):** the Python retriever at `528250f7` (run from the gate worktree) against the
  SQL retriever, on the same stored vectors (each fixed-question query embedded once with
  the live Cohere backend and stored in the queries file, so both sides searched with the
  same vector).

  | query set | route / profile | queries | same top-8 in order |
  |---|---|---|---|
  | feasibility study, 3 scopes (601 to 899 units) | openai-direct, `openai_text_embedding_3_small_v1` | 20 | 20 of 20 against the HEAD Python retriever; 19 of 20 against the study's own saved reference, and the HEAD Python retriever misses the same one (the study put it down to a query-embedding difference), so the miss is in the study's reference |
  | NEET baseline run 235b7f40 (3,415 units, 15 selected) | bedrock, `cohere_embed_v4_1536_v1` | 32 | 32 of 32 |
  | zonal baseline run 9dbe27d7 (3,845 units, 15 selected) | bedrock | 23 | 23 of 23 |
  | obesity baseline run b7755787 (9,002 units, no selection) | bedrock | 13 | 13 of 13 |

  Every query came from the runs' own `search_chunks` tool calls (no filters were used);
  the selection ids and boosts came from each run's stored `synthesis_provenance`.
- **Dev-corpus latency (under load: the widths measurement round was running on the same
  laptop and database, load average 30 to 49; Docker Postgres with 128 MB shared buffers
  against a 6.2 GB `chunk_embedding` table):** pooled over the 68 fixed-question queries the
  SQL search median was 272 ms and 343 ms in two runs, 0 of 68 under 100 ms; the HEAD
  Python search (over an in-memory scope that took 2 to 11 s to load) was 39 to 141 ms
  median. On the feasibility scopes: 118 to 136 ms pooled median, 8 or 9 of 20 under 100 ms.
  One `EXPLAIN (ANALYZE, BUFFERS)` showed the scope's chunk list computed once per leg (a
  scan of `chunk` in each) and the vector leg reading about 32,000 buffers from disk. The
  scope list was tried as one `MATERIALIZED` pass: the planner then stopped probing
  `chunk_embedding` by chunk id and scanned the 6 GB table (about 60 s a query on the same
  13 queries), so the statement is back to the proven shape with a comment saying why
  (synthetic parity green both times). **The contract's "under 100 ms on the dev corpus"
  is not met as measured here**: a quiet-machine re-measurement follows at the SQL-retrieval round, and
  the adjudication note for the review is that the 100 ms figure came from the feasibility
  study's 600 to 900-unit scopes, the fixed questions carry 3,400 to 9,000 units, and the
  per-run cost of about 30 searches at 300 ms is seconds against the scope load it
  replaces (HNSW stays out by D7).
- **Re-measured with no live run after rev3 (the JSON column gone; the laptop's load
  average still 7 to 40 from finishing agents):** parity 68 of 68 again; search medians
  272 ms (NEET, 3,415 units), 351 ms (zonal, 3,845) and 2,086 ms on the first pass over
  the obesity scope (9,002 units), then 721, 451 and 624 ms on three warm passes. The
  laptop's Docker Postgres has 128 MB of shared buffers against a 7.5 GB `chunk_embedding`
  table, so each search of a large scope re-reads 50 MB of vectors from disk; a warm
  scope costs about 450 to 700 ms at 9,000 units here. **The 100 ms figure is not met on
  the dev corpus at these scope sizes.** Per run (about 30 searches) that is 10 to 20 s of
  retrieval against the 2 to 11 s one-time scope load plus 40 to 140 ms searches the
  Python path paid; the production writer's cache is larger (4 GB of RAM against this
  Postgres's 128 MB buffers) but its table is 1.7 × bigger. The N8 lever's gains are the
  cap removal, the JSON column and its 2 MB per batch of writes, and the Python scope
  load; its per-search cost is higher. Adjudication item: whether an HNSW index (D7 says
  no) or a bigger per-search budget is wanted; the synthesise wall in round (e) is the
  round-trip measure.
- Latency on the scratch corpus under heavy machine load (noisy): the statement alone 62 ms
  median on a 900-unit scope and 279 ms on a 5,000-unit scope; the scope load fell from
  2.1 s and 11.3 s (Python, units and vectors into memory) to 20 ms and 139 ms. The SQL
  search is slower per search than the in-memory Python search was; the run no longer pays
  the scope load or hits the 20,000-unit cap.
- **Flagged deviation (minor, an intended fix):** two documents sharing one text snapshot
  (possible inside one task once the body-hash store key is live) were scored twice by the
  Python retriever (both copies' rank terms added into one score). The SQL retriever
  searches the snapshot once, under the smallest allowed document id. Not in the synthetic
  corpus because the two retrievers differ there by design.
- Precision: pgvector stores and sums in float32; the order can differ from the old
  float64 order only on near-ties below about 1e-6; fused scores depend on ranks only.
- Carried into Phase 5 (spec item S4): `components.md` still names `RETRIEVAL_UNIT_CAP`.
- Scratch database `policy_atlas_p3_bench_test` (about 260 MB) stays on the local Postgres
  until the step-6 exit cleanup.

### Measurement round (e): retrieval in SQL, the JSON vector column gone (Phase 3 commit `2bd76a37` plus the judge and three-attempts commits; dev database at rev3)

Three runs, 2026-11-03 09:27 to 10:36 UTC, all `succeeded` (the obesity run lost one
synthesise attempt and re-ran it). Every figure read from `stage-walls-phase3e.{md,json}`,
`phase3e-search-chunks.txt`, `phase3e-retries.txt`, `phase3e-langfuse-errors.txt` and
the round (e) block of `phase2d-embed-overhead.txt`.

| run | question | status | total | acquire | screen_abstract | classify | ingest_full_text | screen_full | characterise | select | synthesise | outside |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 403ff2e3 | NEET | succeeded | 2158 | 67 | 20 | 12 | 1305 | 54 | 21 | 20 | 652 | 7 |
| 617a3e07 | zonal pricing | succeeded | 1749 | 56 | 24 | 15 | 1210 | 52 | 90 | 29 | 265 | 4 |
| 186238ad | childhood obesity | succeeded | 2339 | 88 | 17 | 18 | 783 | 41 | 107 | 262 | 304 (failed attempt) + 591 | 127 |
| median | | | 2158 | 67 | 20 | 15 | 1210 | 52 | 90 | 29 | 652 | 7 |

Documents ingested 126, 73 and 98 (units embedded 8,065, 4,140 and 8,909). Ingest split
A + B: NEET 463 + 840 (72 sleeps, 333 s), zonal 537 + 673 (58 / 285 s), obesity 264 +
518 (12 / 32 s). Embedding-loop overhead 91.8, 34.7 and 43.7 s (median 43.7 s, 8.4 ms a
unit, against 36.9 s and 4.6 ms in round (d)): the NEET run's loop absorbed the zonal
run's two failed batches (a 61 s read timeout and a 28 s throttle, re-sent in halves) in
the same process, so the JSON column's removal shows no gain this timer can see.

**The lever's own signal, `search_chunks` inside `run:synthesise` (Langfuse tool spans,
seconds):**

| question | round (c), Python: calls / median / p99 / sum | round (e), SQL: calls / median / p99 / sum |
|---|---|---|
| NEET | 38 / 0.296 / 3.414 / 19.2 | 40 / 0.514 / 6.303 / 33.7 |
| zonal | 29 / 0.114 / 0.431 / 4.8 | 30 / 0.247 / 1.111 / 9.7 |
| obesity | 30 / 0.360 / 20.747 / 44.8 | 42 / 0.605 / 8.177 / 50.9 (7 in the failed attempt, 35 in the re-run) |

Each SQL search is about twice the Python search's median (0.25 to 0.61 s against 0.11
to 0.36 s), as the quiet-machine measurement above predicted; no search errored. The
summed search time per run is 10 to 51 s, 5% of NEET's synthesise wall; the Python path's
one-time scope load (2 to 11 s on these scopes) is no longer paid, and neither code
version logs a scope-load event, so the net per run is read from the two sums only: NEET
+14 s, zonal +5 s, obesity +6 s. **Round-trip reading:** the median synthesise wall rose
374 → 652 s and the median total 1,815 → 2,158 s, and retrieval does not account for it:
NEET's synthesise took 652 s with 33.7 s of searches; the obesity run's 262 s select was
nine `select_rerank` timeouts (60 s each, two calls to their third attempt, two
`rerank_batch_failed` warnings, select still completed) and its 127 s outside any
component is the failed attempt's hand-back. This round's model stalls (40 retries: judge
10, rerank 7, screen_full 7, characterise_assign 4, classify 3, others 9; six calls to
attempt 2, three of them to a third attempt) were the heaviest of any round, which
dominates the walls. The SQL retriever's cost is the per-search figure in the table
(adjudication item, as stated above); its latency gain is the cap removal and the scope
load, not the search.

**The third attempt (D12 deviation):** the obesity run's first synthesise attempt failed on
three consecutive 80 s `judge_grounding` timeouts at 10:22:28, 10:23:50 and 10:25:11
(`run.failed component=synthesise`, "APITimeoutError: Request timed out."); the runner's
second attempt succeeded. The NEET judge call and the two `characterise_assign` calls that
reached attempt 2 went through on attempt 3. So the third attempt saved two calls this
round and did not save the one call that stalled three times.

**Database check (read-only):** `chunk_embedding` at rev3 has `embedding` and `tokens` and
no JSON column; 22,467 rows created 09:27 to 10:41, every one with both columns, no
duplicate (chunk, profile, policy, index) key, 11,570 distinct chunks. The three
`embed.summary` lines sum to 21,114 units; the 1,353-row difference (686 of them created
at 09:28, before the first embedding request at 09:36) is not explained here and is a
check for the review.

Server-log counts: `model_call.retry` 40, `cohere_rate_limited` 142, `status_code=429`
45, `component.failed` 0 (the failed attempt is logged as `run.failed`), `run.failed` 1.

## Phase 4a: parse profile v2, the per-document function, one stage path

### N7, D8: parse profile v2 — built, tests green

- New names: PDF `pymupdf4llm_v2` / `pymupdf4llm_struct_v2`; HTML `trafilatura_v2` /
  `trafilatura_para_v2`; JATS `jats_expat_v2` / `jats_struct_v2`; plain `plain_v2` /
  `plain_para_v2`. The parser recognises headings and table rows on the raw line as v1
  did, then applies `core.markup.strip_markup` (body lines; table rows with `table=True`
  so a row stays one line; headings cleaned in the locator). `parse_profile_for(content_type)`
  names the pair before parsing (raises `unsupported_type` for types the parser never
  takes).
- On the committed fixture corpus (13 documents): markup-bearing chunks 106 → 0 (v1 counted
  by running the v1 code at `528250f7` and by the test's own switch-off of the rule; 106
  on the PDF and JATS routes plus one HTML hit); chunk count, table chunks, pages and
  heading paths unchanged. E6's 186 → 0 was on ten real control PDFs that are not kept;
  the fixture corpus is the committed stand-in.
- Test re-pins (values only): the byte-identical digest across worker counts 1 and 4
  (`15f69fc2…` → `c84804da…`, same on two runs, old value kept in a comment); the v2 names in
  three tests; one JATS test now expects the parser's escape backslashes removed from the
  chunk text (the rendered markdown keeps them). `make prompt-guard` unchanged.
- **Known limits of the owner-approved rule (one line each):** a reference-list URL with
  paired underscores loses them (`Situation_report_-_the…` → `Situationreport-the…`), the
  tag pattern removes `<b and c>` from `a<b and c>d`, `*p*` in statistics becomes `p`, and
  a removed image can leave a double space. E6 measured the rule on PDFs only.

### N2, N3 (in-process half), N6, N9, D3, D4: the per-document function and the one-path stage — built, tests green

- `sourcing/ingest_document.py`: `ingest_document(connect, *, tss_id, run_id, fetcher, …,
  deadline, on_retryable_failure)` → `DocumentOutcome` (resolution `ingested` /
  `fetch_failed` / `parse_failed` / `late` / `not_queued`, reason, `already_in_store`,
  `retryable`, `written`, route, bytes, redacted attempts). One short read of the link row
  (returns `not_queued` unless `queued`), today's cascade moved not rewritten (Europe PMC
  XML first, URL cascade, landing-page discovery, open-access cross-check, reason
  priority), `Retry-After` on 429 and 503 (seconds or HTTP date, cap 30 s, malformed =
  today's 2 s, a wait that would pass the deadline is not started), the store key
  (`sha256(body)` × `parse_profile_for(content_type)`) looked up before parsing (a hit
  links without parsing), one forkserver parse process per call with the 120 s kill and
  denied sockets, then one short write transaction: snapshot `INSERT … ON CONFLICT (store
  key) DO NOTHING RETURNING`, re-select on conflict, chunks only when this call inserted,
  the link update guarded by `WHERE full_text_status = 'queued'` (rowcount 0 → `late`).
  The deadline reaches the fetcher through a contextvar so the fetcher protocol is
  unchanged.
- The shared row: snapshot `metadata` holds exactly `parse_profile`, `segmentation_policy`,
  `content_type`, `source_kind`; `fetched_from` and `ingested_by_run_id` live on the link
  row; a test asserts the exact column set and JSON keys and that no task, run, link id or
  URL is inside the JSON.
- `sourcing/ingest_queue.py`: `IngestMessage` (`link_row_id`, `run_id`, `schema = 1`, nothing
  else; a test pins the keys), `SendResult`, the `QueueClient` protocol, `LocalQueueClient`
  (thread pool; `workers=0` runs inline on the caller's thread for the rolled-back
  fixture), `build_queue_client` (`queued` raises until the SQS client lands in Phase 4b).
- `ingest_full_text_sources` is one path: eligible set in order; in its own committed
  transaction re-queue orphans (`ingest.orphans_requeued`), flip eligible rows to `queued`,
  commit, send; poll every 3 s on the component connection with ticks (`fetched=None`,
  `parsed` = ingested so far); rows the client could not send → `send_failed`; rows still
  `queued` at the deadline (or, in process, after `send` returned) → `not_ready`; embed at
  the end scoped to this run's full-text snapshots; counts gain `already_in_store` (a
  subset of `ingested`, counted from the store: this run's ingested rows whose snapshot
  predates the stage) and keep the invariant. The SSE summary hides `already_in_store`
  (G6); the tick schema already accepts a null `fetched`.
- Deleted: `_ParseScheduler`, `_run_parse_jobs`, `_drain_*`, `_IngestProgress`, the fetch
  thread pool and its rounds; `run_parse_worker` (one process per call, the `INGEST_SLOTS`
  bound kept) replaces them. Deleted tests and their replacements (rubric item 5):
  fan-out determinism 1 vs 4 → the corpus test at workers 1, 4 and inline with identical
  statuses, reasons and chunks; byte-identical scheduler output → the same digest
  `c84804da…` serial and four threads; timeout-does-not-swallow-sibling → a hung parse
  does not hold back a concurrent one; slow-first-job → a slow document holds only its own
  thread; batch-handover log → `fetch_s`/`parse_s` on the per-document log lines;
  parallel-fetch-matches-serial → the corpus test; progress ticks → rewritten for
  `fetched=None`; the ingest-slots test → rewritten on `run_parse_worker`.
- Plumbing: `POLICY_ATLAS_INGEST_MODE` in `api/settings.py` (`in_process` default,
  `queued`, anything else a startup error); `RunnerBackends.queue` and `.connect`;
  `with_ingest_queue` through the three construction paths (`deps.runner_backends_for`,
  the startup re-execution, the CLI); `run_harness(ingest_queue=, ingest_connect=)`.
- Tests (`test_ingest_stage.py`, own database with a real second connection): late write
  after close (no-op; next run links by key with the parser asserted not called;
  `not_queued` on a repeat call); two connections racing on the store key (one snapshot,
  both links ingested) and on the link row (one `ingested`, one `late`); orphans re-queued;
  one snapshot across two tasks; the connection count stays within a pool of 5 during a
  4-worker run; the fake-queue deadline scenario (`not_ready`, `send_failed`, the
  invariant); `Retry-After` cases. Whole targeted run: 2,349 passed, 1 skipped;
  `make prompt-guard` unchanged.
- **Flagged for the review:** (1) in-process mode now fetches on the parse worker threads
  (4 to 8 by cores) instead of 10 fetch threads plus 4 parse processes, so a laptop's or
  production's in-process ingest may fetch more slowly; the per-document round measures
  it. (2) Envelope (abstract) chunks are no longer embedded at this stage, only the
  run's full-text snapshots; the acquire stage embeds abstracts. (3) `not_ready` is not
  yet special-cased by the read models' access-failure counts (S2, finding 5): Phase 4b.
  (4) `run_parse_worker` imports `runtime.walk_pool` for the slot bound, heavy for the
  function's cold start: Phase 4b decides.

### Measurement round (f): the per-document function in process (Phase 4a commit `049e9429` plus the judge and three-attempts commits; dev database at rev3)

Three runs, 2026-11-03 10:45 to 11:44 UTC, all `succeeded`, no component or run failure.
Every figure read from `stage-walls-phase4f.{md,json}`, `phase4f-perdoc.txt`,
`phase4f-db.txt`, `phase4f-search-chunks.txt`, `phase4f-retries.txt`,
`phase4f-attempt3.txt`, `phase4f-langfuse-errors.txt` and the round (f) block of
`phase2d-embed-overhead.txt`.

| run | question | status | total | acquire | screen_abstract | classify | ingest_full_text | screen_full | characterise | select | synthesise | outside |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0b6005aa | NEET | succeeded | 2391 | 70 | 18 | 11 | 1417 | 69 | 383 | 20 | 398 | 5 |
| 8f9e2a57 | zonal pricing | succeeded | 1574 | 90 | 23 | 23 | 689 | 36 | 28 | 210 | 468 | 5 |
| 3c613457 | childhood obesity | succeeded | 1639 | 88 | 18 | 21 | 754 | 61 | 47 | 70 | 572 | 5 |
| median | | | 1639 | 88 | 18 | 21 | 754 | 61 | 47 | 70 | 468 | 5 |

**The first obesity launch failed before a run existed:** the task-agent turn timed out on
all three 60 s attempts, the API logged `api.unhandled_exception` and returned HTTP 500
(task 67997875, no run row); the orchestrator relaunched it. Flagged: a once-per-task step
cut three times in a row surfaces to the user as a 500, not as a reason-coded failure.

**The lever's own signal, the A split (fetch + parse) and the per-document outcomes:**

| run | ingest wall | A fetch+parse | B embedding | C tail | embed requests | sleeps n / s | documents ingested | units embedded | eligible |
|---|---|---|---|---|---|---|---|---|---|
| NEET | 1417 | 375 | 1039 | 3 | 83 | 107 / 553 | 127 | 7,164 | 215 |
| zonal | 689 | 311 | 378 | 1 | 38 | 30 / 141 | 68 | 3,605 | 226 |
| obesity | 754 | 416 | 337 | 1 | 74 | 1 / 4 | 96 | 7,078 | 264 |

Against round (e) (A 463 / 537 / 264 s on 231 / 255 / 258 eligible documents): the median
A fell 463 → 375 s, two runs faster and one slower; the corpora differ (acquire returns
different sets each round), so this is not like-for-like. Deviation 8's worry (fewer fetch
threads) does not show as a slower A: the summed parse time across NEET's ingested documents
was 2,038 s inside an A of 375 s, so the worker threads (by cores) keep the parse
subprocesses busy. The median ingest 1,210 → 754 s and total 2,158 → 1,639 s are mostly B
(the throttle sleeps: 553, 141 and 4 s) and fewer stalls, not this lever.

Per-document outcomes (every failure written with its reason; `ingested + failed =
attempted` in every run and the database statuses match the log; no `late`, `not_queued`,
`not_ready`, `send_failed` or re-queued orphan):

| run | ingested | of which `already_in_store` | fetch_failed | parse_failed | retryable |
|---|---|---|---|---|---|
| NEET | 127 | 1 | 79 (blocked_by_host 40, paywall 23, fetch_error 11, not_found 3, blocked 2) | 9 (empty 7, thin_text 1, timeout 1) | 11 |
| zonal | 68 | 1 | 107 (fetch_error 50, blocked_by_host 35, paywall 10, blocked 8, not_found 4) | 51 (empty 51) | 50 |
| obesity | 96 | 2 | 138 (paywall 54, blocked_by_host 49, fetch_error 14, not_found 13, blocked 5, timeout 2, too_large 1) | 30 (empty 25, blocked_by_host 2, thin_text 2, timeout 1) | 16 |

Round (e), same query: ingested 126 / 73 / 98, parse_failed 8 / 65 / 28, fetch_failed 97 /
117 / 132. The store (`source_snapshot`, key `body_hash` × `parse_profile` ×
`segmentation_policy`): before this round every row had a null body hash (rev2 does not
backfill it), so the four `already_in_store` hits were pairs of records in the same task
that fetched identical bytes; new profile rows `jats_expat_v2` 45, `pymupdf4llm_v2` 168,
`trafilatura_v2` 74 (287 snapshots for 291 ingested links). `fulltext.summary` reports
`already_in_store=0` because it counts snapshots created before the stage started; the
per-document records carry the four. Noted for the review (the two counts measure
different things).

Embedding-loop overhead: 28.7, 75.9 and 53.1 s (median 53.1 s, 7.9 ms a unit, gap 226 ms;
round (e) 43.7 s, 8.4 ms, 272 ms); NEET's loop re-sent four throttled batches in halves.

`search_chunks` inside synthesise: NEET 38 calls / median 1.507 s / p99 12.2 s / sum 80.2 s;
zonal 26 / 0.682 / 4.9 / 30.1; obesity 29 / 0.540 / 6.6 / 39.9 (round (e): 0.514, 0.247,
0.605 medians). No search errored. The two slower sessions overlapped another run's
embedding-heavy ingest (zonal's synthesise ran under NEET's ingest, NEET's under obesity's);
obesity's synthesise ran alone and matched round (e). The laptop's Postgres shares its 128
MB of buffers with the writes, so the per-search figure under a concurrent ingest is the
upper bound; not a lever of this round.

Stalls: 47 retries (classify 11, rerank 7, screen_full 6, judge 6, characterise_assign 5,
section_turn 4, screen_abstract 4, task_agent_turn 2, characterise_discover 2; 44 timeouts,
3 connection errors); seven calls reached attempt 2. Outcomes: one NEET
`characterise_assign` batch cut three times (`assignment_batch_failed`, batch of 40; its
repair call succeeded on attempt 3 in 11.5 s; characterise 383 s), three zonal
`select_rerank` batches cut three times each (`rerank_batch_failed`; select 210 s), one
obesity judge call cut twice then succeeded in 7.2 s, and the failed launch above. Server-log
counts: `model_call.retry` 47, `cohere_rate_limited` 146, `status_code=429` 42 (all OpenAlex
and fetch retries), `component.failed` 0, `run.failed` 0.

Database check: 17,847 distinct `chunk_embedding` rows under the three tasks' full texts in
the round's window, equal to the summed `units_embedded`; 1,453 more rows in the window are
not under these full texts (round (e) had 1,353 such rows). The lead's reading: the acquire
stage's abstract (envelope) embeddings, written during acquire (round (e)'s 686 rows at
09:28 fall inside acquire); round (g) checks the chunk kind.

## Phase 4b: adaptive embedding, SQS client, handler (N1 to N5, D1, D4, D5, D6)

Built, targeted tests green (2,461 passed on the agent's database after the two judge-effort
pins in `test_model_routes.py` were updated for D14); lint, typecheck, `make prompt-guard`
and `make audit` green (the Linux-only `awslambdaric` pin audited separately with
`pip-audit --no-deps`: no known vulnerabilities; CI on Linux scans it in the lock).

- **Adaptive pool (D6):** `core/embeddings.AdaptivePool` owns concurrency and backoff. The
  backends raise `Throttled` (Cohere on `ThrottlingException` or "too many tokens"; OpenAI
  on 429 with its Retry-After) instead of retrying throttles internally; other errors keep
  the in-backend retry. Width starts at 2, cap `route().embeddings.pool_cap` (8 on every
  route; strict key); a throttle halves the width (floor 1; one burst counts once), puts
  the batch back at the front and sleeps the provider's Retry-After (cap 60 s) or today's
  backoff curve; five clean batches in a row add one. A batch throttled eight times in a
  pass is given up (`embed.batch_failed`, chunks stay pending). Throttling never splits a
  batch. Requests run on a thread pool sized to the cap; writes stay on the calling thread.
  Logs: `embed.pool_width` on every change and one `embedding.<provider>_rate_limited` per
  throttled round with `sleep_s`, so `stage_walls.py` still reads the split. Every caller
  goes through a pool; one-off query embedding uses `embed_with_retry`.
- **The stage embeds as documents land:** a `_StageEmbedder` thread runs from the start of
  the stage with its own connection; each tick hands it the snapshots that became
  `ingested`; before returning the stage hands it every ingested snapshot (including
  already-ingested documents lacking vectors under the current profile), joins and logs one
  `embed.summary`. Inline test mode embeds at the end on the test connection. One more
  database connection per stage (the connection budget gains one per run).
- **SQS client (N1):** `SqsQueueClient` sends batches of 10 with bodies of exactly
  `link_row_id`, `run_id`, `schema` (tests pin the keys and that no value is a URL or a
  user id), partial and whole-call failures reported with the SQS reason; `queued` mode
  needs `POLICY_ATLAS_INGEST_QUEUE_URL` and fails loud at startup without it; wired
  through the three construction paths; the queued stage deadline is 600 s.
- **Handler (N2, D5):** `ops/ingest_worker.handler`: one record only; schema 1; deadline =
  remaining time − 10 s; attempt from `ApproximateReceiveCount`. Decision table: malformed
  body → reported for redelivery (dead-letters after the second); ingested or a store hit
  → written; a non-retryable failure → written with its reason; `not_queued` / `late` → no
  write; attempt 1 with a retryable outcome (timeout, fetch error, the deadline cut, a
  foreign-key failure on the link write because the snapshot was pruned underneath) → row
  left `queued`, record reported for redelivery; attempt 2 or later → written (the
  foreign-key case retries `ingest_document` once first). Cold start reads the secret's
  `db_connection_string` once through `POLICY_ATLAS_DB_SECRET_ARN`, builds a `NullPool`
  engine and a live fetcher; no model client; JSON logging with a URL-redaction processor
  (scheme, host, path only); bound fields `message_id`, `attempt`, `tss_id`, `run_id`.
- **Cold-start weight:** `INGEST_SLOTS` moved into `ingest_full_text.py` (re-exported by
  `runtime.walk_pool`) so the parse worker no longer imports the walk pool, classify and the
  scoping plan; `ops/__init__.py` no longer imports the operator CLI (which needs
  `mypy_boto3_cognito_idp`, absent from the image: the handler would not have imported in
  Lambda). A subprocess test hides that package, imports the handler and asserts none of
  `ops.cli`, `ops.commands` or `policy_atlas.runtime` loaded.
- **`not_ready` out of the access-failure vocabulary (S2, finding 5):** the read models'
  two status ladders treat `not_ready` and `send_failed` as "not read yet" (the row reads
  `relevant` / `not_selected` with no reason; the frontend already shows "The full text
  hasn't been read"); `by_reason` still names them and the counts invariant holds. Two
  status tallies (`steering_bundles._full_text_status_counts`, characterise's reason counts)
  still count them under `fetch_failed`; noted for the review.
- Tests: pool convergence under a fake quota (settles at 2 to 4 for an allowance of 3, no
  batch split, every chunk embedded) and the climb to the cap; the throttle budget; the
  message shape; batches of 10 and partial failures; the three queued-mode scenarios with a
  fake queue, a fake clock and real second connections (all early; some late with the late
  write a no-op and the read model saying `relevant`; deadline hit with orphans re-queued),
  each checking the invariant, `already_in_store` inside `ingested` and `fetched=None`
  ticks; 15 handler tests with a fake event, context and Secrets Manager.
- Dependency (G3): `awslambdaric>=3,<4; sys_platform == 'linux'` in the main group; the lock
  adds `awslambdaric` 3.1.1, `simplejson` 4.2.0, `snapshot-restore-py` 1.0.0.
- Open for staging: whether the forkserver parse subprocess runs inside Lambda (no
  `/dev/shm`); the emulator run below exercises it on the laptop.

### Measurement round (g): the branch head with every lever (`f908e9f7`: the adaptive pool, the stage embedding as documents land; dev database at rev3)

Three runs, 2026-11-03 11:59 to 12:36 UTC, all `succeeded` (the obesity run lost one
synthesise attempt and re-ran it). Every figure read from `stage-walls-phase4g.{md,json}`,
`phase4g-pool.md`, `phase4g-pool-width.tsv`, `phase4g-perdoc.txt`, `phase4g-db.txt`,
`phase4g-search-chunks.txt`, `phase4g-retries.txt`, `phase4g-retry-outcomes.txt`,
`phase4g-quotes.txt` and `phase4g-events.txt`.

| run | question | status | total | acquire | screen_abstract | classify | ingest_full_text | screen_full | characterise | select | synthesise | outside |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| c6e72278 | NEET | succeeded | 850 | 61 | 29 | 10 | 191 | 45 | 16 | 18 | 477 | 3 |
| a1aa2d44 | zonal pricing | succeeded | 680 | 65 | 18 | 11 | 225 | 35 | 25 | 23 | 273 | 4 |
| 1f482579 | childhood obesity | succeeded | 1438 | 65 | 27 | 12 | 246 | 51 | 41 | 31 | 92 (failed attempt) + 745 | 129 |
| median | | | 850 | 65 | 27 | 11 | 225 | 45 | 25 | 23 | 477 | 4 |

**Not like-for-like with round (f) on ingest:** 53, 38 and 30 of the ingested documents
(of 83, 73 and 109) were `already_in_store` from round (f)'s snapshots (the N9 store key
in action: same bytes, same profile, no second parse), so far fewer units were embedded
(1,773, 2,058 and 11,329 against 7,164, 3,605 and 7,078). The ingest wall of 191 to 246 s
against 689 to 1,417 s is therefore the store reuse plus the pool, not the pool alone.

**The lever's own signals (the pool and the overlap):**

| run | ingest wall | first embed request (s into the stage) | last document landed | `embed.summary` | embedding after the last document | requests | throttle sleeps n / s | pool max width | time-weighted mean width | halvings / climbs | max requests in flight |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NEET | 191 | 6.2 | 121.1 | 190.8 | 69.7 | 31 | 0 / 0 | 8 | 5.9 | 0 / 6 | 3 |
| zonal | 225 | 3.1 | 134.3 | 225.3 | 91.0 | 48 | 11 / 70 | 5 | 1.9 | 4 / 5 | 3 |
| obesity | 246 | 3.1 | 181.5 | 246.1 | 64.7 | 158 | 12 / 38 | 8 | 3.3 | 6 / 14 | 8 |

Embedding now starts a few seconds into the stage and runs beside fetch and parse (the A
split of earlier rounds is no longer a fetch-plus-parse measure; "last document landed" is).
The pool climbed to 8 on NEET without a throttle (but never had more than 3 requests in
flight: each pass held few batches), oscillated between 1 and 5 on zonal under 11 throttles,
and on obesity (the only run embedding alone, 11,329 units) reached 8 twice and was halved
six times by 12 throttles (38 s of sleeps against round (f)'s 1 / 4 s on a similar unit
count with one request in flight): **at width 8 the pool finds the quota's edge on its own
and backs off; the throttle count is the cost of probing it.** No `embed.batch_failed`.
Idle time inside B (no request in flight, which now includes waiting for documents): 80, 134
and 85 s. The 65 to 91 s of embedding after the last document is the tail the stage still
waits for.

Per-document outcomes (all written; no `late`, `not_queued`, `not_ready`, `send_failed`,
orphan): ingested 83 / 73 / 109 (`already_in_store` 53 / 38 / 30), fetch_failed 71 / 113 /
134, parse_failed 6 / 46 / 21, retryable 9 / 50 / 15 (reasons as in round (f):
`blocked_by_host`, `paywall`, `fetch_error`, `empty` lead). The zonal `already_in_store`
is 38 in the per-document records and 37 in `fulltext.summary` and the database (deviation
20 again).

`search_chunks` inside synthesise: NEET 24 calls / median 0.298 s / sum 9.5 s; zonal 23 /
0.185 / 7.2; obesity 44 / 0.609 / 37.8 (4 in the failed attempt). With no concurrent ingest
the SQL search medians are back at round (e)'s level or under (0.19 to 0.61 s), which
supports the reading in round (f) that the 1.5 s medians there were the laptop's Postgres
under a concurrent embedding write load.

Stalls: 78 retries (screen_abstract 48, 47 of them in the obesity run at its 7 s timeout
across the 48-wide pool; section_turn 10, judge 9, screen_full 6, key_findings 2, others
3); 73 calls to attempt 2 (every one succeeded there except five), five to attempt 3, four
of which succeeded. **The fifth, an obesity `synthesise_section_turn` call, was cut three
times at 23.2, 23.2 and 23.1 s and failed the synthesise attempt** (component and run
failed at 12:24:13; the runner's second attempt succeeded in 745 s). Three identical cuts
at the limit say the call needed more than 23 s, not that it stalled: the 23 s is 2 × the
healthy p99 from the Phase 0 sample, and this section was longer than that sample's. The
obesity run's 129 s outside any component is one `propose_sections` attempt that hung to
its 120 s cut, then succeeded in 4.4 s. Server-log counts: `model_call.retry` 78,
`embedding.cohere_rate_limited` 23, `status_code=429` 39 (OpenAlex and fetch retries),
`run.failed` 1.

**N7 on the fixed questions (rubric 17):** the served code stores passing citations only,
so the failed quotes were read from the repair-call inputs and the synthesise outputs in
Langfuse and re-verified with the served `qv_v2`: verified 121 / 120 / 126 (exact plus
normalised), failed 0 / 1 / 2 (a case-study card; two `quote_not_found` claims), **0 of 3
with markup characters in the matched window**, and no markup in the failed quotes
themselves. Persisted citations 100 / 102 / 113, all passing.

**Database check:** 16,378 `chunk_embedding` rows in the window, 15,160 under the three
tasks' full-text snapshots (equal to the summed `units_embedded`) and 1,218 on their
`abstract_only` (envelope) snapshots, equal to acquire's units embedded (430 + 323 + 465).
Acquire's units in rounds (e) and (f) were 1,353 and 1,453: exactly those rounds' surpluses.
**Deviation 17 is explained**: the surplus rows are the acquire stage's abstract embeddings.

**For the owner's content reads (rubric 28, N7 and N8):** NEET task `7c60d15e`, synthesise
run `61e2c04b`, artefact `7796f163`; zonal task `0fb750d7`, run `9dd9f946`, artefact
`c5961a67`; obesity task `1c1f7d04`, run `54759cda`, artefact `c3be6e81` (all round (g),
HEAD; full ids in `phase4g-runtable.txt`).

**Across the rounds (medians of three runs, seconds; each round's corpus differs, and the
store reuse in (g) is real but one-off for a repeated question):**

| round | lever added | total | ingest | synthesise | notes |
|---|---|---|---|---|---|
| baseline | none (like-for-like before) | 1,493 | 939 | 258 | obesity degraded on a characterise wire check |
| (a) | step timeouts | 1,698 | 942 | 438 | |
| (b) | widths 12 → 48, 4 → 10 | 1,757 | 872 | 494 | |
| (c) | judge at low, 80 s | 1,815 | 1,164 | 374 | |
| (d) | binary vector writes | 1,479 | 767 | 360 | obesity failed (two stalls) |
| (e) | SQL retrieval, JSON column gone | 2,158 | 1,210 | 652 | heaviest stalls |
| (f) | per-document function | 1,639 | 754 | 468 | |
| (g) | adaptive pool, embedding as documents land | 850 | 225 | 477 | 30 to 53 documents per run from the store |
| (h) | the review's fixes and the owner-ruled timeouts (floor 15 s, multiples of 5 s) | 881 | 221 | 409 | 43 to 82 documents per run from the store; obesity lost one synthesise attempt (a judge call failed all three attempts) |

### Measurement round (h): the reviewed commit `967f2212` (the review's 21 fixes; the owner-ruled timeouts; run at the review, step 7)

Three runs, 2026-11-03 17:47 to 18:23 UTC, all `succeeded`; the obesity run lost one
synthesise attempt and re-ran it. Run by a builder agent from `../policy_atlas-live` at the
reviewed commit; every figure read back from `stage-walls-h.{md,json}`,
`round-h-retry-outcomes.txt`, `round-h-cuts.txt`, `round-h-perdoc.txt`, `round-h-db.txt`,
`round-h-pool.md`, `round-h-search-chunks.txt`, `round-h-quotes.txt` and
`round-h-events.txt` (session scratchpad, `round-h/`). Load average 15.5 / 35.9 / 54.4 before
the round, 4.3 / 5.9 / 14.7 after; no test suite ran beside it.

| run | question | status | total | acquire | screen_abstract | classify | ingest_full_text | screen_full | characterise | select | synthesise | outside |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| c30c1a32 | NEET | succeeded | 787 | 97 | 37 | 15 | 221 | 59 | 20 | 23 | 310 | 4 |
| 28724f1c | zonal pricing | succeeded | 881 | 75 | 21 | 18 | 233 | 48 | 28 | 44 | 409 | 4 |
| 24b8fff3 | childhood obesity | succeeded | 1287 | 61 | 40 | 32 | 203 | 48 | 72 | 80 | 333 (failed attempt) + 414 | 3 |
| median | | | 881 | 75 | 37 | 18 | 221 | 48 | 28 | 44 | 409 | 4 |

**Ingest split and the pool:** ingest walls 220.5 / 232.7 / 203.1 s; first embed request
6.4 / 17.1 / 3.2 s into the stage; last document landed 218.4 / 176.4 / 190.6 s; embedding
after the last document 0.9 / 56.2 / 12.5 s; requests 40 / 47 / 121; throttle sleeps 0 /
9 (44.3 s) / 0; pool max width 8 / 7 / 8; `already_in_store` 82 / 50 / 43 (eligible 202 /
267 / 270). Not like-for-like with round (g): more store reuse (53 / 38 / 30 there), different
eligible sets, and NEET and zonal overlapped on ingest (183 s) and synthesise (243 s). Also
not like-for-like: six `capability_run` rows on other tasks started in the round's window
(the builder's run table), and Langfuse holds 232 generations in the window from sessions
outside the three runs, on `openai-direct` model names (`gpt-5.4-mini`, `gpt-5.6-luna`,
`gpt-5.6-terra`): a second server on the dev database ran other work beside the round.

**Failed-attempt rate per step, the three sessions only (Langfuse, read at the review):**
screen_abstract 6 of 328 (1.8%), screen_full 1 of 101 (1.0%), classify_document 45 of 315
(14.3%, the one 16 s burst), synthesise_section_turn 6 of 48 (12.5%), judge_grounding 6 of
43 (14.0%), select_rerank 5 of 16 (31%), characterise_assign 3 of 10 (30%),
write_block_summary 2 of 32 (6%). The judge and the screen steps run the same model
(`gpt-6-luna`); the rate follows the healthy call's length, not the model: the steps whose
healthy calls take 5 to 12 s (judge 5.5 s median, rerank and characterise 11 s, section
turns 6.4 s on `gpt-6.1-terra`) lose 10 to 30% of attempts, the steps whose calls take 1 to
2 s lose 1 to 2%. That is the shape of a hazard per second in flight (a connection or
routing path that drops at some rate while a request is open), not of a per-request fault.

**Per-document outcomes:** ingested 122 / 93 / 100, fetch_failed 71 / 118 / 143, parse_failed
9 / 56 / 27, retryable 9 / 48 / 17; `not_ready`, `send_failed`, `worker_error`, `late`,
orphans, `embed.batch_failed` and `embed.batch_deferred` all 0; `already_in_store` agrees
across the per-document records, `fulltext.summary` and the database (deviation 20 did not
recur).

**`search_chunks` inside synthesise:** NEET 34 calls / median 0.352 s / sum 15.2 s; zonal
31 / 0.303 / 15.7; obesity 50 / 0.665 / 39.7 (both attempts).

**Retries (the owner-ruled timeouts, served: the `[routes.bedrock.steps]` table of
§ Owner rulings):** 79 retry lines; 73 calls reached attempt 2 (67 succeeded there), 6
reached attempt 3 (4 succeeded, 2 failed). 72 attempts were cut at their timeout and 67
recovered on the next attempt: `classify_document` 44 at 15 s (all recovered; **all 45
classify retry lines fell in one 16 s window, 18:02:55 to 18:03:11**, with zonal's three
summary cuts in the same stretch: a burst at the 48-wide step, the shape probe 3 measured);
`select_rerank` 6 at 25 s (4 recovered); `judge_grounding` 5 at 80 s (2 recovered);
`screen_abstract` 5 at 15 s, `synthesise_section_turn` 4 at 25 s, `characterise_assign` 3
at 30 s, `synthesise_write_block_summary` 2 at 15 s, `screen_full`, `synthesise_judge_summary`
and `task_agent_turn` 1 each (all recovered). Nine further attempts ended in a connection
error; 72 + 9 = 81 = the Langfuse `ERROR` generations.

**Component failures, the only two calls that failed all three attempts (both obesity):**

1. `judge_grounding` call `11b9278adc0a`: a connection error after 26.9 s, then two cuts at
   80.1 s; the synthesise component failed at 18:15:46 (the 333 s attempt) and the runner's
   second attempt succeeded in 414 s.
2. `select_rerank` call `7fd65fc0d37c`: cut at 25.1 s, a connection error at 16.0 s, cut at
   25.1 s; select's own batch retry (25 documents) succeeded, so no component failed.

**Rubric 22's clause "zero components retried because every attempt was cut" did not hold
in substance** (one synthesise re-run). Strictly, no call was cut three times: each of the
two calls had one connection error among its three attempts. The reading for the owner: the
judge's failure (a dropped connection mid-call, then two 80 s hangs on the same call) is the
stale-connection shape stall probe 2 would test; the burst cuts are connection setup at
width 48 (probe 3) and all recover on attempt 2 at a cost of 15 s each.

**Quotes (N7):** re-verified exact / normalised / failed 123 / 4 / 0, 148 / 4 / 0, 173 / 1 / 0;
no quote failure had markup in its window.

## Phase 5: infra, config, documents

### N4, N5, N11, G5: CDK — built, `make -C infra test` 113 passed (18 new)

- `infra/infra/components/ingest_worker.py` (`IngestWorker`): queue `policy-atlas-v3-ingest`
  (retention 4 days, SQS-managed encryption, TLS-only policy, visibility timeout 210 s =
  180 + 30, dead-letter after 2 receives), dead-letter queue (14 days, encrypted,
  TLS-only), `DockerImageFunction` from the SAME backend image asset as the API and
  migration tasks (one `DockerImageAsset`, one image hash in the assets file), command
  `python -m awslambdaric policy_atlas.ops.ingest_worker.handler`, 1,769 MB, 180 s,
  512 MB ephemeral storage, private subnets, own security group admitted to the database
  group on 5432 only, environment exactly `POLICY_ATLAS_DB_SECRET_ARN`,
  `POLICY_ATLAS_MODEL_ROUTE`, `LOG_FORMAT=json` (a test asserts no key-like variable),
  `GetSecretValue`/`DescribeSecret` on the **database** secret only (the app secret holds
  the model keys, which D6 forbids the function to hold; plan P13's "app secret" wording
  was the error), no Bedrock statement, log group `/policy_atlas_v3/ingest` kept 30 days;
  event-source mapping batch size 1, batching window 0, `MaximumConcurrency` 20,
  `ReportBatchItemFailures`. The API task role may `SendMessage`/`GetQueueAttributes`/
  `GetQueueUrl` on the queue only; its environment gains `POLICY_ATLAS_INGEST_MODE`
  (`pa_config.json`: staging `queued`, prod `in_process`; an unknown value fails at synth)
  and `POLICY_ATLAS_INGEST_QUEUE_URL`.
- Alarms: dead-letter depth ≥ 1 (app stack); NAT `NetworkOut` above 1 GB per 5 min for 3
  periods, the busiest of the three fck-nat groups (network stack; threshold documented as
  "a first guess, review on staging"); writer `CPUCreditBalance` below 50 (database
  stack). **No alarm has an action: the stacks had no SNS topic before this slice**; they
  show state in the CloudWatch console only (deferred: a notification topic).
- **For the owner (G5 checkpoint):** a read-only `cdk diff` against staging was run with
  the already-signed-in `pa-staging` session (`--no-change-set`): cert stack unchanged;
  network and database stacks one alarm each; app stack additions only (the 12 ingest
  resources, the ingress rule, the task-role policy; the two task definitions replaced as
  on every deploy for the new image hash and the two environment entries; the service
  gains a `DependsOn`); nothing removed, nothing stateful replaced. The trimmed synth was
  committed as `cdk-synth-ingest.json` in `69f044be` (placeholders for account, VPC and
  subnet ids) and removed from the folder on 2026-11-04: the infra tests pin every resource,
  and the file was already stale on the egress rules (ruling 7). The prod diff needs the `pa-prod` profile. **Owner information:**
  the VPC has three fck-nat instances (one per availability zone), not the one the
  network stack's comment and contract D5 describe.
- `infra/DEPLOYMENT.md` gains the ingest-function section (plain-language terms, sizing,
  `ingest_mode` per environment, the alarms table, the dead-letter drain-and-inspect
  commands, the deploy-order note: the function updates before the migration runs).
- Points carried into the backend: the handler is started with a bare `python` (Lambda
  applies the image's `PATH`; if the first staging start cannot import `awslambdaric`,
  switch the command to `/app/.venv/bin/python`); the secret ARN is the name-based ARN
  without the 6-character suffix (`GetSecretValue` accepts it; the grant uses the
  wildcard); the function pulls its image from the CDK bootstrap repository as CDK's own
  image functions do.

### D3, N12: the retention rule and its script — built, tests green

**Retention rule (the text the data-flow note carries):** a full-text snapshot that no link
row references (through `full_text_snapshot_id` or `source_snapshot_id`), that no
citation quotes and that no extraction record names, is deleted with its chunks and
embeddings once it is older than 90 days, by an operator running
`scripts/prune_unlinked_snapshots.py --apply` by hand (dry run by default; no scheduler
in this slice). Locking: each batch is one transaction that picks the oldest candidates,
locks them `FOR UPDATE SKIP LOCKED` (a snapshot an ingest is linking at that moment holds
the key lock and is skipped), re-checks in the same transaction that no link row points
at each locked snapshot, then deletes and commits; a link attempted after the lock waits
and, if the snapshot is then gone, fails its foreign key and the ingest retries. Tests
(8): old unlinked goes; linked either way, young, envelope stay; dry run deletes nothing;
a link committed between pick and lock is caught by the re-check; a link in flight at lock
time is skipped; a link attempted after the lock blocks. The citation and extraction
guards go beyond D3's "no link row" wording because both tables hold foreign keys to the
snapshot (owner to note).

### S1 to S5 applied; deferred entries written

The five owner-accepted spec items are applied as built with one entry in
`docs/specs/log.md` (2026-11-03); `docs/deferred.md` gains the task 057 section (rubric item
7: the dropped parse rules with E6's numbers, the fallback-parser signals, per-host
coordination, the retention script's scheduling, HNSW, per-claim judge filtering with E9's
numbers, the low-effort judge revisit with E3's numbers, the prod route flip, plus alarm
actions, the three NAT instances and a second retry on once-per-run steps) and closes the
056 seam "timeout retries are billed but untraced". The plan's "two knowledge concepts"
(Phase 5.3) are left to step 8 as the task-cycle-build skill directs (durable records are
authored against the reviewed code); the candidates are listed under § Review handoff.

## Owner rulings after the exit (2026-11-03, same day, before the review)

The owner read the exit report and ruled three things; they are applied on the branch
under the same gate (a second exit commit, § Commands run).

**1. Timeouts for every step with at least 30 healthy calls, floor 15 s** (contract D12
said n ≥ 100 and floor 5 s; the owner lowered the sample floor and raised the time floor
after the burst stalls at the 48-wide steps). `scripts/step_timeouts.py` gains `--min-n`
and `--floor` (defaults unchanged, test added); re-derived from the Phase 0 cache (the
pre-tightening sample, so the tightened steps' p99s are not truncated at their new
timeouts):

| step | n | p99 s | before | now |
|---|---|---|---|---|
| classify_document | 4739 | 5.3 | 11 | 15 (floor) |
| screen_abstract | 7876 | 3.3 | 7 | 15 (floor) |
| screen_full | 921 | 3.9 | 8 | 15 (floor) |
| select_rerank | 85 | 11.7 | 60 | 25 |
| characterise_assign | 57 | 12.7 | 60 | 30 |
| extract_interventions | 1415 | 16.4 | 33 | 35 |
| search_generate_queries | 95 | 3.5 | 60 | 15 (floor) |
| synthesise_propose_sections | 30 | 4.3 | 120 | 15 (floor) |
| synthesise_write_block_summary | 254 | 2.7 | 6 | 15 (floor) |
| synthesise_judge_summary | 277 | 2.3 | 5 | 15 (floor) |
| synthesise_section_turn | 424 | 11.0 | 23 | 25 |
| synthesise_write_source_note | 33 | 1.8 | 30 | 15 (floor) |
| judge_grounding | 254 | 19.8 | 80 (raised once, D12) | 80 (kept) |
| longlist_assign | 71 | 22.6 | 60 | 50 |
| option_profile_line | 65 | 41.7 | 60 | 85 (its p99 was already over today's value) |
| option_profile_place_sentences | 111 | 17.1 | 35 | 35 |

Every value is rounded up to a multiple of 5 s (owner, same day; the script gains
`--round-to`). Every other step has fewer than 30 healthy calls and keeps its `[steps]`
value (the full table is the script's output with `--min-n 30 --floor 15 --round-to 5`). The once-per-run
`propose_sections` step that stalled for 120 s in rounds (a) and (g) now costs 15 s per
stall. Rubric 22's "2 × p99 from at least 100 calls" reads "at least 30, floor 15" from
here on, by the owner's word.

**2. The two markup-rule edge cases that could delete content are closed** (the tag rule
limited to known HTML tag names, so `x<y and y>z` stays whole; the emphasis rule needs a
non-letter before its opening marker, so `Situation_report_-_the` keeps its underscores).
Result: see the diff note below this list.

**3. The stall probes are written as a brief for the review conversation**
(`stall-probes.md`, committed in `c89aba82` and removed on 2026-11-04 once the probes had run; the results are in § Review findings): Bedrock only (`openai-direct` is legacy); three
probes (did the hung requests reach the service; connection re-use on or off; the burst
shape at width 48) with the reading of each outcome.

Markup diff note: `core/markup.py` gains `_HTML_TAGS` (a fixed set of 70 common tag
names, the single source of the tag pattern, sorted longest first; a tag-shaped span whose
name is not in the set stays, e.g. `x<y and y>z`, `<unknown>`), and `_EMPH_RE` gains the
lookbehind `(?<![A-Za-z0-9])` on the opening marker (`snake_case_name` and
`Situation_report_-_the` keep their underscores; `_em_`, `*it*`, `<B>loud</B>` still
strip). `markup_deletions` shares the same patterns, so the quote verifier moves with it.
Tests: four lines added to the agreement set and six examples (46 passed). The module
docstring's rules 4 and 6 are reworded.

**A third content loss found by the gate, fixed in the same spirit (the owner to note):**
the byte-identity digest moved under the two edits, and the one differing chunk was a
statistics table line in `frontiers_school_readiness_2022` whose raw text is
`0.47* 0.50** 0.54***` (significance stars). The old rule returned `0.47* 0.50* 0.54`
and the two edits alone returned `0.47* 0.50 0.54`: the stray-marker rule deletes `**`
and `***` wherever they stand, so both versions lose p-value stars. The stray rule now
leaves a star run that follows a digit or another star (`(?<![0-9*])\*\*+`), the line
is kept whole, and the digest is re-pinned (`c84804da…` → `59655557…`, old value in the
comment). One chunk of the four fixture documents differs from the old rule, that line
only.

## Checks beyond the build

- **Deterministic tests (all in `make verify`; the named ones per phase above):** the
  migration round trip through rev1, rev2 and rev3 with a resumed backfill and the float32
  downgrade (`test_migration_057_document_store.py`); the synthetic retrieval corpus against
  both retrievers (`test_retrieval_synthetic.py`); the fixture corpus giving the same
  statuses inline and at 1 and 4 workers, the two real-connection races (store key, link
  row), orphans re-queued, `already_in_store` across two tasks, the connection count within
  the pool, the three fake-queue scenarios (`test_ingest_stage.py`); the 15 handler
  decision-table tests with a fake event, context and Secrets Manager
  (`tests/ops/test_ingest_worker.py`); the pool convergence under a fake quota
  (`test_embeddings.py`); every call site passing its step and the exhaustion of three
  attempts (`test_step_timeout_sites.py`, `test_traced_attempts.py`); the markup strip both
  ways with the offset map (`test_markup.py`, `test_parse_profile_v2.py`); the retention
  script's lock cases (`test_prune_unlinked_snapshots.py`); the deploy waiter's shell test
  (`make deploy-migration-wait-test`, fake `aws` only); the 18 new CDK pins
  (`infra/tests/unit/test_ingest_worker.py`).
- **AI evals:** none. The grounding judge's first-pass verdict counts (rubric 31) are
  counts read from traces, not a scored eval; the owner's content read decides.
- **Manual, API and database:** seven live measurement rounds of the three fixed Evidence
  search questions plus the fixed scoping question on the dev server (sections above, run
  ids per round); the retrieval parity script on the runs' own queries (88 of 88, then 68 of
  68 after rev3); the Lambda handler under the Runtime Interface Emulator on the built
  image; the cold-import timing of the image before and after compiled bytecode; a
  read-only `cdk diff` against staging; read-only checks of `chunk_embedding` after rev3.

## End-to-end command

Every measurement round used the same thread. The commit under measurement is served from a
second worktree so the main tree stays editable; the main tree's `backend/.env` is read by
the server and by the scripts (`set -a; source backend/.env; set +a` in the shell, never
printed).

```bash
# 1. serve the commit under measurement (two concurrent walks by default, RUN_EXECUTOR_MAX)
git -C ../policy_atlas-live checkout --detach <commit>   # plus cherry-picks for lever isolation
(cd ../policy_atlas-live/backend && uv sync && \
 uv run --env-file /Users/shabeer.rauf/repos/policy_atlas/backend/.env \
   uvicorn policy_atlas.api.app:create_app --factory --port 8000 > <scratchpad>/live-server-<round>.log 2>&1 &)

# 2. the fixed questions as fresh tasks (the third starts when a slot frees; the scoping
#    question in rounds (a) to (c))
uv run --project backend python scripts/fixed_questions.py --only neet --only zonal
uv run --project backend python scripts/fixed_questions.py --only obesity
uv run --project backend python scripts/fixed_questions.py --only scoping

# 3. the per-stage walls and the ingest split, read from the database and the server log
uv run --project backend python scripts/stage_walls.py --run-id <id> --run-id <id> --run-id <id> \
  --logs <scratchpad>/live-server-<round>.log --format md --out stage-walls-<round>.md

# 4. the per-step timeouts from Langfuse (Phase 0; the cache holds timing fields only)
uv run --project backend python scripts/step_timeouts.py --since 2026-11-02 --cache <scratchpad>/langfuse-obs.json --format toml

# 5. retrieval parity on the runs' own queries (reference written once from the Python retriever)
uv run --project backend python scripts/retrieval_parity.py <queries.json>
```

The step-6 exit gate: `make verify` then `make audit` on `HEAD` (results in § Commands run).

## Diff summary

141 files, about +27,100 / −2,200 lines on `task/057-queued-ingest` (13 build commits after
the design commits). About 9,000 of the added lines are the committed synthetic retrieval
corpus, the trimmed CDK synth and the code-only re-pin diff (see § Review handoff for the
review's diff-scoping exclusions).

- **Phase 0 (`2c5071fc`):** `scripts/stage_walls.py` and `scripts/step_timeouts.py` with
  offline tests; the dev and CI Postgres image `pgvector/pgvector:pg17`; the like-for-like
  baseline runs.
- **Phase 1 (`8bc43872`, widths `528250f7`, judge `d4b65aee`, attempts `f908e9f7`):** every
  route step carries `timeout_s`, the bedrock route's nine overrides from 2 × healthy p99,
  every model client at `max_retries=0` with the timeout per request, `tracing.traced_attempts`
  (three traced attempts, each its own generation); the quote verifier `qv_v2` with
  `core/markup.py`; the image compiles bytecode; screen stage 1 and classify 12 → 48,
  option search 4 → 10; the grounding judge at low effort with an 80 s timeout on bedrock.
- **Phase 2 (`a911aa4e`):** rev1 expand (document-store columns, `embedding` vector(1536),
  `tokens`, `queued` status, indexes built concurrently), rev2 keyset backfill with the
  product tokeniser (`core/tokens.py`), the deploy waiter (`scripts/deploy.sh`
  `wait_for_migration_task`, `MIGRATION_WAIT_MAX_S`).
- **Phase 3 (`2bd76a37`):** chunk retrieval as one SQL statement (two legs of 200 candidates,
  reciprocal-rank fusion, best unit per snapshot), `RetrievalScope`, the Python scope load,
  scoring and the 20,000-unit cap deleted, `scripts/retrieval_parity.py`, rev3 drops the
  JSON vector column.
- **Phase 4a (`049e9429`):** parse profile v2 (markup rule), `ingest_document` (one document,
  one outcome record), one stage path over a queue client (`LocalQueueClient` for
  in-process mode), the scheduler and batch hand-over deleted.
- **Phase 4b (`def239a4`):** `AdaptivePool` in the stage's own embedder thread, `SqsQueueClient`,
  the Lambda handler `ops/ingest_worker.handler` with its decision table, `not_ready` and
  `send_failed` outside the access-failure vocabulary, `awslambdaric` (Linux only).
- **Phase 5 (`69f044be`, `3d6029c7`, `dc7245d9`):** the CDK `IngestWorker` construct
  (queue, dead-letter queue, function, alarms, role grants), `ingest_mode` per environment,
  `scripts/prune_unlinked_snapshots.py` and the retention rule, the data-flow note, the
  DEPLOYMENT sections, spec items S1 to S5 with the log entry, the deferred entries, the
  `chmod 755 /app` line.

**Flagged deviations and adjudication items (each is recorded in full in its phase section):**

1. `qv_v2` changes the extraction fingerprint, so the next run on each already-extracted
   document re-extracts once (Phase 1; not named in the contract).
2. A quote that cuts through an emphasis pair fails under `qv_v2` (no `qv_v1` fallback);
   a quote copied with its markup now grades `normalised` (Phase 1).
3. The chat's outer `chat:call` observation is a span, with tokens on the inner generations
   (Phase 1, within D12's vocabulary; a saved Langfuse view may need its filter changed).
4. The tokens SQL follows the product rule, not plan P5's wording (Phase 2; parity is the
   point).
5. The pre-run of rev1 and rev2 before a deploy goes over the tunnel from a checkout of the
   release commit, not through the ECS migration task (Phase 2, plan P14).
6. Two documents sharing one snapshot were scored twice by the Python retriever; the SQL
   retriever scores the snapshot once (Phase 3, an intended fix).
7. **The contract's "under 100 ms a search on the dev corpus" is not met**: 250 to 600 ms
   warm on the fixed questions' scopes, 2 s cold on the largest; about twice the Python
   search; the per-run cost is 10 to 51 s against the scope load it replaces (Phase 3,
   round (e); HNSW stays out by D7). *Owner 2026-11-04: accepted, N8 reworded (review
   ruling 1).*
8. In-process mode fetches on the parse worker threads (4 to 8), not 10 fetch threads
   plus 4 parse processes (Phase 4a; round (f) measures it). *Owner 2026-11-04: 10
   threads in process (review ruling 6).*
9. Envelope (abstract) chunks are embedded by the acquire stage only, not again at ingest
   (Phase 4a).
10. `not_ready` and `send_failed` are still counted under `fetch_failed` by two status
    tallies (`steering_bundles._full_text_status_counts`, characterise's reason counts)
    (Phase 4b).
11. The function reads the **database** secret, not plan P13's "app secret" (which holds
    the model keys D6 forbids the function to hold) (Phase 5).
12. No alarm has an action (the stacks had no notification topic); the VPC has three
    fck-nat instances, not the one the stack comment and D5 describe (Phase 5).
13. `MODEL_CALL_ATTEMPTS` 2 → 3 after round (d) lost a run to two consecutive judge stalls
    (D12; `f908e9f7`). *Owner 2026-11-04: keep three (review ruling 2).*
14. `chmod 755 /app`, a second Dockerfile change beyond G8's one line, without which the
    function cannot start under Lambda's user (`dc7245d9`). *Owner 2026-11-04: accepted
    (review ruling 3).*
15. The retention script also spares snapshots that citations or extraction records point
    at, beyond D3's "no link row" wording (Phase 5).
16. The low-effort judge marked more claims unsupported than the medium one on the live
    runs (10.9% against 5.1%), the opposite of E3's lean; the owner's content read decides
    (round (c), rubric 31). *Owner 2026-11-04: accepted as built; revisit in the synthesis
    refinement task (review ruling 4).*
17. 1,353 `chunk_embedding` rows more than the three `embed.summary` lines account for in
    round (e)'s window: explained in round (g) as the acquire stage's abstract embeddings
    (equal counts in rounds (e), (f) and (g)); not a defect, kept for the record.
18. The option-search width test was generalised to the configured width + 2 when the
    width went 4 → 10 (gate 4).
19. A once-per-task step (`task_agent_turn`) cut on all three attempts surfaces as an HTTP
    500 from the task-creation API, not as a reason-coded failure (round (f), one launch).
20. `fulltext.summary`'s `already_in_store` counts snapshots that predate the stage; the
    per-document records also count same-run pairs of identical bytes (round (f): 0
    against 4; round (g): 37 against 38). Two counts, two meanings.
21. A `synthesise_section_turn` call was cut three times at its 23 s timeout and failed a
    synthesise attempt (round (g)); three identical cuts at the limit read as a long section
    beyond the Phase 0 sample's p99, not a stall. Rubric 22 allows one raise per too-tight
    step; not raised in this build (one call in seven rounds), left to the review with the
    obesity run's 47 `screen_abstract` cuts at 7 s across the 48-wide pool (all recovered
    on attempt 2). *Review:* the owner's rounding ruling moved the step to 25 s; the trace
    cannot say what the call needed (§ Review findings, trace lane); the 7 s cuts are
    connection setup at width 48, not the model (probe 3).
22. The pool-convergence test (`test_adaptive_pool_converges_under_a_quota_and_never_splits_for_throttling`)
    failed once at the exit gate (width climbed to 5 against an allowance of 3) and once in
    five runs alone: its fake backend measures "in flight" by wall clock with a 20 ms hold,
    so late thread starts let the width climb before any throttle. The hold is 0.2 s now
    (ten of ten alone, about 9 s a run instead of 3.5 s); the pool code is unchanged. A
    test-timing fix, not a weakening (rubric 5).
23. The markup rule's stray-marker pattern deleted significance stars after numbers
    (`0.50**`, `0.54***`) in statistics tables, an E6 limit nobody had listed; fixed with
    the owner's two markup rulings (§ Owner rulings after the exit), digest re-pinned.
    *Review:* two more content losses closed (`\*literal\*`, `a<b and c>d`; F13, F14);
    `<b disabled>` is the recorded remaining one.
24. *(Found at the review, contract verifier 11.)* The streamed chat prose call has no retry
    at all: it is exempt from the step timeouts (D12) and the SDK's two silent retries went
    with `max_retries=0`, so a connection error before the first token fails the turn where
    it used to be retried. Recorded as a deferred seam.
25. *(Found at the review, three lanes.)* The shared `source_snapshot` row's `source_locator`
    holds the first fetcher's final URL with its query string (plan P5's "the public document
    URL", owner item 4), while contract N9 says no URL breadcrumb on the shared row; the N9
    test checks columns and JSON keys but not that column. Owner ruling 5 in § Review
    findings. *Owner 2026-11-04: accepted, N9 reworded (review ruling 5).*

## Review findings

The review stack ran on 2026-11-03 in a fresh conversation (step 7), on `fb06cd72` with the
bulk data files excluded by pathspec (§ Review handoff). Five lanes: the contract verifier
(Opus, read-only), `/code-review medium` (the Claude half of the heterogeneous pair), one
security lane (`security-auditor`), the Codex adversarial pass (read-only, the first look
from another model family: every line of the build is Claude-family work), and the lead's
trace lane (Langfuse and the build's saved round artefacts) with stall probe 3 run by a
builder agent. The data files got their own check: a grep of the synthetic corpus, the two
script fixtures and the trimmed synth for URLs, keys, account ids and emails found none (the
12-digit matches are score decimals; the synth carries placeholders).

### What each lane caught

| lane | findings | adopted | owner ruling | declined or deferred |
|---|---|---|---|---|
| contract verifier | 13 | 9 (records, tests, markup, rollback plan) | 2 (rubric 22's zero-retry clause; S5 wording) | 2 |
| `/code-review medium` | 9 | 6 | 1 (deviation 8, the 2-vCPU thread count) | 2 (deferred seams) |
| security auditor | 4 low, 5 info | 5 | 2 (`source_locator`; the function's egress rules) | 2 |
| Codex adversarial | 14 | 8 | 4 (deviations 7, 13; `source_locator`; deviation 8) | 2 |
| trace lane (lead) | 3 | 1 (recorded) + probe 3 run | 1 (deviation 16 content read) | 1 (deferred seam) |

Convergent across families (high confidence): a dead run's late delivery could write into a
row a later run had re-queued (Codex 1, security 8); the prune-race recovery lived only in the
Lambda wrapper (Codex 7, code review 2); the fetched URL with its query string on the shared
snapshot row (Codex 3, security 7, contract verifier 2, three lanes). Unique to one lane and
worth that lane: the lost `lock_timeout` in the migration's autocommit block (Codex),
`\*literal\*` losing its stars (Codex), the socket denial being test-only (security), the
slow-drip body outliving the deadline (security), the lost contextvars on worker threads
(code review), rubric 22 marked Met with a failed clause (contract verifier), failed attempts
carrying no input in Langfuse (trace lane).

### Adopted: code changes in this phase (each marked `# task 057 review:` at the site)

| # | finding (lane) | change | test |
|---|---|---|---|
| F1 | A dead run's delivery writes into a re-queued row; the writes guard on `queued` only (Codex 1, security 8) | the stage stamps `ingested_by_run_id` when it queues a row (`ingest_full_text.py` `_run_stage`); `_read_queued_row`, `_write_ingested`, `_write_failed` and `_close_queued` require that run (`ingest_document.py`, `ingest_full_text.py`) | `test_a_dead_runs_delivery_cannot_write_into_the_run_that_queued_the_row_again` |
| F2 | A `BotoCoreError` on `send_message_batch` (a read timeout after SQS accepted the batch) closed rows `send_failed`; the accepted message then no-ops and the document is lost for the run (Codex 2) | the batch is reported neither sent nor failed (`ingest.queue_send_unknown`); the stage deadline closes the rows `not_ready` if no message arrives (`ingest_queue.py`) | `test_sqs_client_reports_partial_and_whole_call_failures_with_the_reason` (new case) |
| F3 | The prune-race recovery (FK failure on a store hit's link write) lived only in the Lambda wrapper; in process (production's mode) the component failed (Codex 7, code review 2) | moved into `ingest_document`: the store hit's bytes are kept, parsed afresh once and written again; the wrapper calls `ingest_document` directly | `test_a_store_hit_pruned_under_the_link_write_is_parsed_afresh`, `test_an_unrelated_integrity_error_on_the_link_write_still_raises` |
| F4 | The handler had no final exception path: an unexpected error on delivery 2 dead-lettered with the row still `queued` (contract N2), and an escaped SQLAlchemy error's text (SQL, parameters, URL) reached CloudWatch (Codex 8, security 3) | on the last delivery the handler writes `fetch_failed` / `worker_error` (new closed-vocabulary reason, in `NOT_READ_YET_REASONS`), logs the error type only and raises a `RuntimeError` naming the type; `_redact_urls_in` recurses into dicts (`ops/ingest_worker.py`) | `test_an_unexpected_error_is_retried_then_written_as_worker_error`, `test_an_unrelated_integrity_error_is_not_swallowed`, nested-dict redaction case |
| F5 | Deviation 10: `not_ready` / `send_failed` counted as `fetch_failed` by the steering tally (Codex 9) | `NOT_READ_YET_REASONS` defined once in `ingest_full_text.py`, re-exported by the read models; the steering tally counts them as `not_read_yet`; characterise's reason histogram unchanged (reasons are honest there) | `test_full_text_tally_counts_not_read_yet_rows_apart_from_access_failures` |
| F6 | The parse worker's socket denial was a test fixture, not runtime code (security 1) | `_worker_entry` installs `_refuse_socket` before parsing; the module guard now forbids constructing a socket rather than naming the module | `test_the_parse_worker_refuses_sockets_on_its_own`, `test_ingest_module_has_no_http_client` (tightened) |
| F7 | The per-document deadline was not checked while a body streamed (security 2) | `_read_capped_body` returns `timeout` once past `FETCH_DEADLINE` (`fetch_live.py`) | `test_a_slow_drip_body_stops_at_the_deadline` |
| F8 | The sender thread and the local queue's workers dropped the caller's contextvars (code review 3) | `contextvars.copy_context().run` on both | `test_orphaned_queued_rows_are_queued_again_at_start` (asserts the worker's log line carries `run_id`) |
| F9 | A boto3 SQS client per request (code review 6) | `functools.cache` on `sqs_client()` | `test_the_sqs_client_is_built_once_per_process` |
| F10 | The pool granted clean credits in a completion round that also throttled (Codex 10) | no clean credit in a round with a throttle (`embeddings.py`) | `test_adaptive_pool_round_with_a_throttle_grants_no_clean_credit` (fails without the fix) |
| F11 | A batch given up for throttling counted as `failed` while the comment said "stays pending" (code review 5) | `deferred` count and `embed.batch_deferred` event; `failed` is real failures; the stage summary carries `deferred` | `test_adaptive_pool_gives_a_batch_up_after_its_throttle_budget` |
| F12 | `SET LOCAL lock_timeout` ended with part 1's commit, so the autocommit block ran unbounded (Codex 13) | session `SET lock_timeout` inside the block, `RESET` at its end (rev1) | `test_migration_057_document_store.py` (round trip) |
| F13 | `\*literal\*` → `\literal\`: content deletion the test blessed (Codex 12) | an escaped marker neither opens nor closes emphasis (`_EMPH_RE`, `_STRAY_EMPH_RE`); result `*literal*`; digest unchanged (the fixtures carry no escaped markers) | `test_strip_markup_examples` (the "quirk" line now requires the stars) |
| F14 | `a<b and c>d` → `ad`: one-letter tag names took free text as attributes, contradicting the owner-ruling note that the content-deleting cases were closed (contract verifier 5) | a one-letter name is a tag only before `>` or with an `=` attribute; `<b disabled>` is the recorded remaining loss | `test_one_letter_tag_names_need_a_tag_shape` |
| F15 | `_retryable` knew only `openai` errors while the `bedrock-claude` backend (route not in use) runs botocore at one attempt (code review 1) | botocore throttle / not-ready codes and timeouts count as retryable (`tracing.py`) | eight new cases in `test_traced_attempts.py` |
| F16 | A shared snapshot was searched under the lexicographically first document, so the boosts and citation identity were arbitrary (Codex 4) | chosen by priors: selected, then appraised, then the smaller id (`synthesis_tools.py`) | `test_shared_snapshot_is_searched_under_the_selected_document` (fails on the old sort) |
| F17 | `_vector_literal` duplicated `Vector.bind_processor`'s formatting (code review 7) | one `schema.vector_literal` for both | parity suite unchanged (17 passed) |
| F18 | Docstrings said one retry / attempts 1 or 2 (code review 9, contract verifier 9) | `tracing`, `openai_client`, the route-file comment and the call-site table say up to `MODEL_CALL_ATTEMPTS` (three today) | none (text) |
| F19 | `--round-to` had no test and the script's docstring still said `max(5, …)` with n ≥ 100 (contract verifier 5) | docstring describes the three flags; `test_round_to_rounds_up_before_the_floor` | that test |
| F20 | No test pinned the two Dockerfile lines (contract verifier 12) | `tests/ops/test_dockerfile_lines.py` | two tests |
| F21 | The visibility walk's bearer tokens lived 60 s; the HEAD gate (29 min under a load average of 110 to 195) pushed the walk past a minute and it failed with a 401 at step 67 (the gate's one failure; alone it runs in 10 s) | `tests/api/org_support.py` mints 600 s tokens | the walk test |
| F22 | The screen and classify steps sent `max_completion_tokens` of 8,192 and 16,384 against answers of a few hundred tokens. Bedrock admits a request only if `input + max_tokens` fits the tokens-per-minute quota, so one 48-wide classify burst reserved about 786,000 output tokens (a fifth to a quarter of Luna's 4,000,000) for room it never used; the first thing to throttle when production joins staging (the Bedrock brief, recommendation 6; owner's go 2026-11-03) | `SCREEN_MAX_OUTPUT_TOKENS` 8,192 → 2,048 and `CLASSIFY_MAX_OUTPUT_TOKENS` 16,384 → 8,192, sized from Langfuse's recorded output counts since 2026-10-28 (reasoning tokens included: screen:abstract n 3,894, p99 454, max 713; screen:full n 3,869, p99 656, max 1,608; classify:document n 3,850, p99 1,915, max 3,610, some at the old high effort); the 056 call-site fixture refreshed with `CALL_SITE_KWARGS_UPDATE=1` (three entries changed, nothing else); the two prompt files' hashes re-pinned, code-only (no prompt text changed; the diff is commit `bd574c66`) | `test_call_site_kwargs.py` (63 pass), `tests/evidence_search/assess` (253 pass) |

Fake-done check on the fixes: no test was deleted or loosened. One test was removed and
replaced by two stronger ones (the handler-level pruned-snapshot test became a shared-path
test plus an "unrelated integrity error still raises" test); the markup "quirk" assertion was
tightened; the token lifetime change affects no assertion.

### Adopted: records only

- Data-flow note: URLs in logs are scheme, host and path (not "host only"); the shared row's
  `source_locator` is the first fetcher's final URL with its query string (contract verifier 3,
  security 7).
- `infra/DEPLOYMENT.md` § 8: the task 057 rollback entry (both halves; read back against the
  three downgrade functions) and the handler's "writes before giving up" caveats (contract
  verifier 6, 7).
- ADR 0043 decision 3 said the SQL applied every boost and the clamp; the statement returns the
  fused candidates and Python applies the priors, rerank and cut. Decision 4 now carries the
  owner's post-build thresholds (n ≥ 30, floor 15 s, multiples of 5 s) and names the open
  attempts ruling (contract verifier 4).
- `docs/deferred.md`: the stale "second traced retry" entry rewritten as built; six new seams
  (failed attempts carry no input; the chat stream has no retry; three Retry-After parsers; the
  pool fake's timing; the staging inspection secret named by the ADR; the function's egress
  rules); the markup collateral line names `<b disabled>` instead of the closed `<b and c>`
  (contract verifier 4, 5, 9; trace lane; code review 7; Codex 11; security 4).
- Rubric status rows corrected below: 22 (the zero-components-retried clause did not hold in
  rounds (a), (b), (d), (e) and (g)), 21 (the test does not check `source_locator`), 25 and
  21's citations, 3's gate map, 5's six unlisted removed tests (contract verifier 1, 2, 8, 10,
  13).

### Owner rulings (the stack escalated; the owner ruled on 2026-11-04; rulings 6 and 7 changed code)

1. **Deviation 7 / Codex 14 / contract verifier 1:** N8's "under 100 ms a search on the dev
   corpus" is not met (250 to 600 ms warm on the fixed questions' scopes). Codex reads it as a
   contract change needing approval, not a minor deviation; the per-run cost is 10 to 51 s
   against the scope load it replaces. Options: accept the measured figure and reword N8;
   keep the Python retriever until an indexed plan meets 100 ms (D7's HNSW).
   *Ruled 2026-11-04:* accepted and reworded; contract N8's evidence cell now reads "under 1 s warm on the
   fixed questions' scopes" with the measured figure and the reason.
2. **Deviation 13 / Codex 6:** three attempts per call against the contract's one traced
   retry. Codex argues for two attempts plus a raise on the too-tight steps. The build's
   evidence: a stall-then-stall on one step (4 to 6% per judge call at low effort) lost a
   synthesise attempt in most rounds under one retry, 250 to 400 s each time; the third
   attempt costs at most one more timeout. The lead recommends keeping three.
   *Ruled 2026-11-04:* keep three on every step; the deferred seam is closed and ADR 0043 says so. The
   Bedrock brief's finding (AWS's example budget is six attempts) supports it.
3. **Deviation 14:** the `chmod 755 /app` Dockerfile line (unapproved second line; now pinned
   by a test).
   *Ruled 2026-11-04:* accepted under G8.
4. **Deviation 16 / rubric 31:** the trace lane's content read of the low-effort judge's
   first-pass verdicts (NEET, round (c): 9 of 104 unsupported): four of the five read flag the
   writer's own hedge ("does not establish a causal effect", "remains unclear") as an
   unsupported claim, not a mis-citation; the repair pass then removes the caution. The
   extra verdicts at low effort make reports less hedged, not more wrong. The owner's reads
   of `7796f163`, `c5961a67` and `c3be6e81` decide.
   *Ruled 2026-11-04:* accepted as built without the content read; the revisit goes to the synthesis
   refinement task (the D14 seam in `docs/deferred.md` already names it).
5. **`source_locator` on the shared row (Codex 3, security 7, contract verifier 2):** plan
   P5 and owner item 4 accepted "the public document URL" on the shared row; contract N9's
   wording says no URL breadcrumb; the column holds the first task's final URL with its query
   string, which a signed link would carry, and every later task that reuses the bytes reads
   it (the API joins the envelope snapshot for the user-facing URL, so it is not shown).
   Options: strip the query string and fragment on the shared row only (one line; the task's
   own `fetched_from` keeps the full URL; a `?sequence=1`-style path would lose its query);
   accept as-is and reword N9. The test's docstring claim ("no URL key in any column") is
   corrected either way.
   *Ruled 2026-11-04:* option B. The shared row keeps the full public URL; contract N9 now
   reads "the public document URL but no task, user or run breadcrumb". The owner's reasons:
   the query string is the publisher's, never a Policy Atlas identifier; the signed-link case
   is thin (none seen) and the harm would be an expired token for a public file; a document
   store should know where its document is. The user-facing title and URL come from the
   task's own envelope row in all three readers (checked). No code change.
6. **Deviation 8 / code review 4:** in-process threads are `max(4, min(8, cores))`, so 4 on
   the 2-vCPU production task that stays `in_process`; before 057, 10 fetch threads fed 4
   parse processes. Round (f) measured 8 threads on the laptop. Recommend 10 threads in
   process (the parse processes stay bounded by the walk pool); a measured-config change.
   *Ruled 2026-11-04:* 10 threads. `ingest_queue.IN_PROCESS_INGEST_THREADS = 10` is the in-process client's
   default; `DEFAULT_MAX_WORKERS` (4 on 2 vCPUs) still bounds the parse step through
   `INGEST_SLOTS`. Not re-measured on the laptop (round (f) ran 8 threads there).
7. **Security 4:** the function's security group allows all outbound; recommend 80 and 443
   to the internet plus 5432 to the database group (publishers on other ports would be
   refused). Infra gate.
   *Ruled 2026-11-04:* applied. `allow_all_outbound=False` with three egress rules (80 and 443 to
   any IPv4, 5432 to the database group; DNS to the VPC resolver is not filtered by
   security groups); `test_ingest_function_runs_in_the_private_subnets_with_its_own_security_group`
   pins them; `make -C infra test` 113. The committed Phase 5 synth
   (`cdk-synth-ingest.json`, `69f044be`, since removed) predates this and showed "allow all"; the staging
   `cdk diff` after the merge is where the new rules are seen live.
8. **Spec S5 wording** (`docs/specs/system/prompting.md`, contract verifier 4): "retried
   once", "at least 100 traced calls, floor 5 s" no longer match the code (three attempts;
   n ≥ 30, floor 15 s, multiples of 5 s). Proposed replacement: "each attempt is its own trace
   generation (SDK retries off) and a stalled call is retried, up to three attempts, never
   waited out; timeouts are 2 × the healthy p99 from at least 30 traced calls, floor 15 s,
   rounded up to 5 s". Not edited by the stack.
   *Ruled 2026-11-04:* the proposed wording applied to `docs/specs/system/prompting.md` (with the
   "a step with fewer calls keeps its previous value" clause kept, as it is still true).
9. **Stall probes 1 and 2** (the probe brief, `c89aba82`): probe 1 needs Bedrock invocation logging on
   the account; probe 2 is four full runs (about $10 at the 056 basis of $1 to $3 a run; the
   review first wrote $60 from a stale pre-056 figure, corrected by the owner). Probe 3 ran
   (below). Round (h)'s one
   component failure (a judge call: a dropped connection, then two 80 s hangs on the same
   call) is the shape probe 2 tests. *Closed 2026-11-03:* the owner ordered probe 2 (the
   client is cleared) and probe 4 (the bare SDK hangs at our rate); see § Stall probes 2
   and 4 and the brief's items 3 and 4 for what replaces probe 1.
10. **Rubric 13's wording** ("Bedrock is reached through the function's role") predates D6;
    the function has no Bedrock grant, by design. Noted, not edited.
    *Ruled 2026-11-04:* rubric 13 reworded to "the function has no model client and no
    Bedrock grant (D6)".

### Declined (with the reason)

- Codex 5 (the call budget reserves once per logical call while three provider requests may
  run inside): parity with the pre-057 SDK, whose `max_retries=2` made the same three requests
  per slot; the budget counts logical calls by design.
- Codex 11 (the pool test fake "fixed by slowing"): the hold-time change loosened no
  assertion; a virtual-clock fake is a deferred seam.
- Security 5 (match the FK by constraint name): no other FK on the write today; a comment
  would be the only change.
- Security 6 (provider error text in Langfuse `status_message`): no new data class (prompts
  are already on the success input) and the message is the diagnostic.
- Security 9 (digest-pin the dev Postgres image): dev only.
- Code review 8 (the runner's inline-queue default branch): works; a refactor beyond the
  slice.
- Code review 7 (three Retry-After parsers): providers send seconds; deferred seam.
- A separate `/simplify` pass: `/code-review medium` already ran the reuse, simplification and
  efficiency angles (findings 5 to 9) and their fixes were applied (F9, F11, F17); a second
  same-family pass would duplicate it.

### Trace lane (lead)

- **Deviation 21 (the obesity `synthesise_section_turn` cut three times at 23 s, round (g)):**
  Langfuse session `1c1f7d04`, trace `5095919e`: logical call `92f71d5b85ec`, attempts 1 to 3
  `ERROR` at 23.2 / 23.2 / 23.1 s, the second turn of the first section (the turn before it
  took 1.9 s). The successful retry's 20 section turns: tool-request turns 1.8 to 2.5 s (136 to
  218 output tokens), writing turns 7.6 to 10.9 s (1,232 to 2,057 output tokens). **A failed
  attempt's generation carries no input, model or parameters** (`traced_attempts` stamps the
  step, attempt, call id and error; the caller's `update` sets the input on success only), so
  the build's reading ("a long section, not a stall") can be neither confirmed nor refuted
  from the trace. Three consecutive hangs on one call at a 1 to 3% hang rate is about 1 in
  100,000, so "the input needed more than 23 s" is the likelier reading; whether that is long
  output or long reasoning is unknowable. Recorded as a deferred seam (a `before` hook on
  `traced_attempts`, 24 call sites). The owner's rounding has since moved the step to 25 s.
- **Deviation 19 (HTTP 500 on a task-agent turn, round (f)):** the server log shows two
  `model_call.retry` lines at 60 s then `api.unhandled_exception` from
  `create_task_agent_turn`; confirmed as described (no handler for a provider timeout after
  the last attempt). Carried as the known user-facing gap it is (a reason-coded failure would
  need a response shape for that route; out of this slice).
- **Deviation 16:** see owner ruling 4.
- **Round (g) retry outcomes, read back from the build's artefact:** 78 retries; 73 reached
  attempt 2 and all but five succeeded there; four of the five succeeded on attempt 3; the
  fifth is deviation 21. 47 of the 48 `screen_abstract` cuts were the obesity run at 7.0 to
  7.1 s with attempt 2 at 0.5 to 3.3 s: a burst, not stalls (probe 3 below).

### Stall probe 3 (burst shape at width 48; run by a builder agent, 183 calls, read back from `probe3-summary.md`)

Route `bedrock`, the shipped client, the real `screen_abstract` prompt over 22 real abstracts
× 10 intents, timeout 300 s, no retry, no Langfuse; three bursts at width 48 then three at
width 12, 60 s apart; the laptop's load average was 110 to 195 throughout (the gate ran
beside it).

| measure | width 48 | width 12 |
|---|---|---|
| requests, all succeeded | 144 | 36 |
| p50 / p90 / p99 / max s | 4.75 / 6.18 / 7.32 / 7.66 | 1.58 / 2.61 / 3.10 / 3.20 |
| server wait (request sent to headers) p50 / p99 s | 0.91 / 3.61 | 1.06 / 2.83 |
| TCP + TLS setup p50 / max s | 3.05 / 4.07 | 0.23 / 0.26 |
| requests over 7 s / over 15 s | 4 / 0 | 0 / 0 |

Reading: the width-48 p99 (7.32 s) sits under the brief's 7.5 s line, so the owner's 15 s
floor holds, and the slowdown at width 48 is on the client (48 TLS handshakes at once in one
process on a loaded laptop, 3 s each) rather than queueing at the endpoint (the server wait
is the same at both widths). Every request opened a new connection (60 s between bursts is
past the 5 s keep-alive expiry), so the stale-connection question (probe 2) is untested.
Caveat: the load average means the client-side figures are an upper bound. The build's
screen_abstract cuts at 7 s across the 48-wide pool are consistent with this: connection
setup, not the model.

### Stall probe 2 (connection re-use; ordered by the owner after the stack; run by a builder, 4 runs, $2.95)

Two arms on the reviewed commit, NEET and zonal each: arm A with keep-alive off (the live
worktree's client built on an httpx client with `max_keepalive_connections=0`, reverted
after), arm B as shipped; back to back, 19:36 to 20:01 UTC; no other runs on the database;
figures read back from `probe2/probe2.md` and `table-AB.md` (session scratchpad).

| | arm A (no keep-alive) | arm B (shipped pool) |
|---|---|---|
| attempts / failed | 1,536 / 6 (0.39%) | 1,569 / 4 (0.25%) |
| non-fan-out steps, failed | 5 of 149 (3.4%) | 4 of 160 (2.5%) |
| cuts / connection errors | 6 / 0 | 3 / 1 (after 61.4 s) |
| calls that reached attempt 3 | 0 | 1 (judge, succeeded) |
| component failures | 0 | 0 |

**Reading: the client is cleared.** With every request on a fresh connection the hang rate
did not fall, and arm A's cuts have the same shape (a call sits to its timeout, the retry
answers). Both arms ran far quieter than round (h) (0.81% overall, 7.4% on the long steps),
so the rate moves with the hour at the provider. Connection-error counts (0 against 1) are
too small to read. Owner ruling 9 is closed for probe 2; probe 1 is replaced by the brief's
items 3 and 4 (the support case and the free metrics).

### Stall probe 4 (the bare SDK outside the pipeline; ordered after the owner questioned the implementation; builder, 90 calls)

Ten real judge inputs from round (h)'s obesity session, three arms, three repeats,
interleaved, all serial (one request in flight), timeout 300 s: arm 1 the plain OpenAI SDK
with its defaults (`max_retries=2`, no schema, no cache fields, plain text); arm 2 our exact
request body on the default client; arm 3 our client and `parse_structured`. Read back from
`probe4/probe4-summary.md`.

| arm | first attempts hung (> 80 s) | median s | max s |
|---|---|---|---|
| 1, bare SDK | 3 of 30 (10%) | 7.9 | 310 |
| 2, our request shape | 5 of 30 (17%) | 7.0 | 311 |
| 3, our helpers | 5 of 30 (17%) | 6.6 | 302 |
| all | 13 of 90 (14%) | | |

The arms are not distinguishable (Fisher p = 0.53); the hangs cluster in time, not by arm.
**Reading: the provider or the path does it regardless of our code.** Four of the 13 hung
attempts returned on their own after 126 to 246 s (the rest hit the 300 s cut), so some
hangs are very slow answers, not lost requests. Request ids were captured for 86 of 90 calls
(the four cut by our own client have none). Limits: 30 calls per arm cannot tell 10% from
17%, and 90 cannot see a 1% rate.

The research the owner ordered (four sourced notes) and the recommendations against what
we built are in [bedrock-integration-brief.md](bedrock-integration-brief.md) (tracked; its
four notes are local under `research/`, which `.gitignore` keeps out of version control for
every task, so the brief lists the AWS pages they rest on).

### Gate after the fixes and the closing measurement

See § Commands run (the review-fix gate rows) and § Measurement round (h) (the reviewed
commit on the fixed questions: walls at round (g)'s level, one synthesise re-run from a judge
call that failed all three attempts, 72 cuts of which 67 recovered).

## Rubric status

Read against [rubric.md](rubric.md). "Met" means the evidence is in this record; "open"
names what is still outside the build's reach.

| # | Item | Status |
|---|---|---|
| 1 | N1 to N15 | Met for N1 to N14 as recorded per phase; N15 met as built (judge at low); the owner accepted it on 2026-11-04 without the content read, revisit in the synthesis refinement task (item 31). |
| 2 | `make verify` at the four gates, infra tests | Met: § Commands run (build-open, after Phase 2, after Phase 3, exit); `make -C infra test` 113. |
| 3 | No approval-gated change beyond G1 to G10 | Met with one exception flagged: the second Dockerfile line (`chmod 755 /app`, deviation 14), accepted by the owner on 2026-11-04 (review ruling 3); code-only re-pins recorded in commits `8bc43872` (Phase 1) and `bd574c66` (F22's two output caps); no prompt-text re-pin, no public-interface change. *Review (contract verifier 13):* two further changes sit under G10 by extension, not by name: `deploy.sh`'s test-harness mode (`PA_DEPLOY_MIGRATION_WAIT_ONLY`) and the root Makefile prerequisite that runs the waiter's shell test in CI; they are the waiter's own test seam. |
| 4 | No generated files or secrets edited by hand | Met (`uv.lock` and the frontend bundle regenerated by their tools; `.env` never read). |
| 5 | No tests deleted, skipped or weakened without justification | Met: the scheduler tests N6 deletes are listed in Phase 4a with the replacing behaviour; one test generalised (deviation 18); one test's fake timing widened (deviation 22). *Review (contract verifier 8), six removals not listed at the build:* the four embedding throttle-retry tests (`test_openai_embedding_backend_rate_limit_backoff_then_success`, `…_rate_limit_exhaustion_fails_loudly`, `test_cohere_embedding_backend_retries_throttling_then_succeeds`, `…_stops_after_repeated_throttling`) tested the per-backend backoff loops that D6 moved into the pool; their replacements are `test_openai_embedding_backend_raises_throttled_at_once_on_429`, `test_embed_with_retry_waits_out_throttling_then_succeeds`, `test_embed_with_retry_gives_up_after_the_last_attempt`, `test_cohere_embedding_backend_raises_throttled_after_one_call` and the four pool tests. `test_retrieval_unit_cap_error_names_cap` and `test_a_retrieval_cap_is_answered_honestly` tested the 20,000-unit cap N8 deletes. The `envelope_source_snapshot_id` assertion in `test_governance_chain` checked a metadata key N9 moved off the shared row (it is now the link row's column, asserted by `test_already_in_store_on_a_second_task_with_the_same_bytes`). At the review: one handler test replaced by two shared-path tests (F3, F4); no test loosened. |
| 6 | Evidence as the contract's § Verification evidence lists | Met for the laptop; staging tables, the staging migration timing and the embedding quota in force are post-merge (items 15, 28); `cdk diff` reviewed read-only (item 26). |
| 7 | Deferred seams in `docs/deferred.md` | Met: the task 057 section carries every named seam (§ Deferred work). |
| 8 | Tier 4 review stack, ADR Accepted, rollback written and downgrade tested | Open for step 7 (review stack); ADR 0043 Accepted 2026-11-03; the downgrade through all three revisions is tested on the test database; the rollback is in `infra/DEPLOYMENT.md`. |
| 9 | N1 message shape | Met (Phase 4b tests pin the keys and that no value is a URL or user id). |
| 10 | N2 handler statuses, store lookup first, Retry-After, guarded final write, races | Met (Phase 4a and 4b tests: fixture corpus parity, store hit before parse, Retry-After cases, redelivery and late write no-ops, the two real-connection races). |
| 11 | N3 own transaction, visibility to the poll, orphans, counts invariant, `not_ready`, `fetched` null | Met (Phase 4a and 4b tests; `not_ready` outside the access-failure counts in the read models, with deviation 10 on two tallies). |
| 12 | N4, N5 sizing, queue settings, alarm, drain command, connection arithmetic, quotas | Met: CDK pins (Phase 5); drain command in `infra/DEPLOYMENT.md`; connection budget in Phase 2 (scale words; figures in the gitignored notes); the Lambda quota likewise. |
| 13 | D5 function shape, subprocess kill, no sockets, private subnets, secrets at runtime, Bedrock via role | Met: parse in a subprocess with the 120 s kill; the socket deny was a test fixture at the build (contract revision 4 says "as the tests require") and is runtime code since the review (F6, `test_the_parse_worker_refuses_sockets_on_its_own`); private subnets, no S3, no new endpoints; the secret fetched at cold start; the function has no model client and no Bedrock statement (D6 forbids vectors in the function; rubric 13's "Bedrock via role" wording predated D6 and was corrected on 2026-11-04, review ruling 10). |
| 14 | D6 no vectors in the function, adaptive pool converges, no `embed_timeout` | Met (Phase 4b; `embed_timeout` has no occurrence). |
| 15 | D6, G4 staging embedding evidence | **Open until after the merge** (staging deploys from dev); the PR names it as the one open item. |
| 16 | N6 one path, per-document commits, digest across 1 and 4 workers, connection count | Met (Phase 4a tests). |
| 17 | N7 markup chunks 186 → 0, no markup-caused quote failure, new names, old snapshots untouched | Met: the chunk count on the committed control fixtures, the names, and on the fixed questions 0 of 3 quote failures with markup as the cause (round (g)); old snapshots untouched (rev2 backfills vectors and tokens only). |
| 18 | N14 `qv_v2` | Met (Phase 1). |
| 19 | D2, G9, G10 image, migration round trip, resume, rev3 gate, waiter, float32 note | Met on dev and the test database (Phase 2; dev timings recorded); staging and prod row counts and the staging migration timing are post-merge. |
| 20 | N8, D7 parity, frozen snapshot list, both callers, deletions, provenance factors, write time | Met (Phase 3; rounds (d) and (e) give the embedding write time before and after) with deviation 7 on the latency figure. |
| 21 | N9, D3 one snapshot for the same bytes, no identifiers on the shared row, `already_in_store` | Met for task, user and run keys (`test_already_in_store_on_a_second_task_with_the_same_bytes` checks every column and JSON key of the shared row; the earlier citations of `test_no_url_persisted` and `test_source_snapshot_has_no_task_id_column` were wrong: the first tests a document with no URL, the second predates the task). **Partial for the URL:** the shared row's `source_locator` holds the first fetcher's URL (deviation 25, owner ruling 5). `already_in_store` in the stored counts, hidden from the SSE summary. |
| 22 | N10c, D12 timeouts on every step, 2 × p99 with counts, `max_retries = 0`, stalls caught, synthesise wall | Met for the seam, the derivation, `max_retries = 0`, the per-step stall counts and the walls (Phase 0 table, Phase 1, rounds (a) to (g)). **Not met: "zero components retried because every attempt was cut"** failed in rounds (a), (b), (d), (e) and (g) (one component per round at most, each a stall-then-stall or the deviation 21 call); the owner-ruled timeouts (floor 15 s, multiples of 5 s) were not measured live at the build and are measured at the review (round (h), § Measurement round (h)). Deviation 13 (three attempts) is owner ruling 2; the owner's read of the reports is open. |
| 23 | N10a no scoping call over 300 s | Met (round (a)). |
| 24 | N10b option-search width 4 → 10 | Met (round (b): the fan-out window 357 → 326 s; no Bedrock 429 in the round's log). |
| 25 | N10d, D15 widths 12 → 48 | Met (round (b); the `openai-direct` note is in § Intent & assumptions). |
| 26 | N11 CDK resources, `cdk diff` at the owner's checkpoint, staging deploy | Met in CDK with pins; the staging `cdk diff` was run read-only and its synth committed; the owner's checkpoint read and the staging deploy are post-build (**open**); prod stays `in_process`. |
| 27 | N13, G8 compiled bytecode, cold import before and after | Met (Phase 1: 8.24 → 3.79 s). |
| 28 | N12, D9 before and after tables per lever, ingest split, owner's content reads | Met for the laptop (rounds (a) to (g), the across-rounds table in round (g)); the staging tables are post-merge; the owner's two content reads are **open** (artefact ids named in round (g)). |
| 29 | G7, N12 data-flow note, retention rule, DPIA addendum as the merge gate | Met for the note and the rule; the DPIA addendum is named in the PR body (step 9). |
| 30 | S1 to S5 applied with a log line | Met (Phase 5). |
| 31 | N15, D14 judge at low, walls, unsupported counts, owner's read, deferred revisit | Met for the override, walls and counts (round (c)); the owner accepted it on 2026-11-04 without the read (review ruling 4); the revisit is the synthesis refinement task's (`docs/deferred.md`, D14). |

## Intent & assumptions

- Measurements are on the bedrock route only (D9). Production ran `openai-direct` through the
  build and review and moved to `bedrock` on 2026-11-03 (dev `f0018c4e`, merged into this branch
  on 2026-11-04), so the measured route is now the production route; production stays
  `in_process`, the mode the laptop rounds measured.
- The laptop's Docker Postgres (128 MB shared buffers) stands in for the writer; the
  per-search latency there is an upper bound for a warm production cache and nothing more.
- One run per question per round: the medians are over three runs, and model stalls
  (the heaviest in round (e)) move the walls more than any single lever.
- The exact account figures (connection limits, quotas, instance sizes) stay in the
  gitignored notes; this record uses scale words.

## Known unverified items

- Whether the forkserver parse subprocess runs inside Lambda (no `/dev/shm`); the emulator
  run on the laptop is the only evidence.
- The first staging start of the function: the bare `python` command and the `awslambdaric`
  import through the image's `PATH`.
- The prod `cdk diff` (needs the `pa-prod` profile).
- The staging migration timing, the backfill's pre-run over the tunnel, and the staging
  embedding quota in force (items 15, 19, 28).
- The deploy waiter against a real ECS task (shell test with a fake `aws` only).
- The owner's content reads (reports unchanged under the timeouts; one report after N7 and
  one after N8; the judge verdicts).
- *(Review.)* The owner-ruled timeouts (floor 15 s, multiples of 5 s) and the review's fixes
  on a live run: measurement round (h) below. Stall probes 1 and 2 (owner ruling 9). The
  stale-connection question behind the 1 to 3% hangs (probe 2) is untested; probe 3 cleared
  the burst cuts.

## Public safety

Run ids, counts and timings only. No URLs, no report text, no keys. The Langfuse observation
cache used for the timeout table holds timing fields only and stays in the scratchpad. The
committed synth is trimmed with placeholders for the account, VPC and subnet ids. The exact
ops account figures are in the gitignored notes, not in this record.

## Review handoff (step-7/8 inputs)

- **Adjudication items:** the 23 numbered deviations in § Diff summary; items 7, 13, 14 and
  16 need an owner ruling (21 and the timeouts were ruled on 2026-11-03), the rest a
  reviewer's read.
- **Executor provenance (family flip):** the lead wrote the seams, the route-file tables and
  every owner-facing text; deep-reasoner agents built the judgment-bearing phases (schema and
  backfill, the SQL retriever, the per-document function and stage, the pool, the handler,
  the CDK construct); fast-worker agents did the mechanical sweeps (call sites, test
  scaffolds, re-pins); builder agents ran every measurement round and probe. No Codex doer
  in this phase, so the step-7 Codex lane is the first look from another model family.
- **Diff-scoping exclusions for the review:**
  `backend/tests/evidence_search/synthesis/data/retrieval_synthetic/` (generated corpus),
  the synth and re-pin evidence files (since removed from the folder; see § Commands run),
  `backend/uv.lock`, `infra/uv.lock`.
- **Live-trace pointers:** run ids per round in the sections above; Langfuse session id =
  task id; server logs per round in the session scratchpad (not committed).
- **Stall probes:** the probe brief (`c89aba82`, since removed), three Bedrock-only probes for
  the review conversation to run or schedule (the owner dropped the `openai-direct` comparison).
- **Knowledge candidates** (one per durable-seeming lesson, however raw; *adjudicated at
  step 8 on 2026-11-03: every one of the 22 is in one of seven new concepts or the extended
  timeout concept, `docs/knowledge/log.md` § 2026-11-03 says which*):
  - zsh does not word-split an unquoted `$variable` holding several arguments; use `${=var}`.
  - The dev server caps concurrent walks at two (`RUN_EXECUTOR_MAX`); a third fixed-question
    run returns HTTP 409 and must start when a slot frees.
  - Serve the commit under measurement from a second worktree (detached, cherry-picks for
    lever isolation) so agents can edit the main tree during a live round; `git
    cherry-pick` of a commit already in the history aborts the sequence ("nothing to
    commit"): `--quit` then re-pick the rest.
  - A `MATERIALIZED` CTE for the scope's chunk list makes the planner scan the whole
    `chunk_embedding` table (60 s a query on 7.5 GB); `NOT MATERIALIZED` keeps the probe by
    chunk id. Written as a comment on the statement.
  - Docker Postgres with 128 MB of shared buffers re-reads about 50 MB of vectors from disk
    per large-scope search; "under 100 ms" measured on 600 to 900-unit scopes does not
    carry to 9,000-unit scopes. Size the latency claim to the scope.
  - AWS Lambda runs a container image as its own user, not the image's `USER`; a home
    directory made by `useradd --create-home` is mode 700 and the function never starts.
    The Runtime Interface Emulator as uid 1000 reproduces it on the laptop.
  - The handler must not import the operator CLI: `mypy_boto3_cognito_idp` is absent from
    the image and the import fails only in Lambda. A subprocess test that hides the package
    catches it.
  - `uv sync --no-group ops` must be on both sync lines of the Dockerfile; the second line
    re-resolves and would reinstate the group.
  - pgvector sums in float32: the SQL order can differ from the Python float64 order on
    near-ties below 1e-6; fuse on ranks, not scores, and parity holds.
  - The tokens rule "match `[0-9A-Za-z]+` then lower" and "lower then match `[0-9a-z]+`"
    differ on the Kelvin sign and the dotted capital I; match first for parity.
  - A step's timeout at 2 × healthy p99 catches a stall, but a stall-then-stall on one step
    is common enough (4 to 6% per judge call at low effort) that one retry loses a
    synthesise attempt in most rounds; three attempts at the step's timeout are cheap.
  - The grounding judge at low effort marked more claims unsupported than at medium on live
    runs, the opposite of the offline experiment; judge-effort decisions need the content
    read, not the counts.
  - The embedding-loop overhead timer absorbs the other concurrent run's contention in the
    same process; two runs per round make it a noisy write timer.
  - An agent's test database must be addressed as `127.0.0.1` (`localhost` resolves to
    `::1` first and is refused) and the base `*_test` database must exist with the vector
    extension before a worker-scoped copy can be made.
  - Running the rev2 backfill on the dev database under concurrent test suites and Docker
    I/O took about 49 minutes for 272,000 rows (20 minutes alone); the contended timing is not a planning figure.
  - A cherry-pick conflict in `verification.md` is always resolved with `--theirs` on the
    live worktree: the record lives in the main tree only.
  - The planner's `EXPLAIN (ANALYZE, BUFFERS)` was the fastest way to see where a slow
    retrieval statement spent its time (once per leg, 32,000 buffers from disk).
  - When counting embedding rows per run, the acquire stage's abstract (envelope) embeddings
    land in the same table during acquire; a window count over `chunk_embedding` without
    the snapshot kind over-counts the ingest stage by about 1,200 to 1,500 rows per round.
  - A measurement round on a repeated question after the body-hash store is live is not
    like-for-like: 30 to 50 documents per run come from the store, and the ingest wall
    drops with them. Measure the store's effect by naming the `already_in_store` count.
  - An adaptive pool at its cap finds the quota's edge by being throttled; a run that embeds
    alone sees more throttle sleeps than one request in flight did, and that is the probe's
    cost, not a regression.
  - The SQL search's per-call latency on the laptop doubles or triples under a concurrent
    run's embedding writes (the 128 MB buffer pool is shared); compare search timings only
    across sessions with the same overlap.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) § "Queued ingest, document store,
SQL retrieval, step timeouts (task 057 seams)": parse profile v2 is the markup rule only
(header, page-number and footnote rules with E6's numbers, D8); the fallback-parser trigger
signals; per-host coordination across functions (D11); the retention script's scheduling
(D3); HNSW (D7); per-claim judge filtering with E9's numbers; the low-effort judge revisit
with E3's numbers (D14); the prod route flip; alarm actions (a notification topic); the three
NAT instances; a second retry on once-per-run steps. The 056 seam "timeout retries are billed
but untraced" is closed by D12.
