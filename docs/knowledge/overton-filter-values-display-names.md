---
type: Integration quirk
title: Overton source_country takes display names and silently returns zero on anything else
description: Overton's source_country filter matches its own display-name vocabulary ("UK", "USA", "Canada"); ISO codes and full official names ("United Kingdom") return zero results with no error — live-probe filter VALUES, not just keys, before a prompt promises them.
tags: [search-backends, overton, openalex, scope-filters, live-probe, fail-closed]
timestamp: 2026-07-11
---

# Rule

Overton's `source_country` filter (the wire target of the planner's
`publisher_country` scope filter) matches **Overton display names** — `UK`, `USA`,
`Canada` verified live at 20/20 result agreement — and **silently returns zero
results** for ISO codes (`GB`) and full official names (`United Kingdom`). No error,
no warning: a well-formed request with the wrong value vocabulary looks exactly like
"no grey literature from that country".

OpenAlex behaves differently on the same concept: `authorships.countries` takes ISO
codes case-insensitively (`gb`|`GB`, 9.14M works) and **400s fail-closed** on invalid
filter keys.

The general rule: a fail-closed grammar on OUR side cannot protect against a
provider-side silent miss. Before a planner prompt line promises a filter, live-probe
the filter's **values**, not just its key — one probe per vocabulary family, comparing
filtered result counts/contents against an unfiltered control.

# Why

017 shipped the `publisher_country` key wire-verified but value-unverified (recorded
open item). Closing it in 018 B2 found the display-name hazard: every plausible-looking
value except Overton's own display names would have produced silently-empty grey-lit
scopes on live runs — invisible in tests (scripted fixtures echo whatever value they're
given) and misdiagnosable as thin coverage.

# Watch out

- The planner prompt's capability line states the display-name vocabulary explicitly;
  if the filter grammar grows values, re-probe.
- Any new search-backend filter inherits this: key verification (schema/400 behaviour)
  and value verification (does a *correct-looking but wrong* value fail loud or silent?)
  are separate checks.
- **There is no enumeration endpoint** (019 probed every documents.php param shape plus
  the API docs): display-name allowlists can only be built by per-candidate probing
  (019's `publisher_country` allowlist took 265 rate-limited `pp=1` calls). Overton's
  idiom is common short names ("UK", "USA", "South Korea") plus the non-country value
  "IGO"; 63 valid-ISO countries have no mapping and fail closed. Probe method + data
  are provenance-stamped in `src/policy_atlas/country_filters.py`.
- `source_country` is **single-valued**: every multi-value idiom (comma, pipe,
  repeated param, array param) fails silently — comma/pipe/array return zero, repeated
  params last-value-win (019 plan-time probes). Multi-country filtering on Overton is
  post-filter territory, never a wire param.

# Citations

- [018 verification.md § B2](../tasks/018-dress-rehearsal/verification.md) (A6 live
  probes; 017 open item closed)
- `publisher_country` capability line in `src/policy_atlas/planner_prompt.py`;
  `filters["overton"]` mapping in `src/policy_atlas/search_loop.py`
