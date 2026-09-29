# Verification: 046-longlist-refinement

Evidence for the build phase (steps 5 and 6) of task 046. Items, rulings
(R1–R28), amendments (AM, PA), seams (S1–S15) and measures (M1–M9) are
defined in [contract.md](contract.md) and [plan.md](plan.md).

> **Status:** build complete 2026-09-29 · lead. Steps 5 and 6 only. The
> review stack (step 7) has not run; it runs in a fresh conversation.
> Every figure in this file was read back from a saved result file or a
> database query; the file is named beside the figure. The read-backs, the
> traces, the replay tool and the round records are in the gitignored
> `evidence/` folder.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (Phase 0, build-open baseline) | pass | backend 3182 passed; infra 46; frontend 86 files, 805 tests |
| `make verify` (Phase 1, the revision) | pass | backend 3216; infra 46; frontend 805; okf 157 concepts, 0 violations |
| `make verify` (Phase 2, the runner and the chains) | pass | backend 3236; infra 46; frontend 805; audit-paths 137 files, 0 violations |
| `make verify-fast` · `prompt-guard` · `drift-check` (Phase 3) | pass | backend 3240 |
| `make verify-fast` · `prompt-guard` · `drift-check` (Phase 4) | pass on the second run | first run: 2 failed, 3284 passed (see § Red gates); second run: 3287 passed |
| `make verify-fast` · `prompt-guard` · `drift-check` (Phase 5) | pass | backend 3303 |
| `make verify-fast` · `prompt-guard` · `drift-check` (Phase 6) | pass | backend 3312 |
| `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` (Phase 7) | pass | backend 3320; frontend 87 files, 820 tests |
| `make verify` (Phase 8, step-6 exit) | **pass** | backend 3320 passed (879.56 s); typecheck 398 files; lint clean; build; infra 46; okf 157 concepts, 0 violations; audit-paths 137 files, 0 violations; prompt-guard 24 unchanged; font-guard; drift-check OK; frontend 87 files, 821 tests; exit 0 |

`make verify` is okf-validate · backend test, typecheck, lint · infra test ·
audit-paths · prompt-guard · font-guard · drift-check · frontend-verify
(typecheck, lint, vitest, build). The gate map is the plan's: full verify at
Phases 0, 1, 2 and 8.

### Red gates in the build

One. Phase 4, first run: `tests/api/test_longlist_routes.py` lines 520 and
1028 (`'jobcentre' != 'Jobcentres'`, `'employer' != 'Employers'`). Cause: the
new setting fold showed its grouping key as the facet label. Lead ruling: the
fold is a grouping key; the label is the most frequent original spelling. The
two tests were not edited. No commit landed on the red gate.

## Commits on `task/046-longlist-refinement` (local, not pushed)

| Commit | Phase |
|---|---|
| `ecf115b2` | 1 — the revision, the place strip, the tagging-context plumbing |
| `80b28363` | 2 — acquire-only option searches, one plan-level screen, `theme` |
| `74848f6f` | 3 — place strip fixes that the replay found |
| `3b6d3c74` | 4.1 — planning prompt v4 |
| `0b327106` | 4 — profile prompt v2, tag rules, setting pass, coverage |
| `9f77c46e` | 5 — the longlist at reader grain |
| `08ea59d3` | 6 — constrain v2, the distinct call |
| `26e37141` | 6 correction — the code keeps an option of a duplicate pair |
| `a25cbf59` | 7 — read models and views |
| the commit that adds this file | 8 — this file, `docs/deferred.md`, the Tried on facet limit |

## Checks beyond the build

### Deterministic tests (the contract's acceptance bullets)

| Contract bullet | Where | Result |
|---|---|---|
| migration round-trip; null tags read correctly | `tests/core/test_migration_046_tags.py`, `tests/evidence_search/extract/test_interventions_tagging.py` | pass |
| items 1, 4: no unit payload to discovery; digest counts; ceiling; fold; user's option never folded; no `part_of` by `longlist`; one residual pass | `tests/options_scoping/test_longlist.py` | pass |
| item 2: short ids; a mangled short id repaired with no second call | `tests/options_scoping/test_longlist.py` | pass |
| items 5, 8: distinct receives every option; `theme` after `constrain`, included options only; failed `theme` ends the walk `degraded`; stage key; registry, graph, plan mapping | `tests/options_scoping/test_constrain.py`, `test_theme.py`, `tests/runtime/test_compose_by_purpose.py` | pass |
| item 6: a discovered option's outcomes are a subset of the plan's | `test_longlist.py` | pass |
| items 7, 26: typing and constrain batches in parallel; invalid typing keeps the previous values; runner-up served | `test_longlist.py`, `test_constrain.py`, `tests/api/test_longlist_routes.py` | pass |
| item 10: no place token in the constrain plan data; the removal recorded | `test_constrain.py`, `tests/options_scoping/test_longlist_intent.py`, `tests/api/test_longlist_start.py` | pass |
| item 11: silence passes; a kind that cannot be delivered through the setting is excluded | `test_constrain.py` (stub level) | pass |
| items 13, 14: fingerprint changes with the context, not with Where; a place in a setting moves to geography and is logged; folded setting labels | `test_interventions_tagging.py`, `test_interventions_tag_rules.py`, `test_longlist_coverage_046.py` | pass |
| item 15: each thinning rule with its count; title-only gives no profile call; Non-evidence is profiled | `test_longlist.py`, `test_interventions_tagging.py` | pass |
| item 18: a child runs `acquire` only; join before `screen_abstract`; one stage-1 screen row per document; a failed child degrades the walk | `tests/runtime/test_acquire_only_walk.py`, `test_option_search.py` | pass |
| item 18 "with the key set" and item 20 | — | **withdrawn by AM1**; no test |
| item 22: no chain holds `ingest_full_text`; citations labelled *abstract only* | `test_compose_by_purpose.py`, `tests/api/test_answer_core.py`, `ChatMessages.test.tsx` | pass |
| item 23: the screen input on a plan with a setting requirement | `test_longlist_intent.py` | pass |
| frontend: tried on line and facet; variants; runner-up; flag wording | `OptionCard.test.tsx`, `LonglistView.test.tsx`, `longlistPresentation.test.ts` | pass |
| IOF and ICF payloads, prompts and fingerprints byte-identical | existing tests, no edit | pass |

### AI evals

None in this slice (contract). Option quality was read by hand.

### The staged check (R12, R24–R26)

Round records: `evidence/rounds/` (`4.1-planning-r0.md`, `4.2-profile-loop.md`,
`5.2-longlist-loop.md`, `6.2-constrain-loop.md`, `3-baseline-read.md`).

| Loop | Prompt | Rounds | Result on the tuning set | Check set (one read, not tuned on) |
|---|---|---|---|---|
| 4.1 planning | `task_agent_scoping_v4` | 1 | 7 of 7 target units hold no place and no setting | same table |
| 4.2 profile | `extract_interventions_v2` | 2 | M5 passes; outcome tag `other` 54–71% (91–96% in round 0) | M5 passes; heat pumps: 76 records tagged `plan_object` |
| 5.2 suggest, discovery, assignment, typing | `longlist_suggest_v2`, `longlist_cluster_v2`, `lever_typing_v2`, `lever_types_v2` | 4, and 1 model measurement | M1, M2, M3 pass | M1, M2, M3 pass |
| 6.2 constrain, theme | `constrain_v2` (theme prompt unchanged) | 1, and 1 correction | M4 passes; 0 `cannot_check`; 1 exclusion | 0 exclusions |

No loop used more than five rounds. The replay ran on clones. The seven
stored tasks are unchanged: `replay.py check-stored` reports "unchanged: 7
tasks x 19 tables match the reference" after the last replay and after the
live runs.

**The item-2 model measurement.** The assignment ran on the judgment model
for obesity and caregiving (patched in the replay process only). It placed
every class-level review, but it set the not-stated flag on 99 and 100
percent of memberships and left more records unclustered (67 against 33; 122
against 34). Source: `5.2-longlist-r3jm-figures.txt`. The measurement does
not show that the assignment must move. **The assignment stays on the mini
model.**

**The owner's stage decisions (R25) are open.** No owner was present in the
build conversation. Each stage report is in its round record. The owner
decides if each stage is good.

### Live check: three rapid runs on new tasks (stage 2)

Run through the local API on the final code, not attended. Tasks (dev
database): obesity `3f6b79b9`, refugees `42dd142c`, caregiving `ff6ef83c`.
All three longlist walks ended `succeeded`. Sources:
`evidence/rounds/8.1-live-longlist-figures.txt`,
`8.1-live-constrain-figures.txt`, `8.1-live-metrics.txt`, `8.1-cost.txt`,
`8.1-live-m5-m6.txt`, `8.1-precontract-metrics.txt`.

| # | Measure | Obesity | Refugees | Caregiving | Pass |
|---|---|---|---|---|---|
| M1 | Options per run (13 to 25) | 24 | 25 | 25 | **pass** |
| M2 | Rows that are one named trial | none | none | none | **pass** |
| M3 | Class-level reviews are members | see the replay (AM18: M3 is read in stage 1) | — | — | pass in stage 1 |
| M4 | Exclusions with place or population overlap as the reason | 0 (0 exclusions) | 0 (0 exclusions) | 0 (0 exclusions) | **pass** |
| M5 | Setting labels in the top 8 that are a country, region or body | none | none | 1: "EBZ Bruck-Mürzzuschlag location" (6 documents) | **fail on caregiving** |
| M6 | Adjacent evidence shown as tried on | 20 of 20 options with adjacent members | 9 of 9 | 20 of 20 | **pass** |

M5 read-back (caregiving top 8): home 28, hospital 13, online 9, community 7,
EBZ Bruck-Mürzzuschlag location 6, NICU 5, local centers 4, ward 3. The
replay removed this label in round 1 of the profile loop; the live run
brought it back. The cause is run-to-run variation of the mini model, and the
where-tried matcher does not know the place, so the code pass does not move
it. Reported as failed.

Reported, not pass conditions (M7–M9), beside the pre-contract run of the
same question:

| Measure | Obesity before → after | Refugees before → after | Caregiving before → after |
|---|---|---|---|
| M7 cost per run (Langfuse, USD) | 16.18 → 4.32 | 6.26 → 3.29 | 12.07 → 4.24 |
| M7 of which screen | 9.65 → 1.29 | 4.79 → 0.85 | 5.91 → 0.97 |
| M7 stage-1 screen rows in the task | 2629 → 354 | 1409 → 248 | 1575 → 269 |
| M7 screen rows per document, longlist scope | — → 1.00 (334 of 334) | — → 1.00 (234 of 234) | — → 1.00 (249 of 249) |
| M8 longlist walk, seconds | 1926 → 622 | 743 → 531 | 1337 → 569 |
| M8 baseline, seconds | 258 → 227 | 258 → 228 | 549 → 213 |
| M9 pool (documents) | 326 → 334 | 175 → 234 | 229 → 249 |
| M9 relevant in the longlist scope | 100 → 190 | 6 → 102 | 57 → 173 |
| M9 records tagged `other` (population) | — → 158 of 585 (27%) | — → 155 of 304 (51%) | — → 201 of 670 (30%) |
| M9 records tagged `other` (outcome) | — → 312 of 585 (53%) | — → 211 of 304 (69%) | — → 553 of 670 (83%) |
| M9 not-stated flag on memberships | 43–66% (five runs) → 84% | — → 86% | — → 79% |
| M9 `cannot_check` verdicts | 13 → 0 | — → 0 | 16 → 0 |
| M9 documents with no screen row (PA21) | — → 0 | — → 0 | — → 0 |
| M9 duplicate titles (AM16) | 22 → 22 | 12 → 34 | 27 → 24 |
| Options excluded | 13 → 0 | 0 → 0 | 19 → 0 |
| Options with no member | 0 → 0 | 12 of 12 → 6 of 25 | 3 → 0 |
| Child walks' steps | six each → `acquire` only (10) | six each → `acquire` only (12) | six each → `acquire` only (10) |

The obesity cost of 4.32 was read before the chat question of the browser
check; with that question the task's total is 4.44. Pre-contract flag rates
are from the lead's read of 2026-09-28.

Step times of the live obesity walk, seconds: suggest 41, acquire 27, screen
76, classify 48, appraise 1, profile 93, longlist 184, constrain 28, theme 39.

### Manual, browser and API

- **Browser (obesity, desktop 1440 and mobile 390).** The longlist and one
  option card were opened. Read from the page: the card's "Tried on: …
  (2 documents), …" line, the Variants block, "Runner-up lever type: Provide
  a service.", the chip "not stated in the abstract", and "All 36 were read
  from the abstract only." The list shows the Tried on facet. No console
  error. Screenshots: `evidence/live-shots/`.
- **Found by the browser check and corrected:** the Tried on facet showed
  about 45 chips on the obesity list. It now shows 8 and "+N more on the
  option cards", the limit of the Setting facet.
- **Chat without ingest (R13 stop condition).** One question on the live
  obesity task returned an answer with 3 citations; each has
  `text_basis: abstract_only`. The stop condition is not triggered.
  Saved: `pre-contract-runs/live-out/obesity/chat-question.json`.
- **Stage 3 (the other four live runs)** did not run. It runs only on the
  owner's decision (R12).

## End-to-end command

From `backend/`, with the local API running (`uv run --env-file .env uvicorn
policy_atlas.api.app:create_app --factory --port 8000`) and a dev token in
`docs/tasks/046-longlist-refinement/evidence/token.txt`:

```
cd docs/tasks/046-longlist-refinement/evidence/pre-contract-runs
python3 drive_live.py create obesity && python3 drive_live.py pipeline obesity
```

The same for `refugees` and `caregiving`. The replay of one stage on a clone,
from `backend/`:

```
P=../docs/tasks/046-longlist-refinement/evidence/pre-contract-runs
uv run --env-file .env python $P/replay.py stage longlist obesity --label r4 --fresh
```

## Diff summary

56 files outside `docs/`, about 7,200 lines added and 1,300 removed, against
`3ac9385b`.

- **The walk.** The longlist chain is `inherit → suggest → acquire →
  screen_abstract → classify → appraise → extract_interventions → longlist →
  constrain → theme`. A child option search of a longlist walk runs `acquire`
  only; the runner joins the children before the screen; the longlist scope
  screens the whole pool once. No chain ingests full text. `theme` is a
  component of its own and not a spine step.
- **The screen input** is the wide, place-stripped target unit and the
  outcomes: no setting, no place, no option design.
- **The profile** receives the plan's tagging context and writes three tags;
  one alembic revision (`d8f3b6a2c4e1`) adds three nullable columns with two
  check constraints.
- **The longlist** works at reader grain to a target of 20 under a ceiling
  of 25, from a digest, with folds, one residual pass, thinning, short ids,
  no packages, outcomes from member tags, and typing against the baseline.
- **Constrain** judges the kind of action; the distinct screen is one call
  over the whole list; place never reaches the prompt.
- **Read models and views**, additive: tried on, variants, runner-up lever,
  counts, lever definitions by version, `text_basis` on citations.
- **Six prompt revisions**, as planned: `task_agent_scoping_v4`,
  `longlist_suggest_v2`, `extract_interventions_v2`, `longlist_cluster_v2`,
  `lever_typing_v2`, `constrain_v2`; and the list `lever_types_v2`. The theme
  prompt moved to `options_scoping/theme/` with the same hash. The option
  design prompt, the longlist verbs prompt and every Evidence search prompt
  are unchanged.

### Files under `evidence_search/` (the reuse rule, rubric box 12)

Five files, all on the contract's list: `extract/extract.py` (the optional
`interventions_context` argument, the title-only rule of the selection-free
path, the repair counter in the summary), `extract/extraction_backend.py`,
and the intervention profile's own files `extract_interventions_prompt.py`,
`interventions_records.py`, `interventions_profile.py`. `assess/screen.py`,
the search loop, the search prompts, the synthesis backend, the clustering
engine and the baseline targets have no change.

### Deviations, flagged

| # | Deviation | Why | Size |
|---|---|---|---|
| D1 | `strip_place` does not treat "from" as a place preposition. Plan S6 lists it; contract PA11 does not. | "migrants from India" would lose the origin that defines the population. The contract wins. | minor |
| D2 | The tagging context reaches the profile through the intervention profile's own bundle (`functools.partial`), not as a new parameter of `_run_profile` (S4's wording). | The shared pipeline and the IOF and ICF bundles stay untouched. Same effect. | minor |
| D3 | The three tags are required-nullable fields of the wire model from v2; in Phase 1 they were on the carrier and the stored record only. | The wire model is both prompt text and response schema; Phase 1 had to leave the prompt unchanged. | minor |
| D4 | `_own_units` keeps one extraction per document (the current plan's, else the newest) and counts the rest in `provenance.scopes.superseded_records`. | Needed so that a document profiled under two contexts counts once (AM5), before thinning. | minor |
| D5 | A setting facet label is the most frequent original spelling of its group, not the fold key. | The fold key ("jobcentre") is not a reader's word; the existing tests pin the natural spelling. | minor |
| D6 | The merge keeps the option that the unchanged rule of 2026-09-24 names (the user's and the Evidence search's first, then the earliest). Round 0 of the distinct prompt let the model choose; corrected in `26e37141`. | The contract says the merge rule is unchanged. | corrected |
| D7 | Discovery is still called with no room under the ceiling when a seed can be folded. | So a rebuild over 25 can shrink (AM9). New options in that answer are dropped and counted. | minor |
| D8 | A failure of the residual pass keeps the first pass and records `residual_pass.skipped = "failed"`. | The longlist is still written. The contract does not say. | minor |
| D9 | The variants block is in the card's "What it is" section, not in the evidence section. | A variant is a design of the option. Lead call (taste-bearing). | minor |
| D10 | The Tried on facet shows at most 8 chips. | The browser check showed about 45. | minor |
| D11 | The lever definition by version is shown per lever GROUP on the list: the version's definition when the group's options share one version, else the current one. | The card has no longlist data; a group can hold options of two versions. | minor |
| D12 | The spec changes of the contract are **not applied**. | The owner has not accepted the wording. See § Known unverified items. | open |
| D13 | The owner's stage decisions (R25) were not taken during the build. | No owner was present. The reports are in the round records. | open |

### Existing tests edited (rubric box 19)

No test was deleted or skipped. Each edit follows a behaviour that the
contract changes.

| File | Edit | Reason |
|---|---|---|
| `tests/evidence_search/extract/test_extract_interventions.py` | title-only test asserts "dropped and counted"; stub override signature; version string `v2` | item 15 (R17); `interventions_context`; prompt version |
| `tests/evidence_search/extract/test_interventions_tagging.py` | pinned context-free fingerprints re-pinned | the prompt version is in the fingerprint |
| `tests/runtime/test_compose_by_purpose.py`, `test_option_search.py`, `test_inherit_documents.py` | chain content; join before the screen; compose signature | items 18, 22; R28; S1 |
| `tests/options_scoping/test_longlist.py` | theme assertions moved to `test_theme.py`; units from parentless scopes; ceiling, bundle, seeds-over-ceiling and typing tests rewritten; fixtures follow the new wires | R28; AM5; items 1, 4, 7 |
| `tests/options_scoping/test_longlist_intent.py`, `tests/api/test_longlist_start.py` | two criteria, no setting; `place_removed` | item 23 |
| `tests/options_scoping/test_constrain.py` | distinct as its own call; screen ids; batch sizes compared sorted | items 5, 7 |
| `tests/api/test_longlist_routes.py` | fixtures without bundle wire fields (the fixture writes its `part_of` rows with `created_by="user"`); fake backend signature | item 4; item 9 |
| `tests/api/test_read_models.py`, `test_answer_core.py` | one assertion added each (`text_basis`) | PA3 |
| `frontend … OptionCard.test.tsx`, `runProgress.test.ts`, `RunningCard.test.tsx` | flag wording; the longlist sentence has no theme count | item 3; R28 |

## Review findings

Not yet. The review stack (step 7) runs in a fresh conversation.

## Rubric status

Build-phase view. The review conversation checks each box against the code.

| Box | State at the end of the build |
|---|---|
| 1 Discovery at reader grain | built; M1, M2 pass in the replay and live |
| 2 Assignment | built; mini model kept, measurement recorded |
| 3 Typing and themes | built |
| 4 Constrain | built; M4 passes |
| 5 The intervention profile | built; **M5 fails on the live caregiving run** |
| 6 Thinning | built |
| 7 Screening | built; one stage-1 screen row per document in the three live runs |
| 8 | withdrawn by AM1 |
| 9 Ingest | built; chat citations carry *abstract only* |
| 10 Tried on | built; M6 passes |
| 11 Small | built |
| 12a Amendments | built |
| 12 The reuse rule | holds (five files, all on the contract's list) |
| 13 `make verify` | holds: green at the step-6 exit |
| 14 Prompt revisions re-pinned, each round's diff recorded | holds; diffs and findings in `evidence/rounds/` |
| 15 The staged check | done, except the owner's stage decisions (open) |
| 16 One reversible revision | holds (`d8f3b6a2c4e1`, round-trip test) |
| 17 No approval-gated change beyond the contract | holds |
| 18 No generated files or secrets edited by hand | holds (`make openapi-sync` wrote the generated files) |
| 19 No tests deleted, skipped or weakened | holds; edits listed above |
| 20 Spec changes only with the owner's accepted wording | **not applied**; wording proposed in [spec-changes-proposed.md](spec-changes-proposed.md) |
| 21 `docs/deferred.md` | done |
| 22 ADR 0040 | written in the design phase (`5d9f206a`); the owner has not yet read its text |
| 23 The review stack | not run (step 7) |

## Intent & assumptions

- The build ran under a session goal with no owner present. Rulings that
  needed the owner were not taken; they are listed as open.
- The plan's gate map was followed: full verify at Phases 0, 1, 2 and 8.
- A replayed seed has no search of its own, so a replayed option can show
  fewer documents than a live run. The live runs are the test of the whole
  walk.
- One live run per question. The mini model varies between runs, so a
  figure of one run is an observation, not a rate.

## Known unverified items

1. **The spec changes are not applied** (contract § Spec changes items 1–9;
   rubric box 20). The wording is in
   [spec-changes-proposed.md](spec-changes-proposed.md). The specs still
   describe the 045 behaviour in the places that file lists.
2. **The owner's stage decisions** for the four loops (R25).
3. **M5 fails on the live caregiving run** (one named body in the top 8
   setting labels).
4. **Constrain excluded no option in the three live runs** and 1 of 163 in
   the replays. The pre-contract runs excluded 13 to 20 per run. Part of
   this is wanted (R21); part is that discovery now keeps off-scope kinds off
   the list. No measure tests a wrong pass. Example to judge: the live
   obesity list holds "Food-industry political donation and lobbying
   controls", which passed the relevant and in-scope screens.
5. **The distinct screen found no duplicate** in ten lists (seven replays,
   three live). The merge path is covered by tests, not by a live case.
6. **Both of the user's own options have no member in the live refugee
   run** (6 of 25 options have none). Their option searches acquired
   documents, but the assignment placed no record under them.
7. **The not-stated flag is on 79 to 86 percent of memberships** in the
   live runs (R23: the owner decides).
8. **The reasoned-guess path has no live test** (no plan had a preference).
9. **The add walk ("Add an option") was not run live.** Its chain is tested
   with the stub backends only.
10. **A rebuild of a task built before this slice was not run live**; the
    no-double-count rule is tested with seeded rows.
11. **The Your-context path for a stated setting has no replay case**: no
    question of the seven states a setting without a requirement.
12. **Live stage 3** (the other four questions) did not run.
13. Document titles in the live data show two defects that this slice did
    not make: "[THIS TITLE IS BROKEN AND HAS BEEN REMOVED]" and an
    unescaped HTML entity ("Welfare&#39;s").

## Public safety

This file holds counts, option names, setting labels and task id prefixes.
It holds no secret, no raw source text and no trace. The replay tool, the
drive scripts, the read-backs, the screenshots and the round records are in
the gitignored `evidence/` folder. The local dev token that the live runs
used was a file in that folder; it is deleted. The prompt diffs are in the
round records and in the commits.

## Review handoff (step-7/8 inputs)

### Adjudication items

1. Deviations D1 to D13 above.
2. The build agents' calls that no brief settled: discovery with no room
   (D7); the residual-pass failure (D8); two more fold guards
   (`into_itself`, `seed_is_fold_target`) and the re-pointing of earlier
   merges; the runner-up carry-forward stops at a clean typing; the distinct
   call has one retry; an option in a `part_of` relation keeps the forced
   `passes` when the distinct call fails; a new option whose typing fails
   has null lever columns; `provenance.ceiling.excess` is the final option
   count over 25.
3. `theme.py` imports private names from `longlist.py` (`_engine_stats`,
   `_forbidden_label`, `_key`).
4. The unit payload still sends `study_geography` and `quote` to the
   assignment; the prompt does not list them.
5. `current_profile_fingerprints` returns the fingerprints of both backend
   modes, because the longlist component does not know the mode.
6. The setting-repair log line repeats each time coverage is computed.
7. The stub longlist backend is now behind a lock and hands out canned
   responses in call order.

### Executor provenance (for the family flip)

Every phase ran in the Claude family. No phase ran on Codex. The Codex lane
anchors the step-7 review.

| Work | Executor |
|---|---|
| Phases 1, 2, 3 (tool), 4.3, 5.1, 6.1 code | `deep-reasoner` |
| Phase 7.1, 7.2 | `fast-worker` |
| All prompts, all loops, reads and rulings, the place strip fixes, Phase 7.3 words, the lever definition by version, the facet limit, this file | lead |

### Diff-scoping exclusions

`frontend/openapi.json` and `frontend/src/api/gen/types.ts` are generated.
`scripts/prompt_hashes.json` is a pin file. The sub-national table in
`where_tried.py` is data.

### Live-trace pointers

Langfuse session id = task id. Live tasks: `3f6b79b9-3e4b-4b37-8bf5-e9ec26db5833`
(obesity), `42dd142c-5cb3-4e77-88a3-584bd49243ce` (refugees),
`ff6ef83c-d137-44a0-8460-c02b86adf6ff` (caregiving). The replay clones are
tasks named "… — 046 replay clone" in the dev database; `clone.py <slug>
--drop` removes one.

### Knowledge candidates

- The intervention wire model is both prompt text and the response schema:
  a field added to it changes the prompt and the model call.
- The profile memo key holds the prompt **version**, not the prompt text. A
  text change with no version change reuses old records.
- A small model follows a judgement rule better when the wire asks for the
  reason **before** the label or the verdict.
- A rule with two ways out needs both closed: the mini model moved
  class-level reviews from "ungroupable" to "not an option" when only the
  first was closed.
- The judgment model is not better at every task: on assignment it placed
  more class-level reviews but flagged every membership and left more
  records unclustered.
- One screen per document is the largest cost lever of the walk: the screen
  cost fell from 4.79–9.65 to 0.85–1.29 USD per run.
- Run-to-run variation on one prompt: about plus or minus 3 options and
  plus or minus 15 unclustered records; a setting label removed in a replay
  came back in a live run.
- A fold key is not a label: group by the key, show a natural spelling.
- `strip_place` must tidy what a removal leaves: a dangling "and", "of" or
  preposition. Found only by running real plans.
- `test_capability_registry` fails any module outside the registry that
  calls `ScopingPlan.model_validate`; use `validate_plan(OPTIONS_SCOPING, …)`.
- A new stage key changes the OpenAPI document; `drift-check` is red until
  `make openapi-sync`.
- `make verify-fast` takes about 13 minutes on this repo (3,300 tests); it
  is not much faster than the backend part of the full gate.
- A page with an open event stream never reaches Playwright's
  `networkidle`; wait for `domcontentloaded` and a fixed time.
- A subagent that starts its gate in the background can stop before it
  reports; the brief must say that the final message is the report.
- A delegated worker wrote a code comment that attributed a rule to the
  owner with a date. No such statement existed. Check attributions in
  delegated output.
- The dev database was one migration behind at build open; a replay or a
  live run needs `alembic upgrade head` first.
- The stored refugee task holds 175 documents; the "17" of the earlier
  notes was the profiled set.
- The 045 migration round-trip tests pass through the new revision with no
  change; the alembic versions directory is outside the ruff gate.

## Deferred work

[docs/deferred.md](../../deferred.md): § Options scoping longlist refinement
(task 046 seams), § System-level cost and latency, the second case in
§ Synthesis optimisation, and open question 4 marked closed.
