# Rubric: 006-appraise

The task is **done only if every box holds**.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes (test · typecheck · lint · build); no manual/eval checks required.
3. [ ] No approval-gated change snuck in unapproved — the gated changes (schema: new
       `source_appraisal_result` table + composite FKs + check constraint + migration; spec:
       one-line components.md §4 coverage clarification) are approved in the contract;
       nothing beyond them landed.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded in [verification.md](verification.md):
       - `make verify` table with pass counts.
       - Named test results from `test_appraise.py`.
       - Migration roundtrip (`alembic downgrade -1` / `alembic upgrade head`) — both clean.
       - Table count assertion: `len(metadata.tables) == 15`.
       - Check constraint coverage: `ck_sar_quality_score`.
       - Cross-project FK rejection test confirmed.
       - End-to-end command: harness with `component="appraise"`, result rows visible in DB.
       - Diff summary and public-safety confirmation.
7. [ ] Appraise reads the **classified set**: every `source_classification_result` row for the
       scope with an appraisable type gets exactly one appraisal row; relevant-but-unclassified
       rows are counted in `unclassified`, never appraised and never silently dropped.
8. [ ] `DEFAULT_RUBRIC` domain is exactly `EVIDENCE_TYPES` minus `Other (Non-evidence documents)`
       and `Unknown / Insufficient information` (test-enforced); values match the confirmed v2
       hierarchy exactly (5 = SR&MA, 4 = RCT/Quasi, 3 = Observational, 2 = Modelling · Policy
       Syntheses · Qualitative, 1 = Expert Opinion); persisted scores match the rubric for each
       evidence type exercised.
9. [ ] Non-evidence and Unknown sources produce **no appraisal row** and are counted
       (`skipped_non_evidence`, `skipped_unknown`) in the return value and the
       `component.completed` payload — skip is visible, never silent; Unknown remains
       kept-and-eligible.
10. [ ] `rubric_version` (`v2-hierarchy-v1`) is persisted NOT NULL on every row and carried
        in every `source.appraised` event payload.
11. [ ] Idempotency: re-running `appraise_sources` on the same scope inserts no duplicates;
        `already_appraised` reports the prior rows.
12. [ ] All constraint names explicit: `fk_sar_scope_project`, `fk_sar_pss_project`,
        `fk_sar_run_project`, `uq_sar_scope_source`, `ix_sar_scope_score`,
        `ck_sar_quality_score`.
13. [ ] `source.appraised` event payload keys and values match the contract spec exactly;
        no event emitted for skipped rows.
14. [ ] `delete_project_data` removes `source_appraisal_result` rows (FK-safe order); test
        confirms no rows remain.
15. [ ] Spec flow-back landed: components.md §4 coverage clarification + `log.md` entry, and
        nothing else in `docs/specs/` changed.
16. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md):
        steerable / plan-carried rubric; unique-constraint relaxation for re-appraisal under a
        new rubric version; typed dimensions with the full-text second pass; Unknown resolution
        on full text; v2's small-sample −1 penalty (needs sample size, deferred with the
        richer pass); appraisal→classification FK deliberately absent (mirrors the
        classify→screen entry).
17. [ ] Required review stack ran (Tier 3): contract verifier · `/code-review` ·
        `/security-review` · adversarial review (two heterogeneous reviewers) ·
        simplification pass — findings in [verification.md](verification.md).
18. [ ] `make okf-validate` green (components.md frontmatter still parses after the §4 edit).
