# Task contract: 058-perceived-latency

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status: revision 2, re-approval pending.** Revision 1 approved 2026-11-04 · Shabeer Rauf (owner), with three gate rulings folded (two routes to the agent; per-stage timings; no labels that restate the page; annex v3). The contract-stage adversarial review the same day ([adversarial-review-contract.md](adversarial-review-contract.md), Codex, 18 findings) is folded as revision 2: every finding accepted, some narrowed; the material changes are N1/N2 (counts from loops, heartbeats), N4/N7 (the draft replays on connect), N9 (streaming by content negotiation, not a breaking change), N22/N23 (an options read replaces the provisional longlist and the child-walk join), N25 (the measure defined so it is falsifiable) and G1 (the complete interface list). **A plan draft was committed before this review finished (finding 5); it is revised from revision 2 and stays unconfirmed until the owner re-approves.** Owner at revision 2 (2026-11-04): the frontend and backend always deploy together, so no compatibility shims and no kept-beside-the-new fields or responses (N9 and D2 revised); the fast-tier strict gate dropped. Branch
> `task/058-perceived-latency`. Design pass done 2026-11-04 in the same conversation under the
> frontend variant of the cycle (PR #113): grounding (nine explorer reports, four research
> notes, seven experiments, all under `research/`, gitignored), a scripted mock
> ([design-annex.md](design-annex.md) version 4, mock
> https://claude.ai/artifact/Xse3bLcA6XhQqxQJFVEwtH version 7, fifteen scenes), five owner
> feedback rounds and an interview that fixed the intent (`research/intent.md`). The owner
> accepted the mock as direction on 2026-11-04 ("broadly looks okay") and expects more
> judgement on the live app; the polish passes carry that. Plan: not yet. ADR: not yet.

## Goal

Make a run never look stuck, and make the report and the plan appear as they are written. A
run shows one plain line of what the model is doing now at every stage, with counts where
the total is honest. Report sections stream to the Result tab as the writer produces them, a
sentence under repair blurs and settles into its new wording, and the planner's reply streams
in the Agent tab. The Result tab, the sidebar and the other tabs stay alive and point at the
run from start to "ready". Options scoping gets the same card, the same streaming of its
baseline, and a longlist that exists from the first minute of its build. Copy for all of this
comes from one place on the server, in the product's plain voice.

Measured today (`research/exp-event-gaps-and-bands.md`, 59 walks since 2026-11-01 on the dev
database): 90% of active run time sits in gaps over 30 s with no new event on the page; a
section takes p50 26 s and p90 108 s from started to completed; the Result tab shows
"Preparing your results" for most of an Evidence search and the previous report during a
re-run. Options scoping's longlist build takes a median 13.7 min (p80 28.3, 42 walks) with the
Result tab empty until clustering.

## Why this is safe to do now

- Durable resume already exists: `event_log` with a per-task sequence on the SSE `id:` line
  and a `?cursor=` reconnect; a reload replays from zero and never cancels a run
  (`research/grounding-progress-sse-pipeline.md` §2–3). This slice adds frames and ticks on
  top; it does not touch the event log's shape.
- Section streaming is proven on the default route: a strict `json_schema` response streams
  prose ahead of claims on Terra and Luna with a small schema, and the app's real
  `SectionProseWire` schema was accepted strict as-is on Terra, the writer's tier
  (`research/exp-bedrock-streaming-probe.md`, probes 2 and 4). The forced
  tool call the writer uses today delivers its arguments in one burst at the end, so the final
  turn changes shape; the research turns keep their tools.
- The cost of that change is measured from 55 reports: median +$0.03 per report at the lower
  bound (3.5% of a $0.91 run), +$0.18 at the ceiling; accepted by the owner
  (`research/exp-streaming-cache-cost.md`).
- Every model call already passes through one wrapper, `traced_attempts`, that sees the step
  name and the task context (`research/grounding-llm-call-sites.md` §2); task 057 recorded a
  `before` hook there as a deferred seam. The section writer's tool loop already has an
  activity callback that chat uses (`on_tool_start`).
- The skeleton and per-section frames exist (ADR 0027); the live Result body already moves
  sections through planned, writing and filled.
- No schema change. Every interface change is additive on the web API and the SSE union.
- Rollback: the streamed final turn falls back to today's forced tool call on any failure
  (D1); ticks are ephemeral and never state-bearing; the frontend reads only frames it knows.

## Deliverable

A pull request where:

1. Every stage of both capabilities shows an activity line while it runs, from coalesced
   ticks published by the model-call wrapper and by the stage loops that know their items;
   the line survives a reload; the dot moves only while updates arrive (N1 to N5).
2. The writer's final turn streams its prose to the Result tab, a failed sentence blurs while
   it is repaired and settles into the new wording, and the planner's reply streams in the
   Agent tab (N6 to N10).
3. The Result tab, the run strip on every tab, the sidebar, the lifecycle tabs and the task
   list show the run and say when it finishes (N11 to N16).
4. Stage labels, blurbs and activity text have one source on the server, in the plain voice,
   and the web-api spec lists every stage key (N17).
5. The planning conversation and the check-in have one shape for a choice, a stepper the
   client computes, and inputs inside the card (N18 to N21).
6. The Options scoping Result tab shows the provisional longlist from the suggest stage, with
   per-option search status, and fills in waves (N22 to N24).
7. `verification.md` holds the before and after silent-gap measure on the fixed questions,
   the time to first prose, the per-report cost delta, the tick rate, live-dev screenshots of
   every changed surface, the polish log, and a staging run (N25, N26).

## Terms

| Term | Meaning |
|---|---|
| **Activity line** | One line of grey text under the in-progress stage row that says what the model is doing now. Fed by ticks. Owned by the running card (`RunningCard.tsx`) and the run strip. |
| **Tick** | The ephemeral SSE frame `tick` (web-api § SSE). Never persisted, never state-bearing, no `id:`. This slice adds fields to it (D2). |
| **Coalesced** | At most one tick per task per 500 ms per stage, carrying the latest values. Server-side, in `core/liveness.py`. The 32-slot subscriber queue and the one-tick-per-poll SSE loop cannot take one tick per model call (`research/grounding-llm-call-sites.md` §6). |
| **Honest count** | "n of M" only where M is known before the loop starts (classify, screen stage 2, select batches, constrain, option searches, clustering assignment batches, sections). Elsewhere "n so far" or a verb with no count (`research/grounding-per-item-loops.md`). |
| **Final turn** | The last turn of a section's tool loop, the one that emits the section. Today a forced `emit_section` tool call; after this slice a streamed strict `json_schema` call with no tools (D1). |
| **Delta frame** | `artefact.section_delta`, ephemeral like `tick`: `{index, text}` appended to the section being written. |
| **Revising frame** | `artefact.section_revising`, ephemeral: `{index, spans: [{start, end}]}`, the code-point spans of the sentences the judge failed, sent before the repair call. |
| **Run strip** | The one-line run status under the lifecycle tabs on every tab but Agent: dot, text, then the Task Agent mark. |
| **Task Agent mark** | The blue diamond (`logo-mark`) as a button. Opens the sidebar in place; below the medium breakpoint it goes to the Agent tab. |
| **Sidebar** | `ChatSidePanel`, the Task Agent beside any non-Agent tab. After this slice it carries the real stream and run status. |
| **Stepper** | "Plan · step 2 of 3 · Scope", computed by the client from the capability's part ids and the parts settled in the transcript. Never model-written. |
| **Part card** | The planner's choice card (`PartCard.tsx`). After this slice: a radio list, the planner's primary option first with its reason under it, inputs inside the card. |
| **Provisional longlist** | The longlist read before a `longlist_result` row exists: the option rows the suggest stage minted, flagged `provisional`. |
| **Child walk** | An option's own evidence search inside the longlist build (`purpose = targeted`, `parent_capability_run_id` set). Runs `acquire` only. |
| **Wave** | A stage that writes every option in one commit (option_profile, constrain, theme): the longlist fills per stage, not per option. |
| **Silent gap** | An interval over 30 s during an active run with no visible change on the run page: no durable frame and no tick. The slice's headline measure (`research/exp-event-gaps-and-bands.md` method). |
| **Fixed questions** | The three Evidence search questions and one Options scoping question of task 056 (`docs/tasks/056-cost-latency/contract.md` O5), run fresh before and after. |
| **Polish pass** | task-cycle-build § Step 5b: an agent pass by `frontend-designer`, then an owner pass on the live dev app; both again after the review stack. Rulings go into the annex. |
| **Annex** | [design-annex.md](design-annex.md): every state, transition and line of copy. The contract cites it by version; looks live only there. |
| **Decided / Leaning / Open** | Decided is settled. Leaning is the recommended choice unless the owner objects. Open means the owner chooses at the named gate. |

## Facts we rely on

Research and experiment notes are under `docs/tasks/058-perceived-latency/research/`
(gitignored). Each line names its note.

- Durable frames are rebuilt from `event_log` on read; ticks are process-local, bounded at
  32 per subscriber, dropped when no client is connected, and lost on reload. The SSE loop
  takes at most one tick per poll (0.4 s) and never ends on run completion
  (`grounding-progress-sse-pipeline.md`).
- The frontend uses its own stage labels (`planVocabulary.ts`) and ignores the server's
  except for unknown stages; a test pins this. Labels exist in four places; 5 of 10
  Evidence search labels differ; 141 count keys never reach a label; the spec lists 10 of
  19 stage keys (`audit-stage-copy.md`).
- Only `ingest` publishes live counts. Every fan-out shares one submit-then-wait pattern
  with no callbacks; the cheapest tick point is the submitted callable
  (`grounding-per-item-loops.md`).
- `traced_attempts` sees every model call's start and end with the step name, the attempt
  and the task and component contextvars; it does not know the item. Fan-out workers
  inherit the contextvars. One tick per model call would be 12 to 24 a second during
  screening (`grounding-llm-call-sites.md` §2, §6).
- The section writer runs serially: research turns of 1.8 to 2.5 s, a writing turn of 7.6
  to 10.9 s, then judge (p99 19.8 s) and repair; `section_completed` is emitted only after
  all of them. Claim ids are minted by position (`s{n}c{m}`) and spans bound as substrings;
  the reader-facing id is a UUID minted at block write. Repair splices text in place and
  stores no original (`grounding-synthesis-emission.md`).
- A streamed call's per-request timeout bounds the gap between chunks and the streamed call
  sits outside the retry loop (task 057 rule for chat).
- The planner's output puts `reply` first; the Agent tab turn endpoint returns it whole; the
  clarifying `question` never reaches the web client; suggestion chips are local state;
  "Plan · 1 of 3" is model-written; two scoping part ids are rejected by the profile; the
  preset and plan-document time bands disagree (`grounding-planning-conversation.md`).
- The sidebar mounts a second Task Agent pane with no run state; its composer is not locked
  during a run; its plan links do not open the plan (same note, §3).
- Suggested options are real `option` rows seconds in, with no read until the longlist
  stage; child walks run `acquire` only and the client cannot map a child to its option;
  clustering keeps suggestion ids and may fold a row; profiles, checks and themes land in
  three commits (`grounding-scoping-result-tab.md`).
- Bedrock Terra prices: $1 per million input, $0.05 cached, $1.25 cache write, $5 output
  (`exp-streaming-cache-cost.md`). The forced tool call does not stream; strict `json_schema`
  does (`exp-bedrock-streaming-probe.md`).
- A cooperative flag stops a walk within one in-flight call; closing the HTTP client does
  not interrupt a call (`exp-cancel-probe.md`). Cancel is out of this slice (D7).

## Read first

- [web-api](../../specs/system/web-api.md) § SSE (lines 673–733: the frame vocabulary, the
  pinned stage keys, the replay rules, the `artefact.*` grain) and § Deployment posture.
- [execution-orchestration](../../specs/system/execution-orchestration.md) § Durability and
  concurrency.
- [provenance-grounding](../../specs/system/provenance-grounding.md) lines 40–47 (flag,
  don't drop) and [ADR 0015](../../adr/0015-prose-first-synthesis-with-span-anchored-claims.md)
  §4–6 (repair rewrites in place).
- [ADR 0027](../../adr/) decision 4 (skeleton and section frames; whole-section grain).
- [Evidence search capability](../../specs/capabilities/evidence-search/capability.md)
  § Output structure and § Check-in points; [Options scoping capability](../../specs/capabilities/options-scoping/capability.md)
  § Pipeline and gates, § Product surface, § Check-in points.
- [plan-as-object](../../specs/system/plan-as-object.md) (time bands).
- `PRODUCT.md` § Product Principles and `DESIGN.md` (committed by PR #113).
- The annex, then `research/grounding-summary.md` and `research/approach-options.md`.

## Numbered needs

| # | Need | Where it lives today | Measure |
|---|---|---|---|
| N1 | **Activity ticks from the model-call wrapper: verbs and liveness only.** A `before` and `after` hook in `traced_attempts` publishes, through the coalescer, the fixed plain verb for the step (the step → verb table beside `STAGE_PRESENTATION`) and a liveness mark; while a call is in flight the hub repeats the current tick as a heartbeat every 10 s, so a long call keeps the line alive and the dot breathing (review finding 4). The hooks carry no counts: calls and items are unlike units and a retry would make done exceed total (finding 6). The stage is derived from the structlog `component` through `STAGE_BY_REGISTRY`. Chat and Agent-tab turns, which run outside a harness, publish nothing. | `core/tracing.py:230-310`; `core/liveness.py`. | A test with a fake hub asserts one tick per 500 ms per stage under a 50-call burst; a 35 s fake call yields heartbeats at most 10 s apart; the verb table covers every step in `model_routes.toml [steps]` (test); a live run shows the screening line moving. |
| N2 | **Honest counts from the loops, with units.** Each loop that knows its total publishes its own progress from a completion callback at the submit site, with an explicit unit: documents (classify, screen stage 2), batches (select, constrain, the clustering assignment rounds of characterise, group, longlist and theme), searches (option searches), sections. The line reads "n of M <unit>" or "batch n of M". Acquire and screen stage 1 show "n so far" plus the round ("Round 2 of up to 3 · screening 61 new abstracts · 107 relevant so far"). The option-search join loop publishes through the hub with the task id directly (it runs outside `task_liveness`). The full-text fetch notes stop being labelled `acquire`. A retried call never moves a count. | `assess/screen.py`, `assess/classify.py`, `corpus/select.py`, `core/clustering_engine.py`, `runtime/option_search.py`, `sourcing/fetch_live.py`. | Per stage, a test asserts the registered total, the unit and the line text; a retry test shows the count unchanged; `research/grounding-per-item-loops.md` is the checklist. |
| N3 | **Writer activity.** `run_section_loop` passes an `on_tool_start` that publishes the section line ("Section 3 of 7 · Costs and funding") and the action line: "Looking for: <the model's `search_chunks.query`, verbatim>", "Reading findings", "Looking up sources", then "Writing", "Checking claims", "Revising n claims". Key findings, the baseline Sources foot, case studies, source notes and the intro publish their own verbs. | `synthesis_tools.py:3575-3619`; `synthesise.py` around 6102–6402. | A test on the loop with a fake backend asserts the sequence; a live run shows the query text in the line. |
| N4 | **Current activity on connect.** The hub keeps, per task and for the current run only, the last tick per stage and the section draft so far (the concatenated deltas; finding 1); the SSE snapshot sends them after the replay, so a reload shows the activity line and the prose written so far. Entries are keyed by run id, cleared when the stage or the run ends and when a new run starts, expire after 10 minutes without an update, and the per-task memory is bounded (finding 9). A client connecting mid-section receives one `section_delta` with `mode: "replace"` carrying the draft, then appends. A process restart loses the draft until `section_completed`, which stays the record. Nothing is persisted. | `core/liveness.py`; `api/routers/sse.py:624-704`. | Tests: a second client mid-stage and mid-section receives the last tick and the draft first; a re-run shows no stale activity; parent and child activity do not overwrite each other; the TTL and the bound hold; reload-mid-section shows the prose so far within one poll. |
| N5 | **The running card** (annex § The running card, direction C): one row per plan step; the activity line under the in-progress row; the dot breathes only while ticks arrive and stops 1.5 s after the last; after 120 s with no tick the line reads "Still working on this step" with no counter; done rows are one line with the chosen count and a link; upcoming rows are names only; "Searching and screening" is one row, "Categorising" absorbs appraise; no "Shortlist →" link; the top line carries RUNNING or PAUSED, the elapsed time and Minimise. **Per-stage timings (owner, gate ruling 2026-11-04):** each done row carries its wall time in grey after its count ("312 found · 118 relevant · 1 min 4 s", from `stage.completed.seconds`), and the in-progress row shows its own elapsed time ticking in the same place, from the `occurred_at` of its `stage.started` frame (the reducer keeps it). The dot breathes while ticks or heartbeats arrive. **Stage times on the live tail (finding 7):** `component.completed` carries `wall_clock_s` in its own payload (the runner computes it before the terminal event), so `stage.completed.seconds` is never null on a live tail; a merged row's time is the interval from its first constituent's `stage.started` to its last constituent's `stage.completed`. The tick `note` is never rendered raw. | `RunningCard.tsx`, `runProgress.ts`, `reducer.ts:117-125`, `types.ts`; `runtime/runner.py:5956-5967`. | vitest on the reducer (tick fields, heartbeats, the 1.5 s stop, the 120 s line, merged-row times) and the card (rows, states); a live-tail ordering test for `seconds`; the mock journey asserts the rows. |
| N6 | **Streamed final turn.** The section loop's final turn is a streamed strict `json_schema` call of `SectionProseWire` with no tools and `stream_options.include_usage`; each prose delta is published as a delta frame; the parsed object continues into `_section_claims` unchanged. The repair, key findings and every research turn keep today's shape. A streamed call sits outside the normal retry loop (057 rule) and its timeout bounds the gap between chunks; its retry is one non-streamed run of the same turn (the forced tool call) on a stream failure (connection, timeout between chunks, parse failure), counted, with an empty `replace` delta resetting the client's draft. The writer runs on the standard tier (Terra), where the full strict schema is proven (probe 4); the fast tier is unverified for this call shape and no writer step uses it (owner, 2026-11-04: no gate). | `synthesis_backend.py:915-1009`; `section_prompt.py:482-494`; `core/openai_client.py`. | A test with a fake streaming client asserts deltas, the final parse, the fallback path and the draft reset; a test proves the accumulated decoded delta text equals `parsed.prose` across escapes and chunk boundaries; the cache-cost delta per report on the fixed questions is recorded (N25). |
| N7 | **Delta and revising frames.** `artefact.section_delta {index, text, mode}` with `mode` `append` or `replace`, and `artefact.section_revising {index, spans}` join the SSE union as ephemeral frames (no `id:`, never replayed); `section_completed` stays the durable record. The hub's draft memory (N4) gives a reconnecting client a `replace` first. The reducer keeps a `draft` per section separate from `prose`; replay rebuilds `prose` only, so the replay-idempotence tests stand. | `api/contract/sse.py`; `api/routers/sse.py:602-621`; `reducer.ts`; `sseFrame.ts`. | Contract test for the frames; reducer tests for append, replace, mark, completion, and a replay with no deltas; disconnect and reload after n chunks then more chunks; the generated types regenerate with `make openapi-sync`. |
| N8 | **The Result tab while writing** (annex scenes 6 and 15): every proposed section shows pulsing placeholder lines until its prose arrives; the active section shows the writer's action line above its lines until the first delta; prose appears as deltas arrive, plain text; a marked sentence blurs in place; on `section_completed` the draft cross-fades into the final prose with no label, underline or popover afterwards; citation markers appear then; key findings shows "Written last, after the sections are checked." until its turn; after the last section the footer reads "Checking claims and attaching citations" until `run.status` is terminal, then "Report ready" with the primary button. Reduce motion: no blur, instant swap, no pulse. The draft state is visible and accessible: the heading's dot plus a polite live region that announces "being written"; draft text carries no claim marker and no citation, because the judge runs on the parsed object after the draft (ADR 0015 flag-not-drop untouched; finding 11); a terminal-partial run keeps today's drafted-not-final banner. | `ArtefactView.tsx` `LiveArtefactBody`; `index.css` motion utilities. | vitest on each state; the mock journey plays the sequence; live-dev screenshots mid-stream, mid-blur and after. |
| N9 | **Planner reply streaming.** `POST /tasks/{id}/task-agent-turns` responds with the chat route's stream shape (`progress`, `delta`, `completed`, `failed`; exactly one terminal event; a retried completion is one terminal event; reservation and auth resolve before the headers are sent; the turn is durable and finishes whether or not the client stays connected). The JSON response is replaced, not kept beside it: the frontend and backend deploy together (owner, 2026-11-04). Both planner profiles. The Agent tab appends deltas to the pending turn and shows "Drafting the plan" with the dot until the turn lands. The opening turn runs in the Agent tab, not on `/new`: task creation navigates at once and the first turn streams there. | `api/routers/task_agent.py:948-1118`; `api/routers/conversations.py:653-775` (the precedent); `runtime/task_agent.py`; `TaskAgentPane.tsx`; `NewTaskView.tsx`; `api/mutations.ts:61-67`. | Route tests for the stream, the terminal-event rule, auth before headers and a disconnected client; the Agent tab test asserts the pending turn fills and the plan card follows; the opening turn's suggestions are not discarded. |
| N10 | **The planner's clarifying question reaches the client.** `TaskAgentTurnOut` gains `question` (nullable); the chips render under it; chips come from the stored turn, so they survive a reload. | `api/contract/task_agent.py:615-657`; `TaskAgentPane.tsx:678,822`. | Contract test; a reload test keeps the chips. |
| N11 | **The Result tab before writing** (annex scene 5): the run strip, the question as the title and one sentence, "The report's sections are set out when writing begins."; on a re-run with an existing report, one plain line above it, "This report is from <date>. A new run started <n> min ago.", with no button (the strip is the way to the run; owner, contract review 2026-11-04); a paused run keeps the live body. The old "Preparing your results" card goes. | `ArtefactView.tsx:1401-1523`. | vitest on the three states; mock journey. |
| N12 | **Run strip** on every tab but Agent: dot, "<stage> · <section or count> · <elapsed>". Status only, no link and no mark (owner, gate ruling 2026-11-04: the sidebar rail already carries the Task Agent mark on every non-Agent tab, and the Agent tab is the full view; no third route). While a check-in waits the strip turns orange, "Paused · a check-in is waiting on you"; the separate paused banner is removed. On completion the strip reads "Report ready · Read it →" (or the capability's wording) in green, the one link it ever carries. | `AppShell.tsx:443-454` (the banner slot and the paused banner), `LifecycleBar.tsx`. | vitest; mock journey asserts the strip on Sources, the paused strip, and the done link. |
| N13 | **The sidebar is the same agent.** `ChatSidePanel` mounts the Task Agent with the real stream and run status: compact run line, thread tail, a pending check-in (answerable), the composer locked with the same placeholder; "Open in the Agent tab →" in its header; "Review the plan" and "See plan" open the plan document; while a check-in waits, opening the sidebar from its rail lands on the check-in, which glows once (on Agent the check-in card glows in place). | `ChatSidePanel.tsx:236-243`. | vitest on the mounted pane's props and the lock; mock journey: opening the paused sidebar shows the check-in. |
| N14 | **New content marks its tab.** A dot on a lifecycle tab when its content landed while the user was elsewhere (Result on a section or the report; Sources on sources; Findings on findings), cleared on visit; the orange check-in dot stays. The browser title changes to "● Report ready · …" on completion. A `degraded` finish opens the report like `succeeded`. | `AppShell.tsx`, `lifecycle.ts:150-159`, `lib/title.tsx`. | vitest on the marks and the title; mock journey. |
| N15 | **Task list and plan control.** `TaskOut.active_run` gains `stage` (the current public stage key) and `stage_label` (the server's copy, finding 8), derived from the parentless walk so a scoping task shows the parent's stage, not a child's; the list row reads "<Stage> · <elapsed>" (short form below `md`); the task nav gains a "Plan" control beside the tabs that opens the plan document from any tab; the plan document opens as a side panel by default and Escape closes it; the `ReconnectingBanner` is mounted. | `api/contract/tasks.py`, `common.py:387-393`; `TaskListRow.tsx`; `WorkspaceView.tsx:58-75`; `useRunStream.tsx:147-158`. | Contract test; vitest on the row, the control, Escape, the banner. |
| N16 | **Sources during a run.** The Sources view defaults to the "All" filter until screening has completed; the Sources and Landscape queries refresh on ingest ticks only (the stage that commits per document), throttled to a 5 s trailing window (finding 18). | `SourcesView.tsx:53-54`; `useRunStream.tsx:118-165`. | vitest: the default filter; the refresh fires on ingest ticks and not on others; the throttle. |
| N17 | **One source of copy.** `STAGE_PRESENTATION` is the only source of stage labels, blurbs and activity verbs, in the client's wording (owner: concise, no mannered prose); the Options scoping blurbs are rewritten in that voice; the client step vocabulary, its two copies and the mock's labels are deleted and read the server's text; the completion count keys are chosen per stage (not an allow-list) and named in the annex; the web-api spec lists all 19 stage keys and the new frames and fields (S1 to S4). The server's presentation table also says which stage keys share one card row (search+screen as "Searching and screening", classify+appraise as "Categorising"), so the client decides nothing about rows either. | `api/stage_vocabulary.py`; `planVocabulary.ts`, `checkInPresentation.ts:60`, `journey/presentation.ts`; `mock/api.ts`; `web-api.md:704-720`. | A test asserts every public key has a label, blurb and verb; the client has no label literal (grep test); `audit-stage-copy.md` is the before. |
| N18 | **Stepper and part card** (annex scene 11): the client computes "Plan · step n of M · <part>" from the capability's part ids and the transcript; the part card is a radio list, the primary option first with its reason under it, no "Recommended" word, no pre-selection; an option that needs words opens an input inside the card with its own Send (no composer pre-fill); a settled part collapses to "<Part> · <choice> · Change"; the plan card starts the run for both capabilities ("Start the search" / "Confirm and build the baseline"). | `PartCard.tsx`, `PlanCard.tsx`, `TaskAgentPane.tsx`; `task_agent_scoping.py:714-716` (the two rejected part ids are added to the profile). | vitest on the stepper, the list shape, the in-card input, the settled line; the scoping parts render (test); e2e journey updated. |
| N19 | **Check-in card** (annex scene 12): the question as the title (no eyebrow; owner, gate ruling 2026-11-04), one facts line, a radio list with the steering's suggested option first and its `why` under it, "Or steer in your own words" as a closed disclosure, one "Stop the run" link (the duplicate option is dropped), and after answering the line "You chose: <label> · <when>" built from the durable `checkin.resolved` frame, not session storage. The running card's top line reads PAUSED while a check-in waits. | `CheckInCard.tsx`, `AnsweredCheckIn.tsx`, `store/thread.ts:38-56`, `runtime/steering.py` option order. | vitest; mock journey with a real check-in kind and trigger (N26). |
| N20 | **Planner fixes from the survey.** Preset and plan-document time bands agree (one table); longlist replies carry no literal asterisks; evidence-search plan edits survive leaving the tab (held in the store, not the view). | `task_agent_prompt.py:392-407`, `planVocabulary.ts:117-137`; `longlist_turns.py:113-152`; `WorkspaceView.tsx:60`. | Tests per item. |
| N21 | **Option-search activity on the scoping card** (annex scene 9): "n of M searches done · k sources so far" from the join loop; then the parent stages' lines. | `runtime/option_search.py:615-621`. | Test on the join loop's ticks; live scoping run. |
| N22 | **Options read.** New `GET /tasks/{id}/options`: the task's option rows (`option_id`, `name`, `description`, `origin`, `state`, `merged_into_option_id`) each with `search_status` (`queued`, `searching`, `searched`, `failed`) and `found` (the child's acquired count, null until searched), available from the end of the suggest stage; no `provisional` flag (the client already knows whether the longlist exists from `has_longlist`; owner, 2026-11-04); the same readable/public predicate as the longlist read, which the owner accepts for building rows (finding 14); `GET /longlist` is unchanged (404 until the clustering result exists); `has_longlist` is unchanged. The full schema is in G1 (findings 2 and 13). | `api/routers/longlist.py:80-106`; `repository.py:4482-4571` (`option_out` already copes with no result); `runtime/option_search.py:456-476` (`child_walks`). | Contract test; a read between suggest and longlist returns the rows with their statuses; tenancy tests: a public task, a cross-tenant request gets the same 404 as a missing task, strict task scoping. |
| N23 | **Child status reaches the row.** The options query refreshes on child `run.status` and child `stage.completed` frames (today suppressed at `useRunStream.tsx:127-133`); the reducer does not store child stage frames and `RunOut` is unchanged (finding 13: the read carries the status, so no client-side join). | `useRunStream.tsx:118-165`; `reducer.ts:31-33`. | A child's acquire completion refreshes the options query and the row shows "Searched · n found" (test with a fake stream). |
| N24 | **The longlist during the build** (annex scene 15): "Longlist" with no qualifier (owner, gate ruling 2026-11-04: the stage line and the moving rows already say it is being built); the view picks the building state from `has_longlist` being false while a walk runs; one stage line; per-row "Queued", "Searching" (dot) and "Searched · n found" from the child's acquire completion; stage-level lines for abstracts and clustering ("options may be folded together or added"); on the longlist stage a folded row moves under its parent as a grey line and new rows appear "found in the evidence"; counts, lever lines, the excluded group and the theme groups land as waves; shortlist marks at the end; the stage line goes when the walk ends. | `LonglistView.tsx`, `longlistPresentation.ts`, `ArtefactView.tsx:1331-1391`. | vitest on each state; mock scoping journey with child frames (N26); live scoping run screenshots. |
| N25 | **Measurement.** A capture client (`scripts/stream_capture.py`) logs every frame, tick and heartbeat with a timestamp during each fixed-question run; the tick carries a `dropped` counter from the hub. A silent gap is an interval over 30 s with no frame, tick or heartbeat; a healthy run is one where no model-call timeout fired and no fallback ran. Measures, before and after, on the laptop and on staging (the staging baseline is captured before the deploy): silent gaps (count, share of active time, by stage), time from the writing turn's start to the first delta and to the first completed section, the cache-cost delta per report (cached, cache-write and uncached input tokens per section, priced), tick rate per stage, dropped ticks, the fallback count from N6. Saved-result file names are recorded. | `scripts/stage_walls.py` (`--capture` mode from the gap method in `research/exp-event-gaps-and-bands.md`); the capture client is new. | In `verification.md`, read from saved results. Target: zero silent gaps on a healthy run; first delta within 5 s of the writing turn. A gap on an unhealthy run is reported with its cause. |
| N26 | **Mock API and journeys.** The mock returns parts and suggestions, a real check-in kind and trigger, child walk frames and ticks, delta and revising frames, the options read; the e2e journeys assert the annex's states for both capabilities, including a reload mid-run and the paused strip. The scoping journey also asserts the product gate: baseline run → durable pause → answerable gate → no option rows before confirmation → continuation → suggest → the options read (finding 12). | `mock/api.ts`, `mock/fixtures.ts`, `e2e/journey.spec.ts`, `e2e/scoping.spec.ts`. | `make verify` (the mock-journey job) green with the new assertions. |

## Decisions

**D1. Streaming shape. Decided (owner, 2026-11-04).** The final turn streams as a strict
`json_schema` response with no tools; research turns keep their tools; the repair keeps its
forced tool call; a failed stream falls back to today's forced tool call once. The cache
cost of the separate lineage is accepted at the measured $0.03 per report. Build-time check:
strict acceptance of the full schema on Luna as well as Terra.

**D2. Tick shape. Decided (revised after the contract review).** `tick` carries one set of
fields for every stage: `stage`, `activity` (string), `done` and `total` (ints, null when no
honest count), `unit` (string, null with no count), `section` (string, null outside writing),
`heartbeat` (bool), `dropped` (int, the hub's dropped-tick counter), `ephemeral: true`. The
ingest-only fields `note`, `fetched` and `parsed` are removed and the ingest stage publishes
`done`, `total` and `unit = documents` like every other stage (owner, 2026-11-04: replace,
do not layer; the frontend and backend deploy together). Coalesced at 500 ms per task and stage; a heartbeat every 10 s while a call is in
flight. No walk id on ticks; the scoping rows' status comes from the options read (N22).

**D3. The repair marker. Decided (owner, 2026-11-04).** A sentence under repair blurs in place
and cross-fades into its new wording; nothing marks it afterwards. This is the owner's reading
of "never change read text without a visible marker": the transition is the marker. The
browser-held draft is not surfaced (no "old wording" popover). Pre-repair text is not stored.

**D4. Copy source. Decided (owner, 2026-11-04).** The server is the single source; the client
wording wins over the server's current text; the voice is a short label then one plain
sentence, no mannered prose.

**D5. Card rows. Decided (owner, 2026-11-04).** Direction C, the step spine. Search and screen
are one row; "Categorising" absorbs appraise; Shortlisting has no link; Reading has no link.

**D6. No computed time band. Decided (owner, 2026-11-04).** Recent runs predate the 056 and 057
merges and the pending Cohere quota raise. The static table stays; elapsed time only.

**D7. No cancel. Decided (owner, 2026-11-04).** Deferred to its own slice with the probe's
finding (cooperative flag; never close the client). The check-in's "Stop the run" is the
existing abort.

**D8. Two routes to the agent. Decided (owner, 2026-11-04; tightened twice at contract
review).** On any non-Agent tab the sidebar rail's own Task Agent mark opens the sidebar in
place and the Agent tab is the full view. Nothing else links to the agent: the run strip is
status only, the paused banner is removed (the strip carries the paused state) and the re-run
notice has no button.

**D9. Provisional longlist. Decided (owner, 2026-11-04).** The suggested options are the
skeleton. Per-option status is limited to what the pipeline knows: search status per child,
then stage-level lines, then waves. No per-option reading counts before clustering.

**D10. Choices have no "Recommended" label. Decided (owner, 2026-11-04).** The planner's primary
and the steering's suggested option sit first with their reason; no label, no pre-selection,
no prompt change.

**D11. Polish passes. Decided (owner, 2026-11-04; PR #113).** Two passes at the end of the
build (agent, then owner) and two after the review stack, inside this PR. Round budget:
up to three owner rounds at each point. Rulings go into the annex; the owner's sign-off is
recorded in `verification.md`.

**D12. Section proposal stays in synthesise. Decided (owner, 2026-11-04).** Headings appear
when writing begins; moving the proposal earlier would take it out of the component.

**D13. Instrumentation out. Decided (owner, 2026-11-04).** No leave-and-return telemetry;
PostHog is the later answer. N25's measures are server-side.

**D14. Email out. Decided (owner, 2026-11-04).** No notification channel; the SES note stays
for a later task.

## Owner rulings (2026-11-04, this conversation)

1. Email notifications out. 2. Computed time bands out. 3. Scope: option 2 of the approach
note, then blocks G to K added (planner streaming; Options scoping throughout; the planning
conversation; the sidebar; navigation; the scoping Result tab). 4. The model's search queries
shown verbatim. 5. Browser-held draft only (then superseded by D3: no marker after the
fix). 6. Client wording wins; no mannered prose. 7. Card C. 8. Stall counter dropped; "Still
working on this step" after two minutes. 9. Writing shows the section, then the action.
10. Early Result tab: strip, title, one sentence; no output links. 11. Sections proposed
appear with pulsing lines; the action line shows the writer's research turns. 12. The
streamed turn's three cents accepted. 13. Categorising absorbs appraise; no shortlist link;
no read-in-full link. 14. No "Recommended"; the diamond opens the sidebar. 15. Polish is
multi-pass inside the task; all frontend agents load the design skills; the
`frontend-designer` agent. 16. DESIGN.md and PRODUCT.md committed; the six principles stay in
PRODUCT.md.

## Spec items (owner decision at the contract gate)

- S1. `web-api.md` § SSE lists all 19 stage keys (the 9 Options scoping keys are missing).
- S2. `tick` is reshaped (D2): one set of fields for every stage; the ingest-only fields go.
- S3. New ephemeral frames `artefact.section_delta` and `artefact.section_revising`; the
  `artefact.*` paragraph says deltas are display-only and `section_completed` stays the
  record.
- S4. `TaskAgentTurnOut.question`; `RunOut.option_id`; `TaskOut.active_run.stage`;
  `GET /longlist` provisional shape; `POST /task-agent-turns` as a stream. Each additive.
- S5. The Evidence search and Options scoping capability specs' § Product surface gain one
  paragraph each on the live Result tab (streaming sections; the provisional longlist).

## Scope / Out of scope

- **In:** `core/liveness.py`, `core/tracing.py`, `api/stage_vocabulary.py`,
  `api/contract/sse.py`, `api/contract/task_agent.py`, `api/contract/runs.py`,
  `api/contract/tasks.py`, `api/routers/sse.py`, `api/routers/task_agent.py`,
  `api/routers/longlist.py`, `api/read_models/repository.py` (longlist read),
  `evidence_search/synthesis/{synthesis_backend,synthesis_tools,synthesise,section_prompt}.py`,
  the stage loops named in N2, `runtime/option_search.py`, `runtime/task_agent_scoping.py`,
  `runtime/task_agent_prompt.py` (time bands only), `api/longlist_turns.py` (asterisks),
  `model_routes.toml` (the streamed step), `frontend/src/{store,api,views,ui}` as N5 to N24
  name, `frontend/src/mock`, `frontend/e2e`, the web-api and capability specs (S1 to S5),
  `docs/deferred.md`, `docs/knowledge/`.
- **Out:** cancel (D7); computed bands (D6); instrumentation (D13); email (D14); any schema
  change; the section proposal's place (D12); per-option reading counts and per-option
  profile waves (pipeline changes; D9); storing pre-repair text (D3); the Responses API
  move; the chat conversation route (already streams); the longlist's own actions and the
  option card beyond the provisional state; the shortlist view; the planner's prompt (no
  change beyond the two part ids and the time-band table).

## Constraints & approval gates

| Gate | What | Status |
|---|---|---|
| G1 | Public interface, the complete list (the frontend and backend deploy together, so a replaced field or response is acceptable; owner, 2026-11-04): `tick` is reshaped to `stage`, `activity`, `done`, `total`, `unit`, `section`, `heartbeat`, `dropped`, `ephemeral` (the ingest-only `note`, `fetched`, `parsed` are removed); new ephemeral frames `artefact.section_delta {index, text, mode}` and `artefact.section_revising {index, spans}`; `TaskAgentTurnOut.question` (nullable); `TaskOut.active_run.stage` and `.stage_label`; new `GET /tasks/{id}/options` returning `{options: [{option_id, name, description, origin, state, merged_into_option_id, search_status, found}]}`; `POST /tasks/{id}/task-agent-turns` responds with the chat route's event stream instead of a JSON body. `RunOut` and `GET /longlist` do not change. Generated types regenerate; `make drift-check` green. | approved at this contract, revised at the review |
| G2 | Prompt hash re-pin: `section_prompt.py` changes only in the final turn's call shape (the wire's docstrings are hashed); the planner prompt changes only its time-band table; `prompt_hashes.json` re-pinned with the diff in `verification.md`. The judge, the repair and the research turns are untouched. | approved at this contract |
| G3 | No schema change. If a need turns out to need one, stop. | binding |
| G4 | No new dependency. The Markdown renderer is not needed (prose is plain text). | binding |
| G5 | Spec amendments S1 to S5, applied in the build with a line in the spec log. | owner at this contract |
| G6 | Polish round budget (D11): three owner rounds at build end and three after review. | approved at this contract |
| G7 | Staging run of the fixed questions before merge, with the N25 measures. | binding |

Egress unchanged: the same model route, one more streamed call shape on an existing step.

## Public / private boundary

The research folder stays gitignored (experiment outputs name local traces and request ids).
The mock is a private artifact. Ticks carry counts, verbs and the model's own search query text. That text is derived from
the task's question, which the user wrote and may contain names; it goes only to the
authenticated stream of that task, normalised and bounded (§ Disciplines), and never to a log
line or a public viewer (finding 10).

## Model route

`bedrock` default, `openai-direct` legacy. The streamed final turn runs on the writer's
tier (`standard`, Terra) with `reasoning_effort = "none"` as today, as a strict `json_schema`
response. Prompt text does not change; the call shape and the wire's place in the request do
(G2). Build-time check on Luna (fast tier) as well.

## Disciplines binding this slice

- **Flag, don't drop** (provenance-grounding): the streamed prose is display-only; the judge
  runs on the final parsed object; nothing is shown as verified before the judge has run.
- **Honest absence**: no count without a known total; no countdown; no percent bar; nothing
  animates unless real data is arriving; reduce motion honoured everywhere.
- **Model only what behaves**: ticks and deltas are ephemeral; the durable frames are the
  record.
- **Replace, do not layer** (owner, 2026-11-04): the frontend and backend deploy together, so
  a change that supersedes a field, response or component removes the old one in the same
  slice; no compatibility branches.
- **One source of copy** on the server (D4); the annex is the only place looks are written.
- **The model's query text in a tick** is shown verbatim by owner ruling but normalised: NFC, control and format characters stripped, bounded at 120 characters; the stream is auth-gated and public viewers never receive it (finding 10).
- **No label that states what the page already shows** (owner, 2026-11-04): no eyebrow text,
  no pills, no "provisional" or "recommended" words; state is carried by the stage line, the
  dot, the heading colour and the row's own line.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when a gate above is hit; when the strict schema is refused on either
Bedrock tier and the fallback would run every time; when the tick rate cannot be held under
the coalescing cap; when scope would grow past this contract (a schema change, a cancel
endpoint, telemetry); or when the turn or token budget is spent.

## Acceptance checks

- `make verify` green at the build-open baseline, after the backend frames phase, after the
  frontend phases and at the step-6 exit; `make drift-check` green after regeneration.
- Deterministic tests as each need's measure names; the mock journeys for both capabilities
  (N26).
- Live check at the contracted scope: the four fixed questions on the laptop before and
  after; one staging run of each capability after deploy (G7). Screenshots at 1280 and 400,
  light and dark, of every changed surface mid-run.
- The polish passes recorded in the annex's polish log with the owner's sign-off (D11).
- The Tier 3 stack at step 7, none skippable: contract verifier; one security lane (the
  streamed representation, the options read's tenancy, the query text); the heterogeneous
  pair (Codex adversarial and `/code-review medium`); the `frontend-designer` design lane;
  simplification; and the human deep review at step 9 (finding 16). Adversarial reviews at
  the contract and plan stages are recorded in this folder.

## Verification evidence expected

In [verification.md](verification.md): the `make verify` table per phase; the N25 measures
before and after, read from saved results; the fallback count; the Luna and Terra strict
checks; the prompt-hash diff; the spec log lines; the screenshots; the polish log with
dates and sign-offs; the staging run; known gaps and the seams added to `deferred.md`
(cancel with the probe's shape; computed bands with the rolling-window shape; per-option
reading counts; the section proposal's place; telemetry; email).

## Risk tier & review focus

**Tier 3.** Public-interface additions (G1), a prompt-adjacent change (G2), a new streamed
route. No schema, no auth, no new egress. Review focus: the fallback path and the
between-chunks timeout on the streamed turn; replay idempotence with ephemeral frames; the
coalescer under burst; the sidebar's run state and composer lock; copy in one voice; the
annex's states reproduced on the live app.
