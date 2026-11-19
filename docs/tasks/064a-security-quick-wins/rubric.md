# Rubric: 064a-security-quick-wins

The slice is **done only if every box holds**. Problem numbers Q1 to Q17 are defined in
[contract.md](contract.md) § The problems.

1. [ ] Implementation satisfies [contract.md](contract.md): every row of § The problems has
       its "Required" column true in the code.
2. [ ] `make verify` and `make -C infra test` pass; the staging live checks in the contract
       pass and are recorded.
3. [ ] No approval-gated change beyond the contract's list: one index migration, three config
       keys, six infra settings, one container command change plus one container
       environment variable, one deploy-script check, three added and one removed conflict
       code, the matching spec and OpenAPI updates.
4. [ ] No generated files or secrets edited by hand (`make openapi-sync` for the removed
       and added error codes if the contract changes).
5. [ ] No tests deleted, skipped or weakened without written justification. The ADR 0033
       reader test (`test_only_the_named_code_sites_read_the_is_admin_flag`) gains exactly
       one entry, `routers/tasks.py: create_task`, and ADR 0045 names it. The other tests
       that pin old values (contract § Read first) change only the pinned value.
6. [ ] One test per problem exists and fails on the old code: Q1 no locals in a JSON error
       log; Q2 duplicate email gives 201 and one row, and the request's transaction commits
       cleanly; Q3 a foreign exception stores its class name at each of the five sites, a
       product exception keeps its message and reason; Q4 `/healthz` is a coroutine
       function, plus the synth assertion; Q5, Q6 synth assertions; Q7 at each of the three
       admission sites the fourth concurrent run of one user is refused with
       `user_capacity`, another user's run is admitted, a paused run is not counted, and
       two starts by one user inside the reservation window count as two; Q8 the
       fifty-first task in a year is refused, an admin is not, a task older than 365 days
       is not counted, archived rows count, `/me` returns `used` and `limit` for a user
       and `null` for an admin, and the banner renders when `used >= limit` and not
       otherwise (vitest); Q9 the index exists after upgrade and is gone
       after downgrade, and the window subquery returns the same rows for a two-task
       fixture before and after the partition change; Q10 the fake Cognito client receives
       disable and global sign-out in that order, public tasks are made private, an
       already de-enrolled person is handled without error, a person with no `app_user`
       row is handled Cognito-only, a Cognito failure leaves the database untouched, and
       an admin-flag clear emits the admin trace; Q11 the Dockerfile `CMD` carries the three
       flags and the container environment carries `FORWARDED_ALLOW_IPS`; Q12, Q13, Q17
       synth assertions, with a production synth for retention 35; Q14 a dispatch that
       raises leaves its own run `interrupted`, a different active run on the same task
       is untouched, and the task admits a new run; Q15 the code maps to 409; Q16 forty
       threads released by a barrier onto an unknown key id cause one refresh, a refresh
       failure keeps the old keys and a valid token still verifies, a new real key is
       found after the window, and neither `get_current_user` nor `get_optional_user` is
       a coroutine function.
7. [ ] Verification evidence recorded in [verification.md](verification.md), including the
       Q9 `EXPLAIN ANALYZE` pair.
8. [ ] Known gaps and deferred seams listed (the 60-minute access-token window after
       offboard; spend caps; quota display) in [docs/deferred.md](../../deferred.md).
9. [ ] ADR 0045 written and accepted; `infra/DEPLOYMENT.md` documents the two config keys
       and the `user offboard` command.
10. [ ] Required review stack for Tier 4 ran, or skipped with written justification.
