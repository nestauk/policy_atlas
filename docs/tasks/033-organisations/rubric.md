# Rubric: 033-organisations

The task is **done only if every box holds** — otherwise it is in progress, not done.
Rev 3.0: rewritten alongside the contract after the adversarial review. Item 1 of rev 2.0
("implementation satisfies contract.md") is deliberately gone — a 480-line contract behind
one unfalsifiable box absorbed everything the other items missed.

## Process

1. [ ] `make verify` passes **with the `ops` dependency group installed**;
       `make drift-check` green; generated files only via `make openapi-sync`.
2. [ ] No approval-gated change beyond those named in § Constraints; no secrets or
       generated files edited by hand.
3. [ ] No test deleted, skipped or weakened without written justification; the existing
       cross-owner 404 suite stands unmodified.
4. [ ] `verification.md` records evidence per the contract's § Verification evidence.
5. [ ] Known gaps and deferred seams landed in [docs/deferred.md](../../deferred.md).
6. [ ] Tier-4 review stack ran — contract verifier · code review · **security lane in
       three scoped passes** (tenancy boundary · privileged read and audit · operator CLI)
       · plan- and code-stage adversarial · simplification · human deep review.
7. [ ] Spec flow-back landed per § 13; ADR 0032 Accepted **and recording that it amends
       ADR 0031 decision 4**; AGENTS.md phase pointer current.

## Tenancy

8. [ ] **The NULL rule holds in SQL, not Python:** two callers with `org_id IS NULL`
       cannot see each other's `org_id IS NULL` rows, pinned by a named test; the org leg
       is a SQL predicate and no code compares two loaded org values in Python.
9. [ ] **Tenancy matrix**, each row a named test: same-org read 200 · same-org write 403 ·
       cross-org 404 (indistinguishable) · `private` hidden from the org · scope,
       `portfolio_id` and `owner_email` filters correct on both listings · counts exclude
       both unreadable and out-of-org rows.
10. [ ] **Every project-, portfolio- and conversation-scoped route** resolves through the
        helper, enumerated from the tree at plan time — **including the seven routes on
        `conversations.py`'s conversation-id router**. No residual inline `owner_user_id`
        filter outside the helper, scoped to `api/` (`runtime/` is out of scope).
11. [ ] **Own-chats isolation both directions, including the deep link:** a colleague's
        `GET /conversations/{id}/turns` returns 404, not a transcript; the legacy-NULL
        disjunct is `created_by = :me OR (created_by IS NULL AND owner_user_id = :me)`.
12. [ ] **Pending cap and its sweeper are both keyed to the acting user** — a colleague
        with two dead turns is not permanently capped, and an owner's sweep does not fail
        a colleague's in-flight turn. Colleague chat paths take no `FOR UPDATE` on the
        owner's `project` row.
13. [ ] **SSE re-authorises as it streams:** an open stream closes on de-enrolment, on a
        visibility flip and on admin revoke — each pinned by a test.
14. [ ] Dark-launch: with zero orgs the API **and frontend** are observably unchanged —
        including that the Organisation·Mine switcher is absent when `/me` returns no
        organisation.

## The admin flag

15. [ ] **Read only, no exceptions:** an admin is refused every mutation including
        conversation creation and turn POST; an admin is explicitly not treated as a
        colleague.
16. [ ] **Only the four named readers consult `is_admin`** (row-access helper, listing
        scope resolver, `owner_email` gate, `/me` projection), asserted structurally
        against that closed list; no write path reads it.
17. [ ] **Trace grain holds:** one line per row read on the admin leg · one per cross-org
        listing or search request **including one returning zero rows** · one per SSE
        subscribe and re-authorisation · none for a read the caller was already entitled
        to. Admin grant and revoke are themselves recorded with the acting operator.
18. [ ] `is_admin` defaults `false`, is settable only by the CLI, and no HTTP route or
        request body can reach it.

## Identity

19. [ ] **`owner_display` never renders an email** — `display_name` (NOT NULL, required at
        enrolment) then the `sub` rendering. No surface shows one user's address to
        another.
20. [ ] `sub` remains the only claim any request path reads; `get_current_user` stays
        DB-free and Cognito-free; `/me` upserts `DO NOTHING` and never clobbers ops-set
        fields, while enrolment upserts `DO UPDATE`.
21. [ ] **`boto3` is absent from the built API image** (checked against the image, not the
        declaration) and imported by no API module directly or transitively; the API task
        role gains no Cognito permission; `boto3-stubs` satisfies strict mypy.

## The invariant

22. [ ] **Property over i.1–i.6 covering `visibility` *and* `org_id`**, not six examples:
        every `project` with a `portfolio_id` matches its portfolio on both.
23. [ ] i.5 returns 409; a both-fields `PATCH` returns 422; **the i.5-then-i.2 loop cannot
        silently re-expose a row**, and the copy names "leave the Task out of the Project"
        rather than "remove it first".
24. [ ] **`update_portfolio` cannot write `visibility` outside the cascade** — the blind
        `.values(**changes)` splat does not carry the field.
25. [ ] Cascades are owner-only; an org colleague and an admin both 403. The i.4 count
        shown to the user includes only members that caller can see.

## Ops

26. [ ] **Environment mismatch refuses to act** — every command verifies the resolved AWS
        account and pool against the connected database and stops on a mismatch.
27. [ ] **Concurrent operators cannot resurrect admin** — commands read `FOR UPDATE` and
        refuse when current state differs from what the operator acted on.
28. [ ] `user create` passes `DesiredDeliveryMediums=["EMAIL"]`; a database failure keeps
        the account and prints the remediation; an existing address says "use enrol".
29. [ ] **New rows stamp `org_id` from the creator**; re-enrolment leaves old rows with the
        previous org and `reassign-rows` fixes them — both pinned.
30. [ ] No path calls `AdminDeleteUser`; no command accepts a password; **the
        `staging-user`, `prod-user` and `cognito-user` make targets are deleted**.

## Migration and rollback

31. [ ] Up/down roundtrip green; `created_by` backfill correct; the backfill rehearsed at
        production scale; the migration sets a lock timeout and the runbook has a blocker
        preflight.
32. [ ] **The rollback exposure is evidenced, not asserted** — a test proves that pre-033
        code would show a colleague's chat to the project owner, and DEPLOYMENT.md carries
        the roll-forward posture and the manual downgrade procedure.

## Legal and governance

33. [ ] **§ 7 no longer promises what the system cannot do** — it describes what erasure
        actually reaches, and the two-part runbook (application + Cognito, and what backups
        mean) ships in `docs/`.
34. [ ] **§ 3 is accurate** — it no longer calls the email the only user-specific
        identifier, and it discloses what is stored now that storage is real.
35. [ ] § 6 states administrator access and that accesses are logged.
36. [ ] **All three copy blocks are quoted in `verification.md` with the owner's approving
        message**, and the **DPIA screening and processing-record update are recorded as
        done before merge**. Log-group retention is recorded as the bound on how far an
        admin-access investigation can look back.

## Frontend

37. [ ] **The owner/non-owner affordance matrix holds component by component** —
        `PlanningPane` (and its `ChatSidePanel` duplicate), `PlanCard`, `RunPane`,
        suggestion chips, plan-start card, check-in responses and retry controls each
        render read-only for a non-owner. A non-owner cannot reach a mutation by URL.
38. [ ] **The check-in banner is owner-scoped** — a colleague is never told a check-in is
        waiting on them.
39. [ ] `HistoryView` shows decisions and planning turns to any caller who can read the
        project.
40. [ ] **Caches converge without reload** after a cascade and after a membership change;
        `scope` is part of every affected query key.
41. [ ] The account menu names email, organisation and admin state, falling back to the
        `sub` rendering when unenrolled; a long address truncates; the admin's wider list
        says it spans organisations and renders a null owning organisation without a blank.
42. [ ] `PortfolioDetailView` uses the `portfolio_id` filter and is correct beyond 50 rows.
