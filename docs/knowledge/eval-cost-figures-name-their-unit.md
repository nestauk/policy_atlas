---
type: Convention
title: An eval cost figure names what it counts — computed or spent, pages or cap, api or llm
description: A dollar figure in an eval table is honest only with its unit attached — whether it was computed from a price table or actually spent, whether it prices the provider pages a cached fetch used or a request sized to the cap, and whether it is search-service (api) or language-model (llm) money; sub-cent amounts print at four decimals or they read as free; and a fetch-once cache must check the request it was made for, not just the entity id, before it serves results.
tags: [evaluation, cost, langfuse, cache, honesty]
timestamp: 2026-09-25
---

# Rules

- **Computed is not spent.** A per-run cost derived from a price table (calls x price) is
  a *computed* figure. The money a run actually spent goes in the verification record.
  With a fetch-once cache the two differ by design: the service is paid once, every cap is
  scored from the same pages.
- **Say whether the cap or the pages are priced.** Scoring several caps from one cached
  fetch prices the provider pages that *cover* the cap at the page size the service
  returned. That is not "what this cap would cost on its own" when the service accepts
  smaller requests: Consensus at page size 300 makes caps 50, 100 and 200 all cost one
  three-call request, three times the price of a 50-result request. Either compute the
  cap-sized price or label the figure as page-priced. 046 labelled it.
- **Label the money's source.** `api` for search-service calls, `llm` for the model spend
  Langfuse attributes to the run's traces (`TraceWithFullDetails.total_cost`), summed over
  the run's reviews (a sum, never a mean). Neither includes flat subscriptions, compute or
  Langfuse. See [langfuse-cost-by-time-window](langfuse-cost-by-time-window.md) for the
  window method when no run key exists.
- **Sub-cent amounts print at four decimals.** OpenAlex reports `meta.cost_usd` of 0.0001
  per page with a key, so a two-decimal column shows $0.00 and reads as free. One shared
  formatter (`history.usd`) serves every table.
- **A fetch-once cache checks the request, not only the entity.** A cache file keyed on
  the dataset item id must also store and compare the intent and cutoff it was fetched
  for; otherwise an edited item is scored against stale results with zero calls and no
  warning (046 review, convergent Codex and Claude finding).

# Why

046 introduced the first computed cost column next to Langfuse's spent figures. The review
stack found three ways it could mislead without being wrong: the page-priced Consensus
figure under a "cap on its own" label, OpenAlex at $0.00, and a cache that would have
served old results for an edited review.

# Citations

- [046 contract D4 and D9](../tasks/046-search-baselines/contract.md)
- [046 verification § Review findings 1 and 3](../tasks/046-search-baselines/verification.md)
- `scripts/evals/search/history.py` `usd`, `fetch_runs`;
  `scripts/evals/search/baseline_recall.py` `cost_usd`, `pages_for_cap`, `read_cache`;
  `scripts/evals/search/README.md` § The variable cost column
