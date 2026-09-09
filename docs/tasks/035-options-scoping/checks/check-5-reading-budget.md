# Feasibility check 5 — balanced reading within a real budget

Source: `../feasibility-checks.md` § 5. Question: what is the total time and cost to a useful,
qualified result, and what is lost when the per-option document cap tightens?

Method as run (2026-09-08). Three measurements, all on staging data read-only:

1. **Whole-path latency of the Evidence search as built**, from staging's `component.timing`,
   run and steering events for every completed walk (43 walks: 40 standard, 3 deep). This is the
   spine ⟨baseline⟩ and ⟨longlist depth⟩ reuse, and the terminus ⟨assess⟩ multiplies.
2. **The per-option read set under tightening caps** (3 · 5 · 8 · all) for two shortlisted
   options from the inactivity corpus, using a first scoping select strategy (stratify by
   evidence type and outcome family, reserve one review as the counter-case carrier, fill
   round-robin, record omissions) and the light profile's findings per document, with per-document
   wall time and tokens measured.
3. **Three ways to the countable cells**: light extraction per document; targeted reading alone
   (one call over the cap-5 texts producing the cells directly); compatible finding reuse alone
   (the inherited deep findings, no calls).

Runner: `run_checks_4_5.py timings | budget`. Raw results outside the repository: scratchpad
`staging/out/timings.json`, `staging/out/budget.json`. Cold starts were not run (no acquire on
staging); the corpus supplies poor metadata and failed fetches naturally (65 percent of the
inactivity corpus is abstract-only; several "full text" snapshots are failed parses, check 2 C2-7).

## 1 — Where the time goes today

| walk | n | median whole walk | p90 | median per component (seconds) | share of compute |
|---|---|---|---|---|---|
| standard (spine + characterise + synthesise) | 40 | **888 s** (15 min) | 1756 s (29 min) | acquire 22 · screen 22 · classify 72 · appraise 0 · ingest 154 · screen-full 8 · characterise 11 · select 9 · **synthesise 784** | synthesise **72%** · ingest 14% · classify 7% |
| deep (adds select · extract · group) | 3 | **1457 s** (24 min) | — | acquire 26 · screen 58 · classify 156 · ingest 265 · select 10 · **extract 247** · group 43 · **synthesise 611** | synthesise 42% · ingest 18% · extract 17% · classify 11% |
| gate waits (pause → continuation), 13 observed | | **median 1049 s** (17 min) | 7450 s (2 h) | max 62 h (a task left overnight) | |

Synthesise, not the spine and not extraction, is where the compute time goes: the median
Evidence search report takes 13 minutes to write and about 0.9 million tokens (2.4 million in a
deep walk). The spine
(acquire → screen → classify → appraise → ingest) is about 4.5 minutes for a 150-document corpus.
Extraction is 4 minutes in a deep walk. Humans waiting at gates add more than either.

## 2 — The read set under tightening caps

Two options from the inactivity corpus; candidates are the documents whose abstract profile
*evaluates* the option plus the read-set documents check 2 used.

**T3 whole-system, place-based approach** (10 candidates, 3 with real full text)

| cap | documents read (full text) | with effect findings | distinct claims | documents with a non-increase finding in any outcome (see note) | extraction wall time, parallel / sequential | tokens |
|---|---|---|---|---|---|---|
| 3 | 3 (2) | 1 | 3 | 1 | 1.6 s / 2.9 s | 16 k |
| 5 | 5 (2) | 3 | 5 | 1 | 1.8 s / 4.7 s | 19 k |
| 8 | 8 (3) | 6 | 18 | 3 | 20 s / 29 s | 93 k |
| all 10 | 10 (3) | 8 | 22 | 4 | 20 s / 38 s | 102 k |

**T4 community-wide multi-strategy programme** (12 candidates, 4 with real full text)

| cap | documents read (full text) | with effect findings | distinct claims | non-increase finding in any outcome (see note) | extraction wall time, parallel / sequential | tokens |
|---|---|---|---|---|---|---|
| 3 | 3 (1) | 3 | 3 | 2 | 2.8 s / 7.5 s | 10 k |
| 5 | 5 (3) | 5 | 20 | 3 | 16 s / 29 s | 45 k |
| 8 | 8 (4) | 7 | 30 | 5 | 18 s / 54 s | 91 k |
| all 12 | 12 (4) | 11 | 42 | 9 | 18 s / 68 s | 109 k |

What the tallies said at each cap. T4 at cap 3 reads as "no effect on population physical
activity" (the Cochrane review, twice); at cap 12 the physical-activity family reads increase 2 ·
no effect 2 · mixed 2. T3 at cap 3 is three positive claims from one document; at cap 10 it has
four documents with mixed or null results. **The cap changes the texture of the conclusion**,
from a one-sided picture to a balanced one. In T4 a genuine contrary document (the Cochrane
review's null result) survived at every cap because the review reserve carried it. In T3 the
document the runner flagged at caps 3 and 5 (`d745c2c8`) was **not** a counter-case: its only
non-increase finding is a *decrease in sedentary time*, a desirable result. *(Correction after the
pass-4 review, 2026-09-08: the runner flagged any decrease, mixed or no-effect finding as
"contrary" without checking the outcome's desirable direction; the column is renamed above and
the runner now reports non-increase findings without calling them contrary. T3 has no
identified contrary document at any cap.)*

Selection lesson: at cap 3 for T3 two of the three chosen documents had **no effect findings at
all**, because the strategy preferred full text and full text here meant a process evaluation
and a mid-term programme review. The abstract profile already knows which documents *evaluate*
the option and for which outcomes; the strategy must stratify on that, with text length as a
tiebreaker.

Per-document extraction time: abstract-only documents 3.5 s median; full texts 1.6 s to 30 s
(the 368 000-character trial report took 8 windows and 30 s; 235 000-character Inactive Nation, 5
windows, 20 s). In a parallel fan-out the option's extraction latency is the slowest document,
about 20 s, at any cap above 5. Caveat: 15 of the 36 profiled documents carry no wall time
(they were profiled before timing was recorded), so the cap tables' sequential and parallel
columns undercount, and "parallel" is the slowest recorded document, not a timed fan-out.

## 3 — Three ways to the cells (cap 5)

| approach | T3 | T4 | time | what it misses |
|---|---|---|---|---|
| light extraction per document | 5 claims, 1 contrary document | 20 claims, 3 contrary | 2 to 16 s parallel; 19 to 45 k tokens | nothing the read set holds; 17% of anchors fail the quote check (check 2) |
| targeted reading alone (one call over the five texts, cells written directly) | 3 positive families and the sedentary-time decrease; no contrary evidence reported, and none was present (see the correction above) | 3 families, counter-evidence present | 3 to 4 s; one call | no per-claim anchors or claim keys, so nothing to verify or dedup; read only the first 60 000 characters of each text |
| compatible finding reuse alone (inherited deep findings, no reading) | 74 records over 3 documents, 17 with a magnitude | 15 records over 4 documents, **0 with a magnitude** | 0 s | the magnitude cell; any document not in the deep run's selection |

## 4 — What a scoping run would cost, from these numbers

Projection from measured medians; the profile synthesis is assumed to cost what an Evidence
search report section set costs today, scaled to the profile's eight sections.

| stage | rapid (sense-check, 1 option) | standard (explore, 5 assessed) | what it is |
|---|---|---|---|
| spine at longlist depth (150 to 350 documents) | 4 to 8 min | 4 to 8 min | measured, shared across options |
| baseline synthesise | ~10 min | ~10 min | one report-sized synthesis |
| gate 1 (confirm plan against baseline) | human | human | median 17 min today |
| abstract profile over every document | 1 to 2 min | 1 to 2 min | measured: 351 documents in 106 s at 8-way fan-out |
| longlist, constrain, shortlist | ~1 min | ~1 min | measured clustering 36 s; typing and themes 3 calls |
| gate 2 ("Assess these N") | human | human | |
| per option: select + light extraction | 20 s | 20 s each, parallel across options | measured |
| per option: synthesise(profile) | **~8 to 13 min** | **5 × 8 to 13 min** if serial | the lever |
| report synthesise | 0 (the profile is the report front) | ~10 min | |

A rapid sense-check is bounded by two syntheses (baseline and profile), about 20 to 25 minutes
of compute plus one gate. A standard run with five assessed options is bounded by seven
syntheses, 70 to 90 minutes of compute if profiles are written serially, plus two gates. Neither
is bounded by extraction.

## Answer to the question

- *A smaller cap changes the conclusion or drops the counter-case* → **yes, in texture**: cap 3
  gave one-sided pictures for both options; in T4 the genuine counter-case survived because a
  review was reserved; T3 had no identified counter-case to lose. Design consequence: the read-set strategy stratifies on the abstract profile's
  *evaluated* role and outcome families, reserves one review and one primary study, and the
  promised result states "N of M documents read" with the omissions listed (ruling 38 stands and
  is necessary).
- *The spine dominates latency, so shrinking extraction does not solve rapid* → **the spine does
  not dominate; synthesis does**. Extraction is 17 percent of a deep walk and 20 seconds per
  option in parallel. The rapid budget is a synthesis budget: section count, turn caps and the
  reading scope of `synthesise(profile)`.
- *Performance works only on inherited evidence* → **no**. The abstract profile and the light
  extraction are fast on a cold corpus; inherited findings alone cannot fill the magnitude cell
  (17 of 74 and 0 of 15 had one). Reuse saves calls, not the result.

## Findings, ranked by whether they change the design

**Changes the design.**

- **C5-1 — The rapid budget is a synthesis budget.** Set the rapid latency number (open question
  3) against two syntheses plus one gate, and make `synthesise(profile)` the component with a
  declared section budget and reading scope (check 6 F4). Extraction caps are a cost lever, not a
  latency lever. Affects task 3 and the plan contract's depth settings.
- **C5-2 — Stratify the read set on evaluation, not on text availability.** Full-text-first
  picked process evaluations with no effects. The select strategy uses the abstract profile's
  role and outcome families as strata, reserves one review and one primary study, and records
  omissions by stratum. Affects task 3 (`select`, scoping strategy) and the Sources tab's "not
  read under the cap".
- **C5-3 — Countable cells come from per-document extraction, not from reading alone.** The
  test did **not** show reading alone missing contrary evidence (the flagged document was not
  contrary). The reason to prefer extraction is verifiability: it yields per-claim anchors and
  claim keys that the vetter and dedup can check; a single reading call yields neither, and read
  only the first 60 000 characters of each text. Narrative sections may read; the direction tally
  and magnitudes are extracted and anchored. *(Weakened after the pass-4 review.)*

**Clarifies the design.**

- **C5-4 — Cap 5 to 8 is the working range here.** Below 5 the picture was one-sided; above 8
  the claims kept growing but the contrary set was already present. A per-option cap should be a
  plan setting with 5 (rapid) and 8 (standard) as defaults, re-tested in the eval slice.
- **C5-5 — Gate waits are the largest single term.** Median 17 minutes, p90 two hours. The two
  scoping gates are structural (rulings 2, 3); the design already makes the first pause
  productive (question the baseline). Time-to-result claims must be stated as compute time and
  separately as elapsed time.
- **C5-6 — Extraction fan-out latency is the slowest document.** 30 seconds for a 368 000-
  character report. A window cap per document (or reading the abstract plus the results section
  first) bounds it; a cost and quality trade for the eval slice.

**Not tested.** Cold-start acquisition (no acquire runs were made); the profile synthesis itself
(no `synthesise(profile)` exists to time, so its row above is a projection from the Evidence
search's synthesise); the rapid one-option check end to end.

## What this means for the contracts

- **Task 3 (assessment).** The scoping `select` strategy as C5-2; per-option cap as a plan setting
  with defaults 5 and 8 (C5-4); the light profile with vetter and dedup for the cells (C5-3);
  `synthesise(profile)` with a declared section budget and reading scope (C5-1).
- **Task 1 (shell and baseline).** The baseline synthesis is one of the two syntheses in the
  rapid budget; its template should be sized to that (C5-1). Time-to-result copy separates
  compute from elapsed time (C5-5).
- **Open question 3.** The rapid number can now be set from measurements: about 25 minutes of
  compute for a one-option sense-check on today's synthesise, before any synthesis tuning.

## After review (2026-09-08 and 2026-09-09)

Two independent Codex reviews (passes 4 and 5) checked this report against the raw results and found factual errors, corrected in place above and marked *Correction*. The reviews asked for extra runs; the owner ruled that no owner or analyst time was available, so every extra run is **agent-only**, and where the method asked for a human judge an independent model pass (`gpt-5.5`, a different and stronger model than the one that produced the outputs) stands in, labelled **model judge** wherever it appears. It is not human judgement. The runners are in `scripts/feasibility_checks/options_scoping/`; raw results stay outside the repository.

### 4 — Run 6: contrary evidence, judged properly

Contrary = a finding **assigned to the design** whose direction opposes the outcome's desirable
direction (model-mapped per outcome family), or a null or mixed result. Selection strata now use
the documents whose *evaluated mention was assigned to this design* (membership), with one review
and one primary study reserved.

| option | verified findings | eligible for the design | contrary | cap 3 kept / lost | cap 5 | cap 8 | all |
|---|---|---|---|---|---|---|---|
| T3 whole-system | 49 | 6 | **1** (a null result on physical activity in the nationwide place-based trial, `b7166ee9`) | 0 / 1 | 1 / 0 | 1 / 0 | 1 / 0 |
| T4 community-wide | 59 | 16 | **14** (the Cochrane null result across five snapshots; a second review's mixed results) | 4 / 10 | 7 / 7 | 11 / 3 | 14 / 0 |

Only 6 of T3's 49 verified findings belong to the design: most of what the read set carries is
about other things. The cap-3 read set held zero eligible findings for T3. Five of T4's fourteen
contrary findings are one review counted five times, so the dedup of A8 changes this table too.

**Equal text, cap 5** (the first 60 000 characters of each document to both approaches): for T3
extraction produced 4 attributable contrary findings; the single reading call's cells reported
**one null result** in three documents for physical activity (and, for T4, two null and one
mixed for physical activity, one null and one mixed for social participation). *Correction after
the pass-5 review: an earlier version of this section said the reading call showed no contrary
family; the runner's outcome-label matching failed (the reading's family names did not match the
desired-direction map, spaces against underscores), so `contrary_families` came out empty while
the tallies plainly carried the null results.* Reading alone did report the contrary evidence at
cap 5. What it did not produce is a per-claim anchor or claim key; the case for extraction is
verifiability, not detection, and this run does not show a detection difference either way.

### 7 — Run 7 (approximation): one fresh rapid path, timed

One complete rapid Evidence search on the NEET question, fresh acquisition, through the runtime
agent CLI with a scripted console (two console turns: the ask, then "approve"), unattended
steering, and the synthesis shaped at plan time into eight profile-like sections (mechanism and
failure modes; what the interventions are made of; evidence for and against; variation in
practice; case studies; what it would take; what was searched). It is an approximation:
the Evidence search's synthesise stands in for `synthesise(profile)`, and there was no
inherited-material twin to compare against (nothing to inherit exists yet).

| stage | wall time | tokens | note |
|---|---|---|---|
| planning conversation to approval | 26 s | | one planner turn |
| acquire | 28 s | | 100 documents; **78 already in the shared substrate** from other tasks |
| screen | 27 s | 0.40 M | 59 screened in of 100 |
| classify | 87 s | 0.17 M | |
| appraise | 0.2 s | | deterministic |
| ingest full text | 107 s | | 32 ingested; 25 fetches failed (20 blocked by host, 3 paywall) |
| characterise | 10 s | 0.05 M | |
| **synthesise** | **380 s** | **1.13 M** | 8 sections, 9 blocks |
| whole path, end to end | **676 s** (11.3 min) | | no gate waits (unattended) |

Synthesise was **59 percent** of the walk; the spine (acquire through ingest) about four
minutes; the planning turn under half a minute. On a cold corpus the whole rapid path ran in
under twelve minutes of compute, with a profile-shaped synthesis at Evidence search size. Two
things this does not measure: a scoping baseline synthesis and a scoping profile synthesis of
their own sizes, and the human wait at the two structural gates (median 17 minutes on staging).
For the E16 row it means the "about 25 minutes of compute" projection is of the right order for
two syntheses of this size, and remains a projection.

### Pinned fan-out timing (from the pinning run)

All of an option's documents extracted at once: T3, 10 documents, **24.6 s** wall (sum of document times 76.7 s); T4, 12 documents, **16.0 s** (sum 65.2 s). Every document in the pinned run carries a wall time; the earlier tables' "parallel" column, which took the slowest recorded document, was within a second of these where times existed.

