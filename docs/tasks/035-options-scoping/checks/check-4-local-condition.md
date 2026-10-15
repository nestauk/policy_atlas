# Feasibility check 4 — local-condition adjudication

Source: `../feasibility-checks.md` § 4. Question: can the weakest-leg verdict distinguish an
applicable universal fact, an aggregate geography fact, a present user report and a commitment?

Method as run (2026-09-08): a transferability-working prompt was drafted (`draft_transferability.py`,
`os_transfer_v0.1`, lead-authored) for the column-grounded block declared in
`provenance-grounding.md`, in two stages: **stage 1** extracts the factor list once from the
evidence (the two evidence legs plus the support factors, moderators and dealbreakers, each with
ids and a verbatim quote); **stage 2** fills the *Your context* and *Basis* columns for that fixed
list from a closed set of typed context entries. **Code derives the verdict** (weakest leg) and
**enforces the context rules** (`enforce_rows`), recording every correction it makes to the
model's statuses. Evidence: the Walk with Me peer-led walking trial from the staging inactivity
corpus, 8 light-profile effect findings plus 59 implementation-context findings (barriers,
enablers, fidelity, adaptations). Target: inactive adults aged 60 to 70 in Bradford district.
Context entries are **constructed test fixtures, not facts about Bradford**; each pair varies one
thing. Runner: `run_checks_4_5.py transfer`. Raw results outside the repository: scratchpad
`staging/out/transfer.json`.

A first single-stage draft (`os_transfer_v0`) failed in two ways that the two-stage form fixes:
it made the two evidence legs depend on context entries, so every verdict was Unknown; and its
factor set drifted between identical runs (8 rows, then 3). Recorded as C4-1.

## The factor list stage 1 produced (run 1 of 2; run 2 shared only 4 of its 12 factors)

| leg | factor | evidence status | dealbreaker |
|---|---|---|---|
| worked somewhere | MVPA increased at 6 months | met | |
| same causal role | inactive adults aged 60 to 70 in socioeconomically disadvantaged areas | **not met** (target does not state disadvantage) | |
| same causal role | trained volunteer peer mentors of similar age | unknown | |
| support | safe and accessible walking places | unknown | no |
| support | rapport and trusting relationship with peer mentor | unknown | no |
| support | shared-interests matching between peer and participant | unknown | no |
| support | good weather | unknown | no |
| support | convenient meeting time | unknown | no |
| support | paperwork burden | unknown | no |
| support | peer mentor training and support materials | unknown | no |
| support | fidelity of delivery over the full 12 weeks | unknown | no |
| support | easy-to-implement peer mentor role | unknown | no |

Three things to notice before the pairs. **The factor list is not stable across extraction
runs**: the second stage-1 run produced twelve rows of which four matched the first, and the
peer-mentor causal-role status differed (unknown, then met). The list used below is run 1, held
fixed by choice so the pairs compare like with like; that fixity is a design requirement (pin the
list to an evidence, design and target version), not an observed property. *(Correction after
the pass-4 review, 2026-09-08: an earlier version of this report said the list was identical
across two runs.)* The extractor flagged **no dealbreaker**, although the
evidence records a governance block (mentors could not be hosted under the existing walking
scheme; insurance had to be arranged through the university). And the causal-role leg was judged
*not met* because the trial population was in disadvantaged areas and the target did not say so;
the honest status is *unknown*. Both cap every verdict below, so the verdict word never moved in
this run; the rows did.

## The pairs

| pair | entry A | entry B | rows that changed A → B | right reason? |
|---|---|---|---|---|
| P1 national average vs local resource | "63.7% of adults in England are active" (national, 2024) | "Bradford runs 14 volunteer-led walking groups with trained walk leaders" (local, 2025) | none; A unused; B read against three mentor factors and left **unknown** ("walk leaders are not shown to be peer mentors of similar age") | yes: the aggregate filled nothing; the local resource was read but not over-read |
| P2 rule with and without exception | Care Act 2014 duty on every local authority (national rule) | the same rule plus "Bradford's 2025/26 prevention budget excludes community physical activity programmes" | none; the rule matched **no factor** in the evidence-derived list, so neither the rule nor its exception had a row to fill | partly: the machinery was right not to invent a factor; but a user cannot bring a condition the evidence did not name (C4-3) |
| P3 planned funding vs present capacity | "committed to fund 20 peer mentors from April 2027" (planned) | "currently funds 20 trained peer mentors" (stated) | three mentor factors: **conditional → met** | yes, exactly as ruled: a commitment is a condition, a present fact can lift it |
| P4 old vs current observation | 2009 audit: 38 leisure centres, 120 km of paths (local, dated) | 2025 audit: 24 centres, 150 km (local, current) | walking places: **unknown (dated) → met** | yes; the 2009 entry was read, marked dated, and left the factor unknown |
| P5 containing aggregate vs local aggregate | "62% of people in England live within 15 minutes of a park" (national) | "71% of Bradford residents live within 15 minutes of a park" (local) | walking places: **unknown (aggregate only) → met** | yes for A (ruling 34 exactly); B is arguable (proximity to a park is not a safe walking route) |
| P6 assurance | "the leisure trust has assured the council that routes will be available and mentors insured" (planned) | — | the model set **one** factor met on the assurance; the code corrected it to conditional, and restored two evidence-leg statuses the fill had changed without a context entry | the guard is load-bearing: the model did strengthen on an assurance, once |
| P7 rich present context | four entries: local groups, present mentor funding, current paths, present insurance | — | three factors met; six of nine support factors still unknown; the insurance entry matched no factor | shows the ceiling: with good context the support leg stays unknown because most helpful factors are never stated |

Corrections the code made across all 14 cases: 5 — one dated observation set met (P4a); one
planned entry set met (P6); and three evidence-leg statuses the fill had changed to unknown
without a context entry, restored to the stage-1 status (P5b, P6). One of those restorations put
back the **wrong** causal-role "not met": the guard preserves a bad evidence judgement as readily
as a good one. Determinism at stage 2: the baseline case run twice against the fixed list gave
identical rows and statuses. *(Correction after the pass-4 review: an earlier version counted
five over-statements and three assurance corrections.)*

## Answer to the question

The machinery **can** distinguish the four kinds. An aggregate at a containing geography was kept
as context and filled nothing (P1a, P5a). A present user report lifted a factor to met (P3b). A
commitment made the factor conditional and never met (P3a; P6 after correction). A dated
observation was read and left the factor unknown (P4a). A rule that applies by nature was
recognised as such (first draft, P2a) but in this evidence set had no factor to fill.

The check's "changes the design if" clauses:

- *Verdicts strengthen on containment or assurances alone* → **the model did, once, and the
  code caught it**. Keep conditions visible and the verdict conditional, as ruled; the design
  consequence is that the code-side enforcement is part of the block, not a test harness — and
  that it can only enforce entry types, not repair a wrong evidence judgement.
- *Even corrected conditions cannot be judged reliably* → **did not fire**. Corrected conditions
  were judged correctly in every pair; ruling 29's rejection of an argument-only cell stands.

But the **verdict word carried no information in this run**: every case read "Does not transfer
as designed", capped by the causal-role leg. That is a finding about the derivation rule and the
causal-role judgement, not about the context discipline.

## Findings, ranked by whether they change the design

**Changes the design.**

- **C4-1 — The working is two components, not one prompt.** Factor extraction from evidence
  (once per option, **pinned** to an evidence, design and target version — a repeat run shared
  only 4 of 12 factors) and context filling against that fixed list (per context set) must be
  separate steps; a single prompt drifted its factor set and tangled the evidence legs with
  context. Proposal: `synthesise(profile)` runs moderator/dealbreaker extraction as
  its own grounded step producing the factor rows, then the context fill; the column-grounded
  block declaration in provenance-grounding.md names the two steps. Affects task 3.
- **C4-2 — Only dealbreakers cap; helpful factors are shown, not summed.** trust.md already says
  "an unknown or absent dealbreaker caps the verdict on its own"; it also says "the weakest of
  the three legs". With nine helpful support factors, the weakest-leg rule over all rows makes
  the support leg Unknown for every option unless the user states every factor, so the word
  never differentiates options. Proposal: the support leg's status is the weakest **dealbreaker**
  row; helpful factors are listed with their statuses and enter the conditions list when planned,
  but do not cap. When the evidence names no dealbreaker, the leg reads "no necessary condition
  identified" and stays Unknown. Owner ruling needed; this sharpens trust.md rather than
  reversing it.
- **C4-3 — Dealbreaker detection under-fires, and users cannot bring a condition.** The extractor
  flagged none of twelve factors as necessary despite a governance block in the evidence; and a
  statutory duty the user supplies had no row to land on. Proposal: the factor extractor asks
  explicitly "what did the evidence report as blocking delivery" (fidelity, adaptation and
  barrier claims of the ICF profile are the source); and the plan's user-context entries may
  **add** a factor row typed *stated by you* whose *Evidence says* cell is honestly "not
  addressed by the evidence". Affects task 3.
- **C4-4 — The causal-role leg must default to Unknown on unstated features.** The evidence
  population was in disadvantaged areas; the target did not say. The model judged "clearly
  differs" and capped every verdict. Proposal: *not met* on this leg requires a stated
  contradiction between evidence and target; otherwise Unknown with the difference named.
  Affects the prompt and the verify rule (task 3).

**Clarifies the design.**

- **C4-5 — Code-side enforcement is part of the block.** Two over-statements (a dated
  observation and an assurance set met) and three evidence-leg changes were corrected
  deterministically from the entry types and the model's own labels; the same rule restored a
  wrong causal-role status, so enforcement bounds context use but cannot repair the evidence
  judgement it protects. The verify step for the column-grounded block should run exactly these rules
  (planned → never met; aggregate at containing geography → never met/not met; dated → unknown;
  entry id must exist) and record corrections as flags.
- **C4-6 — Currency needs a rule or a field.** The model judged a 2009 audit dated and a 2014
  statute current, which is right, but nothing bounds that judgement. Proposal: retrieved entries
  carry an observation date; the fill records `currency` with a reason; the eval slice
  calibrates the age threshold per factor kind (infrastructure counts age fast; statutes do not).
- **C4-7 — Local aggregates.** A local percentage (71 percent live near a park) was read as
  meeting "safe and accessible walking places". Ruling 34 speaks to containing geographies;
  local aggregates are local facts but still aggregates. Owner to say whether a local aggregate
  can set met, or only a local resource observation can.

**Not tested.** One option and one evidence set; a second option with a genuine dealbreaker in its
evidence (JU:MP's governance dependencies, or the free-access trial's outreach component) would
test C4-3 directly. The owner judges the reasons in the table above.

## What this means for the contracts

- **Task 3 (assessment).** The transferability working is two steps (C4-1) with code-side verify
  (C4-5); the verdict derivation caps on dealbreakers and the two evidence legs (C4-2, pending
  ruling); the causal-role leg defaults to Unknown (C4-4); the factor extractor asks for blockers
  and the plan's context entries can add a row (C4-3); retrieved entries carry a date (C4-6).
- **Spec.** trust.md § Transferability: make explicit that helpful factors do not cap (C4-2) and
  how a local aggregate is treated (C4-7). provenance-grounding.md § Column-grounded blocks: the
  two steps and the verify rules.

## After review (2026-09-08 and 2026-09-09)

Two independent Codex reviews (passes 4 and 5) checked this report against the raw results and found factual errors, corrected in place above and marked *Correction*. The reviews asked for extra runs; the owner ruled that no owner or analyst time was available, so every extra run is **agent-only**, and where the method asked for a human judge an independent model pass (`gpt-5.5`, a different and stronger model than the one that produced the outputs) stands in, labelled **model judge** wherever it appears. It is not human judgement. The runners are in `scripts/feasibility_checks/options_scoping/`; raw results stay outside the repository.

### 5 — Run 4: a second option with a real blocker, model-judged

Option: the whole-system, place-based approach. Evidence: 25 effect findings assigned to it plus
**134 implementation-context claims extracted for the check** from four documents (labelled
ICF-lite; 45 of them blockers, 14 barriers, 28 conditions). Target: children aged 5 to 15 in a
deprived northern district.

**Factor extraction drift, three runs:** 12, 13 and 13 rows; **one factor label shared by all
three** (an exact lower-cased match, so a lower bound on shared meaning); dealbreakers flagged in
one run of three (three factors), none in the other two — with 45 blocker claims in the evidence
(themselves model labels, not quote-vetted). This is worse than the first option showed. A factor list cannot
be re-derived per run; it has to be produced once, pinned to an evidence and design version, and
probably built by clustering the context claims rather than by free extraction.

**Fixtures drafted against the real factor list** (varying one thing each), status on the target
factor:

| case | expected | got | note |
|---|---|---|---|
| blocker present (stated) | met | met | |
| blocker absent (stated) | not met | not met | all-rows verdict "does not transfer"; dealbreakers-only stays Unknown because no dealbreaker was flagged in the run used |
| blocker planned | conditional | conditional | the fill set it conditional itself; the one code correction in this case restored an evidence-leg status, not a planned→met error *(corrected after pass 5)* |
| blocker unstated (entry about a different factor) | unknown | **met** | over-read: an attendance spreadsheet set "place-based coordination" met; the model judge said unknown |
| rule applies by nature | met | met | |
| rule with a local exception | not met | **met** | **not a demonstrated failure**: the drafted exception excluded districts that had already received a comparable grant, and no entry said this target had, so the target was never inside the exception; the model judge agreed with met *(corrected after pass 5: the fixture, not the fill, was at fault)* |

**Chat promotion** (plain messages to typed entries): all six typed as a person would — a budget
bid and a funder's assurance became *planned*, a 2022 audit *retrieved*, a present partnership
board and present officers *stated*, an opinion dropped. The C3 mechanism works at this scale.

**Model judge** on 20 filled rows: agreed with 16; the four disagreements are the two over-reads
above and two rows where the promoted partnership board was read as establishing deliverers and
senior buy-in. In this run the code guard's two corrections both restored evidence-leg statuses;
no planned→met error occurred to catch. The guard cannot catch over-reading. Whether an exception
can defeat a rule remains **untested** across both options (the first option's rule matched no
factor; this option's fixture never placed the target inside the exception). A rerun needs a
fixture that does, and a judge that derives its answer before seeing the system's.

