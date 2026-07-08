# Rubric: 014-llm-screen-classify

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes deterministically with **zero egress** (stub
       backends default everywhere); declared manual/live checks pass.
3. [ ] No approval-gated change snuck in unapproved beyond the three the
       contract names (two generation surfaces [mini screen ×3 reps ·
       judgment-class classify] · two `run_harness` params · one
       migration carrying BOTH schema changes: the `ck_stag_tag_type`
       CHECK widen AND the `uq_ssr_scope_source` partial unique
       index).
4. [ ] No generated files or secrets edited by hand; keys env-only,
       grep audit clean.
5. [ ] No tests deleted, skipped or weakened without written
       justification; the existing sentinel-driven suites still pass
       against the stub backends with unchanged semantics.
6. [ ] Verification evidence recorded ([verification.md](verification.md)),
       including the live e2e run: relevance spread, classification
       distribution not-all-`Unknown`, non-English record handled, tag
       samples within bounds, Langfuse trace ids + scores, cost, the
       decision-10 agreement distribution (unanimous / 2-3 /
       tie-broken), and the borderline review (lowest-confidence band
       + non-unanimous docs with coherent `reason`s).
7. [ ] Known gaps and deferred seams listed (gap →
       [docs/deferred.md](../../deferred.md)); the discharged
       LLM-screen/classify seam entries updated, the seams this slice
       leaves open (thin-base trigger, automated recovery sweep —
       the failed-row rerun retry itself is DISCHARGED in-slice,
       rev 1.1/1.6 — content peek, Unknown resolution) restated, not
       silently absorbed.
8. [ ] Required Tier-3 review stack ran (contract verifier ·
       security-auditor lane — untrusted third-party text enters prompts
       here · Codex adversarial · /code-review medium · live-trace
       content review), or skipped with written justification — findings
       in [verification.md](verification.md).
9. [ ] Injection posture demonstrably enforced: **paired
       clean/adversarial fixtures assert semantic invariance** (same
       decision with and without embedded instruction text — a
       valid-but-steered label fails the test), plus the live paired
       probe in the live check; provider fields enter prompts only
       via the closed allowlist with per-field caps + control-char
       stripping (overlong/instruction-shaped fixtures covered);
       titles/abstracts/provider fields enter prompts as id-keyed
       data records; outputs schema-constrained and code-validated
       against closed vocabularies; NUL scrub at the backend
       boundary.
10. [ ] The failure/uncertainty/consensus semantics (revs 1.1–1.3) are
        test-covered: screen doc failure (all reps failed) persists
        `status='failed'` and a re-run re-attempts the doc as a new
        row (partial unique index; attempt history preserved; counts
        failure-attempt-aware); classify failure writes no row and
        re-runs retry exactly the unwritten docs; per-rep `unsure`
        counts as relevant in the vote and 0.5 in the consensus
        probability; the confidence formula distinguishes 2/3 from
        3/3 and covers the vote/probability divergence case;
        majority / rep-failure-degradation / tie→relevant aggregation
        each covered; **quorum enforced** (< 2 surviving reps → doc
        `failed`, no single-rep decision persists; failed reps out of
        vote AND denominator); **title-only unanimity-to-exclude**
        covered (dissent → relevant, flagged); Unknown-vs-Other
        boundary fixtures both sides; per-rep records + agreement
        count in the event payload; all failure paths counted in
        summaries; effective-status distinct-source counting
        regression-tested for every screening-status reader (incl.
        `characterise._base_counts`).
11. [ ] Open-tag output bounded and provenance-clean: per-record and
        per-tag caps enforced, `asserted_by='classify'` ·
        `tag_type='methodological_structural'`, all writes through
        `tags.insert_source_tags`, migration roundtrip green both DBs.
12. [ ] Stage-2 full-text screen (decision 11, revs 1.7–1.9) holds:
        demote-only enforced as a WRITE invariant (the
        stage-1-exclude + attempted-stage-2-include regression
        fails the insert); stage-2 failure leaves the stage-1 result
        standing; every reader resolves through the shared
        effective-screen helper (no raw `status='relevant'` join
        survives — demoted docs excluded, confirmed docs read once);
        select reads the effective row wholesale (status +
        confidence, `screen_stage` carried into the rationale — the
        rev-1.10 stage-3-cascade rule); availability predicate =
        text availability (ingested OR envelope full_text);
        `screen_stage` provenance on every row and event; effective
        result = highest-stage non-failed everywhere (reader sweep
        covers stage AND status); `skipped_no_fulltext` counted;
        deep profile runs it, rapid profile provably skips it; the
        live-check demotion review reads every demoted doc's
        `reason`; stage-2 confidence never mixed with stage-1 in any
        comparison without the provenance column.
