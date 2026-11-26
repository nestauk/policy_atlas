# Task contract: 068-ops-announcements

> **Status:** approved 2026-11-25 for part 068a, revision 3 (the contract-stage adversarial review is
> folded in: § Folded findings). The owner approved the feature, its gates and
> the design choices in chat on 2026-11-24 and 2026-11-25 (§ Facts settled), and approved
> writing the contract, the plan and the adversarial reviews in one session. The owner
> confirms this text and the six points in § For the owner to confirm at the gate.
> Plan: [plan.md](plan.md) draft 2, with its own adversarial review folded in.
> Contract approved: 2026-11-25 (owner, in chat, part 068a) · Plan approved: 2026-11-25
> (owner, in chat, part 068a) · ADR:
> [0051](../../adr/0051-announcement-email-from-the-ops-server.md). Part 068b: not approved.
> Branch `task/068-ops-announcements`. Tier 4.
> Background and research: [notes.md](notes.md). Screens and copy:
> [design-annex.md](design-annex.md).

## Two parts (owner ruling, 2026-11-25)

The owner split this task. This section wins where the text below says otherwise.

| Part | What | Items | State |
|---|---|---|---|
| **068a: send** | Announcements from the ops pages, unsubscribe, pictures, DMARC | A, B, C, D, E1 to E4, E6 · rubric rows 1 to 28 and 30 · plan phases 0 to 8 and 10 to 12 · live checks 1 to 4, 6, 7, 9, and 10 for sending only | Built first, on this branch and PR #154 |
| **068b: receive** | Email to `updates@` and `support@` reaches the team | E5 · rubric row 29 · plan phase 9 · live checks 5 and 8, and 10 for incoming email | **Not approved. Not built in 068a.** The design below is a draft. 068b gets its own gate, branch and PR |

What changes in 068a because 068b comes later:

- Part 068a builds no MX record, no receipt rule, no bucket for incoming email, no
  forwarder and no `email.inbound` switch.
- The privacy text (C3) and the documents (E6) say nothing about incoming email.
- Until 068b is live, no address at the product domain can receive email. A reply to an
  announcement comes back to its sender as undeliverable. So in 068a every announcement names the
  **reply address** `discoveryhub@nesta.org.uk` (a shared team inbox) as Reply-To, and the footer and the
  unsubscribe page name it where the annex said `support@…`. Part 068b decides whether
  this changes.

## Goal

An operator writes one email on the ops pages and sends it to people who have an account:
everyone, or any mix of cohorts, organisations and named people. The first use is a release
announcement. People can write back: email to `updates@` and `support@` on the product
domain reaches the team.

## Deliverable

One PR on `task/068-ops-announcements` that lands five steps, each with its own switch or
its own deploy order (§ The work):

- A. The tables, the recipient rules, the mail seam and the email layout.
- B. The ops routes that preview, test, send, list and retry.
- C. The public unsubscribe route and page.
- D. The Announcements pages on the ops site.
- E. The AWS setup: send permission, picture hosting, DMARC, and incoming email with
  forwarding.

"Shipped" means: on staging, an operator sends the example announcement to a cohort, the
email arrives with a picture and a working unsubscribe link, a reply to it reaches the team
address, and the result page shows each person's result.

## Terms

| Term | Meaning |
|---|---|
| **Announcement** | One email text sent by an operator to a list of account holders. Table `announcement`. |
| **Kind** | `product_update` or `service_notice`. A product update has an unsubscribe link and skips people who unsubscribed. A service notice has no link and goes to everyone chosen. |
| **Audience** | The operator's choice: everyone, or a set of cohort ids, organisation ids and user ids. Stored on the announcement. |
| **Recipient** | One person on one announcement, with a status. Table `announcement_recipient`. |
| **Left out** | A recipient the server did not send to, with a reason: `deactivated`, `no_email`, `suppressed_bounce`, `suppressed_complaint`, `not_signed_in`, `unsubscribed`. |
| **SES** | Amazon Simple Email Service. It sends Cognito's invitation and sign-in email today. |
| **Suppression list** | The list SES keeps, for each AWS account, of addresses that bounced or whose owner marked our email as spam. SES does not send to an address on it. |
| **Bounce** | An email that the receiving mail server returns because it cannot deliver it. |
| **Mailer** | The new seam in the backend that sends one email and reads the suppression list. One implementation calls SES; one records emails in memory for local work and tests. |
| **Sender domain** | `email.sender_domain` in `infra/pa_config.json`: `v3.policyatlas.uk` on staging, `policyatlas.uk` on production. |
| **Forwarder** | A small AWS Lambda function (code that AWS runs on demand) that sends a copy of each incoming email to the team address. |
| **Team address** | The inbox that gets forwarded email. One SSM parameter (a named setting stored in AWS) for each environment. Never committed. |
| **MX record** | The DNS entry that says where email for a domain goes. |
| **DMARC record** | The DNS entry that tells other mail servers what to do with email that falsely claims to come from the domain. |
| **`pa_ops`** | The ops server's restricted database login (ADR 0046). |
| **Ops server / public API** | The two backend services. The ops server is reachable only from the office (ADR 0046). The public API is reachable by anyone. |

## Read first

- [ADR 0046](../../adr/0046-ops-service-ops-pages-self-signup-and-ops-database-login.md):
  the ops service, the `pa_ops` login, the audit row, the task role.
- [ADR 0048](../../adr/0048-content-security-policy-and-security-headers-on-cloudfront.md):
  the Content Security Policy on both sites.
- [065 contract](../065-accounts/contract.md) and [066 contract](../066-ops-deactivate/contract.md):
  precedent for ops work.
- `infra/DEPLOYMENT.md` § "Pool email through SES"; `docs/knowledge/cognito-invitation-templates-need-ses-sender.md`;
  `docs/knowledge/cdk-poweruser-deploy-boundaries.md`; `docs/knowledge/cloudfront-csp-from-config-pitfalls.md`.
- `docs/deferred.md` § Frontend, "no notification channel" entry: this slice takes in the
  operator-sent part. Email that the product sends by itself (notifications, receipts)
  stays deferred.
- Task 069 (PR #151, open on 2026-11-25) rewrites the privacy notice, including email.
  C3 builds on its text: rebase on it when it merges, and do not write a second version.
- No product spec covers the ops pages; ADR 0046 and this contract are the intent.

## Facts settled (owner, 2026-11-24 and 2026-11-25)

1. The ops pages are the right place; no separate email tool. The pages email account
   holders only.
2. Two kinds of email, as in § Terms.
3. Everyone with the ops role can send.
4. Announcements come from `Policy Atlas <updates@<sender domain>>`. Cognito keeps `no-reply@`.
5. One optional picture is in this version.
6. `updates@` and `support@` receive email. SES receives it and a forwarder sends it to
   the team address. The first team address is the owner's own inbox.
7. A DMARC record is added.
8. Bounces use the suppression list (no event stream).
9. Receiving and forwarding are part of this task.

Checked on 2026-11-25: the sender domain has no MX record and no DMARC record. Staging and
production are separate AWS accounts, both with SES production access, region `eu-west-2`,
which supports SES receiving. No CDK code defines an SES identity; the identity is verified
by hand and stays so.

## The work

### Step A — tables, recipient rules, mail seam, layout

**A1. Schema** (one migration after `a3c9e1f7b2d4`, reversible):
- `app_user.updates_unsubscribed_at timestamptz NULL`.
- `app_user.unsubscribe_token uuid NOT NULL DEFAULT gen_random_uuid()`, unique.
- `announcement`: id, kind (checked), subject, body, button label and link (both or
  neither), picture address and description (both or neither), audience (JSON), a short
  audience summary in words, the sender's user id, the time.
- `announcement_recipient`: announcement id, user id, the email address used, status
  (checked: `pending`, `sending`, `sent`, `failed`, `left_out`), reason (text, null unless
  failed or left out), the time of the last change. Key: announcement id and user id.
- Grants for `pa_ops`: `SELECT, INSERT` on `announcement`; `SELECT, INSERT, UPDATE` on
  `announcement_recipient`. **No** update grant on the two new `app_user` columns.
- The test that pins the `pa_ops` permission list changes to match and in no other way.

**A2. Recipient rules** (one function, used by B1 and B4):
- "Everyone" is every `app_user` row. A chosen audience is the union of the members of the
  chosen cohorts, the people in the chosen organisations and the chosen people.
- One person appears once.
- A person is left out for the first reason that applies, in this order: `deactivated` ·
  `no_email` · `suppressed_bounce` or `suppressed_complaint` (the address is on the
  suppression list) · `not_signed_in` (product update only: `first_signed_in_at` is
  empty) · `unsubscribed` (product update only).
- A service notice still reaches a person who has not signed in, so a reminder to
  invited people stays possible.

**A3. Mailer seam:**
- `send(to, subject, html, text, headers)` and `suppressed()` (address → reason and date).
- The SES implementation uses `boto3` `sesv2` `SendEmail` with **raw content**: SES does
  not accept the unsubscribe headers on its simple content type. The message is built with
  the standard library's `email.message.EmailMessage`, which refuses a line break in a
  header value, so operator text cannot add a header. It is built once at ops start and injected
  the way the Cognito identity is. When it is not configured, the send routes answer 503.
- The in-memory implementation serves local work, the mock journey and tests.
- The public API never builds a mailer.

**A4. Layout:**
- One function turns an announcement and a recipient into a subject, an HTML body and a
  plain-text body. The HTML follows the invitation email's layout (`infra/email/`).
- The operator's text is escaped. Paragraphs split on an empty line. A line that starts
  with "- " is a list item. No other markup, and no HTML from the operator.
- A button link must start with `https://`. A picture address must be one that B3 returned.
- The footer follows the kind (annex § The email).
- Every email carries the header `Reply-To` with the reply address (§ Two parts).
- A product update carries the person's unsubscribe link and the headers
  `List-Unsubscribe` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`. A service
  notice carries neither. The header address is the C1 route on the public API.
- The email goes to `app_user.email` as it is at the send. The recipient row keeps the
  address used. An address changed in Cognito and not yet resynced is a known limit
  (`docs/deferred.md` § Accounts, "Nothing detects an email changed in Cognito").

### Step B — ops routes

All under `/api/v1/ops`, all behind the ops-role dependency, in the ops OpenAPI document.
Each write leaves an `ops_action` row; the row and the log line carry ids and counts, never
an email address or the message text.

- **B1. Preview recipients.** Input: kind and audience. Output: the counts (chosen, get it,
  left out by reason), the list with each person's status, and a **list fingerprint**: a
  hash over every person's id, address, status and reason, in a fixed order. It writes
  nothing.
- **B2. Send a test.** Input: the announcement fields. It sends one email to the
  operator's own address, subject prefixed "[Test] ", with a sample unsubscribe link that
  changes nothing. Action `announcement.test`.
- **B3. Add a picture.** Input: PNG or JPEG as base64 in JSON, at most 1 MB decoded. The
  server checks the leading bytes with the existing upload check, stores the file under a
  random name in the picture bucket (E3) and returns its public address. Action
  `announcement.image`.
- **B4. Send.** Input: the announcement fields, the audience and the list fingerprint from
  B1. In one transaction the server builds the recipient list (A2). If its fingerprint
  differs (a person joined, left, changed address or changed status, even when the count
  is the same), it answers 409 `recipients_changed` with the new counts and fingerprint
  and writes nothing. Otherwise it inserts the announcement, one recipient row for
  each person (`pending` or `left_out`) and the audit row (`announcement.send`). After the
  commit it starts the sender (B5). Answer: 201 with the id.
- **B5. The sender.** A background thread in the ops server. For each `pending` row it
  claims the row (`pending` → `sending`, one statement, so two senders or two ops tasks
  cannot take the same row), calls the mailer, then writes `sent`, or `failed` with a short
  reason. It sends at most 5 emails a second.
  - **Check at the send.** In the claim the sender reads the person's account again. If
    the person is now deactivated, or (product update) now unsubscribed, the row becomes
    `left_out` with that reason and no email goes.
  - **Start after a stop.** When the ops server starts, it starts a sender for every
    announcement that has `pending` rows. So a server that stops after B4's commit, or
    during a send, finishes the send when it comes back. It never touches a `sending` row.
- **B6. List and detail.** The list gives each announcement with its counts by status. The
  detail gives the announcement and its recipients (name, address, organisation, status,
  reason). For the detail the server reads the suppression list and shows a `sent` row as
  bounced or marked as spam when the address joined the list after the send. This overlay
  is not stored. If the suppression list cannot be read, the detail still answers, with a
  flag that says so.
- **B7. Retry.** Moves the `failed` rows of one announcement back to `pending` and starts
  a sender, which also takes any `pending` rows left waiting. It never touches a `sending`
  or `sent` row. Action `announcement.retry`.

**Invariant I1 (no second copy).** A person never gets two copies of one announcement. The
server marks a row `sending` before it calls SES. This is a deliberate at-most-once
choice: if the server stops after SES accepted the email and before the row is written,
the row stays `sending`. The page shows it as "Not confirmed" and nothing sends to it
again. The person may or may not have the email. The operator's remedy is a new
announcement to that one person.

**Invariant I2 (no cross-recipient leak).** Each email has one recipient. No email, log
line or audit row shows one recipient's address to another person.

**Invariant I3 (the opt-out holds).** No product update goes to a person whose
`updates_unsubscribed_at` is set when the sender claims their row (B5, the check at the
send). Only the person can set or clear it: no ops route and no `pa_ops` grant writes it.

### Step C — the public unsubscribe route and page

- **C1. Routes on the public API**, no sign-in:
  `POST /api/v1/unsubscribe?token=…` sets `updates_unsubscribed_at` if it is null;
  `POST /api/v1/resubscribe?token=…` clears it. Both are safe to repeat, ignore the body
  (mail providers post a fixed form body) and answer 204. An unknown or badly formed token
  answers 404. No route changes anything on a GET. A POST with no cookie, no `Origin` and
  no sign-in works and is never redirected (mail providers post this way, RFC 8058).
  - **The token is a bearer secret in an address.** The application's own log lines never
    hold it (the request log drops the query string for these two routes). The
    unsubscribe page sends no referrer, loads nothing from another site, and removes the
    token from the address bar after it reads it. AWS access logs at the edge can hold
    the address; this is an accepted limit, because the token can only switch one
    person's product updates off or on.
- **C2. Page on the public site**, `/unsubscribe`, outside the sign-in guard (annex
  § Unsubscribe page).
- **C3. Privacy page and data protection sign-off (a merge gate).** The privacy page says
  that we email account holders about the service and about product news, how to stop
  product news, and that email sent to `updates@` and `support@` is kept for 14 days in
  our storage and then in the team's inbox. Before the merge the owner records the Data
  Protection Officer's approval of the whole change: the two kinds of email and their
  lawful basis, the wording, and the handling and retention of incoming email.

### Step D — the ops pages

Built to [design-annex.md](design-annex.md) version 3.

- **D1.** The Announcements section and the list.
- **D2.** Compose: kind, audience, message, picture, preview, test. The browser makes a
  picture at most 1200 pixels wide before the upload. The compose preview shows the
  browser's own copy of the picture, so the ops Content Security Policy does not change.
- **D3.** The confirm dialog, with the `recipients_changed` state.
- **D4.** The result page, with retry.
- The ops mock API covers every route in B, with the annex's example data.

### Step E — AWS setup (CDK, per environment)

Four switches in `infra/pa_config.json`: `email.enabled` (it exists) controls E4;
`email.announcements` controls E1 and E2; `email.pictures` controls E3 (the bucket and
the CloudFront path; the ops role's put permission and the bucket setting need both
switches); `email.inbound` controls E5.

- **E1. Send permission.** The ops task role gains two separate statements:
  `ses:SendEmail`, limited to the sender identity and to the From address
  `updates@<sender domain>`; and `ses:ListSuppressedDestinations`, which SES does not let
  us limit to one identity, so its resource is `*`. The public API role gains no SES action. A test pins
  both.
- **E2. Ops settings.** The ops container gains the From address, the reply address
  (`email.reply_to` in `infra/pa_config.json`, one committed value), the public site and API
  addresses, and the picture bucket name. The test that pins the ops environment changes
  to match.
- **E3. Picture hosting.** A new bucket with all public access blocked. The existing
  CloudFront distribution serves it at `/email-images/*` through its own origin and origin
  access control; the bucket policy lets only this distribution read. The ops task role
  may put objects into it and nothing else. Each object has a random name, the content
  type that B3 checked, and a long cache time; it is never overwritten. The deploy
  script's sync of the frontend bucket does not touch it. Pictures are not deleted,
  because a sent email must keep its picture; a picture that was uploaded and never sent
  stays too (an accepted limit, at most 1 MB each, ops users only).
- **E4. DMARC.** A TXT record `_dmarc.<sender domain>` with `v=DMARC1; p=none`. Before
  the deploy the operator confirms in SES that DKIM is on for the sender identity.
- **E5. Incoming email.**
  - An MX record for the sender domain that points to SES receiving in the region.
  - A private bucket for incoming email. It deletes each object after 14 days. Only SES
    may write to it; only the forwarder may read it.
  - A receipt rule set named for the stack, with one rule for `updates@` and `support@`
    only: require TLS, scan for spam and viruses, store the email, then start the
    forwarder, in that order. SES refuses email to any other name.
  - SES uses only the **active** rule set of an account. The deploy makes this set
    active, and the rollback makes no set active. Before the first deploy the operator
    checks that the account has no other active set; if it has one, stop and escalate.
  - The bucket policy lets SES write only for this account's receipt rule. The
    forwarder's invoke permission is for SES and this rule only.
  - The forwarder:
    - forwards only an email whose spam and virus checks both passed; a failed or missing
      result is dropped;
    - drops automatic email: a delivery report (empty return path), an email with an
      `Auto-Submitted` header other than `no`, and an email that carries the forwarder's
      own loop mark. So an out-of-office answer or a bounce notice does not reach the
      team; bounces show on the result page (B6);
    - builds the copy with the standard library's email classes, so a line break in the
      sender's name or the subject cannot add a header;
    - runs at most two at a time, so a flood of email cannot become a flood of sends;
    - sends a copy to the team address, From `"<sender's name> via Policy Atlas"
      <forwarder@<sender domain>>`, Reply-To the original sender, subject unchanged;
    - reads the team address from the SSM parameter each time, so a change needs no deploy;
    - never forwards an email whose sender is the forwarder address;
    - for an email over 25 MB, forwards a short notice with the sender and subject;
    - can forward one email twice when AWS retries a failed run (an accepted limit: a
      second copy in the team inbox is better than a lost email).
  - The forwarder's role may read the bucket, read the one parameter and send from
    `forwarder@<sender domain>`. Nothing else.
- **E6. `infra/DEPLOYMENT.md`** gains the order of steps, the team-address parameter and
  each manual step, if one is necessary.

## Scope / Out of scope

- **In:** A1 to E6; `docs/deferred.md`; ADR 0051; `infra/pa_config.json`;
  `infra/DEPLOYMENT.md`; the ops and public OpenAPI documents and their generated types
  (by `make openapi-sync`).
- **Out (⏸, to record in `docs/deferred.md`):** drafts on the server · a send at a later
  time · saved templates · attachments · more than one picture · open and click tracking ·
  email to people without an account (the waitlist) · a reply sent from `updates@` or
  `support@` · an event stream for bounces and deliveries (temporary failures, delivery
  confirmation) · "Send an email" in the People, Cohorts and Organisations row menus · a
  "What's new" panel in the product · a stricter DMARC policy and DMARC reports · a shared
  team inbox · email the product sends by itself.

## Constraints & approval gates

Tier 4. The owner approved each gated class in chat (§ Facts settled) and confirms it at
this contract's gate.

- **Schema:** A1. Additive, with a reversible downgrade.
- **Auth / tenancy:** no new role. Two new public routes without sign-in (C1), keyed by a
  random token.
- **Runtime egress:** the ops server sends each recipient's address and the message text
  to SES, in the project's own AWS account, and SES delivers the email. The forwarder
  sends incoming email to the team address. No other outside service.
- **Public interface:** C1 on the public API; B1 to B7 on the ops API.
- **Production config:** the `email` block in `pa_config.json`; the ops task role (E1);
  two buckets; a CloudFront path; a Lambda function and its role; a receipt rule set; an
  MX and a TXT record; one SSM parameter for each environment.
- **Dependencies:** no new runtime dependency (no upload or image library: the browser
  resizes, the server checks bytes). One development dependency changes: `boto3-stubs`
  gains the `sesv2` extra, in the same group as today.
- **Frontend:** no new package. New routes in both bundles.
- **CI / deploy:** `scripts/deploy.sh` changes only if E3 or E5 needs it; the plan says.
- **Rollback, each exercised once on staging:**
  - E5: set `email.inbound` false and deploy. The MX record, rule, bucket and forwarder
    go, with any incoming email still in the bucket (at most 14 days; the team inbox
    keeps its copies); email to the domain is returned to its sender as before.
  - E1 and E2: set `email.announcements` false and deploy, and leave `email.pictures`
    true. The send routes answer 503. The picture bucket and its CloudFront path stay,
    so pictures in sent emails keep working.
  - A1: `alembic downgrade a3c9e1f7b2d4` with both services stopped, and the image
    deployed after is the one before this task.
  - E4: remove the record.
- **Ordering:** A1 deploys with the code. E1 to E3 before the first send. E5 after the
  team-address parameter exists. C before the first product update goes out.

## Public / private boundary

Committed: code, the email layout, config keys, the ADR. Never committed and never in an
application log: an email address (the team address is in SSM only), an unsubscribe
token, message text. (AWS access logs at the edge can hold the unsubscribe address: C1.) Announcement pictures are public by design; the compose page says so. Incoming email
is private: it stays in its bucket for 14 days and in the team inbox. Research notes and
review records stay in the gitignored `research/` folder.

## Design annex

[design-annex.md](design-annex.md) version 3 (mock:
https://claude.ai/artifact/9eoXRJFp9XeTTKM9tATZmq). This contract pins behaviours, states,
interfaces and invariants; looks and copy live in the annex. Polish round budget: 2 rounds
at the end of build and 2 at the end of review.

## Model route

n/a. No inference.

## Disciplines binding this slice

- **Model only what behaves.** Every column in A1 is read by a route or a rule in this
  contract. No scheduled time, no template, no open count.
- **Reuse, do not re-implement.** Every ops write goes through a command function and the
  audit row. The picture upload uses the existing byte check and store protocol. The
  forwarder follows the existing Lambda pattern (`infra/deploy_functions/`).
- **Honest result.** No page or route says "delivered" or "opened".
- **Leave deferred seams as seams** in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: a gate above would widen (for example the public API would need an
SES permission, or `pa_ops` an update on the opt-out column); CDK cannot create a part of
E5 under the deploy role; the SES sending rate or quota is too low for the account list;
the suppression list is not enabled or cannot be read; an AWS account already has an
active receipt rule set; DKIM is not on for a sender identity; scope grows past A1 to E6;
the budget is spent.

## Acceptance checks

- `make verify` green; `make openapi-sync` and `make drift-check` clean; infra synth tests green.
- Deterministic tests for every item (the rubric lists them). No AI eval applies.
- **Live, on staging, scoped to the changed surfaces** (about 45 minutes):
  1. Send the example product update to one cohort. It arrives from
     `updates@v3.policyatlas.uk`; its headers show DKIM pass and DMARC pass, and the DKIM
     signature covers both unsubscribe headers; the picture shows; the button works.
  2. Unsubscribe from that email: once by the link and the page, once by the mail
     program's own Unsubscribe button. A second product update leaves that person out; a
     service notice still reaches them. Subscribe again from the page.
  3. Send to a person whose address is on the suppression list: the preview and the
     result show them as left out with the reason.
  4. Stop the ops server during a send of at least 20 emails and start it: the send
     finishes without a click, and every person has at most one copy.
  5. Reply to the announcement, and write a new email to `support@`: both reach the team
     address, and "Reply" there addresses the original sender. Email to another name at
     the domain is refused. An automatic out-of-office answer is not forwarded.
  6. The deployed policies: the SES actions on the ops role and the forwarder role are
     exactly those in E1 and E5; the public API role has none.
  7. Each action left an `ops_action` row, and the ops log holds no email address.
  8. An invitation from Cognito still arrives (the MX and DMARC records did not break it).
  9. One full-chain smoke: a normal task run completes.
  10. Each rollback in § Constraints, once.

## Verification evidence expected

In `verification.md`: the command results; the staging checks with times and the
`Authentication-Results` header of one announcement (addresses redacted); the deployed
role policies; the diff summary; confirmation that no address, token or message text is
in the diff or in a quoted log; known gaps and deferred seams.

## Risk tier & review focus

**Tier 4**: schema, runtime egress, public routes without sign-in, production config, IAM,
DNS. Review stack: contract verifier · code review · security review · adversarial review
at the contract, plan and code · human deep review · ADR 0051 · the rollback plan above.

Focus: I1, I2 and I3 · the public API gains no SES permission and builds no mailer · the
unsubscribe routes change nothing on a GET and reveal nothing · the operator's text cannot
inject HTML or a header · the picture route stores only PNG and JPEG bytes · the forwarder
cannot loop and cannot be used to send to an address other than the team address · the MX
and DMARC records do not break Cognito's email · no email address reaches a log.

## Folded findings (contract-stage adversarial review, Codex, 2026-11-25)

Thirteen findings: 2 blockers, 9 material, 2 minor. All are folded in except the two parts marked "not taken".

| # | Finding | What changed |
|---|---|---|
| 1 | SES simple content cannot carry the unsubscribe headers (blocker) | A3: raw content built with the standard library; live check 1 |
| 2 | A person who unsubscribes between the send click and their email still got it (blocker) | B5 "check at the send"; I3 |
| 3 | A count does not catch a changed list of the same size | B1, B4: list fingerprint |
| 4 | A server that stops after the commit leaves rows waiting for ever | B5 "start after a stop"; B7; live check 4 |
| 5 | "No second copy" hides a row that can never be confirmed | I1 states the choice and the remedy |
| 6 | The unsubscribe token can leak; the one-click POST has no origin | C1 token rules; the boundary section |
| 7 | The suppression-list permission cannot be limited to one identity | E1: two statements |
| 8 | A receipt rule is not live without an active rule set and its policies | E5: rule set, activation, policies; a stop condition |
| 9 | The forwarder could loop or flood, and trusted sender text | E5: automatic email dropped, safe headers, two at a time |
| 10 | "Private bucket, served" was too thin | E3. **Not taken:** deletion of unused pictures (a sent email must keep its picture; unused ones are small and ops-only) |
| 11 | The privacy gate covered only one paragraph | C3 is a merge gate for the whole change |
| 12 | Annex rule "nothing is sent without the confirm dialog" contradicted the test send | Annex rule reworded |
| 13 | `app_user.email` can be stale | A4 states the limit and keeps the address used. **Not taken:** an email resync before each send |

Not reviewed by this pass, so checked by the live checks instead: DMARC alignment (check
1), the MX record's effect on Cognito email (check 8), the firewall in front of the
one-click POST (check 2).

## Owner rulings at the gate (2026-11-25)

- Point 4 below ("test before send" is a rule of the page): agreed.
- Invariant I1's "Not confirmed" row: accepted.
- Point 5 below: the owner states that the Data Protection Officer has signed off. The
  build still records the approval and the final wording in `verification.md` (rubric 23).
- Points 1, 3 and 7 below: agreed.
- Point 6 below (the `boto3-stubs` development dependency): approved.
- Point 2 below: **not agreed.** A product update leaves out people who have not signed
  in yet. The lead made it a fixed rule (A2, reason `not_signed_in`), not a box on the
  page: one rule less to choose and to test. This change came after the adversarial
  review. It is minor (one more left-out reason, no new column, no new route), so the
  review was not run again.
- The task is split into 068a (send) and 068b (receive): § Two parts.
- Picture hosting has its own switch, `email.pictures` (2026-11-25, during the build).
  With one switch, the rollback of sending also removed the CloudFront path, so pictures
  in emails already sent would break. Step E and the rollback text above say the new rule.
- Replies in 068a: the owner chose a Reply-To, `discoveryhub@nesta.org.uk`, "for now". Every recipient
  sees this address.

## For the owner to confirm at the gate

1. **No drafts on the server.** The browser keeps unsent text. (A lead simplification.)
2. ~~No "leave out people who have not signed in yet" box.~~ Replaced by a fixed rule:
   see the rulings above.
3. **Staging sends for real**, to staging accounts only. Without this the send path cannot
   be checked before production. This replaces the earlier proposal "tests only on staging".
4. **"Test before send" is a rule of the page**, not of the server: it guards against a
   mistake by a trusted operator.
5. **Data protection sign-off (C3)** is a merge gate: the Data Protection Officer approves
   the two kinds of email, the wording, and the handling of incoming email, which goes to
   one person's inbox at first.
6. **The development dependency** change (`boto3-stubs` extra).
7. **Automatic email is not forwarded** (out-of-office answers, bounce notices). This
   replaces the earlier idea that bounce notices reach the team inbox.
