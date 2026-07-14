# Verification: 022-synthesis-refinement

> **Status: IN PROGRESS** — being filled during the build (step 6 completes it).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, build open) | pass | 1273 passed · mypy 131 files · ruff · build (2026-07-14) |
| `make verify-fast` (Phase A exit) | pass | 1230 passed · mypy 134 · ruff |
| `make verify` (Phase B exit) | pass | after 2 lead test fixes (below) |
| `make verify` (Phases R+C shared gate) | pass | after 3 lead test fixes (below) |
| `make verify-fast` (Phase E exit) | pass | after 2 stale-fixture re-pins (below) |
| `make verify` (step-6 exit) | _pending_ | |

## Phase log + executor provenance (family-flip input)

- **Phase 0**: baseline green. Lead.
- **Phase A** (engine + characterise refactor): Codex `task-mrk1ywew-txc8o6` (1h11m).
  Lead review: clean; no fixes needed. `clustering_engine.py` + characterise
  adapter; prompts byte-identical (pin tests); equivalence fixture test.
- **Phase B** (migration + UNION view + consumer rewrite + shape-compat):
  Codex `task-mrk4nonl-s267v3` (19m). Lead fixes: one missed re-pin
  (`test_group.py` determinism still asserting the dropped `facet` column);
  codex's new e2e test lacked the characterisation chain
  (`selection_provenance.characterisation_run_id`) and asserted on
  `blocks[0]` (the key-findings block) instead of the section block.
- **Phase R** (ICF `context_label` rider): lead-authored all prompt-bearing
  text (icf_v2 field description, extract_icf_v2 rule block + example
  carriage incl. one filled-label example finding, extract_icf_vetter_v2
  `paraphrased_label` class) + minimal green-keeping plumbing
  (quote_verify field rules, extract.py insert + judge payload); Codex
  `task-mrk68sfr-6t8kff` (2h8m) did test carriage + fingerprint/memo/vetter
  tests + one sanctioned deviation (ICF stub legacy-record defaulting in
  extraction_backend.py, mirroring `_with_iof_defaults`).
  **Executor-mark deviation (logged):** plan marked records/plumbing `codex`;
  the lead did the small product-code plumbing directly because it shares
  files with lead-only prompt surfaces (sequential handoffs on one small file
  set cost more than the plumbing) — tests stayed delegated.
- **Phase C** (multi-facet fan-out + orchestration): Codex
  `task-mrk63zgx-198n54` (2h32m). Lead fixes (all test-authoring bugs, no
  product changes): stale one-call `call_count` expectation (two-stage happy
  path = 2 calls), an order-sensitive UUID list comparison, a fixture whose
  two claims shared the stub's first-token bucket.
- **Phase D** (group prompts + replay): lead-only. `group_clustering.py`
  (`group_cluster_v1` discovery+assignment pair, per-projection variants),
  live factory wired into skeleton + orchestrate; replay evidence below.
- **Phase E** (facet-qualified ids + consumption): Codex
  `task-mrkced6o-rj3lav` (17m). Lead: `query_findings` `group_id`
  description text (qualified-form rule; rides the v7 bump) + two stale
  old-form fixtures re-pinned (`test_synthesis_backend`,
  `test_synthesise_pure`).
- **Phase F0**: lead — `f0-writer-layout.md` (v7 message/prefix layout spec).
- **Phase F1–F5 / G / H**: _pending_.

## Migration evidence (up/down + old-row readability)

- Deterministic suite: `tests/test_synthesis_refinement_migration.py`
  (up transform incl. persisted-consumer rewrite, downgrade round-trip,
  downgrade REFUSAL on multi-facet rows, UNION view projection) — green.
- **Real-data migration** (dev DB `policy_atlas`, 2026-07-14): 37
  `grouping_result` rows + 23 grouping-referencing `synthesis_result` rows
  migrated by `alembic upgrade head` (2f9d7e1c4a6b → 7a4d9c2e1f6b);
  post-checks: every row facet-keyed with `facets` provenance;
  `intervention:g01`-form ids minted; `finding_reference_union` serves 3569
  findings. Pre-migration row snapshots retained locally (scratchpad CSVs,
  not committed — raw source-derived text).

## AI behaviour — replay evidence (eval-blind; shape + scale only)

**Phase D — `group_cluster_v1`** (refine-replay loop; round 1 ACCEPTED, no
refine rounds — no failure signal; ≤3-round bound unused). Tally: **9
component replays** (shared ≤35 budget; Phases R probes + G to add).
Substrate: dev-DB extraction run `232d6afb-5db9-40a9-8714-bc9c362930ee`
(021 both-profiles corpus: 333 findings, 184 distinct intervention values,
203 ICF claims — the exact previously-failing scale).

| Arm | Units | Ceiling | Groups | Residual | Singletons | Repairs | Rejections |
|---|---:|---:|---:|---:|---:|---:|---|
| 1: intervention full scale | 184 | 37 | 18 | 21 | 0 | 1 | "5 unknown labels" (repaired) |
| 2: intervention 60, context ON | 60 | 12 | 12 | 12 | 0 | 0 | — |
| 2: intervention 60, context OFF | 60 | 12 | 11 | 8 | 0 | 0 | — |
| 3: intervention 30 | 30 | 6 | 5 | 2 | 0 | 0 | — |
| 4: barrier_theme | 46 | 10 | 6 | 0 | 0 | 1 | "omitted 1 id" (repaired) |
| 4: enabler_theme | 32 | 7 | 7 | 3 | 1 | 1 | "1 unknown label" (repaired) |
| 4: mechanism_theme | 31 | 7 | 7 | 1 | 1 | 0 | — |
| 4: pooled trio | 109 | 22 | 18 | 2 | 1 | 0 | — |
| 4: ALL 203 claims (scale probe) | 203 | 41 | 23 | 1 | 1 | 0 | — |

- **Scale-limit failure mode closed** (knowledge doc): at 184 values the old
  `group_facet_v1` emitted duplicate ids 4/4 and degraded to all-ungrouped;
  the two-stage shape partitions healthily with zero duplicate-id rejections
  and honest counted residuals. Budgets respected on every arm.
- **Granularity vs the over-fragmentation baseline** (rubric 22): old rows
  ran e.g. 25 values → 12 groups, 101 → 20, 139 → 31; new: 30 → 5, 60 →
  11–12, 184 → 18, all with 0–1 singletons and no forced lower bound (arm 3
  discovered 5 < ceiling 6).
- **Context payload pin-or-revert**: PIN (ON stays default). ON vs OFF at 60
  values: same label quality, no snippet-topic anchoring in ON labels;
  ON split finer (tariffs vs running costs vs finance) with a larger honest
  residual (12 vs 8) — no revert trigger. Full-scale discovery runs
  context-free by the 120-unit gate (dilution guard); assignment always
  carries context.
- **Claim-theme scale**: healthy at every type size and at the pooled
  203-claim probe (23 grounded groups, residual 1, no repairs) with payloads
  enabled.

## End-to-end command

_pending — Phase H live checks._

## Diff summary

_pending — completed at step-6 exit._

Flagged interpretation resolutions (minor, within contract vocabulary — the
007 None-vs-absent precedent):
- **§ Payload shapes ambiguity**: the plan's `groups: {"<facet>": [...]}`
  shorthand vs "residuals inside groups[facet]'s sibling keys" was resolved
  as `groups[facet] = {"groups": [...], "ungrouped": {...}, "no_value":
  {...}}` — facet identity the outer key, residual keys siblings of the
  inner groups array.
- **Migrated flags shape**: old rows' flags wrap as `{facet: <legacy list>}`
  per the plan's "wrap each JSONB column's current flat value" line; Phase C
  producers write the per-facet outcome objects for new rows. Readers
  tolerate both under the facet key.

Sanctioned test-surface changes (rubric 5 justifications):
- Phase B/C re-pinned persisted-shape assertions to the facet-keyed,
  facet-qualified-id shape (the approved schema change).
- `tests/test_group_judgment.py` dropped 8 tests that exercised the retired
  one-call partition/repair machinery (`validate_partition`-path component
  behaviours); equivalent component-level coverage now lives in
  `test_clustering_engine.py` invariants + the new `test_group.py`
  failure-isolation/cap/zero-label/eligibility tests. No behaviour lost
  coverage; the machinery they tested is no longer reachable from group.
- Phase E re-pinned bare `g1`-form ids to qualified ids (the fail-closed
  rule is the contract's item 3).

## Known unverified items

- Old `facet_grouping.py` prompt machinery (`group_facet_v1` templates +
  backends) is now unreachable from group but still present with its unit
  tests — flagged for the review-stage simplification pass (delete or keep
  decision), not silently removed mid-build.
- Group assignment fan-out runs serial (engine `max_concurrent_batches`
  defaults to 1 for group; characterise keeps 4) — acceptable at current
  batch counts (≤5 batches/facet live); wall-time rider re-measure will show
  if it matters.

## Public safety

Replay evidence above carries counts, labels and run ids only — no source
text, no credentials. Pre-migration row snapshots (raw JSONB incl. verbatim
member values) stay in the local scratchpad, NOT committed.

## Review handoff (step-7/8 inputs)

- **Knowledge candidates** (running list):
  - Two-stage open discovery + validated batch assignment closes the
    ~184-value duplicate-id capacity cliff outright (0/9 replay arms showed
    id fabrication; the old one-call shape failed 4/4) — the failure was the
    exhaustive-id-list response format, not model capacity per se.
  - The exhaustive-partition framing was also the over-fragmentation driver:
    removing the every-value-must-land pressure dropped 25-values→12-groups
    to 30→5 with no lower-bound forcing.
  - Codex parallel write jobs on one working tree are safe when file sets
    are disjoint AND briefs carry "never revert files you did not change" +
    an explicit list of the sibling job's files (R ∥ C, this build).
  - Codex-authored tests are the main defect surface (stale expectations,
    order-sensitive UUID comparisons, fixtures colliding with stub token
    rules) — product code landed clean across five deliveries; review
    attention should weight test diffs.
  - A required-key nullable wire field ripples into every explicit
    constructor including few-shot EXAMPLE_RESPONSE objects (021 lesson
    re-confirmed on icf_v2).
  - `update(...).values(selected=selected)` after mutating a list the INSERT
    already captured: test helpers that seed then patch selection rows need
    the characterisation chain too when synthesise walks provenance.

## Deferred work

_pending — Phase H sweep._
