---
type: Convention
title: A result cap belongs per call, not shared across a fan-out
description: A cap that bounds a shared total silently starves a fan-out — divided across N queries it shrinks as N grows, and consumed serially it lets call #1 eat everything and skips the rest. Size caps per call, against the provider's page size, and bound total volume separately.
tags: [search, budgets, fan-out, live-behaviour, convention]
timestamp: 2026-08-04
supersedes_guidance_dated: 2026-07-09
---

# Rule

A per-call result cap (`max_records` on one provider call) and a total-volume
ceiling are **two different bounds**, and one cannot serve as the other.

- **Per call:** size it against the provider's *page size*, not against "as much
  as we can afford". `search_loop.py`'s `result_cap_per_backend` is per call, and
  each depth's value stays within two Overton pages (page 50) / one OpenAlex page
  (page 200), so one logical call is 1–2 real HTTP requests.
- **Total volume:** make it an explicit separate bound, applied where the volume
  gets *spent* rather than where it is fetched. `acquire_sources`'s
  `record_cap_per_backend` is that bound: it trims after a rank-interleaved merge
  across the fan-out and after dedup, so no query is skipped and no repeat
  consumes a slot. Do not implement it by dividing or serially consuming a
  per-call cap.

# Why

Both failure modes have now been seen live, one from each direction.

**Serial consumption (015 live check).** With `max_results = cap - consumed`,
OpenAlex call #1 returned the entire 50-record cap, the remainder hit zero, and
all 14 later planned queries were skipped — silently, because skipping at
cap-exhaustion is correct for each call in isolation. The fix at the time was a
`_distribute_quota` helper dividing the total across the planned fan-out.

**Division (the 2026-07-30 hotfix).** That helper then became the bug. As the
SR/RCT variant fan-out widened to 15 OpenAlex calls, the standard cap of 75
divided to **5 results per query** — recall collapsed, and again nothing errored.
A cap divided by fan-out width shrinks every time the fan-out grows, so the two
numbers are coupled in a way nobody remembers to maintain.

The lesson is that the shared *total* was the defect in both cases. Per-call caps
have neither failure mode: they do not shrink as the fan-out widens, and no call
can consume another's allowance.

# Watch out

- **A time budget over a fan-out is a third way to build the same silent skip.**
  Overton enforces a 1.2 s gap per request and pages at 50, so a per-call target
  far above a page is ~12 s of enforced sleep *per query*. The depth's
  `wall_clock_s` then expires part-way through the fan-out and `execute_call`
  sets `stop_all`, skipping every remaining query. Worse, backends run in order
  (`[openalex, overton]`), so a slow first backend costs the second one *all* of
  its calls — a whole evidence source, and the run still reported `adequate`.
  Task 028 removed the clock for standard and deep for exactly this reason: a
  budget enforced by *stopping early* always truncates the tail of an ordered
  fan-out, and the tail is a specific set of queries and providers, not a random
  sample. Bound the volume instead, after the merge, where every query has
  already had its turn. Task 029 removed rapid's clock too (with a rapid
  record cap replacing its volume role): no depth has a time budget, and if a
  latency bound is ever needed it belongs at the runner as a step timeout,
  never inside the fan-out.
- **`http_budget` counts logical `execute_call`s, not HTTP requests.** Backends
  paginate internally to satisfy `max_results`, so per-call targets above one page
  make the budget's name a lie. Keep targets near a page, or count pages.
- **Nothing downstream bounds volume**, so the bound has to bite at
  acquisition. `_load_stage1_docs` has no LIMIT and screens every unscreened
  snapshot in scope, and `acquire_sources` embeds each record as it persists it —
  so persisting a record is committing to both costs. That is why
  `record_cap_per_backend` trims *before* the write rather than filtering at
  screening time. Owner-set (task 029): rapid 50 / standard 100 / deep 200 per
  backend per round — sized from methodology, not against the provider's
  willingness to return rows. Replace with a measurement from
  `scripts/eval_ground_truth/` (other branch), which scores search recall
  against published systematic-review ground truth.
- Bounds sized on fixtures need one live run where they actually bind before
  they are trusted (see also
  [sanitized-fixtures-audit-against-raw](sanitized-fixtures-audit-against-raw.md)).
  Both defects above were invisible to scripted tests: fixture pages were too
  small for the cap to bind, and no test bounded total volume at all.
