# ADR 0016 — IOF schema v2: effect basis as its own dimension, finding-grain geography

**Status:** Accepted — 2026-07-12 (Shabeer Rauf; task 020 contract + plan, both
approved 2026-07-12 with two Codex adversarial reviews — contract-stage 8 findings/8
adjudicated, plan-stage 9/9 adjudicated, one recommendation flipped). The decision
trail lives in `docs/tasks/020-extract-v2/contract.md` (owner calls inline) and
`plan.md` § Gate decisions.

## Context

The 018 live runs surfaced a structural gap in `intervention_outcome_finding` (iof_v1,
task 011): nothing lets a surface render "this is a projection, not something that
happened". `causality_by_design` folds modelling into `descriptive` alongside observed
descriptive statistics; `study_design` is free text and null-when-unreported (61/122
`not_extracted` on the 018 step-9 replay). Separately, the 011 security review recorded
a prompt-envelope injection seam (title/abstract interpolated inline in the user
template) to be fenced "at the next version bump", and rev 3.2 recorded that no search
API supplies study geography — an extraction-schema gate. The owner-adjudicated pre-eval
sequencing (2026-07-12) requires all schema/vocabulary changes to land BEFORE extraction
ground truth is authored: every fingerprint change re-extracts the corpus, and ground
truth written against v1 would need re-authoring. Task 020 is that one bump.

## Decisions

1. **`effect_basis` is its own dimension, not a `causality_by_design` extension** —
   enum `observed` | `modelled`, null if indeterminate, on the IOF wire and row.
   Causal identification and evidence basis are different axes: a model calibrated on
   RCTs is still modelled. Extending the causality vocabulary was considered and
   rejected (owner, 2026-07-11, recorded in deferred.md; re-affirmed at the 020
   contract).

2. **`effect_basis` joins `claim_key`; `study_geography` does not** (plan-gate
   adjudication of the contract-stage adversarial finding). An observed claim and a
   modelled projection of the same effect are *different claims* — first-wins dedup
   collapsing them would destroy the distinction the field exists to make. Geography
   matches the `population`/`study_design` treatment (descriptive study metadata,
   first-wins): geography-scoped *claims* are already stratum territory
   (`stratum_qualifiers`), so keying on geography would double-represent them.

3. **`study_geography` sits at finding grain** (owner, 2026-07-12) — a single
   source-named string ("the geography of the evidence underlying this finding,
   exactly as the document reports it"), null when unreported, never inferred from
   publisher/venue/affiliation. Geography is document-constant only for primary
   studies; in reviews — the corpus's dominant shape — it varies per finding, the same
   pattern that already puts `population`/`study_design`/`comparator` at finding grain.
   Document-level geography is a *derived aggregation*, deferred with the
   selection-diversity consumers. A document-grain field would have required a new
   doc-level wire surface plus cross-window reconciliation for zero consumer benefit.

4. **No backfill, no invalidation.** Existing v1 rows keep null; new fingerprints
   create records alongside (the data-model rule: upgrades never invalidate existing
   findings). The v1-null vs v2-null distinction is carried by `field_coverage`
   key-absence (v1 coverage maps lack the new keys entirely) plus the extraction
   record's schema version — never by guessing.

5. **`PROFILE_ID` (`eb_iof_base_v1`) does not bump** (owner gate decision 1). The
   profile is a stable requirement-family id ("EB's base IOF extraction"); field-set
   evolution is carried by the schema (`iof_v2`), prompt (`extract_iof_v6`) and rules
   (`iof_rules_v2`) version components, which each enter the extraction fingerprint
   and its recorded components map — provenance stays fully reconstructable per
   record, and a profile bump would be a redundant second invalidation lever. The
   honest counter-position (base-field additions change requirement identity) is
   recorded; the family-id reading is documented at the constant and pinned by a
   provenance test.

6. **Envelope fencing rides the bump** — title, abstract AND `primary_evidence_type`
   enter the extraction prompt as one id-keyed JSON data object (the treatment segment
   text already gets), closing the 011 injection seam. Evidence type is
   closed-vocabulary today; fencing it anyway removes the structural exception.

7. **Evidence-type provenance is attempted-call-only.** The new
   `source_extraction_record.primary_evidence_type` column records what the prompt was
   actually sent (including the `Unclassified` default), CHECK-constrained to
   `EVIDENCE_TYPES` + `'Unclassified'`; pre-prompt failure rows (`empty_basis`,
   `basis_mismatch`) record null — no prompt existed, so no provenance fact exists.
   The column is extraction-call provenance for audit and ground-truth annotation
   only; writer surfaces keep reading live classification.

8. **Annotation payloads do not embed record metadata** (owner, 2026-07-12). The
   payload stays verification output (verdict, judge provenance, anchors, spans);
   the new fields are reachable via the cited finding row, findings' immutability
   makes embed-at-mint buy no snapshot honesty, and the slice that builds an
   annotation rendering surface (C/web-app/export) decides coherently across all
   fields it needs. Purely additive later.

9. **The vetter gains one guidance line, not payload fields** (owner gate decision 2,
   flipped by the plan-stage adversarial review): modelled/projected *results* the
   document reports are findings, not aspirations — the existing aspiration rule
   ("rather than something that happened") would otherwise catch exactly the modelled
   findings v6 deliberately extracts. `extract_finding_vetter_v3`, replay-evidenced.
   The payload still excludes the new fields: showing the model its own basis label
   risks biasing aspiration flagging.

## Consequences

- Extraction ground truth (eval slice) is authored once, against this record shape,
  with `effect_basis`/`study_geography` as first-class annotation targets.
- The fingerprint change means previously-extracted corpora re-extract fresh on next
  run (mini-priced; the designed memoisation behaviour), exactly once for this bump.
- `implementation_context_finding` (slice 021) is unconstrained by this bump: pinned
  as a separate extraction call/profile with its own fingerprint domain.
- Two recorded candidates deliberately NOT riding: `effect_basis` in the judge
  envelope (bound by 018's verification-grade A/B protocol; C/eval gate) and the
  dangling 018 A/B-gated writer-envelope metadata queue — both entered in deferred.md
  by this slice's sweep.
