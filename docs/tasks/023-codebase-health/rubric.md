# Rubric: 023-codebase-health

The task is **done only if every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) — all nine work packages (+ WP10
       if optimisation items are adopted at the contract gate) landed or explicitly moved to
       deferred.md with the owner's sign-off.
2. [ ] `make verify` passes; the orchestrate stub-mode smoke completes under the new
       layout (zero egress); declared grep gates return zero stale module paths (incl.
       `policy_atlas.skeleton` / `policy-atlas-skeleton`).
3. [ ] No approval-gated change snuck in unapproved — dependency diff is exactly the WP9
       set; `uv.lock` unchanged; console-script rename limited to the target path; no
       schema/auth/CI/prod-config change.
4. [ ] No generated files or secrets edited by hand (alembic/versions content untouched).
5. [ ] No tests deleted, skipped or weakened without written justification — specifically:
       every prompt **pin test passes unmodified** (byte-identity of all pinned surfaces),
       and the WP1/WP8 test changes preserve or strengthen assertions (consolidation may
       not drop an assertion an original test made).
6. [ ] Behaviour preservation evidenced: every deletion matches a review-findings line item;
       moved-file diffs are path/import-only beyond the adjudicated cuts **and the three
       WP10 edits**, the facet_grouping constant fold, and the ingest_full_text anchor
       edit; owner-adjudicated KEEPs (v6 lane, ChunkReranker, search cache, leg_directive)
       are untouched; skeleton is fully retired (module + console script + references).
7. [ ] Verification evidence recorded ([verification.md](verification.md)) per the
       contract's list, including the codex-exhaustion review-routing note.
8. [ ] Known gaps and deferred seams listed — at minimum: fan-out consolidation,
       search-as-shared-tool seam, test consolidations 3–5, v6-deletion-post-eval, and any
       optimisation-lane deferrals → [docs/deferred.md](../../deferred.md).
9. [ ] Docs truth holds against the as-built tree: README describes the actual pipeline,
       layout and setup; AGENTS.md prompt pins match code; readiness.md carries the 022
       correction.
10. [ ] Required Tier-3 review stack ran (contract verifier · code review medium · one
        security lane · adversarial pass on the fallback ladder), findings adjudicated in a
        FRESH conversation — in [verification.md](verification.md).
