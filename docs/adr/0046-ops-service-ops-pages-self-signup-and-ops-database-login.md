# ADR 0046 — An ops service behind the office allowlist, with its own pages, its own database login, quota overrides, and self-signup for one domain

- **Status:** Accepted — 2026-11-16 (Karlis Kanders, owner, task 065 plan gate).
- **Date:** 2026-11-16
- **Task:** [065-accounts](../tasks/065-accounts/contract.md) (contract revision 3.1 and plan
  draft 2 approved 2026-11-16), the accounts programme: Cognito email through SES (A), the ops
  service and pages (B), self-signup for `nesta.org.uk` (C).
- **Builds on:** [ADR 0033](0033-organisation-tenancy-and-global-admin-read.md) decision 4
  (the administrator flag) and its Consequences "Deferred" list, both amended here ·
  [ADR 0045](0045-per-user-run-cap-task-quota-offboarding.md) decisions 1, 2 and 5 (the run
  cap, the task quota, the offboard command), extended here · the
  [064 programme map](../tasks/064-security-hardening/programme.md) § "The ops portal is a
  separate task (065)".

## Context

Account work today is done by one engineer at a terminal: creating a Cognito account, enrolling
it in an organisation, moving rows, offboarding, and approving access requests from the waitlist.
Every step needs AWS access, the database and the command-line tool in `policy_atlas.ops`. The
team wants non-technical colleagues to do this work from a web page, and wants people with a
`nesta.org.uk` address to get an account without anyone's help.

Three facts shape the answer. The public API is reachable by anyone and today holds no AWS
permission that can create or disable accounts; the owner wants that to stay true. Cognito can
only send mail through an SES identity in the same AWS account, so each environment owns its
identity and both have production sending access. Metabase already runs behind a listener rule
that admits only office address ranges, with a checked and sized allowlist, so a second service
of the same shape costs nothing new to learn.

ADR 0033 decision 4 made the administrator flag read-only, settable only by the CLI, with a
closed list of code readers, and listed "an admin surface" as deferred. This slice adds that
surface, so decision 4 and the deferred list are amended below rather than left contradicted.

## Decisions

1. **The ops surface is a second ECS service, from the same backend image, started in ops
   mode, reachable only from the office allowlist.** `POLICY_ATLAS_SERVICE_ROLE=ops` mounts
   health checks, the `/api/v1/ops/*` routes and the ops pages, and nothing that runs work: no
   `/me`, no task or run routes, no run executor, no startup sweep, no continuation drainer, no
   ingest consumer (asserted by a test with those entry points patched). The public API keeps
   no `cognito-idp` permission; the ops task role holds exactly five Cognito actions, scoped
   to the pool. The listener admits the ops hostname only from the address ranges in an SSM
   parameter that the deploy script validates and sizes, the Metabase way. Switching the
   service off is `desired_count` 0; the public app is untouched.

   *Rejected:* **an ops page inside the public app**, calling ops routes on the public API
   (contract revision 2's in-app `/ops` route included). Every ops route would then sit on a
   host anyone can reach, and the public API would need the Cognito permission the owner wants
   it never to hold. *Rejected:* **a path rule on the public service** admitting `/api/v1/ops`
   only from the office. One misconfigured rule would expose the routes; a separate host is a
   boundary a reviewer can read in the listener. *Rejected:* **the AWS Cognito console**: it
   needs AWS access per operator, knows nothing of organisations or rows, and leaves no record
   in our database. *Rejected:* **a separate admin tool (Retool or similar)**: a second
   codebase, a second credential to the database, and a vendor between operators and account
   data. *Rejected:* **running the checks on a timer with no server**: a process that is not
   running cannot answer a click.

2. **The ops pages are served from the ops address itself, not from the public app.** A second
   Vite entry (`frontend/ops.html` → `src/ops/main.tsx`) in the same frontend project, with the
   same design system, sign-in code and Cognito client, built by the deploy script and copied
   into the backend image, served by the ops service as a fallback for every non-API path. One
   address (`ops.<domain>`), so the allowlist covers the pages as well as the routes, the
   browser makes no cross-site calls, and the public bundle carries no ops route, link or
   code. The pages have their own shell: no New, Tasks or Projects, because ops work is
   separate from using the product (owner, 2026-11-16). Several people can be selected and one
   action applied to all of them; the route runs the command once per person with one audit
   row each, so one failure leaves the others recorded. The ops routes have their own OpenAPI
   document; the public one has no ops path and `MeOut` is unchanged.

3. **An ops role separate from the administrator flag, and no HTTP route sets either.**
   `app_user.is_ops` admits a person to the ops routes and grants no read of product rows. It is
   granted and revoked only by the CLI, like `is_admin`. De-enrol and offboard clear both flags
   through the command functions, and a database trigger (decision 6) refuses any statement
   from the ops login that sets either flag from false to true. So taking over the ops pages
   cannot widen anyone's access.

   **Amendment to ADR 0033 decision 4.** Its sentence "no HTTP route writes it and no request
   body can reach it" stays true for `is_admin` and now also for `is_ops`. Its closed reader
   list gains two entries: `routers/common.py::effective_limits` (the quota exemption moved
   there from the task-create route) and `contract/ops.py::PersonOut` (the ops-host people
   list projects both flags); the closed-list test records both. Its wider implication,
   that no HTTP route writes `app_user` or `organisation` at all, no longer holds: the ops
   routes, on the ops service only, create and change both through the same command functions
   the CLI calls. Email addresses are visible to ops-role holders on the ops host; the public
   API's `owner_email` rule is unchanged. ADR 0033's Consequences "Deferred" list: "an admin
   surface" is discharged by this slice; multi-org membership, per-organisation roles and MFA
   stay deferred.

4. **Every ops write goes through a command function and leaves one durable audit row.** Routes
   are thin: parse, call the command, record. `ops_action` (time, actor subject, action,
   target, outcome) is inserted in the same transaction as the change, so the page cannot do
   anything the command line could not and the two cannot drift apart. The table is
   append-only: no route updates or deletes it. The `ops.action` log line stays the live
   signal; the table is the record the one-month log retention never gave us.

5. **Quota overrides per person and per organisation, resolved in one place** (extends ADR 0045
   decisions 1 and 2). Nullable `task_quota_per_year` and `runs_per_user` on `app_user` and on
   `organisation`, `CHECK (>= 0)`; null means inherit, `0` means no limit. One resolver gives a
   person's effective limits: their own override, else their organisation's, else the settings
   value. The task-create check, the run-cap check and `/me` call the resolver and nothing else
   reads the columns. Administrators stay exempt from the task quota. The ops pages edit both
   numbers, with a warning on simultaneous tasks because raising it spends shared capacity
   (owner, 2026-11-16: allow the change, show the warning).

   *Rejected:* a quota table with history. Two columns on rows that exist are enough, and the
   audit row records every change with who and when.

6. **The ops service connects with its own least-privilege database login.** A Postgres role
   `pa_ops`, granted exactly what the command functions and the sweep do (contract B13, as
   the review stack narrowed it on 2026-11-17): `USAGE` on the schema with no `CREATE`;
   `SELECT, INSERT` and column-level `UPDATE` on `app_user` and `organisation`; `SELECT` on
   `organisation_domain`; `SELECT` and column-level `UPDATE` on `waitlist_entry` (the two stamp
   columns); `SELECT, INSERT` on `ops_action`; `SELECT` and column-level `UPDATE` on `task` and
   `project`; `SELECT, DELETE` on `project_membership` (moving a person severs their cross-owner
   memberships); `SELECT, INSERT, DELETE` on `cohort` and `cohort_member` and `UPDATE` on the
   seven cohort detail and quota columns (B14); `UPDATE (rejected_at)` and `DELETE` on
   `waitlist_entry`, with a `BEFORE DELETE` trigger that refuses this login's delete of a row
   that is not rejected (B15; amended at the review stack, 2026-11-18, contract revision 4.1);
   nothing on `capability_run`, `alembic_version` or any other
   table. A `BEFORE INSERT OR UPDATE` trigger on `app_user` refuses this login setting
   `is_admin` or `is_ops` to true, by an update or by inserting a row that already carries the
   flag. A test reads the grants back from the catalogue and compares them to this list. The grants live in a migration so a reviewer can read them, a later migration that
   gives the ops service a new table extends them in the same migration, and a test logs in as
   `pa_ops` with a password and checks both what succeeds and what is refused. The password
   is a generated secret in Secrets Manager; the deploy script sets it after migrations and
   before the ops service starts. The database now refuses what the contract's prose used to
   promise.

   *Rejected:* the master login for both services. A fault in the ops service could then touch
   run and report data.

7. **Self-signup is a sweep in the ops service, for listed domains only, and the public form
   is unchanged.** `organisation_domain` maps a domain to an organisation (one row for now:
   `nesta.org.uk` → Nesta; domains are added by CLI, not created automatically). With the
   self-signup flag true, the ops-mode lifespan runs one loop every 60 seconds that turns
   unstamped waitlist rows with a listed domain (exact match on the lower-cased part after `@`,
   no subdomains) into accounts through one idempotent ensure-account command, oldest first,
   at most `max_per_hour` per hour (default 100 since 2026-11-19; was 20) counted from the audit table. The public
   `POST /api/v1/waitlist` route and its response are byte-identical for a listed and an
   unlisted domain, so the form still reveals nothing. The public API never gains a Cognito
   permission.

   **The abuse ceiling, stated honestly (contract C4).** The form is public, so anyone can
   submit addresses they do not own, and the invitation is sent before mailbox ownership is
   proved; ownership is proved only when the invitation is used. The ceiling: one invitation
   per distinct address ever (unique email, permanent stamp), at most `max_per_hour` per hour
   across all rows, only to addresses in a listed domain, and a one-hour 429 cooldown on
   resend. The honeypot stays. **Ordering rule:** production does not set the self-signup flag
   true before 064b's WAF rate rule is live; staging may run it earlier for testing.

   *Rejected:* creating an organisation from a new domain automatically. A listed domain is a
   decision someone made, so the organisation exists before the row does.

8. **Cognito sends through SES with branded templates, switched per environment.**
   `email.enabled` in `pa_config.json` moves the pool to DEVELOPER sending through the
   environment's own identity; the invitation and verification templates are HTML files under
   `infra/email/` applied only with the SES sender, because the research could not confirm
   custom templates work with the default sender. Rollback is `email.enabled` false and a
   deploy. Nesta's shared SES account cannot carry this mail (fact 2), and the Tech Team accepts
   the project accounts owning their identities.

## Alternatives considered

- **Email two-step sign-in on the ops host now.** Deferred to a later 064 slice, after SES is
  live; until then a stolen laptop on the office network can use the ops pages until the
  session expires or the person is offboarded. Accepted for an internal tool behind an
  address allowlist.
- **An ops page that onboards ops users.** Rejected: granting the ops flag stays a terminal
  action (decision 3), because it is rare and should be deliberate.
- **`gov.uk` and other domains.** Deferred; the domain table makes adding one a row, not a
  deploy.

## Consequences

- **One more server, always on**, at the smallest task size, about the cost of the Metabase
  server. The allowlist needs upkeep when the office network changes; working from home means
  the office VPN.
- **A change to the ops pages is a backend deploy**, because the image carries the bundle. For
  an internal tool used by a few people this is accepted. Ops users bookmark the address; the
  app has no link to it.
- **Deploy order changes:** build the ops pages, update infra, stop both services, migrate and
  sync the ops login, start the API, then the ops service. The same order applies to a
  downgrade, and no rollback drops a table while a service that reads it runs.
- **The administrator reader list stays closed**; the ops flag gets its own closed reader list
  and test. Decision 4 of ADR 0033 is amended as written in decision 3 above, not rewritten.
- **`docs/deferred.md`:** the SES entry is discharged, the admin-surface entry is reopened as
  done, and three seams are added: domains beyond `nesta.org.uk`, the domain table on the ops
  page, application-sent email.
- **Accepted limits recorded by the review stack (2026-11-17).** Cognito calls happen before
  the database commit, so a write that rolls back after Cognito answered can leave a sent
  invitation with no `invited_at` stamp, or a disabled account with a `failed` audit row;
  the next attempt lands on the idempotent branch. The `pa_ops` password travels to Postgres
  as a quoted literal in `ALTER ROLE`, which the server would log only if that statement
  failed under a verbose log setting. The sweep assumes one ops instance: the deploy script
  holds `desired_count` at 0 or 1 and the service rolls with no overlap. A request the sweep
  can never fulfil (an address the command or Cognito rejects) is terminal (`refused`) and
  shown as "Check" for an operator; failed attempts count against the hourly allowance, so
  a bad row cannot drive unbounded Cognito calls. The ops host sets `X-Frame-Options: DENY`.
  The ops service's engine hides bound parameters from error tracebacks.
- **Cohorts (owner, 2026-11-18, contract B14):** named groups of people, separate from
  organisations, managed on the ops pages only; `pa_ops` may create, edit and delete cohorts and
  their memberships. A cohort may set the two quotas; they apply after the person's own and
  before the organisation's, and in several cohorts the most recently joined that sets a
  limit wins. Feature versions per cohort are the next task.
- **Ruled by the owner (2026-11-18):** a sweep-created account keeps the form's name, and
  `max_per_hour` is 5 on production. The ops pages do not move single tasks or projects
  (that stays in the CLI), so `pa_ops` has no grant on `task.updated_at`.
- **Was open for the owner (2026-11-17):** whether a sweep-created account should take the
  waitlist row's name at all (anyone can type a colleague's address with any name; the name
  is never written onto an existing account) and whether an address that already has an
  account should be left for an operator instead of enrolled; and `max_per_hour` on
  production (20 today; 5 was suggested for the first weeks).

## Amendment (2026-11-19, task 066): deactivate, reactivate and organisation delete

The owner's first use of the staging ops pages showed that offboarding left no mark the
pages could show, and that re-adding the address left the login disabled. Task 066
([contract](../tasks/066-ops-deactivate/contract.md)) changes this:

- **Deactivate replaces offboard** (owner ruling B). It disables the login, signs the
  person out everywhere, clears the admin and ops roles, takes down their public links
  and sets the new `app_user.deactivated_at`. The person **keeps** their organisation,
  tasks, projects and cohorts. `user offboard` and `POST /people/offboard` are retired.
- **Reactivate** turns the login back on (`AdminEnableUser`) and clears the mark, with
  no role or link given back. No role can be granted while a person is deactivated.
- **Only an operator turns a login back on:** Reactivate, or Add person on that
  address, and then only after the organisation check passes. Waitlist approval and the
  self-signup sweep refuse a deactivated or disabled account. The sweep's outcome
  `deactivated` is terminal and shows as "Check".
- **Whether a login is disabled** is read from `AdminGetUser`, not from `ListUsers`
  (eventually consistent). A failed read fails the command.
- **The ops server's role has six Cognito actions:** the five of decision 7, plus
  `AdminEnableUser`.
- **`pa_ops`** gains `UPDATE (deactivated_at)` on `app_user` and `DELETE` on
  `organisation`. Delete refuses while any person, task, project or domain points at
  the organisation, and the foreign keys refuse as a backstop.
- **Accepted risk:** an access token issued before deactivation can read the
  organisation's shared work until it expires (up to 60 minutes). It is recorded in
  `docs/deferred.md`.
