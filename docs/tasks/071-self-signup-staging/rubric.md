# Rubric: 071-self-signup-staging

The task is **done only if every box holds**. Ids are those of [contract.md](contract.md).
Each slice row names the kind of test that proves it.

## Core

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; the live checks of E3 pass.
3. [ ] No approval-gated change beyond the contract's gate table.
4. [ ] No generated files or secrets edited by hand (`make drift-check` green).
5. [ ] No test deleted, skipped or weakened unless its behaviour stays covered and the
       review confirmed it.
6. [ ] Verification evidence recorded in [verification.md](verification.md).
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md).
8. [ ] The Tier 4 review stack ran (contract verifier · security · Codex adversarial · code
       review · design lane), findings adjudicated in `verification.md`.

## Slice

**Part A**

9. [ ] A1: the form shows the annex intro and success message (rendered-component test).
10. [ ] A2: the invite line shows only when the address carries `invite` (component test).

**Part B**

11. [ ] B1, B5: Add person with two cohorts stores both memberships and two `cohort.add`
        audit rows (route test, stored rows).
12. [ ] B2: an unknown cohort gives 404 and the Cognito double receives no call (route test).
13. [ ] B3, B6, I6: a refused create (another organisation) leaves no membership (route test).
14. [ ] B1 on Approve: an approved request joins the chosen cohorts (route test).
15. [ ] B7: the Cohorts field is on Add person and both Approve dialogs and is sent
        (component tests).

**Part C**

16. [ ] C1, C2: the check route answers rows for a good file, including one with a byte-order
        mark and one with a quoted name that holds a comma (route test).
17. [ ] C2: each fault in the contract's list gives an error with its line (one parametrised
        route test).
18. [ ] I7: the check route writes no row and no audit row (route test, stored rows).
19. [ ] C3, C4: the page creates each person through the one-person route in file order and
        shows the outcome counts; Create is disabled while there is an error (component test).
20. [ ] C4: Try again runs only the failed people (component test).
21. [ ] C5: a second run of the same file sends no second invitation (route test on the
        existing rule; the Cognito double counts creates).

**Part D**

22. [ ] D1: migration round trip passes; the `pa_ops` grant test matches D1 exactly (I8).
23. [ ] D2: a made code has 12 characters of the alphabet and two made codes differ (unit
        test of the public function).
24. [ ] D3, I1: the route's answer has the same shape and status for a good code, a
        malformed code, an unknown code and no code (route test).
25. [ ] D3.4, D3.5: a waiting request takes a new code; a stamped and a rejected request do
        not change (route test, stored rows).
26. [ ] I2: the public service's code path imports no reader of `invite_link` (the existing
        service-role test is extended, or a route test with the table revoked).
27. [ ] D5.1, I3: for each reason a link is not redeemable (revoked, expired, full, wrong
        domain, unknown code) the sweep makes no account and no Cognito call (parametrised
        sweep test).
28. [ ] D5.4: a redeemed request has the account in the link's organisation, the link's
        cohorts, `invite_link_id` set and one sweep audit row (sweep test, stored rows).
29. [ ] D5.5, I4: with `max_uses` 1 and two requests, one is redeemed and one waits (sweep
        test); the redemption locks the link row (test with two connections).
30. [ ] D5.8, I5: 250 requests with unknown codes, older than one redeemable request, do not
        stop it in the same tick (sweep test).
31. [ ] D5.7, I9: a deactivated person and a rejected request get no account through a link
        (sweep test).
32. [ ] D5.9: raising `max_uses` makes a waiting request redeemable at the next tick (sweep
        test).
33. [ ] D5.10: redemptions count toward `max_per_hour` (sweep test).
34. [ ] D5.11: manual Approve of a request with a code does not set `invite_link_id` (route
        test).
35. [ ] D6: create, list, update and revoke work, refuse the out-of-range values, and write
        their audit rows; a non-ops caller is refused (route tests).
36. [ ] D6, I10: no log line and no audit row holds the code (route test on captured logs
        and stored rows).
37. [ ] D6: the link's address uses `PUBLIC_APP_ORIGIN`; the infra unit test pins that the
        ops service gets it from `domain_name`.
38. [ ] D7: the Invite links page lists, creates, copies, edits and revokes against the mock
        API (component tests).
39. [ ] D8: a waiting request with a code shows the label and the reason (route test for the
        field, component test for the line).
40. [ ] D9: deleting an organisation with an invite link is refused with the count (route
        test).

**Part E**

41. [ ] E2: the staging switch is its own commit; the production block of
        `infra/pa_config.json` is unchanged in the whole task (diff check).
42. [ ] E3: all seven live checks recorded with date and outcome.
43. [ ] E4: the rollback (downgrade, then upgrade) rehearsed on a local database.

**Docs**

44. [ ] `web-api.md`, `infra/DEPLOYMENT.md`, the ADR 0046 amendment, the living copy file and
        `docs/deferred.md` are updated as the contract's § Scope says.
