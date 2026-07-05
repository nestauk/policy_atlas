# ADR 0004 — Parsing: PyMuPDF4LLM in v3.0, versioned parse profiles as the upgrade seam

- **Status:** Accepted — 2026-07-05 (Shabeer Rauf, task-008 contract gate).
- **Date:** 2026-07-05
- **Context doc:** [task 008 contract, decision 5](../tasks/008-full-text/contract.md) ·
  parser-landscape research 2026-07-05 (raw file referenced there) ·
  [data-model — "Segmentation is trust-relevant"](../specs/system/data-model.md).

## Context

Parsed chunks are the permanent content-of-record (no bytes retained; one parse, one
segmentation per snapshot — re-parse is impossible by construction), so parser choice is
a substrate-quality decision, not an implementation detail. The 2026 landscape splits
into ML-layout parsers (docling 0.877 on opendataloader-bench — trained layout/table/
reading-order models; ~0.5–0.8 s/page CPU, torch + ~1 GB weights) and the PyMuPDF engine
(fastest classic extraction; structure via PyMuPDF4LLM's heuristics; ~0.02–0.1 s/page,
no ML stack). The repo is AGPL-3.0 (team decision, 2026-07-05), so PyMuPDF's AGPL is
licence-compatible. The user set a wall-clock target: ~a couple of minutes per
~100-document ingestion run — which docling on CPU misses by roughly an order of
magnitude, while on a GPU (T4/L4/A10G class) it lands near the target (~5–10× speedup;
AWS ops shape, not raw speed, is the binding constraint there).

## Decision

1. **v3.0 parses PDFs with PyMuPDF4LLM** (`parse_profile="pymupdf4llm_v1"`), HTML with
   **trafilatura** (`trafilatura_v1`), plain text directly (`plain_v1`).
2. **Every full-text snapshot records its named, versioned parse profile and
   segmentation policy in metadata** — the mechanism by which parser choice stays
   per-snapshot honest and upgradeable without rewriting history.
3. **Docling is the recorded quality-escalation seam, not a dependency**: a future
   `docling_v1` profile, entered via parse-quality evals (and a measured GPU spike on
   our own fixtures), for document classes where heuristic structure detection falls
   short.
4. **Time-budget-aware parser selection is a recorded seam**: the user's stated time
   horizon (and available hardware) steers parser choice per run — a plan/Config-carried
   setting behind its own interface gate, feeding the same profile mechanism.

## Consequences

- A ~100-document (~3,000-page) run ingests well inside the wall-clock target on CPU.
- Structure-aware chunking (heading-bounded sections, tables intact, page +
  heading-path locators) is available now via PyMuPDF4LLM's markdown structure; its
  heuristic limits (font-size heading inference, geometric table finding) are the
  accepted v3.0 quality ceiling, on the record.
- Snapshots parsed under different profiles can coexist; readers and evals can compare
  and selectively re-ingest under a better profile later (new snapshot, same attachment
  mechanism — ADR 0003) without any schema change.
- Length-based parser routing was considered and rejected (it would give the weakest
  parse to the document class that most needs structure — a type-correlated quality
  gradient); parse-time protection is a hard per-document timeout, never truncation.
