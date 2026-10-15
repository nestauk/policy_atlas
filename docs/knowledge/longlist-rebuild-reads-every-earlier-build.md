---
type: Invariant
title: A longlist rebuild reads what earlier builds made — every option's latest finished search, and every existing option
description: A rebuild searches only new entrants, so anything it reads only from its own children silently drops what earlier builds and the verb add searched; and a model step that cannot see the existing options re-proposes them under new words. As built, the longlist reads each option's latest succeeded/degraded targeted scope whatever its parent, and suggest is shown the existing options plus a code-side name/description match.
tags: [longlist, rebuild, option-search, suggest, incremental, task-045, invariant]
timestamp: 2026-09-24
---

# Rule

A rebuild is incremental (P12: only new entrants get an option search), so its reads must not be
scoped to the rebuild itself:

- **Records.** `longlist._option_search_scopes` returns, per option, the `evidence_scope` of its
  latest `succeeded`/`degraded` walk under a `targeted` record — this walk's children, an earlier
  build's, and the verb *add*'s parentless searches alike. Never "children of this walk".
- **Model step.** `suggest` receives `existing_options` and is told not to propose them again; in
  code, a suggestion whose name or description matches an existing option (case-insensitive,
  whitespace collapsed) is dropped. `(origin, name)` is not identity across two model runs — the
  same option comes back under different words.

# Why

- Records: code-review A1 and adversarial B1 converged — the longlist read
  `[context.scope_id, *children of walk_id]`, so a rebuild lost every earlier search's documents
  (membership is replaced task-wide), and an added option's search (parent `NULL`) was read by no
  build at all.
- Model step: the live T1 rebuild held 14 *from your evidence search* options for 7 report options
  before the fix (045 Phase 8; `longlist_suggest_v1` re-pinned).

# Watch out

- "Latest finished" needs the status-aware reading in
  [walk-existence-reads-intent-record-and-status](walk-existence-reads-intent-record-and-status.md):
  a failed search is retried, never read as done.
- The chat answer core reads the same scope set; how a document found by several scopes is
  attributed is [multi-scope-retrieval-primary-scope-wins](multi-scope-retrieval-primary-scope-wins.md).

# Citations

- `backend/src/policy_atlas/options_scoping/longlist/longlist.py` (`_option_search_scopes`, `longlist_scope`)
- `backend/src/policy_atlas/options_scoping/suggest/suggest.py` (module docstring § Rebuild)
- [045 verification.md](../tasks/045-scoping-longlist/verification.md) § Review findings (A1, B1); § Review handoff (knowledge candidates)
