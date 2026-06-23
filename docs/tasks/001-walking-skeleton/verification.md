# Verification: 001-walking-skeleton

Evidence for this slice. No "done" without this (or the same in the PR). Keep it public-safe — no
secrets, raw source text, credentials or unredacted traces. **Blank template — fill on completion.**

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | _pass / fail / stub_ | |
| `make typecheck` | _pass / fail / stub_ | |
| `make lint` | _pass / fail / stub_ | |
| `make build` | _pass / fail / stub_ | |
| `make verify` | _pass / fail / stub_ | should be green once the Makefile is wired |

`stub` = target still red pre-scaffold (expected before wiring); say what you ran instead.

## Checks beyond the build

- **Deterministic tests** — record which ran and the result:
  - [ ] schema validation
  - [ ] event-log append / read-back
  - [ ] plan → config compile + invalid-config-is-caught
  - [ ] content-hash stability
  - [ ] `produce-grounded-block` quote-presence **pass**
  - [ ] `produce-grounded-block` fabricated-quote **hard-fail**
  - [ ] run record created, reaches `succeeded`/`failed` deterministically, and reads back
- **AI evals** — _none this slice._
- **Manual / end-to-end thread** — exact command: _`<paste command here>`_. Record the persisted
  artefact / block / unit / annotation IDs and the event-log entries appended:
  - persisted IDs: _…_
  - event-log entries: _…_

## Diff summary

_What changed and why, in one short read._

## Intent & assumptions

_The spine walked once; seams stubbed. Assumptions made about the gated choices (deps, schema,
migration tool, command surface) — and which approval each rests on._

## Known unverified items

_…_

## Public safety

_Confirm: synthetic fixtures only (no real uploaded/acquired source text); no credentials; no
Policy Atlas runtime egress occurred (stub provider; toolchain install traffic such as `uv sync`
is not runtime egress); no traces to redact this slice._

## Deferred work

_Seams left open → [docs/deferred.md](../../deferred.md). Note anything newly deferred here._
