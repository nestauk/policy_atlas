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

## Plan-time probe evidence (2026-07-12, lead; owner authorized the Overton key)

**OpenAlex (keyless, 4 calls):** `authorships.countries` filter caps at 100 values —
131 codes → HTTP 400 "Maximum number of values exceeded … Decrease values to 100 or
below"; 100 codes → 200, total 38,370,301. Native
`authorships.institutions.is_global_south:true` → 200, total 40,827,452
(magnitude-consistent with the ~100-country hand list).

**Overton (6 calls, keyword mode `query=climate` so totals are uncapped; `pp=1`):**
`source_country=France` → 42,183 · `Germany` → 42,370 ·
`France,Germany` → **0, no error** · `France|Germany` → **0, no error** ·
`source_country[]=France&source_country[]=Germany` → **0, no error** ·
`source_country=France&source_country=Germany` (repeated) → **42,370 =
last-value-wins, silent discard**. Conclusion: `source_country` is single-valued;
every multi-value idiom fails silently (the 015-recorded silent-zero hazard shape).
Feeds plan § Gate decisions item 5.

## Gate decisions (owner, 2026-07-12 — at plan approval; rubric item 9)

1. Coverage stop-grain CHECK migration: **APPROVED** as scoped (one-line widening +
   down-migration).
2. `is_retracted` at screening: **distinct excluded status** (e.g.
   `excluded_retracted`) riding the same migration — visible, attributed, never
   conflated with a relevance verdict; read paths updated.
3. Screen-stage rename persisted vocabulary: **one-time data migration** (rows exist
   only in dev/test DBs pre-launch; no permanent read-side alias).
4. `pytest-socket` dev dependency: **APPROVED**.
5. Tier-2 Overton handling: **post-filter + deeper pagination APPROVED** (rank-
   preserving, membership-enforcing, exclusions on coverage/provenance). Per-country
   fan-out REJECTED (covert budget stratification — owner reasoning recorded in
   plan § 5); pure asymmetry REJECTED (screen does not enforce membership);
   `is_global_south` adoption DROPPED (owner de-scope: "developing" is a rare ask
   for target users; probe evidence parked at the filter-vocabulary seam).
