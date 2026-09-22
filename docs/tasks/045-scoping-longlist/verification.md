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
