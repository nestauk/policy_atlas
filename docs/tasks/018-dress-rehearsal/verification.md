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

## Live component replay tally (bound: ≤30; baselines/fork-probe/B-smoke/D excluded)

| # | Phase | Replay | Counted? |
|---|---|---|---|
| – | A′ | baseline-1: extract ×2, synthesise ×2 | excluded (baseline) |

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
