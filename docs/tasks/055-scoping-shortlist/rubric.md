# Rubric: 055-scoping-shortlist

The task is **done only if every box holds**. Ticked by the review conversation; an unticked
box carries its reason in italics. Items (1–14), rulings (S1–S25), review amendments
(A1–A30, O1–O5) and measures (M1–M7) are defined in [contract.md](contract.md). This file
does not restate them.

## Items (one box per group; each cites the contract's items and rulings)

1. [ ] **Risk appetite (item 1; S2, S5, S10).** The plan holds `risk_appetite` with the three
   values and the default; the plan document shows and patches it; an appetite-only change
   mints a version, opens a shortlist walk when a longlist exists, and leaves
   `plan_inputs_changed` false; the Rebuild state reads `plan_inputs_changed`.
2. [ ] **Places and actions (item 2; S6, S7, S9).** Add to shortlist and Remove from shortlist
   on list rows, grid tiles and the card; Add turns a pick into added-by-you; Remove sets a
   pick aside and clears an added place without refilling; Exclude clears a place; events
   carry the actor.
3. [ ] **The component (item 3; S11–S16; A5, A7, A11–A13, O1).** One call over the card text
   of every included option, the plan, the baseline, the appetite, the kept places, the
   set-asides, one line per excluded option and the previous proposal; shuffled input; the
   hard checks with one re-ask then `ShortlistFailure` and the previous places kept; the note
   written even when no place is filled; the card text matrix held by the golden test; the
   character-ceiling cut only over the ceiling, counted and shown; the task-wide newest row
   locked; one `shortlist.proposed` event per proposal; a user place never merged, folded or
   cleared by constrain; a pick cleared when its option is excluded or merged.
4. [ ] **The walks (item 4; S5, S17).** `LONGLIST_CHAIN` ends in `shortlist` after `theme`,
   not spine; a failed shortlist degrades the walk with themes stored; `SHORTLIST_PURPOSE`
   runs the one component; the five registration points and the `select` stage mapping.
5. [ ] **Suggest more (item 5; S8).** Fills to five under five; adds one at five or more; 409
   when nothing remains or a walk is active, with the reason in words.
6. [ ] **Potential impact (item 6; S19–S22, S24).** A ninth plain line from `option_profile`
   on the judgment model, receiving the baseline and the outcomes as written; conditional
   form naming a pathway and a reach; "size of the prize" appears nowhere; no Reach line;
   `option_profile_v4` pinned.
7. [ ] **Maturity rung (item 7; S18).** Computed by code from coverage: the four rungs, the
   design mix as text, the two modifiers; served on the summary; shown on the card's Evidence
   opener and on shortlist rows; R90 vocabulary.
8. [ ] **The shortlist view (item 8; S23).** The third mode with header and appetite control,
   places with reasons and rungs, Remove, Suggest more and its disabled states, the
   not-covered note, Assess present and disabled with its one line, Other options with Add,
   the empty and degraded states.
9. [ ] **Chat and plan surfaces (item 9; S26, A14).** The Task Agent offers the three
   appetite options like depth and the draft wire carries the choice, default `mostly_tried`;
   `SCOPING_STEPS` and `task_agent_scoping_v6` say the shortlist is built and assessment is not
   yet available; no shortlist verbs by chat.
10. [ ] **Schema and interface (items 10; § Constraints).** One additive revision on
    `f1b6d3a8c2e5` with a downgrade that drops the columns and strips `risk_appetite` from
    plan payloads; read models additive only; OpenAPI regenerated; no new table; no file under
    `evidence_search/` changed.
11. [ ] **Prompts.** `shortlist_v1`, `option_profile_v4`, `task_agent_scoping_v6` pinned;
    every other hash unchanged; prompt texts recorded in `verification.md`.
12. [ ] **Staged check and measures (item 13).** The 24 stored proposals and the live rapid run
    done; M1, M2, M4 and M7 pass; M3, M5, M6 reported with each number read back from the saved
    file; tuning on four tasks, the check set read once.
13. [ ] **ADR (item 11)** written and Accepted with a rollback plan.
14. [ ] **Spec changes and deferred (items 14; § Spec changes).** Each applied spec change
    carries the owner's accepting words; `docs/deferred.md` lists the deferred seams
    (update-in-place, chat verbs, recall eval, comparability rule, inferring appetite,
    direction of effect); `docs/specs/log.md` has one line per applied change.

## Standard

15. [ ] `make verify` passes locally; the `verify` workflow's conclusion is `success` on the
    branch head SHA, with the run URL in `verification.md`; declared manual checks pass.
16. [ ] No approval-gated change beyond § Constraints — schema, auth/tenancy, egress, deps, CI,
    production config, public interfaces, scaffold.
17. [ ] No generated files or secrets edited by hand.
18. [ ] No tests deleted, skipped or weakened without written justification.
19. [ ] Verification evidence recorded ([verification.md](verification.md)), public-safe.
20. [ ] Review stack for Tier 4 ran (contract verifier · code review · security review on the
    routes and the plan patch · adversarial review at contract and plan · simplification), or
    skipped with written justification — findings in [verification.md](verification.md).
