# Task 064a: security quick wins

First slice of the security hardening programme (task 064). Seventeen small, local fixes
from the October 2026 project review. Contract, rubric and plan are in
`docs/tasks/064a-security-quick-wins/`; the decision record is ADR 0045.

## What changes

1. **Q1 Stop leaking secrets into logs.** Error logs no longer print the local variables of every code frame, so user text and secrets stop reaching CloudWatch.
2. **Q2 Hide who is on the waitlist.** Signing up with an email that is already on the list gives the same success reply as a new one, so nobody can probe which addresses are registered.
3. **Q3 Scrub error messages shown to users.** When a run fails, the browser sees only the error's class name unless it is one of our own errors, while the full detail goes to the server log.
4. **Q4 Make the health check lighter.** The load balancer checks a simple "is the process alive" endpoint instead of one that needs the database, so a short database hiccup no longer kills the container and every run on it.
5. **Q5 Force HTTPS.** Anyone who types `http://` is redirected to the encrypted `https://` site.
6. **Q6 Longer passwords.** The minimum password length goes from 8 to 12 characters for new passwords.
7. **Q7 Cap runs per user.** One person can hold at most 3 running runs at a time, so one user cannot occupy all 10 server slots.
8. **Q8 Cap tasks per user.** One person can create at most 50 tasks per year, admins excepted, and a banner tells them when they reach the limit.
9. **Q9 Speed up the screening query.** A database query that ranked every task's rows on every call now filters to one task first, plus a new index, so the task list stops hammering the database.
10. **Q10 Real offboarding command.** A new `user offboard` command disables the person's Cognito login, signs them out everywhere, de-enrols them and removes the public links on their tasks. Projects shared with the organisation are left as they are.
11. **Q11 Fix dropped requests and trust the right proxy.** The web server keeps connections open as long as the load balancer does, stops announcing its name, and reads the real client address only from the load balancer.
12. **Q12 Protect the user pool.** The Cognito user pool gets deletion protection, so an infrastructure change cannot accidentally replace it and lose every account.
13. **Q13 Pin modern TLS.** The load balancer and CloudFront are pinned to the current recommended TLS policy, so encryption settings cannot silently drift.
14. **Q14 Clean up after a crashed run.** A run that fails between steps is marked "interrupted" instead of staying "running" forever and blocking the task.
15. **Q15 Fix a hidden 500 error.** The `confirm_expired` error joins the known conflict list, so the user gets a clear 409 message instead of a server error.
16. **Q16 Stop token-header abuse of the key cache.** The API fetches Cognito's signing keys at most once every 30 seconds, keeps the old keys if a fetch fails, and does the work off the event loop.
17. **Q17 Longer backups in production.** Production database backups are kept for 35 days instead of 7; staging stays at 7.

## Public interface

- New 409 codes: `user_capacity`, `task_quota`, `confirm_expired`. Removed: `already_registered`.
- `GET /api/v1/me` gains an optional `task_quota: {used, limit} | null`.
- New config keys: `task_quota_per_year` and `runs_per_user` (`infra/pa_config.json`), `backup_retention_days` (`infra/db_config.json`).
- One migration: an index on `source_screening_result (task_id, evidence_scope_id, task_source_snapshot_id)`, built concurrently.

## Deploy notes

Q4, Q5, Q6, Q12, Q13 and Q17 change live infrastructure settings. Q11 changes the container
command. Before each deploy, run the per-user task count so the owner knows who will see the
quota banner. The staging checks are listed in the contract § Acceptance checks.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
