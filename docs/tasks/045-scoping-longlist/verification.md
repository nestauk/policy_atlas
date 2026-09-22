# Verification: 045-scoping-longlist

Evidence for the build phase (steps 5–6). Public-safe: no secrets, raw source
text, credentials or unredacted traces. Filled as each phase closes; **Review
findings** and **Rubric status** are added by the review conversation (step 7).

## Commands run

### Phase 0 — build-open baseline (2026-09-22)

| Command | Result | Notes |
|---|---:|---|
| `make verify` at `66d79c6f` | pass | backend 2842 passed (9:13); mypy, ruff, build green; infra 46 passed; prompt-guard 16 modules unchanged; `drift-check: OK`; frontend 708 tests / 82 files |

The decision sheet's task-2 rows (contract § Spec changes item 10) were
filled at plan approval (`66d79c6f`), so Phase 0 had only the baseline to
run.

### Phase 1 — revision, registries, compose by purpose, spine flag, resolver, existence model (2026-09-22, `deep-reasoner`)

| Command | Result | Notes |
|---|---:|---|
| `make verify` (full) | pass | backend 2897 passed (9:06; 55 new); okf 148/0; mypy 343 files clean; ruff clean; infra 46; prompt-guard 16 unchanged; `drift-check: OK`; frontend 708 tests / 82 files |
| `make openapi-sync` + `make drift-check` | pass | additive: `TaskOut.active_run` (nullable `LatestRun`), `TaskOut.has_longlist` (boolean, default false); no new schema, no path change |

Revision `c7e2a9f4b1d8` (revises `b5e1d7a4c026`): `option`, `option_membership`,
`option_relation`, `longlist_result`, `intervention_profile_record`;
`task_link.option_id` (composite FK to the target task's option);
`capability_run.parent_capability_run_id` (composite self-FK, `ix_capr_parent`);
`extraction_result.selection_run_id` nullable; `finding_reference_union`
recreated with the `interventions` branch from `FINDING_REFERENCE_UNION_SQL`
in `core/schema.py`. Downgrade refuses while any walk sits under a `longlist`
or `targeted` intent record, or while an `extraction_result` row has a null
selection; both name `scripts/ops_remove_scoping_tasks.py --apply`, which now
deletes the five tables' rows first. `ck_scope_purpose` already admitted
`longlist` and `targeted` (044 C4), so it is untouched.

New tests: `tests/core/test_migration_045_slice.py` (12: round-trip, both
refusals, the remedy, the FK guards, the three-branch view, closed CHECK
vocabularies); `tests/runtime/test_compose_by_purpose.py` (23: the three
chains and spine flags, the constants, ES sites unchanged, the fresh and both
resume paths recompose the walk's own purpose, the segment re-entry site);
`tests/options_scoping/test_labels.py` (13: own · inherited · absent · stale
rubric; Sources shows an inherited tier; an ES task reaches no other task; a
link grants no read to a task it does not target; nothing written);
`tests/api/test_scoping_existence.py` (7: a running or finished child is never
`latest_run`; `has_longlist`; a child fences neither `POST /runs`, a turn nor
`confirm-baseline`). Six table-count tests moved 38 → 43; the frontend mock
fixture gained the two fields (openapi-typescript makes a defaulted field
required).

**Lead calls recorded (S4 additions beyond the plan's column list):**
`option_relation.created_at`, `uq_orel_pair_kind`, `ck_orel_distinct`;
array-shape CHECKs on the jsonb columns; `ck_option_design_version`; three
task indexes; `created_by_run_id` / `assigned_by_run_id` FK-guarded to
`runs(run_id, task_id)`. No CHECK on `ambition` (S4 lists none; the typing
prompt's Literal is the vocabulary). The resolver's provenance rule: a field
resolves own first, then inherited; `provenance = inherited` when any field
came through a link, so a re-appraised inherited document reads *inherited*
with its own fresh tier. The PATCH `/plan` `run_active` read keeps the
all-walks fence (not in S15's list; a child of a running parent is fenced by
the parent anyway).

**Left for later phases (from the Phase 1 report):** `compile_longlist_intent`
does not exist yet (Phase 3; the longlist screen carries no criteria of its
own until then); the four new components are not in `LLM_BEARING_COMPONENTS`
(Phases 4–5); the stage vocabulary lacks the new names (Phase 4.4);
`continuation_state.build` resumes on the latest approved plan, not the
walk's `plan_id` (pre-existing; check once longlist walks can park).
**Pre-existing bug found:** `api/continuation._with_plan` builds
`type(state)(...)` without `parked_boundary` / `parked_component`, which
`ContinuationState` requires since 027 — the fan-out path with plan
adjustments would raise `TypeError`; not fixed here (out of scope), listed
under known gaps.

### Lead prompt surfaces — 2.1, 3.1, 4.1, 5.1, 7.1 landed together (2026-09-22, `lead`)

| Command | Result | Notes |
|---|---:|---|
| `ruff check` + `mypy` on the nine modules | pass | 16 source files clean |
| `uv run pytest tests/api/test_task_agent_scoping.py tests/runtime/test_task_agent_scoping_prompt.py tests/runtime/test_scoping_plan.py tests/runtime/test_gate_sort_prompt.py` | pass | 57 passed |
| `python3 scripts/prompt_hash_guard.py --update` | 24 entries | **8 added**: `extract/extract_interventions_prompt.py`, `options_scoping/suggest/suggest_prompt.py`, `options_scoping/longlist/longlist_cluster_prompt.py`, `…/longlist_theme_prompt.py`, `…/lever_typing_prompt.py`, `options_scoping/constrain/constrain_prompt.py`, `runtime/longlist_verbs_prompt.py`, `runtime/option_design_prompt.py`; **1 changed**: `runtime/task_agent_scoping_prompt.py` (v2 → v3); 0 removed; every other entry unchanged (the ES search prompts, screen, classify, IOF, ICF, gate sort included) |

All prompt-bearing work was authored by the lead before any delegate built
against it (plan: "prompt-bearing work is `lead` and always the first
sub-phase of its phase"). Every new module is named `*_prompt.py`, so the
guard pins it. `lever_types.py` (the versioned taxonomy, `lever_types_v1`,
ten types with definitions the typing prompt renders as data) and
`interventions_records.py` (the wire model whose field descriptions the
profile prompt renders) are lead-authored too; they are not prompt modules
by the guard's name rule and are pinned through the prompts that import
them.

**`task_agent_scoping_v3` diff (words only, rules otherwise byte-identical to
v2):** the plan's section list gains *Options you already have in mind* and
the run description gains the longlist sentence; a `YourOptionWire{text}`
and `ScopingPlanDraftWire.your_options`; a new section "Options you already
have in mind" (asked once as the part `your_options` with two options
`none_yet` (primary) · `i_have_some`, the user's words verbatim, the design
proposed back by code, never re-asked); the default transferability
preference explained once and never authored by the Task Agent (code mints
it, following Where; Edit removes it); a rule for edits after a longlist
exists (confirm, say the plan document offers Rebuild longlist, never say
the longlist updates itself); `your_options` added to the banned-keys list
and "assessing an option" to the not-yet-available list; the
`baseline_state` docstring names the longlist states.

**Design notes the delegates build against:** the cluster assignment wire
carries `reason` and `design_feature_not_stated` beside the engine's
`unit_id → label` pair (the component's backend keeps them on the side, the
engine sees only the pair — A9); the assignment may answer the component's
own label `not an option` (`NOT_AN_OPTION_LABEL`) beside the engine's
`ungroupable`; the verbs sort carries `assents_to_pending` so a confirming
turn is read explicitly rather than inferred from a sorted `other` (S11's
"a sorted `other` the prompt reads as assent", made a field — lead call,
flagged for the review); the typing wire's `ambition` Literal is the
vocabulary (`do_minimum · incremental · structural`, `AMBITION_BANDS`);
`constrain_v1` takes the three default screens as data ids (`relevant ·
distinct · in_scope`, `DEFAULT_SCREENS`) beside the requirement ids, and the
transferability preference is removed from its input by the caller.

### Phase 2 — the intervention profile on a selection-free path (2026-09-22; 2.1 `lead`, 2.2 `deep-reasoner`)

| Command | Result | Notes |
|---|---:|---|
| `make verify-fast` (shared gate with Phase 3) | pass | backend 2969 passed (11:44); mypy 364 files clean; ruff clean |
| `make prompt-guard` | pass | 24 modules unchanged (the lead's pins from `c89c1d36` / `e093ce34`) |
| `tests/evidence_search/extract/test_extract_interventions.py` | pass | 26 tests |

`extract_interventions` is a real harness node (the other four stubs stay);
`extract_scope(profiles=(os_interventions_base_v1,), selection_run_id=None)`
runs over the scope's screened-in set (`characterise.screened_sources`
projected to `{tss_id, text_basis: abstract_only}`), never loads chunks, and
writes the roll-up with a null selection. Bundle: `interventions_profile.py`
(fingerprint · grounding · writer · window adapter), the stored model and
rules in `interventions_records.py` below the lead's wire models (untouched).
Backend seam `InterventionsBackend` / `OpenAIInterventionsBackend` /
`StubInterventionsBackend` threaded as `RunnerBackends.interventions`; a
requested profile with no backend is an `ExtractError`. Memo through
`source_extraction_record` on (task, envelope snapshot, fingerprint) — the
fingerprint has no window knob and no scope intent, so one profile serves
every scope (A21). `extract_interventions` joined `LLM_BEARING_COMPONENTS`.

**Flagged deviations (2.2):**
1. `KNOWN_PROFILE_IDS` unchanged; `ALL_PROFILE_IDS = (*KNOWN_PROFILE_IDS,
   os_interventions_base_v1)` drives `_selected_profiles`. `KNOWN_PROFILE_IDS`
   is the ES directive grammar (`task_plan.EXTRACT_PROFILE_IDS` asserts on it
   at import); widening it is what P9 rejected. An ES directive naming the
   profile is refused (test).
2. The fingerprint lives in `interventions_profile.py`, not
   `interventions_records.py` (the prompt module imports the records module;
   the other way is a cycle).
3. Grounding locates the quote in the abstract, then the title, then both
   joined (title and abstract often repeat the name, so the joined basis
   alone reads as ambiguous). A failed grounding keeps the record with
   `spans: []` and counts in `quote_unverified`.
4. "Covers no intervention" is the `source_extraction_record` status
   `no_findings` with no rows; the per-row column carries the model's flag.
5. A title-only document is profiled from its title; a document with
   neither fails `empty_basis`.

**For Phase 5:** records for a walk = `intervention_profile_record` ⋈
`source_extraction_record` filtered by the scope's screened-in snapshot ids
(or the roll-up's `docs[].profiles[...].extraction_record_id`); the creating
run may be another scope's (memo); exclude `role = comparator` in the
component; `grounding` is a one-element qv_v1 array with `segment:
title|abstract` spans; `text_basis` rides the parent record (`abstract_only`).

### Phase 3 — plan slots, the longlist intent, the scoping Task Agent v3 (2026-09-22; 3.1 `lead`, 3.2 `deep-reasoner`, plan-document copy pass `lead`)

| Command | Result | Notes |
|---|---:|---|
| `make verify-fast` (shared gate with Phase 2) | pass | as above |
| `make prompt-guard` · `make openapi-sync` · `make drift-check` | pass | 24 unchanged; `drift-check: OK` |
| `make frontend-verify` | pass | 82 files / 714 tests (6 new on the plan document); one pre-existing lint warning (`SplashField.tsx`) |
| `cd frontend && pnpm e2e` | pass | 15 passed |
| new backend tests | pass | `test_scoping_plan_options.py` (22), `options_scoping/test_design.py` (7), `test_longlist_intent.py` (7), `api/test_task_agent_scoping_options.py` (10) |

`OptionDesign` (`options_scoping/design.py`: name · description ·
design_features · outcomes_served · assumed · version; `as_intent()` =
"{name}. {description} Design features: f1; f2; …" — deterministic, the
targeted intent record's text in Phase 4). `ScopingPlan.your_options[]`
(`YourOption{text verbatim, design | None, turn_index}`); designs proposed
at plan approval outside any transaction through
`AgentBackend.propose_option_design` (`option_design_v1`, judgment model;
stub queue in `StubAgentBackend`), only for new or reworded options, a
failed proposal logged and left `None` (the approval never fails on it).
The default transferability preference: `ScopingConstraint.default =
"transferability"`, minted by `build_scoping_plan`, re-texted when Where
changes unless the user edited its text, removable by a patch that omits it
(`ScopingPlan.removed_defaults` carries the removal forward; never
re-minted); never authored by the Task Agent (a draft preference starting
"Transferable to" is dropped and logged). `compile_longlist_intent`
(PICO-shaped, no Where) and `longlist_screening_criteria` (no place; the
setting only when a `setting=True` requirement exists) in
`options_scoping/longlist_intent.py`; the criteria wired into the longlist
and targeted chains' `screen_abstract` deltas. `SCOPING_STEPS` Longlist
blurb replaced. API: `OptionDesignOut`, `YourOptionOut`, `YourOptionIn`;
`ScopingConstraintOut.setting` and `.default`; `ScopingPlanDraft.your_options`;
`ScopingPlanPatch.your_options` — additive. `_baseline_state` gains "a
longlist exists, built from plan version N" and "a longlist is being built".
Plan document: the *Options you already have in mind* section (words, the
proposed design with assumed features marked, Edit), the preference row with
its rider "checked at assessment · assumed" and a **Remove** control.

**Flagged deviations (3.2):**
6. The screen's 2,000-character ceiling is checked by
   `scoping_plan.compose_longlist_screen_intent(plan)` (raises `ValueError`,
   never truncates), not inside compose — raising in compose would leave a
   `capability_run` row open in the runner. Phase 4's opener calls it before
   opening a walk and answers 422.
7. The PICO intent is the longlist intent record's text (Phase 4 writes it),
   not a directive; only the criteria ride the delta.
8. A **Remove** control on the default preference row (the contract says
   "removable"; the section's Edit seeds the chat, and the Task Agent is told
   never to author the default, so chat could not remove it). Shown only
   when the plan is approved, editable and no walk is active.
9. `your_context` entries now record the real approving turn index (was 0):
   the turn route passes `source_turn_index`. Behaviour-preserving otherwise.
10. `ScopingConstraintWire.setting: bool` added to the v3 prompt by the lead
    (`e093ce34`) so code can find a setting requirement (D21) — a wire
    addition, not a plan-object change beyond the contract's table.

Lead copy pass: "Design not proposed yet" → "No design yet"; the rest of the
delegate's copy kept (rider, "Proposed design", "assumed", the Edit seed, the
criteria wording the screen model reads as data).
