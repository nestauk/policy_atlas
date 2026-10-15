---
type: Invariant
title: "Does this walk exist / has it run" reads the intent record, and counts only live or good walks
description: A walk is queued before its capability_run row exists, so an existence check keyed on the walk row misses it and a retried confirm mints a second walk; key on the evidence_scope (intent) row instead. And a status-blind check turns every failure permanent — a failed longlist blocked Build longlist, a failed option search was never retried. Count running/paused, queued, or finished-with-a-result only.
tags: [runner, idempotency, evidence-scope, option-search, longlist, task-045, invariant]
timestamp: 2026-09-24
---

# Rule

Two questions the scoping paths ask about walks, and how each is answered as built:

| Question | Keyed on | Counts | Does not count |
|---|---|---|---|
| Is this plan version's longlist built, building or queued? (`longlist_start.longlist_walk_exists`) | the `longlist` `evidence_scope` row for the plan version | its walk `running`/`paused`; no walk row yet and the record minted by this process (still queued); a `longlist_result` written under it | a walk that failed or was interrupted with no result |
| Has this option been searched? (`option_search.searched_option_ids`) | the `targeted` `evidence_scope` row naming the option | its walk ended `succeeded` or `degraded` | failed, aborted, interrupted |

# Why

The 045 review stack found both halves. **Wrong key** (adversarial B3): the confirm's opener
times out and releases its reservation while the walk is still queued on the executor; the check
looked for a `capability_run` row, found none, and a retried confirm opened a second longlist
walk. **No status** (contract F2, adversarial B2): a failed longlist walk counted as existing, so
*Build longlist* did nothing; a failed option search counted as searched, so no rebuild ever
retried it.

# Watch out

- The intent record is minted in the opener's transaction, before dispatch — that is what makes
  it the earliest durable sign of a walk. Any new "already started?" check should key there.
- The "queued" leg compares `created_at` with the process start (`_PROCESS_STARTED`): a record
  minted by a process that died is not queued forever. It is a single-process assumption
  ([db-row-is-the-single-flight-authority](db-row-is-the-single-flight-authority.md)).
- Related: [child-walks-end-on-every-parent-exit](child-walks-end-on-every-parent-exit.md) (how
  children reach a terminal status), [longlist-rebuild-reads-every-earlier-build](longlist-rebuild-reads-every-earlier-build.md)
  (what a rebuild reads once "searched" is right).

# Citations

- `backend/src/policy_atlas/api/longlist_start.py` (`longlist_walk_exists`)
- `backend/src/policy_atlas/runtime/option_search.py` (`searched_option_ids`, `_FINISHED`)
- [045 verification.md](../tasks/045-scoping-longlist/verification.md) § Review findings (B2, B3, F2)
