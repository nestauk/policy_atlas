# Multi-round search in production: total screening caps, no wall clock, no target

## Context

Task 028 (uncommitted, on `37-hotfix-remove-quota`) replaced the standard/deep wall
clock with a per-backend acquisition cap. Investigating it surfaced a bigger fact,
recorded in `docs/deferred.md`: **the multi-round search loop has been unwired since
task 023** — `run_deep_rounds` / `should_escalate` lost their only caller when
`skeleton.py` was deleted (`3304df4`). In production today every depth runs one round,
no reformulation/snowball/suggest arms, and the depth contract ("standard = 2 rounds,
deep = 3") is aspirational.

The owner's directive (2026-08-06): make the pipeline match the intended methodology —

1. cap documents passed to screening (post merge/dedupe) at **50 rapid / 100 standard /
   200 deep, per backend per round** (owner-confirmed grain, 2026-08-06);
2. remove the wall-clock mechanism **entirely** (including rapid's);
3. make the multi-round mechanism (reformulation, snowballing, suggest) **run in
   production**;
4. remove `TARGET_CONFIDENT_RELEVANT` — the 3-round cap is the budget.

## Decisions taken (flagged where they interpret the directive)

| Decision | Choice |
|---|---|
| **Cap grain (owner-confirmed)** | **Per backend, per round** — exactly the mechanism as built. Each round may pass up to N results from OpenAlex *and* up to N from Overton to screening: rapid 50, standard 100, deep 200. Deep is already 200/backend today; standard changes 150 → 100, rapid changes uncapped → 50 (closing the known gap where rapid could acquire ~750 docs bounded only by its clock). No mechanism change — constants only. |
| **`search.target` directive (owner-confirmed)** | **Remove it entirely** along with `SEARCH_TARGET_MIN/MAX` and `TARGET_CONFIDENT_RELEVANT`. Not a breaking change in any REST sense — the exact consequences are inventoried in § 4 below. |
| Where the loop lives | **In the runner's walk** (Option B below) — not inside the acquire component, not by loosening segment re-entry. |
| Round budget | `DEPTH_CONSTANTS[depth]["round_cap"]` (rapid 1 / standard 2 / deep 3), read from the plan's `search_effort`. Fixes the existing bug where `run_deep_rounds` hardcoded deep's cap. |
| Stop conditions once target is gone | `budget_exhausted` (round cap) and `short_circuit` (yield < 1 new confident-relevant per 50 screened). The `re_searched_still_thin` honesty overlay re-keys from `below_target` to `confident < THIN_CONFIDENT_RELEVANT (8)` — the constant that actually means "thin". |
| `run_deep_rounds` / `should_escalate` | **Delete both** (dead once the runner owns the loop; escalation stays unbuilt — out of scope). Keep `evaluate_deep_stop` (pure), `finalise_deep_stop` (writes the final stop overlay), `confident_relevant_count`. |
| Schema | No migration. `target_reached` and `wall_clock_exceeded` stay in the CHECK constraint as historical/unreachable values. |

### Why the runner loop (Option B)

Explored alternatives and their objections:
- *Loop inside the acquire component*: one opaque run row for the whole block; no
  steering boundary or check-in between rounds; the chain's `screen_abstract` step
  becomes a 0-doc no-op; no per-round SSE frames.
- *Loosen segment re-entry*: the one-cycle limit is hard-coded at its re-presentation
  sites (`runner.py:3535, 3593`) as a deliberate invariant; bending it touches the
  steering machinery's core guards.
- *Call `run_deep_rounds` from the runner*: Connection/Engine mismatch,
  `finalise_deep_stop` writes inside it, and it duplicates orchestration the runner
  already does better (run rows, boundaries, retries, progress).

The runner walk already supports everything a loop needs: one run row **per attempt**
(replacement re-runs and segment re-entry already produce multiple runs per component
name), per-round steering boundaries and check-ins for free, SSE `stage.*` frames per
run, and the frontend timeline already renders repeated stage keys (`ingest_full_text`
maps onto the `acquire` stage today, so every run already shows two "acquire" frames —
`reducer.ts` appends, `JourneyPane` keys by `${stage}-${index}`).

Screening is confirmed incremental (`_load_stage1_docs` NOT-EXISTS on non-failed
stage-1 rows, any generation), as are classify/appraise; stage 2 picks up newly
relevant docs at the same generation. Repeated rounds reprocess nothing.

## Changes

### 1. Per-backend screening caps — constants only (`search_loop.py`)

The mechanism as built (task 029) is already what the owner wants: per-backend
rank-interleave across queries → dedupe → trim to `record_cap_per_backend`, cap
checked before the identity guards (the dropped-twin fix and its regression test
stand). Only the numbers change in `DEPTH_CONSTANTS`:

- rapid: `None` → **50** (closes the known gap: rapid could previously acquire ~750
  docs bounded only by its clock — which § 2 removes)
- standard: `150` → **100**
- deep: `200` → **200** (unchanged)

Targeted verbs (snowball/suggest lookups) still bypass the trim — bounded upstream
(`SNOWBALL_RESULTS=40`, `SUGGEST_CALL_CAP=6`), so a round screens at most
2×cap + ~50. `results_returned` invariant unchanged. Tests: `test_acquire_record_cap.py`
is grain-agnostic (passes the cap explicitly) — only tests pinning depth constants
need the new numbers.

### 2. Remove the wall clock entirely (`search_loop.py`, `acquire.py`)

- Delete `RAPID/STANDARD/DEEP_WALL_CLOCK_S`, `DepthConstants.wall_clock_s`, the clock
  check in `execute_call`, and the whole `stop_all` mechanism (the clock was its only
  setter — every `if stop_all: break` goes; the fan-out simply runs to completion).
- `acquire_sources` loses `wall_clock_breached`; stop attribution becomes
  `error`/`completed` only. `run_search` loses its `clock` param and
  `wall_clock_breached` summary key.
- Tests: delete rapid-breach tests (`test_rapid_result_cap_…wall_clock_stop`'s clock
  half, `test_coverage_wall_clock_exceeded…`), update the standard no-clock test to
  cover all depths. Consequence to state in docs: nothing bounds search latency
  anywhere now; rapid worst case ≈ 21 sequential provider calls + retries.

### 3. Wire the loop into the runner (`runner.py`, small; `search_loop.py` cleanup)

**Gate location:** in `_run_plan_impl`'s walk, immediately after the
`screen_abstract` step's success path completes its after-boundary
(`runner.py:1008–1062` region).

**Gate logic (stateless — recompute from DB so park/resume mid-loop is safe):**
```
if plan.search_effort in ("standard", "deep"):
    rounds_done  = _count_existing_rounds(...)          # coverage rows for the scope
    round_cap    = DEPTH_CONSTANTS[search_effort]["round_cap"]
    confident    = confident_relevant_count(...)
    docs_screened = this screen run's "screened" headline count
    new_confident = confident - confident_before_this_round   # read before the round
    decision = evaluate_deep_stop(round_index=rounds_done, ...,
                                  round_cap=round_cap)
    if decision.stop:
        finalise_deep_stop(..., stop_condition=decision.stop_condition,
                           thin=confident < THIN_CONFIDENT_RELEVANT)
    else:
        re-queue the acquire + screen_abstract ComponentSteps at the head of
        remaining_steps and discard them from completed_components — they then run
        as ordinary steps: fresh run rows, boundaries, check-ins, SSE, retries.
```
- `run_search` needs no change: `_count_existing_rounds` already makes the second
  acquire run round 2 and unlocks the arms (`round_index >= 2` branch).
- The re-queued steps reuse the same compiled `directive_delta` (depth/filters
  preserved; pending overlays still merge per attempt).
- Depth reaches the gate with no new plumbing: `_SteeringState.plan.search_effort`.
- `evaluate_deep_stop` slims to `(round_index, new_confident_relevant,
  docs_screened_this_round, round_cap)` → `short_circuit` | `budget_exhausted` |
  continue. `finalise_deep_stop`'s `below_target` param renames to `thin`.
- **Delete** `run_deep_rounds` and `should_escalate` (+ their tests). The notebook
  `scripts/scratchpad/search_rounds_and_arms.ipynb` currently drives the deleted
  function — it gets rewritten as part of § 6.

**Accepted blemishes (record in deferred.md, do not fix now):**
- `successful_runs["acquire"]` is last-write-wins, so the P1 coverage trigger and the
  "Where I looked" pane (`coverage_out`) see only the **final round's** coverage row
  and queries.
- Timeline shows repeated "Searching sources" / "Screening" rows with no round label.
- A deep run becomes tens of minutes (3 × (2–4 min search + screening)); no step
  timeout exists anywhere.
- Cost: deep worst case ≈ 1,200 docs screened (3 rounds × 200/backend × 2 backends)
  ≈ 3,600 stage-1 calls + embeddings; standard ≈ 400 docs (2 × 100 × 2).

### 4. Remove `TARGET_CONFIDENT_RELEVANT`, `SEARCH_TARGET_MIN/MAX` and `search.target`

**Exact consequences, verified by exploration (owner asked for these before
proceeding). "Breaking change to the steering API" was an earlier overstatement —
the directive is far less shipped than its task-024 docs suggest.**

What does NOT break:

- **No REST/OpenAPI change.** No router accepts `target`; it appears in no API
  contract and no generated frontend types (`frontend/src/api/gen/types.ts`: zero
  hits). No frontend surface exposes it.
- **No steering-bundle change.** The pause-point option bundles offer
  depth/filters/guidance only (`steering.py:648–723`); `target` was never advertised
  as a user choice.
- **No functional loss.** Its entire end-to-end effect today: validated by
  `parse_search_directive`, **discarded** by the plan layer
  (`_apply_acquire_delta` writes only depth/filters), threaded via free-text overlay
  into scope context, echoed as `target_confident_relevant` in the acquire payload —
  which nothing in `src/` or the frontend reads. The stop it nominally configures
  lives in the unwired loop. Removing it deletes a no-op.
- **No DB migration.** `target_reached` stays in the `stop_condition` CHECK
  constraint as a historical value; `test_search_migration.py:109` (constraint
  round-trip) stays green unchanged.

What changes:

- **Free-text steering grammar shrinks, with honest refusal.** The only authoring
  path is free text at a steering pause → the LLM router may compile
  `{"search": {"target": N}}`. Today that compiles and silently does nothing. After
  removal the parser fails closed on unknown keys (`search_loop.py:619-621`), so the
  same request is refused with an explicit error and the user rephrases. Delete the
  router-prompt line advertising it (`orchestrator_prompt.py:530-531` — already
  stale: says 5–60, parser accepts 100) so the router stops compiling the key.
- **Stored-context edge — self-healing, verified.** Old `evidence_scope.context`
  rows may carry a persisted `target`. Every acquire attempt overwrites the scope's
  whole `search` key from the compiled plan delta *before* parsing
  (`runner.py:5136-5155`, top-level replace), and the compiled delta never contains
  `target` — so stale values are wiped before they can reach the parser. Residual
  exposure: only a run parked *before* this change with a target-bearing pending
  overlay, resumed *after* it, would hit the refusal — component fails with the
  honest unknown-key error and is re-runnable after rephrasing. Dev-only,
  vanishingly unlikely; accept and note.

Mechanical work:

- Delete the three constants, the `target_reached` branch in `evaluate_deep_stop`,
  its `target` param, and the `target_confident_relevant` payload echo.
- `parse_search_directive`: drop the `"target"` key → returns
  `(depth, raw_filters, guidance)`; update both unpack sites
  (`search_loop.py:1282`, `steering.py:1896–1902`).
- Tests: rewrite/remove target cases in `test_search_directives.py` (~19 refs, incl.
  the min≤default≤max pin test which dies with the constants), `test_steering.py`
  target deltas (`:284-298`, `:394`), `test_search_loop_deep.py` target/override
  tests.
- Docs: task 024 contract lists D5 `search.target` as in-scope — amend to record the
  removal and rationale (feature was a validated-then-discarded no-op), rather than
  leaving the contract claiming a live feature. If a "stop early at N" user feature
  is ever wanted, rebuild it against the runner gate (§ 3), where the stop decision
  now lives — not in the parser.

### 5. Docs

- New `docs/tasks/030-multi-round-search/plan.md` (this file's content, adjusted) —
  wiring the loop is an architectural change; consider a short ADR ("search rounds are
  runner-orchestrated; component loop deleted with skeleton").
- `docs/deferred.md`: discharge "Deep-round continuation loop is unwired" and the
  `TARGET_CONFIDENT_RELEVANT` entry (both resolved by this change); update the rapid
  no-cap gap (closed); record the accepted blemishes above.
- `docs/tasks/015-live-search/contract.md` decision 6 + task 024 D5 docs: amend for
  total-cap grain and target removal.
- `docs/knowledge/result-caps-need-distribution-rule.md`: cap is now total-per-round
  with backend-balanced split.

### 6. Verification tooling in `scripts/scratchpad/` (owner-requested)

- **`run_live_deep.py`** — drives one live deep run through the real
  production path (the runner via `run_plan`, not hand-rolled loops), then reads back
  and prints: rounds executed (coverage rows), which arms fired per round (from
  `search.executed` events by verb/origin), per-round acquired/screened/
  confident-relevant counts, the final stop condition, wall-clock duration, and an
  estimate of screening spend. Flags: `--depth rapid|standard|deep`, `--intent`.
- **`README.md`** — plain-English explanation of what each file in
  `scripts/scratchpad/` does, what a live run costs, what to look for in the output,
  and which database it writes to.
- **`search_rounds_and_arms.ipynb` — rewritten** for the new architecture: the loop
  is now runner-orchestrated and `run_deep_rounds` no longer exists. The notebook
  steps through the rounds the way the runner does — `run_search` → `screen_sources`
  → the same `evaluate_deep_stop` gate — so each stage stays individually inspectable,
  with the per-round yield table, arms-fired table, and funnel views kept from the
  current version. A header cell states that this mirrors (not replaces) the
  production path, and points at `run_live_deep.py` for the real thing.
- `search_caps_by_depth.ipynb` — touch up the caps table/comments for the new
  constants (50/100/200 per backend) and the removed clock; mechanism cells unchanged.

## Out of scope (state in the task doc)

- Rapid→deep escalation (`should_escalate`) — deleted, not wired; a fresh decision if
  wanted.
- Round labels in the frontend timeline; per-round coverage in "Where I looked".
- Any step/latency timeout to replace the wall clock.

## Verification

1. `make verify` green (expect large test churn in `test_search_loop_deep.py`,
   `test_search_directives.py`, `test_acquire_record_cap.py`, `test_steering.py`).
2. New runner tests (scripted backends, stub screening — patterns exist in
   `test_search_loop_deep.py` and runner tests): deep plan runs acquire+screen 3×
   with three run rows each and stops `budget_exhausted`; standard runs 2×; rapid 1×;
   `short_circuit` stops early on a zero-yield round; a scripted arm round shows
   `fetch_citations`/`lookup_dois` calls (arms actually fire at round 2);
   park mid-loop → resume continues at the right round (stateless gate).
3. Cap tests: depth constants pin 50/100/200 per backend; dropped-twin regression and
   the existing per-backend cap suite still green.
4. One live deep run end-to-end via `scripts/scratchpad/run_live_deep.py` (§ 6):
   confirm 3 rounds in the event log, arms firing, per-round coverage rows, timeline
   renders, duration and screening spend recorded. Owner explores further with the
   rewritten `search_rounds_and_arms.ipynb`.
5. Ground-truth recall eval: **not runnable on this branch** —
   `scripts/eval_ground_truth/` lives on a different branch. Record in the task doc
   that the recall re-measurement (baseline mean 2.4% / max 9.1%) happens after this
   branch and that one merge, and remains the acceptance test for the whole change.
