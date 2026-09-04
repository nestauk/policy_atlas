# Rubric: 038-vocabulary-alignment

Core completion criteria. The task is **done only if every box holds** — otherwise it is in
progress, not done. Terms and defect ids V1–V8 are defined in [contract.md](contract.md);
this file does not restate them.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes (including `drift-check`, `prompt-guard`, `okf-validate`);
       declared manual/eval checks pass.
3. [ ] No approval-gated change snuck in unapproved — the schema migration, the `/api/v1`
       path change and the Makefile variable names are the only gated changes, each
       approved at the contract gate.
4. [ ] No generated files or secrets edited by hand (`openapi.json`, `gen/types.ts` via
       `make openapi-sync` only).
5. [ ] No tests deleted, skipped or weakened without written justification. Every test
       change is a renamed identifier, path or string — the diff proves it.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed (the V3 kept ids, F2 internals, F3 legacy redirects,
       Metabase → [docs/deferred.md](../../deferred.md) § Vocabulary).
8. [ ] Required review stack ran for Tier 4 (contract verifier · code/security review ·
       adversarial at contract, plan and code · simplification) — findings in
       [verification.md](verification.md).

Slice-specific:

9. [ ] **V1 / I1** — the migration renames `project`→`task` with every column, constraint,
       index and the union view; the round-trip test (upgrade → downgrade → upgrade)
       passes; a pre-migration row reads identically under `/api/v1/tasks/{id}`.
10. [ ] **V2 / I2** — `portfolio`→`project` lands second in the same migration; the 033
        tenancy and membership tests pass with renamed identifiers only.
11. [ ] **V3 / I3** — package `evidence_search`; `capability_run.capability` updated with
        the CHECK swapped; the copy table applied verbatim; the invariant grep is clean
        except the kept ids; `prompt_hashes.json` values unchanged (keys re-pathed).
12. [ ] **V4 / I4** — no user-visible "orchestrator"; wire literal `agent`; a
        pre-migration `orchestrator` decision renders "The Agent decided" (read-side
        normalisation, no `event_log` rewrite).
13. [ ] **V5 / I5** — tabs read Agent · Result · Sources · Share · History; the Agent tab is
        the task index route; `/result` segment; tab locking unchanged.
14. [ ] **V6 / I6** — the eighteen leaked literals route through `vocabulary.ts`; the
        literal grep is clean.
15. [ ] **V7 / I7** — `docs/specs/system/vocabulary.md` exists and is indexed; data-model
        and web-api specs updated; ADR 0031 decision 2 marked superseded; ADR 0036
        Accepted with rollback commands; `deferred.md` entries discharged; frozen sources
        and historical docs untouched (`git diff --stat -- docs/specs/sources docs/tasks/0[0-3]*`
        is empty except this task's folder).
16. [ ] **V8 / I8** — the overlay copy table applied; the chat list shows on the Agent tab
        with "Task Agent" pinned first and marked; no chat is labelled "Planning"; chats are
        still called chats.
17. [ ] **Collision audit** ran before the sweep and every listed collision has a recorded
        resolution; the sweep script is committed under `scripts/` and re-runnable.
18. [ ] **No behaviour change** — no test assertion changed in meaning; no prompt text
        changed; `uv.lock` and `pnpm-lock.yaml` unchanged.
19. [ ] **Staging live check** ran as scoped in the contract (one Task, its Project, the
        ops CLI dry-run, `make fe-api-smoke`) and the Metabase follow-up is named in the PR.
