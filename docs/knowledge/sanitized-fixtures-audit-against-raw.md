---
type: Testing rule
title: Audit sanitized fixtures against the raw recording, not the sanitizer's key list
description: Key-based sanitizers silently miss fields (list items inherit the list's key; rare fields like funder_award_id appear only in some records) — the only reliable check is asserting no identifying raw string value survives into the committed fixture.
tags: [fixtures, sanitization, public-safety, recorder, testing]
timestamp: 2026-07-05
---

# Rule

When a recorder derives committed fixtures from real API responses, verify the output by
**substring-auditing the raw recording against the fixture text** (no identifying raw string
value — title, name, org, id, URL, award/grant number — may survive), not by reviewing the
sanitizer's key list. Marker checks (fake-DOI prefix, `example.org` URLs) catch only the
classes they encode.

# Why

Task 007's sanitizers were written from inspected API shapes and still leaked three ways
before the audit caught them:
- **List items inherit the list's key** in a recursive walker — rules written against a
  `parent` check missed `raw_affiliation_strings[]`, `grouped_pdf_ids_in_result[]`,
  `source_tags[]`.
- **Rare fields appear only in some records** — `awards[].funder_award_id` (real, indexed
  grant IDs; one OpenAlex query re-identifies the record) existed in 4 of 25 raw works and
  wasn't in the key list. Found by the security lane, after two audit rounds.
- **Values echo under second keys** — the same journal name arrived under `raw_source_name`
  and `host_organization_lineage_names[]` after `display_name` was handled.

A neutral (non-domain) fake lexicon matters too: domain-flavoured fake words collide with real
values in substring audits and mask genuine leaks as false positives.

# Watch out

- Re-run the audit whenever a recorder is re-run or the provider adds response fields —
  `--resanitize` re-derives from the raw recording without a refetch.
- The committed leak-guard test (`test_fixture_leak_guard`) enforces markers (DOIs, URLs,
  hashed award ids); it does **not** replace the dev-time raw-vs-fixture audit, which needs
  the (gitignored) raw file.
- Raw recordings can embed the API key via echoed pagination URLs — the Overton recorder
  redacts on write; keep that invariant if the write path changes.

# Citations

- [007-acquire/verification.md](../tasks/007-acquire/verification.md) (§ Review findings —
  security lane; § Public safety)
- [scripts/record_openalex_fixtures.py](../../scripts/record_openalex_fixtures.py) /
  [record_overton_fixtures.py](../../scripts/record_overton_fixtures.py) (sanitizer v2)
- [sanitized-fixtures policy](../tasks/007-acquire/contract.md) (§ Public / private boundary)
