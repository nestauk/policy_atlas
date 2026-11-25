# Task contract: 071-self-signup-staging

> **Status:** drafted 2026-11-25. Scope agreed by the owner in chat (2026-11-25, § Owner
> rulings). Contract approved (before planning): _pending_ · Plan approved (before
> implementation): _pending_ · ADR: an amendment to
> [ADR 0046](../../adr/0046-ops-service-ops-pages-self-signup-and-ops-database-login.md),
> written when both approvals are given. Branch `task/071-self-signup-staging`. Tier 4
> (a migration, a database grant, a change to a public route, a staging config change).
> Background: [notes.md](notes.md). Where the notes differ, this contract is right.

## Goal

Three ways for a person to get an account work well, and staging tests the first one with
all of Nesta:

1. **Listed domain.** A person with a `nesta.org.uk` address uses Request access and gets an
   invitation without an operator. Built in task 065; this task switches it on for staging
   and corrects the words on the public page.
2. **Operator adds people.** Add person can put the person in cohorts, and can add many
   people from one file.
3. **Invite link.** An operator makes a link for one organisation, its cohorts and one email
   domain. A person who uses Request access through the link gets an invitation without an
   operator. This is for a pilot where only some people of a domain get access and we do not
   hold their names.

## Deliverable

One pull request to `dev` with parts A to D below, then the staging switch-on (part E) with
its live checks recorded in `verification.md`. Production self-signup stays off.

## Terms

| Term | Meaning |
|---|---|
| **Request** | One row of `waitlist_entry`: what a person sent through the public Request access form. The code says "waitlist"; the pages say "Requests". |
| **Invitation** | The email that Cognito (the AWS sign-in service) sends with a temporary password. Existing. |
| **Invite link** | New. A web address of the public site that carries an invite code. Table `invite_link`. Not the same thing as an invitation. |
| **Invite code** | The secret part of an invite link: 12 characters that the server makes. |
| **Redeem** | The sweep turns a request that carries a valid invite code into an account. |
| **Sweep** | The loop in the ops service that turns requests into accounts every 60 seconds (`ops/sweep.py`). Runs only when `self_signup.enabled` is true for the environment. |
| **Listed domain** | A row of `organisation_domain`: every request from that email domain gets an account in that organisation. |
| **Stamped** | A request whose `account_created_at` is set: it has an account. |
| **Waiting** | A request that is not stamped and not rejected. |
| **Check** | A request the sweep refused for good (in another organisation, deactivated, refused by Cognito). The Requests page shows it for an operator. Existing. |
| **`pa_ops`** | The ops service's restricted database login (task 065). |
| **Ops pages** | The operator web pages on the ops address, behind the office allowlist. |

## Read first

- [ADR 0046](../../adr/0046-ops-service-ops-pages-self-signup-and-ops-database-login.md),
  decisions 1, 6 and 7 and the 066 amendment.
- [web-api.md](../../specs/system/web-api.md) § Waitlist and the public write exception.
- [066 contract](../066-ops-deactivate/contract.md) B4 and B5 (deactivated people).
- `infra/DEPLOYMENT.md` § Self-signup.
- Code: `api/routers/waitlist.py`, `ops/sweep.py`, `ops/commands.py` (`approve_request`,
  `ensure_account_enrolled`, `add_to_cohort`), `api/routers/ops.py` (`create_person`, `_bulk`,
  `approve_request`), `frontend/src/ops/views/` (`AddPersonView`, `RequestsView`),
  `frontend/src/views/splash/` (`SplashView`, `WaitlistForm`).

## Owner rulings (2026-11-25)

1. The sweep stays at 60 seconds.
2. The owner clears old `nesta.org.uk` requests on staging by hand before switch-on.
3. The staging cap of 100 invitations an hour is enough.
4. No new listed domains. A domain where only some people get access is not listed.
5. No default cohort for a listed domain. The owner adds test accounts to a cohort by hand.
6. Bulk add from a CSV file is in scope.
7. Invite links are in scope.
8. The words in part A are drafts until the owner approves them
   ([design-annex.md](design-annex.md)).

## Part A — words on the public page

**A1.** The intro above the form and the success message change to the annex text. They are
the same for every request.

**A2.** The form shows one extra line when the page address carries an invite code (D4). The
line depends on the address only, never on an answer from the server.

**A3.** ❓ Open (owner): one sentence about the authenticator app in the invitation email
(`infra/email/invitation.html`). In scope only if the owner says yes.

## Part B — cohorts at Add person and at Approve

**B1.** `POST /api/v1/ops/people` and `POST /api/v1/ops/requests/{entry_id}/approve` accept
an optional `cohort_ids` list (default empty, at most 10, no repeats).

**B2.** The route resolves every cohort **before** any Cognito call. An unknown cohort gives
the ordinary 404 and changes nothing.

**B3.** The enrolment and the cohort memberships are one database transaction. If a cohort
insert fails, nothing is committed.

**B4.** A person who already has the account, or is already in a cohort, is not an error:
the membership is added where it is missing (`add_to_cohort` already behaves so).

**B5.** Each membership writes one `cohort.add` audit row with the target form the People
list uses (`<user_id>/cohort/<cohort_id>`).

**B6.** The refusals of today do not change (another organisation, deactivated on Approve,
Cognito refusal). A refused call adds no cohort.

**B7.** Add person and both Approve dialogs (one request, many requests) get an optional
"Cohorts" field. The answer names the cohorts in the toast.

## Part C — add many people from a file

**C1. The file.** CSV (comma-separated values) text in UTF-8; a byte-order mark at the
start is accepted (Excel writes one). The first line is a header. The columns `email` and
`name` are required, in any order and any letter case. Any other column is an error. At
most 500 people and 200,000 characters.

**C2. Check route.** `POST /api/v1/ops/people/import-check`, body `{csv}`. It reads the text
with Python's standard `csv` module and answers `{rows, errors}`:

- `rows`: `{line, email, display_name}` for each good line, with the email in lower case.
- `errors`: `{line, message}` for each fault. The faults are: no header or a wrong column; an
  email that fails the Add person rule; an empty name; a name over the Add person limit; an
  email that is in the file twice; too many people; a file that is too large.

The route writes nothing, calls nothing outside the database, and makes no audit row. It uses
the same email and name rules as `PersonCreate`, from one place.

**C3. Create.** The page creates the people one at a time through `POST /api/v1/ops/people`
(B1), in file order, as the Requests page already approves many requests. Each person keeps
their own audit row and their own outcome. There is no new bulk-create route.

*Why not one bulk route:* 500 Cognito calls in one request would pass the load balancer's
60-second limit, and a failure in the middle would leave the operator without a per-person
outcome.

**C4. The page.** Add person gets a second mode, "Add many from a file": choose the file, one
organisation and optional cohorts for the whole file. The page shows the check result. Create
is disabled while the file has any error. During the run the page shows how many are done.
At the end it shows the count for each outcome and lists the people who were not added, with
the reason, and offers Try again for those that failed. States and words: annex § Add many.

**C5.** Running the same file again is safe: a person who already has the account in that
organisation gets no second invitation (the existing rule of `ensure_account_enrolled`).

**C6.** A file is never stored, on the server or in the browser's storage.

## Part D — invite links

**D1. Schema** (one migration after the newest migration on `dev` at build time):

- `invite_link`: `invite_link_id` (key), `code` (unique), `label`, `org_id` (to
  `organisation`), `allowed_domain` (required, lower case), `max_uses` (above 0),
  `expires_at`, `revoked_at` (null until revoked), `created_at`, `created_by` (the
  operator's user id).
- `invite_link_cohort`: `invite_link_id`, `cohort_id`. A deleted cohort or link removes the
  row.
- `waitlist_entry.invite_code` (text, null): the code a request arrived with.
- `waitlist_entry.invite_link_id` (to `invite_link`, null): the link the sweep redeemed.
- One partial index on each of the two new `waitlist_entry` columns (rows where it is set).
- Grants to `pa_ops`: read and insert on both new tables; update of `label`, `max_uses`,
  `expires_at` and `revoked_at` on `invite_link`; update of `waitlist_entry.invite_link_id`.
  Nothing else. The test that pins the grant list is updated to match.
- The downgrade removes all of it.

**D2. The code.** The server makes it with the `secrets` module: 12 characters from 32
letters and digits with no look-alikes (no `0 O 1 I L`), shown in three groups of four with
hyphens. An operator cannot choose it. It is stored as plain text, because the operator must
be able to copy the link again later.

**D3. Public route.** `POST /api/v1/waitlist` accepts an optional `invite_code`.

1. The server normalises it: upper case, hyphens and spaces removed. If the result is not 12
   characters of the code alphabet, the request is stored with no code. The route never
   answers 422 for the code and never reads `invite_link`.
2. The answer is the same as today for every request: a good code, a bad code, no code.
3. A new email address: the request is stored with the code.
4. An email address that already has a **waiting** request: the stored request takes the new
   code. Nothing else on it changes.
5. An email address whose request is **stamped** or **rejected**: nothing changes.
6. The honeypot rule does not change.

**D4. Public form.** The form reads `invite` from the page address
(`https://<site>/?invite=XXXX-XXXX-XXXX#access`) and sends it as `invite_code`. There is no
visible code field. The form works as today without it.

**D5. Redemption (the sweep).**

1. A waiting request is **redeemable** when its `invite_code` matches a link that is not
   revoked, is before `expires_at`, has uses left, and whose `allowed_domain` equals the
   request's email domain (the same exact, lower-case match as a listed domain).
2. **Uses** of a link = the number of requests whose `invite_link_id` is that link.
3. The sweep takes redeemable requests and listed-domain requests together, oldest first. A
   request that is both is redeemed through the link.
4. Redeeming, in one transaction: lock the link row; check rule 1 again; run the existing
   `approve_request` with the link's organisation; add the person to each of the link's
   cohorts; set `invite_link_id`; write the sweep's audit row as today.
5. Two redemptions at the same moment cannot pass `max_uses` (the lock in rule 4).
6. A person who already has an account in the link's organisation gets no email; the cohorts
   are added and the use is counted.
7. The terminal outcomes of today do not change: another organisation, deactivated, refused.
   The request shows as Check and no use is counted.
8. A request whose code is **not** redeemable stays waiting. The sweep writes no audit row
   for it and makes no Cognito call. Any number of such requests does not delay a
   redeemable or listed-domain request (the choice is made in the database query, before
   the per-tick limit of 200).
9. If an operator later raises `max_uses` or moves `expires_at`, the waiting requests with
   that code become redeemable at the next tick. A revoked link stays revoked.
10. The hourly cap (`max_per_hour`) covers redemptions and listed-domain invitations
    together, as counted today.
11. Manual Approve of a request that carries a code works as today. It uses the organisation
    and cohorts the operator picks and does not count as a use.

**D6. Ops routes** (all behind `require_ops`, each write with an audit row):

- `GET /api/v1/ops/invite-links` — every link with its organisation, cohorts, uses, state
  and full web address.
- `POST /api/v1/ops/invite-links` — create: `label`, `org_id`, `cohort_ids`, `allowed_domain`,
  `max_uses`, `expires_at`. Audit `invite_link.create`.
- `POST /api/v1/ops/invite-links/{id}` — change `label`, `max_uses`, `expires_at` only.
  Audit `invite_link.update`.
- `POST /api/v1/ops/invite-links/{id}/revoke` — set `revoked_at`. Accounts already made
  stay. Audit `invite_link.revoke`.
- **State** is one of `active`, `expired`, `full`, `revoked`, worked out when read.
- The web address is built from a new ops-service setting, `PUBLIC_APP_ORIGIN`, which the
  infrastructure code sets from the environment's `domain_name`. It is not a secret.
- Limits: `max_uses` 1 to 1,000; `expires_at` in the future and at most 90 days ahead;
  `allowed_domain` follows the listed-domain rule (`_normalise_domain`).
- The code never appears in a log line or an audit row. The audit target is the link's id.

**D7. Ops pages.** A new section "Invite links" (list, create, edit, copy the link, revoke
with a confirmation). States and words: annex § Invite links.

**D8. Requests page.** A waiting request that carries a code shows the link's label and why
it was not redeemed: unknown code, wrong email domain, expired, full, revoked, or "waiting
for the next run". `RequestOut` gains one optional field for this.

**D9. Delete an organisation** (066 B7) also refuses while an invite link points at it, and
its message counts the links.

**D10. Where links work.** Only where the sweep runs. This task turns the sweep on for
staging (part E). Production keeps `self_signup.enabled` false; turning it on for a pilot is
a later, separate production config decision. With no listed domain on production, the
sweep there would act on invite links only.

**D11. The abuse ceiling, stated honestly.** ADR 0046 decision 7 says invitations go "only
to addresses in a listed domain". After this task: only to addresses in a listed domain
**or in the one domain of a valid invite link**. A person who holds a link can enter
addresses of that domain that are not theirs. The ceiling is: one invitation for each
address ever, at most `max_uses` for each link, at most `max_per_hour` each hour, only to
that domain, and the public form's puzzle and rate rule. A guessed code gives no answer to
test against (D3 rule 2) and is useless without a mailbox in the link's domain.

## Part E — staging switch-on

**E1. Before.** Parts A to D are deployed to staging. The Nesta organisation exists with the
`nesta.org.uk` domain (`make org-domain-add`). The owner has cleared old `nesta.org.uk`
requests on the Requests page.

**E2. Switch.** `self_signup.enabled` becomes true for staging in `infra/pa_config.json`, by
its own small pull request, and a deploy. The production block does not change.

**E3. Live checks** (scope: the changed surfaces plus one full sign-in; about 30 minutes):

1. A new `nesta.org.uk` address requests access → the invitation arrives within two minutes →
   sign in, new password, authenticator app → the person is in Nesta on People.
2. An address of an unlisted domain → no email; the request waits on Requests.
3. The same Nesta address requests again → no second email.
4. Add person with two cohorts → both cohorts show on People.
5. A file of three people (one already has an account) → two invitations, three people in
   the organisation and the cohort.
6. An invite link for a test organisation, a test cohort and the `nesta.org.uk` domain with
   `max_uses` 1: the first request through the link gets an account in the test organisation
   and cohort; the second waits on Requests and shows "full".
7. A revoked link: a request through it waits and shows "revoked".

**E4. Rollback.** Set `self_signup.enabled` to false and deploy: the sweep stops, and both
listed domains and invite links stop making accounts. Requests keep arriving and wait. The
schema is removed by `alembic downgrade` to the revision before this task, after both
services are stopped (the public API writes `invite_code`).

## Scope / Out of scope

- **In:** the files named in § Read first; one migration; `core/schema.py`;
  `api/contract/ops.py` and `api/contract/waitlist.py`; a new ops view and its tests; the
  ops mock fixtures; `infra/infra/policy_atlas_stack.py` (one environment value);
  `infra/pa_config.json` (staging, part E); docs (below).
- **Docs:** `web-api.md` § Waitlist (the `invite_code` field; a spec change, approved with
  this contract); `infra/DEPLOYMENT.md`; the ADR 0046 amendment;
  `docs/tasks/065-accounts/ops-pages-copy.md` (the living copy file); `docs/deferred.md`.
- **Out:**
  - Production config. Production self-signup stays off.
  - New listed domains, and editing the domain table on the ops pages.
  - A default cohort for a listed domain.
  - An invite link with no domain rule, and a visible code field on the form.
  - A per-row organisation or cohort in the CSV file.
  - Email to operators when a request needs a check.
  - The sweep interval.
  - A rename of `waitlist_entry`.
  - The public app's signed-in pages.

**Deferred entries taken in** (`docs/deferred.md` § Accounts, organisations and
administration): "Self-signup works for one email domain" is reworded (invite links now
cover a second organisation without a listed domain). The other entries are left on purpose.
New entries are written for the Out items a user may ask for: a link with no domain rule, a
per-row organisation in the file, the default cohort, the operator email.

## Constraints & approval gates

This contract asks the owner to approve these gated changes:

| Gate | Change |
|---|---|
| Schema | Two tables and two columns (D1) |
| Auth and tenancy | A new way for an account to be made in an organisation (D5); new `pa_ops` grants (D1) |
| Public interface | An optional field on `POST /api/v1/waitlist` (D3); optional fields and new routes on the ops interface (B1, C2, D6) |
| Production config | None for production. Staging: one new ops-service environment value (D6) and the switch (E2) |
| Dependencies, CI, scaffold, runtime egress | None. No new library; the CSV reader is Python's standard `csv` |

Generated files (`frontend/openapi.json`, `frontend/openapi-ops.json`, the generated types)
change only through `make openapi-sync`.

## Invariants

| Id | Invariant |
|---|---|
| I1 | The answer of `POST /api/v1/waitlist` is the same for every accepted body, whatever the code, the domain or the state of the address. |
| I2 | The public API never reads `invite_link` and never calls Cognito. |
| I3 | No account is made through a link whose state is not `active`, or for an address outside the link's domain. |
| I4 | A link never has more uses than `max_uses`. |
| I5 | A request that cannot be redeemed never delays one that can. |
| I6 | A refused or failed Add person or Approve leaves no cohort membership. |
| I7 | The import check writes nothing. |
| I8 | `pa_ops` gains only the grants in D1. |
| I9 | A rejected request and a deactivated person get no account through a link. |
| I10 | The invite code is in no log line and no audit row. |

## Public / private boundary

Public-safe: the code, the docs, the annex. Private: real email addresses, any real CSV
file, invite codes of a real environment, the live-check screenshots if they show an address.
Tests use made-up addresses.

## Design annex

[design-annex.md](design-annex.md) version 1. No mock yet; the surfaces follow the patterns
of the existing ops pages. The owner may ask for a mock round before the build. Polish round
budget: one round at the end of build and one at the end of review.

## Model route

n/a. No inference.

## Disciplines binding this slice

- **Model only what behaves.** No column or field without a behaviour above.
- **Flag, don't drop.** A request that is not redeemed stays visible with its reason (D8).
- Leave the Out items as entries in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: a gate outside the table above is hit; the sweep needs a second
loop, a queue or a new service; the public API would need to read `invite_link`; the build
finds that the per-person create cannot keep its outcome through the file flow; the budget
is spent.

## Acceptance checks

- `make verify` green.
- Deterministic tests only (no AI eval): one focused test for each behaviour in parts A to D
  and each invariant, at a route, a public function, a rendered component or a stored row.
- The migration round trip (upgrade, downgrade, upgrade) and the `pa_ops` grant test.
- The live checks of E3 on staging.

## Verification evidence expected

`verification.md` holds: the `make verify` result; the rubric with each row's test name; the
E3 checks with date and outcome (addresses masked); the diff summary; the list of deferred
entries written; the rollback rehearsal on a local database.

## Risk tier & review focus

Tier 4. Review: contract verifier, security review (the public route, the sweep, the grants),
adversarial review by Codex (contract, plan and code), code review, the design lane for the
ops pages, and the owner's deep review.

Focus: I1 to I5 and I9; the sweep query under load; the lock on redemption; the grant list;
that the bulk flow adds no second create path.
