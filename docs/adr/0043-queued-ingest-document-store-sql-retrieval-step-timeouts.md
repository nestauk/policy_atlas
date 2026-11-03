# ADR 0043 — Full-text reading as queued functions over a shared document store, embedding in the stage, retrieval in SQL, and a timeout per model-call step

- **Status:** Accepted — 2026-11-03 (Shabeer Rauf, owner, task 057 plan gate).
- **Date:** 2026-11-03
- **Task:** [057-queued-ingest](../tasks/057-queued-ingest/contract.md) (contract revision 4,
  plan draft 2, both approved 2026-11-03)
- **Builds on:** [ADR 0042](0042-gpt6-switch-per-call-site-routing-and-caching.md) (one route
  step per model call; the route file's layers) · [ADR 0041](0041-bedrock-inference-route-and-model-route-file.md)
  (Bedrock as the inference route) · [data-model.md](../specs/system/data-model.md) § Corpus &
  source snapshots (acquired snapshots as a shared content-addressed substrate; no original
  bytes retained) · [execution-orchestration.md](../specs/system/execution-orchestration.md)
  § Durability & concurrency (the component boundary is the checkpoint).

## Context

After task 056 a standard Evidence search run took about 30 minutes at the median on the
`bedrock` route, which the owner has made the app's default. Twelve runs measured on
2026-11-02 put 41% of that in one stage, reading the full texts (fetch and parse about 5
minutes, then about 7.5 minutes of embedding), and 29% in writing the report, where one to
five model calls per run hung silently until a 120 s client timeout and then succeeded on
the SDK's retry. Every other stage together was 30%. The web server runs on 2 vCPU, so
parsing cannot be made fast where it is.

Nine experiments and six research notes settled the facts the decisions rest on. Bedrock
throttles the Cohere embedding model by tokens per minute on this account, and a single
request stream already reaches the allowance, so parallel senders cannot speed embedding;
only the quota raise the owner has requested can. The embedding loop's own overhead is almost
all the JSON write of the vectors. On Bedrock the first streamed token arrives at 71 to 97%
of a call's total time, so a streaming watchdog detects a stall no sooner than a total
timeout. Splitting the grounding judge into parallel claim batches saves no time, because
reasoning tokens per call do not shrink with fewer claims. Deterministic grounding checks
catch few unsupported claims and flag many supported ones. The failed quote matches that
motivated a parser rewrite were mostly the previous writer model copying markup; the current
writer fails 0.7% of PDF quotes before any parser change. Fifty uncoordinated fetchers were
refused by one host because the retry ignored its Retry-After header. The parser is
single-threaded and the worst real PDF needs under 300 MiB, so a function gets one full core.
The runner holds one database transaction around a whole component, so rows a function must
update have to be released in their own transaction first. Writing report sections in
parallel was ruled out by the owner for coherence, and the only published evidence on it is
negative.

## Decisions

1. **Reading the full texts becomes a job that fills a shared document store.** In the cloud,
   the stage puts one message per document on an SQS queue (two ids and a schema version, no
   URL and no user identifier) and one Lambda function per message fetches, parses and writes
   the document; on laptops a local queue client runs the same handler on threads. The stage
   itself has one code path in both modes: flip the rows to `queued` in a committed
   transaction, send, poll the statuses, embed as documents land, stop at a deadline. The
   store is the four existing tables, keyed for reuse by body hash × parse profile ×
   segmentation policy, with reuse on from day one and no task, user or run breadcrumb on the
   shared row. A function's late result never changes the current run's rows; it joins the
   store for later runs. Documents past the deadline are `fetch_failed` with reason
   `not_ready`, outside the access-failure vocabulary.

2. **Embedding stays in the stage, under an adaptive pool.** The function writes no vectors.
   The stage embeds pending chunks as documents land through a pool that owns both concurrency
   and backoff: it halves the number in flight on a throttle and adds one after a run of
   clean batches, up to a cap in the route file. The design needs no change when the token
   quota rises. The function is sized for CPU (1,769 MB, one core), not for memory.

3. **Chunk retrieval moves into Postgres.** `chunk_embedding` gains a binary `vector(1536)`
   column and a token array, and one SQL statement computes both legs, the fusion, every
   boost and the clamp before its limit, at parity with the Python retriever on a committed
   synthetic corpus and on recorded real queries. The in-memory scope load, the Python scoring
   and the 20,000-unit ceiling are deleted. The migration is three resumable revisions
   (expand, data-only backfill, assert-and-drop), online-safe so the backfill can run before a
   deploy while the service is up.

4. **Every model-call step carries its own client timeout in the route file,** applied per
   request, set to twice the step's healthy 99th-percentile total where at least 100 traced
   attempts exist and to today's value otherwise, with the SDK's silent retries replaced by one
   traced retry so each attempt is its own generation. The grounding judge runs at `low`
   reasoning effort under the bedrock route's override, to be revisited by the synthesis
   refinement task with a labelled set. Section order and the ledger are untouched.

5. **Parse profile version 2 is the markup rule only.** Chunk text carries no markdown or
   HTML marks; headings stay in the locator. The header, page-number and footnote rules are
   deferred with their measurements. The quote matcher strips markup on the quote side too, as
   verifier version 2.

6. **Not taken, with the measured reason:** parallel section writing (coherence); judge
   splitting (no saving); a two-stage or deterministic judge (poor catch rate); a streaming
   watchdog or hedged requests (no gain over timeouts on Bedrock; double billing); paid
   provider tiers (they multiply the largest cost line); per-host coordination across
   functions (one host affected, Retry-After covers it); durable workflow engines (no
   happy-path saving).

## Consequences

- Expected on the `bedrock` route for a 100-document run: the reading stage from about 12
  minutes to about 2 once the quota raise lands (about 5 while it does not, embedding being
  the floor), report writing from about 8.7 to about 4.5 minutes, the run from about 30 to
  about 14 or 15. The fixed questions decide; every lever is measured on its own.
- New production resources: a queue, a dead-letter queue, a function built from the backend
  image with a second command, their roles and alarms; a config value `ingest_mode` per
  environment; the dev and CI Postgres image gains pgvector; the backend image ships compiled
  bytecode. Rollback for the stage is `ingest_mode = in_process`; for retrieval it is the
  previous image plus the migration's downgrade, which rebuilds the JSON vectors at float32.
- The data flow changes: parsed text is shared across tasks, URLs stay out of the queue, the
  function holds the database secret only. A DPIA addendum gates the merge; a data-flow note
  and a retention rule for unlinked snapshots are part of the slice.
- Staging evidence is gathered after the merge to dev, because staging deploys only from dev;
  the PR names it as the one open item.
- Seams left for later slices, recorded in `deferred.md`: the production route flip to
  `bedrock`; the remaining parse rules; the low-effort judge's labelled-set check and
  per-claim judge filtering; the fallback parser; per-host fetch coordination; the staging
  inspection secret, whose password no longer matches the database.
