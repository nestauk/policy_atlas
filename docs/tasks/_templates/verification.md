# Verification: <task-id>

Evidence for one slice. Copy into `docs/tasks/<task-id>/`. No "done" without this (or the same in the PR).
Keep it public-safe — no secrets, raw source text, credentials or unredacted traces.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass/fail/stub | |
| `make typecheck` | pass/fail/stub | |
| `make lint` | pass/fail/stub | |
| `make build` | pass/fail/stub | |

`stub` = target still red pre-scaffold (expected); say what you ran instead.

## Checks beyond the build

- **Deterministic tests** — schema validation, event-log writes, plan→config compile,
  quote-presence, idempotency, adapter behaviour. Which ran, result.
- **AI evals** (if any) — dataset, scorer, threshold, owner; visibility vs merge-blocking.
- **Manual / browser / API** — what was exercised and observed.

## Diff summary

What changed and why, in one short read. Don't make the reviewer reconstruct intent from the diff.

## Intent & assumptions

## Known unverified items

## Public safety

Logs, screenshots, traces, prompts, links — safe to publish? Any uploaded/acquired source text
that must stay out of evidence?

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md).
