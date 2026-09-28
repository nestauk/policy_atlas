# Intent: longlist refinement (task 046, before task 3)

Confirmed with the owner on 2026-09-28 after the 045 review, one interview,
six pre-contract scoping runs on new domains, a deep read of what those runs
stored, and their Langfuse traces. This is the input to the contract
conversation. It states what the owner wants, not how to build it; the
contract and plan decide that. Items marked **ruling** change an accepted
spec decision and need the owner's word item by item before they land.

## What the owner wants

- **Outcome.** A longlist of about twenty options at the grain of "one
  thing a government could do", named top-down against the plan and the
  baseline with the corpus as one input. Design variants and their evidence
  sit on each option's card, never as separate rows. Every judgement about an
  option is made against the baseline's account of the status quo.
- **User.** The senior policy maker deciding what goes to assessment. Twenty
  is decidable. Forty is not.
- **Why now.** Seven live runs (NEET, heat pumps, childhood obesity, early
  caregiving, refugee integration, industrial energy prices, social cohesion)
  filled the forty ceiling with variants, bundle components and single-study
  trials in five of seven, left half to two thirds of the records
  unclustered, dropped the best systematic reviews into the residual, and
  produced settings, populations and outcomes too noisy to face. Hand folds
  of all seven land between thirteen and twenty-one options. Task 3 builds
  assessment on this list, so the shape has to be right first.
- **Success.** The same seven plans re-run land near twenty options; no
  singleton trial appears as a row; the class-grain reviews (youth
  guarantee, ALMP, combined diet-and-activity programmes) attach to options;
  option searches screen in documents about the option; adjacent-population
  evidence shows as a "tried on" line; the setting facet reads as places of
  delivery, not countries or bodies; cost per run falls well below today's
  $6 to $16.
- **Constraint.** The ceiling is a product number near twenty, not N
  divided by four. Prompt edits are hash-pinned slice work. The owner rules
  on every spec change.
- **Out of scope.** The shortlist and assessment (task 3); the
  rebuild-in-place ruling already given for task 3; the baseline and
  Evidence search profiles; the option-search query wording deferred under
  F4; any second grid axis; cross-task profile reuse.

## In scope

Grouped by where the change lives. Numbers cite the seven runs.

### The longlist

1. Discovery becomes option naming at reader grain over the plan, the
   baseline, the seeds and a compact corpus digest (distinct intervention
   names with counts and roles), with a residual pass. **Ruling: D4 (the
   ceiling formula) and A9 (instance-of).**
2. Assignment rule: a unit naming the same kind of intervention as an option
   joins it with the flag; "ungroupable" is for a different kind;
   "not an option" for non-interventions. Tried on the screen model first,
   moved only on evidence. Unit ids in prompts become short ids (five of
   seven runs paid repair calls for a mangled UUID).
3. The flag is reworded as "not stated in the abstract"; full text may
   resolve it at assessment.
4. No package minting from bundle components (cohesion: ten packages,
   twenty-nine unmatched components, zero relations; four zero-member
   component options in the NEET and NEET-rapid runs).
5. Distinct screen over the whole list, or a deterministic similarity
   pre-pass. Today it never fires: 205 verdicts, 205 passes.
6. Outcomes of a discovered option derived from its members, so the relevant
   screen judges seeds and discovered options alike.
7. Lever line redrawn so commissioning and grant-funding are not "provide a
   service"; ambition judged against the baseline's status quo; the
   runner-up lever shown on the card when typing names one; typing and
   constrain batches run in parallel; the typing wire loses its prose fields.
8. Themes stay as they are (excellent in all seven runs) but are built after
   constrain, so an excluded option never sits inside a theme made for it.
9. The baseline is passed to discovery, typing and constrain. A recorded
   principle for task 3: shortlist and assessment judge against the
   baseline too.

### Constrain

10. Place stripped from the plan JSON the screen receives. **Ruling: D20
    reaffirmed** — the in-scope screen excluded options for being Irish,
    Norwegian, Maltese, Spanish or American in the energy and cohesion runs.
11. Population overlap is not an exclusion: an option for a wider or adjacent
    population goes to the "tried on" bin. Caregiving excluded the flagship
    responsive-caregiving programmes for covering "birth to three years".
12. The relevant screen accepts an outcome on a stated pathway to the plan's
    outcomes. Obesity excluded vouchers, sugar targets and labelling because
    their recorded outcomes said "diets" or "sugar".

### Extraction (the intervention profile)

13. The plan goes in as reference context; every record gets three tags:
    population (on target, adjacent, other), outcome (one of the plan's, or
    other), and object-of-policy (the plan's fixed object, an option, or
    neither). Nothing is dropped; tags only sort. **Ruling: A21 amended.**
    The memo stays per task, which it already is.
14. Setting means where the recipient meets the intervention, null for
    system-level instruments, never a place, a body or the intervention.
    A deterministic pass folds variants into facet labels and moves a
    setting the where-tried matcher recognises as a place into geography
    when geography is empty, logged as a repair.
15. Units are thinned before clustering: `mentioned` records with no
    features and no outcome are dropped; within-document records with the
    same canonical name collapse; a per-document cap. Non-evidence and
    title-only documents are not profiled (caregiving: 154 of 420 records
    came from documents the classifier had marked non-evidence).
16. Negative examples in the profile prompt for the recommended role: a
    target, a concept, a report, a method, a broad aim.

### Search and screen

17. Each option search screens for the option as well as the problem.
    **Ruling: S2 and D21.** Today every option search screens in 13 to 124
    documents of which zero to thirteen are about the option, and
    twenty-eight seeds across six runs ended with no evidence after their
    own search.
18. A screen memo keyed on document and criteria, shared across scopes. Each
    document is screened five to twelve times per run today, three reps
    each, and repeated screens disagree on nineteen to fifty-three percent
    of documents. Screening is forty-five to seventy-seven percent of cost.
19. "Unsure" no longer counts as relevant in option scopes, and a tie no
    longer resolves to relevant.
20. The classify skip list is filled for child walks the way the longlist
    scope already fills it (each document is classified four to six times
    today).
21. A query fallback ladder: when a query returns nothing, drop place and
    institution words and keep the option's kind; the review and trial
    AND-variants stop after the plain form returns nothing. **Ruling:** the
    variants are half the search budget and returned nothing in 64 to 100
    percent of cases.
22. Full-text ingest is deferred until a chat answer needs it (the profile
    reads abstracts; ingest was up to 48 minutes of child time on NEET).
23. The three-bin longlist screen (on target, adjacent, out) with a
    "tried on" facet beside "where tried", never a filter.

### Baseline

24. The Evidence search tools the scoping chain never populates come out of
    the baseline template's tool list (ten error-level calls per baseline).
25. **Ruling:** the rapid baseline's acquisition cap. Baselines cited two to
    fifteen sources and every one took the repair path. If the baseline
    becomes the reference for every judgement, it needs more than two
    documents.

### Small

26. Where-tried gains a table of recurring sub-national places. The
    composed longlist intent loses its double full stop. A typing failure
    leaves the previous typing rather than a blank card.

## Design option: bounded loops inside a workflow

The owner asked whether a more agentic system would fix the above. The
evidence says: not as a replacement for the workflow, yes in three places.

**Why the workflow stays.** Most of the waste is repeated work, not wrong
judgement, and memos and skip lists fix it deterministically. The quality
faults that remain are model inconsistency (the screen disagrees with itself,
themes and constrain disagree), which a free loop would amplify. The
workflow's event log, one trace per run and code-enforced exhaustiveness
are what made these findings readable. The baseline writer is the warning:
it is already an agent with tools and spent ten failed calls per baseline
asking for tools that do not exist.

**Where a bounded loop is right.** Each loop has a budget, a stop condition
and a recorded outcome, so provenance and cost stay predictable.

| loop | today | proposed | stop condition | budget |
|---|---|---|---|---|
| Option search | fixed fan-out: ten searches, fifteen queries each, generic screen | search, screen for the option, count on-option documents, broaden or stop | N on-option documents reached, or the ladder exhausted | queries and screen calls per option; the Evidence search adequacy verdicts reused |
| Discovery | one call over the whole corpus | propose at reader grain, assign, inspect the residual, revise | the residual holds no recognisable kind, or two passes done | two to three passes |
| Allocation across the run | every run searches every seed | after the broad search, decide by corpus size: thin corpus names top-down and skips option searches, rich corpus searches | a documented threshold on documents and units | one decision, recorded in provenance |

The refugee run is the case for the first and third loops: seventeen
documents, twelve searches, no on-option evidence, and twelve seeds that
were already a good longlist. The obesity run is the case for the second:
the class-grain reviews sat in the residual under an instance-grain seed.

**What the contract must decide.** Whether the option search becomes a
loop or keeps its fan-out with an option-specific screen (item 17 alone
recovers most of the value); whether the allocation decision is a rule or a
judgement; and whether the loops' budgets are plan-depth settings the user
can see.

## Evidence

- `docs/tasks/045-scoping-longlist/verification.md` — the three NEET runs.
- The seven live tasks in the dev DB, named "… live run (046 pre-contract …)"
  and "NEET longlist live check (045, rapid, unlinked)".
- Langfuse sessions keyed by task id, one trace per run.
- `docs/tasks/046-longlist-refinement/evidence/pre-contract-runs/` (gitignored)
  — the per-run read-backs, hand folds, the Langfuse cost read, and the
  drive and read-back scripts.
