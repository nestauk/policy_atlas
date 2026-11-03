# Rubric: 057-queued-ingest

Core completion criteria. The task is **done only if every box holds**, otherwise it is in
progress. Item numbers point at [contract.md](contract.md) (revision 2): N1 to N14, D1 to
D14, G1 to G8, S1 to S5. Terms are defined in the contract's § Terms.

Core
1. [ ] Implementation satisfies [contract.md](contract.md) for every need N1 to N14.
2. [ ] `make verify` passes at the build-open baseline, after the schema phase, after the
       retrieval phase and at the step-6 exit; `make -C infra test` passes with the CDK changes.
3. [ ] No approval-gated change beyond G1 to G8: the D2 migration, the `awslambdaric`
       dependency, the N11 resources and config, the function's egress, the Dockerfile line.
       No prompt-text re-pin, no public-interface change; code-only re-pins recorded with diffs.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification (the scheduler
       tests that N6 deletes are listed with the behaviour that replaces each).
6. [ ] Verification evidence recorded ([verification.md](verification.md)) as the contract's
       § Verification evidence lists, read from saved results.
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md): the
       header, page-number and footnote parse rules with E6's numbers (D8), the fallback
       parser trigger signals, per-host coordination across functions (D11), the retention
       script's scheduling (D3), HNSW, the low-effort judge and per-claim judge filtering with
       E3 and E9's numbers (D14).
8. [ ] Required Tier 4 review stack ran (contract verifier · code and security review ·
       adversarial pass at contract and plan stage · simplification) or skipped with written
       justification; the ADR is Accepted; the rollback plan is written and the downgrade
       tested.

Queue and function (N1 to N5, D1, D4, D5, D13)
9. [ ] N1: one message per attempted document; the message carries no user identifier (test).
10. [ ] N2: the handler produces the same statuses and reason codes as the in-process path on
        the committed fixture corpus; a second delivery of the same message is a no-op; a 429
        with Retry-After is waited for (capped) and a still-refused document is redelivered
        with a delay, not failed.
11. [ ] N3: the queued stage returns the counts dict with its invariant intact under the three
        fake-queue scenarios (all early, some late, deadline hit); progress ticks carry the
        store's counts; `already_in_store` is reported.
12. [ ] N4, N5: timeout 180 s, memory 1,769 MB, storage 512 MB, stage deadline 600 s, SQS
        visibility timeout at least 6 × the function timeout, dead-letter after 2 attempts,
        concurrency cap and alarm pinned by infra tests; the plan records the connection
        arithmetic against the writer instance.
13. [ ] D5: the function is the backend image with another command; the parse step runs in a
        subprocess with the 120 s kill and denied sockets; the function runs in the private
        subnets with no S3 and no new endpoints.
14. [ ] D13: under simulated throttling the function's embedding backs off up to the function
        timeout; a document that still cannot embed is `parse_failed` with reason
        `embed_timeout` and holds no chunks without vectors (test).

One code path and the markup rule (N6, N7, N14, D8)
15. [ ] N6: the scheduler and batch hand-over are gone; the per-document function serves both
        modes; the byte-identical digest holds across worker counts 1 and 4 on the fixture
        corpus under profile v2.
16. [ ] N7: on the control PDFs markup-bearing chunks go from 186 to 0 with tables and heading
        paths unchanged; the funnel re-run on the fixed questions holds the PDF quote failure
        rate at or below 0.7%; new profile and policy names on every route whose text changed;
        existing snapshots and citations untouched.
17. [ ] N14: the quote matcher strips markup on the quote side (tests both ways).

Store and retrieval (N8, N9, D2, D3, D7)
18. [ ] D2: migration upgrades and downgrades on the test database; backfill timings recorded
        on dev and staging; the JSONB vector column's fate matches the owner's ruling.
19. [ ] N8, D7: the SQL retriever returns the same top-8 in the same order as the Python
        retriever for the 20 saved queries and the fixed questions' replayed section queries;
        both callers use it; the in-memory scope load, the Python scoring and the unit cap are
        deleted; retrieval provenance records the factors for the returned candidates; the
        embedding write time per run is recorded before and after.
20. [ ] N9, D3: one snapshot for the same bytes across two tasks; embeddings added per profile
        without a second parse; the shared row carries no task or user id (test on the
        columns); `already_in_store` appears in the counts on a live overlapping run.

Timeouts and widths (N10, D12)
21. [ ] N10c, D12: every step in `model_routes.toml` carries `timeout_s`; every model client
        reads it; values are 2 × healthy p99 with the 5 s floor, derived from saved traces and
        listed in verification.md; on the fixed questions no call waits longer than its step's
        timeout plus a normal retry, stalled calls still succeed, any step whose retry was also
        slow is named and raised once; synthesise wall before and after recorded; the owner's
        read finds the reports unchanged in content. Section order and the ledger untouched.
22. [ ] N10a: the cause of the 900 s scoping calls is located and fixed; no call over 300 s on
        the fixed scoping question after the change.
23. [ ] N10b: option-search width 4 → 10 measured on the fixed scoping question; no new 429s;
        or reverted with the measurement recorded.
24. [ ] N10d: screen stage 1 and classify widths 12 → 48 measured on the fixed questions; stage
        walls and 429 counts before and after; or reverted with the measurement recorded.

Infra, image, measurement and governance (N11 to N13, D6, D9, G4, G7, G8)
25. [ ] N11: staging deploys with the function, queue, dead-letter queue, alarm and
        `ingest_mode = queued`; `cdk diff` reviewed at the plan gate; production config stays
        `in_process` unless the owner rules otherwise.
26. [ ] N13, G8: the image ships compiled bytecode; cold import before and after recorded.
27. [ ] N12, D9: before and after tables on the laptop (in-process, bedrock) and on staging
        (queued, bedrock) with run ids; the ingest split per run; the owner's content read of
        one report after N7 and one after N8 recorded.
28. [ ] D6, G4: embedding requests, tokens and throttling sleeps per run recorded on staging
        with the quota in force; the embedding wall compared with tokens ÷ quota and with
        today's 457 s median.
29. [ ] G7, N12: the data-flow note is committed; the retention rule is written; the DPIA
        addendum is named as the merge gate in the PR.
30. [ ] S1 to S5 applied only as the owner accepted them, with a line in the spec log; D14's
        open item resolved by the owner before the plan gate.
