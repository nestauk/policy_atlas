# ADR 0003 — Full-text snapshots attach at the corpus link, not as new corpus members

- **Status:** Accepted — 2026-07-05 (Shabeer Rauf, task-008 contract gate).
- **Date:** 2026-07-05
- **Context doc:** [task 008 contract, decision 2](../tasks/008-full-text/contract.md) ·
  [data-model § Corpus & source snapshots](../specs/system/data-model.md).

## Context

Task 007 acquires documents as metadata-envelope snapshots (`text_basis="abstract_only"`).
Task 008 fetches full text post-screen. Snapshots are immutable, content-hash-identified,
and retain no original bytes — so "the document now has full text" needs a representation
that neither mutates the envelope snapshot nor duplicates the document in the corpus.
Task 007 deliberately left this fork open ("new snapshot vs attach-to-existing").

## Decision

A successful full-text ingest creates a **new immutable `source_snapshot`**
(`text_basis="full_text"`, own content hash and chunks), referenced from the existing
corpus row by a nullable FK: **`project_source_snapshot.full_text_snapshot_id`**, with
`full_text_status` / `full_text_error` recording the fetch-pipeline outcome per document.

Rejected alternatives:
- **Mutating the envelope snapshot** (adding chunks, flipping `text_basis`) — breaks
  immutability and content-hash identity.
- **A second `project_source_snapshot` link for the full-text snapshot** — the document
  appears in the corpus twice; "acquired sources always screen" re-screens it;
  classify/appraise double-process; every future reader needs superseded-link semantics.

## Consequences

- Corpus membership stays one-row-per-document; all existing result-table FKs and
  screen/classify/appraise outcomes are untouched by ingestion.
- **Every future corpus reader (retrieve, extract, grounding, Q&A) follows one rule:**
  take the full-text snapshot's chunks when `full_text_snapshot_id` is set, else the
  envelope's. `text_basis` travels with whichever text a finding rests on.
- Fetch/parse failure is a queryable per-document state (`fetch_failed`/`parse_failed`
  + closed reason vocabulary), distinguishable from `not_attempted` — the source is
  never dropped.
- The spec's `supersedes` edge (human-asserted corrected re-upload) is untouched; this
  system-made attachment is a different relation.
- The full-text snapshot's governance identity is reachable via the link
  (metadata breadcrumbs `envelope_source_snapshot_id` + `ingested_by_run_id` →
  link → run → `search.executed` events).
