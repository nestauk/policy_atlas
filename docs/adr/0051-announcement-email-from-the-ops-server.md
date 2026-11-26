# ADR 0051 — Announcement email is sent by the ops server through SES, to account holders only

- **Status:** Accepted — 2026-11-25 (owner, task 068 plan gate).
- **Date:** 2026-11-25
- **Task:** [068-ops-announcements](../tasks/068-ops-announcements/contract.md), part 068a
  (send). Part 068b (receive email at the product domain) is not decided here.
- **Builds on:** ADR 0046 (the ops server, its database login `pa_ops`, the audit table
  `ops_action`) · ADR 0047 (the firewall in front of the public API) · the SES (Amazon
  Simple Email Service) identities that Cognito already uses for sign-in email.

## Context

The team wants to tell people who have an account about a new release, planned downtime
or a change to the terms. Before this decision the product sent no email of its own: only
Cognito sent invitations and sign-in codes.

Four facts shape the design.

- The list of recipients is the account list. It lives in our database with cohorts and
  organisations. The ops server is the only place that can read all of it.
- UK rules (PECR, the Privacy and Electronic Communications Regulations, and UK GDPR)
  treat product news as marketing. A person must be able to opt out. A notice that a
  person needs to use their account is not marketing.
- An email cannot be taken back. A second copy to the same person is worse than a missed
  one.
- The ops server is open to the office network only, so it cannot serve an unsubscribe
  link. The public API can.

## Decision

1. **No outside email or CRM tool.** The ops pages send the email. The rule that keeps
   this small: the ops pages email account holders only.
2. **Two kinds of email.** A *product update* carries an unsubscribe link and the
   one-click unsubscribe headers (RFC 8058). It leaves out people who unsubscribed and
   people who have not signed in yet. A *service notice* has no link and reaches everyone
   chosen. The operator picks the kind.
3. **The ops server sends through SES**, one email for each person, from
   `updates@<sender domain>`, with a shared team inbox as Reply-To. This is new runtime
   egress: an email address and the message text go to SES in the same AWS account. The
   ops role gets `ses:SendEmail` for that one From address, and read access to the SES
   suppression list. The public API role gets no SES permission.
4. **Raw content.** The mailer builds the message with the Python standard library and
   sends it as raw content, because SES refuses the unsubscribe headers on simple content.
5. **Send at most once.** The send writes one row for each person, then a background
   thread in the ops server claims each row (`pending` to `sending`) before it calls SES.
   A server that stops in the middle leaves a row as "Not confirmed". No code sends that
   row again: the operator decides. A retry takes only rows that failed before SES
   accepted them.
6. **The list is checked twice.** The confirm step compares a fingerprint (a SHA-256 hash)
   of the list the operator saw with the list the server builds. A count is not enough. At
   the send, the server reads the person's account again, so a person who unsubscribed or
   was deactivated a moment ago gets no email.
7. **Unsubscribe by a random token.** Each account has an `unsubscribe_token` (a UUID). Two
   public routes, POST only and without sign-in, set and clear the opt-out. A GET changes
   nothing, because mail scanners open links. `pa_ops` cannot update the opt-out columns:
   only the person can change their choice.
8. **Bounces come from the SES suppression list.** The server reads the list before a send
   and when it shows a result. There is no event stream and no delivery status: "Sent"
   means SES accepted the email.
9. **No tracking.** No open pixel and no click tracking.
10. **One optional picture**, stored in its own private bucket and served by CloudFront.
    Anyone with the link can open it.
11. **A DMARC record** (`v=DMARC1; p=none`) for the sender domain. It reports only; it
    blocks nothing.

## Alternatives considered

- **An email service or CRM (Mailchimp and similar).** Rejected for now: it needs a copy of
  the account list that goes stale, and a new company that holds people's addresses. Move
  to one when we want email to people without an account, open and click statistics, or
  automatic sequences.
- **Send from the public API.** Rejected: it would give the internet-facing service a
  permission to send email. The ops server is behind the office allowlist.
- **A queue and a worker.** Rejected at this size (a few hundred people, a few emails a
  month). The row claim gives the same guarantee. Revisit above about a thousand
  recipients.
- **A signed unsubscribe link.** Rejected: it needs a signing secret and its rotation. A
  random token in the database does the same job.
- **An SES event stream for bounces and deliveries.** Rejected for now: a queue, a worker
  and a table, to learn about temporary failures only.
- **Retry "Not confirmed" rows automatically.** Rejected: it can send a second copy.

## Consequences

- The ops server now sends personal data (address, message) to SES. The privacy notice
  says so, and the Data Protection Officer's sign-off is a merge gate.
- Announcements share the SES account with Cognito's sign-in email. A bad send can hurt
  the delivery of sign-in codes. The low volume, the suppression list, the unsubscribe
  headers and DMARC are the guards.
- A row can stay "Not confirmed" for ever. The operator contacts that person by hand if it
  matters.
- A temporary failure (for example a full mailbox) is not shown.
- Until part 068b is live, no address at the product domain receives email. Replies go to
  the Reply-To inbox; an email typed to `updates@` comes back as undeliverable.
- Unused pictures stay in the bucket. They are small and only an operator can add them.
- Rollback: set `email.announcements` to false and deploy. The tables stay; nothing sends.
