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

## Invariants (verified)

* [Event-log sequence is app-assigned under a single writer](event-log-sequence.md) - `(project_id, sequence)` ordering, append-only at the repo layer.
* [Block content_hash is a normalised hash](block-content-hash.md) - whitespace-insensitive, excludes the (deferred) summary.
* [Plan→config compile fails closed](plan-compile-fails-closed.md) - an invalid plan is rejected with a pydantic `ValidationError` at construction; the harness never runs on it.
* [Upload ingest creates a new snapshot per call](upload-no-dedup.md) - no content-hash dedup for uploaded sources; each re-upload is a distinct snapshot; dedup for acquired sources is follow-on.
* [Citation row written before GroundingError — fail evidence survives](citation-flag-dont-drop.md) - flag-don't-drop is guaranteed within the harness; direct callers outside the harness must catch GroundingError before their transaction boundary.
* [Per-document fan-out must exclude already-processed rows](per-doc-fanout-idempotent.md) - `WHERE NOT EXISTS` guard makes classify_sources/screen_sources safe to re-run for the same scope.
* [Per-document fan-out isolates the decision call, not the persistence](per-doc-fanout-isolates-decision-call.md) - only the classification/screening call is wrapped in try/except, falling back to an already-valid closed value; the insert runs unguarded.
* [Harness scope lookups must filter by project_id](harness-scope-lookup-project-scoped.md) - an ID-only lookup silently accepts a scope from another project; composite FKs guard writes, not reads.
