# Rubric: <task-id>

Core completion criteria for medium/high-risk slices. Copy into `docs/tasks/<task-id>/`.
The task is **done only if every box holds** — otherwise it is in progress, not done.
Add slice-specific criteria (provenance, status markers, etc.) only where the contract demands them.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; declared manual/eval checks pass.
3. [ ] No approval-gated change snuck in unapproved — schema, auth/tenancy, egress, deps, CI,
       production config, public interfaces, scaffold (see the contract).
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md) or PR).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)).
