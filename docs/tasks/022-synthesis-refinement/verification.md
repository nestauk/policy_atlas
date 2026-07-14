# Verification: 022-synthesis-refinement

> **Status: step 6 complete** (2026-07-14). Review stack (steps 7–10) runs in a
> fresh conversation; § Review findings + § Rubric status land there.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, build open) | pass | 1273 passed · mypy 131 files · ruff · build (2026-07-14) |
| `make verify-fast` (Phase A exit) | pass | 1230 passed · mypy 134 · ruff |
| `make verify` (Phase B exit) | pass | after 2 lead test fixes (below) |
| `make verify` (Phases R+C shared gate) | pass | after 3 lead test fixes (below) |
| `make verify-fast` (Phase E exit) | pass | after 2 stale-fixture re-pins (below) |
| `make verify-fast` (F1/F3/F4/F5+G exits) | pass | one per phase boundary |
| `make verify` (Phase F2 exit — judge-path class) | pass | |
| `make verify` (step-6 exit) | pass | final run below |

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
- **Phase F1** (tool-return + retrieval): Codex `task-mrkdbc14-imiz30` (21m).
  Lead fix: one SimpleNamespace doc-record fixture gained the two new fields.
  NOTE: F1 shipped executor-side scope-filter validation only; the tool WIRE
  schema exposure was lead work at Phase G (by design — description text).
- **Phase F2** (repair micro-call + seed split): Codex `task-mrke6r0k-3wqvnf`
  (19m). No lead fixes at gate; one live-only bug found later (below).
- **Phase F3** (unspanned lane): **deep-reasoner** — EXECUTOR SUBSTITUTION:
  Codex ran out of workspace credits mid-Phase-F (codex-exhaustion fallback);
  F3/F5 re-routed to deep-reasoner, F4 was fast-worker per plan. Clean delivery.
- **Phase F4** (cost riders): fast-worker per plan. Clean delivery.
- **Phase F5** (steer surface): deep-reasoner (substitution as above). Clean;
  one flagged design call: `boostable` surfaces the closed VOCABULARY
  (tiers/evidence types/confidence bounds), not corpus-present values —
  unmatched boosts are already recorded non-fatally; reviewer may prefer
  corpus-present tiers (would add an appraisal read).
- **Phase G** (lead): v7 prose (dedup-reference + windowed-return reading
  rules, facet-qualified theme-id rule), scoped-search wire schema + filter
  descriptions, repair-template audit (F2's text stood), planner_v5 sweep
  (grouping_facets list, six-facet vocabulary, deep default set), the
  runnable-v6 harness (`synthesis_prompts_v6.py` + `prompt_variant="v6"`).
- **Phase H** (lead; plan marked fast-worker for record drafts — done lead
  directly, the entries needed the build context anyway): spec flow-back
  (data-model, components §8/§9), deferred.md sweep (all agenda outcomes +
  discharges + new seams), ADR re-check, hygiene audit, live checks below.

## Live-check bug fixes (found by the live runs, not the suites)

Three product bugs only reachable live — each fixed lead-side with a test:

1. **Judge extra-verdict echo** (17(i) interaction): with the all-types span
   map, the live judge emits verdicts for span-map-only claim ids it has no
   verdict duty for → `judge_coverage_invalid`. Fix: drop-and-count extra
   verdicts for span-only ids (logged `judge_extra_verdicts_dropped`);
   coverage of the judged set itself stays exact. Test:
   `test_judge_extra_verdicts_for_span_only_ids_are_dropped_not_fatal`.
2. **Repair wire projection**: judge-failing claims carry ENRICHED citation
   records (resolved `cited_chunk_record_id`, spans, match status) that the
   strict `ClaimWire` re-validation rejected (extra_forbidden) → unhandled
   ValidationError killed the run. Fix: `_wire_claim_data` projects citations
   back to wire fields before repair-input assembly.
3. **`tracing.grouping_score_summary`** still read the flat `counts` shape
   (`no_value`/`groups`) — only reachable live with Langfuse enabled; the
   full-chain smoke caught it. Fixed for facet-keyed counts (aggregating
   across facets), flat shape tolerated.

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

## Live checks (contract § Acceptance, the four pinned checks)

All against the dev DB (`policy_atlas`), scope
`308bb287-330f-4979-91b0-0d399211904f`, extraction run
`232d6afb-5db9-40a9-8714-bc9c362930ee` (021 both-profiles corpus: 333
findings, 184 distinct intervention values, 203 ICF claims).

**1. Scale fix (≥184 values, both profiles)** — PASS. Five-facet run
`d33c5e2e-0a7c-4399-9191-8b6f6dfbf4a3` (92s wall, $0.13): intervention 184
values → 20 groups + 14 ungrouped (0 duplicate-id rejections); outcome 166
values → 15 groups, `no_value` 110 honest (ICF null outcomes). The
facet-partition-value-list-scale-limit failure mode (4/4 duplicate-id at this
exact corpus) is demonstrably closed.

**2. Multi-facet incl. claim themes + synthesise consumption** — PASS. Same
run: barrier_theme 46 eligible → 8 groups, enabler_theme 32 → 7 (one honest
`groups_rejected` flag: a forbidden-label discovery rejection, repaired),
mechanism_theme 31 → 7; per-facet outcome objects all `succeeded`; eligible
bases + sha256 in per-facet provenance; context payloads enabled. Cost run 3
(below) synthesised BOTH lens families via one grouping ref (10 blocks;
theme claims validated per facet). Claim-theme scale ≥200: the Phase D
203-claim pooled scale probe (23 groups, residual 1, payloads on).

**3. Full-chain smoke (mandatory-spine composition)** — PASS. Live walking
skeleton (`uv run python -m policy_atlas.skeleton` with live keys):
34 `run.completed` events across the full chain — acquire → screen →
classify → appraise → ingest → characterise → select → extract → group (new
engine, `group_cluster_v1`, facet-qualified ids in the payload) → synthesise
×4 (v7; one 9-section artefact with per-facet theme claims). The smoke's
demo RENDERERS (skeleton pretty-printers) crashed twice on stale payload
shapes — live bug 3 above plus two pre-existing 021-era stale readers
(`_render_extraction` per-profile shape, `_render_grouping` flat shape) that
had never been live-exercised since 021 — all three fixed tolerant; the
fixed render tail was then validated by replaying the render functions over
the completed run's persisted event log (1010 entries; extraction, grouping,
synthesis ×4 and the rerank check all render — `rerank_used: 8`) rather than
a third ~25-min live rerun. The CHAIN itself completed on the second run;
only the post-run printer trailed.

**4. Cost re-measure, two arms** — table below.

## Cost measurement (three runs, § Cost measurement protocol)

Same corpus + intent, cold-cache starts, back-to-back same-day
(2026-07-14, run order 1→2→3), writer gpt-5.5 / judge gpt-5.4-mini, repair
path taken in all three ($ = Langfuse totals over each run's trace window —
the same source as the historical baseline):

| Run | Prompt ver | Substrate (grouping ref) | Wall | Prompt tok | Cached (rate) | Completion | $ |
|---|---|---|---:|---:|---:|---:|---:|
| 1 | v6 (frozen harness) | single-facet `68e6ad32` (19 groups) | 694s | 1,450,206 | 556,800 (38.4%) | 48,127 | $7.20 |
| 2 | v7 | same `68e6ad32` | 630s | 1,397,403 | 425,216 (30.4%) | 45,469 | $6.94 |
| 3 | v7 | five-facet `d33c5e2e` | 597s | 1,601,060 | 356,608 (22.3%) | 45,532 | $7.95 |

- **Arm (a)** (v6 vs v7, same substrate, Phase-2 isolation): v7 is
  cost-neutral-to-cheaper (−3.6% $, −3.6% prompt tokens, −9% wall) with the
  same section/flag profile — quality-neutrality corroborated by the shared
  substrate and matching block counts (9/9); single-sample caveat noted.
- **Arm (b)** (final multi-facet v7 vs the $15.45 / 24%-cache historical
  baseline): **$7.95 vs $15.45 (−49%)** while consuming FIVE facet lenses
  (the historical run had one), plus grouping $0.13. Wall 10.0 min — inside
  D1's ~10–20 min band (rider 16 re-measure: 11.6 / 10.5 / 9.9 min across
  the three runs).
- Cache-rate honesty: measured hit rates varied 22–38% and did NOT rank
  v7 > v6 on this single sample — the cross-section run-block prefix needs
  same-run request adjacency the section fan-out only partly gives. The $
  win is dominated by the repair micro-call (no transcript resends),
  tool-return dedup and DTO slimming. Deeper cache tuning = eval work.
- Single-facet grouping substrate note: the plan's "legacy" substrate had to
  be freshly minted (`68e6ad32`, intervention-only on the new engine) —
  pre-021 extraction rows are no longer referenceable (021 owner call) and
  the era's actual single-facet grouping rows on this corpus are the
  documented all-ungrouped scale failures. Both arm-(a) runs share it, so
  the isolation property holds.
- The `unspanned_assertions`-bearing runs 1–3 already include the item-17
  fixes: counts are NOT comparable to pre-022 runs (re-baseline note in
  deferred.md).

## 17(i) re-judge-set replay (the slice's ONE judge-envelope change)

Run 3's 16 judge envelopes captured live; each re-ran through the OLD-style
span map (JUDGED_TYPES spans only), same judge prompt (byte-identical):

- 94 verdicts compared; 30 differed — but 5 blocks had IDENTICAL envelopes
  under both maps (no non-judged claims) and still produced 14 verdict
  changes: the flip rate in narrowed blocks (16 over 11 blocks) is
  indistinguishable from the identical-envelope variance baseline, so the
  span-map widening shows **no verdict effect beyond single-sample judge
  variance** (verdict coverage itself unchanged by construction —
  test-asserted).
- The change lands where designed: total unspanned assertions 69 (old map)
  → 59 (new map) — the widened map filters judge over-reports inside
  claimed (pattern/theme/gap) territory.
- Evidence: `judge_ab_17i.json` (scratchpad; verdict-flip list retained
  locally), Langfuse window 2026-07-14T11:05–11:15Z ($0.18, 16 re-calls).

## AI replay tally (shared ≤35 budget)

9 (Phase D group replays) + 1 (203-claim scale probe) + 16 (17(i) re-judge
calls) = **26 component replays**; no refine rounds were needed on any 022
prompt surface (round 1 accepted everywhere — the group prompts and v7 shipped
as first authored; revert-not-iterate discipline never triggered). Phase R's
extraction probes were covered by the icf_v2 memo/fixture tests + the live
smoke's fresh extraction rather than dedicated live probes — flagged as a
conscious narrowing (the rider's one prompt-rule block is small and
vetter-guarded; ICF ground truth arrives at the eval slice).

## End-to-end command

```bash
# Live checks 1+2 (multi-facet grouping) + single-facet substrate mint:
uv run python <scratchpad>/live_check_022_group.py                     # 5 facets
GROUP_FACETS='["intervention"]' GROUP_OUT=live_check_022_group_single.json \
  uv run python <scratchpad>/live_check_022_group.py
# Cost protocol runs + 17(i):
uv run python <scratchpad>/live_check_022_synthesise.py 1   # v6 arm
uv run python <scratchpad>/live_check_022_synthesise.py 2   # v7 arm (a)
uv run python <scratchpad>/live_check_022_synthesise.py 3   # v7 multi-facet + capture
uv run python <scratchpad>/live_check_022_synthesise.py judge_ab
# Full-chain smoke (live check 3):
set -a; source .env; set +a; \
DATABASE_URL=postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas \
  uv run python -m policy_atlas.skeleton
```

## Diff summary

One slice, two phases, 15 commits on `task/022-synthesis-refinement`
(68 files, ~12.4K insertions / 2.1K deletions vs dev). Phase 1: the shared
two-stage clustering engine (`clustering_engine.py`) with characterise
refactored on behaviour-preserving; ONE migration (facet→group grain with
persisted-consumer id rewrite + ICF `context_label` column +
`finding_reference_union` view; downgrade refuses multi-facet rows);
multi-facet fan-out in one `group` run (six-facet vocabulary incl. the
claim-theme trio, per-facet honesty, facet-qualified ids fail-closed
end-to-end); `group_cluster_v1` prompts + live factory; `icf_v2` rider +
`extract_icf_vetter_v2` `paraphrased_label`. Phase 2 (one writer bump,
`synthesise_section_v7`): layered append-only prefix layout, tool-return
dedup + oversized-only windows + budget skip-and-continue, per-argument
scoped search, screen-confidence boost + product clamp, dependency-complete
id-carrying repair micro-call, unspanned precision fixes (all-types span
map · three counters · supersede), cost riders (lookup screening rows,
cited-only key-findings seed, batched embeddings, DTO slimming), the
side-effect-free steer surface, planner_v5 sweep, and the frozen v6 harness
for the cost protocol. Records: ADR 0018 re-checked (matches as-built on
all 8 decisions), spec flow-back (data-model + components §8/§9),
deferred.md sweep (all agenda items A–E carry recorded outcomes).

Prompt-surface discipline (rubric 13): bumped = `group_cluster_v1`
(supersedes `group_facet_v1`), `extract_icf_v2`, `extract_icf_vetter_v2`,
`synthesise_section_v7` (tool schemas versioned with it), `planner_v5`.
Byte-identical = characterise prompts (pin-tested), judge prompt; the ONE
judge-envelope change is 17(i)'s span-map widening (replay above).
prompting.md: no doctrine-grade change needed (the layered-prefix rule it
already pins is what F0 implements); noted, not edited.

## Hygiene audit (rubric 4/5 producer)

- No generated files, lockfiles or `.env` touched in the branch diff; no
  key-like strings in the diff (grep audit).
- 15 deleted test functions, all justified: 8 exercised the retired one-call
  partition machinery (component-level coverage re-established in
  `test_clustering_engine.py` + the new `test_group.py` invariants), 2
  covered the dropped `ck_grr_facet` constraint (removed by the approved
  migration), `test_value_cap_exceeded_fails_before_backend_call` +
  `test_backend_failure_raises_without_rollup_row` +
  `test_one_bad_label_never_zeroes_the_run` were superseded by the
  contract-mandated facet-local failure semantics (cap/backends now fail the
  FACET, with new tests), the socket round-trip was renamed, and
  `test_search_chunks_char_budget_tail_drop_and_zero_budget` asserted the
  exact `break`-drop behaviour item 12 removed (replaced by
  skip-and-continue tests). No skips/xfails added anywhere.

Flagged interpretation resolutions (minor, within contract vocabulary — the
007 None-vs-absent precedent):

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

## Known unverified items / gaps

- **Cache-prefix win not yet demonstrated as a cache-rate improvement** (see
  cost-table honesty note): the layout is correct-by-construction
  (append-only, run-stable block byte-identical — test-asserted) but the
  measured hit rate on single samples ranked below v6's run; eval-slice cost
  axis owns the deeper attribution.
- **Phase R live probes narrowed** (see replay tally): label-present /
  no-label / paraphrase-bait behaviour is covered by deterministic tests +
  the vetter flag class, not dedicated live extraction probes.
- **Quality-neutrality is corroborated, not proven**: rubric 12's "replay
  evidence per phase-2 change" rests on the v6-vs-v7 same-substrate arm +
  the deterministic suites; per-change isolated replays were not run (the
  changes ship as one v7 unit by contract design).
- Group ceiling ratio, boost constants, context-payload bounds: plan-pinned,
  calibration explicitly eval-slice work.

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
  - **Widening a judge's span map makes a live judge emit verdicts for ids
    it was never asked to judge** — envelope data the model can see is data
    it may act on; response validators must anticipate echo (drop-and-count,
    the invented-id posture), not assume the prompt's verdict-duty framing
    binds.
  - **Live-only reachability is a real test-coverage class**: three bugs
    (judge echo, enriched-citation wire re-validation, Langfuse score
    summary) passed the full suite and fell over only on live runs — each
    sat behind a live-model behaviour or a tracing-enabled-only branch.
  - The 17(i) A/B design lesson: an envelope A/B without an
    identical-envelope variance baseline over-reads verdict flips —
    single-sample judge variance produced a same-size flip set on identical
    inputs.
  - Langfuse per-run $ is recoverable by summing trace `totalCost` over the
    run's time window via the public API — no run-id key needed.

## Deferred work

docs/deferred.md updated this slice: agenda A (grammar v2 subsumed/retired,
one narrow tag-vocabulary seam), B (judge envelope unclamped; windowed
returns shipped; web-app read surfaces remain), C (coverage half parked for
eval + the `unspanned_assertions` re-baseline note), D and E (explicit
re-defers to the eval gate as SEQUENTIAL A/Bs), hybrid dimension search
(defer, spec corrected), ICF facet grouping (built; four remaining
context_types = config), UNION view (built, discharged), id-carrying repair
(discharged; re-gather repair still open), steer point (built; pause UX
open), read-tool scoping (plumbing built; WHEN-to-scope guidance post-eval),
multi-facet fan-in instance (dissolved; general seam stays), very-large-corpus
grouping (narrowed to input scale beyond the cap). New seams: gather/writer
model split (post-eval queue head, trace-evidenced), old `group_facet_v1`
machinery retirement (simplification-pass decision), group assignment
concurrency.
