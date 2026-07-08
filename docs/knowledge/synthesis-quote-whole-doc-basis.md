---
type: Invariant
title: Chunk-claim quotes verify against the whole-document basis, one citation row per spanned chunk
description: The cited chunk id must be tool-returned and appraised, but the quote presence-check runs over every chunk of that document; verified spans each write their own citation row, so a citation row's chunk_id can name a chunk the section loop never received.
tags: [synthesise, citation, quote-verification, provenance, invariant]
timestamp: 2026-07-08
---

# Rule

In `_validate_chunk_claim` (`synthesise.py`), the **cited** `chunk_record_id` is gated
(tool-returned via `citable_chunk_ids`, appraised), but the quote itself is matched
against the cached **whole-document** basis (`substrate.basis_by_snapshot_id`). Every
verified span becomes its own citation row keyed to the **spanned** chunk id — including
boundary-spanning quotes and quotes that resolve entirely inside a sibling chunk the
tool never returned.

# Why

Contract rev 8 B2: chunk boundaries are a storage artifact, not an evidence boundary. A
verbatim quote that crosses or lands beside the returned chunk is still real document
text; rejecting it would punish honest quoting, and binding the row to the claimed
location would trust the model's location claim. Appraisal safety holds by construction:
spanned chunks share the cited chunk's document, so they share its appraisal status.

# Watch out

A citation row's `chunk_id` is therefore **not** proof that chunk was in the section
loop's context — `gathered_ids` in provenance is the record of what the loop saw. The
013 review stack's Codex lane flagged this as a "critical" escape before the contract
language settled it (verification.md § Review findings); don't re-litigate it as a bug.
