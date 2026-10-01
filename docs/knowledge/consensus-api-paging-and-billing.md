---
type: Integration quirk
title: Consensus API pages are zero-indexed, refuse to cross 1,000, and bill every call on our account
description: Consensus answers HTTP 400 to any page where (page + 1) x page_size > 1000 and sends next_page null one page early, so at the plan's echoed size 300 the last request must be page 9 at size 100; pages hold a few results fewer than their size, so paging arithmetic must count positions, not results; our API beta account is billed $0.05 per call (one call per 100 results returned) with no included amount.
tags: [search-backends, consensus, paging, billing, evaluation, live-probe]
timestamp: 2026-09-25
---

# Rules

- **Pages start at 0.** `page_size` defaults to 20 and is silently capped to the plan's
  maximum; read the `page_size` the response echoes and use it for every later page.
  Our account echoes **300** (a Pro or Teams size table).
- **The 1,000-result ceiling is enforced per request, not per result.** A page where
  `(page + 1) x page_size` would pass 1,000 is answered **HTTP 400**, and `next_page` is
  `null` on the page before it. At size 300 that leaves positions 900-999 unreachable at
  that size: ask for them as **page 9 at size 100** (750 -> page 3 at size 250). When the
  remainder cannot be asked for as one page at some size, stop and say the fetch is
  incomplete; do not report it as complete.
- **Count positions, not results.** Pages return a few results fewer than their size
  (297, 299, 294 for size 300). A stop rule written as "results so far >= 1,000" never
  fires; write it as "positions covered >= 1,000".
- **Billing.** One call per 100 results returned in a page, rounded up, minimum one per
  request. Our **API beta account pays $0.05 on every call with no included monthly
  amount** (owner, 2026-09-25); the public docs' "included calls, then overage" model does
  not apply to it. A full fetch of one review to 1,000 results is 10 calls, $0.50. Never
  re-fetch (`--refresh` in `baseline_recall.py`) without the owner.
- **Date filter is month-grained** (`year_max`, `month_max`), so a cutoff of the 17th lets
  up to 30 more days through. Say so wherever the numbers are compared with a day-grained
  filter.

# Why

Task 046's first live Consensus fetch stopped at position 900 for every review: the
build's plan rule ("stop when the next page would pass 1,000") was written for a service
that clips the last page, and Consensus refuses it instead. The probe cost one failed
request and a hand `curl` (400) to find. The fix reached 992-998 results per review at the
same 10 calls.

# Watch out

- The price of a cap computed from cached pages is the price of the **pages that cover
  the cap at the echoed size**, not of a request sized to the cap: at size 300, caps 50,
  100 and 200 all cost one request of three calls. Label it as such, see
  [eval-cost-figures-name-their-unit](eval-cost-figures-name-their-unit.md).
- The site blocks plain fetchers; `https://docs.consensus.app/llms-full.txt` is the same
  documentation as text.

# Citations

- [046 contract § Arms](../tasks/046-search-baselines/contract.md) (facts pinned from the
  Consensus docs, 2026-09-25)
- [046 verification § Consensus preflight and flagged deviation 1](../tasks/046-search-baselines/verification.md)
- `scripts/evals/search/baseline_recall.py` `fetch_consensus`, `cost_usd`;
  `test_metrics.py::test_baseline_paging_consensus`
