# Plan: 045-scoping-longlist

Deliverables 1–11, decisions D1–D26, the adversarial folds A1–A23 and every
term are defined in [contract.md](contract.md). This plan cites them and adds
nothing to scope. It was written against the as-built code at `19776b65`
(two seam dossiers, 2026-09-22), not against the contract's own claims.

> **Status:** drafted 2026-09-22 · lead. **Plan-stage adversarial review
> ran 2026-09-22** (fallback lane, `deep-reasoner`, read-only; the Codex
> lane is unavailable on the workspace spend cap): 19 findings, 5 blockers,
> verdict "material change needed", every finding put to the owner before
> any fold (§ Plan-review folds P1–P19). **Five owner rulings at the plan
> gate (2026-09-22):** P4 — scoping readers see *what exists and what is
> active*, not a single latest run ("Yes, scoping readers see what exists
> and what is active"); P5 — the per-component semaphore is built ("Yes,
> add the semaphore"); P10 — contract surface-map row 3 amended to the
> per-step directive key ("Yes, amend row 3"); P16a — the check-in card
> route stays `204` ("Yes, card route stays 204"); P16b — `inherit` is
> non-spine ("Yes, inherit non-spine, fold the rest"). The seven lead calls
> in § Open at the plan gate stand as folded. Plan approved (before
> implementation): _pending · owner_. **ADR 0039 is drafted at step 4 of
> this design phase, after plan approval and before any build phase** (044
> X15); Phase 8 adds evidence and the sign-off date.

Executor marks per AGENTS.md § Agent-side model routing; every `lead` mark
carries its reason. **Owner ruling 2026-09-04 stands:** judgment-bearing
phases go to `deep-reasoner`, not `codex`; the family flip happens at step 7
when Codex reviews the diff. No phase is marked `codex`. Taste-bearing
frontend surfaces and **product copy** (the beat sentences, the stage
words — owner's copy-text principle) are `lead`; delegates land structure
and plumbing. Prompt-bearing work is `lead` and always the first sub-phase
of its phase, so the delegate's brief imports a real artefact (044 P6).

**Verify gates.** Full `make verify` at Phase 0 (build-open baseline), Phase
1 (the revision — schema class), Phase 4 (the runner, child walks and the
two start surfaces), Phase 7 (the turn route and the answer core) and Phase
8 (step-6 exit). Phases 2, 3, 5 and 6 close on `make verify-fast` **plus
`make prompt-guard` and `make drift-check`** (044 P7) plus `make
frontend-verify` where the frontend changed; `pnpm e2e` wherever a route,
the thread or its frames changed (Phases 3, 4, 6, 7). **One green commit
per phase.**

**Spec changes** (contract § Spec changes, items 1–11) are applied in Phase
8 with the owner's words quoted, except item 10 (the decision sheet), which
is applied at plan approval so the build starts from a sheet whose task-2
rows are ruled.

## Decisions fixed here (lead seam design)

S1. **Compose by purpose and the spine flag.** `CapabilitySpec.compose`
(`capability_registry.py:96`) becomes `Callable[[Any, str | None],
ComposedChain]` and `compose_plan(capability, plan, *, purpose: str | None
= None)` (`:165`). The purpose is **the intent record's `purpose` column**.
The fresh walk reads it in `_open_capability_run`'s transaction
(`runner.py:5299`, which already reads the task's capability; its return
becomes `(capability, purpose)` — a signature change) and passes it to the
compose call at `runner.py:732`; the park-resume path reads it at
`continuation_state.py:173` (`cap_row` is in scope); the API resume path
has no connection inside `_with_plan` (`api/continuation.py:1428-1441`), so
its caller at `:1079`, which holds a `conn` and `pause.capability_run_id`,
reads the scope's purpose and passes it in. The four ES-pinned
`compose_plan` sites (`runner.py:3333`, `steering.py:1685`, `:1706`,
`api/routers/task_agent.py:213`) and the three capability-generic ones pass
nothing; `compose(plan, purpose)` for the ES ignores it and
`test_capability_registry.py`'s AST scan stays green. `compose_scoping`
returns three chains: `None | "baseline"` → today's six steps; `"longlist"`
→ `inherit → suggest → acquire → screen_abstract → classify → appraise →
ingest_full_text → extract_interventions → longlist → constrain`, with the
option searches dispatched and joined by the **runner**, not by a component
(S2); `"targeted"` → `acquire → screen_abstract → classify → appraise →
ingest_full_text → extract_interventions` (the child walk; its intent is the
entrant's design, its `record_cap` the option-search target). Directive
deltas: the longlist and targeted acquires carry `record_cap` from
`LONGLIST_ACQUISITION_TARGETS` / `OPTION_SEARCH_TARGET` and the evidence
restrictions as `filters` (`search_loop.py:599` admits only `depth ·
filters · guidance · record_cap`, so nothing new); `screen_abstract` carries
the longlist criteria (target unit, outcomes, setting when required, **no
place**), composed under the 2,000-character ceiling. **Spine membership**
(A6, P16b): `ComponentStep` gains `spine: bool | None = None`
(`task_plan.py:976`, `extra="forbid"`; the chain is rebuilt from the plan on
resume, so the flag survives a park); both `SPINE_COMPONENTS` reads
(`runner.py:1322` and `:3837`, the segment re-entry) take `step.spine` and
fall back to the set when `None`, so every ES chain is unchanged; the
scoping compose sets `spine=False` on `inherit` (owner: "inherit
non-spine" — a failed link read degrades the walk, which continues without
the linked documents, the missing link named on the longlist) and on
`suggest`.

S2. **The option search is a tool; its implementation is a child walk; the
runner dispatches and joins** (D6, D26, A1, P1, P2, P5, P11, P12).
`runtime/option_search.py::run_option_search(engine, *, task_id, plan_row,
design: OptionDesign, parent_capability_run_id: UUID | None, backends,
user_id) -> UUID`: in one transaction, insert the targeted intent record
(`purpose="targeted"`, `intent=design.as_intent()`, `plan_id` = the
confirmed version, `context={"option_id": …}`) **and mint the child's
`capability_run_id`**, then submit `run_plan(engine, …, evidence_scope_id=
targeted, capability_run_id=child_id, parent_capability_run_id=…,
backends=…, io=ParkIO(), session_id=task_id)` to the **option-search pool**
and return the id — no polling, no `_await_new_run` (P2). `run_plan` and
`_run_plan_impl` gain `capability_run_id: UUID | None = None` (today minted
at `runner.py:727`) and `parent_capability_run_id`, both threaded into
`_open_capability_run`, which writes the new column. **The fan-out and the
join are runner-level barrier steps in the step loop** (P1, P11): a harness
component sees a connection and individual backends, never the engine, the
`RunnerBackends` bundle or an executor (`harness.py:106-132`), so
`option_searches` is not a harness node. In `_run_plan_impl`'s loop
(`runner.py:901`), where `engine`, `backends`, `task_id`, `session_id` and
`evidence_scope_id` are in scope: after `suggest` completes, the loop reads
the entrants (the option rows `suggest` minted plus the plan's own options),
applies the cap (`OPTION_SEARCH_CAP` = 15, the user's and the report-derived
first) and, **on a rebuild, only entrants with no prior option search** (a
`capability_run` of purpose `targeted` whose scope names the option — P12),
calls `run_option_search` for each with this walk as parent, and records
the child ids in the walk's state; before `longlist` runs, the loop
**joins**: it waits, **outside any transaction**, for every child to reach
a terminal status, bounded by `OPTION_SEARCH_JOIN_TIMEOUT` (after which the
remaining children are marked `interrupted` and counted as failed
entrants); a child's `failed` adds a synthetic `skipped` outcome so the
parent ends `degraded`, never `failed`. Both barriers emit their own
progress events (S12). **The option-search pool** is `runtime/walk_pool.py`:
a process-wide `ThreadPoolExecutor(max_workers=OPTION_SEARCH_WIDTH)` (4)
**separate from `app.state.run_executor`** (two workers,
`settings.run_executor_max = 2`, `api/app.py:294`; a parent waiting on
children submitted to its own pool would deadlock). **The per-component
semaphores** (P5, owner: "add the semaphore") close the 044 seam as it was
stated: `walk_pool.CLASSIFY_SLOTS = BoundedSemaphore(MAX_CONCURRENT_CLASSIFY)`
and `INGEST_SLOTS = BoundedSemaphore(DEFAULT_MAX_WORKERS)`, acquired around
each provider call in classify's fan-out and each parse job in ingest, so
four children and a parent share 12 classify threads and the parse workers
rather than each taking its own — two `with` statements in the two ES
components, behaviour-preserving for a single walk. **Connections**: the
pool is 5 plus 10 overflow (`api/settings.py:40-41`); the parent holds one
during a component and none during the join; each child holds one during a
component; the live check measures peak use with four children and reports
it — a pool-size change is production config and outside this slice. The
capacity gate in `create_run` (`runs.py:160`) counts only walks with
`parent_capability_run_id IS NULL`, so a parent's children never refuse
another task's walk. The two callers of the tool: the runner's fan-out and
the verb *add* (S11), which passes `parent_capability_run_id=None`.

S3. **The two start surfaces, the follow-on and the conversation lineage**
(D1, A2, A23, P3, P6, P7). `api/longlist_start.py::open_longlist_walk
(engine, *, task_id, plan_row, backends, executor, user_id, await_run:
bool = True) -> UUID | None`: under `runs.py`'s `_dispatch_lock`, the same
admission as `create_run` (no `running | paused` **parentless** walk, the
reservation, the capacity gate), then in one transaction mint the longlist
intent record (`purpose="longlist"`, `intent=compile_longlist_intent(plan)`,
`plan_id` = the confirmed version) and `_dispatching_tasks.add`; submit
`_dispatch_run(..., evidence_scope_id=longlist_scope)` (`runs.py:62` gains
the override) to the walk executor; `_await_new_run` only when
`await_run`; discard. Callers: (a) **the gate**: `_persist_confirm_plan`
beside the `_persist_change_plan` dispatch at `api/continuation.py:241`
(the function itself is at `:941`) — records the decision
(`response="continue"`, `extra={"action": "confirm_plan",
**_baseline_gate_decision(...)}`), sets the baseline walk `succeeded` with
`run.finished{reason: confirm_plan}` **and closes the Task Agent
conversation** (the 029 invariant that `_finish_run` keeps at
`runner.py:5346-5375` and this path would otherwise bypass — P3), returns
`AnswerResult(..., continuation_requested=False, follow_on="longlist")`.
The value travels `answer_check_in` → `gate_turns.commit_decision`
(`api/gate_turns.py:341`) → `DecisionOutcome.follow_on` (new field, `:278`)
→ `_dispatch_gate_turn` (`task_agent.py:902`, which holds `executor` and
`runner_backends`), which calls `open_longlist_walk` after the commit and
puts the opened run on `TurnDecisionOut.opened_run: LatestRun | None`; the
card route (`check_ins.py:236`) calls it with `await_run=False` and stays
`204` (owner: "card route stays 204") — the thread learns of the walk from
the run stream. (b) **`confirm_baseline`** (`task_agent.py:1843`): gains
`executor` and `backends` deps; the route **commits** the minted version,
re-reads the row, and only then calls `open_longlist_walk` outside any
transaction (P6: the opener takes the task row lock itself; the lock order
is task-row transaction closed, then `_dispatch_lock`, as `create_run`
does); `PlanOut` gains `opened_run: LatestRun | None = None`. The
"confirmed but no walk" state is resolved on the idempotent path: when the
current version is already confirmed and no longlist walk exists for it,
the route opens one rather than returning unchanged. (c) **Unattended**
(A2): `_resolve_baseline_gate_unattended` has no executor, so the follow-on
lives where the walk ends: `RunPlanOutcome` gains `follow_on: str | None`;
the gate handler sets it on the state when it records the standing
default; `_dispatch_run` (the worker thread) performs the opener's
mint-and-run **inline** after the baseline `run_plan` returns. **Conversation
lineage** (P3): `_finish_run` skips `close_task_agent_conversation` when
the walk has a `parent_capability_run_id`, so a child never closes the
thread the user is watching; the longlist walk's own closure means the
next Task Agent turn opens a fresh lineage seeded from the approved plan
(`task_agent.py:752` and the closed-predecessor read at `:586`), exactly as
044's post-baseline plan change does today; the verbs (S11) run on that
lineage. Tests: the pre-insert race between `confirm_baseline`, the gate
and `POST /runs` yields one walk; the chat-gate start opens the walk; the
card path opens it without awaiting; unattended opens the second walk with
the standing default recorded; a finished child leaves the conversation
active.

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
`unit_id`, `unit_task_id` (the linked task for inherited findings),
`task_source_snapshot_id` nullable (own rows only), `assignment_reason`,
`design_feature_not_stated` bool, `assigned_by_run_id`; composite FK to
`option`; unique `(option_id, unit_kind, unit_id)`), `option_relation`
(`relation_id`, `task_id`, `from_option_id`, `to_option_id`, `kind` CHECK
`part_of | variant_of`, `created_by`; both composite FKs), `longlist_result`
(`longlist_result_id` PK, `task_id`, `evidence_scope_id`, `run_id`,
`plan_version`, `themes` JSONB, `coverage` JSONB, `judgements` JSONB,
`guesses` JSONB, `counts` JSONB, `provenance` JSONB, `created_at`;
`fk_llr_scope_task`, `fk_llr_run_task`, unique `(evidence_scope_id,
run_id)` — the `characterisation_result` shape), `intervention_profile_record`
(`record_id` PK, `task_id`, `extraction_record_id` with `fk_ipr_record_task`
→ `uq_ser_id_task`, `intervention` NN, `role` CHECK the five values,
`design_features` JSONB, `is_bundle` bool, `components` JSONB, `outcome`,
`population`, `setting`, `study_geography`, `study_design`,
`covers_no_intervention` bool, `field_coverage` JSONB, `grounding` JSONB,
`created_at`; `ix_ipr_record`), `task_link.option_id` (nullable, composite
FK `(option_id, target_task_id)` → `option(option_id, task_id)`),
`capability_run.parent_capability_run_id` (nullable, composite self-FK
`(parent_capability_run_id, task_id)` → `uq_capr_id_task`, `ix_capr_parent`);
relaxes `extraction_result.selection_run_id` to nullable (the composite FK
`fk_exr_selection` stays: MATCH SIMPLE passes a NULL); drops and recreates
`finding_reference_union` with a third branch (`SELECT record_id AS
finding_id, 'interventions'::text AS kind, extraction_record_id, task_id,
intervention, outcome, population, setting, study_geography, study_design
FROM intervention_profile_record` — every shared column exists on the
record, no NULL aliases; the SQL constant lives beside the table stub in
`core/schema.py` and the migration reuses it). Downgrade: refuses while any
`capability_run` row has a scope of purpose `longlist` or `targeted` (the
044 A5 predicate widened), restores NOT NULL (refusing while a null row
exists), restores the two-branch view, drops the columns and tables. The
operator remedy script from 044 gains the walk kinds. The prompt-hash guard
needs nothing.

S5. **The label resolver** (D23, P19). `options_scoping/labels.py::
labels_for_snapshots(conn, *, task_id, tss_ids) -> dict[UUID, DocumentLabels]`
with `DocumentLabels(evidence_type, quality_score, rubric_version,
provenance: Literal["own", "inherited", "absent"], source_task_id,
source_run_id, stale_rubric: bool)`. Own rows first (`latest_row_by_id`,
`repository.py:235`, over the task's classification and appraisal rows —
the pattern at `:705-727`); **when the task has no inbound `task_link` the
resolver returns own rows only and touches nothing else** (an Evidence
search task's readers gain no cross-task reach; test); for the rest, one
query through `task_link` (target = this task) → the source task's
`task_source_snapshot` sharing `source_snapshot_id` → its classification and
appraisal rows in the pinned run's scope; `absent` otherwise. **Rubric
rule**: an inherited appraisal whose `rubric_version` differs from the
current rubric returns `quality_score=None, stale_rubric=True`; the appraise
skip (S6) leaves that row to appraise, which re-appraises
deterministically. Readers: the longlist's coverage; `evidence_page`
(`:650`), `landscape_out` (`:467`), `artefact_out` citations (`:1395`,
`:1408`) and `source_dossier_out` (`:2360`) — the four `latest_row_by_id`
sites through one helper; `_resolve_citation_sources` in the answer core
(`answer_core.py:219`). Output field names are unchanged (`evidence_type`,
`appraisal_tier`), so the Sources table needs no change.

S6. **Inherited documents and the classify/appraise skip** (A3, A4, A7,
P10). `inherit` is a **non-spine step of the longlist walk**, first, so its
rows carry `run_id` and "created by an inherit run" is literal (data-model §
Corpus). `runtime/inherit.py::inherit_documents(conn, *, task_id, run_id) ->
InheritSummary`: for each link, insert `task_source_snapshot` rows for the
source task's screened-in documents of the pinned run that this task lacks
(`origin="acquired"`, `run_id` = the inherit run, `full_text_snapshot_id`
and status copied from the source row so ingest does not refetch),
idempotent on `uq_task_source_snapshot`; a link that cannot be read is
recorded in the summary and skipped (the walk degrades). **The skip**
(owner: "amend row 3" — contract surface-map row 3 now reads: a per-step
directive key computed by the runner's directive-authoring seam at the
classify and appraise steps): `leg_directive` (`runner.py:608`, today pure
and V1-identity) gains the signature `leg_directive(plan, step,
upstream_state, *, engine, task_id, evidence_scope_id)` — both call sites
(`runner.py:1100`, `:3746`) have them — and a scoping branch that, at
`classify` and `appraise` of a longlist walk, calls the resolver over the
scope's screened-in rows and writes `{"classify": {"skip_task_source_snapshot_ids":
[...]}}` / `{"appraisal": {"skip_task_source_snapshot_ids": [...]}}`;
`classify` gains a fail-closed directive parser with that one key
(`assess/classify.py`, today reads none) and `appraise`'s parser
(`appraise.py:194`) gains the key; both add `~in_(skip)` to their selection
queries. Behaviour-preserving when absent (existing tests). Its docstring's
identity promise is revised: the seam now reads the database.

S7. **The intervention profile on a selection-free path** (D3, D24, A5,
A10, P9). `extract_interventions` is a **new registry component**
(`run_spec.py`: `requires: ["evidence_scope_id"]`; a harness node,
conditional edge and `→ finish` edge in `build_graph` (`harness.py:496`);
`registry_component_for` identity; `_reference_kwargs` returns `{}` for it,
so no `select` reference is looked up — which is why it is a component and
not a directive on `extract`, whose registry entry requires
`selection_run_id`). Its handler calls `extract_scope(..., profiles=
(INTERVENTIONS_PROFILE_ID,), selection_run_id=None)` **through the
`profiles` kwarg** (`extract.py:1906`), so `_parse_extraction_directive`'s
IOF-mandatory rule (`:1594`) is **not lifted**; a test pins that an ES
directive naming ICF alone is still refused. In `extract.py`:
`ExtractContext.selection_run_id: UUID | None`; `_load_selection` is
bypassed when `None` in favour of `_screened_in_docs(conn, task_id,
scope_id)` (the `characterise.screened_sources` query projected to
`{tss_id, text_basis}`, which is all `_load_docs` at `:395` needs);
`_write_rollup` (`:2026`) writes `selection_run_id=None`. The profile
bundle: `_interventions_profile` beside `_iof_profile` / `_icf_profile`
(`:1470-1510`), in `interventions_profile.py` (the bundle and the record
writer), `interventions_records.py` (`PROFILE_ID = "os_interventions_base_v1"`,
`SCHEMA_VERSION = "interventions_v1"`, `InterventionsRecordWire` — one
document → many records, the five roles as a Literal, `design_features:
list[str]`, `is_bundle`, `components`, `covers_no_intervention` at document
level), `extract_interventions_prompt.py` (`PROMPT_VERSION =
"extract_interventions_v1"`; the profile reads title and abstract from
metadata, never the full text, so `text_basis` on the record is
`abstract_only` by construction), a fingerprint function on the
`extraction_fingerprint` pattern (`:210`), no vetter, quote anchors located
in the abstract by `quote_verify.locate_unique_span`. Writes
`intervention_profile_record` rows; memo through `source_extraction_record`
as today. `KNOWN_PROFILE_IDS` (`:134`) gains the id; `_selected_profiles`
keeps its order rule.

S8. **The longlist component** (D4, D5, D8, D10, D11, A9, P8).
`options_scoping/longlist/longlist.py::longlist_scope(conn, *, task_id,
run_id, context: LonglistContext, backend: LonglistBackend) -> dict`. Units:
`intervention_profile_record` rows of the longlist scope **and every
targeted scope whose walk is a child of this walk** (through
`parent_capability_run_id`), minus `role == "comparator"`; plus, per link
whose pinned walk ran `extract`, the source task's IOF/ICF rows of that
walk through `finding_reference_union` (unit kind `iof | icf`, `unit_task_id`
= the source). Each unit's payload is the component's projection
(`intervention`, `design_features`, `role`, `outcome`, `setting`,
`study_geography`, a bounded quote). **Seeding lives in the component's
backend, and the engine runs unchanged** (P8): `LonglistClusteringBackend`
(the `_CharacteriseClusteringBackend` shape, `characterise.py:180`) is
constructed with the seeds (the entrants' option rows; on a rebuild, every
existing option); its `discover` returns **seeds ∪ newly discovered
labels** (one model call through `longlist_cluster_prompt.build_longlist_
discovery_messages(units, seeds, max_labels)`, asking for options beyond
the seeds), and its `assign` uses `build_longlist_assignment_messages`;
the component then calls `cluster_units(units, backend=…, policy=
ClusteringPolicy(min_labels=…, max_labels=clamp(ceil(N/4), 8, 40) counting
seeds, residual_label="unclustered", unresolved_policy="residual", …))`
exactly as characterise does — no private engine function is touched and
no repair loop is re-implemented. The assignment output is one label per
unit (a document with several records lands in several options); the
assignment prompt may answer the component's own `not an option` label,
which the component counts beside the residual. Each membership row
carries the assignment's one-line reason and the `design_feature_not_stated`
flag the assignment returns per unit. Option rows: seeds map to existing
rows; discovered labels mint rows (`origin="clustered"`, design v1 from the
discovery output); a discovered bundle mints a package and `part_of` rows.
**Themes**: a second `cluster_units` run (unseeded) over the options as
units. **Typing**: one batched call per ~20 options → `{primary,
secondary[], runner_up, runner_up_reason, none_fits_reason | None,
ambition, ambition_reason}` against `lever_types.py::LEVER_TYPES`
(`TAXONOMY_VERSION`). **Coverage** (deterministic, `coverage.py`): per
option, documents by evidence type and tier (through S5, Unknown and
Non-evidence bucketed, `absent` shown as "not rated"), by role, where tried
(`where_tried.py`: study geography → `COUNTRY_GROUPS` → *United Kingdom ·
comparable systems (OECD) · other* against `plan.where`), populations,
settings, outcomes; DOI collapse for counts (`_metadata_text(metadata,
"doi")`, normalised); flagged members counted. Written last, the 010
pattern. On a rebuild (D14): seeds = existing options; a seed with no
member keeps its row and `coverage` says zero; user state (`state`,
`exclusion`) is never touched by the component.

S9. **Constrain** (D9, D21, D22). `options_scoping/constrain/constrain.py::
constrain_scope(conn, *, task_id, run_id, context, backend)`: reads the
options and `longlist_result.coverage`; per option one judgement call
(batched ~10 per call on the judgment model) over the plan's `requirement`
constraints plus the three default screens, returning per constraint
`{verdict: passes | breaks | cannot_check, reason}`; a `breaks` sets
`state="excluded"` with `exclusion={constraint, reason, by: "constrain"}`
unless the user has already set the state (user state wins); `distinct` is
never applied to an option with a `part_of` relation; per `preference`
constraint except the transferability preference, one capped guess into
`longlist_result.guesses`; the deterministic in-scope check (`in_scope.py`:
publication country and year from metadata against the plan's
`country_group` and years; the country read at `repository.py:205-221`
extracted to a shared helper) sets `no_in_scope_evidence` when no member
document passes. Judgements keyed by `(option_id, design_version)` in
`longlist_result.judgements`.

S10. **Suggest** (D7, A15). `options_scoping/suggest/suggest.py::
suggest_options(conn, *, task_id, run_id, context, backend)`: one call on
the judgment model over the plan (question, intended change, target unit,
outcomes, Your context, `your_options`), the baseline's sections and the
linked reports' bodies (`inherit._report_markdown` per link), with
`LEVER_TYPES` as a checklist; output `{name, description, design_features,
outcomes_served, source: model | linked_report(section)}` up to
`SUGGEST_BOUND` (10). Mints option rows (`origin="suggested"` or
`"from_evidence_search"` with the section in `provenance`), and the plan's
own options as `origin="added_by_you"`. No profile record is ever written
from report text.

S11. **The longlist verbs and the answer core over several scopes** (D13,
A8, A14, P13). `_Reserved` (`task_agent.py:653`) gains `longlist:
LonglistSurface | None`, read in the same locked transaction when no
parentless walk is active and a `longlist_result` exists;
`create_task_agent_turn` gains a dispatch arm beside the gate arm (`:1166`)
calling `api/longlist_turns.py::dispatch_longlist_turn`, the
`_dispatch_gate_turn` pattern: `agent.sort_longlist_turn(utterance, options)`
(`runtime/longlist_verbs_prompt.py`, `LonglistVerbWire{kind: question | add
| exclude | include_again | other, option_id, reason, design_words}`, on
`AGENT_TRIAGE_MODEL` like the gate sort, stub queue in `StubAgentBackend`).
**Two turns per verb**: the sorting turn replies with the proposed action in
words (and, for *add*, the design `option_design_v1` proposed back) and
stores the pending action in the row's `task_agent_state`; the next turn
that confirms (`confirmTarget`, the 044 button-confirm pattern, or a sorted
`other` the prompt reads as assent) applies it: `exclude` / `include_again`
write the option state and a History event; `add` mints the option
(`origin="added_by_you"`), calls `run_option_search` with no parent, and
assigns its records against the existing options through the component's
seeded path. The applied turn is `kind="action"` (`TaskAgentTurnKind`
widened; `TaskAgentTurnOut.action: TurnActionOut{verb, option_id, label,
capability_run_id: UUID | None} | None` — `TurnDecisionOut` is not reused,
its `check_in_id` is required). `question` → the answer core over the
**scoping scope set**: `ResolvedRunScope` gains `extra_scope_ids: tuple[UUID,
...]`; `resolve_terminal_run_components` (`chat_scope.py:59`) gains a
scoping branch (S15): the longlist walk plus its children's targeted
scopes when a longlist exists, else the baseline walk; `build_retrieval_scope`
(`synthesis_tools.py:1189`) takes `scope_ids` (the four `== scope_id` sites
at `:1262-1274` become `.in_()`) with a **precedence rule** (P13): one row
per `tss_id`, the longlist scope's row wins, then the latest by timestamp —
a document screened in under two scopes is tested; `make_lookup_reader`
likewise; `RetrievalUnitCapError` (`:1294`) is caught on the verbs path and
answered honestly. The button routes (`POST /options`, `/exclude`,
`/include`) call the same three apply functions.

S12. **Read models, routes, progress** (deliverable 11, A7, P14, P15).
`api/contract/read_models.py`: `LonglistOut{run_id, plan_version, counts,
themes: [ThemeOut{theme_id, name, description, option_ids}], options:
[OptionSummaryOut]}`, `OptionOut` (the card), exported through
`api/contract/__init__.py`; `repository.py::longlist_out` / `option_out` on
the `artefact_out` idiom (`:1269`; latest `longlist_result` by `created_at
DESC`; 404 when absent); `api/routers/longlist.py` with `_readable` for the
two GETs (public-readable like the artefact) and `accessible_task(write=True)`
for the three POSTs. **Progress**: `StageKey` (`api/contract/sse.py:25`),
`STAGE_KEYS` (`:38`), `PlanStageKey` (`contract/task_agent.py:65`),
`STAGE_PRESENTATION` and `STAGE_BY_REGISTRY` (`api/stage_vocabulary.py:19`,
`:32`) gain `inherit`, `suggest`, `option_searches`, `extract_interventions`,
`longlist`, `constrain` — additive Literal widening; the two runner
barriers emit `run.started` / `component.completed`-shaped events under the
`option_searches` key with their counts in `summary`. **The six beats of
contract deliverable 3** map to boundaries: *suggestions made* ←
`suggest` completed (`summary.suggested`); *option searches finished* ←
the join completed (`summary.finished`, `summary.failed`, `summary.total`);
*retrieval counts* ← `acquire` completed; *abstracts read* ←
`extract_interventions` completed (`summary.documents`, `summary.records`);
*options clustered* ← `longlist` completed (`summary.options`,
`summary.themes`, `summary.unclustered`); *constraints checked* ←
`constrain` completed (`summary.excluded`, `summary.no_in_scope`). The
**sentences are composed client-side** from `StageCompletedFrame.summary`
(the blurb rides only `stage.started`, `sse.py:275-296`): a small
`beatSentence(stage, summary)` in the frontend, its words `lead` (product
copy); child walks publish their own frames under their own run ids and
are not shown in the parent's thread beyond the join beat. `TaskOut`
gains `has_longlist` and `active_run` (S15) computed in `task_out`
(`_common.py`) with one `EXISTS` and one `SELECT … LIMIT 1` (no N+1 on the
listing).

S13. **Frontend** (deliverable 9, A7, P4). `views/longlist/LonglistView.tsx`
(list), `LonglistGrid.tsx` (rows `LEVER_TYPES` from the read model's
taxonomy, columns the three ambition bands, tiles), a view switch in
`ArtefactView` (Baseline · Longlist · Report unavailable) keyed on
`useLonglist(taskId)` (the `useArtefact` shape, 404 → `null`), `OptionCard.tsx`
at `routes.tsx:113` (`/tasks/:taskId/options/:optionId`, wrapped in
`LifecycleRoute tab="result"`); `lifecycle.ts` `TabOptions` gains
`hasLonglist` and `openTabs` treats it like `hasBaseline`; `LifecycleRoute`
and `AppShell` fetch `useLonglist` under the same loading fence as the
artefact. **Scoping readers see what exists and what is active** (S15):
the eight `task.latest_run` readers (`LifecycleRoute.tsx:45`,
`AppShell.tsx` running banner, `ArtefactView.tsx` `hasResult` and
`showLiveArtefact`, `TaskListRow`, `TaskPanel`, `landingPresentation.ts`,
`ChatSidePanel.tsx`, `planStart.ts`) read `task.active_run` for "running"
and the existence flags for "has a result" when the task is a scoping
task; `planStart.ts`'s reducer (`:318-326`) keeps `build | none |
rebuild_or_confirm | confirmed` and adds `longlist_built` (a longlist
exists for the current version, nothing active) and `rebuild_longlist`
(the plan version is newer than `LonglistOut.plan_version`), dispatched
**before** `confirmed`, keyed on `has_longlist`, `active_run` and the
version comparison; `rebuild_or_confirm` stays for the post-baseline,
pre-longlist state; **Rebuild longlist** posts to
`POST /plan/confirm-baseline` on the new version (P12), which opens the
walk; `SCOPING_CONFIRMED_LINE` (`:149`, rendered at `PlanDocument.tsx:606`)
becomes "Longlist built · N options" (N from the read model) or "Building
the longlist" while active. `store/thread.ts` `taskAgentTurnKind` (`:112`)
gains `"action"`; `DurableTurn` (`views/workspace/TaskAgentPane.tsx:328`)
gains a branch reusing `DecisionLine` (`:303`); the beat sentences render
in `RunBlock`'s stage list. `frontend/src/mock/fixtures` and
`frontend/src/mock/api.ts` gain the longlist, an option and the three POST
handlers so `pnpm e2e` can drive it. Taste-bearing: the list, grid, card
and the beat sentences get a `lead` pass with the impeccable skill.

S14. **ADR 0039** records: the longlist as a second walk and the child walk
with `parent_capability_run_id`; the option search as a tool with two
callers and the runner as the dispatcher; the option-search pool, the
per-component semaphores and the capacity rule; compose by purpose from the
intent record; the spine flag; the existence-and-activity model for scoping
readers (S15); the option entity, membership and relation tables and
`longlist_result`; the intervention profile as a third extraction profile
on a selection-free path (E1/F2/F3 edited); the label resolver and the
rubric rule; the longlist verbs as two-turn actions; the stage vocabulary
widening; the revision and its rollback commands and the operator remedy.

S15. **Existence and activity, not a latest run** (P4; owner: "scoping
readers see what exists and what is active"). For a scoping task the
readers ask three things and the read model answers each directly:
`TaskOut.active_run: LatestRun | None` (any `running | paused` walk of the
task, children included); `TaskOut.has_longlist` beside the artefact-based
baseline signal; and the chat's scope set (S11). `TaskOut.latest_run` is
unchanged for the Evidence search and, for a scoping task, is the latest
walk that is neither a child nor targeted (so nothing that reads it breaks
while the scoping readers move to the two new fields). The admission
fences (`create_run`, `confirm_baseline`, the turn route's `active` read)
consider **parentless** walks only, so a child never blocks a user action
except through the option-search pool. Test: a finished or running child
never becomes the task's `latest_run` and never opens or locks a tab.

## Open at the plan gate (resolved 2026-09-22)

1. `inherit` as the first step of the longlist walk — **stands**, non-spine
   (P16b).
2. Capacity counts parentless walks only — **stands**.
3. The SSE stage vocabulary widens by six keys — **stands**.
4. Verbs are two turns — **stands**.
5. `TaskAgentTurnKind` gains `"action"` — **stands**.
6. The unattended follow-on runs inline in the worker thread — **stands**.
7. Classify and appraise gain one optional directive key each — **stands,
   and contract surface-map row 3 is amended** (P10).
8. The check-in card route stays `204` (P16a) — **ruled**.
9. Scoping readers use existence and activity, not a latest run (P4) —
   **ruled**; contract deliverables 10 and 11 amended.
10. The per-component semaphores are built (P5) — **ruled**.

## Phase 0 — Build-open baseline — `lead` (inline)

Reason: a one-command check and the owner's decision-sheet words are not
delegable. Full `make verify` on `task/045-scoping-longlist`. Never build
on a red base. Apply contract § Spec changes item 10 (the decision sheet's
task-2 rows, the owner's words) and commit it with the ADR (step 4) before
Phase 1.

## Phase 1 — Revision, registries, compose by purpose, spine flag, resolver, existence model (deliverables 6/8, 3 part, 11 part) — `deep-reasoner`

Brief (S1, S4, S5, S15): the alembic revision with its round-trip and the
downgrade refusal; `ComponentStep.spine` and the runner's two fallback
reads; `compose_plan(..., purpose=)` with the purpose read from the intent
record on the fresh path and both resume paths (the API path's caller
passes it), the three scoping chains as data (the new components
registered in `run_spec.py`, `harness.py`, `task_plan.py` with stub
handlers that raise `NotImplementedError` until their phases — the graph
must build); the label resolver with its rubric rule and the own-rows-only
rule, the five readers switched to it; `TaskOut.active_run`,
`has_longlist` and the scoping `latest_run` rule; the parentless-only
admission fences; the operator remedy script extended. Tests: the
contract's migration and pool bullets; compose by purpose (ES sites
unchanged; a parked longlist walk resumes on the longlist chain on both
paths); the spine flag (an ES chain's statuses unchanged; a `spine=False`
step's failure degrades; the segment re-entry site); the resolver (own ·
inherited · absent · stale rubric; Sources shows an inherited tier; an ES
task's readers reach no other task; a link grants no read without the
link); a running or finished child is never `latest_run` and never blocks
an admission fence. Done when full `make verify` is green and `make
drift-check` after `openapi-sync` is green (additive).

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
IOF and ICF); an ES directive naming ICF alone still refused; a document
already profiled in this task is served by memo across the longlist and a
targeted scope; Non-evidence profiled; the union view returns the three
kinds.

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
`inherit_documents` as the `inherit` component (non-spine); S10's
`suggest`; `leg_directive`'s new signature and scoping branch; the
classify/appraise skip keys. Tests: the contract's suggest bullet and the
inherit half of the pool bullet; an unreadable link degrades and is named;
the skip keys behaviour-preserving when absent.

4.3 **Option search tool, child walks, the runner barriers, the pool and
semaphores, the two start surfaces, the unattended follow-on, the
conversation lineage — `deep-reasoner`.** S2 and S3 exactly. Tests: the
contract's start and option-search bullets (the pre-insert race; the
chat-gate start; the card path without await; the capacity rule; width 4
and the classify semaphore under a concurrency test; a failing child
degrades; the join timeout; the rebuild's new-entrant filter;
`confirm_baseline` re-opens a missing walk on the idempotent path;
unattended opens the second walk; a child never closes the conversation;
the confirm branch closes it).

4.4 **Stage keys and frame plumbing — `fast-worker`; stage words and beat
sentences — `lead`.** The six stage keys, `STAGE_KEYS`, `PlanStageKey`,
the registry map, the barrier events and the summary counts (fast-worker,
an exact spec); the presentation strings and the client-side
`beatSentence` words (lead — product copy on the thread, the owner's
copy-text principle). Tests: the six named beats appear at their six
boundaries on a stub longlist walk; child frames carry their own run ids.

Gate: **full `make verify`** + `pnpm e2e` (the thread's frames changed).
Commit.

## Phase 5 — Longlist and constrain (deliverables 6, 7)

5.1 **`longlist_cluster_v1`, `longlist_theme_v1`, `lever_typing_v1`,
`constrain_v1` — `lead`.** Reason: prompt-bearing. Seeded discovery
(seeds shown, new options beyond them) and assignment (one option per
record; the `not an option` label; the reason and the
`design_feature_not_stated` flag per unit); theme discovery and assignment
over options; lever typing with `none fits`, runner-up and the ambition tag
with its justification; constraint judgement with the three default
screens and the capped guess wording. Re-pin all four; stubs.

5.2 **Longlist component — `deep-reasoner`.** S8 exactly, including
`lever_types.py`, `coverage.py`, `where_tried.py` and the rebuild path.
Tests: the contract's longlist bullet; `clustering_engine.py` unchanged by
diff; characterise and group tests unchanged; the seeded run keeps seed
ids; the rebuild keeps ids and user state.

5.3 **Constrain component — `deep-reasoner`.** S9 exactly. Tests: the
contract's constrain bullet, with the inherited-document fixture for no
in-scope evidence.

Gate: `make verify-fast` + `make prompt-guard` + `make drift-check`. Commit.

## Phase 6 — Read models, routes and the longlist views (deliverables 9, 11)

6.1 **Read models and routes — `deep-reasoner`.** S12's contract models,
repository functions, the five routes with their access grades; `make
openapi-sync`. Tests: the contract's API bullet (org-scoped read; a link
grants no read of options; the additive diff).

6.2 **List, grid and card — `fast-worker` structure, then `lead` polish.**
S13's views, `useLonglist`, the view switch, the route, the mock fixtures
and handlers. Reason for the `lead` pass: the three surfaces are the
product's first options surfaces; typography, density and copy follow the
ES report's design language (OS capability § Product surface) with the
impeccable skill.

6.3 **Lifecycle, the scoping readers, plan document states, thread —
`deep-reasoner`, then `lead` polish.** `TabOptions.hasLonglist` with the
loading fence, the eight readers moved to `active_run` and the existence
flags for scoping tasks (S15), `planStart.ts`'s two new states ahead of
`confirmed` and the replaced line, **Rebuild longlist** wired to the
confirm route, the thread's `action` turn branch and the beat sentences in
`RunBlock`. Tests: the contract's frontend bullet; `lifecycle.test.ts` and
`planStart.test.ts` extended; a running child shows the banner and
disables the start actions but never opens or locks a tab.

Gate: `make verify-fast` + `make prompt-guard` + `make drift-check` + `make
frontend-verify` + `pnpm e2e`. Commit.

## Phase 7 — The longlist verbs and the answer core over several scopes (deliverable 10)

7.1 **`longlist_verbs_v1` — `lead`.** Reason: prompt-bearing. The sort
(question · add · exclude · include again · other) with the pending-action
confirmation reading; the propose-back wording. Re-pin; stub.

7.2 **Dispatcher, two-turn actions, answer core over the scope set —
`deep-reasoner`.** S11 exactly, including the scoping branch of
`resolve_terminal_run_components`, the precedence rule, the button routes
sharing the apply functions and the `RetrievalUnitCapError` catch. Tests:
the contract's verbs bullet; the gate-turns tests unchanged; a question
answered with a citation from a document only an option search found; a
document in two scopes yields one row with the longlist scope's labels.

Gate: **full `make verify`** + `pnpm e2e`. Commit.

## Phase 8 — Live check, evidence, specs, ADR evidence, step-6 exit — `lead`

Reason: browser-driving the pinned live check, writing the evidence, the
spec edits with the owner's words and the ADR are adjudication-adjacent.

1. The contract's live check (a)–(g) at rapid depth, plus one standard
   build for the numbers; the stage split, the funnel counts, the
   where-tried grouping, the profile's per-document cost and the option
   search's per-entrant cost; the peak database connections with four
   children; the D26 test of the queries on the NEET option searches (add
   `guidance` only if they missed what the design meant, and say so);
   screenshots.
2. `verification.md`: command tails; the migration round-trip; the
   OpenAPI diff; the prompt-hash diff (eight new, one re-pin); the three
   live longlists' numbers and the qualitative reading; the semaphores'
   and the pool's measured effect; review-lane dispositions; deferred
   deltas; known gaps.
3. ADR 0039 (S14, drafted at step 4): add the evidence links and the
   measured numbers.
4. Spec changes items 1–9 and 11 with the owner's words; the surface-map
   row 3 amendment quoted; `docs/specs/log.md` lines; `docs/deferred.md`:
   the on-demand summary, D18, the cross-task profile memo, the `guidance`
   seam if not built, sheet row A9, the `task_link` note, and the 044
   fan-out seam marked closed by the semaphores.
5. Full `make verify` (step-6 exit).

Gate: **full `make verify`**. Commit. **Stop.** Review runs in a fresh
conversation with `task-cycle-review`.

## Plan-review folds (2026-09-22, fallback lane)

| # | Finding | Fold |
|---|---|---|
| P1 | A harness component cannot reach the engine, the backend bundle or an executor, so `option_searches` cannot be a harness node | S2: the fan-out and the join are runner-level barrier steps in the step loop |
| P2 | `_await_new_run` cannot identify which child started and times out behind width 4 | S2: the parent mints the child's `capability_run_id` and passes it to `run_plan`; no polling |
| P3 | `_finish_run` closes the Task Agent conversation on every succeeded/degraded walk; the confirm branch would bypass the 029 invariant | S3: children skip the closure; the confirm branch closes it; the verbs run on the fresh lineage the next turn opens |
| P4 | Every "latest walk" reader would re-point at a child; the *add* child is parentless by design | **owner:** S15 — scoping readers see what exists and what is active; `active_run`, `has_longlist`; `latest_run` kept for the ES |
| P5 | A walk pool does not close the 044 per-component fan-out seam; connections unstated | **owner:** S2 — per-component semaphores around classify's and ingest's fan-outs; connection use measured; pool size out of scope |
| P6 | `confirm_baseline` would self-deadlock calling the opener inside its transaction | S3: commit, re-read, open outside; lock order stated |
| P7 | The chat gate's follow-on threads through `commit_decision` and `_dispatch_gate_turn`, not `_resume_walk`; the card path should not await | S3: `DecisionOutcome.follow_on`; `await_run=False` on the card path; chat-gate start test |
| P8 | Seeded clustering mirrored the engine's private repair loop; `build_discovery_messages` collided with an ES builder | S8: seeds inside the component backend's `discover`; `cluster_units` unchanged; own builders named |
| P9 | Lifting the IOF-mandatory rule widened the ES grammar for nothing | S7: no lift; the `profiles` kwarg path; ES ICF-only still refused (test) |
| P10 | Contract surface-map row 3 ("a filter before the component runs") is unimplementable; `leg_directive` is pure today | **owner:** row 3 amended to the per-step directive key; `leg_directive`'s new signature stated |
| P11 | The join inside a component transaction | = P1; the join runs outside any transaction |
| P12 | The rebuild's new-entrant filter and the Rebuild longlist route had no home | S2 filter and test; S13: posts to `confirm-baseline` on the new version |
| P13 | Multi-scope retrieval dedups silently | S11: precedence rule; two-scope test |
| P14 | Beat sentences assigned to no sub-phase; stage keys are not the contract's six beats | S12: the six beats mapped to boundaries; client-side sentences; 4.4 test named |
| P15 | Product copy marked `fast-worker` | 4.4 split; words to `lead` |
| P16 | Three calls missing from the open list | **owner:** card route stays `204`; `inherit` non-spine; S15 added to the list |
| P17 | Line and name corrections; the API resume path has no connection | folded in S1, S3, S4, S7, S13 |
| P18 | Gate lines inconsistent with the header; Phase 4 without e2e; Phase 0 `lead` unreasoned | gates corrected; e2e added; reason added |
| P19 | The resolver reaches two more readers than D23 named | S5: own rows only when no link; ES-task test |

## Out-of-plan reminders

- Stop conditions (contract § Stop conditions): the runner cannot dispatch
  and join children without touching the ES park-and-resume path (the
  steering tests are the fence); the profile cannot run selection-free
  without changing the IOF/ICF path; the NEET rapid longlist exceeds a time
  the owner will accept — report the split, cut nothing.
- The clustering engine, characterise, group and the ES search prompts are
  not touched. If a phase finds it must, stop and report.
- The Codex spend cap: any Codex lane waits with `scripts/codex_job.sh
  wait` and falls back to `deep-reasoner` on failure; the owner wants review
  findings reported before any fold.
