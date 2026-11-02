# Task contract: 057-queued-ingest

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status:** drafted 2026-11-02, revision 1, awaiting contract approval. Contract approved
> (before planning): _pending_ · Plan approved (before implementation): _pending_ · ADR:
> _pending (step 4)_ · Branch: `task/057-queued-ingest`.
>
> Scope rulings: the owner ruled on the 15 items of the decision sheet on 2026-11-02 (file
> `docs/research-and-development/synthesis-refinement/latency-slice-decision-sheet.md`,
> gitignored). Every item is cited below as "sheet item n". Items 2 and 3 change the shape the
> DevOps colleague saw on 2026-10-30; their agreement is recorded at the contract gate (G1).

## Goal

Cut the wall time of an Evidence search run by taking the one stage the web server cannot
make fast, reading the full texts, out of the web server. Functions fetch, parse and embed
each document and load it into a shared document store; the run reads the store. The same
slice fixes the parsed text (markup, running headers, footnotes) so quotes match, moves chunk
retrieval into Postgres, and takes two small latency levers in Options scoping. Reports are
not meant to change in content; retrieval ships at parity with today's ranking.

Measured baseline (2026-11-02, 12 Evidence search runs on the dev laptop after task 056,
every run overlapping another; `experiments/latency-anatomy-2026-11-02/report.md`, folder
gitignored):

| Stage | Median wall | Share | What binds it |
|---|---|---|---|
| ingest_full_text, bedrock route (10 runs) | 729 s | 41% | fetch and parse 281 s, then 457 s of serial embedding calls (about 6 s each; latency, not quota) |
| ingest_full_text, openai-direct route (2 runs) | 225 s | 12% | fetch and parse 164 s, embedding 61 s |
| synthesise | 562 s | 31% | serial model calls (out of scope, sheet item 10) |
| every other stage together | about 260 s | 15% | provider latency inside thread pools |
| whole run | 1,790 s | | |

Scoping: a full walk took 1,009 s; the option-search fan-out 357 s (10 children of about
144 s through a pool of width 4); two walks held single model calls of about 900 s.

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
- Infra has a Lambda precedent (`database_stack.py`, the secret loader), a NAT instance in the
  private subnets, and a deploy script that runs migrations as a one-shot task before the
  service scales.
- Rollback is a configuration value: `ingest_mode = in_process` returns the stage to the web
  server with the code it runs today on laptops.

## Deliverable

A pull request where:

1. `ingest_mode = queued` makes the ingest stage enqueue one message per document, and a
   Lambda function built from the backend image fetches, parses, writes and embeds that
   document into the document store; the stage waits on the per-document statuses with a
   deadline and continues (N1 to N5).
2. `ingest_mode = in_process` (laptops, tests) runs the same per-document function in a
   thread pool, so one code path serves both modes (N6).
3. Parsed text follows parse profile version 2: plain chunk text, no running headers or
   footers, footnotes separated, clean sentence boundaries (N7).
4. Chunk retrieval is one SQL statement over a pgvector column, at parity with today's top-8
   on the saved queries; the in-memory scope load and the Python scoring are deleted (N8).
5. The document store is content-addressed by body hash, parse profile and segmentation
   policy, and a document already in the store is linked without a second parse (N9).
6. Two scoping levers: the long client timeout behind the 900 s calls is sized to its tail,
   and the option-search width is raised, both measured (N10).
7. New cloud resources in CDK and config: a queue, a dead-letter queue, the function, its
   role and security group, the concurrency cap, one alarm, and `ingest_mode` per
   environment (N11).
8. `verification.md` holds the before and after measurements on the laptop and on staging,
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
| **Segmentation policy** | The named, versioned rule that cut the text into chunks, for example `pymupdf4llm_struct_v1`. Today a column on `chunk` and a key in snapshot metadata; becomes a snapshot column (D2). |
| **Embedding profile** | The named embedding model version stamped on each `chunk_embedding` row (`embedding_profile`), with the unit policy (`embedding_unit_policy_v1`: units of at most 2,000 characters with a 200-character overlap). Cohere Embed v4 on the bedrock route, text-embedding-3-small on openai-direct; both 1,536 numbers, not comparable with each other. |
| **Store key** | Body hash × parse profile × segmentation policy. Two fetches with the same key share one full-text snapshot (D3). Embeddings are per profile on top of that. |
| **Ingest mode** | A configuration value, `in_process` or `queued`, read like the model route (environment variable, set per environment by infra). |
| **Function** | The AWS Lambda function that handles one queue message: one document. Built from the backend container image with a second command, not a second image (D5). |
| **Queue** | One Amazon SQS standard queue. One message per document. A **dead-letter queue** receives a message after its second failed attempt. |
| **Stage deadline** | How long the ingest stage waits for queued documents before it marks the rest not read and the run continues. 10 minutes (D4). |
| **Function timeout** | The Lambda timeout, the per-document deadline: 3 minutes (D4). The parse step inside keeps its own 120 s kill. |
| **Embedding quota** | On the bedrock route the Cohere Embed v4 cross-region quota is 2,000 requests per minute (not adjustable) and 300,000 tokens per minute (adjustable). AWS states that embedding models are throttled by requests per minute, not tokens per minute (Bedrock user guide, "Quotas", read 2026-11-02). A run needs 80 to 110 requests, so the request quota does not bind. The measured 2026-11-02 run embedded at about 320,000 tokens per minute with one throttling sleep, which agrees with the token figure not being enforced. The staging measurement settles it (D6). |
| **Fixed questions** | The three Evidence search questions and one Options scoping question task 056 used (`docs/tasks/056-cost-latency/contract.md` O5), run fresh as new tasks before and after. |
| **Parity** | The SQL retriever returns the same top-8 chunks in the same order as today's Python retriever for the 20 saved section queries of the feasibility study, and for the fixed questions' section queries replayed. |
| **Decided / Leaning / Open** | Decided is settled. Leaning is the recommended choice unless the owner objects. Open means the owner chooses at the named gate. |

## Facts we rely on

| Fact | Source | Consequence |
|---|---|---|
| Ingest is 684 s of a 1,790 s median run; on bedrock 457 s of it is embedding in serial calls of 96 units, about 6 s each; rate-limit sleeps were 0 to 105 s. | `latency-anatomy-2026-11-02/report.md` Tables 2 and 4 | N1 to N5 target fetch, parse and write; embedding is bound by the quota floor (D6). |
| One measured run embedded 7,732 units, about 11 million characters, about 2.7 million tokens, in 83 serial requests over 513 s (about 6 s per request, about 320,000 tokens per minute, one throttling sleep). AWS throttles embedding models by requests per minute; the cross-region request quota is 2,000 per minute. | local DB query 2026-11-02 (this conversation); AWS quota page; Bedrock user guide "Quotas" | Embedding is bound by per-request latency, not by quota, so per-document embedding in parallel functions should cut it from minutes to tens of seconds (D6). No quota request is needed before the build; G4 becomes a fallback. |
| Live fetch took 100 to 250 s per run because the fetcher reserves 25 MB of a 100 MB budget per body, so at most 4 bodies download at once, and one slow host holds a slot. | `fetch_live.py` constants; report Table 4 handover columns | Fetch moves into the function (sheet item 2). |
| Lambda: 15 min timeout, up to 10 GB memory, 10 GB container image, 6 MB synchronous payload, per-queue concurrency 2 to 1,000; London $0.0000167 per GB-second (x86). | `experiments/aws-limits-2026-11-02.md` | D4, D5, N11. |
| A Lambda in the private subnets reaches Aurora by the VPC local route and the internet through the fck-nat instance; S3 is not needed when fetch and writes happen in the function. | `infra/infra/network_stack.py`; AWS docs in the limits note | No bucket, no new endpoints (D5). |
| `full_text_status` is checked to `not_attempted`, `ingested`, `fetch_failed`, `parse_failed`; `ingested` ⟺ snapshot id set; failed ⟺ error set. | `core/schema.py` `ck_tss_*` | D2 adds `queued`. |
| `source_snapshot` has no task id; `task_source_snapshot` holds `task_id` and `origin`. | `core/schema.py` | The shared row already carries no task or user id (sheet item 8). |
| `chunk_embedding.vector` is a JSONB float array; retrieval loads every unit of the scope into memory, caps at 20,000 units, scores cosine and word overlap in Python and fuses with RRF k = 60. | `synthesis_tools.py` `build_retrieval_scope`, `ChunkRetriever` | N8 replaces the load and the scoring with SQL. |
| One SQL statement (vector top-200 + word-overlap top-200, RRF k = 60, the screen-confidence prior) returned today's top-8 in order for 20 of 20 queries; 30 to 47 ms per query on the whole dev corpus; HNSW is not needed at scope sizes. | `pgvector-hybrid-feasibility.md` | N8 at parity; no HNSW index in this slice. |
| 80 of 128 failed quotes were markup left in chunk text; 24 were interleaved page headers, numbers or footnotes; PDF chunks fail 13% against 1% for web pages. | `citation-funnel-measurement.md` | N7 and its measure. |
| The parser already runs each document in its own process with a 120 s kill; a forkserver preloads the modules. Tests pin byte-identical output across worker counts and deny every socket inside the worker. | `ingest_full_text.py` `_ParseScheduler`, `_worker_entry`; `test_ingest_full_text.py` | The function keeps the subprocess and the kill (D5); the digest test moves to the new profile. |
| The backend image has no entrypoint; its command is uvicorn. Infra builds it once (`ContainerImage.from_asset`) and reuses it for the migration task. | `backend/Dockerfile`; `policy_atlas_stack.py` | D5: the function is the same image with another command. |
| The route file names the embedding backend, model and profile per route; `live_embedding_backend()` switches on it; `embed_pending_chunks` already treats chunks under another profile as pending. | `core/model_routes.py`, `core/embeddings.py` | A reused snapshot ingested under another route is embedded, not re-parsed (D3). |
| Scoping call sites held single calls of 901 to 903 s (49 calls over 300 s in one stage). | report Table 7 | N10a. |

## Read first

- `docs/research-and-development/synthesis-refinement/queued-parsing-task-seed.md`,
  `latency-slice-decision-sheet.md` and the two experiment folders named above (gitignored).
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
  file pattern this slice's `ingest_mode` follows.
- `infra/DEPLOYMENT.md` § the deploy sequence (stop → migrate → scale) and the rollback notes.
- Code: `evidence_search/sourcing/ingest_full_text.py`, `fetch_live.py`, `parse_jats.py`,
  `core/embeddings.py`, `core/schema.py`, `evidence_search/synthesis/synthesis_tools.py`
  (`build_retrieval_scope`, `ChunkRetriever`), `api/chat_scope.py`, `runtime/harness.py`
  (`_run_ingest_full_text`), `runtime/scoping_plan.py` (`OPTION_SEARCH_WIDTH`),
  `options_scoping/scoping_backend.py`, `infra/infra/policy_atlas_stack.py`,
  `infra/infra/network_stack.py`, `infra/pa_config.json`, `scripts/deploy.sh`.

## Numbered needs

| # | Need | Where it lives today | Measure |
|---|---|---|---|
| N1 | One message per eligible document on the queue, carrying the link row id, the candidate URLs, the PubMed Central id if any, the open-access flag, and the run id. No user identifier. | `ingest_full_text_sources` builds the eligible set in one query and fetches in threads. | A test asserts the message shape and that no field is a user id; a live run shows one message per attempted document. |
| N2 | The function handles one message: fetch (same rules as today: scheme, private-IP refusal, redirect cap, byte cap, paywall and bot-block vocabulary), parse in a subprocess with the 120 s kill, write the snapshot and chunks, embed the units, set the link row to `ingested` or to a failed status with the same reason codes as today. Idempotent: a link row already `ingested` returns at once. | fetch in `fetch_live.py`; parse and writes in `ingest_full_text.py`; embed in `core/embeddings.py`. | Unit tests on the handler with a fake event and a test database; the committed fixture corpus produces the same statuses and reasons as the in-process path. |
| N3 | The stage in queued mode: set the eligible rows to `queued`, send the messages, poll the statuses, publish progress ticks from the counts, stop at the stage deadline, mark the rows still `queued` as `fetch_failed` with reason `deadline`, return the same counts dict as today. | `ingest_full_text_sources`; `_IngestProgress`. | A test with a fake queue and a fake clock covers: all done early, some late, deadline hit. The counts invariant holds (eligible = ingested + already ingested + fetch failed + parse failed). |
| N4 | Deadlines: function timeout 3 min, stage deadline 10 min, dead-letter after the second attempt, a CloudWatch alarm on the dead-letter queue depth. | none | CDK test pins the values; the alarm exists in the synthesised template. |
| N5 | Concurrency cap on the event-source mapping (Leaning: 50), so the function never opens more database connections than the writer instance allows with the API's pool. | none | CDK test pins the cap; the plan records the writer instance's `max_connections` and the arithmetic. |
| N6 | One code path: a per-document function `ingest_document(conn, link_row, …)` called by the Lambda handler and, in `in_process` mode, by a thread pool of the parse worker count. The N8 scheduler and the batch hand-over are deleted. | `_ParseScheduler`, `_run_parse_jobs`, `_drain_*`, the fetch thread pool. | Byte-identical chunk digest on the committed fixture corpus between worker counts 1 and 4 (the existing test, re-pinned to profile v2); statuses and reasons identical between the two modes on the fixture corpus. |
| N7 | Parse profile v2 and segmentation policy v2 for PDF, HTML, JATS and plain routes: markup removed from chunk text at segmentation (headings kept in the locator, not the text), running headers and footers removed, footnotes placed in their own chunk flagged in the locator, sentence boundaries kept. New profile and policy names; old snapshots untouched. | `_parse_pdf`, `_parse_html`, `_segment_markdown_pages`, `parse_jats.py`. | On the citation-funnel method re-run on the fixed questions, the quote-match failure rate on PDF chunks falls from 13% to at or below 4% (🟡 target); headings and tables per document not below v1 on the 20-PDF Textract comparison set. |
| N8 | Retrieval in SQL: a `vector(1536)` column and a `tokens text[]` column with a GIN index on `chunk_embedding`, backfilled from the JSONB vectors and the chunk text; `ChunkRetriever.search` runs one statement that returns the fused candidate list (up to 50 rows with their prior factors); Python keeps query embedding, the reranker seam, the cut to 8, the character budget, dedup, windowing and provenance. `build_retrieval_scope` no longer loads units or vectors; the 20,000-unit cap and `RetrievalUnitCapError` are deleted. Both callers (synthesis, chat) switch. | `synthesis_tools.py`, `api/chat_scope.py`. | Parity on the 20 saved queries and on the fixed questions' replayed section queries (same top-8, same order); retrieval provenance records the factors for the returned candidates; a query takes under 100 ms on the dev corpus. |
| N9 | Content-addressed reuse: the function hashes the body, looks up the store key, links an existing full-text snapshot instead of parsing again, and embeds only the units missing for the current embedding profile. The shared row carries no task or user id. | `source_snapshot` insert at every ingest; no body hash. | A test ingests the same bytes for two tasks and asserts one snapshot, two link rows; a test with a different embedding profile asserts a second set of embedding rows and no second parse. Live: a second run on an overlapping question shows `already_in_store` in the counts. |
| N10 | Scoping levers: (a) the client timeout behind the 900 s calls sized to the call's tail with the retry kept (056's rule); (b) `OPTION_SEARCH_WIDTH` 4 → 10 if the search backends' limits allow. | `options_scoping/scoping_backend.py` or the client it builds; `runtime/scoping_plan.py`. | The fixed scoping question before and after: fan-out wall, no new 429s in the logs, no calls over 300 s. |
| N11 | Infra: queue, dead-letter queue, function (image = the backend asset, command = the handler, memory 3,072 MB, timeout 3 min, private subnets, security group with Aurora ingress, the app secret and route variables), event-source mapping with the cap, alarm, `ingest_mode` in `pa_config.json` per environment and in the API task's environment. CDK tests. | `policy_atlas_stack.py`, `pa_config.json`. | `make -C infra test` green; `cdk diff` reviewed at the plan gate; staging deploy succeeds. |
| N12 | Measurement and governance: the fixed questions before and after on the laptop (`in_process`, both routes) and on staging (`queued`, bedrock), the ingest split (fetch, parse, embed) from logs, a one-page data-flow note, the retention rule, and the quota raise request recorded. | none | In `verification.md`; the data-flow note committed under `docs/`. |

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
  `vector` and the unit's text; a GIN index on `tokens`; a btree on `(chunk_id)` exists
  through the unique constraint. The JSONB `vector` column is **dropped in the same
  migration** (🟡 Leaning; the downgrade rebuilds it from the vector column; owner may keep
  it one release).
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
next run finds the document already ingested. Dead-letter after 2 attempts. The in-process
mode keeps the 120 s parse kill and has no stage deadline, as today.

**D5. Packaging and network. Decided (owner, sheet item 15).** The function is the backend
image asset with the command `python -m awslambdaric policy_atlas.ops.ingest_worker.handler`
(the Runtime Interface Client is a new dependency in the `ops` group: gate G3). It runs in the
private subnets, reaches Aurora by the local route, and reaches publishers, SQS and the model
providers through the fck-nat instance. No S3, no VPC endpoints. Memory 3,072 MB (the largest
PDFs seen parse inside 3 GB). The parse step runs in a subprocess inside the function with the
same kill, so a crashing PDF cannot take the handler down. Network sockets are denied inside
the parse subprocess as the tests require today; the handler process itself needs the network
for fetch, the database and the embedding provider.

**D6. Embedding. Decided (owner, sheet item 4), with the floor corrected 2026-11-02.** Per
document, inside the function, with the backoff that exists. Today's 457 s on bedrock is 83
serial requests of about 6 s each; with 50 functions in flight the same requests overlap, so
the expected embedding wall for 100 documents is tens of seconds, inside the 2,000 requests
per minute quota. The token-per-minute figure (300,000, adjustable) is listed but, per AWS,
not the throttling mechanism for embedding models; the one measured run exceeded it with one
sleep. The staging measurement records requests, tokens and throttling sleeps per run. If
throttling appears at the token rate after all, G4 (a raise request) is the fallback and the
owner decides then. Switching embedding model is out: a switch re-embeds every stored chunk.
Embedding on OpenAI from the bedrock route is a route-file change the owner can make later
without this slice.

**D7. Retrieval parity. Decided (owner, sheet item 7).** The SQL leg for words uses the
product's own score (share of query words found in the unit), not Postgres full-text ranking,
so the top-8 is reproduced exactly. The ranking choice stays with the synthesis refinement
task. No HNSW index: the planner uses the scope filter and exact distances at our sizes.

**D8. Parse profile v2 changes content, not identity rules. Decided (owner, sheet item 6).**
New profile and policy names for every route whose text changes. Existing snapshots and their
citations are untouched (spec: a parser upgrade applies to newly ingested snapshots only).
The fallback parser (Textract or Bedrock Data Automation) is deferred to a later slice with
the free trigger signals recorded in `deferred.md`.

**D9. Measurement. Decided.** Before: the 2026-11-02 anatomy. After, on the laptop: the three
fixed Evidence search questions in `in_process` mode on both routes, which measures N6 to N8;
on staging: the same three in `queued` mode on bedrock, which measures N1 to N5, with the
ingest split read from the function's logs and the embedding quota state recorded. The fixed
scoping question before and after N10. The owner reads one report per route after N7 and N8
for a content check (reports are not meant to change).

**D10. Out of scope, named.** Parallel report sections and the summary pass (sheet item 10;
synthesis refinement task). Graviton (sheet item 11). Uploaded documents (sheet item 12).
The fallback parser (D8). HNSW. Moving runs out of the API process. Per-host politeness
coordination across functions (D11). The acquire-stage embedding of abstracts (about 4
requests per run; stays in process). Any prompt text.

**D11. Known limits accepted.** With 50 functions in flight the per-host limit (2 at once,
1 s apart) is not coordinated across functions; hosts with many documents may answer 429,
which the fetch retry handles. Measured on staging; if 429s rise, the lever is a per-host FIFO
message group in a later slice. Lambda cold starts (2 to 5 s per concurrent function on the
first run after a deploy) are inside the stage deadline.

## Owner rulings (2026-11-02)

Sheet items 1 to 15 as listed in the decision sheet: 1 yes; 2 yes; 3 yes; 4 yes; 5 yes;
6 yes; 7 yes, and the in-app hybrid search is removed; 8 reuse on, no switch; 9 ok;
10 report writing out; 11 Graviton out; 12 uploads out ("the app doesn't have that yet");
13 yes; 14 ok, "ideally we'd get it as low as possible"; 15 yes.

## Spec items (proposed; the owner decides each)

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

## Scope / Out of scope

- **In:** `core/schema.py` and one migration; `core/embeddings.py` (per-snapshot embedding,
  `tokens`, vector column writes); `evidence_search/sourcing/ingest_full_text.py` (the
  per-document function, the queued and in-process stage, profile v2 segmentation),
  `fetch_live.py` (used from the function; constants unchanged), `parse_jats.py` (v2 text);
  a new `ops/ingest_worker.py` (handler) and a queue client module; `runtime/harness.py`
  (passes the mode); `evidence_search/synthesis/synthesis_tools.py` and `api/chat_scope.py`
  (SQL retrieval); `runtime/scoping_plan.py` and the scoping client timeout; `model_routes.toml`
  only if the embedding profile name changes (it should not); `infra/infra/policy_atlas_stack.py`,
  `infra/pa_config.json`, infra tests; `backend/pyproject.toml` (one dependency, G3);
  `backend/Dockerfile` only if the handler needs a file copied; tests beside each; `docs/deferred.md`;
  one ADR; the spec items the owner accepts; a data-flow note under `docs/`.
- **Out:** everything in D10; `scripts/deploy.sh` beyond passing the mode; the frontend
  (ticks unchanged); prompt text and prompt hashes (no pinned file changes; a code-only
  re-pin stops the slice unless the owner accepts it, 056's rule); Langfuse; the search
  backends; other capabilities.

## Constraints & approval gates

- **G1. Egress (runtime).** The function fetches publisher URLs, calls the embedding provider
  of the route, and talks to SQS and Aurora. Same hosts and same data as today, from a new
  place. Approved at this contract by the owner (sheet item 2); the DevOps colleague's
  agreement to items 2 and 3 recorded here before planning: _pending_.
- **G2. Schema.** The D2 migration, approved at this contract. Tier 4.
- **G3. Dependency.** `awslambdaric` in the `ops` group, approved at this contract. No other
  dependency; vectors are sent as text casts, not through a client library.
- **G4. Quota request (fallback only).** If the staging measurement shows throttling at the
  token rate, the owner or the DevOps colleague requests a raise of the Cohere Embed v4
  cross-region tokens-per-minute quota (adjustable) in eu-west-2 through Service Quotas. Not
  requested before the measurement; the contract does not depend on it.
- **G5. Production config and CDK.** The resources in N11 and `ingest_mode` per environment,
  approved at this contract; `cdk diff` reviewed at the plan gate; production stays
  `in_process` until the staging measurement is read (Leaning).
- **G6. Public interface.** None. The SSE stage and tick shapes are unchanged. The counts
  dict gains `already_in_store` (internal).
- **G7. Governance.** The DPIA addendum for the changed data flow is the owner's artefact and
  gates the merge, as in task 033; the slice supplies the data-flow note (N12).
- **Tests stay offline.** The handler is tested with a fake event and the test database; the
  queue client with a fake; no AWS call in `make verify`.

## Public / private boundary

Committable: code, tests, CDK, config values, this folder's documents with numbers, the
data-flow note (it names services and data classes, not documents). Private: the fixed
questions' report text, publisher URLs lists, credentials, Langfuse keys, the DPIA itself.

## Model route

No model call site changes. The embedding backend follows the route file as today; the
function reads `POLICY_ATLAS_MODEL_ROUTE` from its environment like the API task. No prompt
text changes; no re-pins expected.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves.** `queued` changes what the stage waits on; `body_hash` changes
  what is parsed; the new columns on the snapshot replace JSON keys the code already reads.
- **Flag, don't drop.** A document past the deadline is `fetch_failed` with a reason, visible
  in the counts and retried next run; never silently absent.
- **Honest absence.** Coverage counts keep their base; `already_in_store` is its own count.
- **One code path.** The function and the in-process mode call the same per-document
  function; a behaviour that exists in one mode only is a defect.
- **Measure before and after**, one lever at a time, read from saved results.
- **Specs are the owner's.** S1 to S4 are proposals; the build applies only what is accepted.

## Stop conditions

Halt and escalate when: a gate above is hit without its approval; parity (D7) fails on any
of the 20 saved queries and the cause is not a data difference; the migration's backfill
cannot run inside the deploy's migration task on staging; the function cannot reach Aurora or
the providers from the private subnets; profile v2 lowers headings or tables below v1 on the
comparison set; a re-pin is needed; scope would grow past this slice; the turn or token
budget is spent.

## Acceptance checks

- `make verify` green at the build-open baseline, after the schema phase, after the
  retrieval phase, and at the step-6 exit; `make verify-fast` between other phases;
  `make -C infra test` with the CDK changes.
- Deterministic tests: message shape with no user id (N1); handler statuses and reasons on the
  fixture corpus (N2); the queued stage with a fake queue and clock, including the deadline
  and the counts invariant (N3); CDK pins for timeout, memory, cap, alarm (N4, N5); byte-identical
  digest across worker counts and identical statuses across modes (N6); profile v2 removes
  markup, headers, footers and separates footnotes on the fixture PDFs (N7); SQL parity on
  the 20 saved queries from committed fixtures, provenance factors for returned candidates,
  both callers switched (N8); one snapshot for two tasks, embeddings per profile, no task id
  on the shared row (N9); the timeout value and the width (N10); migration upgrade and
  downgrade round-trip on the test database (D2).
- Manual: the fixed questions as D9 says; the owner's content read of one report per route;
  the staging run read from the function's logs and the dead-letter queue depth.
- Live check scope: the fixed questions only, plus one cheap full-chain smoke on staging after
  the deploy.

## Verification evidence expected

In `verification.md`: the before and after tables per stage on the laptop and on staging with
run ids; the ingest split per run; the parity result per query; the citation-funnel rate on
PDF chunks before and after; the migration timings on dev and staging; `cdk diff`; the quota
request and its state; the data-flow note's path; the retention rule's text; every command;
anything reverted and why.

## Risk tier & review focus

**Tier 4.** A migration with a data backfill and a dropped column, new production resources
and config, a new dependency, product egress from a new place, and a shared cross-task data
store. Review: contract verifier; code review; security review (the function's network
posture, the parse subprocess isolation, the message contents, the shared row's columns, the
Aurora security group); adversarial review at contract and plan stage; human-approved plan;
ADR; rollback plan (`ingest_mode = in_process`, migration downgrade). Focus: at-least-once
delivery and idempotency, late writes after the deadline, connection counts, parity read from
saved results, no scope creep into synthesis.
