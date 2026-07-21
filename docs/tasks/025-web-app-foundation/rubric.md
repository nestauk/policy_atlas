# Rubric: 025-web-app-foundation

Core completion criteria. The task is **done only if every box holds** — otherwise it is
in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes from the hoisted layout (backend + frontend + drift check);
       declared manual/browser checks pass; the pinned live check ran as specified
       (including the mid-run server restart) and is narrated in verification.md.
3. [ ] No approval-gated change snuck in unapproved — schema beyond the `project`
       migration, auth shape, deps beyond the approved lists, CI, public interfaces,
       scaffold (see the contract).
4. [ ] No generated files edited by hand — the TypeScript client is generated only;
       the drift check proves it (mutating a contract model fails the gate).
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed (component-progress protocol, hard purge,
       users/profile table, comments/versioning surfaces, narration, secure licensed-font
       delivery at deployment → docs/deferred.md).
8. [ ] Tier-4 review stack ran: contract verifier · code review · security-auditor lane
       (auth/JWT/CORS/SSE) · adversarial (contract + plan + code) · human deep review —
       findings adjudicated in [verification.md](verification.md).

Slice-specific:

9.  [ ] **One schema, two ends:** every frontend API call goes through the generated
        client; the mock implements the same generated interface; no hand-maintained
        parallel types.
10. [ ] **Durable-record-only reads:** pending check-ins, decision history, and all
        read models are served from Postgres; killing the API server mid-run loses no
        state the UI needs (replay test + live check).
11. [ ] **Real backend semantics:** rename persists to the `project` row; archive
        hides from listings while retaining all rows; no registry sidecar exists;
        answers to check-ins land in the durable steering record via the real seam.
12. [ ] **Auth fail-closed:** every data route rejects unauthenticated (401) access;
        cross-owner access returns 404 indistinguishable from absent (BOLA) —
        proven by the authz test matrix; dev issuer is
        visibly non-production; Cognito cutover requires config only (documented).
13. [ ] **Hoist is import-neutral:** `policy_atlas` import name unchanged; full
        backend suite green post-hoist; CI/Docker/doc paths updated (grep-verified,
        no stale `src/` references).
14. [ ] **RETRO §2 product decisions hold in the UI:** locked vocabulary (component
        names never rendered; labels from the server), appraisal labels never raw
        scores, data-driven surfaces hide rather than fake, annotation layer renders
        in the prose, one shared source dossier.
15. [ ] **No new prompt surfaces:** diff over `runtime/` prompt families is empty;
        the check-in content of record is the deterministic render.
16. [ ] **Accessibility floor:** keyboard-operable check-in card + dossier;
        `prefers-reduced-motion` honoured; no horizontal body scroll at target widths.
17. [ ] **API consistency (contract § API design pins):** single error envelope +
        pinned status mapping on every route; unbounded list endpoints paginated;
        snake_case JSON throughout; SSE/check-in variants are generated discriminated
        unions (no hand-rolled event types); no verbs in resource paths.
18. [ ] **Concurrent users, different projects:** two overlapping runs on two projects
        (distinct users) complete without cross-talk (SSE, steering, read models);
        the concurrent-run bound counts paused walks and at-bound dispatch 409s;
        the plan's chain thread-safety audit ran and its findings are recorded;
        no per-run config via module globals anywhere in the API path.
19. [ ] **Pre-registered deferred.md discharges hold:** one-active-run-per-project
        enforced in Postgres at dispatch (not app memory); citation-context clamp on
        the chunk-context read model; model-authored display strings scrubbed at
        render (no `dangerouslySetInnerHTML` on model/source strings); interrupted
        runs marked by the startup orphan sweep and rendered honestly.
