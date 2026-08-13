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
       or font binary in the repo or the CDK asset tree. Config JSONs are committed
       **without** the `aws_account_id` field (resolved decision 4: account ID is
       env-injected; `cdk.context.json` gitignored); no real account ID, IP allowlist
       or similar operationally sensitive value in any committed file or verification
       evidence.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)), including the
       **per-file port map** (v2 source → v3 path · verbatim / targeted-edit / deleted /
       new).
7. [ ] Known gaps and deferred seams listed — the cross-instance steering/live-tail seam
       stays open in [docs/deferred.md](../../deferred.md); four items are closed there:
       licensed font delivery · deploy-invariant enforcement · FE↔real-API smoke
       (adv-M6) · `VITE_OIDC_AUTHORITY` production build guard.
8. [ ] Required review stack ran for Tier 4 (contract verifier · code review ·
       security-auditor lane · codex adversarial · human deep review), or skipped with
       written justification — findings in [verification.md](verification.md).

Slice-specific:

> Criterion 13 records task 026's original acceptance state. It was superseded
> 2026-08-11 by the dedicated, fixed-target jumpbox in
> [`030-rds-jumpbox`](../030-rds-jumpbox/contract.md).

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
13. [ ] Aurora reachable only from the API service SG, the migration-runner SG, and the
        documented SSM-tunnel path via the fck-nat instance SG (adversarial F4 — the
        tunnel is a contracted deliverable, its ingress rule is deliberate and
        described); no ingress rules ported for deleted v2 services.
14. [ ] **Capacity ceiling encoded and evidenced:** `RUN_EXECUTOR_MAX=10`, explicit
        SQLAlchemy pool sizing, and Fargate CPU/memory sized together for 10 concurrent
        runs (contract § capacity & concurrency); evidence = the 3-concurrent-run smoke
        plus the documented headroom arithmetic (adversarial F12 — config values alone
        don't establish the claim); the provider-rate-limit caveat and deploy-window
        caveat documented in `DEPLOYMENT.md`.
