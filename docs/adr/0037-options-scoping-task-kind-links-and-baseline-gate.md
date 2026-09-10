# ADR 0037 — A second task kind: options scoping's shell, links and baseline gate

- **Status:** Accepted — 2026-09-09 (owner, at the task 044 plan gate; the
  decisions below were ruled one by one in the contract interview and the
  two adversarial reviews the same day)
- **Date:** 2026-09-09
- **Task:** 044-scoping-shell-baseline (options scoping build task 1;
  contract and plan under `docs/tasks/044-scoping-shell-baseline/`)
- **Relates to:** [ADR 0036](0036-one-vocabulary-across-code-schema-api-and-screen.md)
  (the vocabulary rename this one extends to the Task Agent and to "ES");
  [ADR 0033](0033-organisation-tenancy-and-global-admin-read.md) (tenancy;
  unchanged — a link changes no access); [ADR 0035](0035-public-task-read-access.md)
  (public read; unchanged); ADRs 0020–0023 (steering; extended by one
  capability-keyed point); [ADR 0013](0013-mandatory-eb-spine.md) (the spine
  the baseline reuses as is).

## Context

Policy Atlas has one capability, the Evidence search, and every table, plan,
chain and pause assumes it. Options scoping is the second capability
(`docs/specs/capabilities/options-scoping/`). Its first build task lands the
records every later task stands on: which kind a task is, how a task starts
from another, how a plan compiles to more than one intent record, and how a
run pauses on a gate the spec calls structural. It also renames the primary
chat's code names from "planning" to "Task Agent", because that thread now
carries questions, instructions and decisions during a run, not only a plan
before it.

Two feasibility checks and thirty-four adversarial findings shaped these
decisions; the contract's § Adversarial findings and the plan's § Plan-review
folds record each.

## Decisions

1. **A task carries its capability.** `task.capability TEXT NOT NULL DEFAULT
   'evidence_search'`, values `evidence_search | options_scoping`, written at
   creation and never changed; `capability_run.capability` widens to the same
   two values. Every existing task is an Evidence search.

   *Rejected:* deriving the kind from runs (a task with no run has no kind);
   a per-deployment or per-user switch (the feature branch is the switch —
   production deploys from `dev`, and `feat/options-scoping` merges only when
   the capability is ready).

2. **A Link is a row.** `task_link(link_id, source_task_id, target_task_id,
   source_capability_run_id, created_by, created_at)`: many-to-many, one row
   per pair, source ≠ target, both tasks sharing at least one project when
   the link is written, the pinned source run a finished walk
   (`succeeded | degraded`). A link that later stops sharing a project is
   flagged on read, never deleted. A link grants no access. The optional
   option id the data model declares is added in task 2 with the option
   table. `inherit` reads across a link and copies nothing: in this task the
   linked task's whole plan, its report body without citations and its
   coverage statement enter the Task Agent's context; documents and longlist
   suggestions enter with the longlist (task 2).

3. **One capability registry.** `runtime/capability_registry.py` says, per
   capability, which plan model validates a payload, which chain composes,
   which prompt is the Task Agent's, and which steer points exist. Every
   reader of a plan goes through it (ten validate sites, seven compose
   sites). The steering lattice is keyed by capability, so a scoping point
   never names an Evidence search boundary.

   *Rejected:* capability conditionals in each reader (scattered, and the
   flat lattice would have made a scoping pause fire on Evidence search walks
   in frequent mode).

4. **Several intent records per plan.** `evidence_scope` gains `purpose`
   (`baseline | longlist | variant | targeted`, nullable) and `plan_id` (a
   composite foreign key to the plan version row, nullable). The scoping
   plan's approval writes the baseline record with both; a rebuild after a
   plan change writes a new record for the new version.

5. **The baseline gate is structural in attended modes and recorded in
   unattended.** `baseline_confirm` pauses after synthesise in frequent,
   moderate and minimal. In unattended it does not pause: the runner writes a
   decision with `decided_by: standing_default`, flagged for the end-of-run
   review, and continues; choosing unattended writes that standing default
   into the plan. Unattended is never the default (owner: "this shouldn't be
   the default").

6. **"Change the plan" ends the walk and keeps the plan.** The check-in
   option writes its decision (response `abort`, action `change_plan`), marks
   the walk `aborted`, and leaves the plan `approved` and editable. The user
   then chooses: rebuild the baseline (a new walk under the new plan
   version) or confirm the plan against the existing baseline and go on. The
   second is a plan-scoped record, `baseline_confirmed {artefact_id,
   plan_version}`, written as a new plan version through the ordinary
   plan-edit path — it cannot be a steering event, because every steering
   event is attached to a walk.

   *Rejected:* routing a gate edit through the steering router (it refuses
   changes to components that have run, and all have); always rebuilding
   (owner: "the user should have the choice").

7. **The Task Agent chat is open at the gate.** While a scoping walk is
   paused, a non-approving Task Agent turn is admitted, sorted by a small
   prompt into question or decision, and dispatched to a shared answer core
   over the paused walk's pinned scope or to the check-in response
   transaction. The approving branch of a turn and `PATCH /plan` stay refused
   while a walk is running or paused, so a plan version is never minted under
   a live walk. The Evidence search keeps its card-based steering; the owner's
   direction that the Task Agent chat should be a task's control surface is
   recorded in `docs/deferred.md`.

8. **The Task Agent rename.** Conversation kind `planning` → `task_agent`;
   `planning_transcript` → `task_agent_transcript`; `planner_state` →
   `task_agent_state`; `/planning-turns` → `/task-agent-turns` with no
   redirect; `PlanningTurn*` → `TaskAgentTurn*`; the runtime module, backend
   classes and `POLICY_ATLAS_PLANNER_MODEL` → `POLICY_ATLAS_TASK_AGENT_MODEL`
   (the code default is unchanged, so an old-only deployment behaves as
   before); the constraint and index names that carry the word; stored
   values `conversation.kind` and `plan.created_by` rewritten and reversed
   on downgrade. **Kept as they are:** the prompt module's interior (moved
   byte-identical so its hash does not change), the version string
   `planner_v11`, the wire role literal `"planner"` in transcript
   rehydration, the fingerprints `eb_iof_base_v1` and `eb_icf_base_v1`, and
   the legacy steer-point id `evidence_base_coverage`. The abbreviation "EB"
   becomes "ES" in living specs, skills, templates, agentic-ops and code
   comments; ADRs, merged task docs, the spec log's past entries and frozen
   sources are untouched. Not `agent`, which already names the Agent tab and
   the 038 model persona.

9. **Two migration revisions, one per phase.** The rename revision lands with
   the fenced, separately reviewed first phase; the slice revision with the
   second. Each is reversible.

## Rollback

Quiesce first: scale the API to zero so no walk or turn is in flight, and
verify with the manifest queries in the task's `verification.md`.

1. The slice revision's `alembic downgrade -1` refuses while any `task` or
   `capability_run` row carries `options_scoping` (archiving keeps the row, so
   it is not a remedy). Remedy: `scripts/ops_remove_scoping_tasks.py` lists,
   then on `--apply` hard-deletes every `options_scoping` task with its links,
   walks, runs, intent records and result rows — pre-merge, staging-only data
   — refusing on a task that an Evidence search task links to. Then the
   downgrade drops `task_link`, `evidence_scope.purpose` and
   `evidence_scope.plan_id`, `task.capability`, and narrows
   `ck_capr_capability`.
2. The rename revision's `alembic downgrade -1` reverses the table, column
   and constraint names and the two stored values.
3. Deploy the previous image. Set `POLICY_ATLAS_PLANNER_MODEL` again if the
   deployment had renamed it.

## Evidence (task 044 build, 2026-09-09/10)

Recorded at the step-6 exit; details in
`docs/tasks/044-scoping-shell-baseline/verification.md`.

- Revisions `a7d3f1c8e2b5` (rename) and `b5e1d7a4c026` (slice), each with a
  round-trip test; the slice downgrade's refusal and the operator script are
  tested on a seeded scoping task.
- The registry routes all ten validate and seven compose sites; the lattice
  is capability-keyed; an ES walk never names `baseline_confirm` (tests).
- Live, local, real egress: the baseline built in **389 s** (first) and
  **453 s** (rebuild after a plan change) from `POST /runs` to the gate on
  the NEET question — above the 3-to-4-minute aim that assumed parallel
  writing; the writing-mode feasibility check measured sequential 183 s
  against parallel 63 s for the writing alone, and sequential stays (owner
  ruling C6). The gate answered a question with citations in 33.5 s, recorded
  a decision in words in 2.3 s (the gate sort is within that), ended the walk
  on "Change the plan" and rebuilt under the new version, and confirmed
  without a rebuild through the plan-scoped record.

## Consequences

- Tasks 2–5 build on these records: the option table hangs off the task kind
  and the links; the longlist and assessment scopes are further intent
  records; "Assess these N" is the second structural gate under the same
  unattended rule.
- The Evidence search's behaviour is unchanged and pinned by its existing
  tests; its prompt text, chain and card steering are byte-for-byte the same.
- Two known inconsistencies recorded, not fixed here: the Evidence search's
  own Task Agent prompt defaults the steering mode to unattended while the
  execution contract names moderate; the Evidence search's constraint model
  has no language filter, so a language restriction is stored and shown as
  not yet applied.
