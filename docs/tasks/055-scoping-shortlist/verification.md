# Verification: 055-scoping-shortlist

Evidence for the shortlist slice (contract, rubric and plan in this folder). Public-safe: counts,
option names and quoted reasons only; traces, read-backs and drive scripts stay in the gitignored
`evidence/` folder.

## Build-open baseline (Phase 0)

Branch head at open: `e3e60392` (ADR 0041 committed at step 4). `make verify` on 2026-10-27:
`4 failed, 3588 passed` in the backend suite.

- Three failures were `test_every_depth_runs_the_same_pass_and_cuts_at_its_caps[rapid|standard|deep]`
  (Evidence search sourcing). Pre-existing on this machine: the same three fail on the untouched
  `dev` head `eedf9ef9` in a second worktree, while CI's `verify` on that commit is green. Cause:
  the fake backends record calls in thread order and the test asserts plan order over eight
  threads. Fixed in the test only (one thread for that test), commit `9f77bf82`. No file under
  `evidence_search/` source changed.
- One failure, `test_an_intent_record_s_purpose_is_closed`, came from the Phase 1 delegate's
  in-flight schema change (the purpose check now admits `shortlist`) landing while the baseline
  ran; the test was updated in Phase 1.
- Docker Desktop's engine was wedged at open (every `docker` call hung); recovered with
  `docker desktop restart` before the baseline could run.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (step-6 exit) | _pending_ | |

## Phase commits

| Phase | Commit | Gate |
|---|---|---|
| 0 | `9f77bf82` | baseline (above) |
| 1 | `83fa1bfd` | full `make verify` on snapshot `8543cfa0`: 3608 backend passed, 882 frontend passed, drift-check OK, prompt-guard OK |
| 2a + 3a + 5a (prompts) | `d1e4cd96` | shares the Phase 2 gate tree (snapshot `15620802`); the three lead-authored prompts were written before the plumbing was delegated, as the plan requires, and committed together with their re-pin |
| 2b | `e771c16e` | `verify-fast` + `prompt-guard` + `openapi-sync` (clean) + `drift-check` + `frontend-verify` on snapshot `15620802`: 3630 backend passed, frontend green |

## Checks beyond the build

### Deterministic tests

_To be filled per phase._

### The staged check (item 13)

**The seven stored tasks** (team test questions, not user data; contract A30). Named here before
the first prompt round, as the plan requires:

| Slug | Role | Included options |
|---|---|---:|
| neet | tuning | 37 |
| heat-pumps | tuning | 43 |
| caregiving | tuning | 22 |
| obesity | tuning | 25 |
| refugees | check | 23 |
| obesity-deprived | check | 24 |
| social-cohesion | check | 28 |

Task ids are in `evidence/tasks.json` (gitignored).

_Measures M1–M7: to be filled._

## End-to-end command

_To be filled._

## Diff summary

_To be filled._

## Review findings

Added after the review stack (step 7).

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review:**
- **`/simplify`:**

## Rubric status

Filled by the review conversation.

## Intent & assumptions

## Known unverified items

## Public safety

## Review handoff (step-7/8 inputs)

- **Knowledge candidates:**
  - Docker Desktop's engine stopped answering after six days up; every `docker` call (and so
    `make verify`) hung with no error. `docker desktop restart` from the shell recovered it
    without the GUI; a scripted quit-and-reopen of the app was refused by the permission mode.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) (to be written in Phase 8).
