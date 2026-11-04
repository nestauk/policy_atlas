# Implementation plan: 058-perceived-latency

> Status: **approved by the owner 2026-11-04 (Shabeer Rauf), draft 3, with the three owner items ruled as recommended: mock before the frontend; the streamed turn inherits the section turn's 25 s between-chunks bound; the staging baseline is captured before the PR and the "after" lands post-merge as a follow-up evidence commit.** Draft 2 was reviewed
> read-only by the Codex lane (13 findings: two blockers on regeneration sequencing and the
> staging baseline, ten material, one minor; the record stays local under `research/`); every
> finding is folded here. Contract: [contract.md](contract.md) revision 2, approved
> 2026-11-04. Rubric: [rubric.md](rubric.md). Design annex: [design-annex.md](design-annex.md)
> version 5. ADR: [0044](../../adr/0044-live-activity-streamed-sections-one-copy-source.md),
> Proposed until this gate. Terms, needs (N1 to N26), decisions (D1 to D15), gates (G1 to
> G7) and spec items (S1 to S5) are defined in the contract and not restated here. Executor
> routing follows `docs/agentic-ops/harness.md` § Agent-side model routing and the owner's
> rulings of 2026-09-04 (judgment-bearing build work to a reasoning model, mechanical volume
> to `fast-worker`, probes to `builder`) and 2026-11-04 (any delegated frontend work to
> `frontend-designer`; copy and direction stay with the lead; polish passes per
> task-cycle-build § Step 5b). The build runs in a fresh conversation with task-cycle-build,
> opening on Phase 0; each polish cycle (Phase 10 and the post-review cycle) runs in its own
> conversation.

## Context

What the user sees today and what each phase changes (contract § Goal; measured facts in
`research/exp-event-gaps-and-bands.md`):

| Moment | Today | After | Phase |
|---|---|---|---|
| Any stage running | the stage name and a static dot; counts only for full-text reading; a duplicate Screening row | one plain line of activity with honest counts and heartbeats; per-stage times; one Screening row | 1, 6 |
| Writing a section (p50 26 s, p90 108 s) | nothing until the section is checked and repaired | prose streams in; research turns show as lines; a failed sentence blurs and settles | 2, 6 |
| The planner's turn (3 to 12 s) | "Planning…" then the whole reply | the reply streams; "Drafting the plan"; the opening turn in the Agent tab | 3, 7 |
| Result tab before writing | "Preparing your results" or the old report | the run strip, the question, one sentence; a re-run notice | 6 |
| Any other tab | the animated logo | the run strip (status only); the sidebar with the real run; tab dots; the title on completion | 6 |
| A choice in the plan or a check-in | buttons that sometimes only pre-fill; a model-written "1 of 3"; a chip with no question | one radio shape, a client stepper, inputs in the card, the question shown | 3, 7 |
| Options scoping longlist build (median 14 min) | the baseline until clustering | the longlist from the first minute, filling in waves | 4, 8 |
| Progress copy | four client copies, five disagreements, hidden counts | one server source in the plain voice; the spec lists every key | 1, 6 |

Phase order: backend contract phases first (1 to 4), each ending with type regeneration, so
the mock fixtures (5) and every frontend phase (6 to 8) build on real frames; journeys (9);
the first polish cycle (10); measurement and staging (11); exit. Phase 5 lands the mock
before any frontend surface so the `frontend-designer` can self-check transient states.

## Decisions taken in this plan

- **P1. The silent-gap measure counts only what the page can show.** The capture client
  (`scripts/stream_capture.py`, new, read-only against the API with a dev token) logs every
  durable frame and every `tick` frame (heartbeats included) with a timestamp; transport
  keep-alive comments are logged but excluded from the gap measure. `stage_walls.py
  --capture` computes gaps over the active-run interval (first `run.status` to the terminal
  `run.status`, pauses excluded), by stage. A healthy run is one with no model-call timeout
  and no streamed-turn retry in its trace (read from Langfuse by step). `dropped` is a
  monotonic per-task counter; the measure reports its delta over the run. Baseline runs on
  the old tick shape are mapped by the capture client (`note`/`fetched`/`parsed` read as a
  tick with no `unit`). (N25; review finding 9)
- **P2. The verb table is one dict beside `STAGE_PRESENTATION`**, keyed by route step id,
  with a test that every `[steps]` key has an entry; the same table holds the card's row
  grouping and the count keys per stage. (N1, N17)
- **P3. Counts come from the loops, verbs from the wrapper.** Each loop publishes its own
  count with a unit from a completion callback at the submit site through
  `liveness.publish_progress(stage, done, total, unit)`; the wrapper's hooks publish only
  the verb and liveness; the hub repeats the current tick as a heartbeat every 10 s while a
  call is open. (N1, N2)
- **P4. The streamed final turn is a new backend method**, `section_emit_stream`, beside
  `section_turn`; the loop calls it on the forced-emit turn; the once-only re-run calls
  `section_turn` with the forced tool. Route step `synthesise_section_emit` on both routes,
  inheriting the section turn's timeout as a between-chunks bound, `max_retries = 0`. (N6)
- **P5. Deltas, revising spans and ticks share the hub.** The writer publishes
  `section_delta` and `section_revising` as hub messages with a `kind`; the encoder maps the
  kind to the frame type. The hub keeps, per run, the last tick per stage and the current
  section draft, cleared on stage and run end and on a new run, with a 10-minute TTL and a
  per-task bound. (N4, N7, D2)
- **P6. The hub gains an atomic `subscribe_with_snapshot`.** Under the hub's lock it returns
  the subscriber queue and the cached state (last ticks, draft) in one step, so nothing
  published in between is lost or duplicated. The SSE route calls it after the durable
  snapshot and the re-authorisation, before yielding the replay; cached state is yielded
  after the replay. A race test publishes between the durable snapshot, the subscription
  and the cached-state emission. (N4; finding 8)
- **P7. The reducer keeps a `draft` per section** (deltas plus marked spans) separate from
  `prose`; replay rebuilds `prose` only. (N7, N8)
- **P8. The planner route streams** with the chat route's event shape and rules (auth before
  headers, one terminal event, the turn completes without the client; a once-only traced
  retry before the first token); the JSON response is replaced. (N9)
- **P9. A new options read**, `GET /tasks/{id}/options`, under the longlist read's predicate;
  `/longlist` untouched. The client refreshes it on child frames; no client-side join. (N22,
  N23)
- **P10. The sidebar receives the stream by props** from the provider the Agent tab uses, so
  there is one connection. (N13)
- **P11. Copy is written by the lead in one pass** at Phase 1 and committed as the server
  table; the annex's copy is the input. Agents never write user-facing copy.
- **P12. Wall time rides the terminal event.** The runner puts `wall_clock_s` in the
  `component.completed` payload (internal input to `stage.completed.seconds`, not a new
  public field); `component.timing` stays for the anatomy. (N5)
- **P13. Regeneration after every contract phase.** `make openapi-sync` then `make
  drift-check` close Phases 1, 2, 3 and 4; the last backend full gate follows Phase 4's
  regeneration. (finding 1)
- **P14. Prompt hashes are re-pinned in the phase that changes the file**, with the diff
  recorded: `section_prompt.py` in Phase 2, `task_agent_prompt.py` (the time-band table) in
  Phase 3; both phases run `make prompt-guard` at their gate. (G2; finding 3)
- **P15. Codex briefs are one seam each**, with a file boundary and a named test command
  (§ Briefs). Phases list the seams; the build conversation dispatches them one at a time
  or in parallel where the files do not overlap. (finding 7)
- **P16. The staging baseline is captured before merge, on the staging that exists now.**
  Staging deploys only from `dev` (057 plan), so the "before" is a capture of the four fixed
  questions on today's staging, run by the lead with the owner's go before the PR; the
  "after" runs after merge and deploy, and lands as a follow-up evidence commit, as 057 did.
  (N25, G7; finding 2; owner item 3 below confirms it)

## Owner items (ruled 2026-11-04: all three as recommended)

1. **Mock-before-frontend order (Phase 5 before 6 to 8).** Recommendation: yes. Consequence
   of no: the `frontend-designer` cannot reproduce mid-stream, reload, repair, paused or
   child-run states deterministically, and the journeys in Phase 9 force rework of three
   frontend phases.
2. **The streamed step's between-chunks timeout.** Recommendation: inherit the section turn's
   25 s on bedrock. Consequence: a chunk gap over 25 s re-runs the turn without streaming
   once; Phase 11 reports how often that fired, and the value moves if it is false-positive.
3. **Staging evidence timing (G7).** Recommendation: P16, baseline now, "after" post-merge
   as a follow-up commit. Consequence: the PR carries the laptop before-and-after and the
   staging baseline; the staging "after" lands within a day of the deploy. Alternative: a
   branch deploy to staging, which the deploy script does not support today.

## Gate map (binding)

| Boundary | Gate | Why |
|---|---|---|
| Build-open | full | baseline (spine) |
| After Phase 1 | full + `drift-check` | ingest-adjacent publishing; first regeneration |
| After Phase 2 | fast + `prompt-guard` + `drift-check` | re-pin; frames regenerated |
| After Phase 3 | fast + `prompt-guard` + `drift-check` | re-pin; planner types regenerated |
| After Phase 4 | full + `drift-check` | last backend regeneration |
| After Phase 5 | fast | mock only |
| After Phases 6, 7, 8 | fast each | frontend surfaces |
| After Phase 9 | full | after all frontend phases; journeys |
| After Phase 10 | fast per round | polish commits |
| Step-6 exit (after 11) | full | exit (spine) |

## Phases

### Phase 0 — Build-open baseline and measurement tools (N25; P1)
- `make verify` green on the branch (full). Record the laptop's load.
- builder: `scripts/stream_capture.py` and `stage_walls.py --capture` per P1, with a test on
  a recorded stream fixture (gaps, exclusions, healthy classification, dropped delta).
- lead: the four fixed questions on the laptop, `bedrock`, streams captured (owner's go on
  cost); the staging baseline per P16 if the owner rules so.
- Commit on fast.

### Phase 1 — Copy, tick shape, coalescer, hooks, counts, terminal timing (N1, N2, N4, N5 backend, N17, D2, D4, S1, S2; P2, P3, P5, P6, P12)
Seams (codex, one brief each):
- `core/liveness.py`: the reshaped tick, the 500 ms coalescer, the 10 s heartbeat, the
  run-keyed last-tick and draft memory with clearing, TTL and bound, the `dropped` counter,
  `publish_progress`, `subscribe_with_snapshot` (P6), with the race test.
- `core/tracing.py`: `before`/`after` hooks publishing the verb and liveness; the `before`
  hook records the attempt's input on the generation (N1).
- `api/routers/sse.py` + `api/contract/sse.py`: the reshaped tick, the snapshot ordering of
  P6, the ingest stage moved onto the new fields.
- `runtime/runner.py`: `wall_clock_s` in the `component.completed` payload (P12); the
  live-tail ordering test.
- `api/stage_vocabulary.py`: the `screen_full` guard tests the composed component so the
  full-text screen emits no second row; its progress publishes "reading n of M full texts
  for relevance" on the screen stage (N2).
- `runtime/option_search.py`: the join loop publishes "n of M searches done · k sources so
  far" with the task id (N2, N21).
Mechanical (fast-worker, from `research/grounding-per-item-loops.md` as the checklist):
- completion-callback counts with units in classify, screen stage 2, select, constrain, the
  four clustering engines, sections; "n so far" in acquire and screen stage 1; "Search 2" on a
  second pass; the fetch notes drop the `acquire` label; a retry never moves a count (tests).
Lead:
- the single copy table (labels, blurbs, verbs, count keys, row grouping) in the plain voice
  (P11); the coverage test is fast-worker's.
- Spec S1 and S2 in `web-api.md` with a spec-log line.
Gate: full + `make openapi-sync` + `make drift-check`. Commit.

### Phase 2 — Streaming backend (N3, N6, N7 backend, D1, D3, G2, S3; P4, P5, P14)
Seams (codex, one brief each):
- `synthesis_backend.section_emit_stream`: the strict request, `include_usage`, delta
  publishing with `mode`, the once-only non-streamed re-run with an empty `replace`, the
  counter; the test that decoded delta text equals `parsed.prose` across escapes and chunk
  splits; the fake streaming client.
- `synthesise._section_claims`: publishes `section_revising` with the failed spans before
  the repair call.
- `synthesis_tools.run_section_loop`: `on_tool_start` publishing the section and action
  lines; the model's query normalised (NFC, control characters stripped, 120 characters) in
  the publisher (N3); the verbs for key findings, the Sources foot, case studies, notes, intro.
- `api/contract/sse.py` + encoder: the two ephemeral frames.
Lead: `model_routes.toml` step `synthesise_section_emit` on both routes; the
`section_prompt.py` request-builder change and the hash re-pin with its diff; spec S3.
builder: the cache-cost delta on one section before and after.
Gate: fast + `make prompt-guard` + `make openapi-sync` + `make drift-check`. Commit.

### Phase 3 — Planner streaming and planner fixes (N9, N10, N18 backend, N20 backend, S4 part; P8, P14)
Seams (codex): the streamed `POST /task-agent-turns` for both profiles with the chat route's
rules and the once-only pre-token retry; task creation no longer runs the first turn;
`TaskAgentTurnOut.question`; the stored turn's suggestions returned so chips survive a
reload (N10).
fast-worker: `task_agent_scoping.py` part ids gain `who_can_act` and `your_options`; one
time-band table shared by the preset prompt and `task_plan.TIME_BANDS`; `longlist_turns.py`
replies without asterisks; `baseline_gate.baseline_settings()` gains the risk appetite key
(N19). Lead reviews the copy and re-pins `task_agent_prompt.py` with its diff.
Gate: fast + `make prompt-guard` + `make openapi-sync` + `make drift-check`. Commit.

### Phase 4 — Scoping and task reads (N15 backend, N22, N23 backend, S4 rest, S5; P9)
Seams (codex): `TaskOut.active_run.stage` and `stage_label` from the parentless walk;
`GET /tasks/{id}/options` with the child search status per option, the longlist read's
predicate, and the three tenancy tests.
Lead: spec S4 and S5.
Gate: full + `make openapi-sync` + `make drift-check`. Commit.

### Phase 5 — Mock contracts and fixtures (N26 first half)
fast-worker, from the regenerated types and the annex's scenes: the mock turn returns
parts and suggestions and the question; a real check-in kind and trigger; child walk frames
and ticks; the reshaped tick; delta and revising frames with scenario controls
(`?mockScenario=`); the options read; the paused strip state; the scoping scenario's
missing stages and the baseline-gate sequence. The journeys' assertions wait for Phase 9.
Gate: fast. Commit.

### Phase 6 — Frontend core: store, card, Result tab, strip, sidebar, tabs (N5, N7, N8, N11 to N16, N21 frontend; D5, D8, D15; P7, P10)
Seams (codex, one brief each):
- `api/sse.ts`: the 45 s read-inactivity watchdog and reconnect at the cursor (N15).
- `store/reducer.ts` + `types.ts`: tick fields and heartbeats, deltas with `mode`, revising
  spans, stage start times, the per-section `draft`, replay idempotence (P7).
- `store/useRunStream.tsx`: query invalidation (ingest ticks throttled to 5 s; child frames
  refresh the options query); run status and stream passed to the sidebar (P10).
fast-worker: `sseFrame.ts` and generated-type wiring; the deletion of the client
vocabulary and its copies (N17).
frontend-designer, with the annex as authority, one brief per surface: card C with the
activity line, per-stage times and the 120 s line; the Result tab's live body
(placeholders, action line, streaming prose, blur and settle with the accessible draft
state, key-findings note, footer states); the three pre-writing states; the run strip
(status only, orange paused state, green done link); the sidebar's run line, thread tail,
check-in and lock; tab dots and the title; the task-list row with the server label; the
Plan control and Escape; the mounted reconnecting banner; the Sources default filter; the
report sheet's shadow; D15's single orange "waiting on you" colour (the yellow chip and
glow go).
Lead: copy check on every surface; one screenshot round on the live dev app.
Gate: fast. Commit.

### Phase 7 — Planning conversation and check-ins (N18, N19, N20 frontend, D10, D15)
frontend-designer: the stepper, the part card's radio shape and in-card inputs, settled
lines, the plan card's start for both capabilities as `Button` props, the Agent tab's
streaming turn and "Drafting the plan" with Start disabled while a turn streams, the
check-in card (no eyebrow, one stop, the orange rule only), "You chose" from the resolved
frame, the card's PAUSED state, plan edits held in the store, the risk appetite on the gate
card, one Label class across the three components.
Gate: fast. Commit.

### Phase 8 — The longlist during the build (N24, N23 frontend, D9)
frontend-designer: the building state with per-row search status from the options read,
stage lines, the fold, new rows, waves, shortlist marks, no qualifier word; the theme
heading's meta wrap in `ArtefactOutline.SectionDisclosure`.
Gate: fast. Commit.

### Phase 9 — Journeys (N26 second half)
fast-worker, then lead review: both e2e journeys assert the annex's states, a reload
mid-run, the paused strip, and the scoping gate sequence (baseline → pause → gate → no
option rows → continuation → suggest → options read).
Gate: full. Commit.

### Phase 10 — First polish cycle (D11; task-cycle-build § Step 5b), own conversation
- Agent pass: `frontend-designer` against the annex on the live dev app; fixes within the
  annex; copy and direction proposals to the lead.
- Owner pass: up to three rounds (G6); one annex polish-log row and one fast-gated commit
  per round; the owner's sign-off recorded in `verification.md`.

### Phase 11 — Measurement and staging evidence (N25, G7; P1, P16)
- Lead: the four fixed questions on the laptop with capture; the N25 table before and after
  from saved results; the retry count; the Terra strict result; builder: the cost delta per
  report from Langfuse as in `research/exp-streaming-cache-cost.md`.
- Staging per P16: the baseline captured before the PR; the "after" after merge and deploy
  as a follow-up evidence commit named in `verification.md`.
- Gate: full (step-6 exit). `verification.md` complete. Commit.

### Step-6 exit — lead
`make verify` green; `verification.md` complete with the measures, screenshots, the polish
log, the prompt-hash diffs and the spec-log lines; stop. The review runs in a fresh
conversation with task-cycle-review (its design lane included); **the second polish cycle
(agent pass, then owner pass) runs in its own conversation after the review's fixes land**,
with one annex-log row and one fast-gated commit per round, before step 8.

## Briefs (P15)

Each Codex brief names: one seam (the files above), the contract need and annex section,
the tests that define done (`uv run --project backend pytest <path> -q` or `pnpm vitest run
<path>`), and "no other files". Fast-worker briefs name the checklist file and the exact
repetitive shape. `frontend-designer` briefs name the annex scene, the component files and
the screenshot pair to produce. The build conversation keeps a dispatch log in
`verification.md` § Review handoff with the brief, the executor and the result.

## Executor summary

| Executor | Work |
|---|---|
| lead | copy table (1); route step, prompt re-pins, spec items (1 to 4); live runs and captures (0, 11); screenshot rounds (6); owner-facing reads; adjudication |
| codex | one brief per seam: hub, tracing hooks, SSE snapshot, terminal timing, screen_full guard, join loop (1); streamed turn, revising frame, loop callback (2); planner stream and question (3); task and options reads (4); SSE watchdog, reducer, invalidation (6) |
| fast-worker | loop counts (1); planner fixes (3); mock fixtures (5); type wiring and vocabulary deletion (6); journeys (9) |
| frontend-designer | surfaces (6, 7, 8); the agent polish passes (10, post-review) |
| builder | capture tool and gap measure (0); cost delta (2, 11) |

Every `lead` mark is copy, a prompt-adjacent edit, a spec edit, a live run or a judgement
call; none is typing a delegable spec.

## Out of this slice

Cancel (D7), computed bands (D6), telemetry (D13), email (D14), per-option reading counts
and per-option profile waves (D9), the section proposal's place (D12), storing pre-repair
text (D3), the Responses API move, the chat route's own resume, the wider label-class and
grey-shadow sweeps. Each is a seam in `docs/deferred.md` at step 8.
