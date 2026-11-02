# Rubric: 057-queued-ingest

Core completion criteria. The task is **done only if every box holds**, otherwise it is in
progress. Item numbers point at [contract.md](contract.md) (revision 1): N1 to N12, D1 to
D11, G1 to G7, S1 to S4. Terms are defined in the contract's § Terms.

Core
1. [ ] Implementation satisfies [contract.md](contract.md) for every need N1 to N12.
2. [ ] `make verify` passes at the build-open baseline, after the schema phase, after the
       retrieval phase and at the step-6 exit; `make -C infra test` passes with the CDK changes.
3. [ ] No approval-gated change beyond G1 to G7: the D2 migration, the `awslambdaric`
       dependency, the N11 resources and config, the function's egress. No prompt re-pin, no
       public-interface change.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification (the scheduler
       tests that N6 deletes are listed with the behaviour that replaces each).
6. [ ] Verification evidence recorded ([verification.md](verification.md)) as the contract's
       § Verification evidence lists, read from saved results.
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md): the
       fallback parser trigger signals (D8), per-host coordination across functions (D11),
       the retention script's scheduling (D3), HNSW.
8. [ ] Required Tier 4 review stack ran (contract verifier · code and security review ·
       adversarial pass at contract and plan stage · simplification) or skipped with written
       justification; the ADR is Accepted; the rollback plan is written and the downgrade
       tested.

Queue and function (N1 to N5, D1, D4, D5)
9. [ ] N1: one message per attempted document; the message carries no user identifier (test).
10. [ ] N2: the handler produces the same statuses and reason codes as the in-process path on
        the committed fixture corpus; a second delivery of the same message is a no-op.
11. [ ] N3: the queued stage returns the counts dict with its invariant intact under the three
        fake-queue scenarios (all early, some late, deadline hit); progress ticks carry the
        store's counts.
12. [ ] N4, N5: timeout 180 s, memory 3,072 MB, stage deadline 600 s, dead-letter after 2
        attempts, concurrency cap and alarm pinned by infra tests; the plan records the
        connection arithmetic against the writer instance.
13. [ ] D5: the function is the backend image with another command; the parse step runs in a
        subprocess with the 120 s kill and denied sockets; the function runs in the private
        subnets with no S3 and no new endpoints.

One code path and profile v2 (N6, N7, D8)
14. [ ] N6: the scheduler and batch hand-over are gone; the per-document function serves both
        modes; the byte-identical digest holds across worker counts 1 and 4 on the fixture
        corpus under profile v2.
15. [ ] N7: fixture PDFs show plain chunk text, no running headers or footers, footnotes in
        their own flagged chunks; the quote-match failure rate on PDF chunks on the fixed
        questions is at or below 4% (🟡 target; a higher result is reported with the owner's
        decision); headings and tables per document not below v1 on the comparison set.
16. [ ] D8: existing snapshots and citations are untouched; new profile and policy names on
        every route whose text changed.

Store and retrieval (N8, N9, D2, D3, D7)
17. [ ] D2: migration upgrades and downgrades on the test database; backfill timings recorded
        on dev and staging; the JSONB vector column's fate matches the owner's ruling.
18. [ ] N8, D7: the SQL retriever returns the same top-8 in the same order as the Python
        retriever for the 20 saved queries and the fixed questions' replayed section queries;
        both callers use it; the in-memory scope load, the Python scoring and the unit cap are
        deleted; retrieval provenance records the factors for the returned candidates.
19. [ ] N9, D3: one snapshot for the same bytes across two tasks; embeddings added per profile
        without a second parse; the shared row carries no task or user id (test on the
        columns); `already_in_store` appears in the counts on a live overlapping run.

Scoping levers (N10)
20. [ ] N10a: the client timeout behind the 900 s calls is sized to its tail; no call over
        300 s on the fixed scoping question after the change.
21. [ ] N10b: option-search width raised and measured; no new 429s in the logs; or the change
        reverted with the measurement recorded.
21a. [ ] N10c, D12: the stall remedy chosen at the plan gate is built; on the fixed questions
        no synthesis call exceeds its step's timeout plus a normal retry, the stage wall before
        and after is recorded, stalled calls still succeed, and the owner's read finds the
        reports unchanged in content. Section order and the ledger are untouched.

Infra, measurement and governance (N11, N12, D6, D9, G4, G7)
22. [ ] N11: staging deploys with the function, queue, dead-letter queue, alarm and
        `ingest_mode = queued`; `cdk diff` reviewed at the plan gate; production config stays
        `in_process` unless the owner rules otherwise.
23. [ ] N12, D9: before and after tables on the laptop (both routes, in-process) and on staging
        (queued, bedrock) with run ids; the ingest split per run; the owner's content read of
        one report per route recorded.
24. [ ] D6, G4: requests, tokens and throttling sleeps per run recorded on staging; the
        embedding wall compared with today's 457 s median; a quota raise requested only if
        throttling at the token rate appears, with its state recorded.
25. [ ] G7, N12: the data-flow note is committed; the retention rule is written; the DPIA
        addendum is named as the merge gate in the PR.
26. [ ] S1 to S4 applied only as the owner accepted them, with a line in the spec log.
