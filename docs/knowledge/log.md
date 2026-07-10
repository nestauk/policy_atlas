# Knowledge update log

## 2026-07-10 (task 016 step 8)
* **Creation**: Added [execution-options-statement-not-connection](execution-options-statement-not-connection.md) — Connection-level `execution_options` is sticky and wrapped subsequent INSERTs in server-side cursors, red-lining three stage-2 tests at the phase-3 gate (task 016).
* **Creation**: Added [reserve-then-shrink-byte-budgets](reserve-then-shrink-byte-budgets.md) — reserve the per-item cap up front and shrink on completion, or in-flight holders on a shared budget can deadlock; found by lead review of the composed pipeline, not any component's tests (task 016).
* **Creation**: Added [pip-audit-environment-mode-under-uv](pip-audit-environment-mode-under-uv.md) — `pip-audit -r` SIGABRTs under uv-managed CPython on macOS; environment-mode audit over the synced lockfile is the CI-parity fix (task 016 deviation 1).
* **Creation**: Added [httpcore-origin-pooling-pinned-ip](httpcore-origin-pooling-pinned-ip.md) — SSRF-safe IP pinning must live in a custom `NetworkBackend.connect_tcp`, not a rewritten URL, or pooling and SNI break (task 016 plan-stage review blocker #3).
* **Creation**: Added [timing-asserts-injected-clock-logs-corroborate](timing-asserts-injected-clock-logs-corroborate.md) — politeness timing is asserted on an injected clock; live log timestamps only corroborate and can show jittered sub-interval gaps (016 live check).
* **Creation**: Added [http-403-is-usually-bot-blocking](http-403-is-usually-bot-blocking.md) — 403s from document hosts are bot-blocking unless corroborated as a paywall; 5 of 7 016 live-check failures were bot-blocks, zero corroborated paywalls.
* **Creation**: Added [isolation-belts-reraise-config-errors](isolation-belts-reraise-config-errors.md) — a per-item isolation belt swallowed a missing-fixture-corpus `FileNotFoundError` into per-doc `fetch_error` rows, exiting green over a systemic misconfiguration (016 review stack).
* **Creation**: Added [ip-refusal-allowlist-not-denylist](ip-refusal-allowlist-not-denylist.md) — IP refusal is allowlist-shaped (`not ip.is_global`); Python's `is_private` misses RFC 6598 CGNAT space, found by the 016 security lane's bypass-family testing.

## 2026-07-09 (task 015 step 8)
* **Creation**: Added
  [result-caps-need-distribution-rule](result-caps-need-distribution-rule.md) — a total
  cap needs a per-call distribution rule or the fan-out silently collapses to one
  load-bearing query (015 live-check finding, fixed in-slice as `_distribute_quota`).
* **Creation**: Added
  [guard-tests-name-real-invariant](guard-tests-name-real-invariant.md) — the 007
  zero-egress guard's importlib dodge (015 build); guards name their invariant, evasion
  is a defect even on green CI.
* **Creation**: Added
  [embedded-values-escape-wire-grammar](embedded-values-escape-wire-grammar.md) — the
  comma-borne OpenAlex filter injection (015 review stack, convergent across both
  heterogeneous lanes); sanitizers must be wire-grammar-aware.
* **Update**: [synthesise-is-run-terminus](synthesise-is-run-terminus.md) gained the
  substrate corollary — synthesise refuses envelope-only corpora
  (`no_groundable_substrate`), so no acquire-only chain can mint until 016; hit live at
  the 015 chain smoke (contract rev 3.14's wording corrected via components flow-back).
* **Adjudicated, not authored** (015 build candidates): "deep search's judge is free" —
  recorded in ADR 0012 decision 3 + verification evidence, no separate concept;
  429-burst behaviour → the cache-before-throttle seam note (deferred.md, task-015
  section); characterise live-corpus wobbles → deferred.md robustness entry (a work
  item, not durable learning); Overton tag-layer richness → a scale note on the
  filter-vocabulary seam entry.

## 2026-07-09
* **Creation**: Added
  [synthesise-is-run-terminus](synthesise-is-run-terminus.md) — every run ends in
  synthesise (the artefact-minting terminus); characterise and the composition generally
  are plan choices. Captured at the 015 contract gate after the mistake (chains described
  as ending in characterise) recurred across slices; the 015 smoke chain was corrected
  under it (contract rev 3.9). Verified against components.md §9 and the merged 013
  skeleton — not new-slice code, so it lands ahead of 015's PR by exception to the
  in-implementing-PR rule.

## 2026-07-08
* **Creation**: Added
  [effective-screen-row-read-rule](effective-screen-row-read-rule.md) — multiple screening
  rows per doc (stages + failed retries) make the effective-row helper the only legal read;
  the rule binds write paths too — the appraise write-path gap was the 014 review stack's
  unique-to-adversarial-lane find.
* **Creation**: Added
  [untrusted-prompt-fields-json-records](untrusted-prompt-fields-json-records.md) — untrusted
  fields enter prompts only inside `json.dumps` records; the sanitizer preserves newlines, so
  raw interpolation is the breach shape (014 review stack, security lane's stage-2 title
  finding).

## 2026-07-07
* **Creation**: Added
  [facet-grouping-exhaustive-partition](facet-grouping-exhaustive-partition.md) — the
  grouped set is exactly the referenced run's finding set, residuals counted never
  dropped, sum identities enforced at write (task 012).
* **Creation**: Added
  [assert-on-row-not-summary](assert-on-row-not-summary.md) — contract-required keys must
  be asserted on the persisted row, not the completed-event summary; the two drift (task
  012 review stack, the unique-to-adversarial-lane finding).
* **Creation**: Added
  [grounding-location-from-verification](grounding-location-from-verification.md) — a
  model-emitted location is a claim by untrusted output; dereferenceable location fields
  derive from verified spans (task 011 review stack, the convergent security + adversarial
  finding).
* **Creation**: Added
  [reasoning-model-output-cap](reasoning-model-output-cap.md) — `max_completion_tokens`
  covers reasoning + output on gpt-5-class models; an output-sized cap truncates real
  answers (task 011 live evidence, deviation 2).
* **Creation**: Added
  [model-output-nul-scrub](model-output-nul-scrub.md) — Postgres rejects U+0000 in
  TEXT/JSONB; model output is scrubbed once at the backend boundary (task 011 live
  evidence, deviation 3).
* **Creation**: Added
  [directive-parse-malformed-vs-unknown](directive-parse-malformed-vs-unknown.md) — untrusted
  execution-bearing JSONB inputs parse fail-closed on structural malformation (bounded
  strings/collections, static messages) but flag unknown column/tag references non-fatally;
  the split both 010 review families converged on (task 010).

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
