# Knowledge update log

## 2026-07-06
* **Creation**: Added
  [llm-schema-valid-empty-output](llm-schema-valid-empty-output.md) — structured outputs
  guarantee shape, never completeness; validate counts against the input set in code
  (gpt-5-nano returned `{"assignments":[]}` schema-perfectly on realistic batches; task 009
  live evidence). First entry in a new "Integration quirks" index section.
* **Creation**: Added
  [langfuse-host-must-be-explicit](langfuse-host-must-be-explicit.md) — the Langfuse SDK
  defaults its endpoint to the SaaS cloud when no host is set; with full-I/O traces
  `get_langfuse()` requires an explicit host and raises on partial config (task 009 review
  stack, convergent security + adversarial finding).

## 2026-07-05
* **Creation**: Added
  [fulltext-chunk-hash-determinism](fulltext-chunk-hash-determinism.md) — same bytes must hash
  the same in every process; pymupdf4llm 0.3.4's id()-keyed cache breaks it, source-patched at
  import with the fan-out determinism test as backstop (task 008).
* **Creation**: Added
  [sanitized-fixtures-audit-against-raw](sanitized-fixtures-audit-against-raw.md) — verify
  recorder sanitization by substring-auditing raw vs committed fixture (list items inherit the
  list's key; rare fields like grant IDs slip key lists; use a neutral fake lexicon) (task 007).

## 2026-07-03
* **Creation**: Added
  [rubric-domain-defines-appraisability](rubric-domain-defines-appraisability.md) — a scoring
  mapping's domain defines eligibility (absence = skip-and-count); counting buckets have two
  lifetimes (inserted-this-call vs recomputed-from-state); int dict keys become strings in
  JSONB payloads (task 006).

## 2026-07-01
* **Creation**: Added [per-doc-fanout-idempotent](per-doc-fanout-idempotent.md) — the
  `WHERE NOT EXISTS` guard that makes per-document fan-out functions safe to re-run (task 005).
* **Creation**: Added
  [per-doc-fanout-isolates-decision-call](per-doc-fanout-isolates-decision-call.md) — wrap only
  the per-document decision call, never the insert, so one bad document can't abort the batch or
  poison the transaction (task 005).
* **Creation**: Added
  [harness-scope-lookup-project-scoped](harness-scope-lookup-project-scoped.md) — a harness scope
  lookup must filter by `project_id`, not just the scope ID, or cross-project scope use is
  silently accepted (task 005).

## 2026-06-29
* **Creation**: Added [upload-no-dedup](upload-no-dedup.md) — the no-content-hash-dedup invariant for uploaded sources (task 003).
* **Creation**: Added [citation-flag-dont-drop](citation-flag-dont-drop.md) — citation row written before GroundingError; fail evidence survives committed transactions via the harness (task 003).

## 2026-06-24
* **Initialization**: Created the bundle — index + four verified concepts from task 001
  ([structlog-only](logging-structlog.md), [test DB](testing-database.md),
  [event-log sequence](event-log-sequence.md), [block content_hash](block-content-hash.md)).
* **Update**: Added the [plan→config compile fails-closed](plan-compile-fails-closed.md) invariant —
  also verified by task 001, missed in the initial seed.
