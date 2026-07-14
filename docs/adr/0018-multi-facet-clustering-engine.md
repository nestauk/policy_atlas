# ADR 0018 — Multi-facet grouping on a shared two-stage clustering engine

**Status:** Accepted — 2026-07-14 · owner (contract approved same day, contract-stage
adversarial review adjudicated 15/15; plan approved same day, plan-stage adversarial
review adjudicated 12/12; the full decision trail lives in the task's contract —
every call carries an owner adjudication date).
**Task:** [022-synthesis-refinement](../tasks/022-synthesis-refinement/contract.md).

## Context

`group` (task 012) clustered findings on ONE facet per run via a single-call
exhaustive partition over the distinct facet-value list. Three forces broke that
shape at once:

- **Scale**: `group_facet_v1` on gpt-5.4-mini emitted duplicate value ids at ~184
  distinct values in 4/4 live attempts (021's kind-spanning membership roughly
  doubled the list) — a structural capacity cliff of asking one response to emit a
  complete partition, not a retry problem
  ([knowledge](../knowledge/facet-partition-value-list-scale-limit.md)).
- **Multi-facet need**: the 013 live run's outcome-facet groups were structurally
  invisible to a synthesis referencing the intervention facet — one lens per run.
- **ICF's promised facet**: 021 deferred "grouping BY context_type" to this slice;
  ICF stores its content as `claim` prose scoped by a closed enum (deliberately no
  extraction-time labels), so the useful ICF lens is *claim-theme clustering* —
  prose in, themes out — which the value-string partition machinery cannot do.

Separately, the owner observed live (Langfuse, 2026-07-14) that partitions
over-fragment — too many too-granular groups — plausibly caused by the exhaustive
one-call framing itself.

## Decisions

1. **Components stay distinct; clustering machinery converges.** Characterise
   (corpus landscape) and group (findings facets) keep their own substrates, gates
   and consumers. Underneath, ONE shared code-owned orchestration/validation core —
   **open discovery** (labels + descriptions only, never an exhaustive id list)
   then **batched assignment validated against the deterministically known unit-id
   list** (no fabricated ids, no double assignment, unplaced units land in the
   counted residual). Discovery stays open; validation binds assignment. The
   two-stage shape removes the one-call partition cliff structurally. Characterise
   refactors onto the core **behaviour-preserving** (prompts byte-identical;
   component-specific bound policies: characterise keeps MIN 3 / MAX 12, group gets
   min 0 with a corpus-relative ceiling).
2. **Facet fan-out lives IN one `group` run** (owner shape, 2026-07-12): the
   directive names a facet list; separate per-facet engine runs inside one
   component execution, one `grouping_result` row, one synthesise grouping
   reference (`fk_synr_grouping` untouched). This dissolves the recorded multi-run
   design questions (reference-shape list, share-one-extraction rule,
   capability-run-entity dependency) by construction.
3. **Facet moves to group grain** — the row-level `facet` column is migrated in
   place (greenfield: consumers rewritten in the same migration —
   `synthesis_result.blocks` group ids and theme-annotation `referenced_ids` get
   the deterministic old-label → `facet:gNN` mapping); ids are facet-qualified
   everywhere they travel; downgrade refuses when multi-facet rows exist.
4. **The engine is parameterised by unit projection**: value facets = normalized
   value + counterparts + bounded anchor-quote context (on by default — the owner
   overrode the light-default posture; source content only, replay pin-or-revert);
   claim-theme facets = ICF claim prose. **Claim-theme facets ship as the
   high-value trio** (`barrier_theme` / `enabler_theme` / `mechanism_theme`), each
   facet's eligible universe = exactly the ICF rows with matching `context_type`
   (other findings are outside the base, never residual noise). A bare enum
   partition is not a facet (that read surface exists as
   `icf_context_type_count`).
5. **Granularity is steered by a corpus-relative ceiling, never an absolute
   target** (owner, correcting the drafted fixed-band idea): `max_groups =
   clamp(ceil(N/5), 3, 40)` computed per facet run and injected into discovery; no
   lower bound; direction carried by qualitative guidance; never fixed by
   catch-all buckets or code-side merges.
6. **Per-facet failure isolation** (flag-not-drop at facet grain): facet-local
   failure classes persist on that facet's outcome object while siblings survive;
   only corrupt shared input or cross-facet invariant violations abort the
   component.
7. **Cross-kind UNION read view** ships with its first reader: shared reference
   columns only (per the data-model commitment); value-facet loading reads through
   it; claim-theme loading reads the ICF table directly (kind-scoped facet,
   kind-scoped read — `claim` prose is deliberately not shared vocabulary).
8. **ICF `context_label` rider** (`icf_v2`): a nullable, strictly source-named
   short label — filled only when the source itself provides one, never
   extractor-authored summarisation (vetter-flagged). Reasoning corrections
   recorded from the owner's challenge (2026-07-14): cross-source naming variance
   was never the objection (grouping absorbs it, same as intervention);
   clustering-noise dissolves with claim prose as unit context; and
   pre-ground-truth is the CHEAP fingerprint moment (the 021 setting-rider
   precedent) — the eval slice ground-truths the field alongside the rest of ICF.

## Consequences

- Implementation-shaped theme claims get validated groups behind them ("planning
  delays recur as a barrier across heat-pump programmes" = barrier_theme group ×
  kind-spanning intervention group), reference-mediated as designed.
- The ~184-value failure mode is closed by construction; scale pressure moves to
  batch size (50) with a pre-computable call budget.
- Remaining four `context_type` theme facets are config additions, not machinery
  (deferred.md).
- Eval note: grouping-quality baselines cut before this slice do not transfer —
  the eval slice re-baselines granularity and unspanned counts (the companion
  Phase-2 changes are recorded in the task contract, not this ADR: cost work,
  repair micro-call, unspanned precision fixes, steer surface, `synthesise_section_v7`).
