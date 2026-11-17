# Verification: 065-accounts

Evidence for the accounts programme (steps A, B, C). Build opened 2026-11-17 in the
worktree on `task/065-accounts`; the build and the review stack run in the same session by
the owner's decision (2026-11-17), with the review lanes as fresh agents. Public-safe: no
address ranges, passwords, email addresses or account ids.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline) | pass | 2026-11-17, after rebasing onto 064a head `1182bb11` (the first run failed on `test_healthz_is_async_so_it_needs_no_pool_thread`, which 064a fixed in `2cd648e5`; the worktree has no `backend/.env`). 4829 passed, 1 skipped; infra, drift-check and frontend-verify green. |
| `make verify` (step-6 exit) | pending | |
| `make openapi-sync && make drift-check` | pending | |
| `make -C infra test` | pending | |
| `make deploy-build-guard-test` | pending | |
| `aws sesv2 get-account` (both profiles) | blocked | SSO tokens expired on 2026-11-17; the owner signs in and the build re-runs it. Both accounts had production access on 2026-11-16 (contract fact 1). |

## Checks beyond the build

- **Deterministic tests** — filled per phase below.
- **AI evals** — none; the slice runs no inference.
- **Manual / browser / API** — the staging checks below.

## Staging live checks (contract § Acceptance; Phase 11, with the owner)

| # | Check | When | Result |
|---|---|---|---|
| 1 | Ops-page "create person" sends an invitation from `no-reply@v3.policyatlas.uk`, DKIM pass, person signs in | | pending |
| 2 | Resend sends again; a second resend within the hour is 429 | | pending |
| 3 | A `nesta.org.uk` request gets an invitation within two minutes and shows "invited"; an unlisted address is a plain row with the same form response | | pending |
| 4 | `https://ops.v3.policyatlas.uk` refused from a non-allowlisted address | | pending |
| 5 | Non-ops signed-in person sees "does not have the ops role"; 403 on every ops route; `/api/v1/me` on the ops host is 404; `https://v3.policyatlas.uk/ops` is the public not-found page; public bundle has no ops code | | pending |
| 6 | Deployed task-role policies: no `cognito-idp` on the API's; the five on the ops service's | | pending |
| 7 | Each action above has an `ops_action` row | | pending |
| 8 | Task quota 0 hides the quota band; quota 1 refuses the second task with `task_quota` | | pending |
| 9 | Full-chain smoke: a normal task run completes | | pending |
| 10 | Each rollback (A, B, C) exercised once | | pending |
| 11 | As `pa_ops`: `DELETE FROM app_user` and `SELECT FROM capability_run` refused | | pending |

## End-to-end command

Pending.

## Diff summary

Pending; filled at step 6.

## Review findings

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review** (Tier 4):
- **`/simplify`:**

## Rubric status

Pending.

## Intent & assumptions

## Known unverified items

## Public safety

## Review handoff (step-7/8 inputs)

- **Knowledge candidates:**

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md).
