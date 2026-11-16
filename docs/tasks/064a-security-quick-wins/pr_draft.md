# Task 064a: security quick wins

## What / why

Task: `docs/tasks/064a-security-quick-wins/` (contract revision 2, rubric, plan draft 2,
verification). Decision record: `docs/adr/0045-per-user-run-cap-task-quota-offboarding.md`.
First slice of the security hardening programme (`docs/tasks/064-security-hardening/programme.md`),
built from the 2026-10-19 project review.

Seventeen small, local fixes, one per review finding:

1. **Q1 Stop leaking secrets into logs.** Error logs no longer print the local variables of every code frame, so user text and secrets stop reaching CloudWatch.
2. **Q2 Hide who is on the waitlist.** Signing up with an email that is already on the list gives the same success reply as a new one, so nobody can probe which addresses are registered.
3. **Q3 Scrub error messages shown to users.** When a run fails, the browser sees only the error's class name unless it is one of our own errors or one carrying a structured reason code, while the full detail goes to the server log.
4. **Q4 Make the health check lighter.** The load balancer checks a simple "is the process alive" endpoint instead of one that needs the database, so a short database hiccup no longer kills the container and every run on it. The deploy script checks the database-backed endpoint once after each rollout.
5. **Q5 Force HTTPS.** Anyone who types `http://` is redirected to the encrypted site.
6. **Q6 Longer passwords.** The minimum password length goes from 8 to 12 characters for passwords set from now on.
7. **Q7 Cap runs per user.** One person's tasks can hold at most 3 running runs at a time, counted the same way as the global cap at all three start surfaces, so one user cannot occupy all 10 server slots.
8. **Q8 Cap tasks per user.** One person can create at most 50 tasks in any 365 days, administrators excepted; `/me` reports the count and a banner tells them when they reach the limit.
9. **Q9 Speed up the screening query.** The query that ranked every task's screening rows on every call now reads one task's rows (task first in the window's partition key, plus a matching index built without blocking the app): 37 ms to 2 ms on the development database.
10. **Q10 Real offboarding command.** `user offboard` disables the person's Cognito login, signs them out everywhere, de-enrols them and switches off the public links on their tasks. Projects shared with the organisation are left as they are.
11. **Q11 Fix dropped requests and trust the right proxy.** The web server keeps idle connections open longer than the load balancer does, stops announcing its name, and reads the real client address only from the load balancer's address range.
12. **Q12 Protect the user pool.** The Cognito user pool gets deletion protection.
13. **Q13 Pin modern TLS.** The load balancer listener and CloudFront are pinned to the current recommended TLS policies.
14. **Q14 Clean up after a crashed run.** A run that fails between steps is marked "interrupted" instead of staying "running" forever and blocking the task.
15. **Q15 Fix a hidden 500.** The `confirm_expired` error joins the known conflict list, so the user gets a 409 message instead of a server error.
16. **Q16 Stop token-header abuse of the key cache.** The API fetches Cognito's signing keys at most once every 30 seconds whatever key id a token names, keeps the old keys if a fetch fails, and does the work off the event loop.
17. **Q17 Longer backups in production.** Production database backups are kept for 35 days; staging stays at 7.

## Proof it works

Evidence: `docs/tasks/064a-security-quick-wins/verification.md`.

- **`make verify`:** pass on the final tree (run 3 in verification.md § Commands run; the build's
  earlier green claims were not reproducible and are recorded as a finding).
- **Tests, one per problem:** listed in verification.md § Checks beyond the build. New files:
  `test_logging.py`, `test_jwks_provider.py`, `test_migration_064a_ssr_index.py`,
  `test_screen_partition_parity.py`, `test_dockerfile_lines.py`, `QuotaBanner.test.tsx`.
- **Q9 `EXPLAIN ANALYZE`:** sequential scan of 39,682 rows and an on-disk sort (37 ms) became a
  bitmap index scan of 1,221 rows and an in-memory sort (2 ms), same 51 results; re-run through
  the real query construct in the review stack.
- **Staging live checks:** not yet run; they need the deploy. The list is in the contract
  § Acceptance checks and verification.md § End-to-end command, with the pre-deploy per-user
  task count in `infra/DEPLOYMENT.md` § 4.

## Risk tier

Tier 4 — one migration (index only, built `CONCURRENTLY`), production configuration (seven
infrastructure settings, two container keys, one database key, the container command),
auth-adjacent behaviour (JWKS refresh, the administrator exemption as a fifth named reader of
`is_admin`, the first ops command that writes to Cognito), and a public-interface change
(three 409 codes added, one removed, `MeOut.task_quota`).

## AI role

The agent wrote the contract, rubric, plan and ADR under the owner's approval gates (contract
revision 2 and plan draft 2 approved 2026-11-16 after Codex and Opus adversarial reviews);
built all seven phases through delegated executors (`fast-worker`, `deep-reasoner`,
`frontend-designer`) with the lead designing the seams; ran the review stack in a fresh
conversation and adjudicated its findings. The owner ruled on: continuation staying uncapped,
users already over the quota (banner and refusal only), the rolling window, removing
`already_registered` unannounced, and deferring the CloudWatch secret search to after the slice.

## Review focus

- Q7: the three admission sites (`create_run`, `start_toc_check`, `admit_and_mint`) count rows
  plus reservations under the dispatch lock, keyed on the task's owner; `start_toc_check` now
  releases its reservation once the row exists (review stack).
- Q8: `create_task` is the only API creation path; `_is_admin` is the fifth named reader
  (ADR 0045 amends ADR 0033).
- Q9: the parity test is the proof that the row set is unchanged; the plan is the benefit.
- Q10: the four resolution cases (enrolled, de-enrolled, no row, no Cognito account) each
  report what they did; Cognito failures leave the database untouched.
- Q16: the lock across the fetch, the old keys on failure, a key set with no usable key, and
  the slot given back when there are no keys at all.
- Q14: only the id this dispatch minted is marked.

## Reviews run

Findings recorded in `verification.md` § Review findings.

- [x] Contract verifier (pinned Opus, read-only)
- [x] `/code-review` (medium; the Claude half of the heterogeneous pair)
- [x] `/security-review` (no finding above the bar)
- [x] Adversarial review (Codex, read-only; six major, one minor, all adjudicated)
- [x] `/simplify` (folded into `/code-review`'s cleanup angles, justification recorded)

Adopted from the stack: offboarding a row whose Cognito account is already gone now runs the
database half; a theory-of-change check releases its reservation once its row exists; a key set
with no usable key keeps the old keys and a failed first fetch does not hold the 30 s slot; the
Q3 `reason` rule accepts string codes only; `admit_and_mint` fails loudly without `user_cap`;
three tests repaired (two red at HEAD, one that had lost its proof); the Q14 test strengthened;
two missing cap cases added; the IAM and spec wording corrected.

## Known gaps & deferred seams

`docs/deferred.md` § Security quick wins: spend caps; a quota display beyond the banner; a
per-user allowance above 50; the 60-minute access-token window after offboarding; resuming after
a check-in is uncapped; request body size limits (H-02); library text inside steering
rejections; `AdminUserGlobalSignOut` on a disabled account (confirmed on staging); serving a
known key while a refresh runs; `create_run`'s reservation drop after its 10-second wait; the
`policy_atlas.` namespace rule and `SearchTransportError`; the pre-064a drift of the 409 code
lists; the `user_capacity` sentence for a collaborator; the quota's two clocks.

Owner items after merge: the staging live checks; the CloudWatch search for `locals`,
`api_key`, `password` and `dbadmin` in both environments (H-06 step 4, deferred by the owner to
after the slice; the query is in `infra/DEPLOYMENT.md`); `make audit`'s two advisories in
dependencies this slice does not touch (`opentelemetry-api`, `tornado`; red on `dev` too).

## Public safety

- [x] No secrets, credentials, or real/acquired source text in the diff or evidence (the Q1 test
  uses a planted fake value).
- [x] Logs / traces / screenshots are public-safe (the `EXPLAIN` output is from the local
  development database).
- [x] No approval-gated change snuck in unapproved: the migration, the configuration keys, the
  infrastructure settings, the container command, the conflict codes and `MeOut.task_quota` are
  the contract's list, approved 2026-11-16 (rubric item 3).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
