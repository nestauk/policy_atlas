---
type: Convention
title: The event log's run-id FK decides what can carry audit state — no run, no event
description: Anything that happens without a run — a skipped component, a pre-run plan event, a steering interaction — needs a table-first or outcome-object carrier instead; the same constraint resurfaced three times in one slice. Corollary — some tables reach their run only transitively (annotation via block → artefact), shaping how run-scoped queries must be written.
tags: [event-log, persistence, audit, orchestrator, architecture]
timestamp: 2026-07-12
---

# Rule

`event_log` rows require a `run_id` (composite FK; see
[event-log sequence](event-log-sequence.md)), so only things that happen
*inside a run* can be evented. Anything without a run needs a different
carrier, chosen deliberately:

- **plan lifecycle** (proposed/approved/superseded, before any run) →
  table-first: `orchestration_plan` version rows (017 contract rev 2.5).
- **skipped components** (a skip means no run row exists) → the
  `RunPlanOutcome` object + end-of-run collation.
- **steering interactions** → a user-attributed plan version row for
  attribution, with the fine directive in the re-run's
  `selection_result.selection_provenance` (the re-run *has* a run).

# Why

017 hit this constraint three separate times while wiring the orchestrator;
each time the first instinct was "emit an event" and each time the FK made
that impossible. Naming the pattern avoids re-deriving it: when audit state
has no run, pick table-first or outcome-object up front.

# Watch out

Outcome-object carriers are not durable — a skip reason lives only in the
process that ran the plan. If durable skip provenance is ever needed, that is
a schema decision (recorded on the deferred provenance seam), not an event.

The transitive-reach corollary (020 live check): `annotation` has no
`run_id` column — it reaches its run only via `block` → `artefact`. A
run-scoped annotation query therefore joins that path and, when picking a
specific mint, wants newest-first plus a payload-shape filter
(`a.payload ? 'cited_finding_ids'` for finding-claim citations) rather than
assuming run scoping exists on the table.
