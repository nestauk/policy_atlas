# Extra runs after the pass-4 review — agent-only

Source: `pass4-answer.md` § 3 (local review folder) named seven small runs that would let the
decision-sheet rows rest on measurements. The owner ruled (2026-09-08) that no owner or analyst
time is available, so every run below is agent-only. Where the method asked for a human judge,
an independent model pass stands in — a different, stronger model (`gpt-5.5`) than the one that
produced the outputs — and every such number is labelled **model judge**. It is not human
judgement. Runners: `extra_runs.py`, `extra_transfer.py`, `run7_neet.py`. Raw results stay
outside the repository (staging document text); the results folder's `README.md` lists them.

What was not done: the expert halves of runs 1 and 2 (meaningfulness of options, expected
choices), and the analyst's own reading of the check-2 verdict table.

## 0 — Pinning and the runner defects

The review found the results bundle held a later light run than the check-2 report described, and
three runner defects. All are fixed and the bundle is pinned.

- **light_v2** is one complete run over all 36 read-set documents: 173 findings; anchors 125
  exact · 60 normalised · **38 failed (20 percent)**; every document carries a wall time. The
  check-2 trace was recomputed on it (**trace2_v2**). Both are the reference for everything below.
- **True fan-out timing** (all of an option's documents extracted at once): T3, 10 documents,
  **24.6 s** wall (sum of document times 76.7 s); T4, 12 documents, **16.0 s** (sum 65.2 s). The
  earlier "parallel" column, which took the slowest recorded document, was within a second of
  these where times existed.
- Seat replacements are now counted as seats whose seated option changed, not as a symmetric
  difference. "Contrary" is now judged against the outcome's desirable direction and only over
  findings assigned to the design; the earlier flag counted any decrease.

Recomputed check-2 table on the pinned run (compare the report's first-run table):

| target | mentions any / evaluated | support documents | findings (distinct) | independent own-data studies | reviews | inherited |
|---|---|---|---|---|---|---|
| T3 whole-system | 39 / 7 | 6 | 34 (25) | 2 | 1 | 10 |
| T4 community-wide | 24 / 12 | 8 | 21 (19) | 2 | 6 (five are copies of one Cochrane review) | 5 |
| T1 free access with outreach | 3 / 3 | 2 | 4 | 1 | 1 | 6 |
| T2 peer-led walking | 1 / 1 | 1 | 15 (12) | 1 | 0 | 2 |
| T1v, T2v, Y variants | — | 0 | 0 | 0 | 0 | 0 |
| A–D active labour market | 6–13 / 1–5 | 2–3 | 3–7 | 0 | 2–3 | 0 |

The shape of the check-2 findings is unchanged: role separates mention from support; variants
receive nothing from their parents; review-mediated support resolves to no independent study.
Two counts moved enough to matter for the rows: T4's reviews went from 1 to 6 because the
pinned run read all five snapshots of the Cochrane review (A8), and one independence key is a
document id because a paper carried no programme name or registration (A3: identity is a clue,
not proof — as the review said).

## 1 — Run 5: independence cases, model-judged

Real cases from the corpus, resolved by the light profile's `study_identity`:

| case | documents | system resolution | model judge |
|---|---|---|---|
| one Cochrane review as five snapshots | `04940b89` `262fd5bf` `2de6988a` `792b2e60` `fa83c920` | none reports own data, so 0 studies (right); but the name-first key splits them into **three keys** ("community wide" / "community-wide" / none) | **wrong** as a document count: they must be one review record; identity needs normalisation (hyphen, case) and DOI |
| one trial in four papers (JU:MP) | `a3a7243b` `d65ae6e0` `d745c2c8` `de29337d` | one key, 1 study | right |
| protocols | `595fdaf1` `379f0041` | 0 findings, 0 studies | right |
| alias: name vs registration | `9973f940` | one key (Walk with Me = ISRCTN23051918) | right |
| two distinct studies sharing a programme name | — | not constructible from this corpus | untested |
| an older-profile record (simulated: no setting, geography, basis, comparator) | Walk with Me IOF record | satisfies intervention, outcome, direction, population, design, estimate level | **partial reuse only**: lacks magnitude, comparator, period, setting, geography, identity; cannot be reused without mixing comparators or periods |

Model-judged verdict table (V1–V10), judged from document excerpts and the pinned trace: right
V2, V5, V7; wrong V1, V6, V8 — each because the statement's counts came from the first light run
and the pinned run differs (support documents, review copies); cannot tell V3, V4, V9, V10 — the
excerpts did not carry the cited result. This is a judge on the *statements as written*, not on
the design; the statements should be regenerated from trace2_v2 before any human checks them.

## 2 — Run 3: no-document suggestions and a set-aside

Injected into the unemployment corpus with an "OECD evidence only" evidence-scope constraint
(five documents set aside by study geography): a user suggestion (youth guarantee **without**
benefit sanctions, *variant of* the guarantee with obligation), a ministerial suggestion (free
bus travel for jobseekers), a taxonomy-prompted suggestion (guaranteed-hours rights, lever type
*regulate*), and a modified design (wage subsidies restricted to long-term-unemployed under-25s
for twelve months). Discovery at the C3-3 ceiling (`clamp(ceil(N/4), 8, 40)` → 25) found 20
options (residual 33 of 97 units).

| check | result |
|---|---|
| every no-document entrant survives as its own option with its origin label | **yes**, all four; each became an option with zero documents (an honest empty coverage state) |
| the variant is not excluded by the *distinct* screen and keeps its relation | yes; "Youth guarantee without benefit sanctions" is its own option, variant of the guarantee with obligation |
| a user-added place is kept through the proposal | yes; the proposal seated the variant as *added by you* under its lever type |
| scope-shaped constraints judge the specified design | yes: "guaranteed-hours rights" was **excluded** as needing primary legislation (correct for a local-authority constraint); benefit reform and area tax credits likewise; nine options came back **uncheckable** |
| an option whose only source is set aside is kept marked "no in-scope evidence" | **not exercised**: every option with set-aside members also had in-scope members ("skills training": 8 in scope, 5 set aside) |
| reason text when coverage is empty | a defect: "widest implementation record (0 countries recorded across 1 documents)" — the reason axis needs a floor |

## 3 — Run 2 (machinery half): grain on equal inputs

The same 22 documents (the T3 and T4 candidates), three unit sources, one clustering procedure,
grain judged by a model, paraphrase stability measured on each set:

| unit source | units | options | residual | grain (model-judged) | mentions moved under paraphrase |
|---|---|---|---|---|---|
| abstract mentions | 55 | 14 | 23 | **8 class** · 4 specified design · 2 not an option | 2 of 55 |
| inherited deep findings | 89 | 14 | 8 | **10 specified design** · 4 class | 0 of 89 |
| reading two reviews | 6 | 6 | 0 | 5 specified design · 1 class | 0 of 6 |

Cross-fit: 84 of 89 finding units and 6 of 6 review units fit into the mention-path options. The
review's confound (295 versus 17 documents) is removed: **the grain difference is a property of
the unit type**, not of document coverage. Findings-grain options are also the stable ones.
Unchanged: whether either set is *meaningful* to an expert.

## 4 — Run 6: contrary evidence, judged properly

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
extraction produced 4 attributable contrary findings; the single reading call's cells showed **no**
contrary family yet set its counter-evidence flag to true. For T4: extraction 3, reading again
flag true with no family behind it. The reading call knows something is there and cannot say
what; extraction says what and where. That is the honest form of the check-5 claim the review
struck out.

## 5 — Run 4: a second option with a real blocker, model-judged

Option: the whole-system, place-based approach. Evidence: 25 effect findings assigned to it plus
**134 implementation-context claims extracted for the check** from four documents (labelled
ICF-lite; 45 of them blockers, 14 barriers, 28 conditions). Target: children aged 5 to 15 in a
deprived northern district.

**Factor extraction drift, three runs:** 12, 13 and 13 rows; **one factor shared by all three**;
dealbreakers flagged in one run of three (three factors), none in the other two — with 45
blocker claims in the evidence. This is worse than the first option showed. A factor list cannot
be re-derived per run; it has to be produced once, pinned to an evidence and design version, and
probably built by clustering the context claims rather than by free extraction.

**Fixtures drafted against the real factor list** (varying one thing each), status on the target
factor:

| case | expected | got | note |
|---|---|---|---|
| blocker present (stated) | met | met | |
| blocker absent (stated) | not met | not met | all-rows verdict "does not transfer"; dealbreakers-only stays Unknown because no dealbreaker was flagged in the run used |
| blocker planned | conditional | conditional | after one correction: the fill set it met on a commitment, the code corrected it |
| blocker unstated (entry about a different factor) | unknown | **met** | over-read: an attendance spreadsheet set "place-based coordination" met; the model judge said unknown |
| rule applies by nature | met | met | |
| rule with a local exception | not met | **met** | the exception did not defeat the rule — the same failure as the first option's P2 pair |

**Chat promotion** (plain messages to typed entries): all six typed as a person would — a budget
bid and a funder's assurance became *planned*, a 2022 audit *retrieved*, a present partnership
board and present officers *stated*, an opinion dropped. The C3 mechanism works at this scale.

**Model judge** on 20 filled rows: agreed with 16; the four disagreements are the two over-reads
above and two rows where the promoted partnership board was read as establishing deliverers and
senior buy-in. The code guard catches type errors (planned set met); it cannot catch over-reading,
and it cannot make an exception defeat a rule. Those need a field, not a prompt sentence: an
entry that carries an explicit `exception_to` reference, and a verify rule that a factor is filled
only from an entry the model itself tagged as bearing on that factor.

## 6 — Run 1 (machinery half): a real NEET corpus

A fresh rapid Evidence search on the NEET question through the agent CLI (run 7 below) produced
a real corpus: 100 documents acquired (78 already in the shared substrate from other tasks), 59
screened in, 32 with full text, 20 fetches blocked by hosts; grey-literature heavy (20 commentary,
12 policy syntheses, 12 observational, 3 reviews, 1 trial). The check-3 machinery on it:

| measure | NEET |
|---|---|
| mentions → options | 126 mentions from 59 documents; 124 units → **20 options** at a ceiling of 21 (binding) |
| residual | 28 of 124 (23 percent); residual kinds as before: actors ("schools", "colleges"), events, out-of-question measures |
| grain | class-grain again ("Youth Guarantee", 4 documents; "Government-led NEET policy") |
| shortlist | 5 places; the "change who runs the system" seat went to a **one-document, unevaluated** option |
| paraphrase | 14 of 124 mentions moved; 0 seats |
| lever relabel | that one weak seat swapped in **3 of 4** runs; every other seat held |

The pattern from the substitute corpora holds on the real question: seats are stable except where
a lever type is represented only by thin, unevaluated options, and there the seat is decided by
noise. The expert half (are these the right options for NEET) is untested.

## 7 — Run 7 (approximation): one fresh rapid path, timed

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

## What changed for the decision-sheet rows

- **Strengthened:** A2 (mentions and role), A6, A7 (the copy rule was not tested; unchanged),
  B2 and E3 (eligibility: only 6 of 49 findings belonged to the design), C3 (chat promotion
  worked), D2 and D4 (the guard catches types; it restored nothing wrong this time), E7 in its
  membership-informed form (selection by design membership, not by "evaluated anything"), E9,
  A9 in its evidence (grain is a property of unit type, on equal inputs).
- **Weakened or reshaped:** D1 (factor extraction is far less stable than the first run
  suggested; pin, do not re-derive; consider clustering the claims), D5 (dealbreaker detection is
  the bottleneck — with none flagged, a dealbreakers-only rule reads Unknown for everything), E8
  (the honest form: reading alone flags without attribution), E5 (seat instability is real but
  confined to thin, unevaluated lever types — the gap-message guard addresses exactly that; the
  contested-place guard is less supported), A8 (needs normalisation and DOI, and it changes the
  contrary counts too).
- **New:** an entry needs an explicit exception reference and a factor-bearing tag (two failures
  of the same kind across two options); the reason axis needs a floor when coverage is empty; the
  set-aside-only path remains untested.
