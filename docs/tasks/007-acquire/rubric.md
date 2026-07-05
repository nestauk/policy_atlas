# Rubric: 007-acquire

Core completion criteria. The task is **done only if every box holds** — otherwise it is in
progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes (test · typecheck · lint · build); all checks deterministic.
3. [ ] No approval-gated change snuck in unapproved — schema limited to the two approved
       items (`screening_scope` → `evidence_scope` rename; `search_coverage_record` table);
       **zero runtime egress** (fixture replay only; recorder scripts never imported by the
       package); no new dependencies; no auth/CI/production config; no public-interface
       change beyond the registry entry + approved rename.
4. [ ] No generated files or secrets edited by hand; `OVERTON_API_KEY` never committed, never
       read by package code.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)), including the exact
       end-to-end command and both migration roundtrips.
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md):
       live `SearchBackend` implementations (with the v2-lesson requirements: timeouts,
       Overton rate limiter, query sanitization, per-provider caps) · **the Arm-B agentic
       search loop as the chosen query-derivation direction** (R&D pointers: PR #184,
       presentation PDF, ONBOARDING.md; protocol growth to citation-fetch /
       grounding-lookup / dense verbs + capability flags; stop-condition vocabulary
       growth; Semantic Scholar candidate backend; Overton arm-B future work;
       Campbell/3ie/EPPI golden-dataset note → eval workstream) · Overton semantic mode +
       filters · thin-base re-search trigger · cross-project content-hash dedup + fuzzy
       near-dup matching · injection-screening posture for acquired text · full-text
       ingestion (slice 008, with v2's OA-precedence / fetch cascade / parse caps /
       failure-manifest patterns).
8. [ ] Required review stack ran for Tier 3 (contract verifier · `/code-review` medium ·
       `security-auditor` subagent lane · Codex adversarial pass · `ponytail-review` +
       `/simplify`), or skipped with written justification — findings in
       [verification.md](verification.md).

Slice-specific criteria (from the contract):

9. [ ] **Both literatures, authentic structure:** committed sanitized fixture sets for
       **OpenAlex and Overton** covering, at minimum — OpenAlex: a missing abstract, a
       missing year, a non-article type, a non-English record, a structurally real
       `abstract_inverted_index`; Overton: a no-DOI record, a record with a DOI in the
       `keyed_other_identifiers.doi` list, a snippet-less record carrying only
       `llm_document_description`, a record with neither, string-shaped and list-shaped
       `authors`/`topics`, a government/IGO publisher — and the full-chain test shows them
       flowing acquire → screen (`title_only` fail-open where abstract-less) → classify
       (`Unknown`) → appraise (`skipped_unknown`).
10. [ ] Every `search` call emits one `search.executed` governance event **per backend**
        (fixture backends included), payload as contracted, trust class declared.
11. [ ] Exactly one `search_coverage_record` per acquire run — **including error runs**,
        its `backends` array spanning both backends; deterministic verdict rule per
        decision 8 (any backend error → `inadequate`; zero usable records → `inadequate`;
        empty-but-successful backend ≠ inadequate), all four cases test-covered; backend
        errors are isolated (healthy backend's results kept, `component.completed`
        emitted, per-backend `status`/`error` reported); origin `model`; `saturated` not
        an accepted `stop_condition`; all five named check constraints + cross-project
        FKs test-covered.
12. [ ] Acquired snapshots: `origin="acquired"`, `run_id` set, `text_basis="abstract_only"`,
        one chunk of the text in hand, `segmentation_policy="metadata_envelope_v1"`,
        content hash over the chunk text — immutability preserved (no snapshot updated);
        `abstract_source` (`publisher_abstract`/`snippet`/`llm_description`/`none`) on
        every acquired snapshot's metadata, LLM-generated summaries never silently mixed
        in; retained provider fields present (URL/OA block at minimum, per the
        plan-finalized list).
13. [ ] Rerun-stable counting: `acquired + already_acquired + skipped_unusable ==
        results_returned` holds per backend and in total, on first and second runs; second
        run acquires nothing and duplicates no snapshots; **cross-project isolation**
        test-covered (project B acquiring the same fixtures still gets its own links;
        project A untouched).
14. [ ] All three identity guards test-covered separately: `backend_record_id` re-run ·
        normalized DOI across backends (prefixed/bare, mixed case — deterministic winner
        by fixed backend order) · content hash; `source_locator` set per the contracted
        mapping.
15. [ ] OpenAlex abstract-inverted-index reconstruction test-covered against a structurally
        real inverted index (multi-position tokens), plus the empty/missing case.
16. [ ] Rename complete: no stale `screening_scope` / `screening_scope_id` reference in
        code, tests, or the migration upgrade path; existing component tests green under
        `evidence_scope`.
17. [ ] Spec flow-back landed: components.md §1 one-line clarification + spec bundle `log.md`
        entry (approved with the contract).
18. [ ] Fixture provenance documented per backend via each file's `_meta` block (recorder
        query, date, record count, quirk coverage, sanitizer version); **both committed
        fixtures sanitized** (shape-faithful, no real third-party records — user decision
        2026-07-05); raw recordings gitignored; the deterministic leak guard passes
        (`10.99999/` DOI prefix, `example.org` URLs, test-enforced).
19. [ ] Approved gated change 3 in place as contracted: `run_harness` optional
        `search_backends` parameter with the fixture-pair default — no other public
        interface touched.
