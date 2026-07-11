# Verification: 018-dress-rehearsal

> **In progress** — this slice runs phased (contract § How this slice runs); evidence
> accrues per phase rather than landing whole at step 6. Live-run content stays private:
> ids/pointers only, per the contract's public/private boundary.

## Phase log

### B1 (2026-07-10): Phase 0 + A-model + A′ baseline-1 — complete

| Gate | Result |
|---|---|
| Phase 0 build-open full `make verify` | pass (998 passed, mypy 107 files clean, ruff clean, build ok) |
| Phase A-model `make verify-fast` | pass (950 passed, mypy clean, ruff clean) |

- **A-model landed** (commit `58e46f6`): full model-constant sweep per the plan table
  (`gpt-5-mini` → `gpt-5.4-mini`; classify `gpt-5.5` → `gpt-5.4-mini` @ xhigh; synthesis
  writer → `gpt-5.5`); provider-neutral `openai_kwargs` effort knob in `embeddings.py`;
  fake-client test pins the emitted kwargs; `grep '"gpt-5-mini"' src/ tests/` → zero hits.
  **`xhigh` SDK literal verified** against installed openai 2.44.0 (`ReasoningEffort`
  includes `"xhigh"`; `chat.completions.parse` accepts `reasoning_effort`) — no fallback
  substitution needed. Nothing prompt-bearing landed (diff = constants, comments, helper,
  tests). classify@xhigh remains a hypothesis to verify against baseline-1 (plan A1).
- **Baseline-0 recorded** (historical reference, pre-refresh): pointers + counts + block
  texts in `docs/verification/private/018/baseline-0/` (gitignored). **Deviation noted**:
  the contract names `128c0a81` as the second baseline-0 project, but it is the failed
  first attempt (acquire + two failed runs — no extract/synthesise substrate); replays use
  `e8ac8418` (2026-07-09 full chain, different intent) per user direction at B1 open.
- **Baseline-1 captured** (the loop baseline: new models, prompts byte-identical to merged
  dev; references pinned from the original runs' `plan.compiled` payloads):
  - `91d2d684`: extract `ad74f884` (10 docs, 54 findings), synthesise `37016a74` /
    artefact `c54eaaf4`.
  - `e8ac8418`: extract `392f9e5f` (25 docs, 11 extracted, 2 failed), synthesise
    `09596414` / artefact `195761c3`.
  - Records + block texts in `docs/verification/private/018/baseline-1/`; replay/export
    drivers preserved in `docs/verification/private/018/drivers/` (C1 generalises them).
  - Early signal for the loop (not adjudicated): `turn_cap_hit` fires on BOTH synthesise
    replays (absent at baseline-0) — the 5.5 writer works more tool turns (chunk claims
    0→44 on `91d2d684`); `e8ac8418` also flags `uncited_sections`.
- Langfuse traces locate by `run_id` metadata on run spans (sessions land at A2).

### B2 (2026-07-10/11): Phase A-rest (A2–A6) — complete

| Gate | Result |
|---|---|
| B2 build-open full `make verify` | pass (998 passed, mypy 107 files, ruff clean, build ok) |
| Wave 1 (A3–A6) `make verify-fast` | pass (974 passed, mypy 109 files, ruff clean) |
| A2 `make verify-fast` | pass (976 passed, mypy 110 files, ruff clean) |
| Phase A-rest exit full `make verify` | pass (1027 passed, mypy 110 files, ruff clean, build ok) |

- **Wave 1 landed** (commit `a05d984`; A3/A4/A5/A6 in parallel fast-worker lanes,
  lead wording in the same commit):
  - *A3 regrade*: standard row `deep_chain=False` / `selection_budget=None`
    (screen_stage2 + characterise kept; ADR 0013 spine untouched); `FACET_VALUE_CAP`
    150→400; standard×standard band kept at the measured pre-regrade value with a
    stale-flag comment (re-seed in Phase D). Blast radius honestly taken: runner/
    steering/orchestrate fixtures moved to `deep` where they exercise the deep chain,
    and `StubPlannerBackend`'s full-chain draft depth moved to `deep` (the stub was
    the root cause of the console-flow failures — flagged, one line).
  - *A4 planner history*: `build_planner_messages` emits a true user/assistant
    message array (bounding, per-position sanitisation caps, draft-as-data on the
    latest turn, unknown-role coercion preserved; defensive draft-only trailing
    message when the latest turn isn't a user turn). Lead re-anchored the
    anti-injection system-prompt section to the multi-message shape. New
    `tests/test_planner_prompt.py` (9 tests — the old blob shape had no direct tests).
  - *A5 direction rename*: `EFFECT_DIRECTIONS`/`EffectDirection` →
    increase/decrease; migration `64ff33416d1a` (drop `ck_iof_direction` → data
    `UPDATE` → recreate, both directions; constraint absent while transitional
    values exist); fixture sweep (10 test files) + spread-reader pin
    (`direction_spread` zero-fills from the tuple); round-trip test following the
    existing migration-test convention. Lead wording: extract-prompt example
    (`negative`→`decrease` — the rename's own motivating ambiguity) +
    movement-not-desirability guidance; synthesis tool-schema enum now reads
    `EFFECT_DIRECTIONS` directly. `extraction_records` field-description tokens
    renamed by the worker (prompt-adjacent; reviewed and approved as lead wording).
  - *A6 country filter*: grammar + wire mapping already existed (015) —
    the rider reduced to planner expression: `ScopeConstraints` +
    `PlanDraftWire.author_affiliation_countries` (2-letter codes, upper-normalised,
    no dupes/empty), compiled under `filters["openalex"]`, backend-scope coherence
    check (grey_lit_only rejects it), threading through `orchestrate._build_plan`.
    Lead prompt capability line names both geography filters' vocabularies honestly.
- **A6 live probes (lead)**: OpenAlex `authorships.countries:gb|GB` verified
  (9.14M works, case-insensitive; invalid filter keys 400 fail-closed).
  **017's Overton `publisher_country` open item CLOSED**: `source_country`
  filters correctly with Overton *display names* (`UK`/`USA`/`Canada` → 20/20
  results match) but **silently returns zero** on ISO codes and full official
  names ("United Kingdom") — hazard recorded in the planner prompt line
  (display-name vocabulary stated) and in knowledge candidates.
- **A5 migration up/down evidenced on the dev DB (real 017 rows)**: pre
  {positive 1085, negative 731, no_effect 208, mixed 22, unclear 140} →
  upgrade → {increase 1085, decrease 731, rest unchanged} with the new CHECK
  in place → downgrade → exact original distribution restored → re-upgraded;
  dev DB left at head `64ff33416d1a`.
- **A2 landed** (commit `daf90a5`; codex lane, session
  `019f4e57-33c8-7aa1-b173-7b1c38bc4728`): 17 backend-protocol methods return
  `UsageResult[T] = (wire, TokenUsage | None)` (new `usage.py`); `usage_totals`
  in `component.completed` payloads + `runner.component_usage` structlog
  aggregate (017 deferred item discharged); `component.timing` on a fresh
  transaction on success AND failure paths (fault-injected test);
  conversation uuid minted at orchestrate start → planner `plan_turn(session_id=)`
  + `component_span(session_id=)` → one Langfuse session per conversation;
  `_discover_themes` persists validator-rejection `str(exc)` (generic exceptions
  keep type-name only — bounded logs). **Substitution note (routing ladder):**
  codex's sandbox could not reach Docker/Postgres, so DB-gated acceptance ran in
  the lead lane; 7 mechanical leftovers (test-double `session_id` kwargs, frozen
  payload key sets) fixed by a fast-worker from the exact failure list.
- **User riders during A2 (2026-07-11, visible minor additions)**: the session
  uuid is also persisted into `run.started` payloads (`payload->>'session_id'`
  gives the DB→Langfuse session join the plan pin lacked); run trace roots
  renamed `run:{component}:{run_id}` (list-view scannability; metadata unchanged;
  replay-driver rootless traces deferred to C1's driver generalisation, noted).
- Contract A.2(e) (prompt-registry/datasets assess-don't-adopt): plan rev 3
  scoped it out of the A2 row — stands as an eval-slice item, no 018 action.
- Langfuse trace-convention questions (user, 2026-07-11) answered and recorded:
  planner turns are deliberately separate traces (now session-correlated);
  top-level `extract:*:w0`-style traces are the B1 replay drivers running
  without `component_span` (C1 fixes); empty-I/O `run:` traces come from the
  summary-attach guard — run `4077e12f` (succeeded characterise) shows the
  payload-lookup miss; flagged for a C-loop eye, not blocking.

## Live component replay tally (bound: ≤30; baselines/fork-probe/B-smoke/D excluded)

| # | Phase | Replay | Counted? |
|---|---|---|---|
| – | A′ | baseline-1: extract ×2, synthesise ×2 | excluded (baseline) |
| – | A-rest | none (OpenAlex/Overton wire probes are search-API calls, not component replays) | n/a |

Running total: **0 / 30**.

## Loop protocol notes (flow-back candidates for the eval-slice convention)

- **Parallel-by-default replays (user direction, 2026-07-10):** independent C-loop
  replays run in parallel by default (e.g. the two pinned projects' spot-checks
  together); serialize only when two runs contend for the same substrate or when
  isolating one variable's trace matters. Baseline-1 ran sequentially (driver shakedown
  + rate-limit caution) — that caution is not the convention.

## Review handoff (accrues; finalised at Phase E)

- **Knowledge candidates:**
  - Contract-pinned baseline project id was wrong (`128c0a81` = failed first attempt);
    the replayability check (does the project have the component runs you need?) belongs
    at contract time, not build time.
  - Overton `source_country` takes Overton *display names* (`UK`, `USA`, `Canada`) and
    **silently returns zero** on anything else (ISO codes, "United Kingdom") — a
    fail-closed grammar cannot protect against provider-side silent misses; live-probe
    filter *values*, not just keys, before a prompt promises them (B2, 2026-07-11).
  - Parallel same-tree agents: string-Edit-based concurrent edits to the same test file
    interleaved cleanly, but concurrent DB-backed suite runs against the one shared
    test DB flaked (one deadlock, vanished on re-run) — partition test *runs*, not just
    file sets, or give lanes separate DATABASE_URLs (B2).
  - Codex sandbox cannot reach Docker/Postgres: brief codex to gate on pure tests +
    mypy/ruff only and plan a lead-lane DB-gated acceptance pass after delivery —
    that's a routing-ladder property, not a codex quality issue (B2).
  - `run:` trace-level input/output attaches only when the component's score-summary
    payload lookup succeeds (`skeleton.py` guard) — a *succeeded* run can still show an
    empty-I/O trace (seen: `4077e12f`, characterise); make the attach unconditional or
    log the miss if it starts mattering (B2; C-loop eye).
