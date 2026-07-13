---
type: Invariant
title: Cross-parameter validation must run on effective (defaulted) values, not explicit arguments
description: query_findings' kind/filter mismatch check only fired when `kinds` was explicitly present; the omitted-kinds DEFAULT (both kinds) skipped the check entirely, so a kind-specific filter returned the other kind unfiltered — a fail-open path created by validating the raw argument instead of the resolved value (021 review stack, Codex adversarial catch).
tags: [validation, fail-closed, tool-arguments, synthesis-tools, defaults]
timestamp: 2026-07-13
---

# Rule

When an argument has a default, cross-parameter validation must be applied to
the **effective** value after defaulting — never guarded behind
`arg is not None`. A check written as
`if filter and kinds is not None and kind not in kinds: fail` silently
exempts the default path, which is usually the *most common* path a
tool-calling model takes. Resolve first
(`effective = parsed if parsed is not None else DEFAULT`), then validate the
resolved value unconditionally.

# Why

021's `query_findings` documented "a mismatched kind/filter combination is an
error", and tests pinned the explicit-kinds mismatch — but
`{"context_type": "barrier"}` with `kinds` omitted defaulted to both kinds,
skipped the guard, and returned the entire IOF list unfiltered alongside ICF
barriers, violating the contract's fail-closed pin (rubric item 11). The
Claude lanes read the same code as clean; the heterogeneous Codex adversarial
pass caught it — the class hides well because each branch looks locally
correct. The fix also tightened semantics: a kind-specific filter now requires
`kinds` to name exactly its own kind.

# Watch out

- Test the DEFAULT path of every cross-parameter rule explicitly; pinning only
  the explicit-argument path is what let this ship.
- Same family: [plan-compile-fails-closed](plan-compile-fails-closed.md),
  [directive-parse-malformed-vs-unknown](directive-parse-malformed-vs-unknown.md).
