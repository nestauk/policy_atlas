---
type: Capability spec
title: Options Scoping — trust rules
description: OS's instance of the trust contract — generation is free, interpretation is labelled, assessment is grounded; the effect and transferability cells report and never compute.
tags: [capability, options-scoping, provenance, honest-absence, no-composite]
timestamp: 2026-09-04
---

# Options Scoping — trust rules

OS's most consequential outputs are **judgments about options** — how big, how sure, does it
transfer, what to test first — made early, on a shallow pass, in domains the corpus may cover
thinly. The design must make it structurally impossible for a suggestion, a guess or a shallow
pass to masquerade as an assessed fact, and for a fused number to stand in for a judgment. This
file is OS's instance of the system trust contract
([../../system/provenance-grounding.md](../../system/provenance-grounding.md)); distilled from
[options-scoping-concept.md](../../sources/options-scoping/options-scoping-concept.md) § Trust
principle, § Effect cell, § Transferability cell, rulings 3, 4, 12, 13, 14.

## The principle: generation is free, interpretation is labelled, assessment is grounded

- ✅ **Generation is free.** Suggesting an option needs no source. A suggestion is a labelled
  hypothesis ("suggested by Policy Atlas", "added by you") and enters the same funnel as
  evidence-derived options. This is how structural and thin-evidence options get in at all.
- ✅ **Interpretation is labelled.** Mechanism sentences, failure modes and assumptions reuse the
  EB's claim-type and grounding-tier machinery rather than a new scheme: tier-2/3 inferences
  where the literature supports them; capped, visibly labelled *reasoning* claims (tier 4,
  "reasoning, not evidence", which must not smuggle findings) where they are the model's own
  analysis. The full evidence search is what upgrades interpretive claims toward cited tiers.
- ✅ **Assessment is grounded.** Anything *asserted* about an option — evidence strength, effect,
  transferability, case studies, costs — requires retrieval: tiers 1–3 only. Unassessed cells
  are honest empty states: "not yet searched" or "no credible evidence found", never a hedged
  guess. Before assessment an option shows only what the screened set holds (counts, countries,
  source types) and says so.

## Provenance labels every surface carries

- ✅ **Depth label per row and per profile:** *scoping pass* (title-and-abstract screened, not
  full-text confirmed) or *full run* (the EB task's confirmed document set). The label states
  what was and was not read.
- ✅ **Source tier per case study:** academic · Overton grey literature · verified web. A web
  case study never raises an evidence-strength rating. The baseline's skew to official
  statistics and grey literature is shown, not hidden.
- ✅ **Coverage denominators:** "3 of 5 documents", "6 of 9 evaluations" — never a bare
  adjective standing in for a count.
- ✅ **What was searched** is stated on the Sources tab and in the Export bundle: documents
  retrieved and passed, grey literature, web, screens applied, and explicitly *not searched*.
  Breadth is claimed; exhaustiveness never is.

## The effect cell: report, don't compute

- ✅ V2's 1.0–5.0 impact score is the anti-pattern (a composite of categorical LLM judgments,
  similarity weights and dampening with undefined buckets, unknown treated as a small positive,
  two competing formulas, and extracted uncertainty that never entered the score). The
  no-composite rule extends to **cells, not just rankings**.
- ✅ **Direction** by transparent vote count of quality-screened studies ("9 of 11 found
  reductions") with a **discord flag** when the evidence genuinely conflicts.
- ✅ **Magnitude** quoted in native units with citations ("10–25% across 3 RCTs"), never
  converted across measure families, never pooled across contexts.
- ✅ **Scannability** via the source's own characterisation, quoted with provenance ("a small but
  robust effect"). ✅ **No analytical banding in v1**; ❓ banding after v1 requires its own eval
  (literature-anchored or session-calibrated, concept open question 9).
- ✅ Sortable by direction consensus or evidence strength; **there is no impact scalar**.

## The transferability cell: the one opinionated cell, working shown

- ✅ The **three-legs argument** (worked somewhere · same causal role · support factors present);
  any weak leg collapses the argument.
- ✅ **Moderator and dealbreaker extraction** with verbatim quotes and evidence-basis tags
  (empirical · author hypothesis · theory background).
- ✅ **Default-to-Unknown context discipline:** the Factor | Evidence says | Your context | Basis
  table, where **only user-stated facts count** as the user's context — populated from the plan,
  never inferred. Unknown stays unknown.
- ✅ **Ceiling rules:** deterministic caps on verdict strength — "conditional" at most when
  mechanism confidence is weak or most support factors are unknown — and the cap reason is
  always shown. Calibrated language, not a number. ✅ **No numeric fit score, no dampening**;
  the two V2 scoring mechanisms do not fold in.
- ✅ The user's context lives with the scoping task, so a cap caused by unstated context
  survives a full evidence search until the plan says otherwise. The cell is a first-class eval
  axis (calibration).

## Reasoned guesses: interpretation in the shortlisting stage

- ✅ For constraints that can only be checked after assessment (cost, effect, evidence
  strength), each option carries a **reasoned guess** — a capped reasoning claim ("cost: likely
  low, a guess rather than evidence") — so shortlisting and conditional recommendations can use
  it honestly.
- ✅ Guard rails: capped wording ("likely", never "is"); visibly labelled on every surface; a
  flag and a sort, **never a screen, never an exclusion**; replaced by the reported fact with
  provenance after assessment, with any disagreement shown side by side ("guessed low; reported
  £6,500 per placement"). ✅ Guess-versus-evidence agreement is an eval axis.

## Screening and shortlisting: judgments that are checkable, never silent

- ✅ Every exclusion cites the specific constraint it broke; the excluded option stays visible
  in its theme and can be included again. Thin evidence never excludes. LLM judgments about
  whether an option breaks a constraint are fallible and therefore shown and overridable.
- ✅ Shortlist places carry a **single named reason** on a single axis, limited to what is known
  at that depth. **Never a fused cross-list score**; weights are a political question.
  "Most promising" is per-axis sorts and conditional recommendations only.
- ✅ The summary above the assessed table is PA's reading, never a ranking, and says so.

## What is structurally impossible

- A suggestion appearing with an evidence-strength rating it did not earn.
- A scoping-pass cell displayed without its depth label, or a full-run cell without its task.
- A number in any cell or ordering that was computed by fusing judgments.
- A guess that excludes an option, or a guess that survives the reported fact without both
  being shown.
- A transferability verdict stronger than its ceiling rule allows, or a "your context" entry
  the user did not state.
- A case study raising the how-sure rating.
