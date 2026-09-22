# Plan: 045-scoping-longlist

Deliverables 1–11, decisions D1–D26, the adversarial folds A1–A23 and every
term are defined in [contract.md](contract.md). This plan cites them and adds
nothing to scope. It was written against the as-built code at `19776b65`
(two seam dossiers, 2026-09-22), not against the contract's own claims.

> **Status:** drafted 2026-09-22 · lead. Plan-stage adversarial review:
> _pending_ (fallback lane, `deep-reasoner`, read-only, unless the Codex
> spend cap is raised; findings reported to the owner before any fold, as
> at the contract stage). **Seven calls the lead made where the code forced
> a choice the contract does not settle are listed in § Open at the plan
> gate** for the owner. Plan approved (before implementation): _pending ·
> owner_. **ADR 0039 is drafted at step 4 of this design phase, after plan
> approval and before any build phase** (044 X15); Phase 8 adds evidence and
> the sign-off date.

Executor marks per AGENTS.md § Agent-side model routing; every `lead` mark
carries its reason. **Owner ruling 2026-09-04 stands:** judgment-bearing
phases go to `deep-reasoner`, not `codex`; the family flip happens at step 7
when Codex reviews the diff. No phase is marked `codex`. Taste-bearing
frontend surfaces get a `lead` polish pass after a delegate lands the
structure (owner ruling 2026-09-05). Prompt-bearing work is `lead` and always
the first sub-phase of its phase, so the delegate's brief imports a real
artefact (044 P6).

**Verify gates.** Full `make verify` at Phase 0 (build-open baseline), Phase
1 (the revision — schema class), Phase 4 (the runner, child walks and the
two start surfaces), Phase 7 (the turn route and the answer core) and Phase
8 (step-6 exit). Phases 2, 3, 5 and 6 close on `make verify-fast` **plus
`make prompt-guard` and `make drift-check`** (044 P7) plus `make
frontend-verify` where the frontend changed; `pnpm e2e` wherever a route or
the thread changed (Phases 3, 6, 7). **One green commit per phase.**

**Spec changes** (contract § Spec changes, items 1–11) are applied in Phase
8 with the owner's words quoted, except item 10 (the decision sheet), which
is applied at plan approval so the build starts from a sheet whose task-2
rows are ruled.

## Decisions fixed here (lead seam design)

S1. **Compose by purpose.** `CapabilitySpec.compose` becomes
`Callable[[Any, str | None], ComposedChain]` and
`compose_plan(capability, plan, *, purpose: str | None = None)`
(`capability_registry.py:167`). The purpose is **the intent record's
`purpose` column**, so it is recoverable on every path: the fresh walk reads
it in `_open_capability_run`'s transaction (`runner.py:5299`, which already
reads the task's capability) and passes it to the compose call at
`runner.py:732`; the two resume paths (`continuation_state.py:173`,
`api/continuation.py:1441`) read it from the walk's `evidence_scope_id`.
The five ES call sites pass nothing (`compose(plan, purpose)` ignores it)
and `test_capability_registry.py`'s AST scan stays green. `compose_scoping`
returns three chains: `None | "baseline"` → today's six steps; `"longlist"`
→ `inherit → suggest → option_searches → acquire → screen_abstract →
classify → appraise → ingest_full_text → extract_interventions → longlist →
constrain`; `"targeted"` → `acquire → screen_abstract → classify → appraise
→ ingest_full_text → extract_interventions` (the child walk; its intent is
the entrant's design, its `record_cap` the option-search target). Directive
deltas: the longlist and targeted acquires carry `record_cap` from
`LONGLIST_ACQUISITION_TARGETS` / `OPTION_SEARCH_TARGET` and the evidence
restrictions as `filters` (`search_loop.py:599` admits only `depth ·
filters · guidance · record_cap`, so nothing new); `screen_abstract` carries
the longlist criteria (target unit, outcomes, setting when required, **no
place**), composed under the 2,000-character ceiling. **Spine membership**
(A6): `ComponentStep` gains `spine: bool | None = None` (`task_plan.py:976`,
`extra="forbid"`; the chain is rebuilt from the plan on resume, so the flag
survives a park); `runner.py:1322` reads `step.spine` and falls back to
`SPINE_COMPONENTS` when `None`, so every ES chain is unchanged; the scoping
compose sets `spine=False` on `suggest` and `option_searches` only.

S2. **The option search is a tool; its implementation is a child walk**
(D6, D26, A1). `runtime/option_search.py::run_option_search(engine, *,
task_id, plan_row, design: OptionDesign, parent_capability_run_id: UUID |
None, backends, user_id) -> UUID`: in one transaction, insert the targeted
intent record (`purpose="targeted"`, `intent=design.as_intent()`,
`plan_id` = the confirmed version, `context={"option_id": …}`), then submit
`run_plan(engine, task_id=…, evidence_scope_id=targeted, plan=…, plan_id=…,
plan_version=…, backends=…, io=ParkIO(), session_id=task_id,
parent_capability_run_id=…)` to the **option-search executor** and return
the child's `capability_run_id` from `_await_new_run`'s pattern. `run_plan`
and `_run_plan_impl` gain `parent_capability_run_id: UUID | None = None`,
threaded into `_open_capability_run`, which writes the new column. **The
cross-walk bound** is `runtime/walk_pool.py`: a process-wide
`ThreadPoolExecutor(max_workers=OPTION_SEARCH_WIDTH)` (4) **separate from
`app.state.run_executor`** — the walk executor has two workers
(`settings.run_executor_max = 2`, `api/app.py:294`) and a parent that waits
on children submitted to its own pool would deadlock. The capacity gate in
`create_run` (`runs.py:160`) counts only walks with `parent_capability_run_id
IS NULL`, so a parent's children never refuse another task's walk (§ Open,
item 2). The `option_searches` step (spine `False`) reads the entrants
minted by `suggest` and the plan's own options, caps them at
`OPTION_SEARCH_CAP` (15; the user's and the report-derived first), calls
`run_option_search` for each and **returns without waiting**, recording the
child ids in its summary; the `longlist` step **joins** first: it waits for
every child of this walk to reach a terminal status (bounded by
`OPTION_SEARCH_JOIN_TIMEOUT`, after which the remaining children are
abandoned as `interrupted` and counted as failed entrants). A child's
`failed` is a `degraded` parent (`step_outcomes` gains a synthetic `skipped`
outcome per failed child at the join), never a `failed` one. The two callers
of the tool: the `option_searches` step and the verb *add* (S11), which
passes `parent_capability_run_id=None`.

S3. **The two start surfaces and the unattended follow-on** (D1, A2, A23).
`api/longlist_start.py::open_longlist_walk(engine, *, task_id, plan_row,
backends, executor, user_id) -> UUID`: under `runs.py`'s `_dispatch_lock`,
the same admission as `create_run` (no `running | paused` walk, the
reservation, the capacity gate), then in one transaction mint the longlist
intent record (`purpose="longlist"`, `intent=compile_longlist_intent(plan)`,
`plan_id` = the confirmed version) and `_dispatching_tasks.add`; submit
`_dispatch_run(..., evidence_scope_id=longlist_scope)` (`runs.py:62` gains
the override) to the walk executor; `_await_new_run`; discard. Callers:
(a) **the gate**: `_persist_confirm_plan` beside `_persist_change_plan` at
`api/continuation.py:241` — records the decision (`response="continue"`,
`extra={"action": "confirm_plan", **_baseline_gate_decision(...)}`), sets
the baseline walk `succeeded` with `run.finished{reason: confirm_plan}`
(the walk's last step has run, so nothing is skipped), returns
`AnswerResult(..., continuation_requested=False, follow_on="longlist")`
(a new optional field); the two post-commit callers — `check_ins.py:236`
and `task_agent.py:1073 _resume_walk` — call `open_longlist_walk` when
`follow_on` is set (they already hold `executor` and `backends`); the card
route stays `204` (A23's optional field reaches the chat turn and
`confirm_baseline` only, as the dossier found). (b) **`confirm_baseline`**
(`task_agent.py:1843`): gains `executor` and `backends` deps; after minting
the confirmed version it calls `open_longlist_walk` with the freshly
re-read row; `PlanOut` gains `opened_run: LatestRun | None = None`. **The
"confirmed but no walk" state** (dossier flag 7) is resolved on the
idempotent path: when the current version is already confirmed and no
longlist walk exists for it, the route opens one rather than returning
unchanged. (c) **Unattended** (A2): `_resolve_baseline_gate_unattended` has
no executor, so the follow-on lives where the walk ends: `RunPlanOutcome`
gains `follow_on: str | None`; the gate handler sets it on the state when
it records the standing default; `_dispatch_run` (the worker thread) calls
`open_longlist_walk`'s inner mint-and-run **inline** after the baseline
`run_plan` returns — no executor hop, the same thread continues into the
second walk. Tests: the pre-insert race between `confirm_baseline`, the
gate and `POST /runs` yields one walk; unattended opens the second walk
with the standing default recorded.

S4. **The revision** (one alembic revision, reversible; contract §
Constraints). Adds `option` (`option_id` PK, `task_id` FK, `name`,
`description`, `design` JSONB, `design_version` int default 1, `outcomes`
JSONB, `origin` text CHECK `clustered | suggested | from_evidence_search |
added_by_you`, `state` text CHECK `included | excluded`, `exclusion` JSONB
nullable `{constraint, reason, by}`, `no_in_scope_evidence` bool,
`primary_lever_type`, `secondary_lever_types` JSONB, `lever_none_fits_reason`
nullable, `taxonomy_version`, `ambition` text nullable, `ambition_reason`,
`created_by_run_id`, `created_at`, `updated_at`; unique `(option_id,
task_id)` as the composite-FK target), `option_membership` (`membership_id`
PK, `option_id`, `task_id`, `unit_kind` CHECK `interventions | iof | icf`,
`unit_id` (the finding/record id), `unit_task_id` (the linked task for
inherited findings), `task_source_snapshot_id` nullable (own rows only),
`assignment_reason`, `design_feature_not_stated` bool, `assigned_by_run_id`;
composite FK to `option`; unique `(option_id, unit_kind, unit_id)`),
`option_relation` (`relation_id`, `task_id`, `from_option_id`,
`to_option_id`, `kind` CHECK `part_of | variant_of`, `created_by`; both
composite FKs), `longlist_result` (`longlist_result_id` PK, `task_id`,
`evidence_scope_id`, `run_id`, `plan_version`, `themes` JSONB, `coverage`
JSONB, `judgements` JSONB, `guesses` JSONB, `counts` JSONB, `provenance`
JSONB, `created_at`; `fk_llr_scope_task`, `fk_llr_run_task`, unique
`(evidence_scope_id, run_id)` — the `characterisation_result` shape),
`intervention_profile_record` (`record_id` PK, `task_id`,
`extraction_record_id` with `fk_ipr_record_task` → `uq_ser_id_task`,
`intervention` NN, `role` CHECK the five values, `design_features` JSONB,
`is_bundle` bool, `components` JSONB, `outcome`, `population`, `setting`,
`study_geography`, `study_design`, `covers_no_intervention` bool,
`field_coverage` JSONB, `grounding` JSONB, `created_at`; `ix_ipr_record`),
`task_link.option_id` (nullable, composite FK `(option_id, target_task_id)`
→ `option(option_id, task_id)`), `capability_run.parent_capability_run_id`
(nullable, composite self-FK `(parent_capability_run_id, task_id)` →
`uq_capr_id_task`, `ix_capr_parent`); relaxes
`extraction_result.selection_run_id` to nullable (the composite FK
`fk_exr_selection` stays: MATCH SIMPLE passes a NULL); drops and recreates
`finding_reference_union` with a third branch (`'interventions'::text AS
kind`, `NULL::text AS outcome`-style nulls where the record lacks a column).
Downgrade: refuses while any `capability_run` row has a `purpose` of
`longlist` or `targeted` on its scope (the 044 A5 predicate widened),
restores NOT NULL (refusing while a null row exists), restores the
two-branch view, drops the columns and tables. The operator remedy script
from 044 gains the walk kinds. The prompt-hash guard needs nothing.

S5. **The label resolver** (D23). `options_scoping/labels.py::
labels_for_snapshots(conn, *, task_id, tss_ids) -> dict[UUID, DocumentLabels]`
with `DocumentLabels(evidence_type: str | None, quality_score: int | None,
rubric_version: str | None, provenance: Literal["own", "inherited",
"absent"], source_task_id: UUID | None, source_run_id: UUID | None)`. Own
rows first (`latest_row_by_id` over the task's classification and appraisal
rows, the pattern at `repository.py:705-727`); for the rest, one query
through `task_link` (target = this task) → the source task's
`task_source_snapshot` sharing `source_snapshot_id` → its classification and
appraisal rows **in the pinned run's scope** (`capability_run.evidence_scope_id`
of `source_capability_run_id`); `absent` otherwise. **Rubric rule**: an
inherited appraisal whose `rubric_version` differs from the current rubric
is returned with `quality_score=None, provenance="inherited"` and a
`stale_rubric=True` marker; the appraise skip (S6) then leaves that row to
appraise, which re-appraises deterministically. Readers: the longlist's
coverage; `evidence_page`, `landscape_out`, `artefact_out` citations and
`source_dossier_out` (the four `latest_row_by_id` sites, one helper);
`_resolve_citation_sources` in the answer core. Output field names are
unchanged (`evidence_type`, `appraisal_tier`), so the Sources table needs
no change (dossier D6).

S6. **Inherited documents and the classify/appraise skip** (A3, A4, A7).
`inherit` is a **step of the longlist walk** (spine, first), not a
confirm-time write, so its rows carry `run_id` and "created by an inherit
run" is literal (data-model § Corpus). `runtime/inherit.py::inherit_documents
(conn, *, task_id, run_id) -> InheritSummary`: for each link, insert
`task_source_snapshot` rows for the source task's screened-in documents of
the pinned run that this task lacks (`origin="acquired"`, `run_id` = the
inherit run, `full_text_snapshot_id` and status copied from the source row
so ingest does not refetch), idempotent on `uq_task_source_snapshot`. The
skip: `leg_directive` (`runner.py:608`, the named directive-authoring
seam, V1 identity) gains a scoping branch that, at the `classify` and
`appraise` steps of a longlist walk, calls the resolver and writes
`{"classify": {"skip_task_source_snapshot_ids": [...]}}` /
`{"appraisal": {"skip_task_source_snapshot_ids": [...]}}`; `classify`
gains a fail-closed directive parser with that one key
(`assess/classify.py`, today reads none) and `appraise`'s parser
(`appraise.py:194`) gains the key; both add `~in_(skip)` to their
selection queries. Behaviour-preserving when absent (existing tests).

S7. **The intervention profile on a selection-free path** (D3, D24, A5,
A10). `extract_interventions` is a **new registry component** (`run_spec.py`:
`requires: ["evidence_scope_id"]`; a harness node, conditional edge and
`→ finish` edge; `registry_component_for` identity), whose handler calls
`extract_scope(..., profiles=(INTERVENTIONS_PROFILE_ID,), selection_run_id=
None)`. In `extract.py`: `ExtractContext.selection_run_id: UUID | None`;
`_load_selection` is bypassed when `None` in favour of
`_screened_in_docs(conn, task_id, scope_id)` (the `characterise.
screened_sources` query projected to `{tss_id, text_basis}`, which is all
`_load_docs` needs); `_parse_extraction_directive`'s IOF-mandatory rule
(`extract.py:1594`) becomes "at least one known profile"; `_write_rollup`
writes `selection_run_id=None`. The profile bundle: `_interventions_profile`
beside `_iof_profile` / `_icf_profile` (`extract.py:1470-1510`), with
`interventions_records.py` (`PROFILE_ID = "os_interventions_base_v1"`,
`SCHEMA_VERSION = "interventions_v1"`, `InterventionsRecordWire` — one
document → many records, the five roles as a Literal, `design_features:
list[str]`, `is_bundle`, `components`, `covers_no_intervention` at document
level), `extract_interventions_prompt.py` (`PROMPT_VERSION =
"extract_interventions_v1"`, the abstract as the text basis — the profile
reads `title + abstract` from metadata, never the full text, so
`text_basis` on the record is `abstract_only` by construction), a
fingerprint function on the `extraction_fingerprint` pattern, no vetter
(nothing to vet: no effect claim), quote anchors located in the abstract by
`quote_verify.locate_unique_span`. Writes `intervention_profile_record`
rows; memo through `source_extraction_record` as today. `KNOWN_PROFILE_IDS`
gains the id; `_selected_profiles` keeps its order rule.

S8. **The longlist component** (D4, D5, D8, D10, D11, A9).
`options_scoping/longlist/longlist.py::longlist_scope(conn, *, task_id,
run_id, context: LonglistContext, backend: LonglistBackend) -> dict`. Units:
`intervention_profile_record` rows of the longlist scope **and every
targeted scope whose walk is a child of this walk** (through
`parent_capability_run_id`), minus `role == "comparator"`; plus, per link
whose pinned walk ran `extract`, the source task's IOF/ICF rows of that
walk through `finding_reference_union` (unit kind `iof | icf`, `unit_task_id`
= the source). Each unit's payload is the component's projection
(`intervention`, `design_features`, `role`, `outcome`, `setting`,
`study_geography`, a bounded quote). **Seeded run**: the seeds are the
entrants' option rows (from `suggest` and the plan's own options; on a
rebuild, every existing option); discovery is one call with
`build_discovery_messages(units, seeds, max_labels)` asking for **new**
options beyond the seeds (the engine's `discover` protocol, wrapped in a
`LonglistClusteringBackend` on the `_CharacteriseClusteringBackend` pattern
— `characterise.py:180`); the label set is seeds ∪ discovered, validated by
`validate_discovered_labels`; assignment runs through
`call_budget_for_unit_count` → `run_first_assignment_round(labels=…)` →
`validate_assignments` with the component's own repair round; the
ceiling `max_labels = clamp(ceil(N/4), 8, 40)` counts seeds. The engine is
untouched. The assignment output is one label per unit (a document with
several records lands in several options); the discovery output may also
label a unit `not an option`, and the component keeps both buckets
(`residual_label="unclustered"`, `unresolved_policy="residual"`, plus its
own `not_an_option` label). Each membership row carries the assignment's
one-line reason and the `design_feature_not_stated` flag the assignment
returns per unit. Option rows: seeds map to existing rows; discovered
labels mint rows (`origin="clustered"`, design v1 from the discovery
output); a discovered bundle mints a package and `part_of` rows. **Themes**:
a second `cluster_units` run (unseeded) over the options as units, labels =
themes with descriptions, stored run-local in `longlist_result.themes`.
**Typing**: one batched call per ~20 options → `{primary, secondary[],
runner_up, runner_up_reason, none_fits_reason | None, ambition,
ambition_reason}` against `lever_types.py::LEVER_TYPES` (versioned
constant; `TAXONOMY_VERSION`). **Coverage** (deterministic, `coverage.py`):
per option, documents by evidence type and tier (through S5, Unknown and
Non-evidence bucketed, `absent` shown as "not rated"), by role, where
tried (`where_tried.py`: study geography → `COUNTRY_GROUPS` → *United
Kingdom · comparable systems (OECD) · other* against `plan.where`),
populations, settings, outcomes; DOI collapse for counts (`_metadata_text
(metadata, "doi")`, normalised); flagged members counted. Written last, the
010 pattern: `longlist_result` row + option and membership rows in the
component transaction. On a rebuild (D14): seeds = existing options; a seed
with no member keeps its row and `coverage` says zero; user state
(`state`, `exclusion`) is never touched by the component.

S9. **Constrain** (D9, D21, D22). `options_scoping/constrain/constrain.py::
constrain_scope(conn, *, task_id, run_id, context, backend)`: reads the
options and `longlist_result.coverage`; per option one judgement call
(batched ~10 per call on the judgment model) over the plan's `requirement`
constraints plus the three default screens, returning per constraint
`{verdict: passes | breaks | cannot_check, reason}`; a `breaks` on a
requirement or a default screen sets `state="excluded"` with
`exclusion={constraint, reason, by: "constrain"}` unless the user has
already set the state (user state wins, ruling 5's "screens still run and
show on it"); `distinct` is never applied to an option with a `part_of`
relation; per `preference` constraint except the transferability
preference, one capped guess `{constraint, guess, reason}` into
`longlist_result.guesses`; the deterministic in-scope check (`in_scope.py`:
publication country and year from metadata against the plan's
`country_group` and years; the resolver's country read at
`repository.py:205-221` extracted to a shared helper) sets
`no_in_scope_evidence` when no member document passes. Judgements keyed by
`(option_id, design_version)` in `longlist_result.judgements`.

S10. **Suggest** (D7, A15). `options_scoping/suggest/suggest.py::
suggest_options(conn, *, task_id, run_id, context, backend)`: one call on
the judgment model over the plan (question, intended change, target unit,
outcomes, Your context, `your_options`), the baseline's sections (the
pinned artefact's blocks through `inherit._report_markdown`'s pattern) and
the linked reports' bodies (`inherit._report_markdown` per link), with
`LEVER_TYPES` as a checklist; output `{name, description, design_features,
outcomes_served, source: model | linked_report(section)}` up to
`SUGGEST_BOUND` (10). Mints option rows (`origin="suggested"` or
`"from_evidence_search"` with the section in `provenance`), and the plan's
own options as `origin="added_by_you"` (design from `your_options[].design`,
proposed back at planning time by `option_design_v1`). No profile record is
ever written from report text.

S11. **The longlist verbs** (D13, A8, A14). `_Reserved` (`task_agent.py:653`)
gains `longlist: LonglistSurface | None`, read in the same locked
transaction when no walk is active and a `longlist_result` exists;
`create_task_agent_turn` gains a dispatch arm beside the gate arm
(`:1166`) calling `api/longlist_turns.py::dispatch_longlist_turn`, the
`_dispatch_gate_turn` pattern: `agent.sort_longlist_turn(utterance,
options)` (`runtime/longlist_verbs_prompt.py`, `LonglistVerbWire{kind:
question | add | exclude | include_again | other, option_id, reason,
design_words}`, on `AGENT_TRIAGE_MODEL` like the gate sort, stub queue in
`StubAgentBackend`). **Two turns per verb** (substance is never silent):
the sorting turn replies with the proposed action in words ("Exclude
*Youth guarantee with sanctions* because we can't do that?") and, for
*add*, the design `option_design_v1` proposed back; it stores the pending
action in the row's `task_agent_state`; the next turn that confirms
(`confirmTarget` — the 044 button-confirm pattern — or a sorted `other`
that the prompt reads as assent) applies it: `exclude` / `include_again`
write the option state and a History event; `add` mints the option
(`origin="added_by_you"`) and calls `run_option_search` with no parent,
then assigns its records against the existing options through the
component's assign-only path. The applied turn is `kind="action"`
(`TaskAgentTurnKind` widened; `TurnActionOut{verb, option_id, label,
capability_run_id: UUID | None}` — `TurnDecisionOut` cannot be reused, its
`check_in_id` is required). `question` → the answer core over the union
of scopes: `ResolvedRunScope` gains `extra_scope_ids: tuple[UUID, ...]`
(the child walks' targeted scopes, resolved by `parent_capability_run_id`);
`build_retrieval_scope` takes `scope_ids` (the four `== scope_id` sites at
`synthesis_tools.py:1262-1274` become `.in_()`), `make_lookup_reader`
likewise; `RetrievalUnitCapError` is caught on the verbs path and answered
honestly ("too many documents to search in one question"). The ordinary
chat re-points by itself (`resolve_terminal_run_components` takes the
latest walk). The button routes (`POST /options`, `/exclude`, `/include`)
call the same three apply functions.

S12. **Read models, routes, progress** (deliverable 11, A7, dossier flag 1).
`api/contract/read_models.py`: `LonglistOut{run_id, plan_version, counts,
themes: [ThemeOut{theme_id, name, description, option_ids}], options:
[OptionSummaryOut]}`, `OptionOut` (the card: design, lever, ambition,
outcomes, where_tried, coverage, judgements, guesses, provenance,
relations, documents), exported through `api/contract/__init__.py`;
`repository.py::longlist_out` / `option_out` on the `artefact_out` idiom
(latest `longlist_result` by `created_at DESC`; 404 when absent);
`api/routers/longlist.py` with `_readable` for the two GETs (public-readable
like the artefact) and `accessible_task(write=True)` for the three POSTs
(owner-only, ADR 0033 § write grade). `TaskOut` gains `has_longlist: bool`
computed in `task_out` with one `EXISTS` (no N+1 on the listing).
**Progress**: `StageKey` (`api/contract/sse.py:25`), `PlanStageKey`,
`STAGE_PRESENTATION` and `STAGE_BY_REGISTRY` gain `inherit`, `suggest`,
`option_searches`, `extract_interventions`, `longlist`, `constrain` — an
additive Literal widening on a pinned vocabulary (§ Open, item 3); the
component summaries carry counts and `_frames_for_row` renders the blurb
with them ("8 options suggested", "12 of 15 option searches finished", "59
abstracts read", "20 options in 6 themes", "2 excluded"); child walks
publish their own frames under their own run ids and the parent's
`option_searches` completion frame aggregates. No new event kind; the
thread's `RunBlock` already renders stage frames.

S13. **Frontend** (deliverable 9, A7). `views/longlist/LonglistView.tsx`
(list: header counts, Show filter, setting and where-tried facets, theme
sections, option rows; the scoping-pass label; the Do nothing sentence
linking to the baseline view), `LonglistGrid.tsx` (rows `LEVER_TYPES` from
the read model's taxonomy, columns the three ambition bands, tiles), a view
switch in `ArtefactView` (Baseline · Longlist · Report unavailable) keyed on
`useLonglist(taskId)` (the `useArtefact` shape, 404 → `null`), `OptionCard.tsx`
at `routes.tsx:113` (`/tasks/:taskId/options/:optionId`, wrapped in
`LifecycleRoute tab="result"`); `lifecycle.ts` `TabOptions` gains
`hasLonglist` and `openTabs` treats it like `hasBaseline`; `LifecycleRoute`
and `AppShell` fetch `useLonglist` under the same loading fence as the
artefact; `planStart.ts` gains `longlist_built` and `rebuild_or_keep`
dispatched **before** `confirmed`, keyed on `task.has_longlist` and the
plan version the longlist was built from (`LonglistOut.plan_version` versus
`currentVersion`), and `SCOPING_CONFIRMED_LINE` becomes "Longlist built · N
options" (with N from the read model) or, while the walk runs, "Building
the longlist"; `store/thread.ts` `taskAgentTurnKind` gains `"action"` and
`DurableTurn` a branch reusing `DecisionLine`; `mock/fixtures` and
`mock/api.ts` gain the longlist, an option and the three POST handlers so
`pnpm e2e` can drive it. Taste-bearing: the list, grid and card get a
`lead` polish pass with the impeccable skill.

S14. **ADR 0039** records: the longlist as a second walk and the child
walk with `parent_capability_run_id`; the option search as a tool with two
callers; the cross-walk bound and the capacity rule; compose by purpose
from the intent record; the spine flag; the option entity, membership and
relation tables and `longlist_result`; the intervention profile as a third
extraction profile on a selection-free path (E1/F2/F3 edited); the label
resolver and the rubric rule; the longlist verbs as two-turn actions; the
stage vocabulary widening; the revision and its rollback commands and the
operator remedy.

## Open at the plan gate (lead calls the owner should see)

1. **`inherit` as the first step of the longlist walk** (S6), so inherited
   rows carry an inherit run id, rather than a write at confirm time.
2. **Capacity counts parentless walks only** (S2): child walks never make
   another task's `POST /runs` refuse with `capacity`; the option-search
   pool is the only bound on children.
3. **The SSE stage vocabulary widens by six keys** (S12): additive on the
   wire, but `StageKey` is a pinned Literal the spec calls locked.
4. **Verbs are two turns** (S11): propose, then confirm; the same pattern as
   the gate's decision-with-carried-text, never one-shot.
5. **`TaskAgentTurnKind` gains `"action"`** (S11) instead of reusing
   `"decision"`, because `TurnDecisionOut.check_in_id` is required.
6. **The unattended follow-on runs inline in the worker thread** (S3),
   after the baseline walk returns, rather than through an executor hop.
7. **Classify and appraise gain one optional directive key each** (S6),
   fail-closed, behaviour-preserving when absent — an ES component grammar
   extension the surface map's "unchanged code" row must admit.

## Phase 0 — Build-open baseline — `lead` (inline)

Full `make verify` on `task/045-scoping-longlist`. Never build on a red base.
Apply contract § Spec changes item 10 (the decision sheet's task-2 rows,
the owner's words) and commit it with the ADR (step 4) before Phase 1.

## Phase 1 — Revision, registries, compose by purpose, spine flag, resolver (deliverables 6/8, 3 part) — `deep-reasoner`

Brief (S1, S4, S5): the alembic revision with its round-trip and the
downgrade refusal; `ComponentStep.spine` and the runner's fallback read;
`compose_plan(..., purpose=)` with the purpose read from the intent record
on the fresh and both resume paths, the three scoping chains as data (the
new components registered in `run_spec.py`, `harness.py`, `task_plan.py`
with stub handlers that raise `NotImplementedError` until their phases —
the graph must build); the label resolver with its rubric rule and the five
readers switched to it; the operator remedy script extended. Tests: the
contract's migration and pool bullets; compose by purpose (ES sites
unchanged; a parked longlist walk resumes on the longlist chain); the
spine flag (an ES chain's statuses unchanged; a `spine=False` step's
failure degrades); the resolver (own · inherited · absent · stale rubric;
Sources shows an inherited tier; a link grants no read of labels without
the link). Done when full `make verify` is green and `make drift-check`
after `openapi-sync` is green (additive: `has_longlist` may land here).

Gate: **full `make verify`**. Commit.

## Phase 2 — The intervention profile (deliverable 5)

2.1 **`extract_interventions_v1` — `lead`.** Reason: prompt-bearing. The
profile prompt over title and abstract: the interventions covered, each
with role (the five values, with the comparator rule stated), stated
design features, bundle and parts, a quote anchor; document-level setting,
population, outcome family, study design, geography **from the text**, and
`covers_no_intervention`. Re-pin. A stub backend for tests.

2.2 **Selection-free path and the profile bundle — `deep-reasoner`.** S7
exactly. Tests: the contract's intervention-profile bullet; `extract_scope`
with `selection_run_id=None` over a scope's screened-in set; the IOF/ICF
path byte-identical (existing tests, plus a pinned-fingerprint test for
IOF and ICF); a document already profiled in this task is served by memo
across the longlist and a targeted scope; Non-evidence profiled; the union
view returns the three kinds.

Gate: `make verify-fast` + `make prompt-guard` + `make drift-check`. Commit.

## Phase 3 — Plan slots, intent, the Task Agent for scoping v3 (deliverable 2)

3.1 **`task_agent_scoping_v3` and `option_design_v1` — `lead`.** Reason:
prompt-bearing. The one-time question for *Options you already have in
mind*; the default transferability preference explained once and shown in
the constraints; the design proposed back from the user's words (shared
by the plan slot and the verb *add*); the baseline-state line extended
with the longlist states (`_baseline_state`, `task_agent.py:276`). Re-pin
both.

3.2 **Plan model, intent, plan document — `deep-reasoner`, then `lead`
polish.** `ScopingPlan.your_options[]`, the default preference minted by
`build_scoping_plan` and following Where until edited, `SCOPING_STEPS`'
Longlist blurb; `compile_longlist_intent` and the longlist screening
criteria (no place; setting when required); the wire and API projections
(`ScopingPlanDraftWire`, `ScopingPlanDraft`, `PlanOut`); the plan document's
new slot with Edit and the preference row. Tests: the contract's plan-and-
intent bullet. Reason for the `lead` pass: the plan document is
taste-bearing.

Gate: `make verify-fast` + `make prompt-guard` + `make drift-check` + `make
frontend-verify` + `pnpm e2e` (the plan document changed). Commit.

## Phase 4 — The walk: inherit, suggest, option searches, the start surfaces, progress (deliverables 1, 3, 4)

4.1 **`longlist_suggest_v1` — `lead`.** Reason: prompt-bearing. Suggestions
from the plan, the baseline and the linked reports with the lever-type
checklist; the bound; the source labelled per option; a specified design
each. Re-pin.

4.2 **Inherit step and suggest component — `deep-reasoner`.** S6's
`inherit_documents` as the `inherit` component; S10's `suggest`; the
`leg_directive` scoping branch and the classify/appraise skip keys. Tests:
the contract's suggest bullet and the inherit half of the pool bullet; the
skip keys behaviour-preserving when absent.

4.3 **Option search tool, child walks, the cross-walk bound, the two start
surfaces, the unattended follow-on — `deep-reasoner`.** S2 and S3 exactly.
Tests: the contract's start and option-search bullets (the pre-insert race;
the capacity rule; width 4 under a concurrency test; a failing child
degrades; the join timeout; `confirm_baseline` re-opens a missing walk on
the idempotent path; unattended opens the second walk).

4.4 **Stage vocabulary and progress beats — `fast-worker`.** S12's six stage
keys, presentation strings and registry map; the component summaries'
counts rendered in the frames; child frames under their own run ids.
Tests: the six beats appear at their boundaries on a stub longlist walk.

Gate: **full `make verify`** (the runner, the fences and the dispatch lock
changed). Commit.

## Phase 5 — Longlist and constrain (deliverables 6, 7)

5.1 **`longlist_cluster_v1`, `longlist_theme_v1`, `lever_typing_v1`,
`constrain_v1` — `lead`.** Reason: prompt-bearing. Seeded discovery and
assignment (one option per record; the `not an option` label; the reason
and the `design_feature_not_stated` flag per unit); theme discovery and
assignment over options; lever typing with `none fits`, runner-up and the
ambition tag with its justification; constraint judgement with the three
default screens and the capped guess wording. Re-pin all four; stubs.

5.2 **Longlist component — `deep-reasoner`.** S8 exactly, including
`lever_types.py`, `coverage.py`, `where_tried.py` and the rebuild path.
Tests: the contract's longlist bullet; `clustering_engine.py` unchanged by
diff; characterise and group tests unchanged; the seeded run keeps seed
ids; the rebuild keeps ids and user state.

5.3 **Constrain component — `deep-reasoner`.** S9 exactly. Tests: the
contract's constrain bullet, with the inherited-document fixture for no
in-scope evidence.

Gate: `make verify-fast` + `make prompt-guard`. Commit.

## Phase 6 — Read models, routes and the longlist views (deliverables 9, 11)

6.1 **Read models and routes — `deep-reasoner`.** S12's contract models,
repository functions, the five routes with their access grades,
`TaskOut.has_longlist`; `make openapi-sync`. Tests: the contract's API
bullet (org-scoped read; a link grants no read of options; the additive
diff).

6.2 **List, grid and card — `fast-worker` structure, then `lead` polish.**
S13's views, `useLonglist`, the view switch, the route, the mock fixtures
and handlers. Reason for the `lead` pass: the three surfaces are the
product's first options surfaces; typography, density and copy follow the
ES report's design language (OS capability § Product surface) with the
impeccable skill.

6.3 **Lifecycle, plan document states, thread — `deep-reasoner`, then
`lead` polish.** `TabOptions.hasLonglist` with the loading fence,
`planStart.ts`'s two states ahead of `confirmed` and the replaced line,
the thread's `action` turn branch. Tests: the contract's frontend bullet;
`lifecycle.test.ts` and `planStart.test.ts` extended.

Gate: `make verify-fast` + `make drift-check` + `make frontend-verify` +
`pnpm e2e`. Commit.

## Phase 7 — The longlist verbs and the answer core over several scopes (deliverable 10)

7.1 **`longlist_verbs_v1` — `lead`.** Reason: prompt-bearing. The sort
(question · add · exclude · include again · other) with the pending-action
confirmation reading; the propose-back wording. Re-pin; stub.

7.2 **Dispatcher, two-turn actions, answer core union — `deep-reasoner`.**
S11 exactly, including the button routes sharing the apply functions and
the `RetrievalUnitCapError` catch. Tests: the contract's verbs bullet; the
gate-turns tests unchanged; a question answered with a citation from a
document only an option search found.

Gate: **full `make verify`** + `pnpm e2e`. Commit.

## Phase 8 — Live check, evidence, specs, ADR evidence, step-6 exit — `lead`

Reason: browser-driving the pinned live check, writing the evidence, the
spec edits with the owner's words and the ADR are adjudication-adjacent.

1. The contract's live check (a)–(g) at rapid depth, plus one standard
   build for the numbers; the stage split, the funnel counts, the
   where-tried grouping, the profile's per-document cost and the option
   search's per-entrant cost; the D26 test of the queries on the NEET
   option searches (add `guidance` only if they missed what the design
   meant, and say so); screenshots.
2. `verification.md`: command tails; the migration round-trip; the
   OpenAPI diff; the prompt-hash diff (eight new, one re-pin); the three
   live longlists' numbers and the qualitative reading; the cross-walk
   bound's measured effect; review-lane dispositions; deferred deltas;
   known gaps.
3. ADR 0039 (S14, drafted at step 4): add the evidence links and the
   measured numbers.
4. Spec changes items 1–9 and 11 with the owner's words; `docs/specs/log.md`
   lines; `docs/deferred.md`: the on-demand summary, D18, the cross-task
   profile memo, the `guidance` seam if not built, sheet row A9, the
   `task_link` note, and the 044 fan-out seam marked closed.
5. Full `make verify` (step-6 exit).

Gate: **full `make verify`**. Commit. **Stop.** Review runs in a fresh
conversation with `task-cycle-review`.

## Out-of-plan reminders

- Stop conditions (contract § Stop conditions): the runner cannot dispatch
  and wait for children without touching the ES park-and-resume path (the
  steering tests are the fence); the profile cannot run selection-free
  without changing the IOF/ICF path; the NEET rapid longlist exceeds a time
  the owner will accept — report the split, cut nothing.
- The clustering engine, characterise, group and the ES search prompts are
  not touched. If a phase finds it must, stop and report.
- The Codex spend cap: the plan-stage review and any Codex lane wait with
  `scripts/codex_job.sh wait` and fall back to `deep-reasoner` on failure;
  the owner wants review findings reported before any fold.
