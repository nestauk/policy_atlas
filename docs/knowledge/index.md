---
okf_version: "0.1"
---

# Knowledge index

Durable, **verified** knowledge about Policy Atlas — how it's built, how it behaves, and the domain
it works in. Each entry is something a future contributor (human or agent) would otherwise re-learn
the hard way.

**Types are open** — OKF fixes no taxonomy. The bar is editorial, not categorical: *verified*,
*durable*, and *not already another lane's job*. Today's concepts are conventions, invariants and
testing rules (what task-001 proved); as the tool grows, expect domain concepts, architecture
explanations, integration quirks (real search / model providers), runbooks and deployment
assumptions too — add a new `##` section when a new kind arrives.

This is **not** the spec layer. `docs/specs/` holds *intent* — design decisions, some still 🟡 leaning
/ ❓ open. This holds what has been *built and verified*. Don't copy specs here; link to them.

Maintenance: add a concept **in the implementing PR** — after the review stack has finalised the code
([task cycle](../../.claude/skills/task-cycle/SKILL.md) step 8), before merge — written against the
code that shipped, so it can't drift from it. `/okf validate` and `/okf viz` are available for upkeep.

## Conventions

* [structlog is the only logger](logging-structlog.md) - all log calls go through structlog; no print / stdlib logging.
* [Tests run against the dev DB in a rolled-back transaction](testing-database.md) - no separate test database; point `DATABASE_URL` somewhere disposable.
* [Reject model output at the grain of the fault — and persist the reason](validation-reject-at-fault-grain.md) - text-rule violations reject the unit and route it to repair; only id/envelope corruption rejects whole-response; rejection reasons persist with the run (012 fix via the 013 review stack).

## Testing rules

* [Audit sanitized fixtures against the raw recording](sanitized-fixtures-audit-against-raw.md) - key-based sanitizers miss list-inherited keys and rare fields; substring-audit raw vs fixture, with a neutral fake lexicon.
* [Assert contract-required keys on the written row, not the component summary](assert-on-row-not-summary.md) - summary and row are built separately and drift; downstream readers consume rows — anchor evidence there (task 012 review stack).

## Invariants (verified)

* [Event-log sequence is app-assigned under a single writer](event-log-sequence.md) - `(project_id, sequence)` ordering, append-only at the repo layer.
* [Block content_hash is a normalised hash](block-content-hash.md) - whitespace-insensitive, excludes the (deferred) summary.
* [Plan→config compile fails closed](plan-compile-fails-closed.md) - an invalid plan is rejected with a pydantic `ValidationError` at construction; the harness never runs on it.
* [Upload ingest creates a new snapshot per call](upload-no-dedup.md) - no content-hash dedup for uploaded sources; each re-upload is a distinct snapshot; dedup for acquired sources is follow-on.
* [Citation row written before GroundingError — fail evidence survives](citation-flag-dont-drop.md) - flag-don't-drop is guaranteed within the harness; direct callers outside the harness must catch GroundingError before their transaction boundary.
* [Per-document fan-out must exclude already-processed rows](per-doc-fanout-idempotent.md) - `WHERE NOT EXISTS` guard makes classify_sources/screen_sources safe to re-run for the same scope.
* [Per-document fan-out isolates the decision call, not the persistence](per-doc-fanout-isolates-decision-call.md) - only the classification/screening call is wrapped in try/except, falling back to an already-valid closed value; the insert runs unguarded.
* [Harness scope lookups must filter by project_id](harness-scope-lookup-project-scoped.md) - an ID-only lookup silently accepts a scope from another project; composite FKs guard writes, not reads.
* [Rubric domain defines appraisability](rubric-domain-defines-appraisability.md) - types absent from `DEFAULT_RUBRIC` are skipped-and-counted, never scored; a domain test against the closed vocabulary makes the lookup infallible.
* [Full-text chunk hashes are deterministic — via a pymupdf4llm source patch](fulltext-chunk-hash-determinism.md) - same bytes → same chunks in every process; pymupdf4llm 0.3.4's id()-keyed cache breaks this and is patched at import; determinism test is the backstop on any parser bump.
* [Untrusted directive parsing — malformed fails closed, unknown references flag](directive-parse-malformed-vs-unknown.md) - structural malformation raises `DirectiveError` (bounded strings/collections, static messages); a well-formed unknown column/tag reference matches nothing and surfaces in `unmatched_boosts` (task 010).
* [Facet grouping is an exhaustive partition with honest residuals](facet-grouping-exhaustive-partition.md) - grouped set == the referenced extraction run's finding set; every finding in exactly one of group/ungrouped/no_value; sum identities (incl. the overall direction spread) re-asserted at write (task 012).
* [Grounding locations come from the verifier, never the model's claim](grounding-location-from-verification.md) - a model-emitted segment/chunk id is untrusted claim data; every dereferenceable location field derives from the verified spans (task 011, convergent review finding).
* [Chunk-claim quotes verify against the whole-document basis](synthesis-quote-whole-doc-basis.md) - one citation row per spanned chunk, so a row's chunk_id can name a chunk the loop never received; `gathered_ids` records what the loop saw (task 013, rev 8 B2).
* [Same-run re-execution fails loud before the first write](fail-loud-before-first-write.md) - a DB-error failure poisons the transaction and kills the harness's own component.failed event write; pre-write guards keep declared failure modes off the constraint path (task 013 review stack).

## Integration quirks (model / telemetry providers)

* [Schema-valid LLM output can still be empty](llm-schema-valid-empty-output.md) - structured outputs guarantee shape, never completeness; validate counts against the input set in code (gpt-5-nano returned a schema-perfect empty assignment list, live-proven, task 009).
* [Langfuse keys without a host silently export to the SaaS cloud](langfuse-host-must-be-explicit.md) - the SDK defaults to cloud.langfuse.com; with full-I/O traces that is a boundary violation, so `get_langfuse()` requires an explicit host and is loud on partial config.
* [On reasoning models, max_completion_tokens covers reasoning + output](reasoning-model-output-cap.md) - a cap tuned for output alone truncates real answers on gpt-5-class models (LengthFinishReasonError, task 011 live run 1); keep the cap explicit and fingerprinted, size it for both.
* [Postgres rejects NUL (U+0000) in TEXT/JSONB — scrub model output at the backend boundary](model-output-nul-scrub.md) - LLMs emit NUL-bearing strings; psycopg aborts at INSERT; strip once where records come off the wire (task 011 live run 2).
