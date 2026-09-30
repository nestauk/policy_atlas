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
