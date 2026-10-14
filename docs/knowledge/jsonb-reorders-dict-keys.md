---
type: Integration quirk
title: Postgres JSONB returns dictionary keys reordered (shorter keys first, then by name) — compare values, not printed dicts
description: A dict written to a JSONB column comes back with its keys in Postgres's own order (by key length, then bytewise), so a test that prints a dict diff against a JSONB read sees a different key order with identical values; compare with == on dicts (order-insensitive) or sort before printing, and never build a fixture from a JSONB read-back expecting insertion order.
tags: [postgres, jsonb, testing]
timestamp: 2026-10-09
---

# Rules

- **Equality, not text.** `assert payload == expected` on dicts is order-insensitive and
  is the right check for a JSONB column; a `json.dumps` comparison or a printed diff is
  not.
- **Order-sensitive payloads need a list.** Anything whose order carries meaning (a
  ranked list, the executed call order) is stored as a JSON array, never as object keys.
- **Fixtures from JSONB read-backs are reordered.** Build a fixture from the Python
  value the code wrote, or sort keys on export.

# Why

The 051 single-pass tests compared coverage-record payloads against literal dicts and
printed diffs showed reordered keys for equal values; the diff was noise.

# Citations

- [051 verification § Review handoff, knowledge candidates](../tasks/051-improve-production-search-screen/verification.md)
- `backend/tests/evidence_search/sourcing/test_search_single_pass.py`
