# Implementation plan: 057-queued-ingest

> Status: **draft 2, 2026-11-03, awaiting the owner's approval.** Draft 1 was reviewed by two
> read-only lanes ([adversarial-review-plan.md](adversarial-review-plan.md): Codex 16
> findings, Opus 26); every finding is folded here or listed under § Owner items. Contract:
> [contract.md](contract.md) (revision 4: revision 3 approved 2026-11-03, plus the clause
> corrections the review found). Rubric: [rubric.md](rubric.md). Terms, needs (N1 to N15),
> decisions (D1 to D15), gates (G1 to G10) and spec items (S1 to S5) are defined in the
> contract and not restated here. Executor routing follows `docs/agentic-ops/harness.md`
> § Agent-side model routing and the owner's ruling of 2026-09-04: judgment-bearing build
> work goes to `deep-reasoner`, mechanical volume to `fast-worker`, probes and measurements
> to `builder`, seam design, live runs and owner-facing reads stay with the lead (the Codex
> lane asked for Codex as the doer; the owner's ruling stands). The build runs in a fresh
> conversation with task-cycle-build, opening on Phase 0.

## Context

Where the minutes go and what each phase removes (contract § Goal; bedrock route, median of
the 2026-11-02 runs):

| Stage | Today | After | Phase |
|---|---|---|---|
| Every model-call stage, stall tax | 1 to 5 stalls × 120 s per run | each stall costs the step's timeout: 5 to 40 s on steps with enough history, today's value on once-per-run steps | 1 |
| Grounding judge | 11.5 s per call | 5.4 s per call | 1 |
| Screen and classify pools | 50 s and 40 s | about 17 s and 23 s | 1 |
| Reading the full texts: fetch and parse | 281 s | about 60 to 90 s | 4 and 6 |
| Reading the full texts: embedding | 457 s (quota-bound plus JSONB writes) | tokens ÷ quota, about 4 min today, about 1 min after the raise; the JSONB cost gone | 2, 4 |
| Retrieval scope load per run | 1.4 to 2.7 s plus a 20,000-unit ceiling | one SQL query per search | 3 |

Phase order: timeouts and widths first (small, independent, measurable alone); then the
schema, because revision 1 carries the `queued` status and the binary embedding column that
both the stage and the retriever need; then retrieval in SQL while the Python path still
exists to compare against; then the queued stage; then infra and staging. Each phase lands
and is measured before the next changes anything it touched. (The contract recorded the
owner's order as timeouts → queued ingest → SQL retrieval; the schema dependency is the
reason for the swap, put to the owner in § Owner items 3.)

## Decisions taken in this plan

| # | Topic | Decision |
|---|---|---|
| P1 | Step timeouts and the traced retry (N10c, D12) | `Step` gains `timeout_s: float`; `[steps.<name>]` carries **today's per-site literal** for every step (60, 120 or 30 s) so nothing falls back to the SDK default and `openai-direct` keeps today's values; `[routes.bedrock.steps.<name>]` overrides only the measured steps. `Route.timeout_for(step)` resolves override, then base. The timeout is applied **per request**, not per client: `openai_kwargs(...)`, `_step_kwargs` and `traced_parse` take `step` and call `client.with_options(timeout=route().timeout_for(step))`; shared clients stay shared with `max_retries=0`. One retry lives in a wrapper around `tracing.traced_call` that takes `step`: it retries once on `APITimeoutError`, `APIConnectionError`, 5xx, and `RateLimitError` honouring Retry-After (today's SDK coverage); it sets `step`, `attempt` and a shared `logical_call_id` as metadata **when the observation opens**, so a timed-out attempt carries them; observation names do not change (Langfuse saved views depend on them). Sites that already retry with a call budget (screen stage 1, select rerank, extract) are listed by a deep-reasoner before the sweep: wrap, or already budgeted. The OpenAI embedding client gets `max_retries=0` and keeps its own backoff loop. Both Bedrock boto clients get `botocore.config.Config(read_timeout=60, retries={"mode": "standard", "max_attempts": 1})`. Streamed chat clients keep their current timeout and are exempt. `scripts/step_timeouts.py` derives the values from Langfuse over **all bedrock runs since the GPT-6 switch (2026-11-02)**: per step, generations shorter than their client's timeout with no error (the historical stand-in for a healthy first attempt), n, p99 × 2, floor 5 s, only when n ≥ 100; steps below 100 keep today's value and are listed; the script prints the route-file table and the verification table. |
| P2 | Widths (N10b, N10d) | `MAX_CONCURRENT_STAGE1` and `MAX_CONCURRENT_CLASSIFY` 12 → 48; `OPTION_SEARCH_WIDTH` 4 → 10. Constants. Measured one at a time (P12), with peak database connections recorded at width 10. |
| P3 | Judge effort (N15, D14) | `[routes.bedrock.steps.judge_grounding] reasoning_effort = "low"` (the loader's key; unknown keys raise); `openai-direct` keeps `medium`. |
| P4 | Compiled bytecode (N13, G8) | One Dockerfile line in the final stage after the venv copy: `RUN python -m compileall -q /app/.venv /app/src`. The `.dockerignore` patterns gain `**/` so laptop bytecode is not shipped (E4); this second line is named at the gate as part of G8. |
| P5 | Migrations (D2) | `alembic/env.py` sets `transaction_per_migration=True`. Three revisions chained from `152a234e2391`. **rev1 expand** (every statement `IF NOT EXISTS` / rerun-safe): `source_snapshot.body_hash`, `parse_profile`, `segmentation_policy` + backfill from `metadata` + the partial unique index; `task_source_snapshot.ingested_by_run_id` (uuid, nullable) and `fetched_from` (text, nullable) (owner G2 item); `queued` into `ck_tss_full_text_status`; `CREATE EXTENSION IF NOT EXISTS vector`; `chunk_embedding.embedding vector(1536)` and `tokens text[]`; `chunk_embedding.vector DROP NOT NULL` so the new image serves at rev1; GIN on `tokens`. **rev2 backfill, data only**, inside `op.get_context().autocommit_block()`, pure SQL in batches of 2,000 rows: `embedding = vector::text::vector`, `tokens = regexp_matches(lower(substr(chunk.content, start+1, end-start)), '[0-9a-z]+', 'g')` aggregated per unit (the product tokeniser is ASCII-only, so `lower` equals `casefold`); resumable on `embedding IS NULL`. **rev3 drop**: asserts no null `embedding`, drops the JSONB column; downgrade rebuilds JSON from the binary column (float32, documented). rev3 lands at the **end of Phase 3**, after the Python retriever is deleted; through Phase 3 both columns are written. A failure-injection test fails rev2 after a committed batch and reruns `upgrade head`. `schema.py` gets a small `UserDefinedType` for `vector(1536)` (no pgvector package, G3). The tokeniser moves to `core/tokens.py` (core must not import `evidence_search`); a test checks the migration's SQL against it on a fixture. |
| P6 | Dev and CI image (G9) | `docker-compose.yml` `image: pgvector/pgvector:pg17`. Compose declares no volume, so Postgres 17 would refuse the 16 data directory: Phase 0 dumps with `pg_dumpall` before the switch and restores after, checking row counts; the demo worktree shares this database (memory note) and is told. `tests/conftest.py` runs `CREATE EXTENSION IF NOT EXISTS vector` per worker database (the compose user is a superuser; harmless). CI runs `make setup` on a fresh database, so no CI edit beyond the compose file. |
| P7 | Retrieval parity and the query repository (N8, D7) | **Committed test:** the synthetic corpus (`tests/evidence_search/synthesis/data/retrieval_synthetic/`: 40 chunks, 3 snapshots, 2 scopes, stub vectors and tokens covering every boost, filter, tie-break and the multi-scope rule) run through both retrievers until the Python one is deleted, then the SQL one against the frozen expected output. **Recorded, not committed:** after rev1, on the dev database, the Python retriever pointed at the float32 column and the SQL retriever run side by side on the fixed questions' section queries (from Langfuse `search_chunks` tool calls) and on the 20 feasibility queries; same top-8 in order, scores recorded in `verification.md`. SQL computes the fused score, every boost and the clamp **before the limit**, and the limit is the per-leg pool (200), not 50; Python keeps the reranker seam, the cut to 8, the budget, dedup, windowing and provenance for returned candidates. **Interface (lead):** `RetrievalScope` becomes a frozen record of snapshot ids and scope metadata plus a connection factory; synthesis passes a factory over its component connection, chat passes the engine and opens one short read per search; both callers are tested after the scope-building connection has closed. |
| P8 | Per-document function (N2, N6, N9) | `ingest_document(connect, link_row, *, fetcher, parse_fn, deadline) -> DocumentOutcome` in `sourcing/ingest_document.py`, where `connect` is a connection factory. It carries today's full cascade: Europe PMC XML first, next URL on a parse failure, `_maybe_discover_url`, `_apply_oa_cross_check`, the reason-code priority; fetch waits honour Retry-After (429 and 503, capped at 30 s); every wait and the parse kill are capped at `deadline − now − margin`. It opens a connection only for the store lookup and for the one short write transaction (`INSERT source_snapshot … ON CONFLICT (body_hash, parse_profile, segmentation_policy) DO NOTHING RETURNING`, re-select on conflict, chunks, the link update guarded on `queued` with the breadcrumbs on the link row). No embedding. The parse subprocess is today's `_worker_entry` with the kill. |
| P9 | One stage, two queue clients (N1, N3, D1) | The stage has one code path in both modes: in its own committed transaction re-queue orphaned `queued` rows, flip eligible rows to `queued`, **commit, then send**; poll every 3 s on the component connection with ticks (`fetched=None`); embed per tick (P11); at 600 s mark the rest `fetch_failed` / `not_ready` in its own transaction; return the counts (`already_in_store` inside `ingested`, kept out of the SSE summary). Partial `SendMessageBatch` failures mark their rows `fetch_failed` / `send_failed`. `QueueClient` protocol with two implementations: `SqsQueueClient` (boto3, batches of 10) and **`LocalQueueClient`, whose `send()` runs the handler on a thread pool** (in-process mode on laptops), with an inline mode that runs the handler on the caller's connection for tests that use the rolled-back fixture. `_ParseScheduler`, `_run_parse_jobs`, `_drain_*` and the fetch thread pool are deleted. Message schema: see § Owner items 2 (ids only, lead's recommendation, or N1 as written). `ingest_mode` from `POLICY_ATLAS_INGEST_MODE` (`in_process` default, `queued`), read in `api/settings.py`, and plumbed through all three construction paths: `deps.get_runner_backends()`, the startup re-execution in `app.py`, and the CLI in `runtime/agent.py`; `RunnerBackends` carries the queue client. |
| P10 | Handler (N2, D5) | `ops/ingest_worker.py::handler(event, context)`: one record (batch size 1); parse the message; compute `deadline = now + remaining − 10 s`; call `ingest_document`; the receive-count rule: on the first attempt a failure that should be retried leaves the row `queued` and returns the record in `batchItemFailures`; on the second it writes the reason. Reads `DATABASE_URL` from Secrets Manager at cold start through the function's role; no model credential and no Bedrock permission (D6); `POLICY_ATLAS_MODEL_ROUTE` is set because the route is resolved at import. `awslambdaric` in the main dependency group with the marker `sys_platform == "linux"`. |
| P11 | Stage embedding (D6) | `embed_pending_chunks(…, snapshot_ids=)`. `core/embeddings.py::AdaptivePool` owns concurrency **and** backoff: the backends stop retrying throttles internally and raise a `Throttled` signal the pool catches (halve in flight, floor 1, sleep with the backend's backoff curve; +1 after 5 clean batches; cap `route().embeddings.pool_cap`, default 8); throttling is excluded from `_embed_units_with_isolation`'s splitting; one pool per stage across ticks; database writes on the calling thread; the embedding loop runs on its own thread so the poll, ticks and the deadline are never blocked; before the stage returns it embeds everything ingested. Test: a fake backend that throttles above a set rate; the pool converges and no batch is split for throttling. |
| P12 | Measurement (D9, N12) | Build-open: three fresh fixed-question runs on bedrock, run the way the afters are run (the like-for-like "before"; the 2026-11-02 anatomy stays as the historical table). After each lever: three runs, median with spread, `scripts/stage_walls.py` (per-stage wall from `event_log`, from the anatomy's `40_anatomy.py`) plus the per-step attempt counts from Langfuse. Levers in order: timeouts; widths; judge; rev1 and binary writes; SQL retrieval; the per-document rewrite (in-process); the adaptive pool. |
| P13 | Infra (N11) | In `policy_atlas_stack.py`: `sqs.Queue` (retention 4 days, SSE, dead-letter after 2), `lambda_.DockerImageFunction` from the same asset with `cmd` override, 1,769 MB, 180 s, private subnets, a security group with ingress to the database security group read from SSM (as the stack reads it today), `SqsEventSource(batch_size=1, max_batching_window=0, max_concurrency=20, report_batch_item_failures=True)`, a Secrets Manager read grant for the app secret, no Bedrock policy, `sqs:SendMessage` and the queue URL on the API task, alarms on dead-letter depth, NAT network out and writer CPU credits, a log group with 30-day retention and URL redaction in the handler's logger. `pa_config.json` gains `ingest_mode` (`staging: queued`, `prod: in_process`). CDK tests pin every value. `DEPLOYMENT.md` notes that on later deploys the function updates before the migration runs, so a message in flight during a deploy may dead-letter. |
| P14 | Deploy waiter (G10) | `run_migrations` replaces `aws ecs wait tasks-stopped` with a `describe-tasks` loop every 15 s up to `MIGRATION_WAIT_MAX_S` (default 3,600; the deploy role lasts 7,200 s and the job 90 min), failing loudly after. |
| P15 | Spec and knowledge | S1 to S5 applied in Phase 5 with one `docs/specs/log.md` line (S2 names `not_ready`); `deferred.md` entries per rubric item 7; two knowledge concepts; the data-flow note at `docs/agentic-ops/data-flow-queued-ingest.md`; `DEPLOYMENT.md` additions (dead-letter drain, the waiter, `ingest_mode`, the deploy-order note). |
| P16 | Gates | Full `make verify`: build-open (gate 1), end of Phase 0 (compose image, conftest, gate 2), end of Phase 1 (every call site, gate 3), end of Phase 2 (schema, gate 4), end of Phase 3 (retrieval and rev3, gate 5), end of Phase 4a (ingest-adjacent, gate 6), end of Phase 4b (gate 7), step-6 exit (gate 8, plus `make audit`). Phase 5: `make verify-fast` plus `make -C infra test`. |
| P17 | Connection budget (N5) | Written at the plan gate from `show max_connections` on the staging writer (owner item): API pool 15 + 10 overflow, up to 10 runs each with one component connection and, at width 10, 10 child walk connections, the migration task's one, operators' few, and the functions' 20 (one each, held only for the lookup and the write); headroom 20%; if it does not fit, `max_concurrency` drops first, then `OPTION_SEARCH_WIDTH`. In-process mode holds no connection during fetch or parse. |

## Owner items

Before the plan is approved:

1. **Phase 6 and the merge.** Deploying the branch to staging before merge works only if dev
   merges are frozen for the window, because the next dev deploy would ship an Alembic chain
   without this branch's revisions and the migration task would fail with the service at 0.
   Options: (a) freeze dev merges, deploy the branch, measure, then merge (the rubric as
   written); (b) merge first, and Phase 6 is the first post-merge step, with rubric items 15,
   26 and 28 amended to accept post-merge evidence. Lead's lean: (b).
2. **Message content.** N1 as written (URLs and the open-access flag in the message), or ids
   only (`link_row_id`, `run_id`), with the function reading the candidates from the link row
   and snapshot metadata. Ids only keep URLs out of the queue and the dead-letter queue.
   Lead's lean: ids only (a minor amendment to N1).
3. **Phase order.** Schema before the queued stage, for the dependency stated in § Context.
4. **G2 addition.** Two nullable columns on `task_source_snapshot` (`ingested_by_run_id`,
   `fetched_from`) to receive the breadcrumbs that leave the shared row; the shared row's
   `source_locator` keeps the public document URL.
5. **G5 timing.** The `cdk diff` review moves from the plan gate to an owner checkpoint after
   Phase 5 and before any staging deploy.
6. **Staging dry run** (rubric 19). Either DevOps clones staging's Aurora and runs the
   migration task against it, or the dry run is dropped in favour of the non-blocking design
   (nullable JSON column, resumable backfill, serving possible at rev1) plus the row counts.
   Lead's lean: drop it.
7. **Pre-build facts** (read-only, owner or DevOps): staging and prod `chunk_embedding` row
   counts; `show max_connections` on the staging writer; the account's Lambda concurrency
   and memory quotas; whether staging's `DATABASE_URL` user can run `CREATE EXTENSION`; the
   quota case's state.
8. **For information:** in-process mode becomes a local queue client that runs the handler on
   threads, so the stage has literally one path in both modes; the Opus lane proposed it and
   the lead adopted it.

## Phases

Each phase ends in a commit on `task/057-queued-ingest`. Every `lead` mark carries its reason.

### Phase 0 — Build-open, measurement tools, dev image (P6, P12, P1 derivation)

0. `make verify` on the branch as it stands; record counts and time. — **lead inline** (a
   one-command gate reading).
1. `scripts/stage_walls.py` and `scripts/step_timeouts.py` (P1, P12) with saved-fixture
   tests. — **deep-reasoner**.
2. Baseline readings before the image switch: `stage_walls.py` on the twelve 2026-11-02
   sessions reproduces the anatomy's Table 2; three fresh fixed-question runs on bedrock as the
   like-for-like before; `step_timeouts.py` over all bedrock runs since 2026-11-02 prints the
   per-step table with n. — **builder** runs; **lead** reads (owner-facing numbers).
3. Dev database: `pg_dumpall` to the scratchpad; compose image to `pgvector/pgvector:pg17`;
   restore; row counts checked against the dump; `tests/conftest.py` extension line; the
   `verify.yml` comment updated; the demo worktree note. — **fast-worker** (exact steps; done
   is matching row counts and a green suite).

**Gate:** full `make verify` (gate 2).

### Phase 1 — Timeouts, widths, judge effort, image, matcher (N10, N13, N14, N15, D12, D14, D15)

1. The per-site table (P1): every client builder and every call site, its current timeout,
   whether it already retries with a budget, and the step name; today's literals written into
   `[steps.<name>] timeout_s`. — **deep-reasoner** (judgment per site; done is the table plus
   the route file carrying today's values).
2. P1 plumbing: `Step.timeout_s`, `Route.timeout_for`, per-request `with_options`, the retry
   wrapper around `traced_call` with pre-call metadata, `max_retries=0`, the boto `Config`,
   the embedding client decision; a test pins that every step has `timeout_s` or is listed as
   exempt and that every request path passes its step. — **deep-reasoner** (the seam's
   signatures are fixed in P1; the implementation has a machine-checkable done).
3. The sweep from the table: every call site passes `step`, literals removed, budgeted sites
   left as the table says; code-only re-pins recorded with diffs. — **fast-worker**
   (transcription of the table).
4. Bedrock overrides from Phase 0's table for steps with n ≥ 100; `judge_grounding`
   `reasoning_effort = "low"` under the same override. — **lead inline** (a table transcribed
   from a saved result; owner-facing).
5. Measurement, one lever at a time, three runs each (P12): (a) timeouts, with per-step
   attempt counts; (b) widths, with peak connections at width 10 and no call over 300 s on
   the scoping question (N10a); (c) the judge at `low`. A too-tight step is raised once and
   the lever re-run. The owner reads one report after (c). — **builder** runs; **lead** reads
   and decides raises.
6. Dockerfile `compileall` line and the `.dockerignore` fix; cold import before and after in a
   fresh container. — **fast-worker** builds; **builder** measures.
7. `quote_verify.py`: `qv_v2`, symmetric strip, offset map, the anchor-span and two-way tests;
   the brief lists the 11 consumers; extraction anchor tests unchanged or re-pins recorded;
   stored `qv_v1` rows untouched. — **deep-reasoner**.

**Gate:** full `make verify` (gate 3).

### Phase 2 — Schema and the deploy waiter (D2, G9, G10, P5, P14, P17)

1. `transaction_per_migration`, rev1 and rev2 (P5), the `vector(1536)` column type,
   `core/tokens.py`, the frozen-SQL parity test, the failure-injection test, upgrade and
   downgrade round-trips. — **deep-reasoner**.
2. `embed_pending_chunks` writes both columns (`vector` JSON and `embedding` binary) plus
   `tokens` through Phase 3. — **deep-reasoner**.
3. `scripts/deploy.sh` `run_migrations` polling loop (P14) with a shell check. —
   **deep-reasoner** (AWS polling and failure semantics need judgment).
4. Migration timing on the dev database; three fixed-question runs after the binary writes.
   — **builder**.
5. The connection budget (P17) written into `verification.md` from the owner's
   `max_connections` reading. — **lead** (owner-facing arithmetic).

**Gate:** full `make verify` (gate 4).

### Phase 3 — Retrieval in SQL (N8, D7, P7)

1. The synthetic corpus and the two-retriever test. — **deep-reasoner**.
2. The query-repository interface (lead-pinned signatures in P7); `ChunkRetriever.search` as
   one statement with boosts and clamp before the per-leg limit, over the frozen snapshot
   list; both callers switched, chat opening one short read per search; the side-by-side
   parity recording on the dev database (fixed-question queries and the 20 feasibility
   queries); then the Python scope load, scoring, `RETRIEVAL_UNIT_CAP` and
   `RetrievalUnitCapError` deleted and the synthetic test re-pointed. — **deep-reasoner**.
3. rev3 (the drop) and the removal of the JSON write path. — **deep-reasoner**.
4. Query latency on the dev corpus; three fixed-question runs; the owner's content read. —
   **builder** runs; **lead** reads.

**Gate:** full `make verify` (gate 5).

### Phase 4a — Per-document function, markup rule, local queue client (N6, N7, N9, D3, D8, P8, P9)

1. Parse profile v2's markup rule across the PDF, HTML, JATS and plain paths; new profile and
   policy names; the digest test re-pinned; the E6 control metrics as a test on the fixture
   PDFs. — **deep-reasoner**.
2. `ingest_document` (P8) with the cascade, Retry-After for 429 and 503 (valid delay, malformed
   header, the 30 s cap), the store lookup, the short write transaction, the guarded link
   update, the breadcrumbs on the link row, the JSON-key test, the race tests on a separate
   committed-data suite. — **deep-reasoner**.
3. The stage as one path (P9) with `LocalQueueClient` and its inline test mode; the engine and
   connection factory plumbed to the stage through the three construction paths; the
   scheduler, drains and fetch pool deleted; statuses and reasons identical to today's on the
   fixture corpus; the connection-count test. — **deep-reasoner**.
4. Three fixed-question runs in-process. — **builder**.

**Gate:** full `make verify` (gate 6).

### Phase 4b — Adaptive embedding, SQS client, handler (N1 to N5, D1, D4, D5, D6, P9, P10, P11)

1. `AdaptivePool` and the backend throttle signal (P11), `snapshot_ids=`, the embedding thread
   off the poll loop, the convergence test. — **deep-reasoner**.
2. `SqsQueueClient`, the message schema test (no user id; the owner's ruling on item 2), the
   commit-then-send order, partial-send handling, the orphan re-queue, `not_ready`, the real
   second-connection test and the three fake-queue scenarios. — **deep-reasoner**.
3. The handler (P10) with the deadline, the receive-count rule and `batchItemFailures`;
   `awslambdaric` with its platform marker (`uv lock`, `make audit`); handler tests with a
   fake event. — **deep-reasoner**.
4. The image under the Lambda Runtime Interface Emulator on amd64: read-only root, non-root
   user, `/tmp` only, one fixture message against the local database; the result recorded. —
   **builder**.
5. Three fixed-question runs in-process with the pool on; the markup-cause check on quote
   failures; the owner's content read. — **builder** runs; **lead** reads.

**Gate:** full `make verify` (gate 7).

### Phase 5 — Infra, config, documents (N11, N12, P13, P15, S1 to S5)

1. CDK constructs (P13), `pa_config.json`, infra tests pinning every value in N4, N5 and N11;
   `cdk diff` saved for the owner's checkpoint (item 5). — **deep-reasoner**.
2. `scripts/prune_unlinked_snapshots.py` with the locking rule and tests (not scheduled). —
   **deep-reasoner**.
3. The data-flow note, the retention rule text, `deferred.md` entries, two knowledge concepts,
   S1 to S5 with the spec-log line, `DEPLOYMENT.md` additions. — **lead** (spec text and
   owner-facing documents).

**Gate:** `make verify-fast` plus `make -C infra test`.

### Phase 6 — Staging deploy and measurement (D9, N12), shape per owner item 1

1. The owner's `cdk diff` checkpoint; then the deploy (`make deploy-update DEPLOY_ENV=staging`
   by the owner or DevOps), the migration time from the waiter's output, the quota in force.
2. Three fixed-question runs on staging in `queued` mode; `stage_walls.py` through the
   jumpbox; the function's logs for the ingest split and the dead-letter depth; the embedding
   requests, tokens and sleeps. — **lead** (live evidence on the owner's environment).

### Step-6 exit — lead

`make verify` and `make audit` green; `verification.md` complete with every table read from
saved results, the re-pin diffs, the connection budget, the parity recording, the emulator
result and anything reverted; the knowledge notes and `deferred.md` committed. **Stop.** The
review runs in a fresh conversation.

## Executor summary

- **lead** — the P1 and P7 seam designs, the route-file override table, the connection
  budget, every live run and owner read, the spec amendments and owner-facing documents,
  inline one-line edits, raises of too-tight timeouts.
- **deep-reasoner** — the measurement scripts, the per-site timeout table and plumbing, the
  three migrations and the column type, the deploy waiter, the synthetic corpus and the SQL
  retriever, the markup rule, the per-document function and its races, the one-path stage and
  both queue clients, the adaptive pool, the handler, the CDK constructs, the prune script.
- **fast-worker** — the dev image switch with dump and restore, the call-site sweep from the
  table, the Dockerfile lines.
- **builder** — cold-import timing, migration timing, query latency, the emulator run, every
  fixed-question run and its tables.
- **owner or DevOps** — the pre-build facts, the `cdk diff` checkpoint, the staging deploy, the
  quota case.

## Out of this slice

Everything in contract D10 and § Out of scope; the prod route flip; the header, page-number
and footnote parse rules; the low-effort judge's labelled-set check and per-claim judge
filtering (synthesis refinement); the fallback parser; per-host coordination across functions.
