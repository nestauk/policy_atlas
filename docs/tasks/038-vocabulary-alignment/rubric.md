# Rubric: 038-vocabulary-alignment

Core completion criteria. The task is **done only if every box holds** — otherwise it is in
progress, not done. Terms and defect ids V1–V9 are defined in [contract.md](contract.md);
this file does not restate them. Defect ids run V1–V12.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes (including `drift-check`, `prompt-guard`, `okf-validate`);
       declared manual/eval checks pass.
3. [ ] No approval-gated change snuck in unapproved — the gated changes are the schema
       migration (five tables), the `/api/v1` path change, the Makefile variable names, the
       two env var names, the prompt word swaps under R1, and the auth-adjacent V11; each
       approved at the contract gate and nothing beyond them.
4. [ ] No generated files or secrets edited by hand (`openapi.json`, `gen/types.ts` via
       `make openapi-sync` only).
5. [ ] No tests deleted, skipped or weakened without written justification. Every test
       change is a renamed identifier, path or string, except the new tests V8, V9 and V11
       add and the deletions V10/V12 justify (dead code, stale live specs) — the diff proves it.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed (the `eb_*` fingerprint ids, regenerated public
       links, Metabase and Langfuse filters, the phase model for the Task Agent thread →
       [docs/deferred.md](../../deferred.md) § Vocabulary).
8. [ ] Required review stack ran for Tier 4 (contract verifier · code/security review ·
       adversarial at contract, plan and code · simplification) — findings in
       [verification.md](verification.md).

Slice-specific:

9. [ ] **V1 / I1** — the migration renames `project`→`task` and
       `project_source_snapshot`→`task_source_snapshot` with every column, constraint, index
       and the union view, from the checked-in manifest; the round-trip test (upgrade →
       downgrade → upgrade, seeded with all four old event kinds, an old steer-point payload
       and an `orchestrator` decision) passes and the downgrade reverses stored values; a
       pre-migration row reads identically under `/api/v1/tasks/{id}`.
10. [ ] **V2 / I2** — `portfolio`→`project` lands second in the same migration; the 033
        tenancy and membership tests pass with renamed identifiers only.
11. [ ] **V3 / I3** — package `evidence_search`; `capability_run.capability` updated with
        the CHECK swapped; the copy table applied verbatim ("evidence base" kept for the
        collection, "report" for the page, "evidence search" for the capability); the
        identifier grep is clean except the kept ids; `evidence_search_coverage` written, both
        ids read.
12. [ ] **V4 / I4** — no `orchestrat` token remains outside historical docs and frozen
        sources: modules, classes, log/span names, env vars, the `plan` table and the prompt
        text all say agent; wire literal `agent`; a pre-migration `orchestrator` decision
        renders "The Agent decided" (read-side normalisation, no `event_log` rewrite).
13. [ ] **V5 / I5** — tabs read Agent · Result · Sources · Share · History; the Agent tab is
        the task index route; `/result` segment; tab locking unchanged.
14. [ ] **V6 / I6** — the eighteen leaked literals route through `vocabulary.ts`; the
        literal grep is clean.
15. [ ] **V7 / I7** — `docs/specs/vocabulary.md` (A8 option 2) exists and is indexed; data-model
        and web-api specs updated; ADR 0031 decision 2 marked superseded; ADR 0036
        Accepted with rollback commands; `deferred.md` entries discharged; frozen sources
        and historical docs untouched (`git diff --stat -- docs/specs/sources docs/tasks/0[0-3]*`
        is empty except this task's folder and the three `JUMPBOX.md` link edits in
        `docs/tasks/030-rds-jumpbox/verification.md`, `033-organisations/plan.md` and
        `033-organisations/verification.md` — V12; the frozen definitions snapshot
       `docs/specs/sources/vocabulary/policy-atlas-definitions.md` (A8) and the two
       plan-only folders V12 deletes, `029-search-volume-cap` and `030-multi-round-search`).
16. [ ] **V8 / I8** — the overlay copy table applied; the chat list shows on the Agent tab
        with exactly one "Task Agent" pinned first, marked by its label only (active planning
        row, else newest closed; older lineages read "Earlier plan"); no chat is labelled
        "Planning"; chats are still called chats; a non-owner's list is unchanged but for
        labels.
17. [ ] **Collision audit** ran before the sweep and every listed collision has a recorded
        resolution; the sweep script is committed under `scripts/` and re-runnable.
18. [ ] **No behaviour change beyond the enumerated deltas** (routes and URLs · labels ·
        trace grouping · sign-in landing; **amended 2026-09-05** by the owner's build-time
        requests — contract § Amendments) — no test assertion changed in meaning; the prompt
        diff is one-to-one word swaps only (R1) and `prompt_hashes.json` is re-pinned in the
        same commit; `uv.lock` and `pnpm-lock.yaml` unchanged.
19. [ ] **V9 / I9** — planning turn, run start, steering continuation and chat turn share
        `session_id` = task id (stub-client test); chat metadata carries `conversation_id`;
        one staging Task shows as one Langfuse session.
20. [ ] **V10 / I10** — `call_budget` replaces `http_budget`; `RunPane`/`JourneyPane` and their
        orphans are deleted with the justification recorded; six `deferred.md` entries marked
        discharged or corrected as V7 lists.
21. [ ] **V11 / I11** — the post-sign-in navigation test passes; the staging sign-in round
        trip from a task deep link lands on it; 036's signed-out deep-link stash still works;
        the security lane's findings on V11 are in [verification.md](verification.md).
22. [ ] **V12 / I12** — AGENTS.md ≤ 60 lines; knip and vulture outputs recorded and clean as
        I12 states; the listed files are gone from `git ls-files`; `infra/JUMPBOX.md` and its
        referrers updated; the ignore entries present.
23. [ ] **Live checks**: pre-merge, the local check (`make dev` + `make fe-api-smoke` against
        the local API: one Task through its five tabs, its Project, one signed-out public URL,
        one sign-in round trip) is in `verification.md`; post-merge and before the production
        promote, the staging check (one existing Task, its Project, one fresh public link, one
        sign-in round trip, `rows assign --task` dry run, `make fe-api-smoke`) is a dated
        addendum to `verification.md` on `dev`; the Metabase and Langfuse follow-ups are named
        in the PR.
