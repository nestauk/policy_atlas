# Verification: <task-id>

Evidence for one slice. Copy into `docs/tasks/<task-id>/`. No "done" without this (or the same in the PR).
Keep it public-safe — no secrets, raw source text, credentials or unredacted traces.
Fill at verify (step 6); add **Review findings** + **Rubric status** after the review stack (step 7).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass / fail | |
| `make typecheck` | pass / fail | |
| `make lint` | pass / fail | |
| `make build` | pass / fail | |

If a check is red, say whether it's expected for this slice, a known failure, or a blocker.

## Checks beyond the build

- **Deterministic tests** — schema validation, event-log writes, plan→config compile,
  quote-presence, idempotency, adapter behaviour. Which ran, result.
- **AI evals** (if any) — dataset, scorer, threshold, owner; visibility vs merge-blocking.
- **Manual / browser / API** — what was exercised and observed.

## End-to-end command

The exact command run for the manual end-to-end thread (copy-paste, including any env).

## Diff summary

What changed and why, in one short read. Don't make the reviewer reconstruct intent from the diff.

## Review findings

Added after the review stack (step 7) — what each review caught and how it was resolved:

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review** (Tier 2+):
- **`/simplify`:**
- **`/okf validate`** (if specs/knowledge changed):

## Rubric status

Every rubric item checked, or explicitly listed as not-satisfied with reason.

## Intent & assumptions

## Known unverified items

## Public safety

Logs, screenshots, traces, prompts, links — safe to publish? Any uploaded/acquired source text
that must stay out of evidence?

## Review handoff (step-7/8 inputs)

What the review conversation needs but cannot see from the diff: adjudication items
(flagged deviations, build-flagged anomalies), executor provenance for the family flip,
diff-scoping exclusions, live-trace pointers — and:

- **Knowledge candidates** (014 retro): one bullet per durable-seeming lesson from the
  build, however raw — surprises, gotchas, invariants that held for a non-obvious reason.
  Step 8 authors `docs/knowledge/` from this list + the review findings, against the
  final code. An empty list on a non-trivial slice is a smell, not a default.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md).
