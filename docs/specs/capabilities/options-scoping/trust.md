---
type: Capability spec
title: Options Scoping — trust rules
description: OS's instance of the trust contract — generation is free, interpretation is labelled, assessment is grounded; the effect and transferability cells report and never compute.
tags: [capability, options-scoping, provenance, honest-absence, no-composite]
timestamp: 2026-09-07
---

# Options Scoping — trust rules

OS's most consequential outputs are **judgments about options** — how big, how sure, does it
transfer, what to test first — made early, on a shallow pass, in domains the corpus may cover
thinly. The design must make it structurally impossible for a suggestion, a guess or a shallow
pass to masquerade as an assessed fact, and for a fused number to stand in for a judgment. This
file is OS's instance of the system trust contract
([../../system/provenance-grounding.md](../../system/provenance-grounding.md)); distilled from
[options-scoping-concept.md](../../sources/options-scoping/options-scoping-concept.md) § Trust
principle, § Effect cell, § Transferability cell, rulings 3, 4, 12, 13, 14, and the review-round
rulings 15–23, 26 (which win where they differ). The review's central correction: the trust
boundary runs between **propositions**, not between cells or sections — a labelled row is not a
supported sentence, and the sentence is what gets copied into advice.

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
- ✅ **Support belongs to the specified design** (ruling 15). Evidence for a youth guarantee with
  an obligation is not evidence for one without. A user-modified option is a variant with its
  own assessment; the parent's evidence appears in its profile only as *related evidence for a
  different design*, never in its row or the summary. The unresolved difference stays in the
  main proposition ("a hypothesis, with evidence from related implementations and an unresolved
  difference"), not in a caveat beside the parent's numbers.
- ✅ **Claim depth follows reading depth** (ruling 16). Every claim carries the depth of what was
  read — abstract or full text. A section may not assert what the read material does not
  support. Abstracts are quotable anywhere. "Reasoning" never labels an empirical claim about
  the corpus ("every evaluated scheme paired the offer with an obligation" is a sourced corpus
  finding with a stated search boundary, or it is not said).

## Provenance labels every surface carries

- ✅ **Depth label per row and per profile:** *scoping pass* (screened on titles and abstracts;
  full text read for the documents cited; document set not confirmed) or *full run* (the EB
  task's confirmed document set). The label describes the work done; it does not stand in for
  claim-specific support, which each claim carries itself (ruling 16).
- ✅ **Source tier per case study:** academic · Overton grey literature · verified web. A web
  case study never raises an evidence-strength rating. The baseline's skew to official
  statistics and grey literature is shown, not hidden.
- ✅ **Coverage denominators:** "3 of 5 documents", "6 of 9 evaluations" — never a bare
  adjective standing in for a count.
- ✅ **What was searched** is stated on the Sources tab and in the Export bundle: documents
  retrieved and passed, inherited versus added (ruling 22), grey literature, web, screens
  applied, what was read at which depth, and explicitly *not searched*. Breadth is claimed;
  exhaustiveness never is.
- ✅ **The record travels** (ruling 21). The export carries the full longlist with states and
  reasons and the shortlist assembly record, so a reader outside Atlas can see what was
  considered, excluded and why.

## The effect cell: report, don't compute

- ✅ V2's 1.0–5.0 impact score is the anti-pattern (a composite of categorical LLM judgments,
  similarity weights and dampening with undefined buckets, unknown treated as a small positive,
  two competing formulas, and extracted uncertainty that never entered the score). The
  no-composite rule extends to **cells, not just rankings**.
- ✅ **Direction** by transparent vote count of quality-screened studies ("9 of 11 found
  reductions") with a **discord flag** when the evidence genuinely conflicts. Rules (ruling 26):
  one vote per independent study; direction defined per outcome family; statistical
  significance never counted. Tallies are per option and **not sortable across options**.
- ✅ **Magnitude** quoted in native units with citations ("10–25% across 3 RCTs"), each with
  its own comparator, population and period, never converted across measure families, never
  pooled across contexts.
- ✅ **No false common comparison** (ruling 17). Scoping does not forecast, so it never compares
  an option against the UK baseline. The do-nothing band is worded as the situation these
  options would change, never "compared against". The summary uses no superlatives across
  options and makes conditional recommendations only on comparable axes (evidence strength,
  where tried, cost as reported), never on magnitude or direction.
- ✅ **Scannability** via the source's own characterisation, quoted with provenance ("a small but
  robust effect"). ✅ **No analytical banding in v1**; ❓ banding after v1 requires its own eval
  (literature-anchored or session-calibrated, concept open question 9).
- ✅ Sortable by evidence strength and study count only (the direction-consensus sort is
  dropped, ruling 17); **there is no impact scalar**.

## The transferability cell: the one opinionated cell, working shown

- ✅ The **three-legs argument** (worked somewhere · same causal role · support factors present);
  any weak leg collapses the argument.
- ✅ **Moderator and dealbreaker extraction** with verbatim quotes and evidence-basis tags
  (empirical · author hypothesis · theory background).
- ✅ **Default-to-Unknown context discipline, three sources** (ruling 18): the Factor | Evidence
  says | Your context | Basis table takes context entries typed **retrieved** (from the
  baseline or the assessment, cited, geography-tagged and counted only where it matches the
  target unit), **stated by you** (a fact about the present) or **planned by you** (a
  commitment). Never inferred. Unknown stays unknown. Only the first two can lift a cap; a
  commitment becomes a named condition of a conditional verdict ("Conditional on: local
  delivery funded"). A stated intention never acquires the force of verified capacity.
- ✅ **Ceiling rule: the weakest leg decides.** The verdict word is set by the weakest of the
  three legs; an unknown or absent dealbreaker caps the verdict on its own whatever the other
  factors say; prior use somewhere satisfies one leg only. **No factor fractions anywhere.**
  The cap reason is always shown. Calibrated language, not a number. ✅ **No numeric fit score,
  no dampening**; the two V2 scoring mechanisms do not fold in.
- ✅ The user's context lives with the scoping task, so a cap caused by unstated context
  survives a full evidence search until the plan says otherwise. The cell is a first-class eval
  axis (calibration).

## Reasoned guesses: interpretation in the shortlisting stage

- ✅ For constraints that can only be checked after assessment (cost, effect, evidence
  strength), each option carries a **reasoned guess** — a capped reasoning claim ("cost: likely
  low, a guess rather than evidence") — so the user can sort by it if they choose.
- ✅ Guard rails: capped wording ("likely", never "is"); visibly labelled on every surface; a
  flag and a **user-requested** sort, **never a screen, never an exclusion, never an input to
  the shortlist proposal or to any pre-assessment recommendation** (ruling 19: guesses must not
  allocate attention, or the options they discourage never reach the assessment that would
  correct them); replaced by the reported fact with provenance after assessment, with any
  disagreement shown side by side ("guessed low; reported £6,500 per placement"). ✅
  Guess-versus-evidence agreement is an eval axis.

## Screening and shortlisting: judgments that are checkable, never silent

- ✅ Every exclusion cites the specific constraint it broke; the excluded option stays visible
  in its theme and can be included again. Thin evidence never excludes. LLM judgments about
  whether an option breaks a constraint are fallible and therefore shown and overridable.
- ✅ **A restriction on evidence is not a restriction on options** (ruling 23). Evidence-scope
  constraints act on retrieval and screening and can never exclude an option; an option whose
  only example is out of scope stays, marked "no in-scope evidence". The agent asks when a
  sentence is ambiguous. Screens judge the option's specified design; screen findings that rest
  on the corpus are cited.
- ✅ Shortlist places carry a **single named reason** on a single axis, limited to what is known
  at that depth; study count alone is never a reason; thin evidence is a reason to assess
  (ruling 19). Coverage is one place per lever type present (ruling 20). **Never a fused
  cross-list score**; weights are a political question. "Most promising" is per-axis sorts and
  conditional recommendations only, on comparable axes.
- ✅ **Omissions are explicit.** The summary and the export list every kept option that was not
  assessed, by theme, so "no ranking" cannot be defeated by silent selection (ruling 19).
- ✅ The summary above the assessed table is PA's reading, never a ranking, and says so.

## What is structurally impossible

- A suggestion appearing with an evidence-strength rating it did not earn.
- A variant's row or the summary showing evidence that was earned by a different design.
- A claim asserted at a depth greater than the material read for it.
- A scoping-pass cell displayed without its depth label, or a full-run cell without its task.
- A number in any cell or ordering that was computed by fusing judgments; a sort across
  options on a non-comparable measure; a superlative across options in the summary.
- A guess that excludes an option, that feeds the shortlist proposal, or that survives the
  reported fact without both being shown.
- An option excluded by a restriction on evidence.
- A transferability verdict stronger than its weakest leg allows, a "your context" entry that
  was neither retrieved with a citation nor stated by the user, or a cap lifted by a plan.
- A factor count standing in for a transferability judgment.
- A case study raising the how-sure rating.
- An export from which a reader cannot see what was considered, excluded and why.
