# Rubric: 014-llm-screen-classify

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes deterministically with **zero egress** (stub
       backends default everywhere); declared manual/live checks pass.
3. [ ] No approval-gated change snuck in unapproved beyond the three the
       contract names (two generation surfaces · two `run_harness`
       params · the `ck_stag_tag_type` CHECK widen).
4. [ ] No generated files or secrets edited by hand; keys env-only,
       grep audit clean.
5. [ ] No tests deleted, skipped or weakened without written
       justification; the existing sentinel-driven suites still pass
       against the stub backends with unchanged semantics.
6. [ ] Verification evidence recorded ([verification.md](verification.md)),
       including the live e2e run: relevance spread, classification
       distribution not-all-`Unknown`, non-English record handled, tag
       samples within bounds, Langfuse trace ids + scores, cost.
7. [ ] Known gaps and deferred seams listed (gap →
       [docs/deferred.md](../../deferred.md)); the discharged
       LLM-screen/classify seam entries updated, the seams this slice
       leaves open (thin-base trigger, recovery loop, content peek,
       Unknown resolution) restated, not silently absorbed.
8. [ ] Required Tier-3 review stack ran (contract verifier ·
       security-auditor lane — untrusted third-party text enters prompts
       here · Codex adversarial · /code-review medium · live-trace
       content review), or skipped with written justification — findings
       in [verification.md](verification.md).
9. [ ] Injection posture demonstrably enforced: the injection-shaped
       fixture test exists and passes; titles/abstracts/provider fields
       enter prompts as id-keyed data records; outputs
       schema-constrained and code-validated against closed
       vocabularies; NUL scrub at the backend boundary.
10. [ ] The rev-1.1 failure/uncertainty semantics are test-covered:
        screen failure persists `status='failed'` and a re-run
        re-attempts the doc as a new row (partial unique index;
        attempt history preserved; counts failure-attempt-aware);
        classify failure writes no row and re-runs retry exactly the
        unwritten docs; wire-level `unsure` maps to relevant at
        capped-low confidence and is event-recorded + counted; all
        failure paths counted in summaries.
11. [ ] Open-tag output bounded and provenance-clean: per-record and
        per-tag caps enforced, `asserted_by='classify'` ·
        `tag_type='methodological_structural'`, all writes through
        `tags.insert_source_tags`, migration roundtrip green both DBs.
