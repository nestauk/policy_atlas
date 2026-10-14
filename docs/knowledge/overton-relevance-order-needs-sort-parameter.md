---
type: Integration quirk
title: Overton documents.php returns date order with no scores unless sort=relevance is sent
description: Overton's search endpoint orders results by date by default and omits the es_score field; only sort=relevance returns relevance order and scores, so the production client sends sort=relevance on every search and protects the parameter from plan wire params, and a landmark fetched by id (policy_document_id) is accepted only when the reply echoes the requested id.
tags: [overton, search, ordering, egress]
timestamp: 2026-10-09
---

# Rules

- **Send `sort=relevance` on every Overton search.** Without it the first page is the
  newest documents, not the best matches, and no `es_score` is returned. Found in the
  task 049 experiments, fixed in task 051: `OvertonLiveBackend` adds the parameter and
  `_PROTECTED_OVERTON_PARAMS` refuses it from plan wire params, so a directive can never
  switch it off. `test_overton_relevance_sort_is_protected_and_counts_pages`.
- **Fetch by id checks the echo.** `fetch_by_id(policy_document_id)` returns the record
  only when the reply's id equals the request; a mismatch is a transport error, not a
  record. The landmark step (the 15 most-cited documents the search did not return)
  relies on it.
- **Landmarks carry no wire filters.** A landmark is checked locally against
  `source_country_post_filter` only; a dated plan can admit a landmark outside its range
  (seam in `docs/deferred.md`, task 051).

# Why

The task 049 replay showed the date-ordered first page missing the documents the
relevance order puts first; the single-pass policy pool (400 relevance-ordered documents
over three texts, title dedup, landmarks, specificity cut) depends on the order.

# Citations

- [051 contract D8](../tasks/051-improve-production-search-screen/contract.md)
- [049 notes](../tasks/049-improve-overton-search/notes.md)
- `backend/src/policy_atlas/evidence_search/sourcing/search_live.py` (`OvertonLiveBackend._search`, `fetch_by_id`, `_PROTECTED_OVERTON_PARAMS`)
