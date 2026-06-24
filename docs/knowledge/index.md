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

Maintenance: add a concept at the after-merge step of the [task cycle](../../.claude/skills/task-cycle/SKILL.md)
when a slice proves something durable. `/okf validate` and `/okf viz` are available for upkeep.

## Conventions

* [structlog is the only logger](logging-structlog.md) - all log calls go through structlog; no print / stdlib logging.
* [Tests run against the dev DB in a rolled-back transaction](testing-database.md) - no separate test database; point `DATABASE_URL` somewhere disposable.

## Invariants (verified)

* [Event-log sequence is app-assigned under a single writer](event-log-sequence.md) - `(project_id, sequence)` ordering, append-only at the repo layer.
* [Block content_hash is a normalised hash](block-content-hash.md) - whitespace-insensitive, excludes the (deferred) summary.
* [Plan→config compile fails closed](plan-compile-fails-closed.md) - invalid config raises `CompileError`; the harness never runs on it.
