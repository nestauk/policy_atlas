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
