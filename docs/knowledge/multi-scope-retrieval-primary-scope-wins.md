---
type: Invariant
title: Retrieval over several scopes attributes a document to the primary scope first
description: An options-scoping chat answers over the longlist scope plus every option search's targeted scope. build_retrieval_scope keeps one row per task_source_snapshot — the primary scope's row wins, then the latest screen — so a citation that "reads as" a longlist document may equally be the option search's. 045's live check (g) was misread as failing for exactly this reason.
tags: [retrieval, synthesis-tools, scopes, options-scoping, chat, task-045, invariant]
timestamp: 2026-09-24
---

# Rule

`synthesis_tools.build_retrieval_scope(..., extra_scope_ids=...)` (P13):

- The corpus is the effective-relevant documents of the primary scope **and** every extra scope
  ([effective-screen-row-read-rule](effective-screen-row-read-rule.md) per scope).
- A document screened in under several scopes is **one** document: `row_number()` over
  `task_source_snapshot_id`, ordered primary scope first, then `screened_at` desc, then scope id.
  The winning row's scope supplies its classification and appraisal.
- With no extra scope the rule is inert — ES retrieval is unchanged.

So attribution names **one** of the scopes that found a document, by precedence — not the one
that found it for this question. To ask "did the option search find this?", query that scope's
screening rows, not the citation's scope.

# Why

045 Phase 8 wrote (g) — "an added option's search reaches the answer" — as unverified, because
both cited documents were attributed to the longlist scope. The step-7 live-trace review showed
both were screened in by the added option's own search *and* the longlist scope; precedence put
them under the longlist. The check had passed.

# Watch out

- ES retrieval was touched by this change for multi-scope calls only (contract verifier F16);
  a single-scope caller never sees the rule.
- A read model that counts "documents per scope" must not derive it from retrieval attribution.

# Citations

- `backend/src/policy_atlas/evidence_search/synthesis/synthesis_tools.py` (`build_retrieval_scope`, `_scope_precedence`)
- [ADR 0039](../adr/0039-options-scoping-longlist-option-searches-and-option-records.md)
- [045 verification.md](../tasks/045-scoping-longlist/verification.md) § Review findings (live-trace content review (g); F16)
