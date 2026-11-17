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
| `make -C infra test` | pass | 2026-11-17 (Phase 7): 133 passed. |
| `make deploy-build-guard-test` | pass | 2026-11-17 (Phase 9): the build guard, the migration waiter and the new deploy-order harness. |
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

Pending (step 6).

## Build notes (filled per phase)

- **Executor routing.** Codex ran Phases 1-2, 3, 4, 5, 6, 7, 9 and 10 from the plan's briefs; its sandbox cannot reach Postgres or Docker, so every database-backed test was run by the lead, and the database-backed tests of Phases 4 and 6 were written by Claude agents with database access (a deviation from the plan's `codex` marks, justified by the sandbox). The frontend (Phase 8) went to the `frontend-designer` agent as planned.
- **Phase 3 gate.** The first full run failed on 26 tests, all cascading from one cause: the 064a index test stamps the version back without downgrading the new revision, so a worker's database kept 065's objects under an older stamp. The test now steps down to its own revision first. Table counts moved from 52 to 54.
- **Phase 4 deviation (minor, flagged).** The resolver keeps the owner's 064a ruling that administrators are exempt from the run cap as well as the task quota (contract § Terms names only the task quota; the 064a review of 2026-11-16 added the run cap). `tests/api/test_runs_router.py::test_an_administrator_has_no_run_cap` still holds.
- **Phase 7.** `docker build backend/` succeeded without `backend/ops-ui/` and, with a stub bundle present, the image listed `/app/ops-ui/index.html` and `/app/ops-ui/assets/app-abc.js` (2026-11-17). The plan's image test is a text pin on the Dockerfile; the live build is this record.
- **Phase 9.** The deploy script skips the ops bundle build on a bootstrap (no OIDC exports exist before the first deploy) and builds it on every update.

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
