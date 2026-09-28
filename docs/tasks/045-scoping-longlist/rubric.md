# Rubric: 045-scoping-longlist

The task is **done only if every box holds** — otherwise it is in progress,
not done. Terms and deliverable numbers are defined in
[contract.md](contract.md); this file does not restate them.

## Deliverables (one box each)

1. [ ] **Start the longlist.** `confirm_plan` at the gate and
   `POST .../plan/confirm-baseline` both record the decision and open a
   longlist walk (a new `capability_run`, intent record `purpose = longlist`,
   `plan_id` = the confirmed version) under the dispatch lock and the
   pre-insert reservation, so they cannot race `POST /runs`; unattended
   records and flags the standing default and opens the second walk too;
   the walk does not pause; "a longlist exists" means a `longlist_result`
   row; the walk ends `succeeded`, `degraded` (a child or the inherit step
   failed) or `failed` (a spine step failed, Result stays on the baseline
   with the failure line); "Search further" in words is refused honestly; an ES task has no
   longlist chain.
2. [ ] **The plan's new slots and the longlist intent.** `your_options[]`
   validates, is optional, keeps verbatim text and turn index, is asked
   once by `task_agent_scoping_v3` and has an Edit action; every scoping
   plan carries the default preference "Transferable to *Where*" (assumed,
   checked at assessment, following Where until edited, removable); the
   compiled longlist intent carries the target unit and outcomes, the
   setting only when a setting requirement exists, and never Where; Where
   enters neither query generation, nor the screen, nor acquisition
   ranking; the ES intent compile and the ES query prompts are unchanged.
3. [ ] **The chain and the pool.** The chain suggest → option searches ∥
   broad search → intervention profile → longlist → constrain is composed by
   purpose through the registry, with the declared spine membership;
   inherited `task_source_snapshot` rows exist once per linked document
   with their original origin, created by the inherit step; inherited,
   baseline and new documents are screened under the longlist scope in one
   generation; the label resolver returns inherited classification and
   appraisal with provenance and an explicit *absent*, applies the
   rubric-version rule, and never inserts rows; its three readers use it;
   classify and appraise skip resolved rows through their optional
   directive keys, computed per step by `leg_directive`; the broad acquire uses the
   compiled intent with the evidence restrictions as `ScopeConstraints` and
   the depth's target per backend; coverage and header counts collapse by
   normalised DOI while membership rows stay uncollapsed; the six progress
   beats appear at their boundaries.
4. [ ] **Suggestions and entrants, each with an option search.** The
   suggest step reads the plan, the baseline and the linked report's body,
   yields at most the bound, free with the lever-type checklist, each with
   a specified design, labelled *suggested by Policy Atlas* or *from your
   evidence search* (report section named); no profile record is created
   from the report; the plan's own options are entrants labelled *added by
   you*; `run_option_search(design)` exists with two callers and takes the design as its only input (a `guidance` argument only if the build's NEET option searches showed the need, recorded either way — D26); every entrant
   runs one child walk under its own targeted scope with
   `parent_capability_run_id` set, at the option-search target per backend,
   in parallel at width 4 under the cross-walk bound, at most 15 per
   longlist walk with the user's and the report's never dropped, and on a
   rebuild only for entrants with no prior option search; the classify and
   ingest fan-outs share the per-component semaphores across walks; a
   failing child degrades the parent and never closes the Task Agent
   conversation; an entrant whose search finds nothing
   survives with zero documents and says so; entrants are seeds in the
   clustering.
5. [ ] **The intervention profile.** `extract` runs the intervention profile
   (id `os_interventions_base_v1`, schema `interventions_v1`, prompt
   `extract_interventions_v1`, union kind `interventions`) over every
   screened-in document of a scope with no selection run and no IOF
   profile; `extract_interventions` is registered in the component
   registry, the harness graph and the plan mapping; `intervention_profile_record`
   rows carry the five roles, stated design features, bundle and parts, the
   quote anchor, and the shared reference columns including setting and
   study geography read from the abstract; a document covering no
   intervention is recorded; Non-evidence documents are profiled; records
   are memoised per (task, snapshot, fingerprint) and reused across scopes;
   they join the recreated union view; comparator records never become
   members; the IOF/ICF path is unchanged (existing tests pass untouched);
   "intervention mention" and "abstract profile" appear in no code name and
   no living spec.
6. [ ] **The longlist component.** Every record (profile record or inherited
   finding) is assigned to one option, or counted unclustered or not an
   option; a document with several records belongs to several options; the
   run is seeded with the entrants (and on a rebuild the existing options);
   `clustering_engine.py` has no source change and its tests pass; the
   ceiling is `clamp(ceil(N/4), 8, 40)`; options carry name, description,
   specified design v1, outcomes served, one primary lever type from the
   versioned constant list or *none fits* with a reason, secondary types,
   the taxonomy version, and an ambition tag with a justification (the
   words "as described, not measured" dropped by D33; owner 2026-09-24:
   "D33 wins, amend trust.md"); the runner-up is in
   `longlist_result` only; a bundle becomes a package with *part of* rows;
   themes are generated with a one-line "what it does"; coverage is the
   source-quality profile with Unknown and Non-evidence as their own
   buckets, the role funnel, where tried grouped against Where, settings,
   and flagged members counted and shown; membership rows carry an
   assignment reason and the `design_feature_not_stated` flag and no
   stability marker; characterise and group outputs are unchanged.
7. [ ] **Constrain.** Requirement constraints (a setting requirement among
   them) and the three default screens are judged per option on the
   specified design and coverage; every exclusion names its constraint;
   *distinct* never excludes a *part of* row; thin evidence never excludes;
   every preference except the transferability preference yields one capped
   reasoned guess per option that never changes state, and that one yields
   none; "no in-scope evidence" is computed deterministically from
   publication country and year, is exercised by an inherited-document
   fixture, leaves the option included, and names the restriction on the
   card.
8. [ ] **Option records and the walk's claims.** `option`,
   `option_membership`, `option_relation`, `longlist_result`,
   `intervention_profile_record`, `task_link.option_id` and
   `capability_run.parent_capability_run_id` exist in one reversible
   alembic revision that also relaxes `extraction_result.selection_run_id`
   and recreates `finding_reference_union`; judgements and guesses are
   keyed by `(option_id, design_version)` on the option row and in
   `longlist_result`, with no annotation or claim rows; a rebuild keeps
   option ids and user states, re-runs option searches only for new
   entrants, and never deletes an option; the downgrade refuses while a
   longlist or targeted walk row exists and the operator remedy is
   documented in ADR 0039; the ADR declares the walk's claim kinds with
   `option_membership` as the membership set.
9. [ ] **The longlist views** (as amended by D27–D34, 2026-09-23). When a
   `longlist_result` exists the Result opens on the list view with the
   view switch (Baseline · Longlist · Report unavailable), on the report's
   page chrome (sidebar, kind row, section disclosure shared with the
   report); the kind row carries the *scoping pass* chip with the
   screening sentence as its tooltip; the title is the plan's question and
   one line gives the counts; the setting facet, the where-tried facet
   and Group by (Theme · Lever type · Ambition) work; theme sections open
   collapsed with the description as the collapsed line and "N options ·
   {instruments}" in the heading, and lever and ambition groups carry the
   taxonomy definition and "N options · M themes"; option rows show
   "{Lever type} · {Ambition}", the document count, the origin when not
   clustered, the state chips, the exclusion reason and relations, and no
   *abstract only* or outcomes; excluded options sit in one collapsed
   Excluded options section outside Expand all; no sort. The reduced grid
   lays tiles by lever type and ambition, hides excluded options behind
   Show excluded, folds a cell beyond six options, leaves an empty row
   empty, and has no shortlist actions, gap messages or footer. The option
   card is assembled (no writer call) on the report's chrome with What it
   is · What it is for · What the evidence base holds so far (the
   documents as source cards, one per document) · Constraints and guesses
   (the transferability row as "checked at assessment") · Where it came
   from and what it relates to, "All N were read from the abstract only."
   where it applies, and the words "how sure" nowhere; `LonglistOut`
   serves `lever_type_definitions` and `ambition_bands[].definition`;
   Exclude (with a reason), Include again and Add an option work and each
   writes a History event as the user's turn; Sources, Share and History
   are otherwise unchanged and Sources reads inherited labels through the
   resolver.
10. [ ] **The Task Agent around the longlist.** While the longlist exists
    and no walk is active a turn is sorted by `longlist_verbs_v1` into
    question · add · exclude · include again · other; a question is answered
    over the union of the longlist and targeted scopes with citations,
    including a document only an option search found; a verb is confirmed
    before it is applied and never inferred; *add* proposes a design back
    through `option_design_v1`, mints the option as *added by you* and opens
    a child walk with no parent; *exclude* records the reason; verbs and
    buttons write the same state; a turn while a walk runs is 409
    `run_active`; the ordinary chat resolves the longlist walk after it
    runs; the plan step blurb no longer says "Not in this release"; the plan
    document dispatches `longlist_built` and `rebuild_or_keep` ahead of
    `confirmed`, shows "Longlist built · N options" in place of the old
    shared line and, after a plan change, *built from plan version N* with
    **Rebuild longlist**.
11. [ ] **System records and API.** The longlist routes exist with
    org-scoped reads (a link grants no read of options; the resolver reads
    only through an existing link); the plan route and the chat gate
    decision return the opened walk in an optional field and the card route
    stays `204`; `TaskOut.active_run` and `has_longlist` exist and scoping
    readers key on them (a running or finished child never becomes
    `latest_run` and never opens or locks a tab); `your_options` and the
    default preference are on the plan bodies; child walks appear on the run
    stream; the OpenAPI diff is additive and regenerated by `make
    openapi-sync`.

## Cross-cutting

12. [ ] `make verify` passes (okf-validate · test · typecheck · lint · build ·
    drift-check · prompt-guard); the declared live check (a)–(g) ran at
    rapid depth and is recorded with screenshots.
13. [ ] Eight new prompt-hash entries (`extract_interventions_v1`,
    `longlist_suggest_v1`, `longlist_cluster_v1`, `longlist_theme_v1`,
    `lever_typing_v1`, `constrain_v1`, `longlist_verbs_v1`,
    `option_design_v1`) and one re-pin (`task_agent_scoping_v3`, diff
    recorded); every other entry unchanged, the ES search prompts and the
    clustering callers' prompts included; every new prompt module is named
    `*_prompt.py`.
14. [ ] No approval-gated change beyond the contract's § Constraints — no
    second migration, no new host, no non-additive API change, no
    dependency, CI, auth or production config change.
15. [ ] No generated files or secrets edited by hand.
16. [ ] No tests deleted, skipped or weakened without written justification.
17. [ ] Verification evidence recorded in [verification.md](verification.md):
    the funnel counts and stage-split compute times of the three live
    longlists, the where-tried grouping on the NEET cards, the profile's
    per-document token cost, the option search's per-entrant cost, the
    cross-walk bound's measured effect, the migration round-trip, the
    OpenAPI and prompt-hash diffs, known gaps.
18. [ ] Known gaps and deferred seams listed in `docs/deferred.md` (the
    on-demand written summary; D18; the cross-task profile memo; open
    questions 4 and 7 as bounded; sheet row A9; the `task_link` uniqueness
    note), and the 044 per-run fan-out seam marked closed.
19. [ ] The spec changes in contract § Spec changes are applied with the
    owner's words quoted, the decision-sheet columns filled (E1, F2, F3 as
    an edit), and one line per change in `docs/specs/log.md`.
20. [ ] ADR 0039 written, Accepted, with the rollback commands.
21. [ ] The Tier-4 review stack ran (contract verifier · `/code-review
    medium` · one security lane · `/simplify` · adversarial at contract
    (done) and plan · human deep review), findings adjudicated in
    [verification.md](verification.md).
