# Plan: 071-self-signup-staging

> **Status:** drafted 2026-11-25; Codex plan review folded in the same day (ten findings,
> all adopted; the list is in the contract's § Contract review); not yet confirmed by the
> owner. Ids (A1, B2, D5.4, I3) are
> those of [contract.md](contract.md); words are in [design-annex.md](design-annex.md); terms
> are in contract § Terms. The build runs in a fresh conversation with `task-cycle-build`.

## Shape

Ten phases after the baseline. The backend goes first, in the order that keeps every commit green: schema,
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
| Email and name rules for the file | `PersonCreate.email` already calls `WaitlistSignup.validate_email`; the name rule is `Field(min_length=1, max_length=OPS_NAME_MAX)` after stripping | one function, `validate_person_fields(email, display_name)`, beside those rules in `api/contract/`; `PersonCreate` and the import check both call it. No third email rule. The public route does not import `api.contract.ops`. |
| Read CSV | Python `csv` with `utf-8-sig` decoding | nothing |
| Create many from the page | only the pattern of `RequestsView.sendMany`: one `mutateAsync` call for each item in turn, and Try again on the failed subset | a row-result state keyed by file line, with one outcome for each row (`invited`, `added`, `elsewhere`, `failed`); the file and its rows live in memory only |
| Cohort picker with several values | `SearchSelect` (`frontend/src/ops/ui.tsx`) holds one value. None exists for several. | one `CohortsField` in `ops/ui.tsx`, used in four places |
| List page with a dialog | `CohortsView` (table, row menu, add and edit dialog) | `InviteLinksView` on the same pattern |
| Random secret | `commands._mint_temporary_password` shows the `secrets` pattern | `new_invite_code` |
| Sweep outcomes and cap | `sweep_once` as built | one wider candidate query, one redeem branch, one lock for the whole tick; the `if not domains: return` shortcut is removed |

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
   - `redeem_request(conn, cognito, *, pool_id, entry_id, now) -> Approval | None`. Lock
     order, fixed: (1) lock the `invite_link` row; (2) read the uses and check D5.1 again,
     returning `None` when the request is no longer redeemable; (3) call the existing
     `approve_request`, which locks the `waitlist_entry` row; (4) add the cohorts; (5) set
     `invite_link_id`. No code path locks a link after a request. Manual Approve never locks
     a link.
   - Cohorts at create, approve and redeem follow one sequence: resolve and de-duplicate
     every cohort id **before** the first Cognito call; after the enrolment, call
     `add_to_cohort` for each; write a `cohort.add` audit row only where the membership is
     new (`add_to_cohort` reports it); all on the caller's transaction.
3. The candidate query (D5.3, D5.8), one statement:
   waiting requests where the email domain is listed, **or** an `invite_link` row exists
   with the same code, `revoked_at IS NULL`, `expires_at > now`, the same domain, and
   `(SELECT count(*) FROM waitlist_entry WHERE invite_link_id = link) < max_uses`;
   oldest first; limit 200. The statement runs when no domain is listed (the shortcut at
   `sweep.py:91` goes). The listed-domain map is used only for a candidate with no valid link.
   **A failed request waits (D5.13):** the statement also leaves out a request whose newest
   sweep audit row is `failed` and younger than 15 minutes (`ops_action`, actor `sweep`,
   action `invite`, target the request id; the sweep already reads these rows for its
   terminal outcomes).
   **One tick at a time:** `sweep_once` takes a PostgreSQL advisory lock
   (`pg_try_advisory_lock`, one fixed key) on its own connection before the cap read and
   holds it to the end of the tick. If the lock is taken, the tick does nothing. This is what
   keeps the hourly cap true when two ops tasks overlap during a deploy; the link row lock
   alone does not.
4. Two pure functions in one place:
   - `invite_link_state(link, uses, now) -> "active" | "expired" | "full" | "revoked"` for
     the list route (D6).
   - `invite_request_reason(*, invite_code, request_domain, link, uses, now) -> str | None`
     for the Requests route (D8). It handles a missing link (unknown code) and a wrong
     domain, and calls the first function for the rest.
   The sweep does not trust either: it checks again under the lock (seam 2).
5. The public route (D3). The body field is optional text with the contract's length
   bound and no pattern. The route normalises it with `invite_code.normalise` before the
   statement. One statement, with no `RETURNING`:
   `INSERT … ON CONFLICT (email) DO UPDATE SET invite_code = EXCLUDED.invite_code WHERE
   waitlist_entry.account_created_at IS NULL AND waitlist_entry.rejected_at IS NULL AND
   EXCLUDED.invite_code IS NOT NULL`. The route answers with the values it made itself, as
   today, whether a row was inserted, updated or left alone.

## Phases

Check marks: **F** = `make verify-fast`; **FF** = `make frontend-verify-fast`; **V** = full
`make verify`; **D** = `make openapi-sync` then `make drift-check`, with the generated files in
the same commit (a phase that changes a route or a body is not green without it).

| # | Phase | Contract | Executor | Check |
|---|---|---|---|---|
| 0 | Baseline. Rebase on `dev`; find the newest migration (`alembic heads`); run the full check before any edit. Write the ADR 0046 amendment once both approvals are given. | — | lead | V |
| 1 | Schema: `core/schema.py`, one migration (two tables, two columns, a partial index on `waitlist_entry.invite_code` and on `waitlist_entry.invite_link_id`, the `pa_ops` grants), the migration round-trip test, the grant-list test. | D1, I8 | deep-reasoner | V |
| 2 | `cohort_ids` on create person and approve, by the cohort sequence of seam 2: contract models, routes, tests of the exact audit rows. | B1–B6, I6 | deep-reasoner | F + D |
| 3 | Import check: `validate_person_fields`, the route, tests. | C1, C2, I7 | deep-reasoner | F + D |
| 4 | Invite link commands and ops routes; the organisation-delete refusal; tests. `PUBLIC_APP_ORIGIN`, whole: `Settings` requires it in ops mode and refuses a value that is not an `https` origin with no path, query or fragment (local `http://localhost` is allowed as `APP_ORIGIN` is today); the public service does not get it; the infrastructure code sets it from `https://{domain_name}` on the ops container only; a settings test and an infra test of the built container. | D2, D6, D9, I10 | deep-reasoner | F + D + infra tests |
| 5 | Public route: `invite_code` on the body, the statement of seam 5, tests. | D3, I1, I2 | deep-reasoner | F + D |
| 6 | Sweep: the candidate query, the tick lock, `redeem_request`, the Requests reason field. Tests: links with no listed domain; two requests for one link on two connections (bounded by a timeout, so a deadlock fails the test); a second tick that finds the tick lock taken does nothing; 250 unknown-code requests ahead of one redeemable request. | D5, D8, I3–I5, I9 | deep-reasoner | V (includes D) |
| 7 | Public form: the words; read the code from the fragment (`#invite=`), remove it from the address bar, scroll to the form; the invite line; tests. | A1, A2, D4 | frontend-designer (words from the annex; the lead owns them) | FF |
| 8 | Ops pages: `CohortsField`; Add person; Approve dialogs; Add many; Invite links; the Requests line; the Organisations refusal; mock fixtures; tests. | B7, C3–C6, D7–D9 | frontend-designer | FF |
| 9 | Docs: `web-api.md`, `infra/DEPLOYMENT.md`, the living copy file, `docs/deferred.md`. A3 (email sentence) only if the owner said yes. | Scope § Docs, A3 | lead | F |
| 10 | Exit: simplify pass; rollback rehearsal on a local database; `verification.md`. | E4, rubric | lead | V |

Each phase ends with a commit on `task/071-self-signup-staging`.

**Why these full checks.** Phase 0 is the build-open baseline. Phase 1 changes the schema.
Phase 6 changes the loop that makes accounts and reads the new columns. Phase 10 is the
exit. Phases 2 to 5 add routes and tests and do not touch the schema or the ingest code, so
the fast check gates them, with the generated interface files checked in each (D). Phases 7
and 8 are frontend only.

**Why every executor.** Phases 1 to 6 are logic with a machine-checkable done (the rubric
rows), so `deep-reasoner`. Phases 7 and 8 are pages, so `frontend-designer`. No phase is
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
| New API code runs before the migration. | The deploy runs the migration task before it starts the services. The statement of phase 5 names `invite_code`, so it fails loudly, not silently, if the order is wrong. |
| An old API image with the new schema (during a rollback). | The new columns are nullable and the old code does not name them. Safe. |
| The uses count in the candidate query gets slow. | The partial index on `invite_link_id` (phase 1). A link has at most 1,000 uses. |
| Two ops tasks run the sweep at once (a deploy overlap). | The tick lock (seam 3): the second tick does nothing, so the hourly cap and `max_uses` both hold. The link row lock (D5.5) stays as the second guard. |
| The file flow runs for minutes and the sign-in token ends. | The page calls one route for each person, so the token refresh of the ops pages applies between calls. A failed call lands in the failed list with Try again. |
| The grant test and the migration disagree. | Phase 1 changes both in one commit. Phase 6 adds a full redemption on a real `pa_ops` connection, because a matching list does not prove the commands run. |
| The splash page already uses `#access` to scroll to the form. | The page treats `#invite=…` as a second case of the same scroll, then replaces the fragment with `#access`. |
| A rollback removes data. | The normal rollback is the switch (contract E4). Phase 10 rehearses the downgrade on a local database only and records the parent revision. |

## Open items for the owner before the build

1. Approve the contract (the gate table in it).
2. Approve the words in the annex, or change them.
3. A3: the authenticator sentence in the invitation email, yes or no.
4. A mock round for the ops pages before the build, yes or no.
