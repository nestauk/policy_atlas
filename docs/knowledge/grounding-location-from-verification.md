---
type: Invariant (verified)
title: Grounding locations come from the verifier, never from the model's claim
description: A model-emitted location (segment/chunk id) is an unverifiable claim by untrusted output; the trustworthy location is the by-product of the deterministic presence check. Store the claim as data if useful, but derive every dereferenceable location field from verified spans.
tags: [extraction, grounding, provenance, quote-verification, security, untrusted-output]
timestamp: 2026-07-07
---

# Rule

When a model emits both a quote and a *location* for it (segment id, chunk id), the location
is a claim by untrusted output — the model can name any string, including another document's
real chunk UUID, and the quote can still verify because verification searches the whole
document basis. Any location field a consumer might dereference must therefore be **derived
from the verified spans** (where the deterministic presence check actually found the quote),
never copied from the claim.

In task 011's grounding entries: `segment_id` stores the model's claim verbatim (data, never
dereferenced), `spans` record where the verifier found the quote (chunk id + raw char
interval), and the top-level `chunk_id` is `spans[0].chunk_id` — `None` when unverified or
abstract-basis. Enforced by `test_chunk_id_is_verified_location_not_model_claim` (claim
names chunk B, quote lives in chunk A → `chunk_id` = A) and the fabricated-quote test
(`quote_verified: false` → `chunk_id` is `None` even when the claim names a real chunk).

# Why

The 011 review's highest-confidence finding — the only one both review families (Claude
security lane, Codex adversarial) surfaced independently. The original code derived
`chunk_id` from the claimed segment id, so a hijacked model could plant a foreign chunk
UUID beside `quote_verified: true`: cross-document provenance spoofing for any downstream
consumer (UI, group, report) that trusted the convenient top-level field over the spans.
This also matches the spec line the design already carried ("location is the recorded
by-product of the verify step", contract rev 1.3) — the claim-derived field contradicted it.

# Watch out

- The temptation recurs at every new grounding surface: the model's location field is right
  there in the wire record and *usually* correct. Usually-correct untrusted fields are the
  spoofing vector.
- If a future schema wants the claim surfaced (e.g. for verifier-quality evals), name it as
  a claim (`claimed_segment_id`), don't overload a field consumers dereference.

# Citations

- [011-extract/verification.md](../tasks/011-extract/verification.md) (§ Review findings)
- `_grounding_entry` in `src/policy_atlas/extract.py`
- Tests: `test_chunk_id_is_verified_location_not_model_claim`,
  `test_fabricated_quote_kept_and_flagged` in `tests/test_extract_contract.py`
