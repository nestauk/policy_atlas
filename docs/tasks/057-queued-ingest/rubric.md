# Rubric: 057-queued-ingest

Core completion criteria. The task is **done only if every box holds**, otherwise it is in
progress. Item numbers point at [contract.md](contract.md) (revision 4): N1 to N15, D1 to
D15, G1 to G10, S1 to S5. Terms are defined in the contract's § Terms. The review record is
[adversarial-review-contract.md](adversarial-review-contract.md).

Core
1. [ ] Implementation satisfies [contract.md](contract.md) for every need N1 to N15.
2. [ ] `make verify` passes at the build-open baseline, after the schema phase, after the
       retrieval phase and at the step-6 exit; `make -C infra test` passes with the CDK changes.
3. [ ] No approval-gated change beyond G1 to G10: the D2 migration, the `awslambdaric`
       dependency in the main group, the N11 resources and config, the function's egress, the
       Dockerfile line, the compose image, the deploy waiter loop. No prompt-text re-pin, no
       public-interface change; code-only re-pins recorded with diffs.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification (the scheduler
       tests that N6 deletes are listed with the behaviour that replaces each).
6. [ ] Verification evidence recorded ([verification.md](verification.md)) as the contract's
       § Verification evidence lists, read from saved results.
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md): the
       header, page-number and footnote parse rules with E6's numbers (D8), the fallback
       parser trigger signals, per-host coordination across functions (D11), the retention
       script's scheduling (D3), HNSW, per-claim judge filtering with E9's numbers, the
       low-effort judge revisit with E3's numbers (D14), the prod route flip.
8. [ ] Required Tier 4 review stack ran (contract verifier · code and security review ·
       adversarial pass at contract and plan stage · simplification) or skipped with written
       justification; the ADR is Accepted; the rollback plan is written and the downgrade
       tested.

Queue and function (N1 to N5, D1, D4, D5)
9. [ ] N1: one message per attempted document; the message carries two ids and a schema
       version, no user identifier and no URL (test).
10. [ ] N2: the handler produces the same statuses and reason codes as the in-process path on
        the committed fixture corpus; the store lookup happens before parsing; a 429 with
        Retry-After is waited for (capped); the handler always writes a final reason-coded
        status before returning; the final link write is guarded on `queued`, so a second
        delivery and a late result are no-ops; a race of two real connections on the same store
        key and on the same link row leaves one snapshot and consistent rows (tests).
11. [ ] N3: the `queued` flip and the sends commit in their own transaction while the
        component transaction is open, and a real second connection's writes are visible to
        the poll (test); orphaned `queued` rows are re-queued at stage start; the counts dict
        keeps its invariant under the three fake-queue scenarios (all early, some late,
        deadline hit) with `already_in_store` inside `ingested`; the deadline reason is
        `not_ready` and stays out of the access-failure counts; ticks send `fetched` as null.
12. [ ] N4, N5: timeout 180 s, memory 1,769 MB, storage 512 MB, stage deadline 600 s, SQS
        visibility timeout = function timeout + 30 s, dead-letter after 2 attempts, concurrency
        cap 20, dead-letter alarm, pinned by infra tests; the dead-letter drain command is in
        `infra/DEPLOYMENT.md`; the plan records the connection arithmetic (writer
        `max_connections`, API pool, one connection per invocation) and the account's Lambda
        quotas.
13. [ ] D5: the function is the backend image with another command; the parse step runs in a
        subprocess with the 120 s kill and denied sockets; the function runs in the private
        subnets with no S3 and no new endpoints; secrets are fetched at runtime, not placed in
        environment variables; the function has no model client and no Bedrock grant (D6;
        wording corrected 2026-11-04, review ruling 10, from "Bedrock is reached through
        the function's role").

Embedding in the stage (D6, G4)
14. [ ] D6: the function writes no vectors; the stage embeds pending chunks as documents land
        through an adaptive request pool (halve on throttling, add one after a run of
        successes, cap from the route file) that converges in a test with a fake throttling
        backend; a snapshot with chunks but no vectors is handled as today; no `embed_timeout`
        state exists.
15. [ ] D6, G4: embedding requests, tokens and throttling sleeps per run recorded on staging
        with the quota in force; the embedding wall compared with tokens ÷ quota and with
        today's 457 s median; the pool width re-derived if the quota changed. Staging evidence
        is gathered after the merge to dev (owner, 2026-11-03: staging deploys only from dev)
        and appended to verification.md; the PR names it as the one open item.

One code path and the markup rule (N6, N7, N14, D8)
16. [ ] N6: the scheduler and batch hand-over are gone; the per-document function serves both
        modes; in-process mode uses one connection per worker thread with per-document
        commits; the byte-identical digest holds across worker counts 1 and 4 on the fixture
        corpus under profile v2; the test database's connection count stays within the pool.
17. [ ] N7: on the control PDFs markup-bearing chunks go from 186 to 0 with tables and heading
        paths unchanged; on the fixed questions no quote failure has markup as its cause; new
        profile and policy names on every route whose text changed; existing snapshots and
        citations untouched.
18. [ ] N14: verifier version `qv_v2`; markup stripped symmetrically; the raw-offset map holds
        through deleted characters (anchor-span test); tests both ways.

Store and retrieval (N8, N9, D2, D3, D7, G9, G10)
19. [ ] D2, G9, G10: the compose and CI Postgres image carries pgvector; the migration upgrades
        and downgrades on the test database; the backfill commits per batch and resumes on
        `embedding is null`; the JSONB column is dropped only when no row is null (rev3, at the
        end of the retrieval phase); staging and prod row counts recorded before the build (the
        staging dry run was dropped by the owner, 2026-11-03, in favour of the non-blocking
        design); the deploy waiter loop outlasts the measured migration; the downgrade's
        float32 approximation documented; a failure after a committed batch resumes (test).
20. [ ] N8, D7: the committed synthetic-corpus test passes against both retrievers before the
        Python retriever is deleted; the recorded real-query parity on bedrock-profile vectors
        shows the same top-8 in the same order; the snapshot-id list is frozen once per
        synthesise run; both callers use the SQL retriever; the in-memory scope load, the
        Python scoring and the unit cap are deleted; provenance records the factors for the
        returned candidates; the embedding write time per run recorded before and after.
21. [ ] N9, D3: one snapshot for the same bytes across two tasks; embeddings added per profile
        without a second parse; the shared row carries no task, user, run or URL key in any
        column or JSON field (test); the breadcrumbs live on the link row; `already_in_store`
        appears in the stored counts on a live overlapping run and not in the SSE summary (G6).

Timeouts and widths (N10, D12, D15)
22. [ ] N10c, D12: every step under the bedrock route's `[steps]` carries `timeout_s` and every
        model client reads it; values are 2 × healthy p99 (first attempt that succeeded) from at
        least 100 traced attempts, else today's value, floor 5 s, listed in verification.md with
        their sample counts; `max_retries = 0` on every client with one traced retry, so each
        attempt is its own generation; streamed steps exempt; on the fixed questions the per-step
        counts of stalls caught and of retries that were also slow are reported, any too-tight
        step raised once, and zero components retried because every attempt was cut; synthesise
        wall before and after recorded; the owner's read finds the reports unchanged in content.
        Section order and the ledger untouched.
23. [ ] N10a: no call over 300 s on the fixed scoping question under current code (confirmed,
        with the pre-056 explanation of the 900 s calls recorded).
24. [ ] N10b: option-search width 4 → 10 measured on the fixed scoping question; no new 429s;
        or reverted with the measurement recorded.
25. [ ] N10d, D15: screen stage 1 and classify widths 12 → 48 measured on the fixed questions;
        stage walls and 429 counts before and after; or reverted with the measurement recorded;
        the note that prod takes the widths unmeasured on `openai-direct` is in verification.md.

Infra, image, measurement and governance (N11 to N13, D9, G7, G8)
26. [ ] N11: the function, queue (4-day retention, encrypted, batch size 1), dead-letter
        queue, alarms (dead-letter depth, NAT network, writer CPU credits), the API role's send
        permission, the function's log group with retention and URL redaction, and
        `ingest_mode = queued` for staging are in CDK with pinned tests; `cdk diff` reviewed at
        the owner's checkpoint after Phase 5 and before the merge; the staging deploy (from dev,
        after the merge) succeeds; production config stays `in_process` unless the owner rules
        otherwise.
27. [ ] N13, G8: the image ships compiled bytecode; cold import before and after recorded.
28. [ ] N12, D9: before and after tables on the laptop (in-process, bedrock) with run ids,
        ordered by lever with a stage-wall attribution per lever, including three fresh
        build-open runs as the like-for-like before; the staging (queued, bedrock) tables
        appended after the merge (item 15); the ingest split per run; the owner's content read
        of one report after N7 and one after N8 recorded.
29. [ ] G7, N12: the data-flow note is committed and covers the queue and log retention and the
        pseudonymous identifiers; the retention rule for unlinked snapshots is written with its
        locking rule; the DPIA addendum is named as the merge gate in the PR.
30. [ ] S1 to S5 applied as the owner accepted them (S3 in its revision 3 wording), with a line
        in the spec log.
31. [ ] N15, D14: the `judge_grounding` step runs at `low` under the bedrock route override;
        judge wall per call and per run before and after recorded; unsupported-claim counts per
        report recorded against E3's medium spread; the owner's read is the decision and is
        recorded; the revisit is written into `deferred.md` for the synthesis refinement task.
