# ADR 0007 — Extraction: durable findings layer, memo fingerprint, deterministic quote anchoring

- **Status:** Accepted — 2026-07-07 (Shabeer Rauf, task-011 contract + plan gates).
- **Date:** 2026-07-07
- **Context doc:** [task 011 contract, decisions 1–9](../tasks/011-extract/contract.md)
  (revision history records the full decision trail, revs 1–1.5, including the
  field-research and V2-autopsy adoptions and both adversarial reviews) ·
  [EB components §7](../specs/capabilities/evidence-base/components.md) ·
  [data-model — the findings layer](../specs/system/data-model.md) ·
  [EB provenance](../specs/capabilities/evidence-base/provenance.md) ·
  [ADR 0006](0006-selection-strategy-directive-rerank.md) (the explicit
  upstream-run reference and prompt-surface precedents this slice extends).

## Context

Extract (EB component 7) is the step `select` exists to gate: per selected
document, produce `intervention_outcome_finding` records — the framework's
first reusable findings-layer schema, and the substrate `group`/`synthesise`
and every downstream capability will consume. Three pressures shaped the
design. First, the data-model makes findings **information-layer records**
(durable, reusable, memoised), unlike the run-local characterisation and
selection rows — so this slice sets the precedent for how durable derived
records live in the schema. Second, the trust rules are sharpest here: the
extracted set is a strict subset of the corpus, findings are what grounded
synthesis will cite, and extraction is where a model could fabricate
source-attributed content at scale. Third, the V2 autopsy (task-011 research)
showed exactly how this component fails when built loosely: permissive
post-hoc fuzzy grounding that validated topic overlap rather than quote
authenticity, question-relative judgements baked into atomic records,
prompt/schema drift silently deleting fields, forced effect-shaped output from
qualitative documents, and extraction quality that was never measured.

## Decision

1. **Two lifetimes, three tables.** Findings are durable:
   `intervention_outcome_finding` rows are never invalidated or overwritten by
   later runs — a model/prompt/rule upgrade creates records alongside under a
   new fingerprint. Per-document `source_extraction_record` rows carry the
   memo key and doc-level status (`extracted` | `no_findings` |
   `extraction_failed`; "processed, found nothing" is a first-class,
   memoisable state). The run-scoped `extraction_result` roll-up (one per
   (scope, run), referencing its `selection_run_id` explicitly) is what the
   next component references — the ADR-0006 explicit-reference pattern
   continued. A generic schema-typed finding container was considered and
   declined: the two specced evidence kinds are "related-but-distinct, never
   blended", closed vocabularies want DB-level enforcement, and the schema set
   grows at spec pace (revisit trigger: a third finding schema).
2. **The memo fingerprint covers every output-affecting version.** A digest
   over {profile, output schema, prompt, model, backend mode, field-rule set,
   quote-verifier version, windowing policy}. Reuse happens only against
   success states — the memo key is a partial unique index over
   `extracted`/`no_findings`, so failed attempts insert freely as history and
   never block their own retry. Stub-mode fingerprints are distinct by
   construction; stub results can never masquerade as live extraction.
3. **Extraction is question-agnostic.** The prompt receives the document
   (id-keyed segment records), its envelope, and its evidence type — **never
   the scope intent**. Base fields are what the source reports;
   question-relative judgements (normalised magnitude, causal weighting,
   is-beneficial) are enrichment for later capabilities. This is both the
   spec's line and V2's hardest-won lesson (judgement baked into atomic rows
   made them unusable for any other question), and it is what makes the memo
   sound: the same document extracts identically whichever scope asks.
4. **Deterministic quote anchoring, graded, with no LLM repair.** Every
   finding anchors to frozen source text: verbatim quote + a chunk location
   or abstract-envelope location per its basis. Verification is a normalised
   string match (casefold, whitespace-collapse, punctuation folding) with an
   ordered occurrence cursor (repeated quotes map to successive occurrences)
   against the concatenated frozen text, recording raw-text char intervals and
   a graded match status. Failure flags `quote_unverified` — kept, counted,
   never dropped, never re-asked. Deterministic-only keeps the call budget
   exact and grounding *measurable* (run-level verified-share scores from the
   first live run — V2's ">95% grounding" was folklore; ours is a metric).
5. **Full read, honest coverage.** Every selected document is read whole
   (windowed past a token budget; windows independent and parallel;
   abstract-only documents extracted from their envelope, basis-flagged,
   never skipped). Retrieval-scoped extraction was declined: reading a
   retrieved subset makes `no_findings`/`not_extracted` unverifiable — a
   silent new rung on the coverage-base ladder. Doc statuses cover exactly
   the selected set; a reported null is a finding (`no_effect`); coverage
   states are never phrased as absence. Field-level honesty is enforced in
   code: deterministic field rules (bounds, coherence, null-string coercion)
   flag rather than fabricate; within-doc dedup keys on the claim (anchors
   merge) so MECE is enforced, not requested.
6. **The field set carries the V2-proven sharpenings.** Outcome is the base
   measure; timepoint/subgroup/setting live in canonical stratum qualifiers.
   Comparator is a source-named reference. An estimate-level discriminator
   ({study | pooled | claim}, with k/I²/τ² for pooled shapes) lets one schema
   hold both a meta-analysis's pooled findings and a primary study's — the
   part of V2's extraction that genuinely worked, preserved. These ride a
   minor data-model flow-back approved with the contract.

## Consequences

- `group` (component 8) reads a stable, typed, claim-grained substrate with
  groupable source-named references, and references this run's roll-up by
  `extraction_run_id` — the run-reference chain now spans characterise →
  select → extract.
- Extraction cost is paid once per (snapshot, fingerprint) across runs and
  scopes; the extraction *service* (profile resolution, task objects) and
  evidence dataset snapshots remain seams with the minimal honest memo in
  place.
- The quote-verification module and its grounding scores create the first
  measurable extraction-quality surface; the extraction-quality eval seam
  (finding-level ground truth) is where multi-pass recall,
  reason-then-constrain, fuzzy fallback, and per-intervention decomposition
  wait, each with a recorded trigger.
- Mixed/unclear findings are first-class records; the flag-not-drop
  obligation transfers forward to group/synthesise explicitly (V2 extracted
  them and then aggregation silently zeroed them).
