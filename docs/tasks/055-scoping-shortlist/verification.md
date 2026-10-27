# Verification: 055-scoping-shortlist

Evidence for the shortlist slice (contract, rubric and plan in this folder). Public-safe: counts,
option names and quoted reasons only; traces, read-backs and drive scripts stay in the gitignored
`evidence/` folder.

## Build-open baseline (Phase 0)

_To be filled._

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (step-6 exit) | _pending_ | |

## Phase commits

| Phase | Commit | Gate |
|---|---|---|

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
