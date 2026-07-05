# Rubric: 009-characterise

Core completion criteria. The task is **done only if every box holds** — otherwise it is
in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) — all twelve numbered
       decisions as approved (or as amended at the gates, recorded in the contract).
2. [ ] `make verify` passes — deterministic and **zero-egress** (socket-deny covers an
       end-to-end characterise run); the declared manual live check ran with evidence in
       [verification.md](verification.md).
3. [ ] No approval-gated change snuck in unapproved — the four gated changes (schema ·
       `openai`+`numpy` deps · `run_harness` parameter · **live-egress path**) are exactly
       as approved; no existing-table change, no pgvector, no generation/LLM calls, no
       artefact/block writes.
4. [ ] No generated files or secrets edited by hand; `OPENAI_API_KEY` appears in no
       committed file, log, event payload or verification artifact (test-asserted).
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)): counting
       invariants, eager-uniform coverage, determinism (two stub runs byte-identical),
       live-run landscape summary + cost note, migration roundtrip (19 tables).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)):
       EB artefact composition · LLM labelling · steer-point pause · dual-view coverage ·
       pgvector/retrieval · Bedrock swap · exact-token budgeting · clustering upgrade ·
       tag consolidation; class-1 vectorisation entry marked discharged.
8. [ ] Spec flow-back landed: components §5 content-vs-artefact clarification +
       `log.md` entry, as approved with the contract.
9. [ ] Honesty properties hold in the shipped behaviour: pattern grades never conflated
       (coverage = fact + base; clusters = soft, run-local); partial embedding coverage
       refuses to cluster (no silently biased shape); flag-not-block throughout;
       re-runs idempotent with honest counts.
10. [ ] ADR 0005 (embed seam / first product egress) written and Accepted.
11. [ ] Required review stack ran for Tier 3 (contract verifier · code review ·
        security lane · adversarial review · simplification), or skipped with written
        justification — findings adjudicated in [verification.md](verification.md).
