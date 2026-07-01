# Rubric: 005-classify

The task is **done only if every box holds**.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes (test · typecheck · lint · build); no manual/eval checks required.
3. [ ] No approval-gated change snuck in unapproved — the one gated change (schema: new
       `source_classification_result` table + composite FKs + check constraints + migration)
       is approved in the contract; nothing beyond it landed.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded in [verification.md](verification.md):
       - `make verify` table with pass counts.
       - Named test results from `test_classify.py`.
       - Migration roundtrip (`alembic downgrade -1` / `alembic upgrade head`) — both clean.
       - Table count assertion: `len(metadata.tables) == 14`.
       - Check constraint coverage: `ck_scr_primary_evidence_type`, `ck_scr_open_tags_array`.
       - Cross-project FK rejection test confirmed.
       - End-to-end command: harness with `component="classify"`, result rows visible in DB.
       - Diff summary and public-safety confirmation.
7. [ ] Only `status='relevant'` rows from `source_screening_result` are classified —
       `not_relevant` and `failed` rows are skipped; `classified + skipped = total` invariant holds.
8. [ ] `Other (Non-evidence documents)` rows persist in `source_classification_result`
       (flag-don't-drop); `Unknown / Insufficient information` rows are also persisted.
9. [ ] `open_tags` is always a JSON array (`[]` in stub); `ck_scr_open_tags_array` constraint fires
       on a non-array value in the test suite.
10. [ ] All constraint names explicit: `fk_scr_scope_project`, `fk_scr_pss_project`,
        `fk_scr_run_project`, `uq_scr_scope_source`, `ix_scr_scope_type`,
        `ck_scr_open_tags_array`, `ck_scr_primary_evidence_type`.
11. [ ] `source.classified` event payload keys and values match the contract spec exactly
        (including `"Unknown / Insufficient information"` — not the abbreviated form).
12. [ ] `delete_project_data` removes `source_classification_result` before
        `source_screening_result` (FK-safe); test confirms no rows remain.
13. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md):
        LLM-based classify tool, `open_tags` population, grey-lit granularity,
        `Unknown` resolution on full text.
14. [ ] Required review stack ran (Tier 3): contract verifier · `/code-review` ·
        `/security-review` · adversarial review (two heterogeneous reviewers) ·
        `/code-simplify` — findings in [verification.md](verification.md).
15. [ ] `/okf validate` ran (no `docs/specs/` or `docs/knowledge/` changes expected;
        confirm or note if touched).
