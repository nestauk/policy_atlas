# Verification: 046-longlist-refinement

Evidence for the build phase (steps 5 and 6) of task 046. Items, rulings
(R1–R28), amendments (AM, PA), seams (S1–S15) and measures (M1–M9) are
defined in [contract.md](contract.md) and [plan.md](plan.md).

> **Status:** build complete 2026-09-29 · lead; **amendment 2 build complete
> 2026-09-30** (§ Amendment 2 below). Steps 5 and 6 only. The review stack
> (step 7) has not run; it runs in a fresh conversation.
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

## Amendment pass 1 (2026-09-29, after the owner read the results)

The owner's rulings R29 to R33 are in contract.md § Amendments after the
live check, with the owner's words.

| Ruling | Change | State |
|---|---|---|
| R29 | The lever type has a reason on the card. The typing wire keeps `lever_reason` (written before the type); it is stored with the longlist result and served as `lever_reason`. When no lever type fits, the card shows the none-fits reason only. | built |
| R30 | The chip "not stated in the abstract" is off the longlist card. The flag stays in the data. | built |
| R31 | The design of the user's own option names no place: prompt `option_design_v2` (the seventh prompt revision, on a finding) and a code guard (`strip_place` on the name, the description and each feature). The user's words stay verbatim. | built |
| R32 | No fixed list of setting kinds. Three other ways were measured on the three live runs (`evidence/rounds/9-setting-study.txt`). Nothing is built. | open, with the owner |
| R33 | Constraints. A test with hard requirements ran on three replays (`evidence/rounds/9-constrain-hard-requirements.txt`): requirements about what the option is were judged correctly (7 of 7 exclusions correct); requirements about who can act were judged too leniently. The planning prompt was probed with the owner's example (`evidence/rounds/9-plan-probe-temporary-accommodation.json`). Nothing is built. | open, with the owner |

Gates of the pass: `make verify-fast` backend 3325 passed; `prompt-guard` 24
unchanged; `drift-check` OK; `frontend-verify` 87 files, 825 tests. The full
`make verify` must run again before the review, because the tree changed
after the step-6 exit gate.

Not yet replayed: R29 and R31 change two prompts. No replay round has read
the lever reasons or the new designs by hand.

Test data left in the dev database: the replay clones of refugees, obesity
and energy hold the test requirements of R33 in their plans.

## Amendment 2 (build 2026-09-30)

Rulings R34–R53 are in [contract.md](contract.md) § Amendment 2; the design
in [amendment-2-final.md](amendment-2-final.md) ("final"); the phases 9.0 to
14 and the seams S16–S20 in [plan.md](plan.md) § Amendment 2. Steps 5 and 6
only; the review stack runs in a fresh conversation. Every figure below was
read back from a saved file or a database query, named beside it.

### Commands run (the gates)

The gate of each phase ran on a **snapshot of the git index** in a second
worktree (`../policy_atlas-gate`, the `gate.sh` script in the session
scratchpad), so that the next phase could be built while the gate ran. A
commit was made only when the index tree equalled the gated tree. The full
gate ran at Phase 9.0 and at the tree of Phases 9 + 10; Phase 14 carries the
step-6 exit gate.

| Gate | Result | Notes |
|---|---:|---|
| `make verify` (Phase 9.0, build-open baseline) | pass | backend 3325 passed (745 s); infra 46; frontend 87 files, 825 tests; prompt-guard 24 unchanged |
| `make verify` (Phases 9 + 10, one tree) | pass | backend 3341; frontend 829; drift-check OK; prompt-guard 24 unchanged after the re-pin |
| `make verify-fast` · `prompt-guard` (9L round 1) | pass | backend 3341 |
| `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` (Phases 11 + 12a, one tree) | pass | backend 3357; frontend 830; the first `frontend-verify` failed on a `pnpm` purge prompt in the gate worktree (a symlinked `node_modules`); a real install and a second run passed |
| `make verify-fast` · `prompt-guard` · `drift-check` (Phase 12b) | pass | backend 3384; prompt-guard 25 unchanged |
| `make verify-fast` · `prompt-guard` (12L round 1) | pass | backend 3384 |
| `make verify-fast` · `prompt-guard` · `drift-check` (Phase 13) | pass | backend 3394 |
| `make verify-fast` · `prompt-guard` (13L round 1) | pass | backend 3394 |
| `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` (Phase 14a) | pass | backend 3403; frontend 853 |
| `make verify-fast` · `frontend-verify` (Phase 14a.3, the polish after the browser check) | pass | backend 3403; frontend 853 |
| `make verify` (Phase 14, step-6 exit) | **pass** | backend 3403 passed (1000 s); infra 46; prompt-guard 25 unchanged; drift-check OK; frontend 87 files, 853 tests; exit 0. Run on the snapshot of this commit's tree with this one table line still unfilled; the line is the only change after the gate. |

Red gates in the build: none from the code. One tooling red (the `pnpm`
purge prompt above), not a test.

### Commits on `task/046-longlist-refinement` (local, not pushed)

| Commit | Phase |
|---|---|
| `461ef666` | 9 — the plan kinds `boundary` and `consideration`; planning prompt v5 round 0 |
| `5b527867` | 10 — the revision `e9a4c1f7b3d2`: `longlist_result.option_profile` |
| `56c5d96a` | 11A — ADR 0040 amended (decisions 9–15, the rollback) |
| `43cfb768` | 9L round 1 |
| `5f6f2b5a` | 11 — outcome counts in coverage |
| `6940ca24` | 12a — the component `option_profile`, lever typing moved |
| `8e1301b0` | 12b — the line, ambition and setting calls; `option_profile_v1`, `lever_typing_v3` round 0 |
| `8f066d75` | 12L round 1 |
| `f900a483` | 13 — the authority label; `constrain_v3` round 0 |
| `854225ae` | 13L round 1 |
| `9844111c` | 14a — read models and views |
| `5ab7b342` | 14a.3 — the polish after the browser check |
| the commit that adds this section | 14 — this file, `docs/deferred.md`, the spec-change proposals |

Phases 9 and 10 were gated on one tree and committed as two commits (the
Phase 10 files are disjoint); Phases 11 and 12a likewise (the Phase 11
hunks were split out of the shared `longlist.py` diff). Each intermediate
commit's own tree was not gated alone; the tree at each gate holds it.

### Deterministic tests (the plan's test lists)

| Plan phase | Where | Result |
|---|---|---|
| 9: the four kinds and their `checked_at`; a consideration needs an aspect; a boundary refuses one; wire → plan keeps `aspect` and `hard`; an unknown aspect fails closed; the API contract mirrors the vocabularies; a consideration reaches neither of constrain's lists nor suggest and excludes nothing | `tests/runtime/test_scoping_plan.py`, `tests/options_scoping/test_constrain.py`, `test_suggest.py` | pass |
| 9: the plan screen shows a consideration with its line and sentence; a boundary shows the word "requirement" and no kind word | `PlanDocument.test.tsx`, `planVocabulary.test.ts` | pass |
| 10: round trip of `e9a4c1f7b3d2`; an old row reads `{}` | `tests/core/test_migration_046_option_profile.py` | pass |
| 11: a document on two outcomes counts for both; `described` counts for nothing; `other` counts in the total only; DOI collapse; every plan outcome listed in order | `tests/options_scoping/test_longlist_coverage_046.py` | pass |
| 12a: the chain order; registry, graph, plan mapping, `LLM_BEARING_COMPONENTS`, stage keys, stage map and `runProgress` know `option_profile`; `longlist` writes no typing; **the equivalence test** (a stub run's lever columns and typing keys before and after the move, saved as literals before the move); a failed step fails the walk | `tests/options_scoping/test_option_profile.py`, `test_theme.py`, `tests/runtime/test_compose_by_purpose.py`, `runProgress.test.ts` | pass |
| 12b: every line written for every option; `who_decides` and `dependencies` never marked; marks stored as `less` / `more` / null; ambition on every option; the setting lower-cased; Where in the `who_decides` input only; payload keys; at most 5 records by role; a call malformed twice fails the step and writes nothing; once then right succeeds with `retries` 1; a failed typing batch keeps the previous typing; an excluded option is profiled, a merged one not | `test_option_profile.py`, `test_option_profile_prompt.py` | pass |
| 13: no consideration → no call, no entry; one call with every profiled option; the three labels with reason and body; **no exclusion from the label or from any consideration**; the batches and the distinct call get no `who_decides` line and no Where; a call malformed twice → no entry, the step succeeds; the read model lists the same judgements; an unprofiled option is not sent | `test_constrain.py` | pass |
| 14a.1: the profile served in order; settings from the profile; no entry → `profile` null; the authority from `judgements` and absent from `JudgementOut`; ambition `less` / `more` / null, a stored band value served as null; `outcome_counts`; `LonglistOut` has no `ambition_bands` | `tests/api/test_longlist_routes.py` | pass |
| 14a.2: the words (line names, the ten level words, no banned phrase, "Middle" in the grid only); the section collapsed on open and its `<dl>` after a click; absent without a profile; the Who can act facet filters and does not reorder; the column chooser; Untagged | `OptionCard.test.tsx`, `LonglistView.test.tsx`, `LonglistGrid.test.tsx`, `longlistPresentation.test.ts` | pass |

### The refine loops (R48; rubric box 35)

Round records: `evidence/rounds/9L-planning-loop.md`,
`12L-profile-loop.md`, `13L-constrain-loop.md`, with the diffs
(`*-r0.diff`, `*-r1.diff`), the figures and the read-backs beside them.

| Loop | Prompt(s) | Rounds | Stop measure | Tuning set | Check set |
|---|---|---|---|---|---|
| 9L planning | `task_agent_scoping_v5` | 2 (r0, r1) | every statement in the right kind and line (probe + tuning set) — **met at r1** | probe: 8 of 8 statements right; refugees asks who can act; England / UK plans do not ask | NEET asks the target unit; heat pumps, cohesion right |
| 12L profile | `option_profile_v1`, `lever_typing_v3` | 2 (r0, r1) | none of the six known faults of final § 6.1 — **met at r1** (r0: 3 who-decides lines named a regulation no baseline holds) | M10 0 missing on 4 lists; M12 1 to 10 setting labels; M14 passes on obesity and caregiving | 3 lists: no law, no acronym, no empty setting for an option that has one; 7 to 9 labels |
| 12L profile, rounds 2–3 (after the build, 2026-09-30, lead) | `option_profile_v1` | 2 more (r2, r3) | r2: body names as government publications use them (no legal or expanded names) — **met**; r3: the owner's R25 ruling on the spread of the marks — about a third in each level where the data supports it, never forced — **met**, stability 82–88% same mark on two runs (old rule 83%) | r2: obesity, caregiving; r3: obesity, caregiving, refugees, two runs each | none (all three lists used); figures in `12L-profile-loop.md` § Round 2, § Round 3 |
| 13L constrain | `constrain_v3` | 2 (r0, r1) | M11 ≥ 9 of 10 — **met at r1**: refugees 22 of 23, obesity 22 of 24 (r0: about 4 of 23 and 20 of 24; the call matched names) | no exclusion from who decides (1 and 1 exclusions, both by a boundary) | none possible (only two clones hold such statements) |

No loop ran more than two rounds. The prompts were tuned on the tuning set
only. Each prompt is re-pinned in `scripts/prompt_hashes.json` (25 modules).
The stored tasks are unchanged by the replays: `replay.py check-stored` after the loops and the live runs shows 18 of 19 tables of every stored task equal to the reference; the one changed table is `longlist_result`, whose rows gained the new column `option_profile` = `{}` from revision `e9a4c1f7b3d2` (their `created_at` and `run_id` are the old ones; the old reference is kept as `rounds/14-check-stored-reference-before-e9a4c1f7b3d2.json` and a new reference was saved after the check).

**Reported measures (R49):** M10 0 missing sentences on 11 replays; M12 at
most 10 labels per list, no place name, two body kinds ("council" on NEET,
"public service" on cohesion); M14 a nudge below a clinical service on
delivery complexity on obesity and caregiving; **the overlap of coordination
with delivery complexity** (box 38), with the decided question, round 1:
same level 12 of 24 (obesity), 19 of 23 (refugees), 14 of 22 (caregiving),
7 of 19 (energy), opposite 1, 0, 2, 2; check set 15, 12, 13 of 25, opposite
0, 1, 1 — beside the old-question figures of final § 6.3 (52 percent same
on seven lists; 14 of 24 on the live obesity list). Source:
`12L-profile-r1-*.json`, `12L-profile-check-*.json`.

**Marks on a split list.** On the obesity replay about two thirds of the
options carry a cost mark at r0 and r1 (17 of 24), because the list holds
rules (cheap, slow to set up) and programmes (costly, quick) that stand out
against each other; on energy the count fell from 13 to 7 of 19 with round
1. The lead did not tune on the count: the owner accepted the way-A rule
and its stability, and a cap would be a quota. For the owner (R25).

**The owner's stage decisions (R25):** after the build the owner read the live runs and ruled on the spread of the marks ("about a third in each band, although only if the data supports it, the tool shouldn't force that by rule"); round 3 of 12L applies it. The other stage decisions stay open. Each loop record ends with its report.

### Live check (Phase 14): three rapid runs on new tasks

Run through the local API on the final backend code (the tree of
Phases 9–14a; the frontend polish of 14a.3 changed no backend file), not
attended, with `drive_live.py`. Tasks (dev database): obesity `8d73e096`,
caregiving `161ac3d5`, refugees `1409ae63`. Every longlist walk ended
`succeeded`. Sources: `evidence/rounds/14-live-runs.log`,
`14-live-metrics-<slug>.txt`, `14-live-profile-<slug>.json` and
`-read-<slug>.txt`, `14-live-cost.txt`, `14-live-refugees-rebuild.log`,
`pre-contract-runs/live-out/<slug>/longlist-read*.json`.

The refugees plan did not ask who can act on this run (it did on the two
replays and on the first live attempt, which the driver could not answer:
the turn response carries no `part`). After the first walk the lead added
the consideration "Only options that the council can act on itself are of
use to us. It cannot change national law." (`who_decides`, hard) through
`PATCH /plan` and confirmed on plan version 2, which opened a **rebuild**:
the second walk ran the whole chain again (601 s) and labelled every
option. This is also the first live rebuild of the slice.

| # | Measure | Obesity | Caregiving | Refugees (rebuild) | Pass |
|---|---|---|---|---|---|
| M1 | Options per run (13 to 25) | 25 | 25 | 24 | **pass** |
| M2 | Rows that are one named trial | none | none | none | **pass** |
| M4 | Exclusions with place or population overlap as the reason | 0 (0 exclusions) | 0 (1 exclusion, "Paid family leave for new parents" by the setting boundary) | 0 (0 exclusions) | **pass** |
| M5 | Setting labels in the top 8 that are a country, region or body | none (school, retail, community venue, home, food outlet, clinic, street, park) | none (clinic, home, family hub, hospital, workplace) | none (home, college, housing office, workplace, employment office, government office, community centre, welfare office) | **pass** |
| M6 | Adjacent evidence shown as tried on | 22 of 25 options | 18 of 25 | 11 of 24 | **pass** |
| M10 | Every option has a sentence on every line | 25 of 25 | 25 of 25 | 24 of 24 | reported |
| M11 | The authority label right (read by hand) | no consideration; no label | no consideration; no label | 24 labelled: 20 within your power, 4 needs action by (the Parliament of the United Kingdom ×2, the NHS Greater Manchester Integrated Care Board, the Equality and Human Rights Commission); 24 of 24 defensible | reported (live) |
| M12 | Setting labels per list; place or body names | 10; none | 5; none | 9; "government office", "welfare office" are kinds of body | reported |
| M14 | A nudge below a clinical service on delivery complexity | campaigns `less`, family weight management `more` | self-guided materials `less`, perinatal mental health treatment pathways `more` | — | reported |

The setting facet now reads the option-level setting (R41): the M5 fault
of the first build (a named location in the caregiving top 8) cannot
recur from the records.

Reported (M7–M9), beside the first build's live runs of 2026-09-29:

| Measure | Obesity 2026-09-29 → now | Caregiving → now | Refugees → now |
|---|---|---|---|
| M7 cost per task (Langfuse, USD) | 4.32 → 5.56 | 4.24 → 5.64 | 3.29 → 9.20 (two walks: the build and the rebuild) |
| M7 of which `option_profile` | — → 1.60 | — → 1.62 | — → 3.24 (two walks) |
| M7 of which screen | 1.29 → 1.22 | 0.97 → 0.95 | 0.85 → 2.03 (two walks) |
| M8 longlist walk, seconds | 622 → 638 | 569 → 634 | 531 → 501 (first walk), 601 (rebuild) |
| M8 `option_profile` step, seconds | — → 62 | — → 56 | — → 67 (first walk), 72 (rebuild) |
| M8 baseline, seconds | 227 → 212 | 213 → 242 | 228 → 197 |
| M9 pool (documents) | 334 → 327 | 249 → 245 | 234 → 223 |
| M9 relevant in the longlist scope | 190 → 181 | 173 → 174 | 102 → 77 |
| M9 screen rows per document, longlist scope | 1.00 → 1.00 (327 of 327) | 1.00 → 1.00 | 1.00 → 1.00 |
| M9 documents with no screen row | 0 → 0 | 0 → 0 | 0 → 0 |
| M9 duplicate titles | 22 → 20 | 24 → 27 | 34 → 16 |
| Options excluded | 0 → 0 | 0 → 1 | 0 → 0 |
| The user's own options with no member | — | — | 2 of 2 → 2 of 2 (as in the first build) |

Step times of the live obesity walk, seconds: suggest 48, acquire 23,
screen 90, classify 60, appraise 1, profile 127, longlist 141,
`option_profile` 62, constrain 23, theme 30 (from
`14-live-metrics-obesity.txt`). The option profile adds about one minute
and 1.60 USD to a walk (R46: no time limit is a pass condition).

Marks on the live lists (options marked, of 25 / 25 / 24): cost 15 / 5 /
14; workforce 14 / 11 / 13; delivery complexity 14 / 13 / 12; ambition
9 / 5 / 5 (`14-live-profile-<slug>.json`). Who-decides lines: no law, no
acronym; one body each (obesity: "A local authority in England" 8, "The
Department of Health and Social Care in England" 6, "The Department for
Education in England" 6, "The Parliament of the United Kingdom" 2, "A
local planning authority in England" 1; caregiving: "The National Health
Service Commissioning Board in England" for a maternity policy).

### Browser check (rubric box 33)

Live obesity (desktop 1440 and phone 390), with Playwright on the dev
server against the local API, and live refugees for the filter.
Screenshots: `evidence/live-shots/a3-*.png`. Read from the page:

- The card: "What it is" carries "Ambition: Smaller. This adds remote
  parent coaching …", "Delivered through: home"; "What it would take" with
  the label "Estimate, before assessment" opens **collapsed** as a row of
  eight cells (Cost · Cheaper; Workforce requirements · Lower;
  Coordination requirements · Lower; the other five with no word); after
  a click it shows the eight lines with their sentences in a definition
  list; "What the evidence base holds so far" carries "4 documents
  evaluated this option." and the counts per plan outcome ("… at
  reception: 2 documents", "… at year 6: 1 document", "… gap …: no
  documents").
- The list: rows carry the lever only; Group by Theme · Lever type; the
  Setting facet shows the option-level settings.
- The grid: "Columns: Cost" gives Cheaper · Middle · Costlier (no Untagged:
  every option has a profile); "Middle" appears only there.
- Refugees (after the rebuild): the "Who can act" facet with its three
  chips; "Needs action by another body" pressed shows "4 of 24 options
  match"; a labelled card shows "Needs action by The Parliament of the
  United Kingdom. …".
- The first round found two defects, fixed in 14a.3: the eight cells in
  one row overlapped their names at desktop width (now four columns); the
  heading label broke the heading at phone width (now on its own line on
  phones). One confirmation round passed.
- No console error was checked by hand; the dev server reported none in
  its log.

### Diff summary (amendment 2)

Against `74729ba7`: 70 files outside `docs/`, about 6,250 lines added and 1,000 removed (through 14a.3).

- **The plan.** `ConstraintKind` is `boundary` · `consideration` ·
  `preference` · `evidence_restriction`; a consideration carries `aspect`
  (one of the eight line keys or `transferability`) and `hard`, is checked
  at assessment, reaches neither constrain's lists nor suggest, and never
  changes an option's state. No plan slot "who decides". No code reads
  `requirement`. `PROFILE_LINE_KEYS` lives in `runtime/scoping_plan.py`.
- **The walk** is `… → longlist → option_profile → constrain → theme`.
  `option_profile` (new package) is a spine step: lever typing moved in as
  built (same prompt text at round 0, `lever_typing_v3` without ambition at
  12b); ten calls over the whole list at one time (eight lines, ambition,
  setting) on the judgment model; a call malformed twice fails the step
  before any write. Writes: `longlist_result.option_profile` (one JSON
  column, revision `e9a4c1f7b3d2`), `option.ambition` (`less` · `more` ·
  null) and `option.ambition_reason`, the typing keys as before.
- **Constrain** makes one authority call when the plan holds a
  consideration on who decides, and writes one entry per option under the
  key `authority` in `judgements`; never an exclusion. The guess wording
  loses its suffix.
- **Coverage** carries `outcome_counts` (documents that evaluate the option;
  per plan outcome).
- **Read models**, not additive: `ambition_bands` and `AmbitionBandOut`
  removed; `profile`, `authority` on the option models; `outcome_counts` on
  the evidence profile; `settings` from the option-level setting. OpenAPI
  diff: `evidence/rounds/14a-openapi.diff`.
- **Views.** Plain rows; group by theme and lever type; the Who can act
  facet; the card's "What it is" with ambition, delivery setting and the
  authority line; "What it would take" collapsed on open (a row of eight
  cells; expanded, a definition list), with the label "Estimate, before
  assessment"; the outcome counts; the grid's column chooser (seven lines,
  Ambition by default) with Middle and Untagged; no compare table. Level
  words tinted (pale aqua lower, pale violet higher, navy text): the lead's
  proposal for the owner's decision on the built screen.
- **Prompts**: `task_agent_scoping_v5`, `option_profile_v1` (new),
  `lever_typing_v3`, `constrain_v3`; `extract_interventions` unchanged.

### Deviations, flagged (amendment 2)

| # | Deviation | Why | Size |
|---|---|---|---|
| D14 | The plan screen shows no kind word for a boundary ("Requirement" was built, then dropped). A consideration shows "Consideration · <line>" and "Stated limit". | The effect sentence already says what a boundary is; just enough text. | minor |
| D15 | The who-can-act question is asked as a part `who_can_act` with two buttons ("Only what <the body> can adopt" · "Also options that need national action"), not in the exact words of A2 ("Should I keep only options…"). | "Keep only" would promise an exclusion the label never makes; the reply says every option stays and is labelled. | minor |
| D16 | The heading label reads "Estimate, before assessment", not "Policy Atlas's estimate before assessment". | The long form overflowed the heading row at phone width; the short form keeps the meaning. Final § 7.1 left the exact words open. | minor |
| D17 | The gates ran on index snapshots in a second worktree, and two pairs of phases (9 + 10, 11 + 12a) shared one gate tree. | So that building and gating could overlap; the plan's gate classes were not reduced. | process |
| D18 | The `option_profile` column loses the line order in storage (JSONB sorts keys); the read model orders by `PROFILE_LINE_KEYS`. | Postgres. | minor |
| D19 | `kept` in the `option_profile` summary counts only options that had a typing before; `invalid` counts every option with no valid typing from this run. | The two numbers were otherwise always equal. Agent decision, accepted. | minor |
| D20 | The typing usage moves from `longlist`'s `usage_totals` to `provenance.option_profile.usage_totals`. | It is the profile's call now. | minor |
| D21 | The authority call runs for the duplicates a run will merge; their labels are dropped at write time. | Which options merge is known only after the batches. | minor |
| D22 | The spec changes of amendment 2 are **not applied**; the wording is proposed in [spec-changes-proposed.md](spec-changes-proposed.md) § Amendment 2 (items 10–17). | The owner has not accepted any wording. | open |
| D23 | The tints of the level words are built as the lead's proposal (final § 7.1 item 1). | The owner decides on the built screen. | open |

### Existing tests edited (amendment 2; rubric box 19)

No test was deleted or skipped. `test_option_profile.py` holds the typing
tests moved out of `test_longlist.py` with their assertions unchanged. Edits
that follow a behaviour the amendment changes: the kind literal
`requirement` → `boundary` (seven backend test files); `ambition` no longer
`incremental` from the stub (`test_longlist_routes.py`, `test_option_profile.py`);
the guess text without its suffix (`test_constrain.py`); summaries without
`none_fits` (`test_longlist.py`); the chain lists with `option_profile`
(`test_theme.py`, `test_compose_by_purpose.py`, `test_acquire_only_walk.py`,
`test_option_search.py`, `test_longlist_start.py`); `ambition_bands` gone
and `settings` from the profile (`test_longlist_routes.py`); the ambition
group and the band words gone from the vitest files.

### Rubric status (amendment 2 boxes)

| Box | State at the end of the build |
|---|---|
| 24 The plan | built; 9L stop measure met (probe 8 of 8) |
| 25 `option_profile` | built; the equivalence test; a failed call fails the step |
| 26 What it would take | built; M10 0 missing |
| 28 Who decides and the label | built; M11 22 of 23 and 22 of 24; no exclusion from a consideration (test + 13L) |
| 30 Ambition | built; bands removed everywhere |
| 31 The delivery setting | built; M12 reported |
| 32 Outcome counts | built; the rule pinned by a test |
| 33 The reader and the words | built; built; the browser check on live obesity and refugees (both states of the block, the grid with a chosen line, the plain rows, the Who can act filter) |
| 34 Out of the first version | holds: no acceptability, burden, legal-change or powers line |
| 45 The rename | holds; `9-rename-boundary.txt` |
| 35 Every prompt through a loop | holds; four loops of two rounds, one stop measure each |
| 36 No fixed lists, bands or anchors | holds (the prompts hold none; the code has no guard on the marks) |
| 37 The known faults tested | holds; 12L r1: none of the six on the tuning set |
| 38 The overlap measured | holds; figures above |
| 39 No code for old longlists | holds (a stored band value is served as null by the generic rule, no mapping) |
| 40 Migration | holds: `e9a4c1f7b3d2`, round trip, full verify at its gate |
| 41 Measures and time | M8, M10, M12, M14 reported |
| 42 Task 3 principle recorded | `docs/deferred.md` § Amendment 2; spec item 15 proposed |
| 43 Spec changes of amendment 2 | **not applied** (D22) |
| 44 Gates | full verify at 9.0 and 14 (and at 9 + 10); 9 and 12a passed `openapi-sync` and `frontend-verify`; ADR amended in its own commit before 12a |
| 46 The corrected lines | the OpenAPI diff removes `ambition_bands` and adds the fields of final § 3; the rollback and the known limits are in ADR 0040 § Rollback and § Amendment 2 |

### Known unverified items (amendment 2)

- **A user outside the UK.** "Who decides" is the model's estimate from the plan's Where and the baseline, not from the abstracts. A replay of the obesity clone with Where = "New South Wales, Australia" named only Australian bodies, but put three federal matters under the state parliament, and the clone's baseline was England's. No real non-UK task has been run (`12L-profile-loop.md` § Feasibility check, round 4).

1. The spec changes are not applied (D22).
2. The owner's stage decisions for the three loops (R25), the tints (D23)
   and the count of marks on a split list.
3. The deadline rule and the answer "also options that need national
   action" have no replay case (9L).
4. M11 has no check-set read (only two clones hold who-can-act statements).
5. One run per replay; the model varies between runs (in 12L r0 → r1 the
   caregiving who-decides body changed from "the relevant local authority"
   to the Department of Health and Social Care on every option, with no
   prompt change to that rule).
6. The live refugees plan did not ask who can act on this run (the
   replays and the first live attempt did); the label was reached through
   a plan edit and a rebuild.
7. The driver's `pipeline` reused stale run ids from the previous state
   file until the state was reset; the first attempt polled a run that did
   not exist. Recorded as a knowledge candidate.
8. The live check did not run "Add an option" and did not run the chat.

### Knowledge candidates (amendment 2)

- Gating an index snapshot in a second worktree lets the next phase build
  while the gate runs; `git write-tree` + `git commit-tree` + `git
  update-ref` make the commit from the gated tree. `pnpm` refuses a
  symlinked `node_modules` without a TTY (`CI=true` and a real install).
- A subagent's targeted pytest and the gate on the same test database
  deadlock; give each agent its own `*_test` database
  (`make reset-test-db TEST_DATABASE_URL=…`).
- The drive script's `put_state` merges: a new `create` on a slug keeps the
  old run ids, and `pipeline` then polls a run that does not exist (404,
  for ever). Delete the slug's state before a new live run.
- JSONB sorts object keys: an ordered set of lines must be ordered by the
  reader, never by the writer.
- A model that is told the body that "usually" decides matches names; ask
  it about powers and it reasons about powers ("a name is not a reason").
- A relative mark on a list split in two kinds of action marks two thirds of
  the list; "most of the list" has no centre there.
- A prompt that names a law from its own knowledge does so only when it
  has no rule against it; "no Act, regulation or year unless the data holds
  the name" removed all three cases in one round.
- A frontend agent given exact words and told to add no style ships
  structure the lead can polish in one pass; the label beside a heading
  needs a phone-width check before the words are fixed.
- The planning prompt's five-kind sort needed one rule for a sentence that
  is both an aim and a boundary ("prevention alongside existing duties").

## Amendment 3 (build 2026-09-30)

Rulings R54–R75 are in [contract.md](contract.md) § Amendment 3; the design
in [amendment-3-final.md](amendment-3-final.md) ("final 3"); the phases 15.0
to 23 and the seams S21–S28 in [plan.md](plan.md) § Amendment 3. Steps 5 and
6 only; the review stack runs in a fresh conversation. Every figure below
was read back from a saved file or a database query, named beside it.

Rounds 2–5 of loop 12L (`evidence/rounds/12L-profile-loop.md`) were built
before this amendment and are not part of it.

### Commands run (the gates)

The gate of each phase ran on a **snapshot of the git index** in the second
worktree (`../policy_atlas-gate`, the `gate.sh` script in the session
scratchpad), so that the next phase could be built while the gate ran; a
commit was made only from an index whose tree equalled the gated tree. The
first build-open `make verify`, run on the working tree, went red on two
alembic-driven tests (`test_ops_remove_scoping_tasks`,
`test_rename_044_sweep`: "column population does not exist") because the
Phase 16 agent's new revision file appeared in the tree mid-run; the
baseline was rerun on the untouched HEAD (`9b301112`) in the gate worktree
and is the figure below.

| Gate | Result | Notes |
|---|---:|---|
| `make verify` (Phase 15.0, build-open baseline, HEAD `9b301112` in the gate worktree) | pass | backend 3403 passed (887 s); infra 46; okf 157 concepts; prompt-guard unchanged; drift-check OK; frontend 87 files, 853 tests (`gate-15.0-baseline.log`) |
| Phase 15 (ADR, docs only) | — | `make okf-validate` only: the tree is the gated baseline plus one markdown file (a flagged deviation from the plan's `verify-fast`) |
| `make verify` (Phase 16, the schema) | pass | backend 3405 passed (1118 s); infra 46; prompt-guard unchanged; drift-check OK; frontend 853 (`gate-16.log`) |
| `make verify-fast` · `prompt-guard` · `drift-check` (16R round 0) | pass | backend 3410 (1227 s); prompt-guard 26 unchanged (after the re-pin); drift OK (`gate-16R.log`) |
| `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` (16W) | pass, in two runs | backend 3410 (1133 s); prompt-guard 30 unchanged (`gate-16W.log`); the first run's `drift-check` failed because the staged generated OpenAPI files already carried Phase 17's `year` (regenerated by the Phase 17 worker in the shared working tree before they were staged); the files were regenerated from the 16W snapshot in the gate worktree and re-staged, and `drift-check` · `prompt-guard` · `frontend-verify` re-ran green on that tree (frontend 853; `gate-16Wb.log`); the backend tree was identical between the two runs |
| `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` (17) | pass | backend 3412 (1051 s); prompt-guard 30 unchanged; drift OK; frontend 855 (`gate-17.log`) |
| `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` (18 + 16R rounds, one tree) | pass | backend 3431 (939 s); prompt-guard 30 unchanged; drift OK; frontend 860 (`gate-18.log`). Phase 18 and the 16R rounds are disjoint file sets gated on one tree and committed as two commits (the method of amendment 2) |
| `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` (19) | pass | backend 3436 (913 s); prompt-guard 30 unchanged; drift OK; frontend 860 (`gate-19.log`) |
| `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` (20) | pass, in three runs | backend 3452 (1369 s); prompt-guard 31 unchanged; drift OK; frontend 861 (`gate-20.log`). The first run was killed by the background limit at 40 min (the machine carried the replays and the workers' suites); the second stopped before starting because a worker had staged a deletion (`test_strip_place.py`) after the snapshot; the index was restored to the snapshot and the third run passed on the same tree |
| `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` (21 snapshot, first try) | **fail**, 1 test | 3458 passed, 1 failed: `test_place_removed_is_recorded_empty_when_the_walk_opens` — the Phase 21 snapshot had swept in the 18P worker's edit of that test while the 18P code was not in the snapshot (`gate-21.log`). The 21 and 22 snapshot trees were rebuilt with that one file at its committed version |
| `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` (21 + 22a + 22c + 22b, one tree) | pass, in two runs | backend 3459 (995 s); prompt-guard 31 unchanged; drift OK; frontend 875 (`gate-22.log`). The first run hung 31 minutes at 0 % CPU in `tests/runtime/test_option_search.py` (a thread-join timing test three workers also saw stall under load); killed and re-run on the same tree, green. Phases 21, 22a+22c and 22b are committed from their own snapshot trees (the backend of all three is identical; the frontend of each is a subset of the gated tree) |
| `make verify-fast` · `prompt-guard` · `drift-check` (18P + 20L, one tree) | pass, in two runs | backend 3461 (957 s); prompt-guard 31 unchanged; drift OK (`gate-20L.log`). The first run failed on one runtime test (`test_the_longlist_and_targeted_screens_carry_the_criteria_without_where`) that pinned the criteria without the plan's Where (`gate-20L-first.log`); the test was updated to the round-1 rule (Where once, inside the rule sentence) and both snapshot trees rebuilt and re-gated. 18P and 20L are disjoint file sets gated on one tree and committed as two commits; the hash list of each snapshot was regenerated from that snapshot (`pin.sh`) |
| `make verify` (Phase 23, step-6 exit, the final backend tree) | **pass** | backend 3461 passed (1035 s); infra 46; okf 157 concepts; prompt-guard 31 unchanged; drift-check OK; frontend 875 (`gate-23.log`); exit 0. Run on the snapshot `T23` (the coverage-key sweep included). A first run of this gate on the tree before the sweep was stopped and superseded (`gate-23-superseded.log`) |
| `frontend-verify` · `prompt-guard` · `drift-check` (Phase 23, the final tree `T23b`) | pass | the only difference from `T23` is two frontend files (the card's stacked profile table at 390 px and the repeated-place filter, after the browser check); `git diff T23 T23b -- backend` is empty, so the backend result above stands for this tree; frontend 875 (`gate-23b.log`). The commit that adds this section is `T23b` plus this file and `docs/deferred.md` (docs only) |

### Commits on `task/046-longlist-refinement` (local, not pushed)

| Commit | Phase |
|---|---|
| `8a0289f6` | 15 — ADR 0040 § Amendment 3 (decisions 16–21, the rollback) |
| `4e34cae5` | 16 — the revision `f1b6d3a8c2e5`, the column readers, the facet key and its data migration |
| `98409067` | 16R round 0 — `extract_interventions_v3`, the wire, `CoverageMember`, the hash guard's extra-files list |
| `7f3ba826` | 16W — the word swap `population` → `unit` (finding records, payload keys, prompt words, hash guard) |
| `4b2dff29` | 17 — the documents (S25) |
| `f9dc7f3f` | 18 — where tried in two levels from `study_country`; the matcher, groups and OECD rule removed |
| `cf956074` | 16R rounds 1–3 — round 2's text kept, hash re-pinned |
| `62459a86` | 19 — outcome counts over any role, Examples, `folded`; the where-tried spelling made deterministic |
| `48140b8a` | 20 — the folding calls (`folding_v1` round 0) |
| `1e62944c` | 21 — the read models trimmed; the dossier's records route |
| `81a4f850` | 22a + 22c — the card's structure; the facets, the grid |
| `7cbd7a23` | 22b — the card's design and final words |
| `9d83f5dc` | 18P — the place rule in words; the strip stays (M4) |
| `bb74bfa1` | 20L — the folding prompts refined (`folding_v5`) |
| the commit that adds this section | 23 — the coverage keys `populations`/`population_tags`/`tried_on[].population` → `units`/`unit_tags`/`unit` (the last `population` in product code), this file, `docs/deferred.md` |

### The revision and the stored-task reference (R71; plan review 9)

Revision `f1b6d3a8c2e5` (revises `e9a4c1f7b3d2`). On the dev database:
`replay.py check-stored` read "unchanged: 7 tasks x 19 tables" before
`alembic upgrade head`; after it, exactly 7 tables differed — the
`intervention_profile_record` of each stored task (the same row counts, a
new md5: the two added columns) — and nothing else; the reference was saved
again (`check-stored --save`, `replay-out/check-stored.json`, 2026-09-30
16:46) and reads "unchanged" since.

### The 16W word swap, read as words only (R73, R75; the 038 ruling)

The diff of the nine prompt-bearing files (`finding_references.py`,
`iof_records.py`, `icf_records.py`, `iof_prompt.py`, `icf_prompt.py`,
`longlist_cluster_prompt.py`, `synthesis_prompts_v6.py`,
`grounding_judge.py`, `task_agent_prompt.py`) was read line by line before
the commit: every changed line is the word `population` → `unit`
(`POPULATION_DESC` → `UNIT_DESC`, the field lists, the few-shot examples'
keyword, the facet name in the Task Agent prompt), plus one wider
definition (`UNIT_DESC`: "Who or what the intervention was delivered to
(people, organisations, sites or things), exactly as the document describes
them, or null if not reported") and one prose sentence in the assignment
prompt ("The population a study enrolled" → "Whom a study enrolled"). No
rule, example or structure changed; no replay. The finding records keep
their schema and prompt versions (Q24), so no document is extracted again.
`task_agent_prompt.py` was added to 16W's list at build time: it offered the
model the facet `population`, which the API contract refused after Phase 16
(the Phase 16 agent's finding). The hash guard's extra-files list now holds
`interventions_records.py`, `iof_records.py`, `icf_records.py`,
`finding_references.py` and `grounding_judge.py` (30 hashes).

### The refine loops (R69; rubric box 63)

**16R — the record prompt (`extract_interventions_v3`)**: round record
`evidence/rounds/16R-record-prompt-loop.md` (figures per round and list
from `16R-<round>-<slug>.json`; the hand-read files `16R-<round>-read-<slug>.txt`
hold document abstracts and are gitignored). Four rounds (0–3) on the
tuning set, two readers per round over the full files, the lead
adjudicating and writing each change. The stop measure (every
`programme_name` a proper name the abstract gives for this intervention;
every `study_country` the country of the stated place) was **not met at
any round**; round 3 was worse than round 2 on the country and "not
stated" checks (a "never a place cited for another study" rule made the
model drop documents' own hospital and region names), so **the loop ended
at round 3 and round 2's text is the one shipped** (restored in the
16R commit, hash re-pinned). Residual fault rates per list are in the
round record's § Result, reported to the owner (R25). Rubric boxes 57
and 69 are therefore **not met at their "all" threshold**; the figures
are reported. The check-set read (NEET, heat pumps, cohesion) and M1/M2
on the tuning set are below.

### The new read route (Phase 21, S26; marked for `/security-review`, plan review 13)

`GET /api/v1/tasks/{task_id}/sources/{source_id}/records?option_id=` (router
`api/routers/read_models.py`, beside the dossier route; repository
`source_records_out`). Scoping as built: the first line is the same
`_readable(conn, task_id, user)` the sibling dossier route calls
(`readable_or_public_task`): an unreadable, archived or absent task, or an
anonymous call on a private task, gets the byte-identical `404 not_found`;
an owner, a same-org colleague or an admin can read it, and anyone once
the task is public (it joins `_CONDITIONALLY_PUBLIC_GETS` in the
conformance tests). After that check every query is keyed by `task_id`:
an `option_id` not of this task, a `source_id` that is not this task's
snapshot, or a DOI twin outside this task's members, gives an empty list
(200), never another task's data. One design choice for the reviewer: an
unknown or foreign `source_id` on a readable task returns 200 with an
empty list where the sibling route returns 404. Tests:
`tests/api/test_source_records_routes.py` (6: records one per option in
their own words with a DOI twin; the option filter; no record → empty;
unreadable/anonymous 404, public reads; another owner's option or document
id gives nothing and their task 404; the dossier route and an Evidence
search task unchanged).

### Deviations, flagged (amendment 3)

- **Q26's rewrite reaches the group-id prefix** (Phase 16): the grouping
  facet key is also the prefix of every stored group id (`population:g01`),
  which `synthesis_tools.py` and `synthesise.py` check against the key and
  which annotations and synthesis blocks cite by id. The data migration
  therefore rewrites the key AND the prefix in `grouping_result.groups`,
  `counts`, `flags` and `grouping_provenance`, `annotation.payload`
  (grouping themes' `referenced_ids`, pattern claims' `group_id`) and
  `synthesis_result.blocks[].group_ids`, reversibly; resolved within Q26's
  own rule ("every stored place of the facet key, so no reader needs an
  alias"). Not rewritten: run history with no reader
  (`synthesis_result.synthesis_provenance`, `counts.groups_unsectioned_by_facet`,
  `event_log`), listed as a known limit.
- **The old revision `c7e2a9f4b1d8` was edited** (Phase 16): it imported
  the live `FINDING_REFERENCE_UNION_SQL`, so a fresh `upgrade head` would
  have created the `unit` view before the column existed; its
  three-branch SQL is now frozen inside it (no behaviour change for a
  database already past it). The new revision imports the constant too and
  carries the same note for the next view change.
- **`task_agent_prompt.py` joined the 16W word swap** at build time (the
  Task Agent offered the facet `population`, which the API contract refused
  after Phase 16).
- **The folding wire changed at 20L round 2** (kinds first, then indexes)
  because the ceiling in words did not hold on the mini model; the stored
  shape and the read side are unchanged.
- **The 16R loop ends at round 3 without meeting its stop measure**; round
  2's text is kept (§ The refine loops).
- **`OptionOut.where_label` and `LonglistOut.depth_label`**: the longlist
  header still reads `depth_label`, so it stays on `LonglistOut` (R61 takes
  the chip off the card only); `where_label` left `OptionOut` in Phase 21.
- **The Phase 15 ADR commit** was gated on `okf-validate` only (docs-only
  change on the gated baseline tree).
- **The 16W and Phase 17 generated files**: see the gate table (a shared
  working tree regenerated them ahead of the snapshot; fixed by
  regenerating from the snapshot).

### The card, the facets and the grid (Phases 22a, 22c, 22b)

Structure by two workers from final 3 § 2.5–2.9 (22a: the card; 22c: the
facets, the grid at `CELL_LIMIT` 4, the dossier link), design and final
words by the lead (22b, with the design system's rules: the Sixteen Floor,
Tint-Not-Fill, the Word Beside the Colour). The lead's words: section
titles "What it is" · "What it would take" (label "Policy Atlas's
estimate") · "Evidence" · "Checks"; the lever line "Lever: Subsidise, with
Regulate and Provide a service." with the reason under it; the collapsed
row's "Middle" as a plain navy word beside the tinted level words; the
authority word beside "Who decides" as a tinted word (green tint = within
your power, yellow tint = needs action by …, grey = unclear) followed by
the line's own sentence — the constrain reason stays off the card ("just
enough text"; it is served and can return); the outcomes table's "serves"
mark as a small blue label; "Built-in checks: all pass." as the one line.
**Open for the owner (final 3 § 7.1, item 1):** the tints of the level
words (aqua / violet), of "Middle" (none) and of the authority word
(green / yellow / grey), on the built screen. Two judgement calls of the
22a worker stand: the checks list treats the ids `relevant`, `distinct`,
`in_scope` as the built-ins and every other judgement as the user's
boundary (a consideration never reaches `judgements`: Phase 13), and a
`tried_on` with several kinds shows only through the read model (the
fixture keeps one).

**18P — the place rule in words (R74)**: round record
`evidence/rounds/18P-place-rule-loop.md`. Three rounds (0–2) on the seven
clones with the strip removed and the rule in words: constrain never
excluded for place; the screen never failed; on six lists no flagged
rejection was place-based; on refugees the place-based rejections went
10 → 6 → 1 clear (+2 unclear) in 175 documents. **M4 did not reach zero,
so the list stays** (`strip_place`, its name tables and `names_place`
are as at Phase 18; the 18P code deletion was reverted; `where_codes` and
`home` went in Phase 18 regardless). Kept: the rule in words in every
prompt that read the stripped text, and the screen's intent and first
criterion naming the user's place from the plan's own Where field beside
the stripped unit. Rubric box 71: the deletion part is **not done**, by
the box's own rule; the wording part is done; M4 on the live runs is
below. **Deviation flagged:** naming the plan's Where in the screen text
departs from S7's "never Where in the screen input" (that rule described
the strip); the Where enters once per text, inside the rule sentence, and
the intent tests pin it so. The owner decides at review whether one
place-based rejection in 175 is an acceptable price for the list (R25).

**20L — the folding prompts**: round record `evidence/rounds/20L-folding-loop.md`.
Five rounds (0–4): a ceiling in words did not bind the mini model (53–125
kinds on the long lists), nor the indexed wire's description; the ceiling
became a schema constraint (`max_length=12`, round 3) and holds; round 4
fixed concatenated labels and generic catch-alls and made every measure
OF a plan outcome fold into it (the plan's outcome text is used on all
seven lists). The stop measure ("no two kinds name the same kind") is
**not met** in the tail on obesity, NEET and heat pumps, and cohesion's
Tried on collapsed into one catch-all kind under the cap (160 distinct
words). `folding_v5` ships; the residual is on the record for the owner
and two follow-ups are in `docs/deferred.md`.

### The OpenAPI diff (rubric box 65; against the baseline `9b301112`)

Computed from `frontend/openapi.json` at the two trees. **Removed:**
`VariantOut`; `EvidenceProfileOut.outcomes`, `.populations`, `.settings`;
`IofFindingOut.population`, `IcfFindingOut.population`; `LonglistOut.where_label`;
`OptionDocumentOut.where_tried_group`; `OptionOut.depth_label`,
`.runner_up_lever_type`, `.transferability`, `.variants`, `.where_label`;
`OptionSummaryOut.runner_up_lever_type`; `TriedOnOut.population`;
`WhereTriedOut.where/comparable/other/unknown`. **Added:** the schemas
`ExampleOut`, `MeasureKindOut`, `OutcomeKindOut`, `WherePlaceOut`,
`OptionRecordOut`, `SourceRecordsOut`; `EvidenceProfileOut.measures`;
`IofFindingOut.unit`, `IcfFindingOut.unit`; `OptionDocumentOut.place`,
`.year`; `OptionOut.examples`; `OutcomeCountOut.evaluated`;
`OutcomeCountsOut.other`; `TriedOnOut.kind`; `WhereTriedOut.top/documents/
places/countries`; the path `GET /api/v1/tasks/{task_id}/sources/{source_id}/records`.
Kept on purpose: `LonglistOut.depth_label` (the header). Every removal and
addition is in final 3 § 3's public-interface row, plus the route's read
models, and `where_label` stays nowhere else.

### Diff summary (amendment 3, against `9b301112`)

106 files, +6999 / −1887 (backend `src` 38 files +1853 / −616; frontend
`src` 18 files +1543 / −691; the rest tests, the revision, generated
files, docs). Backend: one alembic revision (`f1b6d3a8c2e5`) and the old
`c7e2a9f4b1d8` freezing its view SQL; `core/schema.py` (columns, view,
`GROUPING_FACETS`); the record wire, writer, fingerprint and prompt
(`extract_interventions_v3`); the finding wires and their shared
description; the payload keys and prompt words of the 16W swap;
`where_tried.py` reduced to the two-level rule plus the strip;
`coverage.py` (where tried, examples, folded, outcome counts, the folded
kinds); `longlist.py` (membership read, the removed matcher calls);
`option_profile.py` (the folding calls, the recount, the maps);
`longlist_backend.py` (`fold`); the new `folding_prompt.py`; `constrain.py`
(the merge recompute with the maps); `repository.py` (the documents, the
records route, the trimmed fields); `read_models.py` and the router; the
five prompts carrying the place rule; `longlist_intent.py` (the rule
sentence); the hash guard's extra-files list. Frontend: the card, the
list's facets and grid, the presentation helpers, the dossier slot and
hook, the findings view label, fixtures and the generated types.
Evidence search components touched (the reuse rule): the extract wires
and prompts (the record fields and the word swap), `group.py` and the
synthesis payload keys (the facet key and column), the source dossier
(the slot) — each an edit of the shared component, no mirror.

### Existing tests edited (rubric box 19; amendment 3)

Added: `tests/core/test_migration_046_a3.py`, `tests/api/test_source_records_routes.py`.
Edited (46 files): the core migration tests (`test_effect_direction_migration`,
`test_icf_migration`, `test_migration_045_slice`, `test_migration_046_tags`,
`test_synthesis_refinement_migration`, `test_tracing`: the `unit` column
and facet on rows inserted at head; legacy inserts keep `population`);
the extract tests (`test_extract`, `test_extract_contract`,
`test_extract_interventions`, `test_extraction_backend`,
`test_finding_references`, `test_icf_rules`, `test_interventions_tag_rules`,
`test_interventions_tagging`, `test_quote_verify`, `test_relevance_injection`:
the wire and record names, the two new fields, the versions, the
re-pinned fingerprints); `group/test_group`, `test_group_contract`, the
synthesis tests (`test_synthesis_tools`, `test_synthesise`,
`test_synthesise_pure`: the column and key); `api/test_longlist_routes`
(the documents one per DOI, `year`, `place`, the two-level where tried,
`examples`, kinds, the trimmed fields), `test_read_models`,
`test_api_conformance` (the new public GET); `options_scoping/test_constrain`
(the merge with maps; `names_place` in place of `countries_in`),
`test_longlist` (payload keys, `study_country`, `examples`),
`test_longlist_coverage_046` ("described counts for nothing" replaced by
"any role counts, evaluated separate"; the where-tried places; examples;
folded; the kinds), `test_longlist_intent` (the rule sentence; Where
named once per text), `test_option_profile` (the versions, the folding
tests), `test_strip_place` (the sub-national group test retired),
`test_where_tried` (rewritten: the four-group tests retired, the two-level
rule pinned); the runtime tests holding the facet literal
(`test_agent`, `test_injection_fixtures`, `test_router_compile`,
`test_runner`, `test_steering`, `test_steering_events`,
`test_steering_history`, `test_task_plan`); the frontend tests
(`OptionCard.test` incl. Box 28's authority tests moved to the "Who
decides" row, `LonglistView.test`, `LonglistGrid.test`,
`longlistPresentation.test`, `SourcesView.test`,
`ArtefactView.dossier.test`). Retired outright: none beyond the
where-tried group tests and the sub-national strip test named above.

### End-to-end command (amendment 3)

The live check drove three new tasks through the local API with the
amendment-2 driver (`evidence/pre-contract-runs/drive_live.py`, state in
`live-out/<slug>/`; the amendment-2 state moved to `live-out-2026-09-30-a2/`):

```
cd backend && uv run --env-file .env uvicorn policy_atlas.api.app:create_app --factory --port 8000
cd docs/tasks/046-longlist-refinement/evidence/pre-contract-runs
python3 drive_live.py create obesity && python3 drive_live.py pipeline obesity      # likewise caregiving, refugees
cd backend && P=../docs/tasks/046-longlist-refinement/evidence/pre-contract-runs
uv run --env-file .env python $P/live_metrics.py <task_id>                            # M7–M9
uv run --env-file .env python $P/read_records_a3.py live-<slug> --out $P/../rounds --label live
uv run --env-file .env python $P/read_folds_a3.py  live-<slug> --out $P/../rounds --label live
uv run --env-file .env python $P/analyse_constrain.py live-a3-<slug>; …/analyse_longlist.py live-a3-<slug>
```

The replays (loops 16R, 18P, 20L): `replay.py stage <stage> <slug> --fresh --label <round>`
on the seven clones, with `run_18p.sh` for the whole chain; every figure
in the round records is read from the saved `replay-out/` and
`evidence/rounds/*.json` files.

### Live check (Phase 23): three rapid runs on new tasks

Driven 2026-10-01 00:5x–01:3x through the local API on the final code
(commits through `bb74bfa1`), unattended, with `drive_live.py`. Tasks (dev
database): obesity `1df1ca78`, caregiving `52345ffc`, refugees `7f3abe38`.
Every figure read from `live_metrics.py`, `live_cost.py` (Langfuse),
`read_profile.py` (`23-live-profile-<slug>.json`), `read_records_a3.py`
and `read_folds_a3.py` (`16R-live-live-<slug>.json`, `20L-live-live-<slug>.json`),
`analyse_constrain.py` / `analyse_longlist.py` (`replay-out/live-a3-<slug>/`).

| Measure | Obesity | Caregiving | Refugees | Result |
|---|---|---|---|---|
| M1 options per run (13 to 25) | 25 | 25 | 25 | **pass** |
| M2 rows that are one named trial (the option names read by the lead) | none | none | none | **pass** |
| M4 exclusions because of place | 0 (0 exclusions) | 0 (1 exclusion: "Family-integrated neonatal care" breaks the user's boundary "Only options delivered through existing health visiting, midwifery or family hub services") | 0 (0 exclusions) | **pass** (the strip is in place; the rule in words beside it) |
| M5 setting labels that are a country, region or body | none (school, home, clinic, shop, neighbourhood, public venue, public space, community venue) | none (clinic, family hub, home, hospital, workplace) | none (workplace, classroom, housing service, support service, employment service, home, business service, community, health service, shelter) | **pass** |
| M6's replacement: options whose Tried on shows a kind beyond the target unit | 25 of 25 | 25 of 25 | 18 of 25 | reported |
| M10 every option has a sentence on every line | 25 of 25 | 25 of 25 | 25 of 25 | reported |
| M11 the authority label | no consideration; no label | no consideration; no label | 25 labelled: 22 within your power, 1 needs action by, 2 unclear | reported |
| M12 setting labels per list | 8 | 5 | 10 | reported |
| M14 a nudge below a clinical service on delivery complexity | campaigns, labelling, advertising rules `less`; weight-management services, primary-care identification `more` | digital messaging `less`; home visiting, video-feedback, depression treatment pathways `more` | rights courses, wage subsidies `less`; case management, Housing First `more` | reported |
| Kinds per folding facet (Tried on / Measures) | 12 / 12 | 12 / 12 | 12 / 6 | reported (≤ 12) |
| The plan's text used as a kind (target unit / outcomes) | yes / no | yes / 3 outcomes | no / 3 outcomes | reported |
| Options with examples (examples in all) | 16 of 25 (49) | 16 of 25 (39) | 7 of 25 (16) | reported |
| Records with a `programme_name` (distinct names) | 125 of 586 (105) | 122 of 606 (106) | 30 of 226 (26) | reported |
| Records by `study_country` top level: not stated / United Kingdom / multiple countries / other / next | 208 / 177 / 24 / 18 / United States 31, Vietnam 29, Sweden 17 | 273 / 82 / 20 / 12 / United States 67, Austria 34, Japan 23 | 48 / 18 / 10 / 2 / Switzerland 21, Germany 21, United States 20, France 15 | reported |
| Where tried on the cards: options with an entry; top levels (documents summed over options) | 25; not stated 66, United Kingdom 53, United States 16, multiple countries 12 | 25; not stated 77, United Kingdom 27, United States 20, Austria 19 | 18; not stated 22, Germany 10, United States 10, Switzerland 8 | reported |
| Unit tags on target / adjacent / other | 194 / 153 / 239 | 286 / 159 / 161 | 44 / 86 / 96 | reported |

| Measure | Obesity (amendment 2 → now) | Caregiving | Refugees |
|---|---|---|---|
| M7 cost per task (Langfuse, USD) | 5.56 → 6.19 | 5.64 → 6.13 | 9.20 (two walks) → 4.84 |
| M7 of which `option_profile` (now with the two folding calls) | 1.60 → 1.78 | 1.62 → 1.81 | 3.24 (two walks) → 1.76 |
| M7 of which screen | 1.22 → 1.38 | 0.95 → 1.07 | 2.03 → 0.82 |
| M8 longlist walk, seconds | 638 → 618 | 634 → 735 | 601 → 559 |
| M8 `option_profile` step, seconds | 62 → 50 | 56 → 45 | 72 → 70 |
| M8 `extract_interventions` step, seconds (v3, three new fields) | — → 107 | — → 131 | — → 58 |
| M8 baseline, seconds | 212 → 243 | 242 → 228 | 197 → 213 |
| M9 pool (documents) | 327 → 344 | 245 → 255 | 223 → 215 |
| M9 relevant in the longlist scope | 181 → 184 | 174 → 171 | 77 → 78 |
| M9 screen rows per document, longlist scope | 1.00 (0 with more than one) | 1.00 | 1.00 |
| M9 documents with no screen row | 0 | 0 | 0 |
| M9 duplicate titles | 20 → 30 | 27 → 19 | 16 → 24 |

The 18C "not stated" read, the `programme_name` and `study_country`
reads and the M6 replacement's hand read on these lists are below (§ The
live records, read by hand); the browser check is in § Browser check.

### The live records, read by hand (Phase 23; one reader over the live read files, the lead adjudicating)

**18C — "not stated" on the live lists** (rubric box 53; `18C-not-stated.md`
§ The live lists holds the same counts): obesity 208 not-stated records
(55 documents), of which **7 documents / 25 records** name the place of the
study (UK, Cambridgeshire, Cyprus, Baden-Württemberg, Scotland…), 5
documents borderline (a cost threshold, a guideline name, cited examples);
caregiving 273 (71 documents), **14 documents / 56 records** name the
place (Boston City Hospital, Arizona, King's Mill Hospital, Darent Valley
Hospital, Sherwood Forest Hospitals, New South Wales, Sweden…), 4
borderline; refugees 48 (16 documents), **1 document / 2 records**
(Australia, in the title). Whether a named hospital counts as "names the
place" decides 3 caregiving documents (17 records). The 16R loop ended
with round 2's text (§ The refine loops), so these counts are reported,
not fixed.

**`programme_name` on the live lists** (box 57): obesity ~34 clear faults
of 125 (grantee organisations, surveys, a nutrient-profiling model, funds
and parent schemes, two names from the title only); caregiving ~25 of 122
plus 5 title-only (providers, toolkits, a trial name, generic team names);
refugees 6 of 30 (providers, a cohort study, a parent scheme on the wrong
record). The same families of fault as the tuning set; no invented name
on refugees; a handful of spelling variants of one programme on each list.

**`study_country` on the live lists** (box 69): wrong "multiple
countries" obesity 9 (a fund as the place ×5; "Singapore"; "14
municipalities"; a mixed form), caregiving 6 ("Fake County" ×3; a trials
registry ×2; "the canton"), refugees 3 ("Dutch" ×3); countries with no
supporting geography obesity 8 ("Georgia" the MP's name ×7), caregiving 4
("daycare" ×3); no short form, no UK nation as a country, one spelling per
country on every list.

**`unit`**: organisations, sites and things present on every list
(schools, municipalities, supermarkets, foods; child care providers,
health systems; employers, resettlement agencies, apartments); values that
are not a unit: obesity 12, caregiving ~14, refugees 6 (outcomes, topics,
a case child's name, "members").

**M6's replacement** (box 47): every option with Tried on shows a kind
beyond the plan's target unit (obesity 25 of 25; caregiving 25 of 25;
refugees 18 of 25, 7 options with no Tried on). The reader's caveats stand
as reported: the target unit's kind acts as a catch-all for children of
any age on obesity; overlapping kinds remain ("families" / "children and
families" / "parents"; "refugees" / "status holders" / "displaced
persons"); "body mass index" and "BMI" are two Measures kinds on obesity;
a few members sit under the wrong kind ("local authorities" under
"schools"). The same tail as the 20L loop reported.

**M4 on the live lists** (box 71): no option name and no kind label on any
list carries a place name; places appear only inside member words
("Chinese primary-school-aged children", "refugees from Ukraine"). With
the exclusions (none for place) this is the live M4: **pass**.


### Public safety

Nothing committed names a real person beyond the public bodies and
published programmes the records already carried; the hand-read files
holding document abstracts (`16R-*-read-*.txt`, `20L-*-read-*.txt`) and
every replay output live under the gitignored `evidence/` tree; the
driver's token (`evidence/token.txt`) is gitignored; no key, secret or IP
allowlist is in the diff; the migration carries no account id.

### Rubric status (amendment 3 boxes 47–71; the review conversation ticks them)

| Box | State at step 6 |
|---|---|
| 47 Tried on | built (Phase 20, 20L); M6's replacement reported (25 / 25 / 18 options show a kind beyond the target unit); the stop measure's tail not met (§ The refine loops) |
| 48 Measures and the outcomes table | built (Phases 19, 20, 22a); tests pin A4 |
| 49 Counts over any role | built (Phase 19; the old test replaced with a written reason) |
| 50 The list's facets | built (Phases 18, 20, 22c): labels only, filters, the multiple-countries match, fold at 8, no Measures facet |
| 51 The authority label's rule | unchanged; Box 28's tests moved to the "Who decides" row (listed in § Existing tests edited) |
| 52 Where tried | built (Phase 18); no "comparable"/"OECD"; `where_codes`, `home` gone; the strip's name tables stay (R74 outcome) |
| 53 The "not stated" check | reported (`18C-not-stated.md`; the live read below) |
| 54 Grid | `CELL_LIMIT` 4 (Phase 22c) |
| 55 Header | no boxes, no depth chip; the abstracts note (Phase 22a) |
| 56 Lever line | built (Phase 22a/22b) |
| 57 Examples from `programme_name` | built (16R, Phase 19); **the 16R read's "all" threshold not met** (faults 13–32 % of names on the tuning set; the live read below) |
| 58 Collapsed row | seven cells with "Middle" (Phase 22a) |
| 59 Checks | built (Phase 22a) |
| 60 Documents | built (Phase 17, 18) |
| 61 The dossier from the card | built (Phase 21, 22c); the browser check |
| 62 Layout and critique items | built (Phase 22a/22b); the 16 px classes pinned |
| 63 Every prompt through a loop | 16R (4 rounds, round 2 kept), 18P (3 rounds, the strip kept), 20L (5 rounds, v5 kept); 16W a word swap; the extra-files list in the hash guard (31 hashes) |
| 64 Gates | the gate table: full `make verify` at 15.0, 16 and 23; `prompt-guard` where a prompt changed; `openapi-sync`/`drift-check`/`frontend-verify` where the API or the frontend changed; `/security-review` on the route is for the review conversation (the route's scoping is recorded above) |
| 65 The contract's lines | the OpenAPI diff above; M1, M2, M4 on the live runs pass; records with a `programme_name` per list reported; rounds 2–5 of 12L named as built before this amendment |
| 66 Spec changes | proposals only (`spec-changes-proposed.md`, the owner decides the wording; nothing under `docs/specs/` changed) |
| 67 Migration | built (Phase 16; the data migration reaches the group-id prefix, § Deviations); production downgrade path recorded; the stored-task reference saved again |
| 68 The authority label beside "Who decides" | built (Phase 22a/22b) |
| 69 `study_country` | built (16R); **the "no wrong country" threshold not met** (the round record and the live read) |
| 70 `unit` throughout | built (Phases 16, 16R, 16W); no `population` in product code, wires, prompts or read models (the coverage keys `populations`/`population_tags` are gone with Phase 20's read-model change — a grep over `backend/src` and `frontend/src` finds the word only in English prose) |
| 71 The place rule in words | the wording part built (18P); **the deletion part not done** (M4 did not reach zero on the replays: § The refine loops); M4 on the live runs passes with the strip in place |

### Known unverified items (amendment 3)

- The owner's open items of final 3 § 7.1: the tints, the spec wording, the
  final words on the built screen, the stage decisions for loops 16R, 18P
  and 20L (this file reports them).
- `study_country` and `programme_name` rest on the mini model's reading;
  the residual fault rates are in the round records; a real non-UK task
  is still not run.
- The folding calls' tail (duplicate meanings; a catch-all on a long list).
- The replay chain's `suggest --fresh` artefact (`docs/deferred.md`).
- Run history not rewritten by the data migration (`synthesis_provenance`,
  `counts.groups_unsectioned_by_facet`, `event_log`).
- The `test_option_search.py` thread-join test stalls under load (seen four
  times in this build, never in a quiet run).

### Review handoff (amendment 3; step-7/8 inputs)

**Adjudication items for the review conversation**

1. R74's outcome: the strip stays because M4 did not reach zero (one
   place-based rejection in 175 on the refugees replay after three
   rounds). The reviewer checks the round record and may put the
   deletion to the owner as a decision with that figure.
2. Rubric boxes 57 and 69 (`programme_name`, `study_country`) and the 20L
   stop measure are **not met at their "all" thresholds**; the residual
   rates are on the record. The reviewer decides whether the card may ship
   with them (the card shows at most five examples per option; a stray
   provider's name is visible) or whether a stronger record model is a
   precondition.
3. Q26's reach: the data migration rewrites the group-id prefix in
   annotations and synthesis blocks too (§ Deviations). The reviewer
   confirms the production rollback path (`alembic downgrade -1` writes
   every place back; tests up and down).
4. The old revision `c7e2a9f4b1d8` was edited to freeze its view SQL (a
   merged migration edited — necessary for a fresh `upgrade head`; no
   behaviour change on a database past it).
5. The screen text now names the plan's Where once per text (18P), against
   S7's "never Where in the screen input".
6. The 22b judgement calls: the constrain reason off the "Who decides"
   row; the tints; "Built-in checks: all pass."; the "serves" label.
7. `/security-review` on `GET /tasks/{task_id}/sources/{source_id}/records`
   (its scoping is recorded in § The new read route).

**Executor provenance (for the family flip).** Claude built everything:
the lead wrote every prompt and its rounds (16R, 18P, 20L), the 16W swap,
the 22b design pass, the ADR, the round records and this file;
`deep-reasoner` (Opus) built Phases 16 (the revision and readers), 18,
18P.0, 20 (the folding calls and parser), 21 (the route and dossier slot),
the browser check and every hand read; `fast-worker` (Sonnet) built 16R's
plumbing, 16W's tests, 17, 19, 22a, 22c, the 18P code (reverted) and the
coverage-key sweep. No Codex job in the build; Codex anchors the review.

**Diff-scoping exclusions.** `frontend/openapi.json`,
`frontend/src/api/gen/types.ts` (generated), `scripts/prompt_hashes.json`,
`docs/tasks/046-longlist-refinement/**` (this record and the amendment
documents), `docs/deferred.md`, `docs/adr/0040-*.md` (reviewed as prose,
not code). The evidence tree is gitignored.

**Live-trace pointers.** Langfuse sessions = the task ids above (obesity
`1df1ca78-5065-43a8-bb1d-63bd03fe9c1a`, caregiving
`52345ffc-523a-4820-a180-8c89ce204b4e`, refugees
`7f3abe38-768c-415d-90a9-45ee4583ad44`); the replay clones' runs are in
the dev database under the clone task ids (`replay-out/<slug>/clone.json`).

### Knowledge candidates (amendment 3)

- **A ceiling in words does not bind a mini model; a ceiling in the schema
  does.** Three rounds of "at most 12 kinds" in the prompt and in a field
  description were ignored on long lists (53–125 kinds); `max_length=12` on
  the Pydantic field (a `maxItems` constraint in the structured-output
  schema) held on the first try. Put hard limits in the schema, not the
  prose.
- **A "never X" rule about an edge case is read as "leave X out".** The
  16R round-3 line "never a place cited only for another study" made the
  model drop documents' own hospital and region names (not-stated faults
  rose from 21 to 38 on obesity, 34 to 56 on caregiving); the round was
  reverted. Prefer positive rules with worked examples to negative rules
  about exceptions.
- **The reps quote the criterion's own words back.** When the screen's
  population phrase carried "living in Greater Manchester", the mini reps
  wrote "not … in Greater Manchester" as the reason even with the rule
  beside it; naming the place as "the user's place" cut the faults from
  10 to 1 but not to 0. A place inside the unit phrase is a criterion to
  a mini screen model whatever the surrounding text says — the strip's
  job cannot be done by words alone at this model tier.
- **Under a hard cap, a mini model merges pathologically**: it joined
  several measures into one slash-separated label, fell back to the
  prompt's own generic words ("people", "sites", "things") as kinds, and
  on a list of 160 words put 149 in one kind. A cap needs a rule for how
  to merge ("name the merged kind by what its members share"; "never the
  generic words") and a guard on a catch-all.
- **A shared working tree and index-based gating.** Three snapshot
  mistakes in this build came from workers' edits landing between the
  lead's `git add` and the gate: generated OpenAPI files regenerated by a
  later phase (16W, 17), a staged deletion by a worker (20), a test file
  edited for a later phase swept into an earlier snapshot (21). The fixes:
  regenerate generated files from the snapshot in the gate worktree
  (`pin.sh` does it for the hash list), snapshot trees by explicit path
  lists, and commit from recorded tree ids (`commit-tree`) rather than
  from the live index.
- **`git commit <pathspec>` commits the working tree, not the index.**
  Splitting one gated tree into two commits must go through
  `write-tree`/`commit-tree` (or a temporary index), never
  `git commit -- paths`.
- **The replay tool's stage order matters on a built clone**: `suggest
  --fresh` before `longlist --fresh` turns the clone's earlier options into
  seeds and the longlist fills with them (35 options, 0 discovered). M1 was
  read from a replay that ran `longlist --fresh` alone.
- **The place-matching "flag" over-matches** (OECD country notes, "the
  country"); M4 on the screen is a hand read of the reps' reasons. A
  structured reason code from the screen would make it a count.
- **`test_option_search.py` stalls at 0 % CPU under load** (a thread-join
  timing test), four times in this build, never on a quiet machine; the
  gate hung 31 minutes once. Worth a timeout on that join.
- **The grouping facet key lives inside stored group ids** (`population:g01`)
  and those ids are cited by annotations and synthesis blocks; a facet
  rename is a prefix rewrite in five tables, not a one-key swap.
- **A merged alembic revision that imports a live constant** (`FINDING_REFERENCE_UNION_SQL`)
  breaks a fresh `upgrade head` the moment the constant moves on; freeze
  the SQL in the revision at the time the next revision changes it.
- **`document_where` picked a country's spelling by row order**; a test
  flipped between "United Kingdom" and "united kingdom" one run in three.
  Any "first spelling seen" rule over database rows needs a stable choice
  (the smallest spelling here).
- **On the mini model, each added rule to the record prompt moved faults
  rather than removing them** (four rounds; round 2 kept). Beyond two
  targeted rounds, a loop on a mini model is measuring noise; the next
  lever is the model tier, not the wording.

### Browser check (Phase 23; Playwright over the live dev app, desktop 1440 px and 390 px; screenshots in `evidence/live-shots/a3/`, gitignored)

Read-only (GET requests only; the scripts block anything else). Obesity
card: option "School diet-and-activity programmes with home components"
(29 documents); refugees card: "Post-status integration case management"
(authority "within your power"); Evidence search task `894321f9`.

Seen as built: the header's one grey line and Exclude; "What it is" with
the lever line "Lever: Subsidise, with Provide a service and Inform." and
its reason, Delivered through, features, Examples; "What it would take —
Policy Atlas's estimate" collapsed as seven cells (Ambition "Bigger" ·
Cost "Costlier" · Time to set up "Middle" · Time to effect "Middle" ·
Workforce "Higher" · Coordination "Higher" · Delivery complexity "More
complex") and expanded with Ambition first and, on refugees, "Who decides
| Within your power | The Combined Authority must decide to commission
the integration case management service."; "Evidence" with the outcomes
table (the three plan outcomes with "serves", Documents/Evaluated, then
the other kinds), the roles line, Where tried in two levels, "Tried on:
Children aged 4 to 11 in the most deprived fifth of areas (9 documents),
Children and adolescents (14), Schools (7), …", "Read from titles and
abstracts only", five documents with the meta line "quality · type · role
· place · year" then "Show all 29"; "Checks" with "Built-in checks: all
pass."; a document title → the Sources page's dossier with "In this
option" (intervention · setting · tried on · outcomes measured · role;
"Where" left out where the record has none); the Sources tab's dossier
with "Records", one per option; the facets with no digit in any chip,
Where tried + Tried on filtering ("11 of 25 options match"); the grid
with "+2 more" cells; no "population" on any Evidence search page.

Found and fixed before the exit (22b, this commit): the expanded profile
table stayed three columns at 390 px and cramped the sentences — it now
stacks each row below `sm`; a place that repeats its top level
("Estonia › Estonia") is no longer listed below it. Found and reported
(data, not code): the level below carries the records' geographies as
written, so a mini-model fault shows ("United Kingdom › Georgia" — an
MP's first name; "Spain › Spanish Ministry of Health"; "Multiple
countries" holding "member country", "Estonian"); three spellings of one
programme as three examples on refugees ("San Diego Newcomers Project
(SDNP)" ×3 forms) — the record prompt's "same spelling" rule did not hold;
a "serves" plan outcome with 0 documents shows (by design: a row per plan
outcome); a Measures kind that nearly repeats a plan outcome on obesity
(the 20L tail). Not checkable: the findings view label "Unit" and the
`unit` facet on an Evidence search task — the dev database holds no
finding rows (0 in both tables); the vitest covers the label and the
facet key is in the API contract tests. Observed, pre-existing: the
dossier header reads "Findings extracted · Read in full" with "Read
basis: Title and abstract" beside the card's "Read from titles and
abstracts only".


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
