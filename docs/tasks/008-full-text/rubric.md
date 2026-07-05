# Rubric: 008-full-text

Core completion criteria. The task is **done only if every box holds** — otherwise it is in
progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) (rev 4).
2. [ ] `make verify` passes (test · typecheck · lint · build); all checks deterministic
       (pinned parser + model versions; fixture replay).
3. [ ] No approval-gated change snuck in unapproved — schema limited to the three approved
       columns on `project_source_snapshot`; dependencies limited to `docling` +
       `pymupdf4llm` (+`pymupdf`) + `trafilatura`; public interface limited to the
       `document_fetcher` parameter + registry entry; **zero runtime egress** (fixture
       replay only; docling parses offline from the dev-time-pinned model cache; recorder
       script never imported by the package); no auth/CI/production config change.
4. [ ] No generated files or secrets edited by hand; no credentials anywhere in the slice.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)), including the
       exact end-to-end command, the migration roundtrip, the envelope-immutability,
       no-truncation long-report, fan-out determinism, offline-parse and
       fallback-visibility results, and the measured long-document wall-clock/peak-memory
       numbers.
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md):
       live `DocumentFetcher` (timeouts, redirects, politeness + per-host rate limiting,
       content-type sniffing, landing-page scrape + PDF-link discovery, DOI-URL fallback,
       retry/backoff) · chunk-volume bias controls at the retrieve seam (per-document
       caps / MMR / document-grain grouping) · OCR for `no_text_layer` documents ·
       vectorisation at the first
       vector reader (eager-and-uniform discipline restated; token-budgeted chunk sizing
       with it) · multi-PDF Overton assembly · injection-screening posture extended to
       fetched full text · cross-project full-text snapshot reuse.
8. [ ] Every eligible link lands in exactly one counted bucket
       (`eligible == ingested + already_ingested + fetch_failed + parse_failed +
       skipped_no_url`) — invariant test-enforced; failure is queryable per document
       (`full_text_status` + closed-vocabulary `full_text_error`), never only logged.
9. [ ] **No truncation path exists**: a stored `full_text` snapshot is the whole parsed
       document; over-cap and over-time fail loudly (`too_large`, `timeout`); the
       long-report fixture ingests to its final section (test-enforced).
10. [ ] Envelope snapshots byte-identical before/after ingestion (immutability
        test-enforced); both snapshots carry honest `text_basis`; every chunk carries a
        page/heading-path (PDF) or paragraph locator; parse profile + segmentation policy
        named and versioned on every full-text snapshot — **including honest
        `pymupdf4llm_v1` profiles on fallback parses, counted per run** (a docling→fallback
        downgrade is queryable, never silent).
11. [ ] Ingestion fan-out is real and deterministic: workers=1 vs workers=4 produce
        identical DB state (test-enforced); the worker parameter is wired, not dead config.
12. [ ] Every committed fixture document carries an allowlisted licence (own-org · CC BY
        family) with source URL, publisher and retrieval date in the manifest —
        licence-guard test-enforced; no paywalled or all-rights-reserved content committed.
13. [ ] Required review stack ran for Tier 3 (contract verifier · `/code-review` medium ·
        one security lane · adversarial review) or skipped with written justification —
        findings in [verification.md](verification.md).
