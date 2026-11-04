# Implementation plan: 058-perceived-latency

> Status: **draft 2, 2026-11-04, revised from contract revision 2; unconfirmed until the
> owner re-approves the contract and the plan-stage adversarial review runs.** (Draft 1 was
> committed before the contract review finished; the review's finding 5 names that, and this
> draft replaces it.) Contract: [contract.md](contract.md) revision 2. Rubric:
> [rubric.md](rubric.md). Design annex: [design-annex.md](design-annex.md) version 4. Terms, needs (N1 to N26), decisions (D1 to
> D14), gates (G1 to G7) and spec items (S1 to S5) are defined in the contract and not
> restated here. Executor routing follows `docs/agentic-ops/harness.md` § Agent-side model
> routing, the owner's rulings of 2026-09-04 (judgment-bearing build work to a reasoning
> model, mechanical volume to `fast-worker`, probes to `builder`) and 2026-11-04 (any
> delegated frontend work to `frontend-designer`; copy and direction stay with the lead;
> polish passes per task-cycle-build § Step 5b). The build runs in a fresh conversation
> with task-cycle-build, opening on Phase 0; the polish passes (Phase 9) run in their own
> conversation.

## Context

What the user sees today and what each phase changes (contract § Goal; the measured facts
are in `research/exp-event-gaps-and-bands.md`):

| Moment | Today | After | Phase |
|---|---|---|---|
| Any stage running | the stage name and a static dot; counts only for full-text reading | one plain line of activity with honest counts, moving while calls complete; per-stage times | 1, 5 |
| Writing a section (p50 26 s, p90 108 s per section) | nothing until the section is checked and repaired | prose streams in; the research turns show as lines; a failed sentence blurs and settles | 2, 5 |
| The planner's turn (3 to 12 s) | "Planning…" then the whole reply | the reply streams; "Drafting the plan"; the opening turn in the Agent tab | 3, 6 |
| Result tab before writing | "Preparing your results" or the old report | the run strip, the question, one sentence; a re-run notice | 5 |
| Any other tab | the animated logo | the run strip (status only); the sidebar with the real run; tab dots; title on completion | 5 |
| A choice in the plan or a check-in | buttons that sometimes only pre-fill; model-written "1 of 3"; a chip with no question | one radio shape, a client stepper, inputs in the card, the question shown | 3, 6 |
| Options scoping longlist build (median 14 min) | the Result tab shows the baseline until clustering | the provisional longlist from the first minute, filling in waves | 4, 7 |
| Progress copy | four client copies, five disagreements, hidden counts | one server source in the plain voice; the spec lists every key | 1, 5 |

Phase order: backend frames and copy first (phases 1 to 4), so every frontend phase builds
on real frames and the mock API mirrors them; then the frontend in three phases by surface;
then the mock API and journeys; then polish; then measurement and staging. Each backend
phase is independently testable and lands behind additive interfaces, so the frontend can
start on Phase 5 as soon as Phase 1 and 2 have landed if the build conversation prefers
overlap (the plan does not require it).

## Decisions taken in this plan

- **P1. The silent-gap measure counts ticks.** Ticks are not persisted, so the measure
  captures the SSE stream during each fixed-question run with a small client that logs every
  frame and tick with a timestamp (`scripts/stream_capture.py`, new, read-only against the
  API). `scripts/stage_walls.py` gains a `--capture` mode that computes the gaps from that
  log. Before-and-after runs use the same capture. (N25)
- **P2. The verb table is one dict beside `STAGE_PRESENTATION`**, keyed by route step id,
  with a test that every `[steps]` key has an entry. No step publishes a tick without a verb.
  (N1, N17)
- **P3. Counts come from the loops, verbs from the wrapper.** Each loop publishes its own
  count with a unit from a completion callback at the submit site, through
  `liveness.publish_progress(stage, done, total, unit)`; the wrapper's hooks publish only the
  verb and liveness, and the hub repeats the current tick as a heartbeat every 10 s while a
  call is open. (N1, N2; review findings 4 and 6)
- **P4. The streamed final turn is a new backend method**, `section_emit_stream`, beside
  `section_turn`; the loop calls it on the forced-emit turn; the fallback calls `section_turn`
  with the forced tool as today. The route step for it is `synthesise_section_emit` (its own
  step per the one-step-per-call-site rule), inheriting the section turn's timeout as a
  between-chunks bound and `max_retries = 0`. (N6, D1)
- **P5. Delta frames flow through the tick hub**, not the event log: the writer publishes
  `section_delta` and `section_revising` as hub messages with a `kind`; the SSE encoder maps
  the kind to the frame type. The hub keeps the current section draft per run and sends it
  as one `replace` delta to a connecting client. One ephemeral channel, two frame types.
  (N4, N7, D2; finding 1)
- **P6. The reducer keeps a `draft` per section** (the concatenated deltas plus the marked
  spans) separate from `prose` (from `section_completed`); replay rebuilds `prose` only, so
  the replay-idempotence tests stay as they are. (N7, N8)
- **P7. The planner route streams**, with the chat route's event shape and its rules (auth
  before headers, one terminal event, the turn completes without the client); the JSON
  response is replaced. (N9; owner: deploy together, replace)
- **P8. A new options read**, `GET /tasks/{id}/options`, lists the task's option rows with
  each one's child search status and count, under the longlist read's predicate; `/longlist`
  is untouched. (N22; findings 2, 13, 14)
- **P9. No client-side join.** The options query refreshes on child `run.status` and
  `stage.completed` frames; the reducer keeps dropping child stage frames; `RunOut` does not
  change. (N23; finding 13)
- **P10. The sidebar receives the stream by props**, from the same provider the Agent tab
  uses (`RunStreamProvider` already mounts once per task), so there is one connection. (N13)
- **P11. Copy is written by the lead in one pass** at Phase 1 (labels, blurbs, verbs, count
  keys, the Options scoping blurbs) and committed as the server table; the annex's copy is
  the input. Agents never write user-facing copy.
- **P12. No fast-tier gate.** The writer runs on the standard tier, where the full strict
  schema is proven; the fast tier is noted as unverified for this call shape. (N6; owner)
- **P13. Wall time rides the terminal event.** The runner puts `wall_clock_s` in the
  `component.completed` payload, computed before the event, so the live tail never projects
  a null; `component.timing` stays for the per-stage anatomy. (N5; finding 7)

## Owner items (to rule at the plan gate)

1. **Phase order:** backend first (phases 1 to 4) then frontend (5 to 7), as above, or
   vertical slices per surface. The plan recommends backend first for the mock API's sake.
2. **The streamed step's timeout:** inherit the section turn's 25 s on bedrock as the
   between-chunks bound (plan), or set its own value from the first measured runs.
5. **The options read's access grade:** the longlist read's readable/public predicate
   (contract N22, the plan's assumption), or owner and members only for rows that are still
   being built.
3. **Polish budget (D11):** three owner rounds at build end and three after review, as
   contracted, or fewer.
4. **Staging run timing (G7):** after Phase 10 on the branch, before the PR (plan), or
   after merge as 057 did.

## Phases

Gate legend: **full** = `make verify`; **fast** = `make verify-fast`. Mandatory full gates:
build-open, after Phase 2 (prompt hash and types), after Phase 5 (the frontend core), the
step-6 exit. Others fast.

### Phase 0 — Build-open baseline and measurement tools (N25; P1)
- `make verify` green on the branch (full). Record the laptop's load.
- `scripts/stream_capture.py` (builder): connects to `/events` with a dev token, logs
  frames and ticks with timestamps to JSON; `stage_walls.py --capture` computes silent gaps
  (count, share of active time, by stage), time to first delta and to first completed
  section.
- Baseline: the four fixed questions on the laptop, `bedrock`, streams captured (lead runs;
  owner's go on cost, about $1 to $3 per run).
- Commit on fast.

### Phase 1 — Copy, tick shape, coalescer, wrapper hook, honest totals (N1, N2, N4, N17, D2, D4, S1, S2; P2, P3)
- `api/contract/sse.py`: the reshaped tick (one field set; the ingest-only fields removed)
  and the ingest stage moved onto it (codex); `make openapi-sync`.
- `core/liveness.py`: coalescer (500 ms per task and stage, latest wins), the 10 s in-flight
  heartbeat, last-tick and draft memory keyed by run with clearing, TTL and a bound, the
  `dropped` counter, `publish_progress(stage, done, total, unit)`, a `publish_delta` path for
  Phase 2 (codex).
- `core/tracing.py`: `before`/`after` hooks in `traced_attempts` publishing the verb and
  liveness through the coalescer with the stage from the structlog component (codex).
- `runtime/runner.py`: `wall_clock_s` in the `component.completed` payload (P13) (codex).
- `api/stage_vocabulary.py`: the single copy table: labels, blurbs, verbs per step, count
  keys per stage, in the plain voice (lead, P11); the test that every key and step is
  covered (fast-worker).
- N2 completion-callback counts with units across the stages named in
  `research/grounding-per-item-loops.md`; the option-search join publishes with the task id;
  the fetch notes drop the `acquire` label (fast-worker from the checklist, codex for the
  join loop).
- SSE snapshot sends the last ticks and the current draft after replay (codex).
- Spec: S1 (19 keys) and S2 (tick fields) in `web-api.md` with a spec-log line (lead).
- Gate: full (types regenerated; `make drift-check`). Commit.

### Phase 2 — Streaming backend (N3, N6, N7 backend, D1, D3, G2, S3; P4, P5, P12)
- `synthesis_backend.section_emit_stream` with the strict `json_schema` request,
  `include_usage`, delta publishing with `mode`, the once-only fallback (which publishes an
  empty `replace`) and its counter; the loop's forced-emit turn calls it; the test that the
  decoded delta text equals `parsed.prose` across escapes and chunk splits (codex).
- `section_revising` published from `_section_claims` with the failed spans before the
  repair call (codex).
- `run_section_loop` gets `on_tool_start`; the writer's section and action lines; the
  verbs for key findings, Sources foot, case studies, notes, intro (codex).
- `model_routes.toml`: `synthesise_section_emit` step on both routes (lead).
- Prompt hash: `section_prompt.py` changes only in the request builder; re-pin with the
  diff recorded (lead).
- Probe (builder): the cache-cost delta on one section before and after.
- Frames in `api/contract/sse.py` and the encoder; S3 in the spec (codex, lead).
- Gate: full. Commit.

### Phase 3 — Planner streaming and planner fixes (N9, N10 backend, N18 backend, N20 backend, S4 part; P7)
- `POST /task-agent-turns` streams for both profiles with the chat route's rules, replacing
  the JSON response; the opening turn no longer runs inside task creation;
  `TaskAgentTurnOut.question` (codex).
- `task_agent_scoping.py` part ids gain `who_can_act` and `your_options`; one time-band
  table shared by the preset prompt and `task_plan.TIME_BANDS`; `longlist_turns.py` replies
  without asterisks (fast-worker; lead reviews the copy).
- Gate: fast. Commit.

### Phase 4 — Scoping backend reads (N15 backend, N22, N23 backend, S4 rest, S5; P8)
- `TaskOut.active_run.stage` and `stage_label` from the parentless walk; `GET /tasks/{id}/options`
  with the child search status per option, tenancy through the longlist read's predicate and
  the three tenancy tests (codex).
- Spec S4 and S5 (lead).
- Gate: fast; `make drift-check`. Commit.

### Phase 5 — Frontend core: store, card, Result tab, strip, sidebar, tabs (N5, N7 frontend, N8, N11 to N16, N21 frontend; P6, P9, P10)
- 5a plumbing (fast-worker, from the contract's needs and the regenerated types): reducer
  cases for the tick fields and heartbeats, deltas with `mode`, revising spans, stage start
  times, the per-section `draft`; `sseFrame.ts`; the provider's run status and stream passed
  to the sidebar; query invalidation rules (ingest ticks throttled, child frames refresh the
  options query) (N16, N23).
- 5b surfaces (frontend-designer, with the annex as authority): card C with the activity
  line, per-stage times and the 120 s line; the Result tab's live body (placeholders, action
  line, streaming prose, blur and settle, key-findings note, footer states); the three
  pre-writing states; the run strip (status only) with the paused state; the sidebar's run
  line, thread tail, check-in and lock; tab dots; the title; the task-list row; the Plan
  control and Escape; the mounted reconnecting banner; the Sources default filter. The client
  vocabulary and its copies are deleted (N17).
- Lead: copy check on every surface; a screenshot round on the live dev app.
- Gate: full. Commit.

### Phase 6 — Planning conversation and check-ins (N18, N19, N20 frontend, D10)
- frontend-designer: the stepper, the part card's radio shape and in-card inputs, settled
  lines, the plan card's start for both capabilities, the Agent tab's streaming turn and
  "Drafting the plan", the check-in card and the "You chose" line from the resolved frame,
  the card's PAUSED state, plan edits held in the store.
- Gate: fast. Commit.

### Phase 7 — Scoping Result tab during the build (N24, N23 frontend, D9)
- frontend-designer: the longlist during the build with per-row search status from child
  frames, stage lines, the fold, new rows, waves, shortlist marks; no qualifier word.
- Gate: fast. Commit.

### Phase 8 — Mock API and journeys (N26)
- fast-worker: the mock turn returns parts and suggestions; a real check-in kind and
  trigger; child frames and ticks; delta and revising frames; the scoping scenario's missing
  stages.
- fast-worker, then lead review: both e2e journeys assert the annex's states, including a
  reload mid-run and the paused strip.
- Gate: full. Commit.

### Phase 9 — Polish passes (D11; task-cycle-build § Step 5b), own conversation
- Agent pass: frontend-designer against the annex on the live dev app; fixes within the
  annex; copy and direction proposals to the lead.
- Owner pass: up to three rounds; each round's rulings into the annex's polish log; commits
  on fast; the owner's sign-off recorded in `verification.md`.

### Phase 10 — Measurement and staging (N25, G7)
- The four fixed questions on the laptop with capture (lead); the N25 table before and
  after, read from saved results; the fallback count; the Luna and Terra strict results; the
  cost delta per report (builder computes from Langfuse as in
  `research/exp-streaming-cache-cost.md`).
- Staging deploy from the branch and one run of each capability with capture and screenshots
  (owner item 4 decides before or after the PR).
- Gate: full (step-6 exit). `verification.md` complete. Commit.

### Step-6 exit — lead
`make verify` green; `verification.md` complete with the measures, the screenshots, the
polish log, the prompt-hash diff and the spec-log lines; stop. The review runs in a fresh
conversation with task-cycle-review (its design lane and second polish round included).

## Executor summary

| Executor | Work |
|---|---|
| lead | copy (Phase 1); route step and prompt re-pin (2); spec items; live runs and captures (0, 10); screenshot rounds; owner-facing reads; adjudication |
| codex | coalescer, heartbeat, draft memory, hooks, snapshot, wall time in the terminal event, the reshaped tick (1); streamed turn, revising frame, loop callback, decoded-equality test (2); the streamed planner route and question (3); the options read and `stage_label` (4) |
| fast-worker | copy-coverage test and loop registrations (1); planner fixes (3); store plumbing (5a); mock API and journeys (8) |
| frontend-designer | surfaces (5b, 6, 7); the agent polish pass (9) |
| builder | capture tool and gap measure (0); cost delta (2, 10) |

Every `lead` mark above is copy, a prompt-adjacent edit, a spec edit, a live run or a
judgement call; none is typing a delegable spec.

## Out of this slice

Cancel (D7), computed bands (D6), telemetry (D13), email (D14), per-option reading counts
and per-option profile waves (D9), the section proposal's place (D12), storing pre-repair
text (D3), the Responses API move, the chat route. Each is a seam in `docs/deferred.md` at
step 8.
