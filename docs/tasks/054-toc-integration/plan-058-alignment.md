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
4. **The report streams section by section**, reusing 058's report-section frames and live report view.
5. **What changes from `TocTrace`:**
   - The per-search lines move to the Sources tab's "Search queries".
   - The outcome counts stay, as server counts on the finished rows.
   - The draft and the check stay separate cards.
   - "Usually takes 1 to 2 minutes" and the per-step timer go.
6. **Finish words:** "Theory drafted · Read it →" and "Evidence checked · Read it →". A failure reads "Stopped" or "Failed".
7. **Verdict colours:** the shared tones everywhere, the canvas lines included. The dash patterns stay.
8. **The rounded canvas boxes stay** (contract W2).
9. **The canvas colours each connection as soon as it is judged.**
10. **After the reader's edits** the report says "Written before your latest changes." with "Update the report". The update stays the reader's action.
11. **The Task Agent sidebar stays open by default** on ToC tasks (a colleague's ruling).
12. **The audit's 11 copy proposals** go to the owner one by one with the mock (phase 1).

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
  - Written section by section on Sol, one streamed call per section with no tools.
  - Each section's claims checked by the shared grounding judge, with repair.
  - 058's frames and the live report view; the committed report swaps in place.
  - The connections table, the title and the verdict label stay built by code or by their own calls.
- **D. The report page**
  - The shared `ReportPage` shell: the question as `h1`, the date line, the facts line, Download in the kind row, the contents, an h2/h3 outline, the expand state.
  - The shared References.
  - The full citation sheet: source marks, the dossier with "Back to the claim".
- **E. Consistency**
  - The audit's findings 2–18: the phone canvas, buttons, links, disclosures, close and icons, typography and callouts, dates and counts, plan sections, plan card, shadows, status words.
  - The detail panel in the option card's pattern.
  - Set-aside pathways as "Exclude" / "Include again".
  - The public link read-only.
  - Per-connection commits in the judge, so the canvas colours connection by connection.
  - The stale-report line.

**Out of scope (the follow-up PR, or later)**
- Changing any model.
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
  - `walkKind` and `READY_WORDS` gain the two ToC kinds.
  - `resultHref` points at the ToC Result.
- **S4. The section writer.**
  - A new prompt version (`toc_report_v8`): a per-section request returning `{prose, claims[{text, sources[n]}]}` under a strict schema, streamed and decoded on `prose`.
  - Sections run one after another, and each publishes deltas to its display index.
  - The connections table's reasons and the title come from one non-streamed structured call, run alongside.
  - Any retry sends `replace ""` first. The streamed call runs once, outside both inner retry loops; one non-streamed fallback is the retry.
- **S5. The claim check.**
  - Each claim's `[n]` maps to that source's abstract chunk and judge quote.
  - The shared `judge_grounding` checks it.
  - Failed claims go to a lead-written repair request (S4's prompt family); the revising frames carry the spans.
- **S6. The frames.**
  - The ToC report emits 058's `artefact.skeleton` (its section list), then the section deltas, revising, claim and completed frames.
  - The build's first step confirms that the skeleton and `section_completed` fit a report that is not an Evidence search artefact. If they do not, it adds the smallest generalisation and the lead records it here.
- **S7. The swap.** The live view hands over to the committed report from `GET /toc`. Citation numbers and the pathway order may change at the swap: they fade in as 058's swap does.
- **S8. Per-connection commits.**
  - The judge writes each connection's evidence rows in a short transaction of their own, idempotent under a component retry.
  - The canvas refetches on a ToC `stage.completed`, and on a tick or a 5 s poll while the judge runs.
  - The grade shown before classify and appraise finish is the provisional one; the edges keep the "checking" style until the walk ends.
- **S9. Stale report.** The report read carries `stale` (edits since the report was written). The page shows "Written before your latest changes." with "Update the report", and the `ActionLine` while the update runs.

## 6. Phases

| Phase | What | Executor | Gate |
|---|---|---|---|
| **0** | Copy the 058 digest into `research/`. Fix the phone canvas (`max-lg:flex-none`). | lead | `make frontend-verify` |
| **1** | **Mock.** The ToC run card (live, paused and ended, for the draft and the check); the run status bar; the task row; the live report streaming section by section with its checks and revising; the report page in `ReportPage`; the detail panel in the option card's pattern; the canvas colouring connection by connection; the stale line. Built from a real dev task's data. | frontend-designer (loads the design skills) | — |
| **🛑 1b** | The owner reviews the mock and the 11 copy items. The lead records the rulings in § 8 (design notes). | owner | — |
| **2** | Acceptance items for this pass written into § 9, then a contract-stage adversarial review (one fresh read-only lane). Spec change S-1 applied and logged. | lead + one reviewer | — |
| **3** | **Server progress (S1–S3).** Stage keys, presentation, rows, counts, registry, the fan-out stage, activity ticks, the walk kind; `make openapi-sync`. | deep-reasoner (Opus) | full `make verify` (contract change), `make drift-check` |
| **4** | **Report writer (S4–S7).** Prompts by the lead first: section, repair, the table-and-title call; replayed on the 3 local tasks; pinned. Then the backend streaming, judge, repair and frames. | lead (prompts), then deep-reasoner | `make prompt-guard`, `make verify` |
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

- **The report gets slower.** Sol thinks before each section's first words, so 6–8 sections one after another may take longer than today's single call (33 s on the dev task). The writing line covers the wait on screen. Phase 9 measures the report's wall time. If it is more than twice today's, the owner chooses: sections written in parallel and shown one at a time, or fewer sections.
- **Retries multiply.** There are three retry layers today. S4 keeps the streamed call outside the inner two.
- **The 058 frames may assume an Evidence search artefact** (S6). The first build step checks this before anything depends on it.
- **The swap changes numbers.** Citation renumbering and pathway sorting happen in code (S7).
- **Early grades are provisional.** Per-connection colours are shown before classify and appraise finish (S8).
- **The prompt-hash rule.** Every prompt change is a version bump, a re-pin and a replay.

## 8. Design notes (filled after the mock; the owner's rulings)

Empty until phase 1b.

## 9. Acceptance items for this pass (written in phase 2)

Draft list, to be made testable in phase 2:
- **Progress**
  - A ToC walk's steps reach the client as `stage.started` and `stage.completed` frames, with server labels and counts.
  - No ToC step copy stays in `frontend/src`. The guard in `runProgress.test.ts` holds without its `TocTrace` exemption.
  - The run status bar and the task row show the step and the activity for a ToC walk.
  - The finished card reads the ToC finish words and links to the ToC Result.
  - Search progress during a ToC check never says "Searching for each option".
- **The report**
  - It streams section by section on Sol.
  - Each section's claims are judged, and a failed claim is repaired or removed.
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
| S-2 | `docs/specs/capabilities/theory-of-change/capability.md`: the report is written section by section, streamed, and its claims are checked against the sources | accepted by the owner 2026-11-09; applied in phase 2 and logged in `docs/specs/log.md` |
| S-3 | The same file: the canvas colours each connection as it is judged; a report written before the reader's edits says so | accepted by the owner 2026-11-09; applied in phase 2 and logged in `docs/specs/log.md` |

## 11. ADR

An amendment to [ADR 0042](../../adr/0042-theory-of-change-task-kind.md), written in phase 2. It records:
- the report's section writer with the shared grounding judge;
- the stage keys;
- the per-connection commits;
- the split with the follow-up PR.

It points at [ADR 0044](../../adr/0044-live-activity-streamed-sections-one-copy-source.md) for the shared live machinery.
