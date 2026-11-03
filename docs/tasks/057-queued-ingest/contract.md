# Task contract: 057-queued-ingest

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status:** approved, revision 2. Drafted 2026-11-02; revision 2 on 2026-11-03.
> **Contract approved (before planning): 2026-11-03 · Shabeer Rauf (owner).** Contract-stage
> adversarial review: _running_ (findings folded as revision 3 if material). Plan approved
> (before implementation): _pending_ · ADR: _pending (step 4)_ · Branch: `task/057-queued-ingest`.
>
> Revision 1 encoded the owner's 15 rulings on the decision sheet of 2026-11-02 (file
> `docs/research-and-development/synthesis-refinement/latency-slice-decision-sheet.md`,
> gitignored; cited as "sheet item n"). Revision 2 folds in six research notes and nine
> experiments (E1 to E10, E7 cancelled; `experiments/experiments-057-2026-11-02/README.md`)
> and the owner's triage of 2026-11-03 (§ Owner rulings). Items 2 and 3 of the sheet change
> the shape the DevOps colleague saw on 2026-10-30; their agreement is recorded at the
> contract gate (G1).

## Goal

Cut the wall time of an Evidence search run on the `bedrock` route, the app's default route,
by taking the one stage the web server cannot make fast, reading the full texts, out of the
web server, and by removing the stall tax on every model call. Functions fetch, parse and
embed each document and load it into a shared document store; the run reads the store. The
same slice moves chunk retrieval into Postgres, strips markup from parsed text, and takes
measured width levers. Reports are not meant to change in content; retrieval ships at parity
with today's ranking; the grounding judge is untouched.

Measured baseline (2026-11-02, 12 Evidence search runs on the dev laptop after task 056,
every run overlapping another; `experiments/latency-anatomy-2026-11-02/report.md`, folder
gitignored):

| Stage | Median wall | Share | What binds it |
|---|---|---|---|
| ingest_full_text, bedrock route (10 runs) | 729 s | 41% | fetch and parse 281 s, then 457 s of embedding: the account's token quota plus the JSONB vector writes |
| synthesise | 519 s (bedrock) | 29% | serial model calls; 1 to 5 stalled calls per run each wait the 120 s client timeout (132 to 630 s per run, 37 to 70% of the stage) |
| every other stage together | about 540 s | 30% | provider latency inside fixed thread pools; the same stalls |
| whole run | 1,786 s | | |

Scoping: a full walk took 1,009 s; the option-search fan-out 357 s (10 children of about
144 s through a pool of width 4).

Expected after this slice, on bedrock, a 100-document run: reading stage about 2 min (about
1 min of it embedding once the quota raise lands), report writing about 4.5 min, whole run
about 14 to 15 min from about 30. Estimates from the experiments; the fixed questions decide.

## Why this is safe to do now

- The parser is a pure function (`parse_and_segment(body, content_type, thin_min)`), and
  every write it leads to goes through four tables with content-based identity already
  (`source_snapshot.content_hash`). A function can run the same code on the same rows.
- The data-model spec already says acquired snapshots are a shared, content-addressed,
  cross-task substrate and that no original bytes are retained. This slice builds what the
  spec says; it does not change the model of the data.
- The hybrid retrieval query was reproduced in SQL for 20 of 20 real section queries
  (`experiments/pgvector-hybrid-feasibility.md`), and the pinned Aurora engine (17.7) ships
  pgvector 0.8.0.
- The function was sized locally (E4): the backend image fits Lambda with a 2 MB addition,
  the worst real PDF parses in 296 MiB, and the parser is single-threaded.
- The stall remedy is the simplest one: on Bedrock the first token arrives at the end of the
  call (E2), so a per-step total timeout catches a stall as well as a streaming watchdog, with
  no new code path.
- Infra has a Lambda precedent (`database_stack.py`), a NAT instance in the private subnets,
  and a deploy script that runs migrations as a one-shot task before the service scales.
- Rollback is a configuration value: `ingest_mode = in_process` returns the stage to the web
  server with the code it runs today on laptops; timeouts and widths are constants.

## Deliverable

A pull request where:

1. `ingest_mode = queued` makes the ingest stage enqueue one message per document, and a
   Lambda function built from the backend image fetches, parses, writes and embeds that
   document into the document store; the stage waits on the per-document statuses with a
   deadline and continues (N1 to N5).
2. `ingest_mode = in_process` (laptops, tests) runs the same per-document function in a
   thread pool, so one code path serves both modes (N6).
3. Parsed text carries no markup: parse profile version 2 for every route (N7).
4. Chunk retrieval is one SQL statement over a pgvector column, at parity with today's top-8
   on the saved queries; the in-memory scope load and the Python scoring are deleted (N8).
5. The document store is content-addressed by body hash, parse profile and segmentation
   policy, and a document already in the store is linked without a second parse (N9).
6. Every model call site has its own timeout in the route file, sized from its measured tail
   with the retry kept; the scoping and screen widths are raised and measured (N10).
7. New cloud resources in CDK and config: a queue, a dead-letter queue, the function, its
   role and security group, the concurrency cap, one alarm, and `ingest_mode` per
   environment (N11); compiled bytecode in the image (N13).
8. The quote matcher strips markup from the quote as well as the chunk (N14).
9. `verification.md` holds the before and after measurements on the laptop and on staging,
   the data-flow note for the DPIA addendum, and the retention rule (N12).

## Terms

| Term | Meaning |
|---|---|
| **Document store** | The four tables that hold parsed text today: `source_snapshot` (one row per parsed text, identified by content), `chunk` (the frozen passages of a snapshot), `chunk_embedding` (one row per embedding unit of a chunk) and `task_source_snapshot` (the link from a task to a snapshot, holding `full_text_status`). Owned by `core/schema.py`. No new table is added. |
| **Snapshot** | A `source_snapshot` row. An *envelope* snapshot holds a document's abstract and metadata (`text_basis = abstract_only`); a *full-text* snapshot holds its parsed full text (`text_basis = full_text`). |
| **Link row** | A `task_source_snapshot` row: this task has this document. It carries `task_id`, `origin`, `full_text_status` and `full_text_snapshot_id`. The only place a task id meets a snapshot. |
| **Body hash** | SHA-256 of the fetched bytes, before parsing. New column on `source_snapshot` (D2). Null on envelope snapshots. |
| **Content hash** | `source_snapshot.content_hash` today: a hash of the chunk texts after parsing. Unchanged; it stays the provenance identity. |
| **Parse profile** | The named, versioned parser that produced a snapshot's text, for example `pymupdf4llm_v1`. Today in the snapshot's `metadata` JSON; becomes a column (D2). Version 2 is N7. |
| **Segmentation policy** | The named, versioned rule that cut the text into chunks, for example `pymupdf4llm_struct_v1`. Today a column on `chunk` and a key in snapshot metadata; becomes a snapshot column (D2). A chunk is a whole heading section or table; nothing splits by size (E6). |
| **Embedding profile** | The named embedding model version stamped on each `chunk_embedding` row (`embedding_profile`), with the unit policy (`embedding_unit_policy_v1`: units of at most 2,000 characters with a 200-character overlap, about 435 tokens each). Cohere Embed v4 through the `eu.` profile on the bedrock route. |
| **Store key** | Body hash × parse profile × segmentation policy. Two fetches with the same key share one full-text snapshot (D3). Embeddings are per profile on top of that. |
| **Ingest mode** | A configuration value, `in_process` or `queued`, read like the model route (environment variable, set per environment by infra). |
| **Function** | The AWS Lambda function that handles one queue message: one document. Built from the backend container image with a second command, not a second image (D5). |
| **Queue** | One Amazon SQS standard queue. One message per document. A **dead-letter queue** receives a message after its second failed attempt. |
| **Stage deadline** | How long the ingest stage waits for queued documents before it marks the rest not read and the run continues. 10 minutes (D4). |
| **Function timeout** | The Lambda timeout, the per-document deadline: 3 minutes (D4). The parse step inside keeps its own 120 s kill. |
| **Embedding quota** | The account's Bedrock quota for Cohere Embed v4 through a cross-region profile, measured at 620,000 to 673,000 tokens accepted per 60 s at any concurrency (E1). A run's embedding time cannot go below its tokens divided by that rate: about 4 min for 100 documents today. The owner has asked AWS for 3,000,000 per minute (case open 2026-11-03). |
| **Stall** | A model call that returns nothing until the client timeout and then succeeds on the SDK's retry. Measured at 4% of first attempts on Bedrock (E2); every one silent to the 120 s timeout. |
| **Step timeout** | The per-step client timeout this slice adds to the route file: 2 × the step's healthy 99th-percentile total time, floor 5 s, retries kept (D12). |
| **Fixed questions** | The three Evidence search questions and one Options scoping question task 056 used (`docs/tasks/056-cost-latency/contract.md` O5), run fresh as new tasks before and after. |
| **Parity** | The SQL retriever returns the same top-8 chunks in the same order as today's Python retriever for the 20 saved section queries of the feasibility study, and for the fixed questions' section queries replayed. |
| **Decided / Leaning / Open** | Decided is settled. Leaning is the recommended choice unless the owner objects. Open means the owner chooses at the named gate. |

## Facts we rely on

Experiment folders are under `experiments/experiments-057-2026-11-02/` (gitignored).

| Fact | Source | Consequence |
|---|---|---|
| Ingest is 684 s of a 1,790 s median run; on bedrock 457 s of it is embedding in 83 serial requests of 96 units. | `latency-anatomy-2026-11-02/report.md` Tables 2 and 4 | N1 to N6. |
| Bedrock throttles Cohere Embed v4 by tokens on this account ("Too many tokens"): 620,000 to 673,000 accepted per 60 s at concurrency 1 to 16; a single stream already runs at about 700,000 per minute; latency = 0.40 s + 0.074 s per 1,000 tokens; 435 tokens per unit. One batch gave up after 4 retries at concurrency 8. | E1 `summary.json` | D6: fan-out does not speed embedding; the quota raise is the lever; the function's backoff must be patient (D13). |
| The embedding loop's own overhead is 17 to 21 s on a quiet machine and 45 to 118 s under load, almost all of it the JSONB vector INSERT (2 MB of JSON per batch, 172 MB per run, 76 MB stored). | E10 `results/tables.md` | N8's `vector(1536)` column removes most of it. |
| Live fetch took 100 to 250 s per run because the fetcher reserves 25 MB of a 100 MB budget per body, so at most 4 bodies download at once. | `fetch_live.py` constants; report Table 4 | Fetch moves into the function (sheet item 2). |
| 50 uncoordinated fetchers on one run's 117 documents: 112 succeeded; one host (ONS, behind Cloudflare) sent 8 × 429 and 4 documents failed because the retry waits a fixed 2 s while Retry-After asked 7 to 10 s; no 403s; other hosts took bursts of 11 to 14 in one second. | E5 `report.md` | N2 honours Retry-After; per-host coordination deferred (D11). |
| Backend image 164 MB compressed, 532 MB unpacked; the Lambda runtime client adds 2 MB. Peak parse memory 296 MiB on amd64 over 50 real PDFs; the parser is single-threaded; worst parse 67 s on one full core. The image ships no compiled bytecode: cold import 6 to 8 s, 2 to 4 s compiled. No disk used. | E4 results files | D5: 1,769 MB (one core), 512 MB disk; N13. |
| Lambda: 15 min timeout, up to 10 GB memory, 10 GB image, per-queue concurrency 2 to 1,000; London $0.0000167 per GB-second. | `experiments/aws-limits-2026-11-02.md` | D4, D5, N11. |
| A Lambda in the private subnets reaches Aurora by the VPC local route and the internet through the fck-nat instance. | `infra/infra/network_stack.py` | No bucket, no new endpoints (D5). |
| `full_text_status` is checked to `not_attempted`, `ingested`, `fetch_failed`, `parse_failed`; `ingested` ⟺ snapshot id set; failed ⟺ error set. `source_snapshot` has no task id. | `core/schema.py` | D2 adds `queued`; the shared row already carries no task or user id. |
| `chunk_embedding.vector` is JSONB; retrieval loads every unit of the scope into memory (cap 20,000), scores cosine and word overlap in Python, fuses with RRF k = 60. One SQL statement reproduces today's top-8 for 20 of 20 queries at 30 to 47 ms. | `synthesis_tools.py`; `pgvector-hybrid-feasibility.md` | N8 at parity; no HNSW. |
| The synthesise stage is 97 to 99% inside serial model calls. Every synthesis call site shares one client at 120 s with two retries; the grounding judge has the same. Stalls: 4% of first attempts (8 of 200), silent to the timeout; also seen in classify at the 60 s timeout. Healthy p99 total: judge_summary 1.9 s, grounding 13.6 s, section_turn 11.3 s, key findings 8.7 s. On Bedrock the first token arrives at 71 to 97% of total time; no reasoning streams; the sync client cannot cancel an abandoned request. | `synth_breakdown.py`; E2 `summary.json`; E8 | D12, N10c. |
| Splitting the grounding judge into parallel claim batches saves no time (reasoning tokens per call do not shrink), costs 1.5 to 2×, doubles unspanned-prose flags. Low effort halves the judge's time at 0.8× cost with agreement at the judge's own noise floor (91.7%; 8% of claims flip run to run) but marked 26 claims unsupported against 33 and 28, missing 3 real catches in 157. | E3 `tables.md` | Judge untouched (D14). |
| Deterministic quote, number and negation checks catch 8 of 26 unsupported claims with 82 false flags; skipping whole judge calls saves 8% of tokens. | E9 `results.json` | No two-stage judge (D14). |
| Screen stage 1 at width 48: set wall 14.4 → 4.8 s; classify 7.9 → 4.5 s; zero 429s up to 48; per-call latency flat; Bedrock returns no rate-limit headers on success. | E8 `summary.json` | N10d. |
| On today's writer (gpt-6.1-terra) 0.7% of PDF quotes fail the quote match; on the old writer 12.1% (it copied markup). Parse profile v2's markup rule recovers every markup failure and clears 186 markup-bearing chunks to 0 on 10 control PDFs with tables and heading paths unchanged; header, page-number and footnote rules add 5 quotes of 941 and only work together. v2 output is byte-identical across runs. | E6 `results/report.md` | N7 is the markup rule only (owner); N14. |
| The scoping client has a 60 s timeout with two retries; the 901 to 903 s single calls in two walks are therefore not one timeout. | `scoping_backend.py:479`; report Table 7 | N10a locates them at plan time. |
| The parser already runs each document in its own process with a 120 s kill; tests pin byte-identical output across worker counts and deny every socket inside the worker. | `ingest_full_text.py`; `test_ingest_full_text.py` | D5; the digest test moves to profile v2. |
| The backend image has no entrypoint; its command is uvicorn. Infra builds it once and reuses it for the migration task. | `backend/Dockerfile`; `policy_atlas_stack.py` | D5, N13. |
| The route file names the embedding backend, model and profile per route; `embed_pending_chunks` already treats chunks under another profile as pending. | `core/model_routes.py`, `core/embeddings.py` | D3. |

## Read first

- `docs/research-and-development/synthesis-refinement/queued-parsing-task-seed.md`,
  `latency-slice-decision-sheet.md`, `experiments/experiments-057-2026-11-02/README.md`,
  `experiments/llm-latency-research-2026-11-02/` and the two measurement folders named
  above (all gitignored).
- [system/data-model.md](../../specs/system/data-model.md) § Corpus & source snapshots: the
  shared content-addressed substrate, "no original bytes retained", "one parse, one
  segmentation per snapshot", a parser upgrade applies to newly ingested snapshots only.
- [capabilities/evidence-search/components.md](../../specs/capabilities/evidence-search/components.md)
  § 4 full-text ingestion (fetch → parse → segment → embed for the whole screened-in set;
  flag-not-drop; the access-failure vocabulary; eager uniform vectorisation at unit grain).
- [system/execution-orchestration.md](../../specs/system/execution-orchestration.md)
  § Durability & concurrency (serial components, within-step fan-out retained).
- [system/provenance-grounding.md](../../specs/system/provenance-grounding.md) § quote
  presence (normalised string match over frozen chunks).
- [system/web-api.md](../../specs/system/web-api.md) § SSE, the `ingest` stage and its tick
  counts (task 056 S5); unchanged by this slice.
- [deferred.md](../../deferred.md) § Cost and latency (task 056 seams), § System-level cost
  and latency, the document-identity entry.
- [ADR 0042](../../adr/0042-gpt6-switch-per-call-site-routing-and-caching.md) for the route
  file pattern that `ingest_mode` and the step timeouts follow; the owner's rule "one route
  step per call site" (2026-10-29).
- `infra/DEPLOYMENT.md` § the deploy sequence (stop → migrate → scale) and the rollback notes.
- Code: `evidence_search/sourcing/ingest_full_text.py`, `fetch_live.py`, `parse_jats.py`,
  `core/embeddings.py`, `core/schema.py`, `core/openai_client.py`, `core/model_routes.py`,
  `model_routes.toml`, `evidence_search/synthesis/synthesis_tools.py`
  (`build_retrieval_scope`, `ChunkRetriever`), `synthesis_backend.py`, `grounding_judge.py`,
  `quote_verify.py`, `api/chat_scope.py`, `runtime/harness.py` (`_run_ingest_full_text`),
  `runtime/scoping_plan.py` (`OPTION_SEARCH_WIDTH`), `options_scoping/scoping_backend.py`,
  `evidence_search/assess/screen.py` and `classify.py` (pool widths),
  `infra/infra/policy_atlas_stack.py`, `infra/infra/network_stack.py`, `infra/pa_config.json`,
  `backend/Dockerfile`, `scripts/deploy.sh`.

## Numbered needs

| # | Need | Where it lives today | Measure |
|---|---|---|---|
| N1 | One message per eligible document on the queue, carrying the link row id, the candidate URLs, the PubMed Central id if any, the open-access flag, and the run id. No user identifier. | `ingest_full_text_sources` builds the eligible set in one query and fetches in threads. | A test asserts the message shape and that no field is a user id; a live run shows one message per attempted document. |
| N2 | The function handles one message: fetch (same rules as today: scheme, private-IP refusal, redirect cap, byte cap, paywall and bot-block vocabulary; plus: a 429 or 503 with Retry-After waits that long, capped at 30 s, and a document still refused goes back to the queue with a delay instead of failing), parse in a subprocess with the 120 s kill, write the snapshot and chunks, embed the units, set the link row to `ingested` or to a failed status with the same reason codes as today. Idempotent: a link row already `ingested` returns at once. | fetch in `fetch_live.py` (fixed 2 s retry); parse and writes in `ingest_full_text.py`; embed in `core/embeddings.py`. | Unit tests on the handler with a fake event and a test database; the committed fixture corpus produces the same statuses and reasons as the in-process path; a test with a fake 429 and Retry-After. |
| N3 | The stage in queued mode: set the eligible rows to `queued`, send the messages, poll the statuses, publish progress ticks from the counts, stop at the stage deadline, mark the rows still `queued` as `fetch_failed` with reason `deadline`, return the same counts dict as today plus `already_in_store`. | `ingest_full_text_sources`; `_IngestProgress`. | A test with a fake queue and a fake clock covers: all done early, some late, deadline hit. The counts invariant holds (eligible = ingested + already ingested + fetch failed + parse failed). |
| N4 | Deadlines and sizing: function timeout 180 s, memory 1,769 MB, ephemeral storage 512 MB, stage deadline 600 s, SQS visibility timeout at least 6 × the function timeout, dead-letter after the second attempt, a CloudWatch alarm on the dead-letter queue depth. | none | CDK test pins the values; the alarm exists in the synthesised template. |
| N5 | Concurrency cap on the event-source mapping (Leaning: 50), so the function never opens more database connections than the writer instance allows with the API's pool. | none | CDK test pins the cap; the plan records the writer instance's `max_connections` and the arithmetic. |
| N6 | One code path: a per-document function `ingest_document(conn, link_row, …)` called by the Lambda handler and, in `in_process` mode, by a thread pool of the parse worker count. The N8 scheduler and the batch hand-over are deleted. | `_ParseScheduler`, `_run_parse_jobs`, `_drain_*`, the fetch thread pool. | Byte-identical chunk digest on the committed fixture corpus between worker counts 1 and 4 (the existing test, re-pinned to profile v2); statuses and reasons identical between the two modes on the fixture corpus. |
| N7 | Parse profile v2 for PDF, HTML, JATS and plain routes: markdown and HTML markup removed from chunk text at segmentation, with headings kept in the locator. New profile and policy names; old snapshots untouched. The header, page-number and footnote rules are **not** built (owner, 2026-11-03). | `_parse_pdf`, `_parse_html`, `_segment_markdown_pages`, `parse_jats.py`. | On the 10 control PDFs of E6: markup-bearing chunks 186 → 0, tables and heading paths unchanged; the citation-funnel re-run on the fixed questions holds the PDF quote failure rate at or below today's 0.7% on the current writer; v2 byte-identical across runs. |
| N8 | Retrieval in SQL: a `vector(1536)` column and a `tokens text[]` column with a GIN index on `chunk_embedding`, backfilled from the JSONB vectors and the chunk text; `ChunkRetriever.search` runs one statement that returns the fused candidate list (up to 50 rows with their prior factors); Python keeps query embedding, the reranker seam, the cut to 8, the character budget, dedup, windowing and provenance. `build_retrieval_scope` no longer loads units or vectors; the 20,000-unit cap and `RetrievalUnitCapError` are deleted. Both callers (synthesis, chat) switch. | `synthesis_tools.py`, `api/chat_scope.py`. | Parity on the 20 saved queries and on the fixed questions' replayed section queries; retrieval provenance records the factors for the returned candidates; a query under 100 ms on the dev corpus; the embedding write per batch measured before and after (E10's 17 to 45 s per run). |
| N9 | Content-addressed reuse: the function hashes the body, looks up the store key, links an existing full-text snapshot instead of parsing again, and embeds only the units missing for the current embedding profile. The shared row carries no task or user id. | `source_snapshot` insert at every ingest; no body hash. | A test ingests the same bytes for two tasks and asserts one snapshot, two link rows; a test with a different embedding profile asserts a second set of embedding rows and no second parse. Live: a second run on an overlapping question shows `already_in_store` in the counts. |
| N10 | Timeout and width levers, each measured: (a) the cause of the 900 s scoping calls located and fixed (the scoping client is already 60 s × 3 attempts, so it is elsewhere); (b) `OPTION_SEARCH_WIDTH` 4 → 10; (c) **step timeouts for every model call site in the repo** (D12): a `timeout_s` value per step in `model_routes.toml`, set to 2 × that step's healthy p99 total from the last 20 runs' traces, floor 5 s, SDK retries kept at 2; the long-output steps keep their 120 s only if their own p99 says so; (d) pool widths: screen stage 1 and classify 12 → 48; screen stage 2 and extract unchanged unless measured. | `scoping_backend.py`; `scoping_plan.py`; `synthesis_backend.py:721`, `grounding_judge.py:332` and every other client the 056 inventory lists (58 sites); `screen.py`, `classify.py`. | Scoping: the fixed question before and after, fan-out wall, no new 429s, no calls over 300 s. Timeouts: on the fixed questions, per step, calls that hit the timeout and then succeeded (stalls caught) and calls that hit it and were slow on retry too (set too tight; raise that step); synthesise wall before and after; owner's read finds the reports unchanged. Widths: screen and classify stage walls before and after, 429 count. |
| N11 | Infra: queue, dead-letter queue, function (image = the backend asset, command = the handler, 1,769 MB, timeout 180 s, private subnets, security group with Aurora ingress, the app secret and route variables), event-source mapping with the cap, alarm, `ingest_mode` in `pa_config.json` per environment and in the API task's environment. CDK tests. | `policy_atlas_stack.py`, `pa_config.json`. | `make -C infra test` green; `cdk diff` reviewed at the plan gate; staging deploy succeeds. |
| N12 | Measurement and governance: the fixed questions before and after on the laptop (`in_process`, bedrock) and on staging (`queued`, bedrock), the ingest split (fetch, parse, embed) and the embedding requests, tokens and throttling sleeps from logs, the quota's state, a one-page data-flow note, the retention rule. | none | In `verification.md`; the data-flow note committed under `docs/`. |
| N13 | Compiled bytecode in the backend image (`python -m compileall` of the venv and `src` in the Dockerfile), so a cold function or API task does not recompile 6,500 files. | `backend/Dockerfile` ships no `.pyc`. | Cold import of the parser stack in a fresh container before and after (E4: 7.7 → 3.8 s on amd64). |
| N14 | The quote matcher normalises markup out of the quote as well as the chunk, so quotes that copied `**` or `_` from old snapshots keep matching. | `quote_verify._normalise`. | A test with a markup-bearing quote against a plain chunk and the reverse; the funnel re-run on the fixed questions. |
| N15 | The grounding judge's route step runs at `low` reasoning effort (D14). | `model_routes.toml` `[steps]` judge_grounding effort `medium`. | Judge wall per call and per run before and after on the fixed questions; the count of claims marked unsupported per report against the medium baseline's spread (26 vs 28 to 33 per 157 claims in E3); the owner's read of the reports. |

## Decisions

**D1. The shape. Decided (owner, sheet items 1 to 5).** One message per document; one
function invocation per message; the function fetches, parses, writes and embeds; the run
polls the store. Fetch in the function removes the S3 bucket, the upload step and the
4-bodies-at-once ceiling, and the function never keeps bytes after parsing.

**D2. Schema. Decided at this contract (gate G2).** One migration:
- `source_snapshot`: new nullable columns `body_hash` (text), `parse_profile` (text),
  `segmentation_policy` (text); backfilled from `metadata` for existing full-text snapshots
  (`body_hash` stays null for them: their bytes are gone, so they are never reused by key);
  a unique partial index on `(body_hash, parse_profile, segmentation_policy)` where
  `body_hash` is not null.
- `task_source_snapshot`: `queued` added to `ck_tss_full_text_status`; the consistency
  checks unchanged (`queued` has no snapshot id and no error).
- `chunk_embedding`: `CREATE EXTENSION IF NOT EXISTS vector`; new `embedding vector(1536)`
  and `tokens text[]` columns, backfilled in batches inside the migration from the JSONB
  `vector` and the unit's text; a GIN index on `tokens`. The JSONB `vector` column is
  **dropped in the same migration** (Decided, owner 2026-11-03: "We can drop it"; the
  downgrade rebuilds it from the vector column).
- Downgrade path written and tested on the dev database.
Backfill size: 130,614 units took 367 s locally; staging holds fewer. The deploy script
already waits for the migration task without a timeout of its own.

**D3. Store key and reuse. Decided (owner, sheet item 8: reuse on, no switch).** The key is
body hash × parse profile × segmentation policy. On a hit the function links the existing
snapshot and embeds only what the current embedding profile lacks. The shared row never
carries a task or user id (it has none today; a test guards the columns). Reuse applies to
`origin = acquired` rows only; there is no upload path in the product (sheet item 12).
Old-profile snapshots are not matched by key, so every document is parsed once more under
profile v2 the first time it is seen again. Retention rule (Leaning): a full-text snapshot
with no link row is deleted by a documented script after 90 days; no scheduler in this slice.

**D4. Deadlines. Decided (owner, sheet item 5).** Function timeout 180 s; stage deadline
600 s from the first message sent; rows still `queued` at the deadline become `fetch_failed`
with reason `deadline`, so they are retried on the next run like any fetch failure. A function
that finishes after the deadline still writes `ingested`; the current run has moved on and the
next run finds the document already ingested. Dead-letter after 2 attempts; SQS visibility
timeout at least 6 × the function timeout (research note). The in-process mode keeps the
120 s parse kill and has no stage deadline, as today.

**D5. Packaging, sizing and network. Decided (owner, sheet item 15; sized by E4).** The
function is the backend image asset with the command
`python -m awslambdaric policy_atlas.ops.ingest_worker.handler` (the Runtime Interface Client
is a new dependency in the `ops` group: gate G3). Memory **1,769 MB**: Lambda scales CPU with
memory and gives one full core at that size; the parser is single-threaded and the worst real
PDF needs 296 MiB and 67 s on a full core (at 444 MB it would take about 4.5 min). Ephemeral
storage 512 MB (the parser reads from memory). It runs in the private subnets, reaches Aurora
by the local route, and reaches publishers, SQS and the embedding provider through the fck-nat
instance. No S3, no VPC endpoints. The parse step runs in a subprocess inside the function
with the same kill and the same socket denial as the tests require today; the handler process
itself needs the network. Cost for 100 documents at this size: about one to two cents.

**D6. Embedding. Decided (owner, sheet item 4), floor measured by E1.** Per document, inside
the function, with the backoff that exists, made patient (D13). Bedrock throttles Cohere
Embed v4 by tokens on this account: about 620,000 to 673,000 per minute at any concurrency,
which a single serial stream already reaches. Fan-out therefore neither speeds nor hurts
embedding; the stage's embedding time is tokens ÷ quota, about 4 min for 100 documents today.
The owner has requested a raise to 3,000,000 per minute (G4); at that quota embedding is about
1 min. The JSONB write overhead (E10) goes with N8's binary column. Switching embedding model
is out: every London model has a token quota and a switch re-embeds every stored chunk.

**D7. Retrieval parity. Decided (owner, sheet item 7).** The SQL leg for words uses the
product's own score (share of query words found in the unit), not Postgres full-text ranking,
so the top-8 is reproduced exactly. The ranking choice stays with the synthesis refinement
task. No HNSW index.

**D8. Parse profile v2 is the markup rule only. Decided (owner, 2026-11-03, after E6).** The
quote failures that motivated v2 were mostly the old writer copying markup; on the current
writer the v1 failure rate is 0.7%. The markup rule still earns its place: it clears every
markup-bearing chunk (186 → 0 on the controls) with structure unchanged, which cleans the text
the embeddings and the writer see. The header, page-number and footnote rules add 5 quotes of
941 and only work together: dropped, recorded in `deferred.md` with E6's measurements. New
profile and policy names; existing snapshots and citations untouched (spec rule). The
fallback parser (Textract or Bedrock Data Automation) stays deferred.

**D9. Measurement. Decided; bedrock only.** `bedrock` is the app's default route from now on
and `openai-direct` is legacy (owner, 2026-11-02). Before: the 2026-11-02 anatomy (bedrock
rows). After, on the laptop: the three fixed Evidence search questions in `in_process` mode,
which measures N6 to N8, N10c and N10d; on staging: the same three in `queued` mode, which
measures N1 to N5, with the ingest split and the embedding requests, tokens and sleeps read
from the function's logs. The fixed scoping question before and after N10a and N10b. The owner
reads one report after N7 and one after N8 for a content check. `openai-direct` keeps working
but is not measured.

**D10. Out of scope, named.** Parallel report sections (owner: coherence). Splitting or
re-tiering the grounding judge (D14). The streaming watchdog and hedged requests (E2: no
benefit over step timeouts on Bedrock). A two-stage or deterministic judge (E9). Per-host
coordination across functions (D11). A rate-limit-aware limiter (Bedrock sends no headers).
Per-document hand-over into full-text screening (that stage is 35 s). Paid provider tiers
(owner, 2026-11-02). Graviton (sheet item 11; E4 noted arm64 imports 30% faster). Uploaded
documents (sheet item 12). The fallback parser. HNSW. Moving runs out of the API process.
The acquire-stage embedding of abstracts (about 4 requests per run). Any prompt text.

**D11. Known limits accepted.** With 50 functions in flight the per-host limit (2 at once,
1 s apart) is not coordinated across functions. E5 saw one host answer 429; N2's Retry-After
handling and queue redelivery cover it. If 429s rise on staging, the lever is a per-host FIFO
message group in a later slice. Lambda cold starts (2 to 4 s with compiled bytecode) are
inside the stage deadline.

**D12. Stalls are removed by step timeouts in the route file. Decided (owner, 2026-11-03;
method chosen from E2).** Every model call site gets `timeout_s` in its `[steps]` entry,
following the one-route-step-per-call-site rule, set to **2 × the step's healthy p99 total**
from the last 20 runs' traces, floor 5 s, with the SDK's 2 retries kept. The owner asked for
"a bit more aggressive" than 3 × p99; 2 × p99 is the choice, and the after-measurement names
any step whose retry was also slow, which is the signal to raise that step. A streaming
watchdog adds nothing on Bedrock (first token at 71 to 97% of total, E2) and hedging bills
twice. Section order and the ledger are untouched. The Bedrock embedding client's botocore
`read_timeout` and retry mode are set explicitly too.

**D13. The function's embedding backoff is patient. Decided (from E1).** Under the shared
token quota, 50 functions embedding at once will be throttled as a burst until the raise
lands. The function's backoff rises to a cap of 60 s and continues until the function timeout
rather than giving up after 4 attempts (E1 saw a batch fail that way); a document whose
embedding does not finish is `parse_failed` with reason `embed_timeout`, retried next run, and
never left with chunks but no vectors.

**D14. The grounding judge runs at `low` reasoning effort; its prompt, batching and place in
the loop are untouched. Decided (owner, 2026-11-03).** Splitting saves nothing (E3). Low
effort halves the judge's time (11.5 → 5.4 s per call, 70 to 120 s per run) at 0.8× its cost,
with agreement to the medium judge at the judge's own noise floor (91.7%), while marking 26
claims unsupported against 33 and 28 for two medium runs and missing 3 attribution catches in
157 claims (E3). The owner takes that trade in this slice as a route-file value for the
`judge_grounding` step only (one route step per call site), guarded by the owner's read of the
fixed-question reports, and asks the synthesis refinement task to revisit it with a labelled
set of disputed claims and raise it again if the leniency is real. Recorded in `deferred.md`
with E3's numbers. No prompt text changes.

## Owner rulings

**2026-11-02.** Sheet items 1 to 15: 1 yes; 2 yes; 3 yes; 4 yes; 5 yes; 6 yes; 7 yes, and the
in-app hybrid search is removed; 8 reuse on, no switch; 9 ok; 10 report writing out;
11 Graviton out; 12 uploads out ("the app doesn't have that yet"); 13 yes; 14 ok, "ideally
we'd get it as low as possible"; 15 yes. Later the same day: per-step synthesis timeouts in;
parallel section writing out for coherence; `bedrock` is the default route going forward,
`openai-direct` legacy; no Bedrock Priority or fast tiers ("small costs" such as Lambda are
fine); the embedding quota raise filed (3,000,000 tokens per minute, Global cross-region row,
case open).

**2026-11-03 triage of the experiments.** Act on all of: step timeouts (more aggressive than
3 × p99, for every LLM call site in the repo), queued per-document ingest, the quota raise,
pgvector and SQL retrieval, 1,769 MB functions, Retry-After, compiled bytecode, the quote-side
markup strip. Act on the leans: pool widths 12 → 48 measured; option-search width 4 → 10
measured; parse v2 markup rule only. Drop: the header, page-number and footnote rules; judge
splitting; two-stage and deterministic judge; streaming watchdog; hedging; per-host
coordination; rate-limit limiter; per-document hand-over into full-text screening. Low-effort
judge: "Let's drop it to low in this task, but revisit in synthesis refinement to potentially
increase again in that task" (D14).

**2026-11-03, the four contract-gate items.** G1: "It's fine". S1 to S5: "They're fine". D2's
JSON column: "We can drop it". The `prod` route flip to `bedrock`: a separate change, "when
we're ready to move from staging to prod, after some internal testing by the team"; out of
this slice, noted in `deferred.md`.

## Spec items (accepted by the owner 2026-11-03: "They're fine"; applied in the build with a line in the spec log)

- **S1.** data-model § Corpus & source snapshots: record the substrate key as built (body
  hash × parse profile × segmentation policy, embeddings per profile on top), `body_hash` as
  the pre-parse identity, and that reuse is on for acquired snapshots with the retention rule.
- **S2.** components § 4: ingestion runs as a queued job outside the web server in the cloud
  (`ingest_mode`); the stage waits with a deadline; documents past the deadline are
  `fetch_failed` with reason `deadline`.
- **S3.** execution-orchestration § Durability & concurrency: the first component whose work
  runs outside the API process; the component boundary is still the checkpoint; the store is
  the hand-over.
- **S4.** components § 9 or provenance: chunk retrieval is a SQL query over the store at
  parity; the Python scope load is gone. One sentence.
- **S5.** prompting.md § Provider-specific or ADR 0042's route-file section: each step carries
  a client timeout sized from its measured tail; stalls are retried, never waited out.

## Scope / Out of scope

- **In:** `core/schema.py` and one migration; `core/embeddings.py` (per-snapshot embedding,
  patient backoff, `tokens`, vector column writes, botocore config); `core/model_routes.py`
  and `model_routes.toml` (`timeout_s` per step); `core/openai_client.py` (reads the step
  timeout); `evidence_search/sourcing/ingest_full_text.py` (the per-document function, the
  queued and in-process stage, the markup rule), `fetch_live.py` (Retry-After), `parse_jats.py`
  (markup); a new `ops/ingest_worker.py` (handler) and a queue client module;
  `runtime/harness.py` (passes the mode); `evidence_search/synthesis/synthesis_tools.py` and
  `api/chat_scope.py` (SQL retrieval); `synthesis/quote_verify.py` (N14); every module that
  builds a model client (timeouts move to the route file); `runtime/scoping_plan.py`;
  `assess/screen.py`, `assess/classify.py` (widths); `infra/infra/policy_atlas_stack.py`,
  `infra/pa_config.json`, infra tests; `backend/pyproject.toml` (one dependency, G3);
  `backend/Dockerfile` (compiled bytecode, G8); tests beside each; `docs/deferred.md`; one ADR;
  the spec items the owner accepts; a data-flow note under `docs/`.
- **Out:** everything in D10; `scripts/deploy.sh` beyond passing the mode; the frontend
  (ticks unchanged); prompt text and prompt hashes (a code-only re-pin for a timeout line is
  recorded with its diff, 056's rule; a prompt-text change stops the slice); Langfuse; the
  search backends; other capabilities.

## Constraints & approval gates

- **G1. Egress (runtime).** The function fetches publisher URLs, calls the embedding provider
  of the route, and talks to SQS and Aurora. Same hosts and same data as today, from a new
  place. Approved at this contract by the owner (sheet item 2; 2026-11-03 on the shape change
  against the 2026-10-30 agreement: "It's fine"). The owner carries the change to the DevOps
  colleague.
- **G2. Schema.** The D2 migration, approved at this contract. Tier 4.
- **G3. Dependency.** `awslambdaric` in the `ops` group, approved at this contract. No other
  dependency; vectors are sent as text casts, not through a client library.
- **G4. Quota.** The owner filed the raise on 2026-11-03 (case open: Global cross-region
  tokens per minute for Cohere Embed V4, 3,000,000, eu-west-2). The contract does not depend
  on it being granted; the staging measurement records the quota in force.
- **G5. Production config and CDK.** The resources in N11 and `ingest_mode` per environment,
  approved at this contract; `cdk diff` reviewed at the plan gate; production stays
  `in_process` until the staging measurement is read (Leaning). The `prod` route flip to
  `bedrock` is a separate later change (owner, 2026-11-03).
- **G6. Public interface.** None. The SSE stage and tick shapes are unchanged. The counts
  dict gains `already_in_store` (internal).
- **G7. Governance.** The DPIA addendum for the changed data flow is the owner's artefact and
  gates the merge, as in task 033; the slice supplies the data-flow note (N12).
- **G8. Dockerfile.** One change: compile bytecode into the image (N13). Approved at this
  contract.
- **Tests stay offline.** The handler is tested with a fake event and the test database; the
  queue client with a fake; no AWS call in `make verify`.

## Public / private boundary

Committable: code, tests, CDK, config values, this folder's documents with numbers, the
data-flow note (it names services and data classes, not documents). Private: the fixed
questions' report text, publisher URL lists, credentials, Langfuse keys, the DPIA itself, the
experiment folders (gitignored).

## Model route

No model changes. One effort change: the `judge_grounding` step moves from `medium` to `low`
on the bedrock route (D14), measured on the fixed questions (verdict counts and the owner's
read). Every step gains a `timeout_s` in the route file. No prompt text changes; code-only re-pins for timeout lines in
pinned modules are expected and recorded with their diffs.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves.** `queued` changes what the stage waits on; `body_hash` changes
  what is parsed; the new columns on the snapshot replace JSON keys the code already reads;
  `timeout_s` changes what a stall costs.
- **Flag, don't drop.** A document past the deadline is `fetch_failed` with a reason, visible
  in the counts and retried next run; never silently absent.
- **Honest absence.** Coverage counts keep their base; `already_in_store` is its own count.
- **One code path.** The function and the in-process mode call the same per-document
  function; a behaviour that exists in one mode only is a defect.
- **Measure before and after**, one lever at a time, read from saved results; a lever whose
  after-measurement is worse is reverted and recorded.
- **Specs are the owner's.** S1 to S5 are proposals; the build applies only what is accepted.

## Stop conditions

Halt and escalate when: a gate above is hit without its approval; parity (D7) fails on any
of the 20 saved queries and the cause is not a data difference; the migration's backfill
cannot run inside the deploy's migration task on staging; the function cannot reach Aurora or
the providers from the private subnets; the markup rule changes a table or heading count on
the control PDFs; a step timeout cuts healthy calls on the fixed questions after one raise; a
prompt-text re-pin is needed; scope would grow past this slice; the turn or token budget is
spent.

## Acceptance checks

- `make verify` green at the build-open baseline, after the schema phase, after the
  retrieval phase, and at the step-6 exit; `make verify-fast` between other phases;
  `make -C infra test` with the CDK changes.
- Deterministic tests: message shape with no user id (N1); handler statuses and reasons on the
  fixture corpus, Retry-After honoured (N2); the queued stage with a fake queue and clock,
  including the deadline and the counts invariant (N3); CDK pins for timeout, memory, cap,
  visibility timeout, alarm (N4, N5); byte-identical digest across worker counts and identical
  statuses across modes (N6); the markup rule on the fixture PDFs with structure unchanged (N7);
  SQL parity on the 20 saved queries from committed fixtures, provenance factors for returned
  candidates, both callers switched (N8); one snapshot for two tasks, embeddings per profile, no
  task id on the shared row (N9); every step has a `timeout_s` and every client reads it, the
  widths (N10); migration upgrade and downgrade round-trip (D2); patient backoff and
  `embed_timeout` (D13); the compiled bytecode present in the image (N13, an image test or a
  build-time check); quote-side markup (N14).
- Manual: the fixed questions as D9 says; the owner's content read of one report after N7
  and one after N8; the staging run read from the function's logs and the dead-letter queue.
- Live check scope: the fixed questions only, plus one cheap full-chain smoke on staging after
  the deploy.

## Verification evidence expected

In `verification.md`: the before and after tables per stage on the laptop and on staging with
run ids; the ingest split per run and the embedding requests, tokens, sleeps and quota in
force; the parity result per query; the markup-chunk count and quote-failure rate before and
after; per step, the timeout set, the stalls caught and any retry that was also slow; the
width measurements; the migration timings on dev and staging; `cdk diff`; the cold-import
times before and after N13; the data-flow note's path; the retention rule's text; every
command; anything reverted and why.

## Risk tier & review focus

**Tier 4.** A migration with a data backfill and a dropped column, new production resources
and config, a new dependency, a Dockerfile change, product egress from a new place, a shared
cross-task data store, and timeouts on every model call. Review: contract verifier; code
review; security review (the function's network posture, the parse subprocess isolation, the
message contents, the shared row's columns, the Aurora security group); adversarial review at
contract and plan stage; human-approved plan; ADR; rollback plan (`ingest_mode = in_process`,
migration downgrade, timeouts and widths are constants). Focus: at-least-once delivery and
idempotency, late writes after the deadline, connection counts, throttled embedding never
leaving chunks without vectors, parity read from saved results, timeouts that cut healthy
calls, no scope creep into synthesis.
