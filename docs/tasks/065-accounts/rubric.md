# Rubric: 065-accounts

The task is **done only if every box holds**. Ids (A1 to C6) are the contract's; terms are in
[contract.md](contract.md) § Terms.

1. [ ] Implementation satisfies [contract.md](contract.md), items A1 to C6.
2. [ ] `make verify` passes; `make openapi-sync` and `make drift-check` are clean; the infra
       synth tests pass; the declared staging live checks pass and are recorded.
3. [ ] No approval-gated change snuck in unapproved: schema (B1, C1, C2), auth/tenancy (B1,
       B4), production config (A1, B3), public interface (B7), deploy script (B3). Nothing else
       of those classes changed.
4. [ ] No generated files or secrets edited by hand; the allowlist address ranges, temporary
       passwords and email addresses appear in no committed file and no quoted log.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded in [verification.md](verification.md).
7. [ ] Known gaps and deferred seams listed; `docs/deferred.md` updated (SES entry discharged,
       admin-surface entry reopened, new seams: domains beyond `nesta.org.uk`, domain table on
       the ops page, application-sent email).
8. [ ] Required Tier 4 review stack ran: contract verifier · code review · security review ·
       adversarial review at contract, plan and code · human deep review; findings in
       `verification.md`.

Slice-specific:

9. [ ] **A1, A3.** With `email.enabled` true the synthesised pool carries `DEVELOPER` sending
       with the identity ARN in the pool's own account and region plus the From address; with it
       false the pool has no email configuration. No CDK resource creates an SES identity or DNS
       record.
10. [ ] **A2.** Both templates are HTML files under `infra/email/`, contain `{####}`, the
        invitation contains `{username}`, they are set on the pool only with `email.enabled`
        true, and the copy was owner-reviewed before the build ended.
11. [ ] **B1.** `is_ops` has no HTTP writer; the reader list is closed and asserted by a test;
        `ops grant` and `ops revoke` emit the post-commit admin trace; `user offboard` clears it.
12. [ ] **B2.** In `ops` mode the app serves only health and `/api/v1/ops/*` (no `/me`), every
        non-health route carries the ops-role dependency, and the ops lifespan constructs no run
        executor and calls no startup sweep, continuation drainer or ingest consumer (asserted with
        those entry points patched). In `api` mode no `/api/v1/ops` path exists. All are tests.
13. [ ] **B3.** The public API task role carries no `cognito-idp` action; the ops task role
        carries only the five listed, scoped to the pool ARN. The ops hostname is reachable only
        through listener rules on host header plus source address from the ops SSM parameter;
        `scripts/deploy.sh` validates and sizes that parameter and stops both services before
        migrating. Both roles are synth-pinned.
14. [ ] **B4, B9.** Every ops write calls a command function, inserts one `ops_action` row in
        the same transaction and emits one `ops.action` line, each with the caller's subject; no
        route re-implements a command; browser-created accounts always have an organisation;
        resend is 429 within an hour of the last send; 401 without a token, 403 without the role,
        200 with it; a non-ops token creates no `app_user` row through the ops host.
15. [ ] **B5.** The runtime image imports `policy_atlas.ops.commands` without the `ops`
        dependency group (a test runs the import with the stubs absent, or the build proves it).
16. [ ] **B6, B7.** The public `/me` carries `is_ops`; the `/ops` navigation entry shows only
        when it is true; the page calls the ops host from `VITE_OPS_API_BASE_URL` using types
        generated from `frontend/openapi-ops.json`; the public OpenAPI document has no ops path;
        `make openapi-sync` and `make drift-check` cover both documents; offboard asks for
        confirmation.
17. [ ] **B10.** ADR 0046 is Accepted with a date, amends ADR 0033 decision 4 and the 033 Out
        list, records the rejected shapes, the C4 abuse ceiling and the production ordering rule.
18. [ ] **B11, ensure-account.** `ops_action` is append-only with no route that updates or
        deletes it; the ensure-account command's three branches and the Cognito-created-then-
        database-failed retry are tested; the CLI's `create_user` is unchanged.
19. [ ] **C1 to C3.** The domain table exists with the CLI commands; the public waitlist route
        and its response are unchanged; the sweep runs only in ops mode with the self-signup flag
        true, stamps on success, retries after failure, enrols without sending when the address
        exists unenrolled, leaves an address enrolled elsewhere for an operator, stops at the hourly
        cap, and matches domains exactly (lower-cased, no subdomains).
20. [ ] **C4, C6.** The form response is byte-identical for a listed and an unlisted domain
        (conformance test); the ceiling (one per address, `max_per_hour`, listed domains only,
        resend cooldown) and the rule that production enables self-signup only after 064b's rate
        rule are stated in the ADR.
21. [ ] **Rollback.** Each step's rollback in contract § Constraints was exercised once on
        staging (A: `email.enabled` false; B: `desired_count` 0 then the downgrade with the
        service stopped; C: the flag false then the downgrade), and no rollback drops a table
        while a service that reads it runs.
