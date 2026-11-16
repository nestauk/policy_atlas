# ADR 0045 — A per-user run cap, a task quota that administrators do not have, a run id minted before dispatch, and an offboard command

- **Status:** Accepted — 2026-11-16 (Karlis Kanders, owner, task 064a plan gate).
- **Date:** 2026-11-16
- **Task:** [064a-security-quick-wins](../tasks/064a-security-quick-wins/contract.md)
  (contract revision 2 and plan draft 2 approved 2026-11-16), first slice of the
  [064 security hardening programme](../tasks/064-security-hardening/programme.md).
- **Builds on:** [ADR 0033](0033-organisation-tenancy-and-global-admin-read.md) decision 4
  (the administrator flag, its closed reader list), amended here ·
  [ADR 0037](0037-options-scoping-task-kind-links-and-baseline-gate.md) (parentless walks fence a task; option
  searches do not occupy the executor) · the 2026-10-19 project review (findings H-01,
  H-04, H-11, H-17 and M-02; the review file sits in the programme folder).

## Context

The project review found that one user can take all ten run slots (H-17), that nothing
limits how many tasks a user creates (H-04), that a run which fails between pipeline steps
stays `running` until a restart (H-11), and that removing a person from an organisation
leaves their Cognito account able to sign in (M-02). All four are small, but each one sets a
rule the rest of the code must keep, which is why they are recorded.

The admission check lives in three places today: `create_run` and `start_toc_check` in
`api/routers/runs.py`, and `admit_and_mint` in `api/longlist_start.py`. All three take the
same process lock, count running parentless executor walks against the global cap, and add
a reservation for the task before the run row exists. Resuming a paused walk after a
check-in has no capacity check: the person's decision is already committed when the resume
runs.

Task creation has one API path, `create_task`. The runtime command-line path writes rows
with no owner and is not reachable from the product.

The administrator flag has a closed list of four code-level readers, asserted by a test that
scans every module under `api/` for the name `is_admin` in any scope.

## Decisions

1. **A per-user cap on concurrent runs, counted the same way as the global cap, at the
   same three sites, under the same lock.** `runs_per_user` (3 in every environment, a
   key in `infra/pa_config.json`). The count is the user's running parentless executor
   walks, joined to the task owner, plus the user's tasks in the reservation set that will
   occupy a worker. Reservations count because the run row is written after the lock is
   released; counting rows alone admits N simultaneous starts. Refusal is
   `409 user_capacity`. The cap applies to administrators. Resuming after a check-in stays
   uncapped. The two-start window the global cap already has is accepted for the user cap
   too.

2. **A task quota per user, counted on rows, with no new table.** `task_quota_per_year`
   (50 in every environment). At `create_task`, the caller's task rows of any capability,
   archived included, with `created_at` in the last 365 days by the database clock, are
   counted; at or above the quota the request is refused with `409 task_quota`. A rolling
   window needs no scheduled reset. `GET /me` reports `used` and `limit` so the frontend can
   show a banner at the limit; a person already over the quota when the rule lands sees
   the banner and cannot create tasks, nothing else.

3. **Administrators have no task quota, and that is the first administrator behaviour
   that is not a read.** The exemption goes through the existing `_is_admin` helper, so
   the column is not read anywhere new, but `create_task` becomes the **fifth named
   entry** in the closed reader list. ADR 0033 decision 4's sentence "only four places may
   read the flag" is amended to five: the row-access helper's admin leg, the listing scope
   resolver, the `owner_email` filter gate, the `/me` projection, and task creation's quota
   exemption. The list stays closed and structurally asserted; the test's list, its
   comment block and the `_is_admin` docstring name the fifth entry. The flag still grants
   no write, and is still settable only by the ops CLI. The run cap deliberately does
   **not** exempt administrators: it protects the server, not the budget.

4. **Every start surface mints the run id before dispatch, and a failed dispatch marks only
   that id.** The queued theory-of-change path and `admit_and_mint` already did this;
   `create_run` now does too. `_dispatch_run`'s failure branch calls
   `mark_interrupted_best_effort` with the minted id and never looks a run up by task,
   because the reservation is dropped once the row exists and another surface can start a
   walk in that gap.

5. **Offboarding is a separate ops command, Cognito first.** `user offboard` disables the
   Cognito account and revokes its refresh tokens, then de-enrols the person if they are
   still enrolled or hold the administrator flag, then makes their public tasks private.
   Projects have no public-link surface; their `visibility` is tenancy and is left alone. A
   database failure after the Cognito step leaves a disabled account that a rerun
   completes. The command runs from the operator's own credentials; the public API holds no
   Cognito write permission, and the planned ops service will reuse the same function from
   its own task role. An access token already issued stays valid for up to 60 minutes, and
   an open progress stream outlives it; that window is accepted and documented.

## Alternatives considered

- **A usage table with spend per user.** Needed for spend caps, which the owner deferred
  until the task quota has run for a while. A row count needs no schema.
- **A calendar-year quota with a reset job.** More moving parts than a rolling window for
  the same effect.
- **Capping continuation after a check-in.** Would strand a decision the person already
  made. Refused.
- **Exempting administrators from the run cap too.** The cap exists to keep the single
  server responsive; an administrator's run costs the same thread.
- **A `disabled` flag checked on every request.** Would close the 60-minute window at the
  price of a database read per request. Deferred; the window is documented instead.

## Consequences

- Three new 409 codes (`user_capacity`, `task_quota`, `confirm_expired`), one removed
  (`already_registered`, task 064a Q2); `docs/specs/system/web-api.md` lists them.
- `MeOut` gains an optional `task_quota` object. Additive.
- Any future admission site must call both the global and the per-user check under the
  lock, and must mint its run id before dispatch. The three sites are the pattern.
- Any future reader of `is_admin` is a sixth entry and a new amendment, not a quiet
  addition.
- Deferred, in `docs/deferred.md`: spend caps and per-user chat and planner turn limits;
  a quota display beyond the banner; the 60-minute token window and open streams after
  offboarding; a per-user allowance above 50.

## As built (2026-11-16, task 064a build)

Three details settled during the build, within the decisions above:

1. **The run cap is checked against the task's owner, not the caller.** Decision 1
   counts walks on the tasks a person owns. The three sites therefore pass
   `task.owner_user_id` to the check, so a collaborator with write access could not lift
   an owner above the cap. Today write access is owner-only, so this changes no current
   behaviour; it fixes the identity the rule is stated in.
2. **The reader-list test is stricter.** The structural walk matched only the name
   `is_admin`, so a call to the `_is_admin` helper from another module would not have
   registered. The walk now also counts `_is_admin` calls outside `access.py`, which is
   how the fifth entry (`routers/tasks.py: create_task`) is asserted.
3. **The error sentences carry no numbers.** `user_capacity` and `task_quota` are
   server settings, so the frontend's sentences name no limit; the banner reads its
   number from `/me`. `useCreateTask` invalidates `/me` on success, so the banner appears
   on the create that reaches the limit, not on the next page load.
