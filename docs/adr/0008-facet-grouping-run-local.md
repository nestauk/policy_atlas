# ADR 0008 — Group: run-local facet grouping, value-grain clustering, fail-closed scale cap

- **Status:** Accepted — 2026-07-07 (Shabeer Rauf, task-012 contract + plan gates).
- **Date:** 2026-07-07
- **Context doc:** [task 012 contract, decisions 1–9](../tasks/012-group/contract.md)
  (revision history records the full decision trail, revs 1–1.3, including
  two rounds of user gate-challenges and the contract-stage adversarial
  review) · [EB components §8](../specs/capabilities/evidence-base/components.md) ·
  [EB capability § Cluster persistence](../specs/capabilities/evidence-base/capability.md) ·
  [EB provenance grade 3](../specs/capabilities/evidence-base/provenance.md) ·
  [data-model — the findings layer](../specs/system/data-model.md) ·
  [ADR 0007](0007-findings-layer-extraction.md) (the findings layer this
  component is the first reader of).

## Context

Group (EB component 8) sits between extract and synthesise: it organises the
extracted `intervention_outcome_finding` records on an intent-derived facet
(intervention | outcome | population — the schema's source-named references)
so synthesise can produce one grounded block per group. It is the chain's
second clustering (topic-level over documents at characterise; facet-level
over findings here), the findings layer's **first reader**, and an
interpretive shape (EB provenance grade 3) that additionally inherits the
extraction dependency. Its labels sit on a line the specs guard carefully:
source-named references are "groupable/canonicalisable *downstream*, never
baked-in canonical entities", and resolving descriptive clusters into named
comparable options is Options Assessment's decision-relative job. Two
user-challenge rounds at the contract gate stress-tested the persistence
question; the contract-stage adversarial review (10/10 adopted) hardened the
mechanics.

## Decision

1. **Groups are run-local; one run-scoped roll-up row.** `grouping_result`
   mirrors the characterisation/selection precedent: one row per
   `(evidence_scope_id, run_id)`, carrying facet, the executed
   `extraction_run_id`, provenance (including the inherited extraction base:
   fingerprint, profile, base-ladder counts, finding-set size + hash), the
   groups with memberships and per-group/per-residual/overall direction
   spreads, counts and flags. No group entities, no tags, no finding
   mutations, nothing canonical. Run-local ≠ ephemeral: the row is durable and
   run-referenced — synthesise reads it by `grouping_run_id`; downstream
   capabilities read a *specific* grouping by reference. **Canonical
   promotion is a recorded staged seam** (run-local → project-scoped
   persistent → graph datastore, gated on the data-model's
   entity-resolution-quality bar), because a persisted facet-group label is a
   cross-source identity judgment over sources' own vocabularies — often
   question-relative — and must not become silently-trusted ground truth
   before a quality bar exists. The asymmetry with characterise's tag
   persistence is deliberate: document topics have a standing accreting
   annotation layer (`source_tag`) to land in; findings/reference values do
   not.
2. **Cluster the values, membership derives in code.** The LLM's single
   judgment is partitioning the distinct source-named facet values (id-keyed
   data records with light counterpart context) into coherent, descriptive,
   corpus-grounded groups; finding membership then derives deterministically
   (finding → normalised value → group). Exhaustiveness is structural: the
   partition = named groups + counted `ungrouped` (values the model honestly
   can't group; no catch-all labels — a deterministic forbidden-label/length/
   duplicate validation layer rejects them, the 009 precedent) + counted
   `no_value` (null-facet findings). Mixed/unclear findings are first-class
   in the partition — the 011 carried-forward requirement — visible in every
   direction spread; spreads are counts, never verdicts (the weighted
   consensus roll-up stays deferred).
3. **Fail-closed scale cap, no degraded pass.** Above `FACET_VALUE_CAP` the
   component fails structurally (`value_cap_exceeded`) — a head-sample
   discover/assign pass cannot discover tail-only groups and would silently
   inflate `ungrouped`. The large-corpus algorithm is an eval-gated seam.
   Likewise, backend failure fails the component honestly: grouping has no
   deterministic fallback and a partial grouping is worse than none.
4. **One shared `cluster` tool, two wrappers.** Characterise and group are
   the spec's two wrappers over one shared tool; the code reflects it — the
   009 backend renames to `ThemeGroupingBackend` (kwarg
   `theme_grouping_backend`) beside the new `FacetGroupingBackend`, and the
   deterministic skeleton (id-keyed records, schema-constrained call,
   validation, one targeted repair, counted residual, pre-run budget) is
   factored where the code genuinely coincides. `query-findings` is an
   explicit recorded deviation from components §8's tool table: it lands with
   its deliberative consumer (synthesise's agent-loop); group's v3.0 read is
   a direct deterministic load resolved via the extraction roll-up's
   `docs[].extraction_record_id`.
5. **Labels are untrusted model output.** Bounded and validated at write,
   stored and rendered as data, never executed; carried forward onto
   synthesise: group labels/descriptions enter downstream prompts as data
   records, never instructions.

## Consequences

- Synthesise (013) gets a stable, provenance-complete read surface
  (`grouping_run_id`) whose invariants — grouped set == the referenced run's
  finding set; sum identities; residuals counted — are test-enforced.
- Re-grouping is cheap and honest: a new facet or finding set is a new run;
  nothing is overwritten, nothing canonical drifts stale.
- A real >cap corpus cannot run group v1 — loud, named, and routed to the
  recorded seam rather than silently degraded.
- The rename touches every `GroupingBackend` reference (harness, tracing,
  skeleton, characterise, tests) in one grep-verified sweep; stored-data
  vocabulary (`characterise_grouping_v1`) is unchanged.
