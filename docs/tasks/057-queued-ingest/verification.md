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

### N13, compiled bytecode — Dockerfile edited; cold-import measurement pending

One `RUN python -m compileall -q /app/.venv /app/src` line after the venv copy; the
`.dockerignore` bytecode patterns gained `**/` so the laptop's `.pyc` files stay out.

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
