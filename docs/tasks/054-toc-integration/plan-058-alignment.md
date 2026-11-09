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
4. **The report streams in page order (changed 2026-11-09).** Today's single `toc_report_v7` call streams unchanged: same prompt, model and content, and no hash change. Its fields fill the page top to bottom as the model writes them, through 058's report-section frames and live view. **The report's content does not change in this pass; only its formatting and presentation do.** The header above the canvas keeps all four parts: title, verdict and headline, question, "what would settle it". Writing each section with its own call, and the claim check with repair, move to the follow-up PR (owner, 2026-11-09).
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
- Filling the canvas while the draft is written: the draft commits once and its retry would undo streamed boxes.

## 5. Seams the build fixes

- **S1. Stage keys.**
  - Add one key per ToC step the reader sees, and one per fan-out (`toc_item_searches`, `toc_new_link_searches`, `toc_retry_searches`).
  - Rows group them as the server decides.
  - `STAGE_BY_REGISTRY` maps the `toc_*` components.
  - `option_search._publish_progress` takes the stage.
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
  - The ToC report emits 058's `artefact.skeleton` (its section list), then the section deltas, revising, claim and completed frames.
  - The build's first step confirms that the skeleton and `section_completed` fit a report that is not an Evidence search artefact. If they do not, it adds the smallest generalisation and the lead records it here.
- **S7. The swap.** The live view hands over to the committed report from `GET /toc`. Citation numbers and the pathway order may change at the swap: they fade in as 058's swap does.
- **S8. Per-connection commits.**
  - The judge writes each connection's evidence rows in a short transaction of their own, idempotent under a component retry.
  - The canvas refetches on a ToC `stage.completed`, and on a tick or a 5 s poll while the judge runs.
  - Each connection takes its verdict tone as soon as it is judged (owner decision 9).
  - The grade shown before classify and appraise finish is provisional. It may shift once more when they land.
- **S9. Stale report.** The report read carries `stale` (edits since the report was written). The page shows "Written before your latest changes." with "Update the report", and the `ActionLine` while the update runs.

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
- **Sol stalls on Bedrock.** In the feasibility rerun, Sol timed out seven times at 300 s on one task (`research/report-synthesis-feasibility/round2/`). A stalled stream would wait out the 300 s timeout (which, when streaming, measures the gap between pieces) before falling back. Phase 4 adds a shorter time-to-first-content limit on the streamed call, so the fallback starts sooner. The limit is set from the measured thinking wait, with margin.
- **Retries multiply.** There are three retry layers today. S4 keeps the streamed call outside the inner two.
- **The 058 frames may assume an Evidence search artefact** (S6). The first build step checks this before anything depends on it.
- **The swap changes numbers.** Citation renumbering and pathway sorting happen in code (S7).
- **Early grades are provisional.** Per-connection colours are shown before classify and appraise finish (S8).
- **The prompt-hash rule.** Every prompt change is a version bump, a re-pin and a replay.

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
- **Including a set-aside pathway again** changes the theory, so the report shows the stale line.
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
- The tooltips:
  - document "Exclude": "Leave this document out of this connection's evidence."
  - document "Include again": "Count this document in this connection's evidence again."
  - pathway "Exclude": "Leave this pathway out of the theory and the report."
  - pathway "Include again": "Put this pathway back in the theory and the report."
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

## 9. Acceptance items for this pass (written in phase 2)

Draft list, to be made testable in phase 2:
- **Progress**
  - A ToC walk's steps reach the client as `stage.started` and `stage.completed` frames, with server labels and counts.
  - No ToC step copy stays in `frontend/src`. The guard in `runProgress.test.ts` holds without its `TocTrace` exemption.
  - The run status bar and the task row show the step and the activity for a ToC walk.
  - The finished card reads the ToC finish words and links to the ToC Result.
  - Search progress during a ToC check never says "Searching for each option".
- **The report**
  - It streams in page order on Sol, from today's unchanged call.
  - Its committed content matches a non-streamed run of the same call; only presentation differs.
  - The live page hands over to the committed report in place.
- **The report page**
  - It uses `ReportPage`, the shared References and the full citation sheet with the dossier and "Back to the claim".
- **Consistency**
  - The audit's findings 2–18 are closed, or recorded as kept on purpose.
  - The canvas shows at 400 px wide.
- **Per-connection colours and the stale report**
  - The canvas colours connections before the judge step ends.
  - After an edit, the report reads "Written before your latest changes."

## 10. Spec changes

| # | Change | Status |
|---|---|---|
| S-1 | `docs/specs/system/web-api.md` § SSE: the stage-key list gains the ToC keys (S1) | accepted by the owner 2026-11-09; applied in phase 2 and logged in `docs/specs/log.md` |
| S-2 | `docs/specs/capabilities/theory-of-change/capability.md`: the report streams to the page as it is written (its content is unchanged) | accepted by the owner 2026-11-09; applied in phase 2 and logged in `docs/specs/log.md` |
| S-3 | The same file: the canvas colours each connection as it is judged; a report written before the reader's edits says so | accepted by the owner 2026-11-09; applied in phase 2 and logged in `docs/specs/log.md` |

## 11. ADR

An amendment to [ADR 0042](../../adr/0042-theory-of-change-task-kind.md), written in phase 2. It records:
- the streamed report call;
- the stage keys;
- the per-connection commits;
- the split with the follow-up PR.

It points at [ADR 0044](../../adr/0044-live-activity-streamed-sections-one-copy-source.md) for the shared live machinery.
