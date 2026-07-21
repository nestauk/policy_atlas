# Rubric: 026-infra-deployment

The task is **done only if every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes (including the new infra test target); declared manual checks
       pass (dev-env deploy + full-chain smoke + second-deploy invariant check + font
       check, as pinned in the contract).
3. [ ] No approval-gated change snuck in unapproved — schema, auth/tenancy, egress, deps,
       CI, production config, public interfaces, scaffold. In particular: no `cdk deploy`
       before the account/env 🛑 cleared; Cognito pool config was named in the approved
       plan.
4. [ ] No generated files or secrets edited by hand; no secret value, account credential
       or font binary in the repo, the CDK asset tree, or committed config (config JSONs
       are committed v2-style per resolved decision 4 — identifiers only, no secrets).
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)), including the
       **per-file port map** (v2 source → v3 path · verbatim / targeted-edit / deleted /
       new).
7. [ ] Known gaps and deferred seams listed — the cross-instance steering/live-tail seam
       stays open in [docs/deferred.md](../../deferred.md); the licensed-font-delivery and
       deploy-invariant-enforcement items are closed there.
8. [ ] Required review stack ran for Tier 4 (contract verifier · code review ·
       security-auditor lane · codex adversarial · human deep review), or skipped with
       written justification — findings in [verification.md](verification.md).

Slice-specific:

9.  [ ] **Copy-first discipline holds:** every ported file is diffable against its v2
        source; edits are targeted; no wholesale rewrites. Fresh code exists only for
        surfaces with no v2 precedent (Cognito, font bucket, migration runner swap).
10. [ ] **No Supabase remnants:** no Studio/postgres-meta/PostgREST/JWT-Lambda resources,
        SSM parameters, security-group rules, or config keys survive the port.
11. [ ] **Deployment posture encoded in CDK, not prose:** API service has
        `desired_count=1`, no autoscaling, stop-old-before-boot-new deployment config,
        short stop timeout — and the second-deploy check evidenced it.
12. [ ] **Auth chain live end-to-end:** Cognito-issued token verified by the deployed API
        (real JWKS fetch), frontend login via the existing `OidcAuthProvider` with
        config-only changes.
13. [ ] Aurora reachable only from the API service SG (and the migration runner); no
        ingress rules ported for deleted v2 services.
14. [ ] **Capacity ceiling encoded:** `RUN_EXECUTOR_MAX=10`, explicit SQLAlchemy pool
        sizing, and Fargate CPU/memory sized together for 10 concurrent runs (contract
        § capacity & concurrency); the provider-rate-limit caveat and deploy-window
        caveat documented in `DEPLOYMENT.md`.
