# Rubric: 004-screen

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; all checks are deterministic tests (no eval required this slice).
3. [ ] No approval-gated change snuck in unapproved — schema and Plan/Config interface change both approved in contract.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded in [verification.md](verification.md).
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md).
8. [ ] Required review stack ran (contract verifier · `/code-review` · `/security-review` · adversarial review) — findings in verification.md.
9. [ ] `/okf validate` ran — not expected to change this slice; pass confirmed.

### Slice-specific checks

10. [ ] `len(metadata.tables) == 13` — two new tables present.
11. [ ] Migration roundtrip clean: `alembic downgrade -1` then `alembic upgrade head` both succeed.
12. [ ] `project_source_snapshot` carries `uq_pss_id_project` composite unique after migration.
13. [ ] `source_screening_result` has all five check constraints, the `(screening_scope_id, project_source_snapshot_id)` unique constraint, and the `(screening_scope_id, status)` index.
14. [ ] Cross-project insert test: a result row with scope from project A and source from project B is rejected by the DB.
15. [ ] Fail-open: `_stub_screen` with no abstract → `status="relevant"`, `basis="title_only"` — never `not_relevant`.
16. [ ] `status="failed"` produces `basis=None`, `decision_confidence=None`; enforced both by stub and DB constraints.
17. [ ] `source_screening_result.screened_by_run_id` is set on every result row.
18. [ ] `ScreenContext.context` is loaded from `screening_scope.context` JSONB.
19. [ ] `source.screened` event payload matches the spec: six keys, nulls for basis/confidence when failed.
20. [ ] `component.completed` payload carries all seven keys: `component`, `screened`, `relevant`, `not_relevant`, `failed`, `title_abstract`, `title_only`.
21. [ ] Component-scope registry covers both `echo` and `screen`; unknown component still rejected.
22. [ ] No relevance state on `project_source_snapshot`.
23. [ ] `delete_project_data` cleans `source_screening_result` before `project_source_snapshot`, and `screening_scope` before `project`.
