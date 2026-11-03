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
  [call-sites.md](call-sites.md) note 2). Both boto3 clients get `read_timeout=60` and
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
  `step=`, the `_STAGE_STEP` dict, one rewritten comment). The full diff is committed as
  [repin-phase1-timeouts.diff](repin-phase1-timeouts.diff); no prompt text changed
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
  gains a `DependsOn`); nothing removed, nothing stateful replaced. The trimmed synth is
  committed as [cdk-synth-ingest.json](cdk-synth-ingest.json) (placeholders for account,
  VPC and subnet ids). The prod diff needs the `pa-prod` profile. **Owner information:**
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

## Checks beyond the build

Filled per phase below.

## End-to-end command

Filled at the step-6 exit.

## Diff summary

Filled at the step-6 exit.

## Review findings

Added after the review stack (step 7).

## Rubric status

Filled at the step-6 exit.

## Intent & assumptions

## Known unverified items

## Public safety

Run ids, counts and timings only. No URLs, no report text, no keys. The Langfuse observation
cache used for the timeout table holds timing fields only and stays in the scratchpad.

## Review handoff (step-7/8 inputs)

- **Knowledge candidates** (grown during the build):
  - zsh does not word-split an unquoted `$variable` holding several arguments; use `${=var}`
    (cost one failed script call in Phase 0).
  - The dev server caps concurrent walks at two (`RUN_EXECUTOR_MAX`); a third fixed-question
    run returns HTTP 409 "capacity" and must be started when a slot frees.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md). Listed at the step-6 exit.
