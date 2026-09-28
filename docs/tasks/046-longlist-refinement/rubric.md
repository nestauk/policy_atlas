# Rubric: 046-longlist-refinement

The task is **done only if every box holds**. Terms, item numbers, rulings
(R1–R23) and measures (M1–M9) are defined in [contract.md](contract.md).
This file does not restate them.

## Items (one box per group; each cites the contract's item numbers)

1. [ ] **Discovery at reader grain (items 1, 4, 9; R1, R2, R9, R14, R20).**
   Suggestions are named at reader grain, and their designs name no place
   and no institution of one country. Discovery receives the plan, the
   baseline, the seeds and the corpus digest, and no unit payload. The
   option count never exceeds the hard ceiling. A suggested seed can be
   folded and then shows as a variant. A user's option is never folded or
   renamed. At most one residual pass runs and its outcome is in
   `provenance`. Discovery mints no package. Variants are computed from
   members and shown on the card.
2. [ ] **Assignment (items 2, 3).** The new rule is in the prompt. Prompts
   carry short ids only. The flag reads "not stated in the abstract". The
   model tier is the mini model, or the move is justified by a recorded
   measurement.
3. [ ] **Typing and themes (items 7, 8, 26).** `lever_types_v2` is in
   force and each option records its taxonomy version. Typing receives the
   plan and the baseline. Typing and constrain batches run in parallel. The
   typing wire has no `lever_reason` and no `runner_up_reason`. The
   runner-up lever is served and shown. A typing failure keeps the previous
   typing. Themes are built after constrain and hold included options only.
4. [ ] **Constrain (items 5, 6, 10, 11, 12; R4, R21).** No place token
   reaches the prompt. Population overlap does not exclude. Silence about
   the target unit or the setting passes. A setting requirement excludes
   only a kind of action that cannot be delivered through the setting. The relevant screen
   accepts a stated pathway. The distinct screen sees the whole list. A
   discovered option's outcomes come from its members' tags. Constrain
   receives the baseline.
5. [ ] **The intervention profile (items 13, 14, 16; R3).** Each new
   record carries the three tags. The fingerprint includes the
   tagging-context hash and no place. The setting rule and the negative
   examples are in the prompt. The code pass folds setting labels and moves
   places to geography with a logged repair.
6. [ ] **Thinning (item 15; R17).** The three unit rules hold. Title-only
   documents are not profiled. Non-evidence documents are profiled. Each
   rule's count is in `provenance`. No rule reads a tag.
7. [ ] **Screening (items 10, 18, 23; R5, R15, R16, R18, R19).** The
   planning prompt keeps target unit, setting and geography apart. The
   screen input of a longlist run holds the wide target unit and the
   outcomes, and no setting, no place and no option design. An option
   search of a longlist walk runs `acquire` only (marked by
   `acquire_only` in its scope's context, AM4), the join is before the
   screen, and each document has one stage-1 screen row per longlist walk.
   Units come from the longlist scope and from add-walk scopes only (AM5).
   The add walk is as built in task 045, without ingest (AM1). No file of
   the Evidence search screen changes.
8. [ ] *Withdrawn by AM1 (item 20, the classify skip list for the add
   walk). The number is kept so that later numbers do not move.*
9. [ ] **Ingest (item 22; R13).** Neither chain contains
   `ingest_full_text`. The chat answers over a longlist from abstract
   chunks and its citations are labelled *abstract only*.
10. [ ] **Tried on (item 23).** Coverage counts members by population tag.
    The card shows the *tried on* line. The list has the facet. Neither
    filters or excludes.
11. [ ] **Small (item 26).** The sub-national table. No double full stop
    in the composed intent or criteria.

12a. [ ] **Amendments from the review.** Each amendment in contract
    § Amendments from the review holds (AM1, AM3, AM7, AM8 and AM9 as the
    owner accepted them on 2026-09-28). Where an amendment and an item above differ,
    the amendment wins. A record with null tags reads as "not tagged". The
    place removal is recorded in `provenance`.

## Cross-cutting

12. [ ] **The reuse rule (R16, AM1, AM3).** Under `evidence_search/`,
    outside the intervention profile's own files, the only edits are the
    optional `interventions_context` argument on the extract path
    (`extract.py`, `extraction_backend.py`) and the title-only rule of the
    selection-free path. The IOF and ICF payloads, prompts and fingerprints
    are byte-identical. `screen.py` has no source change. The existing
    Evidence search tests pass with no edit. The search loop, the search prompts, the
    synthesis backend and the baseline targets are unchanged.
13. [ ] `make verify` passes (okf-validate · test · typecheck · lint ·
    build · drift-check · prompt-guard).
14. [ ] Six prompt revisions are re-pinned with their diffs recorded
    (`task_agent_scoping_v4`, `longlist_suggest_v2`, `extract_interventions_v2`,
    `longlist_cluster_v2`, `lever_typing_v2`, `constrain_v2`). Every other
    hash is unchanged.
15. [ ] **The staged check (R12).** The replay ran on the seven stored
    tasks and left their stored longlists unchanged. Three live rapid runs
    ran (obesity, refugees, caregiving). M1 to M6 pass on the hand reading,
    or a failed measure is reported as failed with its read-back. M7 to M9
    are reported beside the pre-contract figures. Each figure was read back
    from a saved result file. The other four live runs ran only if the
    owner asked for them.
16. [ ] One reversible alembic revision adds three nullable columns and
    nothing else. No new table.
17. [ ] No approval-gated change beyond the contract's § Constraints.
18. [ ] No generated files or secrets edited by hand.
19. [ ] No tests deleted, skipped or weakened without written
    justification.
20. [ ] Each spec change in contract § Spec changes is applied only if the
    owner accepted its wording, with the owner's words quoted and one line
    in `docs/specs/log.md`.
21. [ ] `docs/deferred.md` carries: a new entry for the system-level cost
    and latency task (items 21 and 24, a screen memo across scopes, L1,
    L3); the thin baselines added to § Synthesis optimisation as a second
    case; the full-text fetch for shortlisted options and its failure rate
    noted for task 3; user-visible loop budgets; the known limits of R22
    (provider-written abstracts, duplicates without a DOI, the untested
    guesses path, the process-wide option-search pool, empty OpenAlex
    queries). Open question 4 is marked closed.
22. [ ] ADR 0040 written, Accepted, with the rollback commands.
23. [ ] The Tier-4 review stack ran (contract verifier · `/code-review
    medium` · one security lane · `/simplify` · adversarial at contract and
    plan · human deep review). Findings are adjudicated in
    [verification.md](verification.md).
