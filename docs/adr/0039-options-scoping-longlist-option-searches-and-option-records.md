# ADR 0039 — The longlist: a second walk, option searches as child walks, and the option records

- **Status:** Accepted — 2026-09-22 (owner, at the task 045 plan gate; the
  decisions below were ruled one by one in the contract interview, the
  contract-stage review and the plan-stage review the same day)
- **Date:** 2026-09-22
- **Task:** 045-scoping-longlist (options scoping build task 2; contract,
  rubric and plan under `docs/tasks/045-scoping-longlist/`)
- **Relates to:** [ADR 0037](0037-options-scoping-task-kind-links-and-baseline-gate.md)
  (the task kind, `task_link`, the scoping plan, the baseline gate — this
  one builds on every record it declared); [ADR 0017](0017-icf-second-finding-schema.md)
  and [ADR 0018](0018-multi-facet-clustering-engine.md) (the two extraction
  profiles and the shared clustering engine, both reused as is);
  [ADR 0013](0013-mandatory-eb-spine.md) (the spine; extended by a per-step
  spine flag); [ADR 0033](0033-organisation-tenancy-and-global-admin-read.md)
  (tenancy; unchanged — the label resolver reaches a linked task only
  through an existing link); [ADR 0027](0027-durable-planning-transcript-artefact-streaming.md) (progress
  events; six stage keys added).

## Context

Task 044 ended a scoping task at the baseline gate. This task builds what
the user confirmed the plan for: the longlist, built both ways at once. The
model's suggestions and the user's own options each get an option search;
a broad search on a PICO-shaped intent is read by a new extraction profile
for the interventions each abstract covers; seeded clustering joins the two
into options and themes; the plan's requirement constraints are checked;
the Result opens on the longlist, edited by chat verbs and buttons. Nothing
is assessed and no report is written (concept ruling 50).

The as-built runner is one walk, one intent record, sequential steps keyed
by component name, on a two-thread executor. The reviews (23 contract-stage
findings, 19 plan-stage findings) showed that the entrants' searches cannot
live inside that walk, that every "latest walk" reader would follow a
child, and that several claims about reusing the extraction and clustering
machinery were wrong as written. The decisions below are what survived.

## Decisions

1. **The longlist is a second walk on the confirmed plan version.** A new
   `capability_run` with its own intent record (`evidence_scope.purpose =
   'longlist'`, `plan_id` = the confirmed version), opened by both confirm
   surfaces (the gate option `confirm_plan` and `POST /plan/confirm-baseline`)
   under the run dispatch lock and reservation, and by the unattended path
   inline in the worker thread after the baseline walk returns. It does not
   pause; the second structural gate is task 3. A longlist exists when a
   `longlist_result` row exists; the walk ends `succeeded`, `degraded` (a
   child or the inherit step failed) or `failed` (a spine step failed).

   *Rejected:* continuing the baseline walk (it has ended by the time the
   plan document's confirm is pressed, and the gate ends it by design — ADR
   0037 decision 6); one walk for the unattended path (one walk carries one
   intent record, so everything would key to the baseline scope).

2. **A chain is composed by capability and purpose.** `compose_plan
   (capability, plan, purpose=…)`; the purpose is the intent record's
   `purpose` column, so it is recoverable on the fresh path and both resume
   paths. Options scoping composes three chains: baseline (unchanged),
   longlist (`inherit → suggest → acquire → screen → classify → appraise →
   ingest → extract_interventions → longlist → constrain`) and targeted (the
   option search: the spine to `extract_interventions`, intent = the
   entrant's design). `ComponentStep.spine: bool | None` lets a chain
   declare which steps fail the walk; `None` keeps the Evidence search's
   global spine set, so every ES chain is unchanged. `inherit` and `suggest`
   are non-spine (owner: "inherit non-spine").

   *Rejected:* a purpose squeezed into `capability_run.capability` (its
   check admits only the two capabilities); persisting the composed chain
   (the intent record already carries the fact that selects it).

3. **The option search is a tool whose implementation is a child walk.**
   `run_option_search(design)` — the design is its only input (D26; queries
   are generated inside the walk as the Evidence search generates them; a
   `guidance` argument is a seam, tested during the build) — inserts a
   targeted intent record, mints the child's `capability_run_id`, and runs
   `run_plan` with `capability_run.parent_capability_run_id` set. Two
   callers: the longlist walk's runner-level fan-out after `suggest` (at
   most 15 per walk, the user's own options and the report-derived ones
   first, only new entrants on a rebuild) and the chat verb *add* (no
   parent). The runner joins before `longlist`, outside any transaction,
   bounded by a timeout; a failed child degrades the parent, never fails it.
   Owner: "I was thinking the mini evidence searches function as
   essentially a tool which the task agent runs"; "parallel at width 4,
   build the cross-walk bound in this task".

   *Rejected:* a harness component that dispatches walks (a component sees
   a connection and individual backends, never the engine, the backend
   bundle or an executor); the per-run-row poll to identify a child (it
   returns any new walk and times out behind the pool); a runner rewrite
   with per-step scopes and a fan-out primitive (touches the Evidence
   search's park-and-resume path); deferring the searches to assessment
   (owner: "if we don't do top-down searches at the longlist stage we could
   omit options that the user might be interested in").

4. **Concurrency is bounded twice.** Child walks run on their own pool of
   width 4, separate from the two-worker walk executor (a parent waiting on
   children in its own pool would deadlock). Two process-wide semaphores
   around classify's provider fan-out and ingest's parse workers close the
   fan-out seam task 044 recorded (owner: "add the semaphore"). The
   capacity gate counts parentless walks only. The database pool is not
   changed; peak connections are measured in the live check.

5. **Scoping readers see what exists and what is active, not a latest
   run** (owner: "scoping readers see what exists and what is active").
   `TaskOut.active_run` (any running or paused walk, children included) and
   `TaskOut.has_longlist` beside the artefact-based baseline signal; the
   chat resolves the longlist walk and its children's scopes once a
   longlist exists, the baseline walk before; the admission fences consider
   parentless walks only; `latest_run` is unchanged for the Evidence search
   and, for a scoping task, is the latest walk that is neither a child nor
   targeted. A child never opens or locks a tab and never closes the Task
   Agent conversation (`_finish_run` skips the closure for children; the
   gate's confirm branch closes it, keeping the 029 invariant).

   *Rejected:* one predicate on "latest" (the *add* child is parentless by
   design, so no predicate on the parent column suffices).

6. **The intervention profile is a third extraction profile on a
   selection-free path.** Registry component `extract_interventions`
   (`requires: [evidence_scope_id]`) calls `extract_scope(profiles=…,
   selection_run_id=None)` over every screened-in document of a scope;
   `extraction_result.selection_run_id` becomes nullable; the IOF-mandatory
   directive rule is not lifted (the component passes profiles directly).
   Names (owner, rejecting "intervention mention" and "abstract profile"):
   profile id `os_interventions_base_v1`, schema `interventions_v1`, prompt
   `extract_interventions_v1`, table `intervention_profile_record` — one
   row per intervention a document covers, with its role (evaluated ·
   described · recommended · comparator · mentioned), stated design
   features, bundle and parts, a quote anchor, and the shared reference
   columns; `finding_reference_union` gains a third branch. No adoptability
   flag. Decision-sheet rows E1, F2 and F3 are edited to this (owner: "Yes,
   selection-free, record it as an edit to those rows").

   *Rejected:* an `all_screened_in` select strategy (a selection row per
   scope, including one per option search, to say "all of them"); rows in
   the IOF or ICF table (a mention has no effect and no typed claim, so the
   trust rule "a mention is not support" would rest on a sentinel).

7. **The option entity and its records.** `option` (name, description, a
   versioned specified design, outcomes served, origin, state with its
   exclusion, primary and secondary lever types with the taxonomy version,
   the ambition tag), `option_membership` (one row per unit assigned — a
   profile record or an inherited finding — with the assignment reason and
   `design_feature_not_stated`), `option_relation` (`part_of`, `variant_of`
   reserved), the run-keyed `longlist_result` (themes, coverage, judgements,
   guesses, counts — the characterise pattern), and `task_link.option_id`
   (ADR 0037 D13). Option-level judgements are keyed `(option_id,
   design_version)` on the option row and in `longlist_result`; the
   annotation layer is not extended until a reader needs it; the ambition
   tag and the guesses are labelled reasoning in words, no claim row. A
   rebuild seeds the clustering with the existing options, so ids, user
   exclusions and additions survive; nothing is deleted.

   *Rejected:* an instance-of relation and a two-level longlist (sheet row
   A9; waits for evidence from live use); a run-time stability marker (a
   second clustering pass per run).

8. **Seeded clustering with the engine untouched.** The longlist component
   supplies a backend whose `discover` returns the seeds (the entrants; on a
   rebuild, every option) plus newly discovered options, and calls
   `cluster_units` as characterise does; one option per record, a document
   with several records in several options; counted `unclustered` and
   `not an option` buckets; ceiling `clamp(ceil(N/4), 8, 40)` counting
   seeds. Themes by a second unseeded run; lever typing against one
   versioned Python list for every domain (the instrument the state uses),
   with *none fits* counted and the runner-up recorded but never shown.

   *Rejected:* composing the engine's private assignment and repair
   functions (mirroring); a per-domain lever list (the shortlist's coverage
   denominator must be fixed, and themes already carry the domain's words).

9. **Inherited labels are read across through one resolver** (owner:
   "groundwork for a meta-analysis capability"; ADR 0037's A7 ruling
   honoured as written). `labels_for_snapshots` returns a document's
   evidence type and quality tier with provenance (own, inherited through
   `task_link` from the pinned run, or absent), own rows only when the task
   has no link; an inherited appraisal under a different rubric version is
   re-appraised rather than mixed. Classify and appraise skip resolved rows
   through one optional, fail-closed directive key each, computed per step
   by the runner's directive-authoring seam after the inherit step has run
   (contract surface-map row 3 amended; owner: "amend row 3"). Inherited
   `task_source_snapshot` rows keep their origin; they are inherited
   because the inherit step created them.

   *Rejected:* re-classifying (owner: "It feels like a waste"); copying
   rows (owner preferred reading across); a compose-time filter (the
   inherited rows do not exist at compose time).

10. **Where enters nothing in retrieval.** The longlist intent is
    PICO-shaped without a place (target unit, intervention open, outcomes,
    setting only when required); Where is neither in query generation nor
    the screen nor acquisition ranking (owner: "the idea of options
    appraisal is also to bring in international evidence that might be
    transferable"); it is shown on the way out as *where tried*, grouped
    against the plan's Where, and returns at transferability in task 3.
    "Transferable to *Where*" is a default preference on every scoping
    plan, checked at assessment, with no guess before it (concept ruling
    29). The Evidence search's query prompts are untouched.

    *Rejected:* Where as context for query generation (owner: "would that
    cause the query generation to inject the Where into every query?").

11. **The longlist verbs are two-turn actions.** While no parentless walk
    is active and a longlist exists, a Task Agent turn is sorted
    (`longlist_verbs_v1`) into question · add · exclude · include again ·
    other; a verb is proposed in words and applied only on the next
    confirming turn, as `kind = "action"` (`TurnActionOut`); the buttons
    call the same apply functions; a question is answered over the longlist
    walk and its children's scopes with a precedence rule for a document in
    two scopes. Owner: "chat verbs in task 2, buttons as the second way".

12. **The check-in card route stays `204`** (owner). The opened walk rides
    the plan route's response and the chat gate decision; the thread learns
    of it from the run stream. Six stage keys (`inherit`, `suggest`,
    `option_searches`, `extract_interventions`, `longlist`, `constrain`)
    widen the run stream's vocabulary additively; the six beat sentences
    are composed client-side from the completion summaries.

## Rollback

One alembic revision, reversible. Quiesce the API. `alembic downgrade -1`
refuses while any `capability_run` row has a scope of purpose `longlist` or
`targeted`; the remedy is `scripts/ops_remove_scoping_tasks.py` (ADR 0037)
extended to those walks, which hard-deletes the scoping tasks' longlist and
targeted walks, option rows, memberships, relations, `longlist_result` rows
and profile records. The downgrade then drops `option_relation`,
`option_membership`, `option`, `longlist_result`, `intervention_profile_record`,
the columns `task_link.option_id` and `capability_run.parent_capability_run_id`,
restores `NOT NULL` on `extraction_result.selection_run_id` (refusing while
a null row exists) and the two-branch `finding_reference_union`; deploy the
previous image. The eight new prompt surfaces and the `task_agent_scoping_v3`
re-pin revert with the image.

## Evidence

_Added in the build's Phase 8: the migration round-trip, the three live
longlists' funnel counts and stage-split times at both depths, the peak
database connections with four children, the profile's per-document cost,
the option search's per-entrant cost, the semaphores' measured effect, and
the D26 reading of the queries._

## Consequences

- A scoping task now has walks of three purposes and the readers that
  matter ask "what exists" and "what is active"; the Evidence search keeps
  its single-lineage reading untouched. Task 3's assessment walks follow
  the same pattern (a fourth purpose, `assessment`, already admitted by
  decision C4's vocabulary).
- Concurrency has two bounds the product never had; production sizing (the
  database pool, the pool widths) is measured here and decided later.
- The intervention profile is the first extraction profile without a
  selection run and the first over abstracts; task 3's light profile joins
  the same mechanism.
- The label resolver is the first cross-task read; it reaches only through
  an existing link and widens to findings when a later capability needs it.
- Open questions 4 (target longlist size) and 7 (deltas, not restarts)
  stay open; 5 (taxonomy storage) is closed. Deferred: the on-demand
  written summary, retrieval during the baseline pause, the cross-task
  profile memo, the `guidance` argument unless the build adds it, sheet
  row A9, the `task_link` uniqueness note for task 5.
