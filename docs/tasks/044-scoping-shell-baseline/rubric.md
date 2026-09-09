# Rubric: 044-scoping-shell-baseline

The task is **done only if every box holds** — otherwise it is in progress,
not done. Deliverables 1–10, decisions D1–D13, the second-round amendments,
the adversarial findings A1–A18 and the terms are defined in
[contract.md](contract.md); this rubric points at them and restates nothing.

## Deliverables (one box each — A18e)

1. [ ] **1 Task kind** lands: `task.capability` written at creation, never
       derived (D2); the card, list and header say "Options scoping" (D5);
       the list shows no depth (owner).
2. [ ] **2 Task Agent rename** lands as one commit reviewed on its own before
       feature code, complete per the contract's list (A10): conversation
       kind, transcript table and column, routes, models, frontend consumers,
       the ES `planner` module, class and environment-variable names,
       constraint and index names, stored `kind` and `created_by` values
       rewritten and reversed on downgrade; the version string `planner_v11`
       still stands; the sweep test finds none of the old names and honours
       the allow-list (`eb_iof_base_v1`, `eb_icf_base_v1`,
       `evidence_base_coverage`); the rename manifest from the plan phase is
       the checklist (C13); the conversation kind is `task_agent`, not
       `agent`. The EB → ES sweep covers the living specs, skills, templates,
       agentic-ops and code comments and leaves ADRs, merged task docs,
       `docs/specs/log.md`, frozen sources and quoted rulings untouched
       (A11), recorded by grep in `verification.md`.
3. [ ] **3 Start a scoping task**: the form is question plus Starts from
       only, same-project Evidence search tasks; no depth or job control; one
       create request carrying projects and links (C10).
4. [ ] **4 Link and inherit**: `task_link` rows with the contract's rules and
       a pinned `source_capability_run_id` of a finished walk (C11); a link
       whose tasks stop sharing a project renders flagged (A18b, C12); the
       Task Agent's context carries the linked plan, the report body without
       citations and the coverage statement, fenced once and stable across
       turns; nothing is copied into the receiving task's rows (D4).
5. [ ] **5 Scoping plan**: the § Plan object fields validate as specified
       through the capability registry (C9); provenance is at version grain
       (C16); an ES task rejects a scoping payload and the
       reverse (D1); the plan document renders every scoping section with its
       Edit action (C18).
6. [ ] **6 Task Agent for a scoping task**: `task_agent_scoping_v1` offers
       the two depths as labelled options, never the internal keys (A8);
       Where defaults to the United Kingdom tagged assumed; the constraint-
       kind question and the Where warning (D8) behave; steering mode is not
       asked and defaults to moderate.
7. [ ] **7 Baseline run**: the eight required sections are supplied and
       always present; at most two proposed sections; every section can
       render the not-found state; the key assumption and what is contested
       carry the reasoning label; claims are chunk, reasoning or gap only
       (A7); the baseline's own Sources section names what was not searched
       (A14); the intent record carries `purpose=baseline` and its `plan_id`
       (A16); sections are written sequentially with the ES-only passes off
       (C6, C7); the sequential-versus-parallel feasibility check is recorded
       and none of it ships; compute time measured and recorded.
8. [ ] **8 The gate**: `baseline_confirm` exists only in the scoping chain
       and an ES walk in frequent mode never names it (A2); it pauses in
       frequent, moderate and minimal; in unattended it writes a recorded,
       flagged `standing_default` decision without pausing and the plan
       carries that default (A9, D11); non-approving Task Agent turns are
       admitted while paused, sorted into question · decision and dispatched
       to the answer core or the existing check-in response transaction bound
       to run, check-in and plan version (A12, C2, C5); Change the plan ends
       the walk, the next Task Agent turn mints a new plan version and the
       user chooses Rebuild baseline or Confirm plan and build longlist (C1,
       C3); the steering router is
       untouched; the approving branch and `PATCH /plan` stay fenced (A6); a
       decision from chat or card lands in one transaction (A13); an ES pause
       still refuses turns; nothing after the gate runs (D12).
9. [ ] **9 Tabs and views**: Result shows the baseline with the band and run
       state; Sources, Share and History unchanged.
10. [ ] **10 System records**: exactly the schema changes named in the
        contract § Constraints, in two reversible revisions — the rename
        revision (phase one) and the slice revision (phase two; owner ruling
        2026-09-09) — whose downgrades reverse the stored values, the slice
        one refusing while any `task` or `capability_run` row carries
        `options_scoping` (A5).

## Cross-cutting

11. [ ] `make verify` passes; the deterministic test list in the contract
        § Acceptance checks is present and green; the pinned live check
        (a)–(g) ran with notes, screenshots and measured times (compute for
        both baseline builds; gate-sort latency).
12. [ ] The OpenAPI diff is additive apart from the path rename;
        `frontend/openapi.json` and `frontend/src/api/gen/types.ts` changed
        only via `make openapi-sync`; no generated files or secrets edited by
        hand.
13. [ ] Prompt hashes: three new entries (`task_agent_scoping_v1`, the
        baseline template, the gate sort); the ES Task Agent entry's path
        moved with its byte-identical file, hash unchanged (C14); the ES section proposer changed only if template mode needed
        it, versioned if so; the section writer's prompt is template-keyed
        with the ES preamble rendering byte-identical messages (owner ruling
        2026-09-09, contract § Constraints) and its module re-pinned once as a
        words-only diff; every other hash unchanged; the ES chain and
        the ES's card-based steering behave as before, pinned by the
        existing tests.
14. [ ] No tests deleted, skipped or weakened without written justification.
15. [ ] Verification evidence recorded ([verification.md](verification.md)),
        including the three-baseline qualitative note with compute times and
        the review-lane dispositions.
16. [ ] Known gaps and deferred seams listed in
        [docs/deferred.md](../../deferred.md): per-field turn provenance ·
        Search further (D10) · inherited document rows (task 2, D4) ·
        `task_link.option_id` (task 2, D13) · scoping deep (D6) · the later
        latency levers (D7) · the Task Agent as the Evidence search's control
        surface and any chat carrying Task Agent turns (D9).
17. [ ] The seven spec changes in contract § Spec changes are applied with the
        owner's words quoted and logged in `docs/specs/log.md`; sources
        untouched.
18. [ ] ADR 0037 written and Accepted with sign-off date, with the rollback
        commands and the operator remedy (A5).
19. [ ] Required review stack for Tier 4 ran (contract verifier ·
        `/code-review medium` · one security lane · adversarial at contract,
        plan and code · `/simplify` · human deep review), or a step was
        skipped with the owner's written ruling — findings and dispositions
        in [verification.md](verification.md).
