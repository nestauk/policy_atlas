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

### Phase 4 — the walk: inherit, suggest, option searches, the start surfaces, progress (2026-09-22; 4.1 `lead`, 4.2 `deep-reasoner`, 4.3 `deep-reasoner`, 4.4 `fast-worker` plumbing + `lead` words)

| Command | Result | Notes |
|---|---:|---|
| `make verify` (full, the phase gate) | pass after one fix | first run: 2 failures in `test_task_agent_router.py` — two full-object expectations of `PlanOut` lacked the new optional `opened_run: None` (additive field, expectations extended); rerun: backend 3079 passed (13:08); okf 148/0; mypy 380 files clean; ruff clean; build OK; infra 46; prompt-guard 24 unchanged; `drift-check: OK`; frontend 83 files / 722 tests |
| `cd frontend && pnpm e2e` | pass | 15 passed |
| `make openapi-sync` + `make drift-check` | pass | additive: `TurnDecisionOut.opened_run`, `PlanOut.opened_run`; the five `stage` enums widened by the six keys |

**4.2 — inherit and suggest** (new tests: `test_inherit_documents.py` 8,
`options_scoping/test_suggest.py` 12, `test_skip_directive.py` 20;
`test_compose_by_purpose` updated — the stub walk now runs inherit and
suggest and fails at `longlist`). `inherit_documents` inserts one
`task_source_snapshot` row per linked document the task lacks (origin copied
from the source row — A3; `run_id` = the inherit run; full-text link and
status copied), `ON CONFLICT DO NOTHING` on `uq_task_source_snapshot`; each
link in its own savepoint, an unreadable link rolled back and named in the
summary (`failed_link_ids`, `failed_reasons`), the step completes with
`degrades_walk: true` and the runner ends the walk `degraded` (a new
completed-step flag, `DEGRADES_WALK_KEY`). `suggest_options` reads the plan,
the latest baseline `synthesis_result`'s sections and the linked reports'
bodies, calls `longlist_suggest_v1` through `AgentBackend.suggest_options`
(a narrow `SuggestBackend` protocol; stub queue), mints `suggested` /
`from_evidence_search` rows (the report section recorded in the run's
`component.completed` payload — the `option` table has no provenance
column) and the plan's own options as `added_by_you` (minted before the
model call, so a failed call still leaves them). `leg_directive(plan, step,
upstream_state, *, engine, task_id, evidence_scope_id)` reads the scope's
purpose at `classify` and `appraise` of a longlist walk and writes the
`skip_task_source_snapshot_ids` keys from the resolver; classify gains a
fail-closed parser; both selection queries add `NOT IN`.

**Flagged deviations (4.2):**
11. Classify's skip is narrower than S6's words: a document is skipped at
    classify only when its label is inherited, its type resolved **and**
    appraise has nothing left to do (tier resolved, or the type outside the
    rubric) — appraise reads this scope's classification rows, so skipping
    classify for a stale-rubric inherited document would leave it with no
    tier. Cost: one classify call per stale-rubric document.
12. `suggest_options` is not on the `AgentBackend` protocol (test doubles
    implement it); the harness types against `SuggestBackend`.
13. An own option with no design (a failed `option_design_v1` proposal)
    still becomes an entrant, on a design read from the user's words
    (`own_without_design` counted); `ensure_option_designs` is not called
    inside the component's transaction.
14. Rebuild matching is `(origin, name)`; an own option that first entered
    on its words and later gains a proposed design with a different name
    would mint a second row. Known gap (edge: only after a failed proposal).
15. Provider `source_tag` rows are not copied to inherited rows, so
    classify's priors are missing on an inherited document it does classify.

**4.4 — stage keys and beats** (`test_stage_vocabulary.py` 4;
`runProgress.test.ts` new): six keys `inherit · suggest · option_searches ·
extract_interventions · longlist · constrain` on `StageKey`, `STAGE_KEYS`,
`PlanStageKey`, `STAGE_PRESENTATION` (the lead's labels and blurbs) and
`STAGE_BY_REGISTRY`; OpenAPI additive (the five `stage` enums widened);
`beatSentence(stage, summary)` composes the six beats client-side from
`StageCompletedFrame.summary` and rides `stageDetailLines`.

**4.3 — the option search tool, child walks, the barriers, the pool and
semaphores, the two start surfaces, the unattended follow-on, the
conversation lineage** (new tests: `test_option_search.py` 12 + 1,
`api/test_longlist_start.py` 14 + 1; gate-turn, check-in, scoping and
existence tests updated with a recording executor). `run_option_search`
(`runtime/option_search.py`) mints the child's `capability_run_id`, inserts
the targeted intent record (`intent = design.as_intent()`, `context.option_id`)
and submits `run_plan(capability_run_id=…, parent_capability_run_id=…)` to
the option-search pool (`runtime/walk_pool.py`, width 4, separate from the
walk executor); `CLASSIFY_SLOTS` / `INGEST_SLOTS` semaphores around
classify's provider calls and ingest's parse jobs. The barriers sit at the top
of the step loop for a `longlist` walk: fan-out on the first step after
`suggest` (cap 15, the user's and the report's entrants first; only entrants
without a prior search on a rebuild; durable as its own event so a resumed
walk never dispatches twice), join when `longlist` is popped (outside any
transaction, polling child statuses; `OPTION_SEARCH_JOIN_TIMEOUT = 1800 s`;
stragglers `interrupted`; a failed child adds a synthetic `skipped`
`option_searches` outcome so the parent ends `degraded`). The `option_searches`
frames ride `run.started` / `component.completed` events with `run_id = None`
(inert for every existing reader; `sse._map_rows` maps them). The opener
`api/longlist_start.py::open_longlist_walk` (admission under `_dispatch_lock`,
`compose_longlist_screen_intent` → 422 before any mint, the longlist intent
record with the PICO text, the reservation released by a small daemon thread
on the non-waiting paths); callers: `_persist_confirm_plan` (ends the baseline
walk `reason: confirm_plan`, closes the conversation, `follow_on="longlist"`
→ `DecisionOutcome.follow_on` → `_dispatch_gate_turn` → `TurnDecisionOut.opened_run`),
the card route (204, `await_run=False`), `confirm_baseline` (commit, re-read,
open; `PlanOut.opened_run`; the idempotent path reopens a missing walk; a
newer version opens a rebuild), and the unattended follow-on inline in
`_dispatch_run` after the baseline returns (`RunPlanOutcome.follow_on`, set
only when a declared standing default was honoured). `_finish_run` skips the
conversation closure for a child. Peak connections on the stub walk with 6
entrants at width 4: 5 (the parent plus four children; the parent holds none
at the join).

**Flagged deviations (4.3):**
16. **`core/events.py` `APPEND_ATTEMPTS = 32`** (was 5). The event log has one
    sequence per task and assumed one writer per task (ADR 0001 § 6); a
    parent and four children exhausted five retries on the stub walk. Ordering
    is unchanged (a collision waits for the other writer's commit and
    retries). The real cost stands: acquire, screen, classify and appraise
    append events inside long component transactions, so concurrent children
    on one task wait on each other's uncommitted rows — Phase 8 measures the
    effective concurrency; it may be well below 4. Not in the plan; accepted
    by the lead; a review item and a knowledge candidate.
17. **The longlist walk and its children run under the unattended plan**
    (`option_search.unattended_plan`: the confirmed plan with
    `steering_mode = unattended` and the gate's standing default; the plan
    row is untouched). Under the parent's attended mode a rule-fired check-in
    (a `classification_type_mix_collapse` on a small search) parked every
    child, and then the parent too, which D1 forbids ("the walk does not
    pause"). Resolved within the contract's vocabulary: the longlist chain
    has no lattice point, so nothing is ever put to the user; rule-fired
    boundaries are recorded as `triggers_fired` collation flags. Test:
    `test_a_longlist_walk_never_parks_even_under_frequent`. The baseline walk
    is unchanged.
18. Ingest slots are more than a plain `with`: a walk waits for a slot only
    when none of its own parse jobs is in flight, else it drains its own
    first (avoids a deadlock between walks); every exit path returns the
    slots; a single walk behaves as before.
19. `open_longlist_walk` returns the minted UUID (never `None`); on the chat
    and card paths a refusal (capacity, plan too long) is logged, the decision
    stays durable and `opened_run` is null — the plan document's confirm
    reopens the walk later.
20. `_persist_confirm_plan` ends the baseline walk `degraded` rather than
    `succeeded` when the baseline had a failed or skipped step (`_finish_run`'s
    own rule).
21. If a spine step fails before `longlist`, the parent ends `failed` without
    joining and its children finish on their own.
22. `CONFIRM_REPLY` → "Plan confirmed. Building the longlist now." (lead copy).
23. **For Phase 7:** a parentless *add* child would close the Task Agent
    conversation in `_finish_run` (the skip keys on the parent column); Phase
    7 must also skip the closure for `purpose = targeted` walks.

### Phase 5.2 — the longlist component (2026-09-22; 5.1 `lead`, 5.2 `deep-reasoner`; gated with Phase 4)

New tests: `options_scoping/test_longlist.py` (20), `test_where_tried.py`
(19); `test_compose_by_purpose` updated (the stub walk runs through
`longlist` and fails at `constrain`). `clustering_engine.py` has no diff;
characterise, engine and group tests pass unchanged.
`options_scoping/longlist/longlist.py` (units → seeded clustering → option
rows and memberships → themes → typing → coverage → `longlist_result`),
`longlist_backend.py` (`LonglistBackend` protocol; OpenAI: judgment model for
discovery, themes and typing, mini model for assignment; stub), `coverage.py`,
`where_tried.py`; `RunnerBackends.longlist`; `longlist` in
`LLM_BEARING_COMPONENTS`. Seeds pass through the engine as labels returned
first by the backend's `discover` (`max_new = max_labels − seeds`, no call
when 0; a restated seed dropped and counted); `not an option` and the
prompt's `ungroupable` both go to the engine as its residual label, the
backend remembers each unit's raw answer, reason and flag on the side, and
the component splits the residual into the two counted buckets afterwards;
`forbidden_label_reason` rejects a discovered label named like either bucket.
Exhaustiveness (units = memberships + unclustered + not an option) is
enforced in code; every model call happens before the first write. Theme
ceiling `clamp(ceil(options/3), 3, 12)`, `min_labels = 0` for both runs.
`COUNTRY_GROUPS`: lower-case country names and adjectives → ISO alpha-2 (the
UK and its nations, the 38 OECD members, ~30 common others; longest match
first; case-sensitive `ABBREVIATIONS` for UK/US/USA so the pronoun "us" never
matches; `OECD_MARKERS` sends "12 OECD countries" to *comparable*; ambiguous
adjectives left to *unknown*).

**Flagged deviations (5.2):**
24. Seeds are every option row of the task (added_by_you → from_evidence_search
    → suggested → clustered), not suggest's `entrants` event — on a first
    build these coincide; `max_labels = max(ceiling, seeds)` so a rebuild with
    more options than the ceiling passes engine validation.
25. Every discovered label is minted, even one ending with zero members
    (coverage shows zero); a discovered option with no stated features gets
    `[description]` as its one feature (`OptionDesign` needs one).
26. The DOI is normalised locally (`coverage.normalise_doi`) rather than by
    importing the API layer's `_metadata_text`.
27. Linked findings get a role for the funnel: IOF counts as `evaluated`, ICF
    as `described`; both are also counted under `coverage.findings`.
28. Units are read through each scope's newest extraction roll-up carrying
    the profile, not through `screened_sources`.
29. An invalid typing leaves `ambition` NULL and records `lever_none_fits_reason
    = "typing invalid"`, counted in `counts.typing_invalid`.

### Phase 5.3 — constrain (2026-09-22; 5.1 `lead`, 5.3 `deep-reasoner`; gated with Phase 6)

New tests: `options_scoping/test_constrain.py` (20); `test_compose_by_purpose`
updated — **a longlist walk on the stub backends now runs end to end and ends
`succeeded`**, with its `longlist_result` judged. `options_scoping/constrain/
constrain.py` (`constrain_scope`, `ConstrainBackend`, `user_holds_state`),
`in_scope.py`; `constrain` rides the `LonglistBackend` seam
(`OpenAILonglistBackend.constrain` on the judgment model; the stub's FIFO
queue passes everything and guesses `cannot_say`); the last harness stub is
gone (`_NotBuiltYet` / `OPTIONS_SCOPING_STUBS` removed); `constrain` in
`LLM_BEARING_COMPONENTS`. Verdicts: the first `breaks` (requirements before
screens) excludes with `{constraint, reason, by: "constrain"}`; a user-held
row (`exclusion.by == "user"`, whatever its state — an *include again* keeps
the record) is never touched; `distinct` is forced to `passes` for any option
with a `part_of` relation at either end; thin evidence never excludes.
Judgements keyed `judgements[option_id][str(design_version)]` with ids
`req-N`, `relevant`, `distinct`, `in_scope`; guesses `pref-N` (the
transferability default removed before the call — asserted on the stub's
recorded inputs); the in-scope record under `in_scope_evidence`.

**Flagged deviations (5.3):**
30. The in-scope check reads the **OpenAlex authorship countries** beside the
    publication country (Overton display names mapped back to ISO through
    `OVERTON_COUNTRY_DISPLAY`): the OpenAlex search filters a country group
    on `authorships.countries`, and D9 says "the same fields retrieval
    filtered on" — without it a UK-restricted OpenAlex article published by
    a Dutch publisher would read as out of scope (A12). Lead: accepted.
31. A document with no country or no year in its metadata **passes** that
    part of the check (the check marks only what the metadata proves);
    documents counted once per DOI. Lead: accepted (honest absence).
32. The in-scope record's key is `in_scope_evidence` (the plan's `in_scope`
    collides with the *within scope* screen id); `counts.no_in_scope_evidence`
    (5.2's reserved key) is filled rather than a second `no_in_scope`.
33. The three default screens always need one call per batch, so "the
    in-scope check makes no backend call" is tested on `in_scope_evidence`
    directly and on a walk whose backend always fails (two calls: the batch
    and its retry; the mark still correct).
34. `provenance["constrain"]` added (run id, model, batches, retries,
    usage). Layering: `in_scope.py` imports `publication_country` from the
    API read-model module (no cycle today; move the helper to a neutral
    module if one appears).

### Phase 6.1 — read models, routes and the apply functions (2026-09-22, `deep-reasoner`; gated with Phase 5.3)

| Command | Result | Notes |
|---|---:|---|
| `make verify-fast` (5.3 + 6.1 + the coverage fix) | pass | backend 3122 passed (15:03); mypy 386 files clean; ruff clean |
| `make prompt-guard` · `make openapi-sync` · `make drift-check` | pass | 24 unchanged; `drift-check: OK` |
| `tests/api/test_longlist_routes.py` | pass | 14 tests: org-scoped and public reads like the artefact; a link grants no read of the target's options; 404 without a longlist; the list matches the rows; the card carries every section and never "how sure" (serialised JSON); exclude records the reason and include reverses it, one History event each; user state survives a rebuild's constrain; add proposes a design, mints `added_by_you` and opens a parentless stub child; 409 `run_active` only for a parentless walk; 422 on an ES task |

`api/contract/read_models.py`: `LonglistOut`, `OptionSummaryOut`, `OptionOut`,
`LonglistThemeOut`, `LonglistCountsOut`, `WhereTriedOut{where, comparable,
other, unknown}` + `where_label`, `RelationOut{kind: part_of | has_part}`,
`ExclusionOut`, `EvidenceProfileOut`, `JudgementOut`, `GuessOut`, `InScopeOut`,
`OptionDocumentOut`, `AmbitionBandOut`, `OptionAddIn`, `OptionExcludeIn`,
`OptionIncludeIn`, `OptionAddedOut` (18 schemas; 5 paths; additive).
`repository.longlist_out` / `option_out` (latest `longlist_result` by
`created_at DESC`; 404 when absent); `api/longlist_actions.py` (`add_option`,
`exclude_option`, `include_option`, `propose_design`, the fence
`admit_longlist_action`) — the buttons and Phase 7's verbs share them;
`api/routers/longlist.py` (two GETs on `_readable`, three POSTs on
`accessible_task(write=True)`). **History**: no 044 precedent fitted (a button
has no walk to hang on), so each action appends a task-level `event_log` row
(`option.added` / `option.excluded` / `option.included`, `run_id = None`,
actor in the payload — the rename/share audit pattern); `GET /decisions`
renders them `decided_by = "user"`; `historyPresentation.ts` gains the
category in 6.3.

**Flagged deviations (6.1):**
35. `WhereTriedOut` is `{where, comparable, other, unknown}` with `where_label`
    (the first group is the plan's Where, not always the UK); `ThemeOut` is
    named `LonglistThemeOut` (the name existed for the landscape).
36. Extra fields: `LonglistOut.capability_run_id`, `lever_types`,
    `ambition_bands`, `taxonomy_version`, `where_label`; `OptionOut` the same
    two. `options`, `included`, `excluded`, `no_in_scope`, `none_fits` are
    counted live from the option rows (a user exclusion shows at once);
    `themes`, `unclustered`, `not_an_option` from the stored result.
37. Include takes an optional body `{reason?}` (deliverable 11 says "with the
    user's reason" for both); include writes the `by: "user"` marker on an
    included row (5.3's rule) and the read model hides `exclusion` unless
    excluded.
38. Errors added: add with no approved plan 422; a failed design proposal
    503 `unavailable` (nothing minted); a blank reason 422.
39. Lock order: exclude/include read the dispatch reservation set without
    `_dispatch_lock` (they hold the task row lock; the openers take the lock
    then the row). **`archive_task_route` takes them in the reverse order
    today — a latent deadlock risk, pre-existing, listed under known gaps.**
40. Coverage bug found and fixed (5.2, `coverage._pick_label`): DOI twins took
    the label of the first id even when unrated; now the rated twin's label
    wins (own before inherited, a tier before none), tested in both id
    orders.
41. `test_longlist_routes` builds its fixture without the link for the add
    test: a shared snapshot between a linked task and the scoping task needs
    custom teardown (`delete_task_data` deletes snapshots the other task
    still references) — a test-helper gap for the review.

### Phase 6 + 7 — the longlist views, lifecycle and plan states, the longlist verbs (2026-09-23; 6.2 `fast-worker` structure, 6.3 `deep-reasoner`, 7.1 `lead`, 7.2 `deep-reasoner`)

| Command | Result | Notes |
|---|---:|---|
| `make verify` (full, the Phase 7 gate over 6.2 + 6.3 + 7.2) | pass | backend 3138 passed (11:56); mypy 388 files clean; ruff clean; build OK; infra 46; prompt-guard 24 unchanged; `drift-check: OK`; frontend 86 files / 780 tests |
| `cd frontend && pnpm e2e` | pass | 18 passed (3 new: building → built → Result on Longlist with Report disabled; the beats in the thread; a plan edit → "built from plan version 1" → Rebuild longlist → "Building the longlist") |
| `make openapi-sync` + `make drift-check` | pass | additive: `TurnActionOut`, `action` on `TaskAgentTurnOut` and `TaskAgentTranscriptTurnOut`, `kind` widened with `action` |

**6.2 — list, grid, card** (`views/longlist/LonglistView.tsx`, `LonglistGrid.tsx`,
`OptionCard.tsx`, `longlistPresentation.ts`; `useOption`, `useAddOption`,
`useExcludeOption`, `useIncludeOption`; the card route; mock fixtures with
four full option cards and the five handlers; 25 vitest). The facets filter
the list only (the grid's axes are orthogonal). Judgement `leaning` and
document dedup are not rendered (no template calls for them).

**6.3 — lifecycle, readers, plan states, thread** (`views/scopingActivity.ts`:
`isScoping · activeRun · isRunActive · statusRun · tabRunStatus · hasLonglist ·
hasTaskResult`; nine readers moved — `LifecycleRoute`, `AppShell` (running
indicator and tabs), `ArtefactView` (`hasResult`, `showLiveArtefact`, the
Baseline · Longlist · Report switch on `?view=`), `TaskListPanel`,
`ChatSidePanel`, `planStart`, `WorkspaceView.chatsEnabled`; `useTask`/`useTasks`
poll while a scoping task's `active_run` is set; `planStart` gains
`longlist_built`, `rebuild_longlist`, `none{buildingLonglist}`, and `confirmed`
carries **Build longlist**; `scopingStatusLine(state)`; the thread's `action`
turn via `DecisionLine` (`actionLine`); History category **Longlist**; the
mock streams a longlist walk with the six beats; 33 vitest, 3 e2e).

**7.2 — the longlist verbs** (`api/longlist_turns.py`; `_Reserved.longlist`;
the dispatch arm; `AgentBackend.sort_longlist_turn` on `AGENT_TRIAGE_MODEL`;
the pending action in `task_agent_state.pending` with a one-option confirm
part `longlist_action`; confirm by the button marker or by sorted assent;
`exclude_option(require_reason=False)` on the verb path (the copy allows
"Reason: none given"); the scope set = every targeted scope on the task
(children of any longlist walk plus every parentless option search — a
rebuild skips entrants that already have a search, so older children still
hold their documents); `build_retrieval_scope(..., extra_scope_ids=())` and
`make_lookup_reader` with the P13 precedence (the longlist scope's row, then
the latest screen); a label fallback through the resolver in `chat_scope`
for inherited documents (the citation floor refused them as unappraised
otherwise); `_finish_run` also skips the conversation closure for
`purpose = targeted` walks; 16 tests).

**Flagged deviations (6.2, 6.3, 7.2):**
42. `LifecycleRoute` / `AppShell` read `TaskOut.has_longlist` and do not
    fetch the longlist (the flag rides the task payload); `ArtefactView` and
    `planStart` fetch it because they need its data.
43. The tabs key on `latest_run` for both task kinds (a pure `active_run`
    read would lock Sources and History whenever nothing runs; the server
    keeps a scoping task's `latest_run` parentless and non-targeted, so a
    child never opens or locks a tab).
44. `scopingStatusLine(state)` takes the state alone (the count and the
    "built from" version live on it); `none` carries `buildingLonglist`.
45. The 044 e2e gate helper no longer clicks "Close the scoping plan" after
    the baseline start; with the start area kept mounted during a walk,
    `WorkspaceView.onStarted` closes the plan as designed (the old test
    passed on an unmount race).
46. The 7.2 pending-action rule as ruled by the lead: a non-assenting
    `other` **keeps** the pending action and replies "Still waiting: …";
    only an applied action, a replacing verb or an explicit confirmation
    clears it. Verbs keep the exclusion reason and add wording only when
    they appear verbatim in the utterance.
47. `build_retrieval_scope` / `make_lookup_reader` keep `scope_id` as the
    primary and take `extra_scope_ids=()` (the plan said `scope_ids`): the
    primary encodes the precedence rule and synthesis calls stay
    byte-compatible.
48. Question turns pass `entry_artefact_id=None`. If the process fails after
    `add_option` commits but before the turn completes, a retry would add
    the option again (the button route has the same property; `add_option`
    owns its transactions).

**Open risks recorded for the review:** the mock `mockLonglist()` hard-codes
`plan_version: 1` (a mock rebuild stops at "Building the longlist" — mock
only); `planStart` finds the baseline walk in the first 200 runs, which now
include option searches (about eight rebuilds of 25 options could push it
off the page); the stream reducer was not checked against child-walk frames
(the mock streams none; the live check does).

### Lead taste pass on the longlist surfaces and the thread (2026-09-23, `lead`)

| Command | Result | Notes |
|---|---:|---|
| `make frontend-verify` | pass | 86 files / 782 tests (2 new: the walk kinds and their words) |
| `cd frontend && pnpm e2e` | pass | 18 passed |

Screenshots of the mock surfaces (the session scratchpad; public-safe, mock
data) drove the pass. Changes: the list's filter row gains the group labels
**Show · Setting · Where tried** so the three facets read as three things;
the "Do nothing" sentence keeps only *the baseline* as the link; the add
control is a compact field ("An option of your own, in a few words") beside a
secondary button; the thread's run card and finished notice follow the walk
kind (`runProgress.walkKind(capability, stages)`): a longlist walk ends "The
longlist is ready" · **Read the longlist** · "The longlist is built. Open it
in the Result tab."; a baseline walk "The baseline is ready" · **Read the
baseline**; the Evidence search's words are unchanged; the composer's
placeholder while a longlist exists and nothing runs reads "Ask about the
longlist, or add, exclude or include an option." The grid and the card stayed
as built (the card's sections and templated evidence sentences read
correctly; the grid's empty rows are the contract's words).

### Phase 8 — live check (a)–(g), local app, real egress (2026-09-23, `lead`)

Driven through the local API with a dev-issuer token (the 044 method), the
backend started without `--reload` on the committed tree at `ba1b60ad` (so
the defects found below were fixed in the tree afterwards, not mid-run), the
frontend on `:5173` for the screenshots (headless Playwright). Dev DB
upgraded `b5e1d7a4c026 → c7e2a9f4b1d8` first. Every figure below is read
back from the saved responses and the event log (session scratchpad
`live/out/<task>/*.json`; the screenshots and JSON travel as the PR's
evidence zip, `docs/tasks/*/evidence/` being gitignored).

**Three live longlists**

| | T1 — linked, rapid, one own option (the pinned check) | T2 — unlinked, standard (the numbers) | T3 — unlinked, rapid |
|---|---|---|---|
| task | `4e12db1d…` from the NEET Evidence search `1e03e719…` | `e898f733…` | `22937fdd…` |
| baseline (`POST /runs` → `paused`) | 301 s | 798 s (13.3 min) | 316 s |
| longlist walk (confirm → `succeeded`) | **1,447 s (24.1 min)** | **1,724 s (28.7 min)** | **1,607 s (26.8 min)** |
| stage split | inherit 0.1 s · suggest 46 s · acquire 24 s · screen 49 s · classify 3 min 23 s · appraise 1 s · ingest 3 min 50 s · profile 18 s (fresh 48, reused 103) · option searches (fan-out to join) 15 min 43 s · longlist 4 min 11 s · constrain 3 min 27 s | suggest 38 s · acquire 22 s · screen 52 s · classify 6 min 4 s · appraise 1 s · ingest 6 min 42 s · profile 14 s (fresh 20, reused 117) · option searches 21 min 36 s (contended: the rebuild's eight extra children shared the pool) · longlist 4 min 2 s · constrain 2 min 27 s | suggest 28 s · acquire 27 s · screen 44 s · classify 2 min 15 s · appraise 1 s · ingest 8 min 23 s · profile 39 s (one failed attempt on the memo race — the old server code — retried in 7 s; fresh 12, reused 76) · option searches 20 min 21 s (contended with the exit gate's test suite on the same machine) · longlist 4 min 11 s · constrain 1 min 47 s |
| option searches | 11 children (1 own · 7 from the report · 3 suggested), width 4 held (three waves), each 168–359 s, all `succeeded` | 10 children (10 suggested — the bound; no report, no own option), 177–831 s, all `succeeded` | 10 children (10 suggested), 108–775 s, all `succeeded` |
| funnel | acquired 185 screened (rapid, 25 per backend + 59 inherited + baseline) → 151 relevant → 295 documents in the pool → 395 profile records (evaluated 43 · described 132 · recommended 138 · mentioned 70 · comparator 12) → 383 units → **40 options** (the ceiling) in **12 themes** (1 unthemed) · unclustered 168 · not an option 94 · none fits 0 → included 36 · **excluded 4** (1 by the requirement "No benefit sanctions or benefit cuts", 3 by the *relevant* screen) · no in-scope evidence 0 (no evidence restriction on the plan) · cannot_check 12 | 189 screened (standard, 50 per backend + baseline) → 137 relevant → 294 documents → 344 records → 337 units → **40 options** in **11 themes** · unclustered 113 · not an option 79 · none fits 0 → excluded 4 (the *relevant* / *in scope* screens; no requirement on the plan) · no in-scope evidence 0 · cannot_check 2 | 125 screened (rapid, 25 per backend + baseline) → 88 relevant → 217 documents → 305 records → 289 units → **40 options** in **12 themes** · unclustered 68 · not an option 73 · none fits 0 → excluded 3 · no in-scope evidence 0 · cannot_check 9 |
| profile cost | 166,293 prompt + 8,738 completion tokens for 48 fresh documents = **about 3.5 K prompt tokens per document** (135 K of the prompt cached) | | |
| option-search cost per entrant | 0.55–1.55 M prompt tokens (mean about 1.05 M) and 93–190 K completion; the screen dominates (89–295 candidates screened per search, 72–175 in) | | |
| peak DB connections | **6 active** (the parent, four children, the poll) at width 4 — inside the 5 + 10 overflow pool; with two walks running at once (the rebuild and T2) the bound held at four children in total | | |

**T1 (a)–(g), what happened**

| Step | Observed | Measured |
|---|---|---|
| (a) | Task linked to the NEET Evidence search; turn 1 recorded the own option verbatim, proposed its design back (six features, three assumed), set rapid, explained the default preference once and asked only the constraints part; turn 2 typed a requirement (longlist) and a preference (assessment) and became ready. `GET /plan` v1: `your_options[0].design` present; constraints = requirement · preference · **"Transferable to England"** (`default: transferability`). Baseline paused at the gate | turns 14.8 s · 10.2 s; baseline 301 s |
| (b) | "Looks right. Confirm the plan and build the longlist." → `kind: decision`, reply "Plan confirmed. Building the longlist now.", `opened_run` running; the beats appeared in the thread; the Result opened on the longlist | confirm turn 1.7 s; walk 24.1 min |
| (c) | 40 options: the own option *added by you* (7 documents, 2 evaluated), seven *from your evidence search*, three *suggested by Policy Atlas*, 29 *clustered from N documents*; one excluded by the requirement ("Reduced sanctions for young Universal Credit claimants" — breaks "No benefit sanctions or benefit cuts"), three by the *relevant* screen; the Do nothing sentence; the setting facet (28 source-named settings — capped to eight with "more" in the fix below) and the where-tried facet (England · comparable systems (OECD) · other · unknown). Where tried on the cards is mostly *unknown*: abstracts rarely state the study geography; where they do, England/UK and OECD countries appear (e.g. the procurement-clauses option: comparable 4) | |
| (d) | Grid: lever type × ambition with the excluded and no-in-scope states; the own option's card: the design's six features, lever *provide a service*, ambition *structural* "as described, not measured", where tried, the evidence profile in sentences (7 documents; 2 evaluated, 3 described, 1 recommended, 1 mentioned; by type and tier; 5 flagged not stated; 7 abstract only; "A mention is not support."), the judgements (req-1 `cannot_check`, the three screens `passes`), one guess (low cost: *likely falls short*), the transferability row "checked at assessment", Show the documents (8 rows, roles and tiers) | |
| (e) | "Exclude the wage subsidies option — we can't fund employer grants from this budget." → proposed back with the reason verbatim and a one-button confirm part; "Yes, go ahead." → `kind: action`, the row `excluded` with `{by: user, reason, constraint: "your decision"}`; Include again by button → `included`, `by: user`; "Add a youth mentoring scheme: …" → the design proposed back (five features); "Yes." → `kind: action`, the option minted *added by you* and a parentless targeted walk opened; History lists the three actions as the user's turns | sort turns 1.6–1.7 s; the add's search 3 min 22 s (124 screened in, 75 profiled) |
| (f) | `PATCH /plan` adding the requirement "Only options a local authority can run." → v2; `GET /longlist`: `built_from_plan_version 1`, `current_plan_version 2`; `POST /plan/confirm-baseline` on v2 → v3 and a rebuild walk `opened_run` | rebuild walk **2,411 s (40.2 min)**: suggest 28 s · broad chain 12 min · option searches 31 min 51 s (eight duplicate searches — the defect below — sharing the width-4 pool with the standard walk's ten) · longlist 3 min 27 s · constrain 4 min 25 s. After it: **all 41 option ids kept**, the user's re-included option still `included`, the sanctions option still excluded, the added option now clustered (10 memberships, 7 documents), the new requirement excluded 10 options (16 excluded in all), plan version 3 = `built_from_plan_version` |
| (g) | "What does the evidence say about youth mentoring schemes for young people at risk of becoming NEET?" → `kind: answer` over the union of scopes, an honest "the committed evidence does not establish…" with two citations (a commentary and a policy synthesis). **The two cited documents were screened in under the longlist scope, not under the added option's own search** — the answer core ranked them above the mentoring search's 124 documents; the union works, the contract's "from its own search's documents" did not happen on this question | 41.6 s |

**Defects the live check found and fixed in the tree** (each with a test;
the running server kept the old code):

- **Concurrent option searches aborted a component transaction** (child
  `61291f72…`, `extract_interventions`, recovered by the retry): two
  children profiling the same shared document raced on the memo row
  (`uq_ser_memo` unique violation), the error left `extract_scope`, and the
  harness's generic handler appended `component.failed` on the aborted
  transaction (`InFailedSqlTransaction`), hiding the cause. Fix (2.2
  agent): each document's memo + record writes run in a savepoint; a
  `uq_ser_memo` conflict re-reads the sibling's row and marks the document
  `reused`; IOF/ICF share the path with a savepoint per document and no
  other change. Test
  `test_a_sibling_walk_s_memo_row_is_reused_not_a_failed_transaction`.
  **Still exposed (known gap, harness):** `_run_scope_component`'s generic
  `except` appends the failure event on the component's own transaction
  without rolling back, so any DB error in any component reads as
  `InFailedSqlTransaction` in the event log.
- **An option added after the build showed no documents until a rebuild**
  (its search's records got no memberships). Fix (6.1 agent): the read
  models derive such an option's documents and counts from its own
  targeted scope's profile records (DOI-collapsed, labels through the
  resolver) until the next build, and `search_pending` (new, additive) says
  "still searching" apart from "found nothing"; the list shows "searching
  for its evidence…". Test `test_an_added_option_reads_its_own_search_until_the_next_build`.
  S11's "assigns its records against the existing options through the
  component's seeded path" is **not** built: the records are clustered at
  the next rebuild (recorded in `docs/deferred.md`).
- **A rebuild re-proposed the report-derived options under new names**
  (the `(origin, name)` match missed all seven; eight duplicate option
  searches started). Fix: `longlist_suggest_v1` re-pinned with an
  `existing_options` data block and the rule never to propose one again;
  `suggest` passes every existing option (name and description) on every
  run and drops a suggestion whose name or description matches an existing
  option case-insensitively; repeated suggestions are seeds, not entrants,
  so the fan-out starts searches only for genuinely new ones. Tests
  `test_a_rebuild_shows_the_model_the_existing_options_and_drops_repeats`,
  `test_a_first_build_shows_the_model_no_existing_options`.
- The setting facet listed 28 raw source-named settings; capped to the
  commonest eight with a "+N more" toggle (lead).

**D26 reading (the `guidance` seam):** the option searches' queries were
generated from the designs alone; the own option's search (youth guarantee)
screened in 101 of 135 candidates and the report-derived ones 72–175 — the
designs carried enough for the acquire's query generation, so **no
`guidance` argument was added**; the seam stays recorded in `docs/deferred.md`.

### Step-6 exit gate — final tree (2026-09-23)

| Command | Result | Notes |
|---|---:|---|
| `make verify` (full) | pass | backend 3142 passed (18:12, under the live walks); okf 148/0; mypy 388 files clean; ruff clean; build OK; infra 46; prompt-guard 24 unchanged; `drift-check: OK`; frontend 86 files / 784 tests |
| `cd frontend && pnpm e2e` | pass | 19 passed |
| `make prompt-guard` | pass | 24 unchanged after the `longlist_suggest_v1` re-pin |
| `make okf-validate` | pass | 148 concepts, 0 violations (after the spec changes) |

## Checks beyond the build

- **Deterministic tests** — every contract acceptance-check bullet has named
  tests in the phase sections above: the migration round-trip and refusals
  (12), compose by purpose and the spine flag (23), the label resolver (13),
  existence and activity (7), the intervention profile (26 + 1), plan slots
  and the longlist intent (22 + 7 + 7 + 10), inherit and suggest (8 + 12 + 2),
  the skip keys (20), the option search tool, barriers, pool and start
  surfaces (13 + 15), the longlist component and where tried (20 + 20),
  constrain (20), the routes (15), the verbs (16), the stage vocabulary (4),
  the frontend (about 100 new vitest cases across lifecycle, plan start, the
  plan document, the run card, the three longlist surfaces and the thread)
  and 3 new e2e legs.
- **AI evals** — none in this slice (contract: option quality is judge
  behaviour and goes to the eval slice).
- **Manual / API / browser** — the live check above: three longlists at both
  depths, the chat verbs, the buttons, the rebuild, a question over the
  union of scopes; screenshots of the list, grid, card, thread and plan
  document (mock and live).

## End-to-end command

The live check is scripted (session scratchpad `live/drive.py`, a
requests-based driver against the local API with a dev-issuer token). The
backend and frontend were started by hand so the backend did not reload
under the walks:

```
cd backend && uv run --env-file .env alembic upgrade head
cd backend && uv run --env-file .env uvicorn policy_atlas.api.app:create_app --factory --port 8000
cd frontend && VITE_DEV_TOKEN="$(cd ../backend && uv run python -m policy_atlas.api.dev_issuer mint --dir .dev-issuer --sub dev-user --client-id policy-atlas-dev --ttl 14400 | tail -1)" pnpm dev --port 5173
python3 live/drive.py create t1 linked "NEET longlist live check (045, linked, rapid)"
python3 live/drive.py turn t1 "<the opening message with one own option, rapid>"
python3 live/drive.py turn t1 "<the constraints message>"
python3 live/drive.py run t1                      # baseline → paused at the gate
python3 live/drive.py turn t1 "Looks right. Confirm the plan and build the longlist."
python3 live/drive.py poll t1 <opened capability_run_id> longlist
python3 live/drive.py get t1 /longlist longlist; python3 live/drive.py get t1 /options/<id> option
python3 live/drive.py turn t1 "Exclude the wage subsidies option — …" ; python3 live/drive.py turn t1 "Yes, go ahead."
python3 live/drive.py post t1 /options/<id>/include include-button '{}'
python3 live/drive.py turn t1 "Add a youth mentoring scheme: …" ; python3 live/drive.py turn t1 "Yes."
python3 live/drive.py turn t1 "What does the evidence say about youth mentoring schemes …?"
python3 live/drive.py patch t1 patch-requirement '{"scoping": {"constraints": [...]}}'
python3 live/drive.py post t1 /plan/confirm-baseline rebuild '{"artefact_id": "…", "plan_version": 2}'
node live/shots-live.mjs <task_id> <out dir> <prefix>   # headless Playwright screenshots
```

The mock-mode e2e that drives the same surfaces without egress: `cd frontend && pnpm e2e`.

## Diff summary

Eleven deliverables on `task/045-scoping-longlist` in nine gated commits
(`bbad5691` … `ba1b60ad` plus the live-check fixes): one alembic revision
(`c7e2a9f4b1d8`: five tables, two columns, one relaxed column, the
three-branch union view, the widened downgrade refusal and remedy); compose
by purpose with a per-step spine flag; the label resolver and its five
readers; existence and activity on `TaskOut`; the intervention profile as a
third extraction profile on a selection-free path with its own backend seam;
the plan's `your_options` (designs proposed back by `option_design_v1`) and
the default transferability preference; the PICO-shaped longlist intent and
screening criteria (no Where); `inherit` (documents) and `suggest`; the
classify/appraise skip keys computed by `leg_directive`; the option search
as a tool whose implementation is a child walk, the runner's fan-out and
join barriers, the option-search pool and the classify/ingest semaphores;
the two start surfaces, the unattended follow-on and the conversation
lineage rule; six stage keys and client-side beat sentences; the longlist
component on the untouched engine (seeded discovery, themes, lever typing,
coverage, `longlist_result`); constrain (requirements, the three default
screens, guesses, the deterministic in-scope check); the longlist read
models, five routes and the shared apply functions with History events; the
list, grid and card; lifecycle and readers; plan-document states and
Rebuild longlist; the longlist verbs as two-turn actions over the union of
scopes; eight new hash-pinned prompts and one re-pin (`task_agent_scoping_v3`);
the spec changes with the owner's words; ADR 0039's evidence. Every flagged
deviation is numbered in the phase sections (1–48) and in Phase 8.

**Prompt-hash diff (final):** 8 added, 2 changed against `66d79c6f`
(`task_agent_scoping_prompt.py` v2 → v3 with the `setting` flag;
`longlist_suggest_v1` amended after the live check with the
`existing_options` block — same version id, the change is one data block and
one rule, recorded in Phase 8), 0 removed; the ES search prompts, screen,
classify, the IOF and ICF prompts, the gate sort and the clustering callers'
prompts unchanged.

**OpenAPI diff (final, additive):** paths `GET /tasks/{id}/longlist`,
`GET /tasks/{id}/options/{option_id}`, `POST /tasks/{id}/options`,
`POST …/exclude`, `POST …/include`; schemas `LonglistOut`, `OptionSummaryOut`,
`OptionOut`, `LonglistThemeOut`, `LonglistCountsOut`, `WhereTriedOut`,
`RelationOut`, `ExclusionOut`, `EvidenceProfileOut`, `JudgementOut`,
`GuessOut`, `InScopeOut`, `OptionDocumentOut`, `AmbitionBandOut`,
`OptionAddIn`, `OptionExcludeIn`, `OptionIncludeIn`, `OptionAddedOut`,
`OptionDesignOut`, `YourOptionOut`, `YourOptionIn`, `TurnActionOut`; fields
`TaskOut.active_run`, `TaskOut.has_longlist`, `PlanOut.opened_run`,
`TurnDecisionOut.opened_run`, `ScopingPlanDraft.your_options`,
`ScopingPlanPatch.your_options`, `ScopingConstraintOut.setting` and
`.default`, `TaskAgentTurnOut.action` and `TaskAgentTranscriptTurnOut.action`,
`OptionSummaryOut.search_pending`, `RunOut.parent_capability_run_id` and
`.purpose`; the `stage` enums widened by six keys; `TaskAgentTurnKind`
widened with `action`. No path or field removed or retyped.

## Intent & assumptions

- The longlist is a second walk; the option search a child walk; the
  engine untouched; Where out of retrieval; the option is a task-scoped
  entity; the verbs are two-turn; the readers key on existence and
  activity — all as ruled in the contract and ADR 0039.
- Assumed and carried: the longlist walk and its children run under the
  unattended plan so they never pause (D1); the classify skip is narrower
  than S6's words (a stale-rubric inherited document is classified here so
  appraise can re-tier it); repeated suggestions on a rebuild are seeds,
  not entrants.

## Known unverified items

- The peak database connection count under two concurrent longlist walks
  was read from `pg_stat_activity` on the local pool (6 active); the
  production pool is untouched (contract § Constraints).
- The `guidance` seam (D26) was judged from the option searches' screened-in
  counts, not from reading the generated queries one by one.
- The (g) question was answered over the union of scopes but cited two
  longlist-scope documents rather than the added option's own; the
  unit test covers the "document only an option search found" case.
- The concurrency fix (the memo race) and the rebuild-suggest fix were
  tested but not re-driven live; the running server carried the old code.
- Effective concurrency under the per-task event-log sequence (the retry
  cap raised to 32) is bounded but not measured beyond "no failed append".

## Public safety

Contract, rubric, plan, ADR and this file are public-safe. The screenshots
show a NEET longlist built from OpenAlex and Overton metadata (titles,
counts, the model's option names) — public-safe as the design reference.
The saved API responses and the event-log extracts carry document titles
and abstracts' derived fields and stay in the evidence zip, not the repo.
No credentials, prompts with secrets, or raw full text anywhere in the
evidence.

## Review handoff (step-7/8 inputs)

- **Adjudication items** — the 48 numbered deviations above plus Phase 8's
  four live-check fixes; in particular: the event-log retry cap (16), the
  unattended longlist walk (17), the narrower classify skip (11), the added
  option reading its own search until a rebuild (Phase 8, S11 not built),
  the OpenAlex authorship countries in the in-scope check (30), the
  `Remove` control on the default preference (8), the History mechanism for
  option actions (6.1), the thread hiding child walks (Phase 8).
- **Executor provenance (family flip)** — every phase was built by Claude
  agents (deep-reasoner / fast-worker) with the lead reviewing and the
  prompts lead-authored; the Codex lane was unavailable at design time on the
  spend cap; step 7's Codex review is the family flip.
- **Diff-scoping exclusions** — `frontend/openapi.json`,
  `frontend/src/api/gen/types.ts` (generated); `scripts/prompt_hashes.json`
  (pins); the mock fixtures (`frontend/src/mock/*`, bulk data).
- **Live-trace pointers** — the three live tasks in the local dev DB (ids
  above); Langfuse traces per walk under the dev-user subject.
- **Knowledge candidates** (raw, for step 8):
  - A component that appends its failure event on its own aborted
    transaction hides the real error behind `InFailedSqlTransaction`;
    the harness's generic handler should roll back (or use a fresh
    connection) before recording a failure.
  - Concurrent walks on one task share one event-log sequence; each append
    waits for a competing writer's commit. Long component transactions
    that append events (acquire, screen, classify, appraise) serialise
    children on the same task; a per-walk sequence would remove it.
  - A memo keyed per (task, snapshot, fingerprint) races under concurrent
    walks of one task; the writer must treat a unique violation as "reuse
    the sibling's row", inside a savepoint.
  - A rebuild's model step must see what already exists or it will
    re-propose it under new words; `(origin, name)` is not identity across
    two model runs.
  - Compose-time filters are impossible for rows a walk's own earlier step
    creates; the runner's per-step directive seam is the place.
  - A walk's `steering_mode` and the plan row are separable: a walk can run
    unattended under a plan that says otherwise, and the plan row stays
    honest.
  - Making a generated OpenAPI field required (a defaulted boolean) breaks
    every hand-written mock fixture; openapi-typescript treats defaults as
    required.
  - `PlanOut` full-object test expectations must include every optional
    field the contract gains (`opened_run: None`).
  - Study geography read from abstracts is mostly absent: "where tried" on
    a longlist built from abstracts reads *unknown* for most documents; the
    label is honest but thin until full text is read.
  - The setting facet from source-named settings is long-tailed (28 values
    on one longlist); facets over free text need a cap.
  - A single-option confirm part works in `PartCard` unchanged; the
    planner's 2–4 rule is a prompt rule, not a component constraint.
  - The clustering ceiling `clamp(ceil(N/4), 8, 40)` was binding on both
    NEET longlists (383 and 337 units → 40); the unclustered and
    not-an-option counts (168/94, 113/79) are the numbers the owner set the
    targets to measure against (open question 4).
  - The chat's dev token must be minted for the same subject that owns the
    task (`dev-user`), or every write route is 403.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) § Options scoping
longlist (task 045 seams): the on-demand written summary (D15); retrieval
during the baseline pause (D18); the cross-task profile memo (A22); the
option search's `guidance` argument (D26, not needed on the NEET searches);
sheet row A9; the `task_link` uniqueness note for task 5 (A21); the added
option clustered only at the next rebuild (S11); the harness failure event
on an aborted transaction; the per-task event-log sequence; History listing
child-walk events; the plan document's 200-run window. The 044 per-run
fan-out seam is marked closed.
