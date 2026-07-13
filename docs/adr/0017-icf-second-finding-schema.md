# ADR 0017 — `implementation_context_finding`: the second reusable finding schema

**Status:** Accepted — 2026-07-12 · owner (contract + plan approved same day; both
adversarially reviewed and adjudicated — 8/8 and 6/6 findings adopted).
**Task:** [021-icf](../tasks/021-icf/contract.md) · design research:
[design-research.md](../tasks/021-icf/design-research.md).

## Context

v3.0's findings layer shipped with one reusable schema (`intervention_outcome_finding`,
ADR 0007/0016). Implementation-shaped material — mechanisms, barriers, enablers,
conditions, delivery/process, adaptations, fidelity — had no structured home:
implementation-shaped pattern claims were prohibited in synthesis for lack of a
deterministic validator, and the future Transferability / Options Assessment / Baseline
capabilities need this substrate. The owner promoted ICF pre-eval (2026-07-12, 020
contract review): EB synthesis is its first reader, and eval baselines must be cut on
the intended composition.

## Decisions

1. **A second typed schema, not a generic container and not runtime custom
   extraction** (011 rulings re-affirmed against the V2 question taxonomy). Typed
   records are what deterministic validation, ground truth, memo reuse and
   cross-question interpretability rest on; the long tail of question shapes is served
   by verified chunk-grounded synthesis (ADR 0010). Future kinds are added deliberately
   via the recorded schema-candidate ladder (`reported_statistic`, `case_example`,
   `intervention_specification`; first readers named; additive schemas never
   invalidate eval baselines).
2. **Separate extraction call/profile with its own fingerprint domain**
   (`eb_icf_base_v1` / `icf_v1`). One combined pass was rejected: memo isolation
   (ICF iteration must not re-extract IOF), the with/without-ICF eval axis (the IOF
   arm must be byte-identical across compositions), and focused-call extraction
   quality (the V2 cross-contamination lesson).
3. **The extract pipeline goes profile-parameterised** — a per-domain bundle
   (models + prompt + rules + vetter + table writer + judge payload) bounded to what
   the two real instances force; a third schema is content work, not plumbing. The
   `extraction_result` roll-up becomes per-profile keyed JSON (no DDL), carrying
   "profile not selected" vs "fired, zero findings".
4. **Composition is a plan-visible directive**: the extract directive's `profiles`
   field, fail-closed compile, defaults per depth (deep → both), IOF-only expressible;
   planner prompt updated (lead-only) — no silent compilation.
5. **Field set grounded in the transferability/appraisal frameworks** (TRANSFER,
   PIET-T, GRADE EtD, Green Book, CFIR 2.0, FRAME, Carroll/TIDieR — design-research.md)
   under the source-groundability line: extraction captures the SOURCE side of every
   comparative judgment; target-context values and transfer verdicts are analysis
   work, never extraction (V2's inferred High/Moderate/Low ordinals are the recorded
   anti-pattern). Seven-value `context_type` (incl. `adaptation`, `fidelity`);
   `claim_basis` three-way (V2 forecast EvidenceBasis pulled through); `claim_level`
   study|pooled joins the claim key (count honesty for pattern claims); `level`,
   `resource_requirements`, `workforce_requirements`; shared source-named references.
6. **Shared reference vocabulary defined once** (code-level mixin + cross-schema
   drift guard; shared meaning/coercion, per-schema requiredness overrides). Storage
   stays parallel tables — a merged table is two disjoint payloads glued to a common
   header. Cross-schema linkage stays reference-mediated via `group` (no link
   objects); the UNION read view rides Slice C with its first reader.
7. **IOF `setting` rider (`iof_v3`)** — the shared vocabulary was always
   intervention/outcome/population/setting, and setting is what GRADE
   indirectness/Wang/TRANSFER compare for effect evidence too. One bounded,
   owner-approved bump before ground truth exists (the only cheap moment); top-level
   setting coexists with stratum setting and does not join the IOF claim key (the 020
   geography precedent). Nothing else rides the bump.
8. **One unified kind-typed `query_findings`** (kind-segregated typed return,
   fail-closed kind filters, per-kind caps, honest per-kind availability) — the
   dominant writer query is "effects AND context of intervention X" and writer turns
   are the run-cost centre; related-but-distinct is held by the record-level fences,
   not the tool boundary. Pre-discharges the N-schema writer-tool seam.
9. **Kind-spanning group membership (minimal bridge)** — group's loader reads both
   tables via the shared references (facet shape untouched; `direction_spread`
   IOF-members-only; kind tags); without it, ICF findings would never reach the
   writer envelope on grouped runs. Slice C's multi-facet redesign inherits it.
10. **ICF vetter with IOF storage semantics** — flag classes `recommendation` ·
    `aspiration` · `vague_context` · `deictic_naming`; vetted-out findings excluded
    from insert and recorded in the doc summary (flag-not-drop = recorded in
    provenance, not row persistence). All prompt surfaces developed through the
    018-style bounded refine-replay loop, honestly eval-blind.

## Consequences

EB synthesis gains deterministically-validated implementation-shaped pattern claims
and ICF finding claims (theme claims over kind-spanning groups at the existing softest
grade); Transferability/Options/Baseline get their substrate without re-extraction
(the V2 forecast's re-extract-from-chunks pathology is the failure this layer
prevents). Costs: one added mini-priced extraction + vetter call per selected document
per run at deep; one deliberate IOF memo invalidation now, none later. Deferred with
owners: ICF facets, hybrid dimension search, UNION view (Slice C) · ICF ground truth +
with/without-ICF axis (eval slice) · schema-candidate ladder (Baseline et al.).
