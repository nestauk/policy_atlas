---
type: Testing rule
title: The live search transport caches responses process-wide — tests that build a live backend around a scripted fetch must start with the cache empty
description: search_live keeps a module-level response cache keyed by URL and parameters (never the API key) with a one-hour life; two tests in one pytest process that request the same URL through live backend classes share it, so one test's reply answers the other's request (an Overton page-2 reply without a next page cut a later test's search to two pages); an autouse fixture in backend/tests/conftest.py empties the cache before every test, and a test that wants a cache miss must not rely on the TTL environment variable alone.
tags: [testing, cache, search, flakiness]
timestamp: 2026-10-09
---

# Rules

- **Assume the cache is shared.** `search_live._SEARCH_CACHE` is one ordered dict per
  process, keyed by `(url, params minus the key)`, TTL `POLICY_ATLAS_SEARCH_CACHE_TTL_S`
  (default one hour). A live backend built in a test with a scripted `fetch` still reads
  and writes it.
- **Start every test empty.** `backend/tests/conftest.py` has an autouse fixture that
  clears the cache before each test. Setting the TTL to zero in one test does not clean
  what an earlier test stored.
- **Pair tests by URL when hunting an order-dependent failure.** The 051 review
  bisected the failing test against every earlier test in its file and found no single
  pair; the trigger was a *different file* run in the same process. Reproduce with the
  two files together before bisecting within one.

# Why

Found at the 051 review when the wire tests and the single-pass tests ran together:
`test_logical_calls_count_pages_and_retries_once` saw Overton pages `[2, 2]` instead of
`[3, 3]`, alone it passed every time.

# Citations

- [051 verification § Review findings](../tasks/051-improve-production-search-screen/verification.md)
- `backend/tests/conftest.py` (`_empty_search_cache`);
  `backend/src/policy_atlas/evidence_search/sourcing/search_live.py` (`_SEARCH_CACHE`)
