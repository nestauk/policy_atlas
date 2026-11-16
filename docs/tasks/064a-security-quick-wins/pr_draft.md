# Task 064a: security quick wins

## What / why

First slice of the security hardening programme (`docs/tasks/064-security-hardening/programme.md`),
from the 2026-10-19 review. Seventeen small fixes, one per finding. Task folder:
`docs/tasks/064a-security-quick-wins/`. Decision record: `docs/adr/0045-per-user-run-cap-task-quota-offboarding.md`.

1. **Q1** Error logs no longer print frame locals, so user text and secrets stay out of CloudWatch.
2. **Q2** A duplicate waitlist email gets the same success reply as a new one.
3. **Q3** Run failures show the user only the error class name, unless it is one of our errors or carries a string reason code.
4. **Q4** The load balancer checks `/healthz` (process alive) instead of the database-backed endpoint; the deploy script checks `/readyz` once after each rollout.
5. **Q5** HTTP redirects to HTTPS.
6. **Q6** Minimum password length 8 to 12.
7. **Q7** At most 3 running runs per user, counted at all three start surfaces.
8. **Q8** At most 50 tasks per user per rolling year, administrators exempt; `/me` reports the count and a banner shows the limit.
9. **Q9** The screening query reads one task's rows (task-first partition key plus a matching index, built without blocking): 37 ms to 2 ms.
10. **Q10** `user offboard` disables the Cognito login, signs out everywhere, de-enrols and switches off public links.
11. **Q11** uvicorn keeps idle connections longer than the load balancer, drops the server header, and trusts proxy headers only from the VPC range.
12. **Q12** Cognito user pool deletion protection.
13. **Q13** Load balancer and CloudFront pinned to current TLS policies.
14. **Q14** A run that crashes between steps is marked interrupted instead of blocking the task forever.
15. **Q15** `confirm_expired` returns 409 instead of 500.
16. **Q16** Cognito signing keys are fetched at most once per 30 s whatever key id a token names; old keys are kept when a fetch fails.
17. **Q17** Production database backups kept 35 days (staging stays 7).

Also: `make audit` is green again. `opentelemetry-api` 1.45.2 and `tornado` 6.6.1 close two
advisories that were red on `dev` (lock file only).

## Proof it works

`docs/tasks/064a-security-quick-wins/verification.md`.

- `make verify` passes on the final tree (run 3). The build's earlier green claim was not
  reproducible; two tests were red at HEAD and are fixed. Recorded as a finding.
- One test per problem (verification.md § Checks beyond the build).
- Q9 `EXPLAIN ANALYZE`: sequential scan of 39,682 rows became an index scan of 1,221 rows, same
  51 results; re-run through the real query in the review.
- Staging live checks still to run after deploy (contract § Acceptance checks). Pre-deploy
  per-user task count in `infra/DEPLOYMENT.md` § 4.

## Risk tier

Tier 4: one migration (index only, `CONCURRENTLY`), production configuration, auth-adjacent
behaviour (JWKS refresh, admin exemption as a fifth `is_admin` reader, first ops command writing
to Cognito), public interface (three 409 codes added, one removed, `MeOut.task_quota`).

## AI role

The agent wrote the contract, rubric, plan and ADR under the owner's approval gates, built all
seven phases through delegated executors, and ran the review stack in a fresh conversation. The
owner ruled on continuation staying uncapped, users already over the quota, the rolling window,
removing `already_registered`, and deferring the CloudWatch secret search.

## Review focus

- Q7: the three admission sites count rows plus reservations under the dispatch lock, keyed on the task owner.
- Q8: `create_task` is the only creation path; `_is_admin` is the fifth named reader.
- Q10: the four resolution cases each report what they did; Cognito failures leave the database untouched.
- Q16: the lock across the fetch, old keys on failure, the slot freed when there are no keys at all.

## Reviews run

Findings in `verification.md` § Review findings.

- [x] Contract verifier (pinned Opus, read-only)
- [x] `/code-review` (medium)
- [x] `/security-review` (no finding above the bar)
- [x] Adversarial review (Codex, read-only)
- [x] `/simplify` (folded into `/code-review`'s cleanup angles, justification recorded)

Fixed from the review stack:

- Offboarding a row whose Cognito account is already gone now runs the database half.
- A theory-of-change check releases its reservation once its row exists (it held two of three slots).
- A key set with no usable key keeps the old keys; a failed first fetch does not hold the 30 s slot.
- The Q3 `reason` rule accepts string codes only.
- `admit_and_mint` fails loudly without `user_cap`.
- Three tests repaired, the Q14 test strengthened, two cap cases added, IAM and spec wording corrected.

## Known gaps & deferred seams

`docs/deferred.md` § Security quick wins. Owner items after merge: the staging live checks and
the CloudWatch secret search (H-06 step 4, query in `infra/DEPLOYMENT.md`).

## Public safety

- [x] No secrets, credentials, or real/acquired source text in the diff or evidence.
- [x] Logs / traces / screenshots are public-safe (the `EXPLAIN` output is from the local development database).
- [x] No approval-gated change snuck in unapproved: the migration, configuration keys, infrastructure settings, container command, conflict codes and `MeOut.task_quota` are the contract's approved list.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
