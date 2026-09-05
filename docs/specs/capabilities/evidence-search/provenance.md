---
type: Capability spec
title: Evidence search — derived-claim provenance
description: EB's instance of the trust contract — making it structurally impossible for a pipeline artefact to masquerade as a corpus fact.
tags: [capability, evidence-search, provenance, honest-absence]
timestamp: 2026-06-22
---

# Evidence Base — derived-claim provenance (the central trust rule)

EB's most consequential claim is an **absence** ("little evidence exists on X"), so the design
must make it **structurally impossible for a pipeline artefact to masquerade as a corpus fact.**
This file is EB's instance of the system trust contract
([../../system/provenance-grounding.md](../../system/provenance-grounding.md)); the framework
rule (gap coverage base, pattern grades) is owned there, and the coverage-state set by
[../../system/data-model.md](../../system/data-model.md). The gap rule below is EB's application of
that framework rule, not its definition. Distilled from
[backend-evidence-base-build-spec.md](../../sources/backend/backend-evidence-base-build-spec.md) §2
*(Derived-claim provenance)*.

## Why this is acute for EB

The `select → extract` gating is what makes it sharp: extraction is gated to the **selected
subset**, so the extracted finding set is a **strict subset** of the relevant corpus. Any absence
read off extracted findings is relative to *what EB chose to extract*, **not** to the corpus.

## The gap rule (framework-level, applied by EB)

- **Every gap / absence claim carries its coverage base** as a required field — the pipeline
  ladder **attempted-search → acquired → screened → selected → extracted.** Each rung narrows;
  each narrowing can manufacture a false absence.
- **Only `searched_and_absent` over an adequately-searched base licenses an absence claim.**
  `not_selected` (screened-in but not chosen — the gap `select` creates), `not_extracted`,
  `extraction_failed` and `unclear` **never** do. A reported null is a **finding**, not a gap; a
  silence is **coverage**.
- **Even `searched_and_absent` is bounded by acquisition scope** — absence is "absent from the
  *searched* space" (configured backends / trust classes), never absolute; a corpus-level absence
  carries a **search-adequacy caveat**.
- **Shallow vs deep base, from the depth axis:**
  - characterise's **shallow** coverage rests on the **screened** base (the whole relevant corpus
    — flag-not-block, so no false gaps);
  - synthesise's **deep** coverage rests on the **selected / extracted** base (a subset), must be
    **base-labelled**, and is **never promoted to corpus absence.**
  - **The shallow landscape is the structural check on a deep absence:** nothing on X in extracted
    findings *but* X-relevant docs in the screened-base landscape ⇒ surfaced as `not_selected`,
    **not** "little evidence exists."
- **`search_coverage_record` operationalises "adequately-searched"** — a corpus-level absence
  references a record with the **search-space boundary** (backends / trust classes), a **stop
  condition** (v3.0: *breadth-truncated* / *re-searched-still-thin* / *error* — **`saturated` is
  not a v3.0 value**; saturation-based stopping is a ⏸ seam), an **adequacy verdict + origin**
  (model or human), plus by reference the queries/expansions run (→ `search` governance events)
  and scope filters (date/geography/language + citation/recency floor). **Fail closed:** absent a
  non-`inadequate` record, an absence degrades to "not found in extracted/selected material,"
  never corpus-level.

## Patterns — three grades, never conflated

The same discipline applies to *patterns*, not only gaps. Each grade carries different authority:
1. **Deterministic metadata patterns** — counts/distributions over Tier-0 columns. Facts: exactly
   reproducible, profile-independent, over the whole screened base. *Hardest grade.*
2. **Finding-query patterns** — counts/direction-spreads over extracted findings. Deterministic
   *given the recorded (finding-set, coverage-state, extraction-profile)*, but extraction-coverage/
   profile-dependent — carry that provenance; **not metadata-grade**. ❓ their grade + roll-up
   relationship left open. *Middle grade.*
3. **Thematic clustering** — the `cluster` groupings (topic-level at characterise, facet-level at
   `group`), LLM-labelled. An **interpretive shape, not a count** — recomputable, never a
   deterministic fact. *Softest grade* (facet grouping at `group` also inherits the extraction
   dependency).

## How EB surfaces this

- The **dual-view coverage** at characterise (overall vs policy-filtered "well-evidenced") is the
  honest way to show where the base thins under the user's citable bar **without manufacturing a
  gap** — below-policy evidence is **present-but-flagged**.
- The **deepening-selection steer-point** ([capability.md](capability.md)) escalates exactly when
  selection would create a material `not_selected` gap (a large / high-priority / user-nominated
  cluster dropped) or when the base is thin / the policy is unmeetable above-bar.
- At synthesise, the source/evidence policy is **flag-not-block**: below-bar support is **flagged
  weakly-grounded / below-policy**, never hidden or silently dropped (project-wide
  flag-don't-drop).
