# Rubric: 008-full-text

Core completion criteria. The task is **done only if every box holds** — otherwise it is in
progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes (test · typecheck · lint · build); all checks deterministic.
3. [ ] No approval-gated change snuck in unapproved — schema limited to the three approved
       columns on `project_source_snapshot`; dependencies limited to `pypdf`; public
       interface limited to the `document_fetcher` parameter + registry entry; **zero
       runtime egress** (fixture replay only; generator script never imported by the
       package); no auth/CI/production config change.
4. [ ] No generated files or secrets edited by hand; no credentials anywhere in the slice.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)), including the
       exact end-to-end command, the migration roundtrip, and the envelope-immutability,
       thin-text and cascade-fallback test results.
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md):
       live `DocumentFetcher` (timeouts, redirects, politeness, content-type sniffing,
       landing-page scrape + PDF-link discovery, DOI-URL fallback, fetch pacing) ·
       vectorisation at the first vector reader (eager-and-uniform discipline restated) ·
       multi-PDF Overton assembly · injection-screening posture extended to fetched full
       text · cross-project full-text snapshot reuse.
8. [ ] Every eligible link lands in exactly one counted bucket
       (`eligible == ingested + already_ingested + fetch_failed + parse_failed +
       skipped_no_url`) — invariant test-enforced; failure is queryable per document
       (`full_text_status` + `full_text_error`), never only logged.
9. [ ] Envelope snapshots byte-identical before/after ingestion (immutability
       test-enforced); both snapshots carry honest `text_basis`; parse profile +
       segmentation policy named and versioned on every full-text snapshot.
10. [ ] Required review stack ran for Tier 3 (contract verifier · `/code-review` medium ·
        one security lane · adversarial review) or skipped with written justification —
        findings in [verification.md](verification.md).
