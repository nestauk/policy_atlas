# Task contract: 066-ops-deactivate

> **Status:** built 2026-11-19. Scope and ruling B approved by the owner in chat (2026-11-19);
> the owner reviews this text with the local UI review and the PR. Plan: this contract's
> § Build order (a small slice, no separate plan) · ADR: amendment to
> [ADR 0046](../../adr/0046-ops-service-ops-pages-self-signup-and-ops-database-login.md).
> Branch `hotfix/ops-portal-fixes`. Tier 4 (migration, a database grant, an AWS permission,
> a retired command).

## Goal

The owner's first use of the staging ops pages (2026-11-19) found page bugs (part A, done)
and two gaps (part B):

- After **offboarding**, nothing showed that the person was locked out, and adding the same
  address again enrolled them but left the login disabled ("User is disabled").
- There is no way to **remove an organisation**.

Part B replaces offboarding with **deactivate** and **reactivate**, recorded in the
database and shown on the pages, and adds **delete** for an empty organisation.

## Terms

| Term | Meaning |
|---|---|
| **Deactivate** | Block a person's login and mark them deactivated. Replaces "offboard". Their organisation, tasks and projects stay (owner ruling B, 2026-11-19). |
| **Reactivate** | Turn the login back on and clear the mark. |
| **Deactivated** | `app_user.deactivated_at` is set. New column. |
| **Disabled** | Cognito's own flag on the account (`Enabled = false`). Deactivate sets it; accounts offboarded before this task have it with no `deactivated_at`. |
| **`pa_ops`** | The ops server's restricted database login (task 065, ADR 0046). |

## Part A — page fixes (done, commit `68c56f00`)

1. The first calls after sign-in went out with no token (staging logs: bare 401s, no
   `auth.token_rejected`). The sign-in provider now updates its token reference before
   any child query starts. This also fixes "a non-ops account cannot sign out": the page
   showed Sign in instead of the no-ops-role page with its Sign out.
2. No section links until the first read answers (no flash).
3. Sign in sits at the right of the top bar.
4. Cohort dates wrap at the dash instead of running into Links.
5. People shows "12 of ∞" when there is no task limit.
6. A failed action opens a dialog with Try again, so a long table cannot hide it.

## Part B — behaviours

**B1. The column and grants** (one migration after `e8f6a4b3c1d0`):
- `app_user.deactivated_at timestamptz NULL`.
- `GRANT UPDATE (deactivated_at) ON app_user TO pa_ops`.
- `GRANT DELETE ON organisation TO pa_ops`.
- Downgrade drops the column and revokes the delete grant.
- The test that pins `pa_ops`'s permission list is updated to match, and nothing else in it changes.

**B2. Deactivate** (`commands.deactivate_user`; it replaces `offboard_user`, which is
deleted):
1. Cognito first: `AdminDisableUser`, then `AdminUserGlobalSignOut`. If either fails, the
   command stops before any database write, as offboard did.
2. Database, in one transaction:
   - set `deactivated_at`;
   - clear `is_admin` and `is_ops`;
   - turn off every public link on their tasks.
3. **Kept:** the organisation, tasks, projects, cohort memberships and quotas.
4. An already deactivated person: the Cognito disable and sign-out run again (they
   repair the login state if someone turned it back on by hand). The database keeps the
   first `deactivated_at`, and the step says "already deactivated".
5. You cannot deactivate your own account from the pages (the existing self-guard).
6. A person with no Cognito account (deleted from the pool) still gets the database half,
   as offboard did.

**B3. Reactivate** (`commands.reactivate_user`):
1. `AdminEnableUser`, then clear `deactivated_at`.
2. It does **not** restore the admin or ops role or public links. Those are separate,
   deliberate acts. `admin grant` and `ops grant` **refuse** while a person is deactivated,
   so no role can be given in advance and come back with the login.
3. It also enables an account that is disabled in Cognito but has no `deactivated_at`
   (people offboarded before this task).
4. A person who is not deactivated or disabled gives the outcome "not deactivated" and
   makes no change.

**B4. Add person on a deactivated address.** `POST /api/v1/ops/people`, on an address
whose account is deactivated or disabled:
1. Check the organisation **first**. If the person is in a different organisation, give
   the existing "enrolled elsewhere" refusal, with no Cognito call and no database write.
2. Only then reactivate (B3) and enrol: the same organisation succeeds, and no
   organisation means enrol.
3. The answer says it reactivated the account.
4. `ListUsers` finds the account. Whether it is disabled is read from `AdminGetUser`,
   which is authoritative; `ListUsers` is eventually consistent. If the read fails, the
   command fails and changes nothing. The check covers accounts offboarded before this
   task.

**B5. No silent reactivation anywhere else.**
- **Approving a waitlist request** for a deactivated or disabled account refuses: "This
  person is deactivated. Reactivate them on People first."
- **The self-signup sweep** skips such a request, with the terminal audit outcome
  `deactivated`. The request stays unstamped, no invitation is sent, and the waitlist
  page shows it as "Check", like the other terminal outcomes. A deactivated person cannot
  get back in through the public form.

**B6. The pages (People):**
- A `DEACTIVATED` chip on the row.
- A status filter: Active (default), Deactivated, All.
- Row menu: "Deactivate…" for an active person, keeping today's typed confirmation.
  "Reactivate…" for a deactivated one, with a plain confirmation.
- The selection bar has "Deactivate" and "Reactivate".
- "Resend invitation" is disabled for a deactivated person.
- `PersonOut` gains `deactivated_at`. Every word "offboard" on the pages becomes
  "deactivate".

**B7. Delete an organisation** (`DELETE /api/v1/ops/organisations/{id}`,
`commands.delete_organisation`):
1. It refuses unless no person, task, project or domain points at the organisation.
   The refusal names the counts, for example "Still has 3 people and 12 tasks."
2. The foreign keys refuse as well, as a backstop.
3. On Organisations, the row menu gets "Delete…", with a confirmation dialog that shows
   the refusal when there is one.
4. Audit action `organisation.delete`.

**B8. Command line.**
- `user offboard` is **retired** (owner, 2026-11-19: still in testing). It is replaced by
  `user deactivate` and `user reactivate`, with the same `--email | --sub` selectors.
- `org delete --org ORG` is added.
- The parser-structure test is updated.

**B9. Routes and audit.**
- `POST /people/offboard` is removed. It is replaced by `POST /people/deactivate` and
  `POST /people/reactivate`, both bulk, with the same shape.
- The audit actions are `person.deactivate`, `person.reactivate` and
  `organisation.delete`.
- The ops OpenAPI document and its types are regenerated.

**B10. AWS.** The ops task role gets `cognito-idp:AdminEnableUser` on the one user pool,
so it has 6 actions. The infra test that pins the list is updated.

**B11. Docs.**
- In `infra/DEPLOYMENT.md` and `infra/JUMPBOX.md`, offboard becomes deactivate/reactivate.
- The ADR 0046 amendment records the ruling, the sixth permission and the grant.
- ADR 0045 gets a one-line pointer.
- Update the copy in `docs/tasks/065-accounts/ops-pages-copy.md`, which is a living copy
  file.
- In `docs/deferred.md`, remove "deleting an organisation" if it is listed.

## Contract review (Codex, read-only, 2026-11-19)

All five findings were adopted into B2 to B5 above:
1. **Critical:** re-add reactivated before refusing another organisation.
2. **High:** roles could be granted while a person was deactivated.
3. **High:** the sweep's `deactivated` outcome was not terminal on the waitlist page.
4. **Medium:** `ListUsers` was used for the enabled check.
5. **Medium:** the repeat-deactivate rule was not stated.

The review found no other table that points at `organisation`, and `pa_ops` can already
read `task` and `project` for the counts.

## Risk the owner accepts by ruling B

Offboarding removed a person from their organisation at once. Deactivation keeps the
organisation, so an access token issued **before** the deactivation can still read the
organisation's shared work until it expires (up to 60 minutes). It cannot sign in again or
renew. Offboarding already accepted the same window for the person's own work (ADR 0045).
If this is not acceptable, the follow-up is a `deactivated_at IS NULL` check where the
public API loads the caller. Not in this slice.

## Out of scope

- Moving a person's tasks to another owner, which is deferred ownership transfer.
- Deleting a Cognito account.
- Renaming an organisation.
- A deactivated person's quotas or cohorts.
- Production config.

## Approval gates (all in this contract)

- Schema: B1.
- Database grant: B1.
- Auth and IAM: B10.
- A public interface removed: B8 and B9 (offboard).

## Rollback

- Redeploy the previous image.
- Downgrade to `e8f6a4b3c1d0` with both services stopped. People deactivated by then stay
  disabled in Cognito. Turn them back on with `aws cognito-idp admin-enable-user`.
- Drop the IAM action by redeploying the previous stack.

## Checks

- Unit and database tests for B2 to B5 and B7, run as the real `pa_ops` login:
  deactivate, reactivate, re-add, approve refused, sweep skipped, and delete refused or
  done.
- Frontend tests for B6 and the organisation dialog.
- `make verify` green.
- The owner reviews the pages locally (`make` mock or dev) before push.
- After merge, on staging:
  1. Deactivate a test account; its sign-in says disabled.
  2. Reactivate it; sign-in works.
  3. Re-add a deactivated address; sign-in works.
  4. Delete an empty organisation.

## Build order

1. Migration and the `pa_ops` permission test.
2. Commands and their tests.
3. Routes, contract models and OpenAPI.
4. Command line.
5. IAM.
6. Pages.
7. Docs.
8. `make verify`.
