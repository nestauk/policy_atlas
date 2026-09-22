# Rubric: 045-scoping-longlist

The task is **done only if every box holds** — otherwise it is in progress,
not done. Terms and deliverable numbers are defined in
[contract.md](contract.md); this file does not restate them.

## Deliverables (one box each)

1. [ ] **Start the longlist.** `confirm_plan` at the gate and
   `POST .../plan/confirm-baseline` both record the decision and open a
   longlist walk (a new `capability_run`, intent record `purpose = longlist`,
   `plan_id` = the confirmed version); the walk does not pause and ends
   `succeeded` or `degraded`; unattended continues in one walk with the
   standing default recorded and flagged; "Search further" in words is
   refused honestly; an ES task has no longlist chain.
2. [ ] **The plan's new slot and the longlist intent.** `your_options[]`
   validates, is optional, keeps verbatim text and turn index, is asked
   once by `task_agent_scoping_v3` and has an Edit action; the compiled
   longlist intent carries the target unit and outcomes, the setting only
   when a setting requirement exists, and never Where; the longlist
   screening criteria carry no place; Where reaches query generation as
   context; the ES intent compile is unchanged.
3. [ ] **The chain and the pool.** The chain suggest → mini searches ∥ broad
   search → intervention profile → longlist → constrain is composed by
   purpose through the registry; inherited `task_source_snapshot` rows
   (origin `inherited`) exist once per linked document; inherited, baseline
   and new documents are screened under the longlist scope in one
   generation; inherited classification and appraisal are read across,
   never inserted; the broad acquire uses the compiled intent with the
   evidence restrictions as `ScopeConstraints` and the depth's target per
   backend; coverage counts by DOI where present; the progress beats appear
   in the thread.
4. [ ] **Suggestions and entrants, each with a mini evidence search.** The
   suggest step yields at most the bound, free with the lever-type
   checklist, each with a specified design, labelled *suggested by Policy
   Atlas*; the plan's own options (*added by you*) and the linked report's
   interventions (*from your evidence search*) are entrants; every entrant
   runs one mini search under its own targeted scope inside the same
   `capability_run`, at the mini target per backend, in a bounded fan-out;
   an entrant whose search finds nothing survives with zero documents and
   says so; entrants are seeds in the clustering.
5. [ ] **The intervention profile.** `extract` runs the intervention profile
   (key `interventions`, `intervention_profile_v1`) over every screened-in
   document of a scope with no selection run; `intervention_profile_record`
   rows carry the five roles, stated design features, bundle and parts, the
   quote anchor, and the shared reference columns including setting and
   study geography read from the abstract; a document covering no
   intervention is recorded; Non-evidence documents are profiled; records
   are memoised per (snapshot, version) and join the union view; comparator
   records never become members; the IOF/ICF path is unchanged (existing
   tests pass untouched); "mention" and "abstract profile" appear in no
   code name and no living spec.
6. [ ] **The longlist component.** Every record (profile record or inherited
   finding) is assigned many-to-many, or counted unclustered or not an
   option; the run is seeded with the entrants (and on a rebuild the
   existing options); the ceiling is `clamp(ceil(N/4), 8, 40)`; options
   carry name, description, specified design v1, outcomes served, one
   primary lever type from the versioned constant list or *none fits* with
   a reason, secondary types, the taxonomy version, and an ambition tag with
   a justification stored as a tier-4 claim; the runner-up is in
   `longlist_result` only; a bundle becomes a package with *part of* rows;
   themes are generated with a one-line "what it does"; coverage is the
   source-quality profile with Unknown and Non-evidence as their own
   buckets, the role funnel, countries, settings, and flagged members
   counted and shown; membership rows carry an assignment reason and the
   `design_feature_not_stated` flag and no stability marker; characterise
   and group outputs are unchanged.
7. [ ] **Constrain.** Requirement constraints (a setting requirement among
   them) and the three default screens are judged per option on the
   specified design and coverage; every exclusion names its constraint;
   *distinct* never excludes a *part of* row; thin evidence never excludes;
   every preference yields one capped reasoned guess per option that never
   changes state; "no in-scope evidence" is computed deterministically from
   publication country and year against the plan's restriction, leaves the
   option included, and names the restriction on the card.
8. [ ] **Option records.** `option`, `option_membership`, `option_relation`,
   `longlist_result`, `intervention_profile_record` and
   `task_link.option_id` exist in one reversible alembic revision;
   judgements and guesses are keyed by `(option_id, design_version)` on the
   option row and in `longlist_result`; a rebuild keeps option ids and user
   states, re-runs mini searches only for new entrants, and never deletes an
   option; the downgrade refuses while a longlist walk row exists and the
   operator remedy is documented in ADR 0039.
9. [ ] **The longlist views.** After a longlist walk the Result opens on the
   list view with the view switch (Baseline · Longlist · Report unavailable),
   the counts header, the Show filter and the setting facet, collapsible
   theme sections, option rows with origin, state, exclusion reason and
   relation, the Do nothing sentence with its link, and no sort; the reduced
   grid lays tiles by lever type and ambition, shows states, and has no
   shortlist actions, gap messages or footer; the option card is assembled
   (no writer call) with What it is · What it is for · What the evidence
   base holds so far · Constraints and guesses · Where it came from, the
   countries and setting lines, Show the documents, and the words "how
   sure" nowhere; Exclude (with a reason), Include again and Add an option
   work and each writes a History event as the user's turn; Sources, Share
   and History are otherwise unchanged.
10. [ ] **The Task Agent around the longlist.** While the longlist exists
    and no walk is active a turn is sorted by `longlist_verbs_v1` into
    question · add · exclude · include again · other; a question is answered
    over the longlist scope with citations; a verb is confirmed before it is
    applied and never inferred; *add* mints the option as *added by you*,
    proposes a design back and opens a targeted walk that assigns against
    the existing options; *exclude* records the reason; verbs and buttons
    write the same state; a turn while a walk runs is 409 `run_active`; the
    plan step blurb no longer says "Not in this release"; the plan document
    shows "Longlist built · N options" and, after a plan change, *built
    from plan version N* with **Rebuild longlist**.
11. [ ] **System records and API.** The longlist routes exist with
    org-scoped reads (a link grants no read of options); the confirm
    surfaces return the opened walk; `your_options` is on the plan bodies;
    the OpenAPI diff is additive and regenerated by `make openapi-sync`.

## Cross-cutting

12. [ ] `make verify` passes (okf-validate · test · typecheck · lint · build ·
    drift-check · prompt-guard); the declared live check (a)–(g) ran and is
    recorded with screenshots.
13. [ ] Seven new prompt-hash entries (`intervention_profile_v1`,
    `longlist_suggest_v1`, `longlist_cluster_v1`, `longlist_theme_v1`,
    `lever_typing_v1`, `constrain_v1`, `longlist_verbs_v1`) and one re-pin
    (`task_agent_scoping_v3`, diff recorded); every other entry unchanged;
    every new prompt module is named `*_prompt.py`.
14. [ ] No approval-gated change beyond the contract's § Constraints — no
    second migration, no new host, no non-additive API change, no
    dependency, CI, auth or production config change.
15. [ ] No generated files or secrets edited by hand.
16. [ ] No tests deleted, skipped or weakened without written justification.
17. [ ] Verification evidence recorded in [verification.md](verification.md):
    the funnel counts and stage-split compute times of the three live
    longlists at both depths, the countries on the NEET cards, the profile's
    per-document token cost and the mini search's per-entrant cost, the
    migration round-trip, the OpenAPI and prompt-hash diffs, known gaps.
18. [ ] Known gaps and deferred seams listed in `docs/deferred.md` (the
    on-demand written summary; D18; the per-run fan-out bound; open
    questions 4 and 7 as bounded; sheet row A9).
19. [ ] The spec changes in contract § Spec changes are applied with the
    owner's words quoted, the decision-sheet columns filled, and one line
    per change in `docs/specs/log.md`.
20. [ ] ADR 0039 written, Accepted, with the rollback commands.
21. [ ] The Tier-4 review stack ran (contract verifier · `/code-review
    medium` · one security lane · `/simplify` · adversarial at contract and
    plan · human deep review), findings adjudicated in
    [verification.md](verification.md).
