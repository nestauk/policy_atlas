# Rubric: 009-characterise

Core completion criteria. The task is **done only if every box holds** — otherwise it
is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) — all thirteen numbered
       decisions as approved (or as amended at the gates, recorded in the contract).
2. [ ] `make verify` passes — deterministic and **zero-egress** (stub embedder + stub
       grouper; tracing no-op without keys; socket-deny covers an end-to-end
       characterise run) — and the manual live check ran with evidence in
       [verification.md](verification.md), including the run trace visible in the
       dev Langfuse instance.
3. [ ] No approval-gated change snuck in unapproved — the four gated changes exactly
       as approved: schema (three project-scope-guarded tables + the `open_tags`
       column retirement) · `openai` + `langfuse` deps · `run_harness`
       `embedding_backend` + `grouping_backend` parameters · live egress (embeddings
       + the two-stage grouping calls within the budget baseline/maximum + full-I/O
       traces to the user's Langfuse instances). No pgvector, no generation surface
       beyond the grouping pair, no artefact/block writes, no new orchestration
       dependency.
4. [ ] No generated files or secrets edited by hand; `OPENAI_API_KEY` and
       `LANGFUSE_*` credentials appear in no committed file, log, event payload or
       verification artifact (test-asserted).
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)): counting
       invariants, eager-uniform coverage, unit-derivation determinism,
       validation/repair behaviour, two stub runs byte-identical on the
       characterisation row, live-run landscape summary (real themes) + cost note +
       dev-instance trace, migration roundtrip (19 tables).
7. [ ] Known gaps and deferred seams listed (gap →
       [docs/deferred.md](../../deferred.md)) per the contract's verification
       section, and the class-1 vectorisation entry marked
       discharged-ahead-of-reader (approved exception).
8. [ ] Spec flow-backs landed with `log.md` entries: components §5
       content-vs-artefact; components §5 thematic mechanism +
       vectorisation-with-gate exception; data-model tag-layer assertion provenance.
9. [ ] Honesty properties hold in the shipped behaviour: pattern grades never
       conflated (coverage = fact + base; themes = soft, run-local,
       provenance-stamped); tag provenance classes distinguishable (provider /
       provider-LLM / own — `llm_document_theme` never masquerades as curated or
       ours); `source_tag` is the single tag home; no placeholder theme, silent
       drop, or partial grouping representable; `unclustered` counted;
       flag-not-block throughout; no absence claims; re-runs idempotent with honest
       counts.
10. [ ] ADR 0005 (embed + generation seams / first product egress / injection
        posture) written and Accepted; the `characterise_grouping_v1` prompt pair is
        lead-authored and co-versioned.
11. [ ] Required review stack ran for Tier 3 (contract verifier · code review ·
        security lane · adversarial review · simplification), or skipped with
        written justification — findings adjudicated in
        [verification.md](verification.md).
