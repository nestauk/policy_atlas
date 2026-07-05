# Rubric: 009-characterise

Core completion criteria. The task is **done only if every box holds** — otherwise it is
in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) — all twelve numbered
       decisions as approved (or as amended at the gates, recorded in the contract).
2. [ ] `make verify` passes — deterministic and **zero-egress** (stub embedder + stub
       grouper; socket-deny covers an end-to-end characterise run); the declared manual
       live check ran with evidence in [verification.md](verification.md).
3. [ ] No approval-gated change snuck in unapproved — the four gated changes (schema ·
       `openai` dep · `run_harness` parameter · **live egress: embeddings +
       the one grouping generation call**) are exactly as approved; no existing-table
       change, no pgvector, no second generation surface, no artefact/block writes,
       no LangChain/framework.
4. [ ] No generated files or secrets edited by hand; `OPENAI_API_KEY` appears in no
       committed file, log, event payload or verification artifact (test-asserted).
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)): counting
       invariants, eager-uniform coverage, validation/repair behaviour, determinism
       (two stub runs byte-identical), live-run landscape summary (real themes) + cost
       note, migration roundtrip (19 tables).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)):
       EB artefact composition · large-corpus grouping · grouping-quality +
       adversarial-content evals · steer-point pause · dual-view coverage ·
       pgvector/retrieval (chunk vectors' first reader) · Bedrock swap · exact-token
       budgeting · v2 `group`-seam lessons · tag consolidation; class-1 vectorisation
       entry marked discharged-ahead-of-reader (approved exception).
8. [ ] Spec flow-backs landed: components §5 content-vs-artefact clarification + the
       thematic-mechanism update (LLM grouping at small scale; vectorisation-with-gate
       exception) + `log.md` entries, as approved with the contract.
9. [ ] Honesty properties hold in the shipped behaviour: pattern grades never conflated
       (coverage = fact + base; themes = soft, run-local, provenance-stamped with
       prompt version + model id); no placeholder theme, silent drop, or partial
       grouping representable; `unclustered` counted; flag-not-block throughout;
       re-runs idempotent with honest counts; the key appears in no captured output.
10. [ ] ADR 0005 (embed + generation seams / first product egress / injection posture)
        written and Accepted; the grouping prompt is lead-authored and versioned.
11. [ ] Required review stack ran for Tier 3 (contract verifier · code review ·
        security lane · adversarial review · simplification), or skipped with written
        justification — findings adjudicated in [verification.md](verification.md).
