# Task 068 — announcements from the ops pages: design notes

> **Status:** background and research only. [contract.md](contract.md) is the authority:
> where these notes differ (pictures, drafts, staging, bounce notices, the reply-to), the
> contract is right. Screens: https://claude.ai/artifact/9eoXRJFp9XeTTKM9tATZmq ·
> explainer: https://claude.ai/artifact/LJLLL8ANkQeHvLh6Y8UH2k (both private to the owner).

## Goal

An operator writes one email in the ops pages and sends it to people who have an account:
everyone, one or more cohorts, one or more organisations, or named people. The first use is
release announcements.

## What the code has today

- The ops server is a separate service behind the office allowlist (ADR 0046). It has its
  own database login (`pa_ops`) and an audit table (`ops_action`).
- `app_user.email`, `organisation`, `cohort` and `cohort_member` already hold everything the
  recipient picker needs.
- The backend sends **no** email today. Only Cognito sends (invitation and sign-in codes),
  through SES (Amazon Simple Email Service), from `no-reply@policyatlas.uk`.
- `boto3` (the AWS library for Python) is already a dependency. No new library is needed.
- The privacy page says the lawful basis for holding the email address is legitimate
  interest, for user testing. It does not mention product news.

## Is the ops pages the right place? (Do we need a CRM?)

Yes for this scope. A CRM (customer relationship management tool) or an email service such
as Mailchimp is the wrong tool **now**:

- The recipient list is the account list. It lives in our database with cohorts and
  organisations. A separate tool needs a copy, and the copy goes stale.
- A new tool is a new company that holds people's email addresses: a data-processing
  agreement, a privacy-page change, a new place for a leak.
- We have a few hundred people at most and send a few emails a month.

Keep one rule: **the ops pages email account holders only.** Move to a real tool when we
want one of these: email to people without an account (waitlist, newsletter), open and click
statistics, automatic sequences, or designed marketing templates. Do not build those here.
Ask Nesta's communications team which tool they already use before that day.

## What we can use it for

| Use | Kind |
|---|---|
| New release, new feature | Product update |
| Request for feedback or a survey | Product update |
| Planned downtime, incident and the follow-up | Service notice |
| Security change (for example the authenticator-app sign-in) | Service notice |
| Change to terms, privacy notice, quota or limits | Service notice |
| Cohort logistics: pilot start, end, session reminders | Service notice |
| Reminder to people who were invited but never signed in | Service notice |

## Good practice, and what it means for the build

1. **Two kinds of email.** A *service notice* is something a person must know to use their
   account. A *product update* is news. UK rules (PECR, the Privacy and Electronic
   Communications Regulations, and UK GDPR) treat news as marketing: the person must be able
   to opt out. So a product update has an unsubscribe link and skips people who
   unsubscribed; a service notice has no link and goes to everyone chosen.
   **Check this split and the privacy-page wording with the Data Protection Officer.**
2. **One email per person.** Never one email with everyone in To, CC or BCC.
3. **A test first.** The operator must send the email to themselves before the real send.
4. **Show the count, then confirm it.** The page shows how many people get the email and who
   is left out. The operator types the count to confirm. An email cannot be taken back.
5. **A record of every send.** Who sent what to whom, and the result for each person. A
   retry sends only to the people that failed, so nobody gets two copies.
6. **Protect the sign-in email.** SES drops addresses that bounced or complained (its
   account-level suppression list). Send announcements with the standard `List-Unsubscribe`
   header. Low volume keeps the sender reputation that Cognito's sign-in codes depend on.
7. **No tracking.** No open pixels or click tracking. It fits the product and the privacy
   page, and it is less to build.
8. **Plain content.** Subject, plain-text message (paragraphs and "- " lists) and one
   optional button, in the same branded template as the invitation email. No rich editor
   and no HTML from the operator: nothing to sanitise, and every email looks the same.

## Proposed build (smallest version that is safe)

- **Pages:** a fifth top-bar section, **Announcements**: a list, a compose page, a confirm
  dialog and a result page. Later: "Send an email" in the row menu of a cohort, an
  organisation or a person, which opens compose with that recipient filled in.
- **Tables:** `announcement` (subject, body, kind, who chose it, sent by, sent at) and
  `announcement_recipient` (one row per person: sent, failed or left out, with the reason).
  One new column, `app_user.updates_unsubscribed_at`.
- **Sending:** the ops server calls SES once per person, in a background task, a few per
  second. The result page reads the per-person rows.
  Ceiling: fine up to about a thousand people; above that, move to a queue.
- **Unsubscribe:** a link with a signed token to one small route on the **public** API (the
  ops server is office-only, so it cannot serve it). The route sets the column and shows a
  short page. No sign-in needed.
- **Audit:** each send writes an `ops_action` row.

### Hard gates this touches (all need the owner's approval)

- **Schema:** two tables, one column, grants for `pa_ops`.
- **Runtime egress:** the ops server sends email addresses and message text to SES. Same AWS
  account that Cognito already uses, but a new permission (`ses:SendEmail`, limited to our
  sender identity) on the ops task role.
- **Public interface:** new ops routes and one public unsubscribe route.
- **Infra:** the permission above; a reply-to address.

## Skipped on purpose

Scheduling a send for later, saved templates, attachments, images, open and click
statistics, email to the waitlist, a rich-text editor, an in-app "What's new" panel.
Add each when someone needs it. The in-app panel is the most useful next step: many people
do not open email.

## Sender address (researched 2026-11-25)

- `policyatlas.uk` has no MX records (the DNS entries that say where mail for a domain
  goes), so no address at the domain can receive mail today. `hello@` would promise an
  inbox that does not exist.
- Email-service guidance agrees: do not send news from a no-reply address; use a monitored
  address, or a branded From with a separate Reply-To. No-reply stays acceptable for
  sign-in and security codes.
- A separate sending subdomain is not worth it at our volume: a low-volume subdomain cannot
  build its own reputation.
- **Proposal:** From `Policy Atlas <updates@policyatlas.uk>` for both kinds (SES can send
  from any address at a verified domain, so no new setup), Reply-To an existing shared Nesta
  inbox. Cognito keeps `no-reply@`.

## Images (researched 2026-11-25)

- Use **hosted images** (a normal web link to a picture on our own site, as the email logo
  already is), not pictures attached inside the email: attached pictures make the email
  large and show unreliably in web mail.
- Outlook on the desktop hides pictures until the reader allows them, so the text must make
  sense alone and every picture needs alt text (the words shown when the picture is not).
- A hosted picture is public to anyone with the link. A screenshot must show no private data.
- The build needs two new libraries (file upload and image resizing), a storage permission
  and a public path: a second step, not the first version.
- **Proposal:** version 1 has no pictures; the button links to a page that has them.
  Version 2 adds one picture per email, uploaded on the compose page, with required alt text.

## Rulings (owner, 2026-11-25)

- Two kinds of email, as proposed: agreed.
- Everyone with the ops role can send, for now.
- From address: `updates@policyatlas.uk`.
- Pictures are in version 1 (this overrides the "version 2" proposal above).

- DMARC record: yes.
- `updates@policyatlas.uk` becomes a real address: SES receives the mail and a forwarding
  step sends it to the team's inboxes. The owner tries it in the console first.
- Staging sends from `v3.policyatlas.uk`; SES is in production mode in both environments.

### Receiving and forwarding: the parts

1. MX record for the domain: `10 inbound-smtp.eu-west-2.amazonaws.com`.
2. A storage bucket for incoming mail, which deletes each email after a few days.
3. A small forwarding function (AWS publishes a sample): it reads the email from the bucket
   and sends a new email to the team, with the original sender as Reply-To. It sends from
   an address the receipt rule does not accept (for example `forwarder@`), so a bounce of a
   forwarded email cannot loop.
4. A receipt rule for `updates@` only: spam and virus scan, store, then call the function.
5. Console first on staging, then the same in CDK so production matches (infra hard gate).

### Bounces: two levels

- **Level 1 (proposed for this task):** read the SES suppression list. Before a send, leave
  out addresses on it. On the result page, mark recipients that joined it since the send
  ("the address does not exist", "marked as spam"). One read permission, no new parts.
  It misses temporary failures such as a full mailbox.
- **Level 2 (later):** a configuration set publishes bounce, complaint and delivery events
  to a queue, and a worker writes them to the database. Needed only for delivery
  confirmation per person or for temporary failures.

## Mail sent to `updates@policyatlas.uk` (checked 2026-11-25)

- The domain has no MX records, so mail addressed to `updates@` is returned to its sender
  as undeliverable. A normal reply goes to the Reply-To inbox and is not affected.
- The domain has no DMARC record (the DNS entry that tells other mail servers what to do
  with mail that falsely claims to come from us). Add one in this task; start with
  `v=DMARC1; p=none`.
- SES accepts an email first and reports a bounce (a returned email) later. By default it
  emails the bounce notice to the From address, which has no inbox, so the notice is lost.
  SES still adds the address to its suppression list. To show "the address does not exist"
  on the result page we must wire SES bounce events to the database: decide in the contract.

## Open points for the owner

1. **From and reply-to.** Agree with `updates@policyatlas.uk`? Which inbox gets replies?
2. **Pictures.** Version 1 without, or in from the start?
3. **Staging.** Staging has its own accounts and its own SES identity. Allow real sends
   there, or only tests to yourself?
4. **Privacy page.** It needs a line about product news and the opt-out. Who words it?
5. **Entry points** from the People, Cohorts and Organisations rows: in this task or later?
