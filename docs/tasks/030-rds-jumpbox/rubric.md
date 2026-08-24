# Rubric: 030-rds-jumpbox

The task is **done only if every box holds** — otherwise it is in progress.

1. [x] Implementation satisfies [contract.md](contract.md).
2. [x] `make -C infra test` passes.
3. [x] No unapproved schema, auth, dependency, CI, or application-interface
       change is included.
4. [x] No generated files or secrets were edited.
5. [x] No tests were deleted, skipped, or weakened.
6. [x] Verification evidence is complete in [verification.md](verification.md).
7. [x] The custom Session document fixes the remote host and port and exposes
       only the local port to callers.
8. [x] The jumpbox has no ingress, no public IP, IMDSv2, database-only egress on
       the configured DB port, and only its environment-selected SSM path.
9. [x] Aurora no longer trusts fck-nat; migration, jumpbox, and BackendSG access
       remain distinct and synth-asserted.
10. [x] Local-only mode and imported RDS resources with an explicit SG are
        supported without invalid endpoint/connection assumptions.
11. [ ] A stack deploy and least-privilege engineer IAM policy are manually
        verified by the owner; until then, the slice remains pre-deploy.
12. [x] `NetworkStack` owns the production `ssm`/`ssmmessages` endpoints and
        their endpoint/client SG relationship; the jumpbox only consumes the
        managed-node SG.
13. [x] Staging synth has no interface endpoints; endpoint-mode synth has no
        public HTTPS fallback and fails closed when its SG is absent.
