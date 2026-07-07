---
type: Invariant
title: Untrusted directive parsing — malformed fails closed, unknown references flag
description: Execution-bearing JSONB inputs (the selection directive) are parsed fail-closed with bounded strings and collections; structurally malformed input raises DirectiveError, but a well-formed reference to an unknown column/tag matches nothing and is flagged non-fatally.
tags: [select, directive, untrusted-input, fail-closed, flag-not-block, invariant]
timestamp: 2026-07-07
---

# Rule

The selection directive is user/plan-authored JSONB (`evidence_scope.context["selection"]`) —
an untrusted, execution-bearing input. Its parse (`_parse_directive` in `select.py`) splits two
cases that look similar but must behave differently:

- **Structural malformation fails closed** — unknown keys, wrong types, out-of-range or
  NaN/inf weights, invalid UUIDs, control characters or over-length strings
  (`DIRECTIVE_STRING_MAX`), over-cap budgets (`DIRECTIVE_BUDGET_MAX`) and oversized lists
  (`DIRECTIVE_LIST_MAX`) all raise `DirectiveError` with a **static message** before any
  work runs. No silent run on a bad directive.
- **Unknown references flag non-fatally** — a well-formed boost naming a column or tag the
  data doesn't have matches nothing and surfaces in `selection_provenance.unmatched_boosts`
  (likewise unmatched priority patterns). The run completes; the author sees the miss.

# Why

The two cases have different authors' intents: malformation means the input is *broken*
(fail loudly so the author fixes it — the plan-compile posture,
[plan-compile-fails-closed](plan-compile-fails-closed.md)); an unknown reference is *speculative vocabulary* over open
data (tags are an open namespace; failing the run would make every directive brittle
against corpus drift). Bounding strings and collections at parse also closes log-injection
and resource-burn paths before any O(boosts × candidates) matching runs.

# Watch out

The 010 build initially failed closed on unknown *columns* while flagging unknown *tags* —
both review families independently flagged the asymmetry against the contract. Keep the
split by *shape*, not by field: structure → closed, reference → flagged. And keep every
`DirectiveError` message static — never reflect directive content into errors or logs.

# Citations

- [010-select/contract.md](../tasks/010-select/contract.md) (decision 4: soft boosts, unknown references flagged, malformed directives caught)
- [010-select/verification.md](../tasks/010-select/verification.md) (§ Review findings: the convergent unknown-column finding and the security lane's bounds)
- `src/policy_atlas/select.py` (`_parse_directive`, `_string_value`, the `DIRECTIVE_*` caps); `tests/test_select.py` (`test_unknown_column_boost_is_flagged_non_fatal`, `test_malformed_directive_shapes_raise`)
