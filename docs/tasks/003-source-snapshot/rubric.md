# Rubric: 003-source-snapshot

The task is **done only if every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes (test · typecheck · lint · build).
3. [ ] No approval-gated change snuck in unapproved — schema, auth/tenancy, egress, deps, CI,
       production config, public interfaces, scaffold.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded in [verification.md](verification.md).
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md).
8. [ ] Required review stack ran (contract verifier · `/code-review` · `/security-review` ·
       adversarial review) — findings in [verification.md](verification.md).
9. [ ] `/okf validate docs/knowledge` ran (no new concept files this slice, so pass expected).

### Slice-specific checks

10. [ ] `source_snapshot` has no `project_id` column — identity is content, not project.
11. [ ] `chunk.segmentation_policy` column exists and is populated (`manual_v1` this slice).
12. [ ] `chunk.source_locator` is not used — `source_locator` lives on `source_snapshot`.
13. [ ] Upload ingest creates a **new** `source_snapshot` row on each call — no silent
        content-hash dedup for uploaded sources.
14. [ ] Every `annotation` with `annotation_type = 'citation'` has a corresponding `citation` row
        with a non-null `chunk_id` FK — no JSONB-only references.
15. [ ] `produce_grounded_block` no longer calls `fixtures.get_source()`; all chunk lookups go
        through the DB.
16. [ ] Fabricated-quote hard-fail still fires: `GroundingError` raised, `citation.verification_result = 'fail'`,
        `chunk_id` FK still set (flag-don't-drop).
17. [ ] `citation.verification_result` values are `pass` | `fail` only — grounding tier from the
        LLM-as-judge is a deferred seam, not stored this slice.
