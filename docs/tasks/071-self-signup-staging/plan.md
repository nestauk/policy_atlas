# Plan: 071-self-signup-staging

> **Status:** drafted 2026-11-25; not yet confirmed by the owner. Ids (A1, B2, D5.4, I3) are
> those of [contract.md](contract.md); words are in [design-annex.md](design-annex.md); terms
> are in contract § Terms. The build runs in a fresh conversation with `task-cycle-build`.

## Shape

Twelve phases. The backend goes first, in the order that keeps every commit green: schema,
then the three operator features, then the public route, then the sweep. The pages come
after the interface is generated. The staging switch (part E) is a separate small pull
request after this one merges.

## Reuse before new code

| Need | Reuse | New |
|---|---|---|
| Make an account in an organisation | `commands.ensure_account_enrolled`, `commands.approve_request` | nothing |
| Cohort membership | `commands.add_to_cohort`, `commands.resolve_cohort`, the route helper `_cohort` | nothing |
| Audit row and log line | `commands.record_action`, `_audit`, `_queue_log` | three action names |
| Domain rule | `commands._normalise_domain` | nothing |
| Email and name rules for the file | the validator and limits of `PersonCreate` (`api/contract/ops.py`), moved to one function both use | one small function |
| Read CSV | Python `csv` with `utf-8-sig` decoding | nothing |
| Create many from the page | the "one call for each item, keep each outcome" loop of `RequestsView.sendMany` | the same loop over file rows |
| Cohort picker with several values | `SearchSelect` (`frontend/src/ops/ui.tsx`) holds one value. None exists for several. | one `CohortsField` in `ops/ui.tsx`, used in four places |
| List page with a dialog | `CohortsView` (table, row menu, add and edit dialog) | `InviteLinksView` on the same pattern |
| Random secret | `commands._mint_temporary_password` shows the `secrets` pattern | `new_invite_code` |
| Sweep outcomes and cap | `sweep_once` as built | one wider candidate query and one redeem branch |

## Seams the lead fixes before delegation

These signatures are part of the briefs. The agents implement them; they do not redesign them.

1. `policy_atlas/core/invite_code.py` (no import of `ops`, so the public API can use it):
   - `ALPHABET: str` (32 characters), `CODE_LENGTH = 12`.
   - `normalise(value: str | None) -> str | None` — upper case, remove hyphens and spaces;
     `None` unless exactly 12 alphabet characters.
   - `new_code() -> str` — the stored form (no hyphens).
   - `display(code: str) -> str` — `XXXX-XXXX-XXXX`.
2. `commands.py`:
   - `create_invite_link(conn, *, label, org, cohorts, allowed_domain, max_uses, expires_at, created_by, now) -> InviteLink`
   - `update_invite_link(conn, *, invite_link_id, label, max_uses, expires_at, now) -> InviteLink`
   - `revoke_invite_link(conn, *, invite_link_id, now) -> InviteLink`
   - `redeem_request(conn, cognito, *, pool_id, entry_id, now) -> Approval | None` — locks the
     link, checks D5.1 again, and returns `None` when the request is no longer redeemable.
3. The candidate query (D5.3, D5.8), one statement:
   waiting requests where the email domain is listed, **or** an `invite_link` row exists
   with the same code, `revoked_at IS NULL`, `expires_at > now`, the same domain, and
   `(SELECT count(*) FROM waitlist_entry WHERE invite_link_id = link) < max_uses`;
   oldest first; limit 200.
4. The link state (D6) and the not-redeemed reason (D8) come from one function,
   `invite_link_state(link, uses, now)`, used by the list route and the Requests route.
5. The public upsert (D3.3 to D3.5), one statement: insert; on an email conflict, set
   `invite_code` to the new code where the stored request is waiting and the new code is
   not null.

## Phases

Check marks: **F** = `make verify-fast`; **FF** = `make frontend-verify-fast`; **V** = full
`make verify`.

| # | Phase | Contract | Executor | Check |
|---|---|---|---|---|
| 0 | Baseline. Rebase on `dev`; find the newest migration (`alembic heads`); run the full check before any edit. Write the ADR 0046 amendment once both approvals are given. | — | lead | V |
| 1 | Schema: `core/schema.py`, one migration (two tables, two columns, a partial index on `waitlist_entry.invite_code` and on `waitlist_entry.invite_link_id`, the `pa_ops` grants), the migration round-trip test, the grant-list test. | D1, I8 | deep-reasoner | V |
| 2 | `cohort_ids` on create person and approve: contract models, routes, tests. | B1–B6, I6 | deep-reasoner | F |
| 3 | Import check: the shared person-field function, the route, tests. | C1, C2, I7 | deep-reasoner | F |
| 4 | Invite link commands and ops routes; `PUBLIC_APP_ORIGIN` in `Settings`; the organisation-delete refusal; tests. | D2, D6, D9, I10 | deep-reasoner | F |
| 5 | Public route: `invite_code` on the body, the upsert, tests. | D3, I1, I2 | deep-reasoner | F |
| 6 | Sweep: the candidate query, `redeem_request`, the Requests reason field, tests (including the two-connection lock test and the 250-request test). | D5, D8, I3–I5, I9 | deep-reasoner | V |
| 7 | `make openapi-sync`; commit the generated files. | — | lead, inline | F |
| 8 | Public form: the words, the address code, the invite line, tests. | A1, A2, D4 | frontend-designer (words from the annex; the lead owns them) | FF |
| 9 | Ops pages: `CohortsField`; Add person; Approve dialogs; Add many; Invite links; the Requests line; the Organisations refusal; mock fixtures; tests. | B7, C3–C6, D7–D9 | frontend-designer | FF |
| 10 | Infrastructure: the ops service gets `PUBLIC_APP_ORIGIN` from `domain_name`; the infra unit test. | D6 | fast-worker (exact two-line spec) | infra tests |
| 11 | Docs: `web-api.md`, `infra/DEPLOYMENT.md`, the living copy file, `docs/deferred.md`. A3 (email sentence) only if the owner said yes. | Scope § Docs, A3 | lead | F |
| 12 | Exit: simplify pass; rollback rehearsal on a local database; `verification.md`. | E4, rubric | lead | V |

Each phase ends with a commit on `task/071-self-signup-staging`.

**Why these full checks.** Phase 0 is the build-open baseline. Phase 1 changes the schema.
Phase 6 changes the loop that makes accounts and reads the new columns. Phase 12 is the
exit. Phases 2 to 5 add routes and tests and do not touch the schema or the ingest code, so
the fast check gates them. Phases 8 and 9 are frontend only.

**Why every executor.** Phases 1 to 6 are logic with a machine-checkable done (the rubric
rows), so `deep-reasoner`. Phases 8 and 9 are pages, so `frontend-designer`. No phase is
marked `codex`: the second model family reads the work at the review stack. No phase holds a
prompt.

## After the merge (part E)

| Step | What | Who |
|---|---|---|
| E-a | Deploy `dev` to staging (the migration runs first, as every deploy does). | lead, on the owner's go |
| E-b | E1: confirm the Nesta organisation and its domain; the owner clears old `nesta.org.uk` requests. | owner |
| E-c | E2: a pull request that sets `self_signup.enabled` true for staging only; deploy. | lead, owner approves |
| E-d | E3: the seven live checks; record them in `verification.md`. | lead and owner |
| E-e | The owner sends the announcement. | owner |

## Order risks

| Risk | Answer |
|---|---|
| Task 068 (announcements) may merge a migration first. | Phase 0 rebases and takes the newest migration as the parent. The chain is rebuilt, never the other task's file. |
| New API code runs before the migration. | The deploy runs the migration task before it starts the services. The upsert of phase 5 names `invite_code`, so it fails loudly, not silently, if the order is wrong. |
| An old API image with the new schema (during a rollback). | The new columns are nullable and the old code does not name them. Safe. |
| The uses count in the candidate query gets slow. | The partial index on `invite_link_id` (phase 1). A link has at most 1,000 uses. |
| Two ops tasks run the sweep at once (a deploy overlap). | The link row lock (D5.5) and the existing row lock in `approve_request`. The two-connection test proves it. |
| The file flow runs for minutes and the sign-in token ends. | The page calls one route for each person, so the token refresh of the ops pages applies between calls. A failed call lands in the failed list with Try again. |
| The grant test and the migration disagree. | Phase 1 changes both in one commit. |

## Open items for the owner before the build

1. Approve the contract (the gate table in it).
2. Approve the words in the annex, or change them.
3. A3: the authenticator sentence in the invitation email, yes or no.
4. A mock round for the ops pages before the build, yes or no.
