# Rubric: 016-live-fetch

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) as approved
       (including any gate-recorded revisions).
2. [ ] `make verify` passes — deterministic and zero-egress: the fixture
       fetcher remains the default everywhere; the egress guard extends to
       the live module's import boundary.
3. [ ] No approval-gated change snuck in unapproved — schema, auth/tenancy,
       egress beyond the approved fetcher, deps, CI, production config,
       public interfaces, scaffold (see the contract).
4. [ ] No generated files or secrets edited by hand; no fetched document
       bytes committed.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] SSRF guards test-pinned: scheme allowlist · private/loopback/
       link-local/metadata IP refusal · per-hop redirect re-validation ·
       refusals are per-URL reason-coded failures, never crashes.
7. [ ] Resource bounds test-pinned: explicit timeouts on every request ·
       size cap enforced against both Content-Length and streamed body ·
       total prefetch buffering capped · per-host politeness (concurrency +
       min interval) observed with an injected clock.
8. [ ] Per-link exception isolation holds: a raising/failing fetch yields a
       reason-coded outcome; the component never fails because documents
       failed; flag-not-drop — unfetchable sources stay, `text_basis`
       labelled.
9. [ ] Content handling test-pinned: magic-byte-first classification (PDF as
       octet-stream never reaches the plain-text parser) · charset path per
       contract decision 6 · landing-page discovery and DOI fallback bounded
       exactly as contracted.
10. [ ] The chain-composition rule (contract decision 9, Option A) is
        implemented as adopted: every profile's chain includes the ingest
        leg; synthesise's substrate gate untouched; components §9 +
        capability.md flow-back with `log.md` entry and an ADR recording
        the mandatory spine.
11. [ ] The access-failure ladder (contract decision 8) is test-pinned:
        401 vs corroborated-403 vs `blocked_by_host` vs 200-with-markers;
        the OA cross-check logs inconsistencies; bot-blocks are never
        counted as paywalls.
12. [ ] The pinned live check ran and is evidenced in
        [verification.md](verification.md): live fetch/ingest outcome
        distribution recorded (observed counts, no pinned targets) · the
        mandatory-spine chain smoke WITH the ingest leg (discharging the
        015 rev-3.14 deviation) · wall-clock per leg recorded.
13. [ ] Verification evidence recorded (verification.md), including the
        exact end-to-end commands run.
14. [ ] Known gaps and deferred seams updated in
        [docs/deferred.md](../../deferred.md): discharged entries marked
        (live `DocumentFetcher`; the pip-audit CI pre-registration;
        stage-2 windowing rider if landed), kept
        seams intact (docling/OCR · multi-PDF assembly · caching ·
        component-progress protocol · corpus relocation · per-depth fetch
        budgets).
15. [ ] Required review stack ran for Tier 3 (contract verifier ·
        code/security review · adversarial review · human deep review), or
        skipped with written justification — findings in verification.md.
