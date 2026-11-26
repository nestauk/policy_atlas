# Task contract: 071-self-signup-staging

> **Status:** drafted 2026-11-25; Codex contract review folded in the same day (§ Contract
> review). Scope agreed by the owner in chat (2026-11-25, § Owner rulings). Contract approved: 2026-11-25 (owner, in chat) · Plan approved: 2026-11-25 (owner, in
> chat) · ADR: the 2026-11-25 amendment to
> [ADR 0046](../../adr/0046-ops-service-ops-pages-self-signup-and-ops-database-login.md),
> Branch `task/071-self-signup-staging`. Tier 4
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
3. **Invite link.** An operator makes a link for one organisation, its cohorts and a short list of
   email domains. A person who uses Request access through the link gets an invitation without an
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
9. A failed request waits 15 minutes before the next try (D5 rule 13): agreed.
10. A new invite code replaces an older one on a waiting request (D3 rule 4): agreed.
11. An invite link can have several email domains, 1 to 10 (D1, D5 rule 1, D6).
12. The invitation email gets one sentence about the authenticator app, with no product
    name (A3).
13. A mock of the ops pages is made before the build (§ Design annex).
14. The contract, the words of the annex, the mock and the plan are approved.

Rulings in the review (2026-11-26):

15. A made-up code can replace a valid code on a waiting request (D3 rule 4). The rule
    stays; D11 states the limit.
16. A file run never reactivates a deactivated person (C3).
17. Delete organisation removes the organisation's revoked links that have no uses (D1, D9).
    `pa_ops` gets the delete right on `invite_link` for this.
18. An edit of a link may change one value and leave the others (D6).

## Part A — words on the public page

**A1.** The intro above the form and the success message change to the annex text. They are
the same for every request.

**A2.** The form shows one extra line when the page address carries an invite code (D4). The
line depends on the address only, never on an answer from the server.

**A3.** The invitation email (`infra/email/invitation.html`) gains one sentence about the
authenticator app (annex § Invitation email). It names no product. Both environments use
this one file, so production gets the sentence at its next deploy.

## Part B — cohorts at Add person and at Approve

**B1.** `POST /api/v1/ops/people` and `POST /api/v1/ops/requests/{entry_id}/approve` accept
an optional `cohort_ids` list (default empty, at most 10, no repeats).

**B2.** The route resolves every cohort **before** any Cognito call. An unknown cohort gives
the ordinary 404 and changes nothing.

**B3.** The enrolment and the cohort memberships are one database transaction. If a cohort
insert fails, no database change is committed. Cognito is called before the commit, as today
(ADR 0046, accepted limits): an account that Cognito already made stays, and the same call
can be sent again safely, because the second call finds the account and sends no second
invitation.

**B4.** A person who already has the account, or is already in a cohort, is not an error:
the membership is added where it is missing (`add_to_cohort` already behaves so).

**B5.** Each **new** membership writes one `cohort.add` audit row with the target form the
People list uses (`<user_id>/cohort/<cohort_id>`). A membership that already existed writes
no row.

**B6.** The refusals of today do not change (another organisation, deactivated on Approve,
Cognito refusal). A refused call adds no cohort.

**B7.** Add person and both Approve dialogs (one request, many requests) get an optional
"Cohorts" field. The answer names the cohorts in the toast.

## Part C — add many people from a file

**C1. The file.** CSV (comma-separated values) text. The browser decodes the file as UTF-8
and sends the text; a byte-order mark at the start is accepted (Excel writes one). The rules:

- The first line is a header. The columns `email` and `name` are required, in any order and
  any letter case. Any other column, or the same column twice, is an error.
- A blank line is skipped.
- A value may be in double quotes (a name with a comma). A value that holds a line break is
  an error.
- Quoting that does not follow the CSV rules is an error (the reader runs in strict mode).
- Text that holds the Unicode replacement character (U+FFFD) is an error: the file was not
  saved as UTF-8.
- Two lines with the same email, compared in lower case, are an error.
- At most 500 people and 200,000 characters.
- A line number in an answer is the line of the file where the record starts, counting the
  header as line 1.

**C2. Check route.** `POST /api/v1/ops/people/import-check`, body `{csv}`. It reads the text
with Python's standard `csv` module and answers `{rows, errors}`:

- `rows`: `{line, email, display_name}` for each good line, with the email in lower case.
- `errors`: `{line, message}` for each fault: each rule of C1, an email that fails the Add
  person rule, an empty name, a name over the Add person limit.

The route writes nothing, calls nothing outside the database, and makes no audit row. It uses
the same email and name rules as `PersonCreate`, from one place.

**C3. Create.** The page creates the people one at a time through `POST /api/v1/ops/people`
(B1), in file order, as the Requests page already approves many requests. Each person keeps
their own audit row and their own outcome. There is no new bulk-create route.
The page sends `reactivate: false` (a new optional field of the route, default true): a
deactivated person in a file is not turned back on and is listed as not added, with the
reason. An operator who means it adds the person with the one-person form.

*Why not one bulk route:* 500 Cognito calls in one request would pass the load balancer's
60-second limit, and a failure in the middle would leave the operator without a per-person
outcome.

**C4. The page.** Add person gets a second mode, "Add many from a file": choose the file, one
organisation and optional cohorts for the whole file. The page shows the check result. Create
is disabled while the file has any error. During the run the page shows how many are done.
At the end it shows the count for each outcome and lists the people who were not added, with
the reason. Try again covers only a failure that a retry can help: no answer, or a server
error. A refusal (another organisation, an address Cognito refuses) is final and is not
retried. States and words: annex § Add many.

**C5.** Running the same file again is safe: a person who already has the account in that
organisation gets no second invitation (the existing rule of `ensure_account_enrolled`).

**C6.** A file is never stored, on the server or in the browser's storage.

## Part D — invite links

**D1. Schema** (one migration after the newest migration on `dev` at build time):

- `invite_link`: `invite_link_id` (uuid, key); `code` (text, unique, a check that it is 12
  characters of the code alphabet); `label` (text, 1 to 200 characters); `org_id` (to
  `organisation`, required); `allowed_domains` (a list of text, required, a check that it holds 1 to
  10 entries; the command makes each entry lower case and refuses a repeat); `max_uses` (integer, a check that it is above 0); `expires_at` (timestamp with time
  zone, required); `revoked_at` (timestamp with time zone, null until revoked); `created_at`
  (timestamp with time zone); `created_by` (text, the operator's user id, as
  `ops_action.actor_user_id`).
- `invite_link_cohort`: `invite_link_id`, `cohort_id`; the pair is the key. A deleted cohort
  removes its rows.
- A link with a use is never deleted, so the uses and the reasons on Requests keep their
  source. There is no delete route. One exception (D9): Delete organisation removes the
  organisation's links that are revoked and have no uses.
- `waitlist_entry.invite_code` (text, null): the code a request arrived with.
- `waitlist_entry.invite_link_id` (to `invite_link`, null): the link the sweep redeemed.
- One partial index on each of the two new `waitlist_entry` columns (rows where it is set).
- Grants to `pa_ops`: read and insert on both new tables; update of `label`, `max_uses`,
  `expires_at` and `revoked_at` on `invite_link`; delete on `invite_link` (D9; the cohort
  rows of a deleted link go by the foreign key); update of `waitlist_entry.invite_link_id`.
  Nothing else. The test that pins the grant list is updated to match.
- The downgrade removes all of it.

**D2. The code.** The server makes it with the `secrets` module: 12 characters from 31
letters and digits with no look-alikes (no `0 O 1 I L`), shown in three groups of four with
hyphens. An operator cannot choose it. It is stored as plain text, because the operator must
be able to copy the link again later.

**D3. Public route.** `POST /api/v1/waitlist` accepts an optional `invite_code`.

1. The field is text of at most 64 characters, with no pattern. A longer value gets the
   ordinary 422 of an oversize field, which says nothing about any code. The server
   normalises the value: upper case, hyphens and spaces removed. If the result is not 12
   characters of the code alphabet, the request is stored with no code. The route never
   reads `invite_link`.
2. The answer has the same status, the same fields and the same headers for a good code, an
   unknown code, a malformed code and no code. The values are those of today: the email sent,
   a new id, the time.
3. A new email address: the request is stored with the code.
4. An email address that already has a **waiting** request: the stored request takes the new
   well-formed code, and replaces an older code. Nothing else on it changes. A request with
   no code or a malformed code changes nothing. (Why replace: a person whose first link
   expired can use a new one. The cost is in D11.)
5. An email address whose request is **stamped** or **rejected**: nothing changes.
6. The honeypot rule does not change.

**D4. Public form.** An invite link is `https://<site>/#invite=XXXX-XXXX-XXXX`. The code is
in the fragment (the part after `#`), which a browser never sends to a server, so it is in
no CDN or load-balancer log and no referrer. The page reads the code, keeps it in memory,
removes it from the address bar (`history.replaceState`), scrolls to the form, and sends it
as `invite_code` with the request. There is no visible code field. The form works as today
without a code.

**D5. Redemption (the sweep).**

1. A waiting request is **redeemable** when its `invite_code` matches a link that is not
   revoked, is before `expires_at`, has uses left, and whose `allowed_domains` hold the
   request's email domain (the same exact, lower-case match as a listed domain).
2. **Uses** of a link = the number of requests whose `invite_link_id` is that link.
3. The sweep takes redeemable requests and listed-domain requests together, oldest first.
   **Precedence:** a redeemable request is redeemed through the link, also when its domain
   is listed. A request whose code is not redeemable is handled as if it had no code: if
   its domain is listed it gets the listed-domain account (no link cohorts, no use counted);
   if not, it waits. So a code can never hold back a listed-domain request.
   The sweep also runs when no domain is listed.
4. Redeeming, in one transaction: lock the link row; check rule 1 again; run the existing
   `approve_request` with the link's organisation; add the person to each of the link's
   cohorts; set `invite_link_id`; write the sweep's audit row as today.
   *Accepted limit:* Cognito is called before the commit. If the database write fails after
   Cognito made the account, the request stays waiting and the sweep completes it after the wait of
   rule 13 (the account exists, so no second invitation). If the link became full, expired or revoked in
   between, the request stays on Requests with its reason (D8) and an operator approves it
   by hand. No new mechanism is built for this rare case.
5. Two redemptions at the same moment cannot pass `max_uses` (the lock in rule 4).
6. A person who already has an account in the link's organisation gets no email; the cohorts
   are added and the use is counted.
7. The terminal outcomes of today do not change: another organisation, deactivated, refused.
   The request shows as Check and no use is counted.
8. A request whose code is **not** redeemable, in a domain that is not listed, stays
   waiting. The sweep writes no audit row
   for it and makes no Cognito call. Any number of such requests does not delay a
   redeemable or listed-domain request (the choice is made in the database query, before
   the per-tick limit of 200).
9. If an operator later raises `max_uses` or moves `expires_at`, the waiting requests with
   that code become redeemable at the next tick. A revoked link stays revoked.
10. The hourly cap (`max_per_hour`) covers redemptions and listed-domain invitations
    together, as counted today.
11. Manual Approve of a request that carries a code works as today. It uses the organisation
    and cohorts the operator picks and does not count as a use.
12. **One tick at a time.** A tick takes one database lock for its whole run, from the cap
    read to the last request. A second tick that starts in that time does nothing. Two ops
    tasks that overlap during a deploy therefore cannot pass `max_per_hour` or `max_uses`.
13. **A failed request waits before the next try.** Today a request that fails for a passing
    reason (a Cognito throttle, an outage) is tried again every tick, and every try spends
    the hourly cap. One such request can spend 60 of the 100. New rule, for listed-domain and
    link requests alike: a request whose last sweep attempt failed is not tried again for 15
    minutes. This is read from the audit rows the sweep already writes; there is no new
    column. This changes the behaviour built in task 065.

**D6. Ops routes** (all behind `require_ops`, each write with an audit row):

- `GET /api/v1/ops/invite-links` — every link with its organisation, cohorts, uses, state
  and full web address.
- `POST /api/v1/ops/invite-links` — create: `label`, `org_id`, `cohort_ids`, `allowed_domains`,
  `max_uses`, `expires_at`. Audit `invite_link.create`.
- `POST /api/v1/ops/invite-links/{id}` — change `label`, `max_uses`, `expires_at` only (the domains of a link do not change; an
  operator revokes the link and makes a new one).
  A value that is left out does not change, and the limits are checked only for a value
  the call changes (so a link that has expired can still get a new label).
  `max_uses` below the link's current uses is refused, checked under the link row lock. A
  revoked link cannot be changed. Audit `invite_link.update`.
- `POST /api/v1/ops/invite-links/{id}/revoke` — set `revoked_at`. Accounts already made
  stay. Audit `invite_link.revoke`.
- **State** is one of `active`, `expired`, `full`, `revoked`, worked out when read.
- The web address is built from a new ops-service setting, `PUBLIC_APP_ORIGIN`, which the
  infrastructure code sets from the environment's `domain_name`. It is not a secret.
- `expires_at` is a full date and time with its zone (RFC 3339). The page offers a date and
  sends the end of that day in the operator's own time zone.
- Limits: `max_uses` 1 to 1,000; `expires_at` in the future and at most 90 days ahead;
  `allowed_domains` holds 1 to 10 domains with no repeat, and each follows the listed-domain
  rule (`_normalise_domain`).
- The code never appears in a log line of the backend or in an audit row. The audit target
  is the link's id. The list answer carries the code inside the web address, for ops users
  only.

**D7. Ops pages.** A new section "Invite links" (list, create, edit, copy the link, revoke
with a confirmation). States and words: annex § Invite links.

**D8. Requests page.** A waiting request that carries a code shows the link's label and why
it was not redeemed: unknown code, wrong email domain, expired, full, revoked, or "waiting
for the next run". `RequestOut` gains one optional field for this.

**D9. Delete an organisation** (066 B7) also refuses while an invite link that is not
revoked, or that has a use, points at it, and its message counts those links. Links that are
revoked and have no uses are deleted with the organisation.

**D10. Where links work.** Only where the sweep runs. This task turns the sweep on for
staging (part E). Production keeps `self_signup.enabled` false; turning it on for a pilot is
a later, separate production config decision. With no listed domain on production, the
sweep there would act on invite links only.

**D11. The abuse ceiling, stated honestly.** ADR 0046 decision 7 says invitations go "only
to addresses in a listed domain". After this task: only to addresses in a listed domain
**or in one of the domains of a valid invite link**. A person who holds a link can enter
addresses of those domains that are not theirs. The ceiling is: one invitation for each
address ever, at most `max_uses` for each link, at most `max_per_hour` each hour, only to
those domains, and the public form's puzzle and rate rule. A guessed code gives no answer to
test against (D3 rule 2) and is useless without a mailbox in one of the link's domains.

A link holder can also put the link's code on another person's **waiting** request, if the
holder knows that person's address (D3 rule 4). The result is the same as a new request for
that address: an invitation to the mailbox owner, in the link's domains only. It cannot stop
or delay a listed-domain account (D5 rule 3).

*A known limit, accepted by the owner (ruling 15).* The public route never reads a link (I2),
so it cannot tell a real code from a made-up one. Anyone who knows a person's address, with
or without a link, can replace the valid code on that person's waiting request with a
made-up one. In an unlisted domain that request then waits. The Requests page shows "code
not recognised" and an operator approves it by hand. The usual window is the time to the
next tick (60 seconds); it is longer while the hourly cap is spent, the link is full, or
the request waits after a failure. A holder of two links for one domain can move a waiting
person from one link to the other; this is accepted.

## Part E — staging switch-on

**E1. Before.** Parts A to D are deployed to staging in the order of ADR 0046: build the ops
pages, update the infrastructure, stop both services, migrate and sync the ops login, start
the API, then the ops service. The Nesta organisation exists with the
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
6. An invite link for a test organisation and a test cohort, for a domain that is **not**
   listed and where the owner has two mailboxes, with `max_uses` 1: the first request
   through the link gets an account in the test organisation and cohort; the second waits
   on Requests and shows "full". After a revoke, a third request shows "revoked".
7. Precedence: a link for `nesta.org.uk` (a listed domain) and a test organisation, then
   revoked: a new Nesta address that requests through it gets an account in Nesta, not in
   the test organisation.

**E4. Rollback.** The normal rollback is the switch: set `self_signup.enabled` to false and
deploy. The sweep stops, and both listed domains and invite links stop making accounts.
Requests keep arriving and wait. One link is stopped by Revoke.

Removing the schema is a last resort and **destroys data**: every link, every stored code
and the record of which link made which account. It needs the owner's word. The steps: stop
both services; `alembic downgrade` to the named parent revision of this task's migration
(recorded in `verification.md`; later migrations must be downgraded first); start an image
from before this task. An older image also runs safely on the new schema, because the new
columns are nullable and old code does not name them, so a code rollback alone needs no
downgrade.

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
  - A change to the domains of a link after it is made.
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
| Production config | No production config value. The email sentence (A3) reaches production at its next deploy. Staging: one new ops-service environment value (D6) and the switch (E2) |
| Dependencies, CI, scaffold, runtime egress | None. No new library; the CSV reader is Python's standard `csv` |

Generated files (`frontend/openapi.json`, `frontend/openapi-ops.json`, the generated types)
change only through `make openapi-sync`.

## Invariants

| Id | Invariant |
|---|---|
| I1 | The answer of `POST /api/v1/waitlist` has the same status, fields and headers for every accepted body, whatever the code, the domain or the state of the address. Its values are the email sent, a new id and the time. Equal timing is not promised; no code or link lookup runs in the request. |
| I2 | The public API never reads `invite_link` and never calls Cognito. |
| I3 | No account is made through a link whose state is not `active`, or for an address outside the link's domains. |
| I4 | A link never has more uses than `max_uses`, after a redemption or after an edit. |
| I5 | A request that cannot be redeemed, or that keeps failing, never stops one that can be redeemed, and a code never holds back a listed-domain request. |
| I6 | A refused or failed Add person or Approve leaves no cohort membership. |
| I7 | The import check writes nothing. |
| I8 | `pa_ops` gains only the grants in D1. |
| I9 | A rejected request and a deactivated person get no account through a link. |
| I10 | The invite code is in no backend log line, no audit row, and no web address that reaches a server (it travels in the fragment and in the request body only). |
| I11 | At most one sweep tick runs at a time. |

## Contract review (Codex, read-only, 2026-11-25)

Twelve findings on the contract and ten on the plan. All were adopted. The ones that changed
this contract:

1. **Critical:** link and listed-domain precedence contradicted itself → D5 rule 3, E3.6, E3.7.
2. **Critical (plan):** the sweep stopped early with no listed domain → D5 rule 3.
3. **High:** the code was in the query string, which servers log → D4 (fragment), I10.
4. **High:** a stranger could change another person's waiting request → D3 rule 4 and D11
   now state the rule and its ceiling; D5 rule 3 removes the way to hold a request back.
5. **High:** a request that keeps failing could spend the hourly cap → D5 rule 13.
6. **High:** an edit could put `max_uses` below the uses → D6, I4.
7. **High:** "one transaction" hid the Cognito call → B3, D5 rule 4 (accepted limit).
8. **High:** the rollback was destructive and had no order → E1, E4.
9. **High (plan):** two overlapping ticks could pass the hourly cap → D5 rule 12, I11.
10. **Medium:** CSV rules, schema types, the wording of I1, missing rubric rows, retry
    classes, the audit row for an existing membership, the code's length bound → C1, C4, D1,
    D3 rule 1, D6, I1, B5 and the rubric.

**Reopened for the owner** (material changes since the scope was agreed): D5 rule 13 changes
how the existing sweep retries; D3 rule 4 lets a new code replace an old one; D4 fixes the
form of the link.

**Owner's answer (2026-11-25):** D5 rule 13 and D3 rule 4 are agreed. The owner asked for
several domains for each link, which changed D1, D5 rule 1, D6 and D11 **after** the Codex
review. Codex has not read that change; the code-stage review covers it.

## Public / private boundary

Public-safe: the code, the docs, the annex. Private: real email addresses, any real CSV
file, invite codes of a real environment, the live-check screenshots if they show an address.
Tests use made-up addresses.

## Design annex

[design-annex.md](design-annex.md) version 2. Mock: a private page with six scenes
(https://claude.ai/artifact/GqkMxEqCd6W6EfkB6EdS2g), direction settled by the owner on 2026-11-25. Polish round
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
