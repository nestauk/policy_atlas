# ADR 0006 — Selection: stratified structure, agent-facing directive, bounded generative rerank

- **Status:** Accepted — 2026-07-06 (Shabeer Rauf, task-010 contract + plan gates).
- **Date:** 2026-07-06
- **Context doc:** [task 010 contract, decisions 1–10](../tasks/010-select/contract.md)
  (revision history records the full decision trail, revs 1–7) ·
  [EB components §6](../specs/capabilities/evidence-base/components.md) ·
  [plan-as-object — forecast vs commit](../specs/system/plan-as-object.md) ·
  [ADR 0005](0005-embed-grouping-seams-first-egress.md) (the seam/egress/injection
  precedent this slice extends).

## Context

Select (EB component 6) gates Tier-1 extraction — the first genuinely expensive
per-document step — and creates the `not_selected` state the gap-provenance rules
police hardest. The spec realises it as a *procedure* over cheap pre-extract
signals, stratified over the characterisation clusters, with must-includes as the
one hard rule and a mandatory bidirectional rationale. At the contract gate the
user pressure-tested the deterministic-vs-LLM question across five revisions:
where does reasoning belong in a component the spec keeps arithmetic? The specs
answer it structurally (the capability agent's just-in-time *commit* parameterises
tools; the tool executes), but the v3.0 build has no agent layer yet — and the
user directed that the component be designed for that architecture now, not
retrofitted. Two further challenges reshaped the slice: embedding-cosine relevance
was cut (the semantic dimension is already spent twice — screening judged
relevance, stratification grouped semantically), and a generative rerank was
pulled in-slice (009 made the marginal cost of bounded LLM calls small).

## Decision

1. **Deterministic, code-owned selection structure — under every strategy.**
   Candidates = the screened-in *eligible* set (`Non-evidence` excluded and
   counted; `Unknown` and unclassified eligible). Strata = the referenced
   characterisation's themes + `unclustered` (a partition). Allocation:
   must-includes (outside the budget, satisfying their stratum's breadth floor) →
   breadth floor one-per-stratum in deterministic order → largest-remainder
   proportional with exhausted-stratum redistribution. Hard rules never leave
   code; LLM output can order candidates but structurally cannot include or
   exclude one.
2. **The `SelectionDirective` is the agent-facing parameter surface.** A
   first-class facade argument (budget · must-include ids · soft boosts over
   columns + tags, the data-model scoping vocabulary · bounded weight emphasis ·
   priority strata), fail-closed validated, recorded whole in provenance. Boosts
   re-weight and never exclude. v3.0 sources it from the evidence-scope context;
   the future capability agent authors it just-in-time at invocation (the
   plan-as-object commit), making the agent layer a parameter-authoring change.
   The source/evidence **policy** integrates here when its slice lands — the
   policy *compiles into directive boosts*, provenance-stamped; select's code is
   untouched by construction. No policy field ships now (the field's shape
   belongs to the policy slice; an inert field violates data-model Principle 10).
3. **Two strategies over one structure; the rerank is bounded judgment, not a
   selector.** `coverage_stratified_v1` (default, suite path): fully
   deterministic — weighted composite (recency · quality tier · text-basis tilt ·
   screen confidence · origin) with byte-identical payload determinism.
   `llm_rerank_v1` (live path): batched schema-constrained scoring of **contested
   strata only** against the intent, on the envelope uniformly (title + abstract,
   never full text — the pre-extract line); coarse integer scores 0–10 (finer
   scales are false precision for uncalibrated cross-batch judgments), ties
   broken by the composite; per-doc/batch **fallback to the deterministic
   composite** (`rank_fallback`, flagged, never dropped); scored-before-fallback
   ordering (the two scales are never interleaved); pre-run enforced call budget.
   `select_rerank_v1` is the repo's second product prompt, lead-authored, under
   the ADR-0005 injection posture; reason strings are untrusted, potentially
   source-derived output. Cross-encoder relevance models (Cohere-class, Bedrock)
   were considered and routed to the `retrieve` seam — query-relevance is
   retrieval's upgrade, not purpose-fit judgment.
4. **Embedding-cosine relevance declined.** Screening already judged relevance
   and stratification already grouped semantically; within-stratum
   cosine-to-intent discriminates weakly, and its live role reduced to the
   fallback ordering, which simpler signals serve honestly. Select reads no
   vectors; `retrieve` remains their first reader. Recorded as a declined seam,
   revisited only via rerank-quality evals.
5. **Run-local selection record with an explicit characterisation reference.**
   One `selection_result` row per (scope, select-run), written as the last
   statement after all fallible work; empty scopes write no row. The
   characterisation it stratifies over is an **explicit `characterisation_run_id`
   on `Plan`/`Config`**, required at compile for select (fails closed; recorded
   in provenance and the summary) — the one-run-per-component model stands, and
   a grouping is never silently reused. The row carries the bidirectional
   rationale (per-doc selected reasons + scores; per-stratum exclusion
   aggregates + notable exclusions) and the deepening-selection **trigger
   flags** (`large_stratum_excluded` · `priority_stratum_excluded`, hardest ·
   `must_include_conflict` · `thin_base` · `thin_full_text`); the mode-governed
   pause machinery stays a recorded seam. Run-model framing settled at the plan
   gate: plan/orchestration groups via the plan object + decision log; the
   capability run is the recorded missing middle (additive parent entity;
   multiple plans and plan runs per project expected); component execution is
   the as-built `runs` grain.

## Consequences

- Extraction (component 7) reads a countable, auditable selection with its
  extraction substrate visible up front (per-stratum full-text shares,
  `thin_full_text`).
- `not_selected` stays derivable coverage state — no doc-status column — so no
  pipeline artefact can masquerade as corpus absence.
- The rerank's quality is unverified until extract gives selection a consequence:
  machinery correctness is this slice's bar; ranked-vs-reranked comparison on
  downstream yield is the recorded eval seam (with listwise ordering as the
  known-better candidate method).
- Gates opened: `selection_result` (table 20) · `"select"` registry entry +
  `ranking_backend` + `characterisation_run_id` · the `select_rerank_v1`
  generation surface. No new dependency; no embeddings use. One spec flow-back:
  components §6 realisation refined to *procedure with bounded generative
  rerank*.
