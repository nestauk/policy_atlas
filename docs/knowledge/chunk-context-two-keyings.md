---
type: Architecture note
title: Quote-in-context reads come in two keyings — artefact citation-table ids and durable chunk ids
description: repository.chunk_context_out resolves only artefact citation-table ids; chat citations carry durable chunk ids, so 029 added the chunk-keyed variant (chunk_quote_context_out + GET /projects/{id}/chunks/{chunk_id}/context?quote=). Any future non-artefact citation surface needs the chunk-keyed read, not the artefact one.
tags: [chunk-context, citations, read-models, chat, api]
timestamp: 2026-08-11
---

# Rule

Two clamped-window quote-in-context read models exist, same mechanics,
different keys:

- **Artefact citations** → `chunk_context_out`, keyed by the citation-table
  id (the artefact reader's hover).
- **Chat (and any future notebook-like surface)** → `chunk_quote_context_out`,
  keyed by durable `chunk_id` + the quoted text, exposed at
  `GET /projects/{id}/chunks/{chunk_id}/context?quote=` — because chat
  citations persist durable chunk ids, not citation-table rows.

Both are owner-scoped with the byte-identical-404 rule; on the chunk-keyed
route, `quote` is OPTIONAL in the signature and 422s only after ownership
resolves (a required query param 422s pre-handler and becomes an ownership
oracle — the 029 gate-integrity incident's second failure).

# Why

A non-verbatim model quote resolves to honest absence (404) and the popover
degrades to the stored quote + source title — quote fidelity itself is the
eval slice's measurement, not this read's job.

# Watch out

The two implementations share their window mechanics by parallel code, not a
common helper — they had already drifted once by review time. Fold them if a
third keying ever appears.
