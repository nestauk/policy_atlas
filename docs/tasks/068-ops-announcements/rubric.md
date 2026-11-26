# Rubric: 068-ops-announcements

The task is **done only if every box holds**. Ids (A1 to E6, I1 to I3) and terms are the
contract's ([contract.md](contract.md) § Terms, § The work).

> **Two parts:** row 29 belongs to part 068b and is not checked in 068a. In the other
> rows, leave out what concerns incoming email (contract § Two parts).

1. [ ] Implementation satisfies [contract.md](contract.md), items A1 to E6.
2. [ ] `make verify` passes; `make openapi-sync` and `make drift-check` are clean; the infra
       synth tests pass; the ten staging live checks pass and are recorded.
3. [ ] No approval-gated change snuck in unapproved: schema (A1), public routes (C1), ops
       routes (B1 to B7), egress (A3, E5), production config and IAM (E1 to E5), the
       development dependency. Nothing else of those classes changed.
4. [ ] No generated files or secrets edited by hand. No email address, unsubscribe token or
       message text is in a committed file or a quoted log.
5. [ ] No test deleted, skipped or weakened unless its behaviour stays covered by another
       test and the review confirmed it.
6. [ ] Verification evidence recorded in [verification.md](verification.md).
7. [ ] Known gaps and deferred seams listed; `docs/deferred.md` updated (the "no
       notification channel" entry narrowed; the contract's Out list recorded).
8. [ ] Required Tier 4 review stack ran: contract verifier · code review · security review ·
       adversarial review at contract, plan and code · human deep review; findings in
       `verification.md`.

Slice-specific (each is a test unless it says "live"):

9. [ ] **A1.** The migration upgrades and downgrades cleanly. Every existing `app_user` row
       has a distinct `unsubscribe_token`. `pa_ops` holds exactly the contract's grants, and
       an update of `updates_unsubscribed_at` or `unsubscribe_token` as `pa_ops` is refused.
10. [ ] **A2.** For the annex's example data the rules give 82 chosen, 79 for a product
        update and 81 for a service notice. A person in a cohort and an organisation appears
        once. Each left-out reason is produced, in the contract's order of precedence.
11. [ ] **A3.** In API mode the application builds no mailer. In ops mode without the
        sender settings the send, test and retry routes answer 503.
12. [ ] **A4.** Operator text with `<script>`, `&`, a quote and a line break in the subject
        comes out escaped in the HTML, and a line break in a header value is refused. A button link that does not
        start with `https://` is refused. A product update has the unsubscribe link and both
        headers; a service notice has none. The plain-text body carries the same content.
13. [ ] **B1.** The preview returns counts and reasons and writes no row.
14. [ ] **B2.** The test goes to the operator's own address only, and its unsubscribe link
        changes no account.
15. [ ] **B3.** A PNG and a JPEG are stored and their address returned. A file over 1 MB,
        an SVG, and a text file named `.png` are refused.
16. [ ] **B4.** A matching fingerprint inserts the announcement, every recipient row and
        one audit row in one transaction. A changed list answers 409 `recipients_changed`
        and inserts nothing, also when one person left and another joined (same count).
17. [ ] **B5, I1.** Two senders on one announcement send each email once. A row is
        `sending` before the mailer is called. A mailer error gives `failed` with a reason
        and the sender goes on to the next row. A person who unsubscribes (product update) or is
        deactivated after B4's commit and before their row is claimed gets no email and
        becomes `left_out`. A failure after the mailer accepted and before the row is
        written leaves `sending`, and neither retry nor a restart sends to it. With
        `pending` rows in the database, ops start-up starts a sender.
18. [ ] **B6.** The detail shows a `sent` row as bounced when its address joined the
        suppression list after the send, and stores nothing. With the suppression list
        unreadable the detail still answers, with the flag set.
19. [ ] **B7, I1.** Retry sends to `failed` and `pending` rows and never to a `sending` or
        `sent` row. The detail shows a `sending` row left by a stopped server as "Not
        confirmed".
20. [ ] **I2.** Each mailer call has one recipient. The audit rows and log lines of a send
        hold no email address and no message text.
21. [ ] **I3, C1.** A product update leaves out a person who unsubscribed and a person who
        has not signed in yet; a service notice leaves out neither. `POST` unsubscribe and resubscribe set and clear the mark and are safe to
        repeat; an unknown token answers 404; a GET on either address changes nothing; a
        form POST with no cookie and no `Origin` answers 204 with no redirect; the request
        log line for these routes holds no token. No ops route writes the mark.
22. [ ] **C2.** The unsubscribe page works signed out, shows the annex's four states,
        sends no referrer and removes the token from the address bar.
23. [ ] **C3.** The privacy text is in, and the owner recorded the Data Protection
        Officer's approval of the whole change (kinds of email, wording, incoming email).
24. [ ] **D1 to D4.** The mock journey plays the annex's five scenes: the list; compose
        with the count changing between 79 and 81 with the kind; the send button disabled
        until a test of the current text succeeded, and disabled again after an edit; the
        confirm dialog and its `recipients_changed` state; the result page with retry.
25. [ ] **E1.** Synth: the ops task role holds `ses:SendEmail` (limited to the identity and
        the From address) and, in its own statement, `ses:ListSuppressedDestinations`, and
        no other SES action; the
        public API role holds none. With `email.announcements` false neither is present.
26. [ ] **E2.** Synth: the ops container's environment is exactly the pinned list.
27. [ ] **E3.** Synth: the picture bucket blocks all public access; its policy lets only
        this distribution read; the distribution has the `/email-images/*` behaviour with
        its own origin and access control; the ops role may only put objects into it.
28. [ ] **E4.** Synth: one `_dmarc` TXT record for the sender domain, present only when
        `email.enabled` is true.
29. [ ] **E5.** Synth: with `email.inbound` true there is one MX record, one receipt rule
        whose recipients are exactly `updates@` and `support@`, with TLS required, the scan
        on and the store action before the forwarder action; the rule set is made active;
        a bucket with a 14-day expiry that only SES may write to, for this rule; an invoke
        permission for SES and this rule only; a forwarder role with only the three
        permissions and at most two runs at a time; with it false, none.
        Forwarder unit tests: a failed or missing spam or virus result is dropped; a
        delivery report, an automatic answer and an email with the loop mark are dropped;
        a line break in the sender's name or subject adds no header; the copy has the
        contract's From, Reply-To and To; an email from the forwarder address is not
        forwarded; an oversized email gives the notice.
30. [ ] **E6.** `infra/DEPLOYMENT.md` has the steps, and a person who follows them on
        staging reaches live check 5 (live).
