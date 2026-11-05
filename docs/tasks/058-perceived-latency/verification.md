# Verification: 058-perceived-latency

Evidence for one slice. Filled during the build (task-cycle-build, steps 5 and 6); the
review stack adds **Review findings** and **Rubric status** at step 7. Public-safe: no
secrets, no raw source text, no unredacted traces.

> Status: **build in progress** (opened 2026-11-05 in a fresh conversation on plan Phase 0; backend Phases 0 to 4 committed the same day).

## Commands run

| Gate | Command | Result | Notes |
|---|---:|---|---|
| Build-open baseline (2026-11-05) | `make verify` | pass | backend 4126 passed, 1 skipped (8 min 44 s); frontend 943 tests, 88 files; `drift-check: OK`; exit 0. Log kept in the session scratchpad. |

| Phase 0 and Phases 1 to 4 (2026-11-05) | `make okf-validate && make -C backend verify && make eval-check && make -C infra test && make audit-paths && make prompt-guard && make font-guard`, then `make openapi-sync && make drift-check` | pass | backend 4256 passed, 1 skipped (7 min 9 s); mypy clean on 464 files; ruff clean; prompt-guard 41 files unchanged after the re-pin; infra 113 passed; `drift-check: OK`. **Deviation from the gate map:** the four backend phases were built in parallel (the Codex spend cap forced a re-route mid-phase), so one combined full backend gate closed them instead of four. The frontend lane of `make verify` is red between these commits and the Phase 6 commit: the regenerated types replaced the tick fields and added `PlanStep.row`, and the client is rewired in Phases 5 to 8 (replace, do not layer). The first fully green `make verify` is the Phase 9 gate. |

| Phase 5, mock (2026-11-05, `1ae4425f`) | `pnpm vitest run src/mock`, `pnpm exec eslint src/mock`, `tsc -b` (no errors under `src/mock`) | pass | 43 tests; the backend tree is unchanged since the Phase 1 to 4 gate, so the fast gate's backend lanes were not re-run. |
| Lead additions after brief O (2026-11-05) | `pytest tests/api/test_sse.py tests/api/test_contract_models.py`, `make openapi-sync`, `make drift-check`, `pnpm vitest run src/store src/mock src/views/workspace/runProgress src/views/workspace/RunningCard src/views/taskLive` | pass | `stage.completed.counts` on the server and the client; the mock emits `plan.updated` at run start so the card has rows to come; the breathing dot's trough raised to 0.5. |
| Phase 6, store (2026-11-05, `c72006c5`) | `pnpm vitest run src/store src/api`, `pnpm exec eslint src/store src/api`, `tsc -b` (no errors under `src/store`, `src/api`) | pass | 106 tests; remaining `tsc` errors are in `src/views`, the Phase 6 surfaces. |

| Phases 6 to 8, surfaces (2026-11-05) | `make verify-fast` (backend test-fast, typecheck, lint, eval-check); `pnpm typecheck && pnpm exec eslint src e2e/<the four specs> && pnpm test && pnpm build`; `make drift-check` | pass | backend 4219 passed, 1 skipped (after two option-profile tests learned to skip verb lines); frontend 1064 tests in 93 files, build OK, `drift-check: OK`. The lint lane was run on `src` and the four committed specs because the Phase 9 agent's scratch `e2e/probe.spec.ts` was in the tree at that moment (deleted before Phase 9's gate). |

(Later gates are appended as each phase closes.)

## Checks beyond the build

- **Deterministic tests** — per phase, listed with the gate row.
- **Manual / browser / API** — the live-dev checks, the fixed-question captures and the
  screenshots are recorded in § End-to-end and § N25 measures.

## End-to-end command

To be filled at step 6.

## Diff summary

Filled per phase as it lands; the flagged deviations are in § Review handoff.

## Intent & assumptions

- The hub API (`core/liveness.py`) was designed by the lead before any brief was written
  and is recorded in `research/briefs/hub-api.md` (gitignored research folder). Every
  Phase 1 and Phase 2 brief codes against it.

## Known unverified items

To be filled.

## Public safety

To be filled.

## Review handoff (step-7/8 inputs)

### Dispatch log (plan § Briefs, P15)

| Brief | Seam | Executor planned | Executor actual | Result |
|---|---|---|---|---|
| F | `scripts/stream_capture.py`, `stage_walls.py --capture`, tests | builder | builder (Opus) | done 2026-11-05: 30 tests pass, ruff clean. Two departures the lead accepted: `--until-terminal` follows the run the page follows (the reducer's rule) and ignores terminal statuses older than the capture start; the measure uses that run's stage frames only. |
| A | `core/liveness.py` hub | codex | **deep-reasoner** (Codex died on the workspace spend cap before applying any change) | done: 15 hub tests, the ingest and single-pass tests pass; nine API points interpreted (recorded in the agent's report, the main ones: a held append is sent to existing subscribers before a snapshot so no text arrives twice; the kept draft keeps the first 20 000 characters; `end_run` resets the dropped counter; a loop tick blocks hook verbs for the rest of the stage). Lead change after: `clear_draft` sends a held append before forgetting the draft. |
| B | `core/tracing.py` hooks, `traced_parse` `before`, harness stage binding | codex | codex (code applied; cap hit) → deep-reasoner finished | done; `_verb` imports the table inside the function (core stays import-light) |
| C | `api/routers/sse.py` encoder, snapshot, drain | codex | codex (code applied; cap hit) → deep-reasoner finished | done; the revocation tests now also publish a delta and a revising mark after revocation and assert nothing leaks |
| D | runner `begin_run`/`end_run`, `wall_clock_s`, join-loop tick | codex | codex (code applied; cap hit) → deep-reasoner finished | done; note: `component.timing.headline_counts` now carries `wall_clock_s` for every component (it copies the completed payload); `stage_walls.py` reads the top-level timing field, so the anatomy is unchanged |
| E | loop counts (N2) | fast-worker | fast-worker | done: ten loops, five summary keys (`theme_count`, `selected_count`, `finding_count`, `group_count`, `documents`), new `core/done_callbacks.py` (a pool thread runs a done-callback in an empty context, so the callback must carry the submitting thread's context or the bound task is lost); `ClusteringPolicy.progress_key`; `round_index` is 1-based so "Search n" shows from the second pass |
| G | `section_emit_stream` | codex | codex (method and loop call applied; cap hit) → deep-reasoner finished | done; the decoder dropped the first of two adjacent high surrogates (fixed, every-split-point test); lead: the step's `CACHE_MODES` row was missing, so every streamed turn fell back silently (added `auto`); lead: one decoder for both sites (`core/openai_client.JsonStringFieldDecoder`) |
| H | writer activity lines, revising frame | codex | deep-reasoner (cap) | done with G; "Checking claims" and the revising frame also run for key findings, which is not streamed (harmless: the client blurs only draft spans) |
| J | planner stream | codex | deep-reasoner (cap; Codex applied nothing) | done; the strict schema sent is `openai.lib._pydantic.to_strict_json_schema(wire)` (the raw schema is not strict-valid); the pre-token retry catches the SDK's error classes only (the import guard forbids `httpx`); the shared test helper `resource_support.task_agent_turn` now reads the stream |
| K | planner fixes (N18/N19/N20 backend) | fast-worker | fast-worker | done; its asterisk test needed a real option id on `PendingAction` (lead fix) |
| M | frontend store (N5, N7, N15, N16, N23) | codex | deep-reasoner (cap) | done: 106 tests; the watchdog, drafts held before the skeleton, child frames refresh `options` only, ingest ticks refresh evidence and landscape once per 5 s |
| N | mock contracts and fixtures (N26 first half) | fast-worker | fast-worker | done: 43 tests; the annex figures; the real `search_review` check-in; twelve child walks; the options read; scenarios `reload-mid-section`, `paused-strip`; `setMockPace` for unit tests. Follow-up by a second fast-worker: the walk-time longlist read shares the options read's ids and grows stage by stage. |
| O | card C, strip, tab marks, title, task row, Plan control, Sources default, one orange | frontend-designer | frontend-designer (hit its 150-turn limit; reported on a resume) | done: 859 view tests; `useFreshness`, `taskLive.tsx`, `planPanel.tsx`; the client vocabulary deleted; screenshots partial (round 1 of the strip, the paused card, the task row). Lead after: the done-row counts moved to the frame; the mock sends `plan.updated` at run start; dot trough 0.5. |
| P | Result tab before and while writing; the sidebar | frontend-designer | frontend-designer | done: 143 tests; `SidebarRun.tsx`; screenshots of every state (round 1 and 2). Lead after: three copy fixes (ended-early line, "just now", the tail shows the activity only). |
| Q | planning conversation and check-ins (N9, N10, N18, N19, N20) | frontend-designer | frontend-designer | done: 956 tests across views, store and api; the turn stream reader, `planEdits.ts`, `Button variant="start"`, `LABEL_CLASS`; screenshots of scenes 10 to 12. Lead after: the server's check-in render starts with its question (`CHECK_IN_QUESTIONS`), and the client titles the card with it. |
| R | the longlist during the build (N24) | frontend-designer | frontend-designer | done: 174 tests; `LonglistBuilding`, `useOptions`; no screenshots (two mock gaps, fixed by the follow-up to N). Lead after: the clustering note comes from the server tick. |
| L | task-list stage, options read | codex | deep-reasoner (cap) | done; the `LatestRun.model_rebuild` workaround for the `StageKey` import cycle was replaced by the lead: `StageKey`/`STAGE_KEYS` now live in `contract/common.py` and are re-exported |

**Executor substitution (memory rule, owner 2026-07-09):** the Codex workspace spend cap was
hit at about 09:30 on 2026-11-05 during Phase 1. Every Codex-marked seam from that point
runs on `deep-reasoner` (Opus); the family flip for review stays with conversation C's
Codex adversarial lane if the cap is lifted, else with the Claude lanes alone (to be
adjudicated at step 7).

### Prompt-hash re-pin (G2)

`python3 scripts/prompt_hash_guard.py --update` re-pinned two files on 2026-11-05:

- `evidence_search/synthesis/section_prompt.py`: `d9011b4a…` → `b771fd12…`. The only text change
  is a second final-turn message for the streamed shape, `SECTION_FINAL_TURN_MESSAGE_STREAMED`
  ("This is your final turn: write the section now, as the prose and the claims this section can
  support from what you have gathered."), selected by `build_section_messages(..., streamed=True)`.
  The research turns, the repair and the forced-tool final turn keep their wording.
- `runtime/task_agent_prompt.py`: `4071ece4…` → `ead2bf75…`. The three preset time bands are
  now read from `task_plan.TIME_BANDS` (one table, N20). Two bands were already equal; the
  Rapid overview band changes from "~5-10 min" to "~10-15 min" (the plan document's value).
  No other prompt text changes; `PLANNER_PROMPT_VERSION` stays (like-for-like swap ruling).

### Flagged deviations (minor, resolved within the contract's vocabulary)

1. **`PlanStep.row`** (public interface, additive; not on G1's list). N17 says the server's
   presentation table decides which stage keys share one card row and "the client decides
   nothing about rows". The only way the client can learn the grouping without a copy of
   its own is a key on the plan step, so `PlanStep` gains `row: str` and the server fills it
   from `STAGE_ROW`. The frontend and backend deploy together (owner, 2026-11-04).
2. **Stage derived once, in the harness.** N1 says the hook derives the stage from the
   structlog `component` through `STAGE_BY_REGISTRY`. The harness already knows the
   component, so it derives the stage there and binds it into the liveness context
   (`task_liveness(task_id, stage=...)`); the hook reads the bound stage. Same mapping,
   one place, and the loops need not name their stage.
3. **`stage.completed.counts`** (public interface, additive; not on G1's list). N17 says the
   count keys are chosen per stage on the server and the client has no copy; the first build
   put a copy of `STAGE_COUNTS` in the client (the frontend-designer flagged it), so the frame
   now carries `counts: [{value, noun}]` and the client renders them as given. The mock keeps a
   copy of the table to build its frames (a private fixture). Spec table updated.
4. **Grouped stages share a label.** `acquire` and `screen` both carry "Searching and
   screening", `classify` and `appraise` both "Categorising", so every surface that shows
   a stage label (the strip, the task list, the sidebar line) shows the row's name.

### Open proposals from the frontend passes (for the polish cycle and the owner)

- The strip shows the writer's whole section line while writing; a short form ("Section 3 of 7")
  needs the server to ship one or the client to cut at the first middot.
- The built longlist view takes over when the walk ends (its own header, themes collapsed); keep
  the watched rows in place, or open the themes expanded after a watched build.
- Link the longlist's row names to the option card once the longlist read exists.
- `STAGE_ROW` and `STAGE_COUNTS` have no backend coverage test of their own yet (the vocabulary
  test covers labels and blurbs; the route-step verb test covers verbs).
- `planStart.ts` `START_SEARCH_CLASS` (the plan document's own Start button) could move to
  `Button variant="start"`.
- Add a `role` to `ArtefactSectionSkeleton` so key findings is not recognised by index and
  title; add a phase key to the writer tick so the client does not compare the server's text
  against "Writing".
- The `funnel` query does not refresh on ingest ticks (only evidence and landscape).

### Knowledge candidates (014 retro)

- Codex's sandbox has no Postgres and no localhost sockets (known), and the workspace
  spend cap can end a job mid-apply with no file list: `git status` after every Codex job,
  and every Codex partial needs a finishing brief that names what was found applied.
- A streamed strict `json_schema` response delivers `prose` incrementally on Bedrock; a
  streamed forced tool call delivers its arguments in one burst at the end (probe 1 vs 2).
- A pool thread runs a `Future` done-callback in an empty context: a callback that reads a
  contextvar (the bound task and stage) must carry the submitting thread's context with it
  (`core/done_callbacks.py`), or it publishes nothing in production and everything in a test.
- A new route step needs three rows, not one: `[steps]`, the per-route override, and
  `CACHE_MODES`; a missing cache-mode row raised inside the streamed call's broad `except`, so
  every streamed turn fell back to the forced tool call silently. A test now pins the cache
  table against the steps table.
- A frontend-designer run that must also take screenshots of transient mock states runs out of
  turns (150) before reporting; the screenshot round is better as its own brief.
- Tests that never ask for the `engine` fixture depended on an earlier test migrating the
  worker's database; adding tests reshuffled the order and exposed it (`conftest` now migrates
  once per worker before any test).
- The hub's queue drain: the SSE loop took one tick per 0.4 s poll; with deltas it must
  drain the whole queue per poll or the 32-slot queue evicts prose.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md), listed at step 8.
