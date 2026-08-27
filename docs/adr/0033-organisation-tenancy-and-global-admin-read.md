# ADR 0033 — Organisation tenancy above the entity hierarchy, and a global admin read

- **Status:** Accepted — 2026-08-24 (owner, with the 033 contract and plan approvals)
- **Date:** 2026-08-24
- **Task:** 033-organisations · contract rev 3.0 approved 2026-08-24 · plan rev 2.0
  approved 2026-08-24. Both were rewritten after adversarial review; the contract review
  recommended splitting the slice in three and the owner ruled to keep one slice and patch
  every finding.
- **Binding design records:** `docs/tasks/033-organisations/contract.md` (owner calls
  (a)–(k); §§ 3, 3a, 3b, 4, 5, 6, 7, 12a), `plan.md`, `rubric.md` (42 items)
- **Amends:** **ADR 0031 decision 4** — see decision 6.

## Context

Until now the system had exactly one tenancy rule: a row belongs to the `sub` in
`project.owner_user_id`, and anyone else gets an indistinguishable 404. That rule is
correct and this ADR does not weaken it. What it could not express is the thing the product
now needs — that a person works inside an organisation, and colleagues should be able to
read each other's work.

Three constraints bound the answer:

1. **The IdP cannot supply membership.** The Cognito pool is deliberately feature-free:
   no groups, no custom claims, and `UsernameAttributes: ["email"]` means
   `cognito:username` is a generated UUID. The access token the API receives carries
   `sub` and nothing else usable.
2. **`docs/specs/system/data-model.md` § Entity hierarchy** governs what may sit between a
   project and its artefacts. Tenancy must not become another level inside that hierarchy.
3. **The system is live**, so every change is additive, dark-launchable, and must leave
   behaviour byte-identical while no organisation exists.

## Decisions

1. **Tenancy sits ABOVE the entity hierarchy, as two columns on the rows that already have
   owners.** `organisation` and `app_user` are new tables; `project` and `portfolio` each
   gain a nullable `org_id` and a `visibility` (`org`|`private`). Nothing below the project
   row learns a new parent and no read model gains a level, so the data-model rule holds
   for the same reason ADR 0031 gave: this is on the other side of the project entirely.

   *Rejected:* an `organisation` FK on artefacts, runs or findings. Tenancy would then have
   to be re-derived at every grain, and the 404 rule would need restating per read model.

2. **`sub` remains the only identity the API reads, and the only key.** `app_user.user_id`
   **is** the token `sub`. Email is resolved once, out of band, by the ops CLI and stored
   for operator and admin use; it is never read from a token, never sent by a client, and
   never rendered to another user.

   *Rejected:* keying on the email address. Addresses change — a surname, a move between
   departments — and Cognito permits the attribute to be updated. A person's Tasks would
   silently detach from them on the day theirs changed.

   *Rejected:* a pre-token-generation Lambda to put email or membership into the access
   token. It puts personal data in every request header, adds infrastructure, and would
   make the IdP authoritative for something the application owns.

3. **One access helper, three read legs and one write grade — and the org leg is a SQL
   predicate.** Read = owner ∪ (same organisation ∧ `visibility='org'`) ∪ admin. Write =
   owner only, with exactly one documented exception: the three chat mutations a same-org
   colleague may perform on a readable project. Not-visible is still an indistinguishable
   404; visible-but-not-writable is a 403, which is the hook `web-api.md` reserved.

   **The NULL rule is part of the decision, not an implementation detail.** A row with
   `org_id IS NULL` is reachable by its owner and by an admin only; a caller with
   `org_id IS NULL` matches no org leg. The leg must be expressed in SQL, where
   `NULL = NULL` is unknown — evaluated in Python, `None == None` is `True`, and on the day
   of the migration every row and every un-enrolled caller has a NULL `org_id`. That single
   mistake would expose the entire existing corpus to every signed-in user. It is written
   here because it is the highest-blast-radius error available in this design.

4. **Administrator access is one global boolean, read-only, and disclosed by a trace rather
   than by restriction.** `app_user.is_admin` grants read of every row in every
   organisation, `visibility='private'` included. It grants **no write, ever** — an admin
   is explicitly *not* treated as a colleague, so it does not inherit the three chat
   mutations. It is settable only by the ops CLI: no HTTP route writes it and no request
   body can reach it.

   Only four places may read the flag — the row-access helper's admin leg, the listing
   scope resolver, the `owner_email` filter gate, and the `/me` projection — and that
   closed list is asserted structurally, because `is_admin` is a broad name and broad names
   attract unrelated checks.

   **The honest position on the control set.** The design intended two controls: a trace on
   every admin read, and a sentence in the published privacy notice telling users that
   administrators can access content. **The owner ruled that this slice does not edit legal
   copy** — that belongs to whoever owns the notice, which names a Data Protection Officer.
   So only the trace ships, and the three discrepancies the review found in the notice
   (§ 7 promising an erasure no lever performs, § 3's "only user-specific identifier"
   claim, § 6's silence on administrator access) are escalated in writing instead.
   **While that stands, the trace is the sole control**, which is why decision 5 exists and
   why the log's one-month retention is recorded as the bound on any investigation.

   *Rejected:* a "dev organisation" whose members see everything. An organisation means a
   tenancy boundary here, and one-org-per-user would force the deferred multi-org join
   table — an admin would stop being a normal member of their own organisation. A flag is
   also cheap to drop later where a join table is not.

   *Rejected:* letting the flag pierce nothing, i.e. admins seeing only org-visible rows.
   Support cases are disproportionately the private ones, and whoever holds ops access can
   already read the database. The flag adds convenience over an existing boundary, not a
   new claim on user data.

5. **The audit trace is only real if it is structured, so this slice wires logging at the
   API entrypoint.** `configure_logging()` was called solely by `runtime/orchestrate.py`'s
   `main()`, which runs only as a local CLI. The container starts
   `uvicorn ... api.app:create_app` directly and executes runs in-process, so **nothing
   deployed had ever configured logging** and `LOG_FORMAT=json` was inert. A pre-existing
   defect would normally be its own slice; this one is not, because decision 4 leaves the
   trace as the admin leg's only control and an unstructured line is not an audit trail.

6. **The visibility invariant, and the amendment to ADR 0031 decision 4.** A `project` with
   a `portfolio_id` carries that `portfolio`'s `visibility` **and** its `org_id`.
   Resolution is deterministic and nothing prompts: joining a private project to an
   org-visible portfolio promotes it; joining an org-visible project to a private portfolio
   demotes it — the non-exposing direction; a portfolio's visibility change cascades to its
   members. Setting a project's visibility while it belongs to a portfolio is refused with
   409, because it alone would change rows the caller never named.

   **This amends ADR 0031 decision 4**, which stated that assignment is a PATCH on the
   project and that create routes are left alone to keep the gated public surface smaller.
   `POST /portfolios` now accepts `from_project_id`, creating the portfolio, inheriting the
   source project's `visibility` and `org_id`, and taking it as the first member. The
   amendment is narrow and deliberate: "create a Project from this Task" is the owner's
   stated flow, and without the assignment the inheritance would describe nothing. The
   cost is a second write path that must uphold the invariant, which is why the invariant
   is proved by a property test over all six paths rather than by six examples.

7. **Enrolment carries a person's existing work with them, private.** `user enrol` stamps
   `org_id` onto every `project` and `portfolio` the person owns and sets those rows
   `visibility='private'`, in one transaction with the `app_user` upsert. Two properties
   decide it: **no operator action can expose a row** — they arrive private and the person
   opts each one in deliberately — and **the person sees no change**, because rows with a
   NULL `org_id` were already invisible to everyone but them.

   The move is safe as a set operation because a portfolio's members are always owned by
   the portfolio's owner: setting `portfolio_id` requires ownership of both rows. So one
   person's rows are a closed set and the invariant cannot break mid-move.

   *Rejected:* leaving history behind and reporting the count. It splits a person's work in
   two with nothing on screen explaining why, and the repair — a bulk stamp — would then be
   an operator action that discloses a whole back catalogue at once.

   **De-enrolment is symmetric**: it clears `org_id` on their rows, so an organisation loses
   sight of a departing member's work. This treats work as belonging to the person rather
   than the organisation. The alternative is defensible and would need ownership transfer,
   which is deferred; it is recorded here as a decision rather than an assumption.

## Consequences

- **Every project-, portfolio- and conversation-scoped route** resolves access through one
  helper, including the seven routes keyed by conversation id that an earlier revision of
  the contract missed entirely.
- **Tenancy invalidates assumptions written for single-owner access.** SSE authorised once
  and streamed through revocation; the stale-turn sweeper was keyed to the project owner;
  `PATCH /portfolios/{id}` splatted its payload straight into an `UPDATE`. Each is now in
  scope. This is the general lesson: tenancy is not a refactor of ownership checks.
- **Rollback is forward-only.** The downgrade is schema-reversible and data-destructive: it
  drops `created_by`, and pre-033 code lists every conversation on a project to its owner,
  so rolling back after adoption would expose colleagues' chats. It also drops both
  `visibility` columns, so a re-upgrade defaults every row back to `org` and no private
  choice survives. The dark launch is the real safety net, and de-enrolment reverts an
  organisation without a deploy.
- **Deferred, and coupled:** deleting a Cognito user and transferring ownership ship
  together or not at all, because deleting someone who owns work needs somewhere for that
  work to go. Multi-org membership, per-organisation roles, an admin surface and MFA on the
  pool are each recorded in `docs/deferred.md` with the condition that would reopen them.
- **The vocabulary split persists.** This ADR works in code words; screen **Task** =
  `project`, screen **Project** = `portfolio`. The rename slice that follows 033 retires
  the split and must cover this slice's code.
