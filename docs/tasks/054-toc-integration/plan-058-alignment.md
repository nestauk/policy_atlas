# Plan: 054 alignment with 058 (progress, streaming, consistency)

> **Status:** owner-approved direction, 2026-11-09. Nothing is built yet.
> The phases below run in order. A 🛑 marks a point where the owner decides.
> When the build ends, the owner runs the task-cycle review stack (steps 7–10) on this pass, together with the rest of 054.

## 1. Why this pass

Task 058 (perceived latency) merged into `dev` on 2026-11-09 and was merged into `task/054-1-core` the same day (merge `d84a5c2b`). The owner asked for three things:
- **Token streaming for the theory of change (ToC) report**, as the Evidence search report has.
- **One progress card in the Task Agent**, as the other capabilities have, with the same detail in the run status bar. All step words come from the server, none from the browser.
- **A consistency pass**, so the ToC reads as one product with Evidence search. 058's annex decisions, and the Options scoping ones, apply wherever they are relevant.

## 2. Grounding (what this plan rests on)

| Source | What it says | Where |
|---|---|---|
| 058 design annex, read for the ToC | The decisions that carry over (progress, streaming, report page, citation sheet, History, shared homes, copy) and the Options scoping patterns | `research/058-decisions-for-toc.md`[^1] |
| Backend investigation | How 058 streams; how the ToC report is written today; the ToC has no server stage keys; the fan-out ticks carry Options scoping's label; the canvas commits once per step | lead conversation, 2026-11-09 |
| Design audit (frontend-designer) | 18 ranked inconsistencies; TocTrace and RunTrace compared row by row; what to keep as different | lead conversation, 2026-11-09 |
| Feasibility check: the report through the shared synthesis | Synthesis can write the ToC report and grounds better (19 of 19 claims), but fits worse without a ToC template. Bedrock refuses Sol with function tools. | `research/report-synthesis-feasibility/report.md` |
| Feasibility check: Sol streaming | Sol streams cleanly on Bedrock with no tools, as plain text and under a strict JSON schema. The thinking wait before the first words is 7–9 s on tiny prompts. | `research/report-synthesis-feasibility/sol-stream-probe/` |

[^1]: The digest lives in the lead's scratchpad today. Phase 0 copies it into `research/` (gitignored).

## 3. Owner decisions (2026-11-09)

1. This pass is part of 054 (PR #114), not a new task.
2. **The split.** This PR stays on Sol and keeps the ToC's own writer. A follow-up PR decides Terra against Sol and the move to the shared synthesis, after a colleague's manual quality checks. The rerun of the synthesis comparison on 3 local tasks feeds that follow-up (`research/report-synthesis-feasibility/`).
3. **Contract change accepted:** the ToC step names join the API's stage keys (spec § SSE).
4. **The report streams (changed 2026-11-09).** Today's single `toc_report_v7` call streams unchanged: same prompt, model and content, and no hash change. Its fields fill the page in the order the model writes them, each in its own place (owner, 2026-11-09; S6), through 058's report-section frames and live view. **The report's content does not change in this pass; only its formatting and presentation do.** The header above the canvas keeps all four parts: title, verdict and headline, question, "what would settle it". Writing each section with its own call, and the claim check with repair, move to the follow-up PR (owner, 2026-11-09).
5. **What changes from `TocTrace`:**
   - The per-search lines move to the Sources tab's "Search queries".
   - The outcome counts stay, as server counts on the finished rows.
   - The automatic chain is **one card** (changed by the owner on 2026-11-09). A draft and the check the server starts after it read as one run: "Drafting the theory" is the first row, the check's rows follow, and it ends "Evidence checked · Read it →". Four kinds of walk keep their own card: an uploaded theory's read, a check the reader starts ("Check the evidence", a check on chosen connections) and "Update the report". The server keeps the two walks and marks the check as the draft's follow-on (seam S3); the frontend joins them.
   - "Usually takes 1 to 2 minutes" and the per-step timer go.
6. **Finish words:** "Theory drafted · Read it →" and "Evidence checked · Read it →". A failure reads "Stopped" or "Failed".
7. **Verdict colours:** the shared tones everywhere, the canvas lines included. The dash patterns stay.
8. **The rounded canvas boxes stay** (contract W2).
9. **The canvas colours each connection as soon as it is judged.**
10. **After the reader's edits** the report says "Written before your latest changes." with "Update the report". The update stays the reader's action.
11. **The Task Agent sidebar no longer opens by itself** on ToC tasks (owner, 2026-11-09, reversing the earlier ruling): the run status bar shows the run, so the sidebar opening on its own is unnecessary. The status bar follows 058's rule and steps aside only while the sidebar shows the Task Agent.
12. **The audit's 11 copy proposals** go to the owner one by one with the mock (phase 1).
13. **No "draft landed" message in the automatic chain** (owner, 2026-11-09). The Task Agent's code-written line when the draft lands (`DRAFT_LANDED_MESSAGE`) is not posted when the check follows automatically; the message when the check ends stays. An uploaded theory keeps its "check how we read it" message, where the reader acts.

## 4. Scope

**In scope**
- **A. Server progress**
  - ToC stage keys with their label, blurb, row and counts.
  - The fan-out ticks under ToC stages.
  - Activity ticks from the ToC loops (judge, pick, figures, select).
  - The walk kind (draft or check) on the run read.
  - `RunOut.stages` and `active_run.stage` filled for ToC walks.
- **B. One progress card**
  - `RunTrace` / `PastRunLine` for ToC walks.
  - The run status bar and the task list row.
  - The review line as the shared `ActionLine`.
  - `TocTrace.tsx` deleted.
- **C. The report**
  - Today's `toc_report_v7` call, streamed unchanged on Sol: the same prompt, content and model.
  - Each field is published to its page part as it closes, through 058's frames and live report view.
  - The committed report swaps in place.
  - The code's after-call edits (renumbering, pathway order, the table) stay as they are and fade in at the swap.
- **D. The report page** (presentation only; the content stays as it is)
  - The shared `ReportPage` shell: the date line, the facts line, Download in the kind row, the contents, an h2/h3 outline, the expand state.
  - The header above the canvas keeps its four parts. The report's own title stays the `h1`: 058's "question as h1" rule does not apply here, because it would change content.
  - The shared References.
  - The full citation sheet: source marks, the dossier with "Back to the claim".
- **E. Consistency**
  - The audit's findings 2–18: the phone canvas, buttons, links, disclosures, close and icons, typography and callouts, dates and counts, plan sections, plan card, shadows, status words.
  - The detail panel: **small consistency changes only**. That means the shared tones and marks, the shared buttons, links, disclosures and close button, the shared type sizes, and citations opening the shared citation sheet. A colleague refined its content and order; both stay (owner, 2026-11-09).
  - Set-aside pathways as "Exclude" / "Include again".
  - The public link read-only.
  - Per-connection commits in the judge, so the canvas colours connection by connection.
  - The stale-report line.

**Out of scope (the follow-up PR, or later)**
- Changing any model.
- Writing the report section by section, and checking its claims with the grounding judge and repair. Both change the content, so both go to the follow-up PR.
- The shared synthesis for the ToC report.
- Moving synthesis to the Responses API. That is its own system-level task, seeded 2026-11-09 (`docs/research-and-development/responses-api-migration-seed.md`, local).
- ~~Filling the canvas while the draft is written: the draft commits once and its retry would undo streamed boxes.~~ Moved into scope as S12 (owner, 2026-11-10: "Let's do the live draft too."). The sketch is not committed, so a retry resets it instead of undoing anything.

## 5. Seams the build fixes

- **S1. Stage keys.**
  - Add one key per ToC step the reader sees, and one per fan-out (`toc_item_searches`, `toc_new_link_searches`, `toc_retry_searches`). That makes 15 ToC keys (§ 9).
  - A fan-out and the step that runs it keep separate keys but share a label; `cardRows` merges rows with the same label into one row. No `row` field is added to the frames.
  - `STAGE_BY_REGISTRY` maps the `toc_*` components. `PlanStageKey` (`api/contract/task_agent.py`) is the third mirror of the keys and gains them too.
  - `option_search._publish_progress` takes the stage as a parameter.
  - **The upload's read.** `toc_draft` in a `review_first` draft walk reports as `toc_read`. The component name alone cannot tell the two apart, so the runner stamps `"stage"` on that walk's component payloads, and `stage_for_payload` reads a stamped `"stage"` first.
- **S2. Derived counts.** The counts that `TocTrace` computes on the client ("N judged · M test them", "N set aside") become server count keys on `stage.completed`.
- **S3. The walk kind.**
  - Expose draft against check on the run read: a field, or a `purpose` value.
  - Mark a check the server started after a draft as that draft's follow-on (the draft walk's id on the run read). The server already records it: `admit_and_mint(..., draft_run_id=…)`; this only exposes it. The frontend renders the pair as one card: one timer from the draft's start, the draft's row first, the check's finish words.
  - `walkKind` and `READY_WORDS` gain the two ToC kinds.
  - `resultHref` points at the ToC Result.
- **S4. Streaming today's call.**
  - `toc_report` keeps its prompt (`toc_report_v7`), route step and schema. It is called with `stream=True` and the same strict `json_schema`, as 058's introduction stream is.
  - String fields are followed with `JsonStringFieldDecoder`; the array fields (pathways, connection reasons, found routes, supporting activities, tests) with `JsonArrayObjectDecoder`.
  - Each field is published to its page part's display index as it arrives; arrays arrive item by item.
  - Any retry sends `replace ""` first. The streamed call runs once, outside both inner retry loops; one non-streamed fallback is the retry.
- **S5. Citations while streaming.** A streamed `[n]` shows as 058's muted pending chip `[·]`. The numbered sources are known before the call, so their titles can travel on the sources frame for the chip's hover. There is no claim check in this pass, so there is no revising blur.
- **S6. The frames.**
  - The ToC report emits 058's `artefact.skeleton` (its section list), then the section deltas, sources and completed frames. There is no claim check, so no revising or claim frames.
  - **Contract generalisation (touches Evidence search).** The ToC header parts (the verdict line, the headline) are not sections of an Evidence search artefact. Phase 4 first tries to place the header parts as ordinary skeleton entries. If that fails, the live frames gain a small `LiveSectionRole` so a skeleton entry can name its part (possible spec change S-4, § 10). Evidence search sends the same frames as today; its regression tests must pass unchanged at phases 4 and 6.
  - **Fill order (owner, 2026-11-09).** The fields fill **in the order the model writes them**, each in its own place on the page. The output format is in the protected prompt, so it does not change. The order written: the header parts, Summary, Pathways, How it could fail, the connection reasons (the Assumptions table), How it could be expanded, Supporting activities, What to test first. So the reader sees the table and two parts below fill before "What to test first" above them.
  - **Decoders.** String fields use `JsonStringFieldDecoder`; arrays of objects use `JsonArrayObjectDecoder`. `supporting_activities` is an array of strings, so it needs a small string-array decoder.
  - **Markers in deltas.** A streamed `[n]` shows as the pending chip `[·]`. A `#n` code (a box or connection) shows as plain text until the swap. A marker split across two deltas is held until it closes.
  - **Reconnects and failures.** Each field gets `section_completed` as soon as it closes, so a reconnect replays the closed fields. On a failure the fallback sends a fresh skeleton and `replace ""` for every part, then the fallback's text arrives as one replace per part.
- **S7. The swap.** The live view hands over to the committed report from `GET /toc`. Citation numbers and the pathway order may change at the swap: they fade in as 058's swap does.
- **S7b. Only a first report streams.** "Update the report", and a check walk that runs while a report exists, do not stream over the old report. The old report stays with the `ActionLine` until the new one swaps in (§ 8).
- **S8. Per-connection commits.**
  - The judge writes each connection's evidence rows through its own database connection (a `ConnectFactory`, as ingest does), in a short transaction per connection.
  - Each commit updates the `counted_hash` that the canvas read uses, so the canvas sees the change.
  - Idempotent under a component retry: a retry skips the connections that this step's earlier attempt wrote (rows at the current hash created since the step's first attempt started). Changed at build: "written by the same run" would make the second search (`toc_search_again`, same walk) skip every link it must judge. The unique key `uq_toc_evidence_link_doc_hash` also blocks duplicates.
  - The step still sends one `toc.changed` at its end, so History gets one change record.
  - The canvas refetches at most once per finished connection batch, on a ToC `stage.completed`, and on the 5 s poll while the judge runs.
  - Each connection takes its verdict tone as soon as it is judged (owner decision 9). The grade shown before classify and appraise finish is provisional. It may shift once more when they land.
- **S9. Stale report.** The report read carries `stale`. It is true when a content edit, an undo or an evidence decision was made after the report's walk started (`run.started`). Moving a box, resetting the layout, and undoing either do not count (a `layout` flag on the change event). The page shows "Written before your latest changes." with "Update the report", and the `ActionLine` while the update runs.
- **S10. Between the walks.** In the automatic chain, the card shows the draft row as done and stays "Running" until the check's first frame. If the check is refused (for example by the cost guard), the card ends with the draft's finish words and the refusal message from today.
- **S11. Not built in this pass: including a set-aside pathway again.** The spec lists it as not built and `docs/deferred.md` records the seam. It needs a new edit with undo and maybe a migration. The set-aside line stays as text.
- **S12. The live draft** (owner, 2026-11-10). The theory is drawn on the canvas while the first draft is written.
  - **What does not change.** The draft's content: the same prompt (`toc_draft_v5`), route step (`toc_draft`), answer format (`DraftResponse`), checks, retry and stored graph. Only how the answer is read changes: the call is streamed (`OpenAITocBackend.draft_stream`, the same request as `draft` plus `stream`), on Bedrock.
  - **What is streamed.** The model writes the boxes first, then the connections, then the pathways and the rest. Each box and each connection is sent as soon as its part of the answer closes (`JsonArrayObjectDecoder` on `boxes` and `links`). Pathways are not sent: they come after every connection, the stored graph lands seconds later, and the canvas needs only boxes and arrows to draw.
  - **The frame.** One new ephemeral frame, `toc.sketch`: `{boxes: [{key, layer, text}], links: [{key, source, target}]}`. It carries the whole sketch so far each time and replaces the one before, as `characterise.themes` does. That is the smallest form that fits the live hub: a lost or merged frame costs nothing, and a full queue's resync is one message. Keys are the model's draft keys (`b1`, `l1`), not stored ids; a connection names its ends by box keys, and is sent only after both boxes. The Evidence search section frames (skeleton, delta, card) are not used: they describe text parts of a report, not boxes on a canvas.
  - **Done and reset.** The sketch is display-only. It ends when the `toc_draft` stage completes: the page then reads the stored graph (`GET /toc`), which replaces the sketch (`toc.changed` is not an SSE frame). An **empty** `toc.sketch` means "start again", and the page drops its sketch. It is sent (1) when the stream fails or sends nothing within `first_content_s`, before the ordinary call runs (the report's `fresh()` reset); (2) when a draft fails its checks, before the retry is drawn from its first box; (3) when the retry fails its checks too, before the step fails.
  - **What the reader sees on a retry.** The first draft drawn whole, then an empty canvas, then the retry drawn again box by box. On a fallback: whatever was drawn goes, and the ordinary call's graph arrives at the end with no sketch.
  - **Reconnect.** The same answer as the report's open part: the live hub keeps the latest sketch, and a browser that reconnects mid-draft gets the sketch so far at once. Nothing is saved to `event_log`: the sketch is never the record, and the report's saved frames exist because a closed part is final, which a sketch box is not (a retry can drop it). The hub forgets the sketch when the draft's stage ends, or the run ends.
  - **Where it runs.** `toc_draft_scope`, inside the draft walk's run (stage `toc_draft`). No new runner wiring: the frames go through the live hub binding the harness already sets, not through `ProgressEmitter`.
  - **Only a draft that becomes the canvas as drawn is sketched.** A user's own boxes on the canvas, or a diagram kept as drawn (`as_drawn`: an upload, or `drawn_on_canvas`), keep their place and the draft only fills them in; those use the ordinary call as today, with no sketch. So an upload's read (`toc_read`) never sketches.
  - **The time limit.** `first_content_s = 90` on `toc_draft` in the route file. Sol thinks before it writes the first box: first words came at 30.2, 31.8 and 38.6 s on 3 real drafts (`research/draft-stream-probe/`), far later than the report's 7 to 10 s, so the report's 45 s would cut off healthy drafts. 90 s still ends a stalled stream 210 s sooner than the 300 s timeout.
  - **Checks.** `tests/theory_of_change/test_draft_stream.py`: each box then each connection in order; a box split across pieces; mid-stream failure and late first words reset then make the ordinary call; a failed check resets then redraws; the reconnect snapshot; the stored graph is the same streamed or not; a user's diagram is not sketched; the streamed request is today's request plus `stream`. `make prompt-guard` with no re-pin.

## 6. Phases

| Phase | What | Executor | Gate |
|---|---|---|---|
| **0** | Copy the 058 digest into `research/`. Fix the phone canvas (`max-lg:flex-none`). | lead | `make frontend-verify` |
| **1** | **Mock.** The ToC run card (live, paused and ended, for the draft and the check); the run status bar; the task row; the live report filling in page order; the report page in `ReportPage`; the detail panel with small consistency changes; the canvas colouring connection by connection; the stale line. Built from a real dev task's data. | frontend-designer (loads the design skills) | — |
| **🛑 1b** | The owner reviews the mock and the 11 copy items. The lead records the rulings in § 8 (design notes). | owner | — |
| **2** | Acceptance items for this pass written into § 9, then a contract-stage adversarial review (one fresh read-only lane). Spec change S-1 applied and logged. | lead + one reviewer | — |
| **3** | **Server progress (S1–S3).** Stage keys, presentation, rows, counts, registry, the fan-out stage, activity ticks, the walk kind; `make openapi-sync`. | deep-reasoner (Opus) | full `make verify` (contract change), `make drift-check` |
| **4** | **Report streaming (S4–S7).** The streamed `toc_report` call with its fallback, the decoders and the frames. No prompt change: `make prompt-guard` must stay green with no re-pin. | deep-reasoner | `make prompt-guard`, `make verify` |
| **5** | **Per-connection commits and stale report (S8, S9).** | deep-reasoner | `make verify` |
| **6** | **Frontend: progress card, live report, report page (B, C, D).** `TocTrace` deleted. | frontend-designer | `make frontend-verify`, e2e |
| **7** | **Frontend: consistency sweep (E)** and the copy the owner accepted. | frontend-designer (one or more, by file group) | `make frontend-verify` |
| **8** | **Polish:** an agent pass, then an owner pass on the live app, both against § 8. Rulings recorded in § 8. | frontend-designer, then owner 🛑 | — |
| **9** | **Live run end to end** on the 3 local tasks on `bedrock`. `verification.md` gets this pass's section: wall time of the report before and after, cost, grounding results, screenshots. | lead | full `make verify` |
| **10** | **Hand-off.** The owner runs the task-cycle review stack. | owner | — |

**Inner loop and housekeeping** are as in `plan.md` ("How this build runs"):
- small commits;
- touched-module tests plus `make verify-fast`;
- stage by explicit path;
- `ruff check --fix` on touched files only;
- never single-file mypy.

## 7. Risks and what we watch

- **The wait before the first words.** Sol thinks before the first field (7–9 s on tiny prompts; longer on the report). The writing line covers the wait on screen. Phase 9 records the time to the first words and the report's wall time against today's.
- **Sol stalls on Bedrock.** In the feasibility rerun, Sol timed out seven times at 300 s on one task (`research/report-synthesis-feasibility/round2/`). A stalled stream would wait out the 300 s timeout (which, when streaming, measures the gap between pieces) before falling back. Phase 4 adds a shorter time-to-first-content limit on the streamed call, so the fallback starts sooner. The limit lives in `model_routes.toml`, not in code. Before phase 4, the lead measures the thinking wait on one real report and sets the limit from it, with margin.
- **Retries multiply.** There are three retry layers today. S4 keeps the streamed call outside the inner two.
- **The 058 frames may assume an Evidence search artefact** (S6). The first build step checks this before anything depends on it.
- **The swap changes numbers.** Citation renumbering and pathway sorting happen in code (S7).
- **Early grades are provisional.** Per-connection colours are shown before classify and appraise finish (S8).
- **The prompt-hash rule.** Every prompt change is a version bump, a re-pin and a replay.
- **Evidence search and Options scoping regressions.** Phases 3, 4 and 6 touch shared code (the stage vocabulary, the live frames, `RunTrace`). Their existing tests must pass unchanged at each of those gates.
- **The fill order is not the page order** (S6). Accepted by the owner.

## 8. Design notes (the owner's rulings on the mock, 2026-11-09)

- **The mock:** `research/mock/mock.html` (gitignored; the source is in the lead's scratchpad). Round 1 built 11 scenes; round 2 made the draft and the check one card and added the upload journey; round 3 kept the report's content as it is. **Where the mock and these notes differ, these notes win**, as 058's annex does over its mock.

### Behaviour
- **One card for the automatic chain**, separate cards for the walks the reader starts (decision 5). The uploaded theory really stops after the read: the draft walk carries `TOC_REVIEW_FIRST_KEY`, and the check starts only from "Check the evidence" (`api/toc_start.py`, `run_toc_sequence`).
- **No "draft landed" message in the automatic chain** (decision 13).
- **The sidebar does not open by itself.** The run status bar shows the run on every tab except Agent, and steps aside only while the sidebar shows the Task Agent (decision 11).
- **The report's content does not change** (decision 4). The header keeps its four parts, and the report title stays the `h1`.
- **The report sections keep today's order:** Summary, Pathways, How it could fail, What to test first, How it could be expanded, Supporting activities, Assumptions, References.
- **"Policy Atlas is checking each step against the evidence. Steps take their colour as they are checked."** is removed. The run status bar says it.
- **The verdict line** shows as soon as writing begins: the verdict is decided before the report call, so only the timing changes.
- **The assumptions table** keeps all its columns, including Sources.
- **Download** arrives with the committed report (058).
- **"Update the report":** the old report stays, with the `ActionLine`, until the new one swaps in. The update does not stream over it.
- **Including a set-aside pathway again** is not built in this pass (S11). When it is, it changes the theory, so the report shows the stale line.
- **The live report fills in the order written**, not page order (S6; owner, 2026-11-09).
- **"The report's sections are set out when writing begins."** is removed. Before writing starts, nothing shows under the canvas.
- **The detail panel:** small consistency changes only (decision 12 in § 4 E).

### Copy
**Step rows**, as the server's labels:
- Drafting the theory
- Reading your diagram (an upload's read)
- Searching for each connection
- Screening
- Looking for other routes
- Merging similar steps
- Searching for the new connections
- Judging the evidence
- Searching again for thin connections
- Finding the size of change
- Classifying (shared)
- Choosing pathways
- Writing titles and summaries
- **Writing the report** (the owner's word; no count)

Blurbs as in `research/mock/brief.md`. The ToC plan has no steps, so the blurbs show nowhere today.

**Done counts and links** as in the brief's table, for example "Searching for each connection · 17 searches · 412 found · Sources →".

**Finish words:** "Evidence checked · Read it →", and "Theory drafted · Read it →" for an upload's read.

**The plan's ToC sections:** "Search filters", "Publication years", "No preference", "From 2000" (as Evidence search).

**The banner after an upload stays as it is today** (the owner declined the shorter version).

**Smaller copy changes:**
- The suggestion cards lose their uppercase eyebrows.
- The citation sheet drops "Open the source"; the title opens the source details, with "Back to the claim".
- The new task form shows the file name with an icon from `icons.tsx` in place of 📄.
- The plan card reads "Theory of change plan" over the plan's title.
- "Not enough evidence" takes a light grey (Line 2) tone square; the canvas line stays a faint dashed grey.
- The set-aside line reads "Set aside by Policy Atlas · Too little evidence for 2 of its 4 connections."
- **The document controls keep their words, "Remove" and "Restore"**, as the colleague wrote them (owner, 2026-11-09). They get the quiet control style. Their tooltips:
  - "Remove": "Leave this document out of this connection's evidence."
  - "Restore": "Count this document in this connection's evidence again."
- There is no pathway control in this pass (S11), so the pathway tooltips wait for it.
- The facts line reads "Sources 21 cited out of 412 found · Published 2003–2025" (the figures from the task).

**Kept from the audit's list:**
- Removing the draft estimate (decision 5).
- The stale line, "Written before your latest changes." with "Update the report" (decision 10).

**Not taken from the audit's list:**
- The shorter banner (declined).
- The Assumptions intro as an info hint, and FindMore's help as an info hint. Both would change the detail panel or the report; the owner keeps their content.
- Deleting the References footer. It stays as it is today.

### Owner sign-off
The mock rulings were accepted on 2026-11-09. The polish passes (phase 8) record their rulings here.

**Owner pass on the live app, 2026-11-10:**
- The report's contents sit inside the paper, at the right of Summary to Supporting activities. The canvas and the Assumptions table use the full width (as before phase 6). The contents stay on the right.
- The verdict line has a rule in its tone (2px, as Evidence search's claim rule), not a tone square.
- Report lists use the shared square bullet (`BulletList`), as in the other capabilities. The detail panel and suggestions take the bullet shape only.
- A connection being searched or checked is a thicker, darker grey line that breathes on the shared 1.6 s rhythm, arrowhead included (still under reduced motion). Blue was dropped because it read like a verdict colour; a travelling dot was dropped as too busy. The canvas key shows "Being checked" only while a check runs.
- "What to test first" is numbered in the live report too, so its markers do not change when the finished report replaces it.
- The task is named by Policy Atlas at Start (`task_title`), as in Evidence search and Options scoping.
- The first draft is drawn live on the canvas (S12).
- Per-request timeouts of each ToC step are about 1.5 to 2 times its slowest answered call (measured 2026-10-25 to 2026-11-10). A healthy call cut off costs one more try.

## 9. Acceptance items for this pass

Each item names its check. "Test" means a new or changed automated test, named in `verification.md`.

### The stage keys (S1)
| Stage key | Component(s) or fan-out mapped | Label (§ 8) | Done counts |
|---|---|---|---|
| `toc_draft` | `toc_draft` (draft walk, not `review_first`) | Drafting the theory | boxes, connections, pathways |
| `toc_read` | `toc_draft` in a `review_first` draft walk, by the stamped `"stage"` (S1) | Reading your diagram | boxes, connections, pathways |
| `toc_item_searches` | the check's first fan-out (`TOC_ITEM_SEARCHES_STAGE`) | Searching for each connection | searches, found |
| `toc_select` | `toc_select` | Screening | read, relevant |
| `toc_discover` | `toc_discover` | Looking for other routes | routes found |
| `toc_merge` | `toc_merge` | Merging similar steps | merged |
| `toc_search_new` | `toc_search_new` | Searching for the new connections | connections |
| `toc_new_link_searches` | its fan-out (`TOC_NEW_LINK_SEARCHES_STAGE`) | Searching for the new connections (merged row) | searches, found |
| `toc_judge` | `toc_judge` | Judging the evidence | judged, test them |
| `toc_search_again` | `toc_search_again` | Searching again for thin connections | connections, judged |
| `toc_retry_searches` | its fan-out (`TOC_RETRY_SEARCHES_STAGE`) | Searching again for thin connections (merged row) | searches, found |
| `toc_figures` | `toc_figures` | Finding the size of change | figures |
| (shared) `classify`, `appraise` | as today | Classifying | as today |
| `toc_choose` | `toc_choose` | Choosing pathways | kept, set aside |
| `toc_summarise` | `toc_summarise` | Writing titles and summaries | — |
| `toc_report` | `toc_report` | Writing the report | — |

15 ToC keys; with the 19 keys today, 34 in all. Rows with the same label merge into one row in `cardRows` (S1).

- The blurbs are as in `research/mock/brief.md`. A key that cannot be mapped as written stops the build and goes back to the lead.
- The counts the client derives today ("set aside" = read − relevant; "test them") become integer count keys on `component.completed`, so `stage.completed.counts` carries them.

### Acceptance items
| # | Item | Check |
|---|---|---|
| A1 | `StageKey` and `STAGE_KEYS` hold the 15 ToC keys of the table (34 in all), and so does `PlanStageKey`; `STAGE_PRESENTATION`, `STAGE_ROW`, `STAGE_COUNTS` and `STAGE_BY_REGISTRY` cover them; `make openapi-sync` regenerates the frontend types | `test_stage_vocabulary.py` coverage tests extended; `make drift-check` |
| A2 | A ToC check walk emits `stage.started` and `stage.completed` for each step with the table's label and counts. A ToC walk's `RunOut.stages` and `active_run.stage` / `stage_label` are filled | backend SSE and runs-read tests on a stub ToC walk |
| A3 | Fan-out progress on a ToC walk carries the ToC key and label, never `option_searches` / "Searching for each option". An Options scoping walk is unchanged | `test_option_search.py`: `_publish_progress` stage test for both capabilities |
| A4 | Activity ticks: the fan-outs ("n of M searches done · S found"), screening ("n of M read · R relevant") and the judge ("n of M documents") publish through the shared `ACTIVITY` templates, throttled as 058's ticks are | unit tests on the loops' tick publishing |
| A5 | The run read exposes the walk kind (draft, read, check, report update) and, for a check the server started after a draft, the draft's walk id, read from `evidence_scope.context["draft_capability_run_id"]` | API contract test; `make drift-check` |
| A6 | `walkKind` and `READY_WORDS` gain the ToC kinds ("Theory drafted", "Evidence checked"); `resultHref` points at the ToC Result | `taskStatus` and `runProgress` unit tests |
| A7 | A draft and its follow-on check render as one `RunTrace` card: one timer from the draft's start, the draft row first, the check's finish words. A walk the reader starts gets its own card | `TaskAgentPane` / `RunTrace` tests with a two-walk fixture |
| A8 | `DRAFT_LANDED_MESSAGE` is not posted when the check follows automatically; the check's end message and the upload's review message stay | `test_toc_start` (or the walks test) |
| A9 | `TocTrace.tsx` is deleted, and no ToC step copy remains in `frontend/src` | the guard in `runProgress.test.ts` passes with its `TocTrace` exemption removed |
| A10 | The run status bar and the task list row show the step label and activity for a ToC walk. The ToC sidebar does not open by itself | `RunStatusBar` / `TaskListRow` / `ChatSidePanel` tests |
| A11 | `toc_report` streams: one streamed call outside the inner retry loops, with a time-to-first-content limit; on failure `replace ""`, then one non-streamed fallback. A skeleton of the report's parts comes first; each field publishes in the order written and gets `section_completed` when it closes; the fallback sends a fresh skeleton and `replace ""` per part. `[n]` shows as `[·]`; a marker split across deltas is held | backend tests with a scripted stream (success, mid-stream failure, no first content, reconnect after two closed fields, a split marker); prompt hash unchanged (`make prompt-guard` with no re-pin) |
| A12 | The committed report from a streamed call equals the report from the same response parsed without streaming, and the request sent is the same apart from `stream` | test: one canned response fed through both paths gives an identical stored payload |
| A13 | The ToC Result renders the live report in the order written, each part in its page place, with `◆ Writing`, `[·]` chips and no revising; it swaps in place to the committed report | frontend test with the frames fixture; e2e scene |
| A14 | The report page uses `ReportPage`: kind row with Download (committed only), date line, facts line, contents, h2 sections, the expand state. The header's four parts are unchanged; the report title is the `h1` | `TocResult` / `DetailedInformation` tests |
| A15 | References use the shared form; the citation sheet is the shared one with source marks and the dossier with "Back to the claim"; "Open the source" is gone | frontend tests |
| A16 | The judge commits each connection's evidence through its own connection in a short transaction, updates `counted_hash`, and skips connections already written by the same run at the current hash; the step sends one `toc.changed`; the canvas shows a connection's tone before the judge step ends | backend test (a retried judge leaves no duplicates); frontend test on a mid-walk graph read |
| A17 | The report read carries `stale`: true after a content edit, undo or evidence decision made after the report walk's `run.started`; a box move does not count. The page shows "Written before your latest changes." with "Update the report", and the `ActionLine` while the update runs; the old report stays until the swap | backend read test; frontend test |
| A18 | § 4 E: the audit's findings 3–17, as ruled in § 8, are closed or recorded as kept. The detail panel's content and order are unchanged | the lead's checklist in `verification.md`; polish pass sign-off |
| A19 | The copy in § 8 is shipped word for word. The copy guard in `runProgress.test.ts` lists the ToC labels | grep-based test of the strings where practical; polish review |
| A20 | Live: on the 3 local tasks on `bedrock`, a full draft and check shows one card, the status bar and a streamed report. The time to first words and the report's wall time are recorded against today's | `verification.md` live section |
| A21 | The upload's read reports as `toc_read`: the runner stamps `"stage"` on the `review_first` draft walk's payloads and `stage_for_payload` reads it first | backend test: the same component reports `toc_draft` in a draft walk and `toc_read` in an upload's |
| A22 | Only a first report streams. "Update the report", and a check while a report exists, send no section frames; the old report stays until the swap | backend test (no `artefact.section_delta` on an update); frontend test |
| A23 | Between the walks the card stays "Running" with the draft row done; a refused check ends the card with the draft's finish words and today's refusal message | `RunTrace` test with a two-walk fixture and a refused check |
| A24 | Evidence search and Options scoping are unchanged: their stage, live-frame and run-trace tests pass with no edits, at the phase 3, 4 and 6 gates | `make verify`; the diff shows no edits to those tests |

## 10. Spec changes

| # | Change | Status |
|---|---|---|
| S-1 | `docs/specs/system/web-api.md` § SSE: the stage-key list gains the ToC keys (S1) | accepted by the owner 2026-11-09; applied in phase 2 and logged in `docs/specs/log.md` |
| S-2 | `docs/specs/capabilities/theory-of-change/capability.md`: the report streams to the page as it is written (its content is unchanged) | accepted by the owner 2026-11-09; applied in phase 2 and logged in `docs/specs/log.md` |
| S-3 | The same file: the canvas colours each connection as it is judged; a report written before the reader's edits says so | accepted by the owner 2026-11-09; applied in phase 2 and logged in `docs/specs/log.md` |
| S-4 (possible) | `docs/specs/system/web-api.md` § SSE: the skeleton frame names a part's role (`LiveSectionRole`, S6), if phase 4 cannot place the ToC header parts without it | not yet proposed; the lead brings it to the owner at phase 4 only if needed |

## 11. ADR

An amendment to [ADR 0042](../../adr/0042-theory-of-change-task-kind.md), written in phase 2. It records:
- the streamed report call;
- the stage keys;
- the per-connection commits;
- the split with the follow-up PR.

It points at [ADR 0044](../../adr/0044-live-activity-streamed-sections-one-copy-source.md) for the shared live machinery.
