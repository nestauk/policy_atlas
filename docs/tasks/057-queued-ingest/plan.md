# Implementation plan: 057-queued-ingest

> Status: **draft 1, 2026-11-03, awaiting the plan-stage adversarial review and the owner's
> approval.** Contract: [contract.md](contract.md) (revision 3, approved 2026-11-03). Rubric:
> [rubric.md](rubric.md). Terms, needs (N1 to N15), decisions (D1 to D15), gates (G1 to G10)
> and spec items (S1 to S5) are defined in the contract and not restated here. Executor
> routing follows `docs/agentic-ops/harness.md` § Agent-side model routing and the owner's
> ruling of 2026-09-04: judgment-bearing build work goes to `deep-reasoner`, mechanical
> volume to `fast-worker`, probes and measurements to `builder`, design seams, live runs and
> owner-facing reads stay with the lead. The build runs in a fresh conversation with
> task-cycle-build, opening on Phase 0.

## Context

Where the minutes go and what each phase removes (contract § Goal; bedrock route, median of
the 2026-11-02 runs):

| Stage | Today | After | Phase that moves it |
|---|---|---|---|
| Every model-call stage, stall tax | 1 to 5 stalls × 120 s per run | each stall costs the step's timeout, 5 to 40 s | 1 |
| Grounding judge | 11.5 s per call | 5.4 s per call | 1 |
| Screen and classify pools | 50 s and 40 s | about 17 s and 23 s | 1 |
| Reading the full texts: fetch and parse | 281 s | about 60 to 90 s | 4 and 6 |
| Reading the full texts: embedding | 457 s (quota-bound plus JSONB writes) | tokens ÷ quota, about 4 min today, about 1 min after the raise; the JSONB cost gone | 2, 4 |
| Retrieval scope load per run | 1.4 to 2.7 s plus a 20,000-unit ceiling | one SQL query per search | 3 |

The order is the owner's: timeouts and widths first (small, independent, measurable on their
own), then the store and retrieval, then the queued stage, then infra and staging. Each phase
lands and is measured before the next changes anything it touched.

## Decisions taken in this plan

| # | Topic | Decision |
|---|---|---|
| P1 | Step timeouts (N10c, D12) | `Step` gains `timeout_s: float | None`; `[steps.<name>]` and `[routes.<route>.steps.<name>]` accept `timeout_s`; `Route.timeout_for(step)` returns the route override, else the step value, else the client's current default. `resolve_openai_client` gains `step=` and reads `timeout_for(step)`; `max_retries` becomes 0 everywhere. One traced retry lives in `core/openai_client.py` (`call_with_one_retry(fn, *, step)`): it retries once on `APITimeoutError`, `APIConnectionError` and 5xx, each attempt its own Langfuse generation named `<step>` with an `attempt` field. Streamed chat clients keep their current timeout and are exempt. The values are derived by `scripts/step_timeouts.py` from Langfuse: per step, first-attempt successes in the last 20 Evidence search and scoping runs on bedrock, p99, × 2, floor 5 s, only when n ≥ 100; the script prints the table that goes into the route file and `verification.md`. |
| P2 | Widths (N10b, N10d) | `MAX_CONCURRENT_STAGE1` and `MAX_CONCURRENT_CLASSIFY` 12 → 48; `OPTION_SEARCH_WIDTH` 4 → 10. Constants, not route values. Measured one at a time (P12). |
| P3 | Judge effort (N15, D14) | `[routes.bedrock.steps.judge_grounding] effort = "low"`; the `openai-direct` step keeps `medium`. |
| P4 | Compiled bytecode (N13, G8) | One Dockerfile line in the final stage after the venv copy: `RUN python -m compileall -q /app/.venv /app/src`. The `.dockerignore` patterns gain `**/` so laptop bytecode is not shipped (observed in E4; a tidy-up in the same change). |
| P5 | Migration files (D2) | Two Alembic revisions. `<rev1>_document_store_and_vectors`: `source_snapshot.body_hash/parse_profile/segmentation_policy` + backfill from `metadata` + the partial unique index; `queued` into `ck_tss_full_text_status`; `CREATE EXTENSION IF NOT EXISTS vector`; `chunk_embedding.embedding vector(1536)` and `tokens text[]`; backfill in batches of 2,000 rows with a commit per batch, resumable on `embedding IS NULL`; GIN on `tokens`. `<rev2>_drop_vector_jsonb`: asserts no null `embedding`, drops the JSONB column. Downgrade of rev2 rebuilds the JSONB from the binary column (documented as float32). The tokeniser used for `tokens` is the product's (`synthesis_tools._tokens`, ASCII-only), imported by the migration. |
| P6 | Dev and CI image (G9) | `docker-compose.yml` `image: pgvector/pgvector:pg17`; `tests/conftest.py` runs `CREATE EXTENSION IF NOT EXISTS vector` on each worker database before `alembic upgrade head` (the migration also does it; the test path needs no superuser on the pgvector image). `make setup` unchanged. |
| P7 | Parity fixture (N8, D7) | Before Phase 2's migration, `scripts/capture_retrieval_parity.py` replays the fixed questions' section queries (from Langfuse `search_chunks` tool calls) through the Python retriever on the dev database and saves `{query, filters, top-8 chunk ids in order}` per query to `tests/evidence_search/synthesis/data/retrieval_parity_bedrock.json` (ids and ranks only: public-safe). Phase 3's SQL retriever must reproduce it. The synthetic corpus (`tests/.../data/retrieval_synthetic/`) has 40 chunks across 3 snapshots and 2 scopes with stub vectors and tokens that exercise every boost, filter, tie-break and the multi-scope rule; one test runs both retrievers over it until the Python one is deleted, then the SQL one against the frozen expected output. |
| P8 | Per-document function (N6) | `ingest_document(conn, link_row, *, fetcher, parse_fn, store) -> DocumentOutcome` in `sourcing/ingest_document.py`: fetch (with Retry-After), body hash, store lookup, parse in a subprocess (today's `_worker_entry` with the kill), the short write transaction (`INSERT … ON CONFLICT (body_hash, parse_profile, segmentation_policy) DO NOTHING RETURNING`, re-select on conflict, chunks, the guarded link update). No embedding. In-process mode: `ThreadPoolExecutor(max_workers)` where each worker opens its own connection from the engine and commits per document. `_ParseScheduler`, `_run_parse_jobs`, `_drain_*` and the fetch thread pool are deleted. |
| P9 | Queued stage (N1 to N5) | `ingest_mode` from `POLICY_ATLAS_INGEST_MODE` (`in_process` default, `queued`), read in `api/settings.py` and passed through `RunnerBackends` like the fetcher. `sourcing/ingest_queue.py` holds a `QueueClient` protocol (`send(messages)`), an SQS implementation (boto3, batches of 10) and a fake. The stage receives the engine: in one committed transaction it re-queues orphaned `queued` rows, flips eligible rows to `queued` and sends messages; polls every 3 s on the component connection; publishes ticks with `fetched=None`; at 600 s marks the rest `fetch_failed` / `not_ready` in its own transaction. Message schema: `{"link_row_id", "run_id", "candidate_urls", "pmcid", "is_oa", "schema": 1}`. |
| P10 | Handler (N2, D5) | `ops/ingest_worker.py::handler(event, context)`: for each record, parse the message, open one connection, call `ingest_document`, always write a final reason-coded status before returning (using `context.get_remaining_time_in_millis()` with a 10 s margin), return `batchItemFailures` for records that must be redelivered (a 429 still refused after Retry-After). Reads `DATABASE_URL` and the route key from Secrets Manager at cold start through the function's role. |
| P11 | Stage embedding (D6) | `embed_pending_chunks` gains `snapshot_ids=` so each poll tick embeds the snapshots that landed since the last tick; the adaptive pool (`core/embeddings.py::AdaptivePool`: start 2, halve on `ThrottlingException`, +1 after 5 clean batches, cap `route().embeddings.pool_cap` default 8) sends batches concurrently; the existing per-batch backoff stays. The in-process mode calls the same function per completed document. |
| P12 | Measurement (D9, N12) | `scripts/fixed_questions.py` (task 056) starts the three Evidence search questions and the scoping question; `scripts/stage_walls.py` (new, from the anatomy's `40_anatomy.py`) prints per-stage wall from `event_log` for the sessions given. Levers are measured one at a time in Phase 1 (timeouts → widths → judge), then Phase 3, then Phase 4; each measurement is three runs on bedrock, median reported with the spread. |
| P13 | Infra (N11) | New constructs in `policy_atlas_stack.py`: `sqs.Queue` (+ dead-letter), `lambda_.DockerImageFunction` from the same `ecr_assets` asset with `cmd` override, `SqsEventSource` with `max_concurrency=20` and `report_batch_item_failures=True`, security group with Aurora ingress (imported from the database stack's exports), `secretsmanager` grants, Bedrock invoke policy on the function role, `sqs:SendMessage` on the API task role, three alarms, log group retention 30 days. `pa_config.json` gains `ingest_mode` per environment (`staging: queued`, `prod: in_process`). CDK tests pin the values. |
| P14 | Deploy waiter (G10) | `run_migrations` replaces `aws ecs wait tasks-stopped` with a loop over `describe-tasks` every 15 s up to `MIGRATION_WAIT_MAX_S` (default 3,600), failing loudly after. |
| P15 | Spec and knowledge | S1 to S5 applied in Phase 5 with one `docs/specs/log.md` line; `deferred.md` entries per rubric item 7; two knowledge concepts (`queued-ingest-document-store.md`, `step-timeouts-and-traced-retry.md`); the data-flow note at `docs/agentic-ops/data-flow-queued-ingest.md`. |
| P16 | Gates | Full `make verify`: build-open (gate 1), end of Phase 0 (compose image and conftest, gate 2), end of Phase 1 (every call site, gate 3), end of Phase 2 (schema, gate 4), end of Phase 3 (retrieval, gate 5), end of Phase 4b (ingest-adjacent, gate 6), step-6 exit (gate 7, plus `make audit` for the new dependency). `make verify-fast` at the end of Phases 4a and 5. |

## Owner and DevOps items before the build opens

- Staging and prod `chunk_embedding` row counts (`select count(*)`), for the backfill sizing
  (rubric 19). Owner or DevOps, read-only.
- The account's Lambda concurrency and memory quotas in eu-west-2 (Service Quotas console).
- Whether staging's `DATABASE_URL` user can run `CREATE EXTENSION` (the master user can; a
  restricted user cannot).
- The quota case's state (G4), for the Phase 6 reading.

## Phases

Each phase ends in a commit on `task/057-queued-ingest`. Every `lead` mark carries its reason.

### Phase 0 — Build-open, measurement tools, dev image (P6, P12, part of P1)

0. `make verify` on the branch as it stands; record counts and time. — **lead inline**.
1. `docker-compose.yml` to `pgvector/pgvector:pg17`; `tests/conftest.py` creates the
   extension per worker database; `make setup` and the suite pass on the new image; the
   `verify.yml` comment updated. — **fast-worker** (exact edits; done is a green suite on the
   new image).
2. `scripts/stage_walls.py` from `experiments/latency-anatomy-2026-11-02/40_anatomy.py`:
   per-stage wall per session from `event_log`; `scripts/step_timeouts.py` from the Langfuse
   fetch pattern in `experiments/experiments-057-2026-11-02/e2-stream-watchdog/fetch.py`:
   per step, first-attempt successes, n, p99, proposed `timeout_s`. — **deep-reasoner** (one
   concern each; done is the two scripts with a saved-fixture test).
3. Baseline reading: `stage_walls.py` on the twelve 2026-11-02 sessions reproduces the
   anatomy's Table 2 medians (the "before"); `step_timeouts.py` on the last 20 runs prints the
   per-step table; both into `verification.md`. — **lead** (reads the numbers; owner-facing).

**Gate:** full `make verify` (gate 2).

### Phase 1 — Timeouts, widths, judge effort, image, matcher (N10, N13, N14, N15, D12, D14, D15)

1. P1 plumbing: `Step.timeout_s`, `Route.timeout_for`, `resolve_openai_client(step=…)`,
   `max_retries=0`, `call_with_one_retry`, the `attempt` field on generations; a test pins
   that every step in the route file has a `timeout_s` or is listed as exempt (streamed), and
   that every client builder passes its step. — **deep-reasoner** (the seam is designed here
   in P1; the implementation has a machine-checkable done).
4. The sweep: every client builder in the 58-site inventory passes `step=` and drops its
   literal `timeout=` and `max_retries=`; code-only re-pins recorded with diffs. —
   **fast-worker** (mechanical, from the inventory).
5. Route file: `timeout_s` per step from Phase 0's table under `[routes.bedrock.steps]`; steps
   with n < 100 keep today's value and are listed; `judge_grounding` effort `low` under the
   same override. — **lead inline** (a table transcribed from a saved result; owner-facing).
6. Measurement, one lever at a time, three fixed-question runs each on bedrock, `stage_walls.py`
   plus the per-step stall counts from Langfuse attempts: (a) timeouts; (b) then widths
   (`MAX_CONCURRENT_STAGE1`, `MAX_CONCURRENT_CLASSIFY` 48; the scoping question for
   `OPTION_SEARCH_WIDTH` 10, no call over 300 s confirms N10a); (c) then the judge at `low`.
   Any step whose retry was also slow is raised once and the run repeated. The owner reads one
   report after (c). — **builder** runs and tabulates; **lead** reads and decides raises.
7. Dockerfile: the `compileall` line and the `.dockerignore` fix; cold import before and
   after in a fresh container. — **fast-worker** builds; **builder** measures.
8. `quote_verify.py`: `qv_v2`, symmetric markup strip, offset map through deleted characters,
   the anchor-span test and the two-way tests. — **deep-reasoner**.

**Gate:** full `make verify` (gate 3).

### Phase 2 — Document store schema and the deploy waiter (D2, G9, G10, P5, P14)

1. `scripts/capture_retrieval_parity.py` and the saved parity fixture (P7), taken on the dev
   database before the migration. — **deep-reasoner** (reads Langfuse tool calls; done is the
   committed fixture with ids and ranks only).
2. `core/schema.py` and revision 1: the snapshot columns and backfill, the partial unique
   index, `queued` in the check, the extension, the two embedding columns, the batched
   resumable backfill, the GIN index; revision 2: the drop. Upgrade and downgrade round-trip
   test; a test that a half-done backfill resumes. — **deep-reasoner**.
3. `embed_pending_chunks` writes the binary column and `tokens`; `validate_vector` stays;
   the JSONB write path is removed after revision 2. — **deep-reasoner**.
4. `scripts/deploy.sh` `run_migrations` polling loop (P14) with a test in `infra` or a shell
   check. — **fast-worker**.
5. Migration timing on the dev database recorded; the staging dry run and row counts are the
   owner's or DevOps's and go into `verification.md` when available. — **lead** (owner-facing).

**Gate:** full `make verify` (gate 4).

### Phase 3 — Retrieval in SQL (N8, D7)

1. The synthetic corpus and the two-retriever test (P7). — **deep-reasoner**.
2. `ChunkRetriever.search` as one SQL statement over the frozen snapshot-id list, returning
   up to 50 candidates with factor columns; Python keeps the reranker seam, cut, budget,
   dedup, windowing and provenance (factors for returned candidates). `build_retrieval_scope`
   stops loading units and vectors; `RETRIEVAL_UNIT_CAP` and `RetrievalUnitCapError` deleted;
   `api/chat_scope.py` switched (multi-scope through the snapshot list). The parity fixture
   test passes; the synthetic test passes against the SQL retriever alone after the Python
   path is deleted. — **deep-reasoner** (one concern with a machine-verifiable done: the two
   parity tests).
3. Query latency on the dev corpus recorded (under 100 ms). — **builder**.
4. Three fixed-question runs; `stage_walls.py`; the owner's content read of one report. —
   **builder** runs; **lead** reads.

**Gate:** full `make verify` (gate 5).

### Phase 4a — Per-document function, store key, markup rule, in-process mode (N6, N7, N9, D3, D8, P8)

1. Parse profile v2: the markup rule in `_segment_markdown_pages` and the JATS and HTML
   paths; new profile and policy names; the digest test re-pinned on the fixture corpus; the
   E6 control-PDF metrics reproduced in a test on the fixture PDFs (markup-bearing chunks 0,
   headings and tables unchanged). — **deep-reasoner**.
2. `ingest_document` (P8) with the store lookup before parsing, the short write transaction,
   the guarded link update, Retry-After in `fetch_live.py`; breadcrumbs (`ingested_by_run_id`,
   `envelope_source_snapshot_id`, `fetched_from`) move to the link row; the JSON-key test on
   the shared row; the two-connection race tests (same store key; same link row). —
   **deep-reasoner**.
3. In-process mode on the per-document function with per-thread connections; the scheduler,
   drain and fetch pool deleted; statuses and reasons identical across modes on the fixture
   corpus; the connection-count test. — **deep-reasoner**.
4. Stage embedding per completed document in in-process mode through the adaptive pool
   (P11), `snapshot_ids=` on `embed_pending_chunks`, the fake-throttling convergence test. —
   **deep-reasoner**.

**Gate:** `make verify-fast`.

### Phase 4b — Queued stage, queue client, handler (N1 to N5, D1, D4, D5, P9, P10)

1. `ingest_mode` setting and plumbing through `RunnerBackends`; `QueueClient` protocol, the
   SQS client and the fake; the message schema test (no user id). — **deep-reasoner**.
2. The queued stage (P9): its own transaction for re-queue, flip and send; the poll with ticks
   (`fetched=None`); the deadline with `not_ready`; `already_in_store` in the stored counts and
   not in the SSE summary; the real-second-connection test; the three fake-queue scenarios. —
   **deep-reasoner**.
3. The handler (P10) with the remaining-time guard and `batchItemFailures`; handler tests
   with a fake event and the test database; `awslambdaric` in the main dependency group
   (`uv lock`, `make audit`). — **deep-reasoner**.
4. Fixed-question runs in `in_process` mode after 4a and 4b (the laptop cannot run `queued`);
   `stage_walls.py`; the markup-cause check on quote failures; the owner's content read of one
   report. — **builder** runs; **lead** reads.

**Gate:** full `make verify` (gate 6).

### Phase 5 — Infra, config, documents (N11, N12, P13, P15, S1 to S5)

1. CDK constructs (P13), `pa_config.json`, infra tests pinning every value in N4, N5 and N11;
   `cdk diff` saved for the owner. — **deep-reasoner** (new constructs with pinned tests).
2. The data-flow note, the retention rule and its script (`scripts/prune_unlinked_snapshots.py`
   with the locking rule, not scheduled), `deferred.md` entries, two knowledge concepts, S1 to
   S5 with the spec-log line, `infra/DEPLOYMENT.md` additions (the dead-letter drain, the
   waiter, `ingest_mode`). — **lead** (spec text and owner-facing documents).

**Gate:** `make verify-fast`.

### Phase 6 — Staging deploy and measurement (D9, N12)

1. Deploy the branch to staging with `make deploy-update DEPLOY_ENV=staging` (owner or DevOps
   runs it with their credentials; the lead cannot). Record the migration time from the
   waiter's output and the quota in force. — **owner or DevOps**.
2. Three fixed-question runs on staging in `queued` mode through the API; `stage_walls.py`
   against staging's `event_log` through the jumpbox, or from the SSE event export; the
   function's logs for the ingest split and the dead-letter depth; the embedding requests,
   tokens and sleeps. — **lead** (live evidence on the owner's environment).
3. If staging cannot be deployed from the branch before review, Phase 6 becomes an owner item
   after merge, as task 056's N8 was, and `verification.md` says so.

### Step-6 exit — lead

`make verify` and `make audit` green; `verification.md` complete with every table read from
saved results, the re-pin diffs, the `cdk diff`, and anything reverted; the knowledge notes
and `deferred.md` committed. **Stop.** The review runs in a fresh conversation.

## Executor summary

- **lead** — the P1 seam design, the route-file table, every live run and owner read, the
  spec amendments and owner-facing documents, inline one-line edits, raises of too-tight
  timeouts.
- **deep-reasoner** — the timeout plumbing and traced retry, the measurement scripts, the
  parity fixture and synthetic corpus, the migrations and the binary write path, the SQL
  retriever, the markup rule, the per-document function and its races, the in-process mode,
  the adaptive pool, the queued stage, the queue client, the handler, the CDK constructs.
- **fast-worker** — the compose and conftest change, the 58-site client sweep, the Dockerfile
  and dockerignore lines, the deploy waiter loop.
- **builder** — cold-import timing, query latency, every fixed-question run and its tables.
- **owner or DevOps** — the pre-build items above, the staging deploy, the quota case.

## Out of this slice

Everything in contract D10 and § Out of scope; the prod route flip; the header, page-number
and footnote parse rules; the low-effort judge's labelled-set check and per-claim judge
filtering (synthesis refinement); the fallback parser; per-host coordination across functions.
