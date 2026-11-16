# Task 054: simplification review before the adversarial review

Date: 2026-11-05. Branch `task/054-1-core` at 93565851, compared with `origin/dev` (3d276c21):
117 commits, 283 files, about 61k lines added. Product code in scope: the
`theory_of_change` package (12.3k lines), the ToC API and runtime files (4.2k), the ToC
frontend views (5.5k), and every shared backend and frontend file the branch touched.
Prompt text and the eval scripts under `scripts/evals/theory_of_change/` were not reviewed.

Five read-only reviews, one per area, each finding checked by grep for callers. The
headline items were re-checked by hand. Nothing has been changed yet.

Totals: about **1,200 lines** can go with no change in what the product does. The bigger
win is not the line count but the drift risk: the same query, the same rule or the same
widget is written two to six times in several places, and the copies have already started
to disagree (see § 4).

## 0. Status (2026-11-05, same day)

Applied in five commits on `task/054-1-core` (bc0917ce, 97f86c2a, 0a32853d, f81d8989,
97e7e397). `make verify-fast` is green: 4,364 tests, mypy and ruff clean, drift-check and
prompt-guard pass. Net about 1,000 lines less.

Owner decisions on § 1: the chat sidebar opens by itself only on a theory-of-change task;
finish alerts stay for every task kind; History reads the theory only for a ToC task; only a
ToC search writes `source.seen_again`; the child plan is parsed at dispatch again; Langfuse
masking stays global (measured 0.8 ms per call on a 1.4 MB payload).

Skipped, with the reason: the `TocBackend` Protocol and `admit_and_mint` shape (house
convention); `DraftFailure` (the runner records the exception's class name); `route_ops`
(the two builders are not byte-identical); the `DEFAULT_PUBLISHED_AFTER` double default
(it would change the stored plan payload); `usePanelWidth` on `useRail` (different start
and keyboard semantics; dev's rail at risk); the code-splitter merge (different boundary
rules); the third upload preview (not a link); the two step-label vocabularies (a copy
decision). Three gate fixes rode along: migrations before every conformance request,
timeout sites for the ToC steps, and the mypy errors in two ToC test files.

Visible differences, all small: the chat pane's paperclip uses the New Task page's glyph;
the More menu opens with the Download menu's 150 ms scale-in and closes on Esc; the
Download and More menus now show in full screen (a bug fix). § 4 is still open for the
adversarial review.

## 1. Shared files that change evidence search or options scoping

The branch was meant to leave the other two capabilities alone. These hunks do not. Each
needs a decision: keep as a deliberate product change, or gate it on the ToC capability.

### Frontend

| Where | What changes for every task kind | Suggested call |
|---|---|---|
| `views/workspace/chat/ChatSidePanel.tsx:85-94` | The Task Agent chat sidebar now opens by itself on every task page (evidence search and scoping too) unless the user closed it before. Mounted from `AppShell.tsx:473`. | Decide. If it was only meant for ToC, gate on `isToc`. |
| `api/mutations.ts:247-254` + `lib/askForAlerts.ts` | Every Start click now triggers the browser's notification-permission prompt. | Decide. Fine if finish alerts are wanted everywhere. |
| `views/AppShell.tsx:300` + `views/finishAlerts.ts:75` | Finish alerts ("Your results are ready", "Policy Atlas has a question for you") fire for every task kind. The test asserts the evidence-search alert on purpose. | Looks deliberate. Confirm. |
| `api/queries.ts:186` | The shared tasks-list query polls every 15 s while the tab is hidden, on every page. | Keep only if the alerts stay. |
| `views/HistoryView.tsx:31` | Sends `GET /toc` for every task; a 404 for non-ToC tasks. `taskResult.ts:39` already shows the gated form. | Gate: `useToc(isToc(task.data) ? taskId : "")`. 1 line. |
| `views/NewTaskView.tsx:354-381` | The question box now grows with the text for every capability; the submit button sits in a new column. | Looks harmless. Confirm. |
| `views/SourcesLayout.tsx:15-20` | Themes renders nothing until the task loads. | Harmless. |

### Backend

| Where | What changes for every walk | Suggested call |
|---|---|---|
| `evidence_search/sourcing/acquire.py` | Every acquire now writes a `source.seen_again` event when it meets a document the task already holds. Only `theory_of_change/check.py:1410` reads it. The dev test was changed to expect it. Grows `event_log` on every evidence search. | Gate on the ToC capability, or accept the extra rows. |
| `runtime/option_search.py:323-363` | The options child's plan is now resolved inside the worker through a new database lookup (`child_plan`), after the scope row is inserted. One extra round trip per option search. A malformed plan now leaves a `targeted` scope row and a failed child, where dev raised before the insert. | Put the resolved plan on `ChildSearchRequest` instead; restores dev's path exactly (-12 lines). |
| `runtime/option_search.py:914-945` | `abandon_children` runs three queries (one per stage) instead of one. Same result. | One query with the stage in an `IN` list. |
| `core/tracing.py` | Langfuse now masks base64 file strings in every trace, which walks every payload of every evidence-search trace. Output unchanged for non-ToC. | Accept, or make the walk cheap (skip when no string starts with `data:`). |
| `api/app.py` | CORS now also allows `DELETE` for the whole app. | Accept (ToC needs it). |

Everything else in the shared files is gated on the ToC capability or is additive
(new registry keys, new constraint values, new CSS variables, optional props with old
defaults). The runtime review found no copy of the task-agent loop: `task_agent_toc.py` is
a profile like the scoping one, and `toc_plan.py` is a third plan model, not a copy.

## 2. Recommended cuts, by area

Each line: location, tag, what, replacement, estimated lines saved. Tags: delete, dup
(duplicates code elsewhere), yagni (one implementation, nobody sets it), shrink, stdlib or
native (the platform or an existing helper already does it).

### 2.1 Dead surface (delete, about -110)

- `api/routers/toc.py:1434-1449` + `contract/toc.py:758-763`: delete `POST /clarifications` and `TocClarificationIn`. No frontend, test or script calls it. The chat already writes the clarification event (`runtime/task_agent_toc.py:212`), so contract C49 holds. -24
- `contract/toc.py:537-542`: delete `TocRevisionIn`, referenced nowhere. -8
- `contract/toc.py:597`: drop `"rest"` from `TocCheckIn.mode`; nothing sends it or branches on it. 0
- `contract/toc.py:629` + `routers/toc.py:1189`: delete `TocUploadOut.content_type`, read by nothing. -2
- `core/uploads.py:65-67, 90-91, 116-117`: `UploadStore.delete` has no production caller (only its own test). -12
- `core/uploads.py:142-153, 218-226`: `Upload.task_id`, `.purpose`, `.size_bytes` are never read; `find` copies seven columns by hand. Trim to the four fields used. -6
- `runtime/toc_plan.py:164-176, 196, 220, 330`: `TocFromOption`, `from_option` and the `inherit` branch of `compose_toc` are "None until increment 7"; nothing in `backend/src` sets them. Delete and add back in increment 7. -20
- `runtime/toc_plan.py:224-230`: `drop_retired_fields` validator exists for plans saved on 2026-11-04 on this unmerged branch. Delete unless such plans exist in a shared database. -7
- `runtime/toc_plan.py:59, 341-342`: `TOC_WALK_RECHECK` "lands in increment 2"; the fall-through `ValueError` already covers it. -4
- `runtime/toc_plan.py:142, 149`: `TocEvidenceRestriction.country_group` is set by nothing (`TocPlanPatch` has years only). -2
- `runtime/option_search.py:215-221`: `ChildSearchRequest.stage` is never read. -4
- `core/schema.py:246` + migration `9127f849697f`: conversation kind `stress_test` ("used from increment 4") has no use. Drop from the constraint while the migration is unmerged. -1
- `theory_of_change/check.py:1926-1981`: the pre-C31 path (`_own_search_documents` and the `None` branch of `_walk_picks`). `toc_select` is the first step of every check chain, so the picked event always exists when the judge runs; the feature is unmerged, so no older walks exist outside local databases. `test_light_check.py:376` uses the helper as an oracle and needs its own query. -30
- `theory_of_change/check.py:179`: `Document.score` is set in four places and read in none. -4
- `theory_of_change/check.py:2489-2499`: `not_models` in `toc_choose` feeds one log line and nothing else. -10
- `theory_of_change/report.py:114`: `LinkFacts.target_layer` set, never read. -2
- `theory_of_change/draft.py:59-60`: `DraftFailure` is raised once and caught nowhere; `RuntimeError` behaves the same. -3
- `theory_of_change/edits.py`: unreachable guards. The unknown-field checks (150-152, 186-188) cannot fire because the router builds `fields` from the patch model; `"sentence"` in `LINK_FIELDS` has no sender; `create_link(for_text=)` has no caller; `move_box`'s x/y check (the router sends both); `history(limit=)` never overridden; `_STEP_TEXT["toc_search_new"]` is never recorded. -13
- `theory_of_change/check.py:375-377`: `_current_hash` recomputes a hash the judge loop already has. -4
- `theory_of_change/check.py:2712-2714`: `check_citations` is `set(cites) <= allowed`; inline at its two sites. -4
- `evidence_search/sourcing/search_loop.py:1751`: `generation_calls = 1` is never reassigned. -2
- `runtime/runner.py:1030`: `resume_from is None and ...` guards a state the comment says cannot happen. -1
- `views/toc/Editing.tsx:322-347`: `HistorySection` has no callers; `HistoryView.tsx` renders its own table. -26
- `views/toc/types.ts:8-18`: `TocResultCriteria`, `TocWeights`, `TocGradeRule`, `TocLinkEvidence`, `TocCaseStudy` have no importers. -5
- `api/queries.ts:667-681`: the `TocGet` hand cast says the routes are "not in the generated client yet"; they are (`gen/types.ts:1189`, `:1373`), and `finishAlerts.ts:66` already calls them typed. Use `client.GET` directly. This also removes the api→views import at `queries.ts:8`. -15
- `api/mutations.ts:428-436`, `api/queries.ts:744-746`, `PlanDocument.tsx:1039`, `TaskAgentPane.tsx:869-870`: orphaned JSDoc blocks stranded by the iterative build; move onto their functions or delete. -8
- `workspace/TaskAgentPane.tsx:343`: `export { UPLOAD_MESSAGE }` has no importers. -1
- About 20 frontend symbols exported but used only inside their own file (`shortAuthors`, `TocCitation`, `previewOf`, `CanvasEditing`, `TocTraceView`, `tocYearsLabel`, `DownloadItem`, `exportName`, `ReadingGuide` internals, eight names in `tocModel.ts`, three in `fixture.ts`). Drop the `export` keyword. 0 lines, less surface.

### 2.2 Copies of the same thing (dup, about -480)

Backend queries and rules:

- Six copies of "task_source_snapshot joined to source_snapshot for these ids, give me metadata" (`check.py:2879-2898`, `:1423-1438`, `:1759-1767`; `figures.py:169-195`; `report.py:370-388`; `seminal.py:92-103`). One `snapshot_meta(conn, task_id, ids)` next to `screened_documents`. -45
- `check.py:665-733` (`_route_suggestion`) and `draft.py:439-521` (`suggest_the_rest`) both turn a route into add_box → add_link → add_pathway ops with r1, r2 grouping. One `route_ops(...)` in `proposals.py`. Inputs differ (box keys vs link keys), so this needs care. -30
- `report.py:687-709, 719-743, 752-766`: "number this source once, reuse for the same work, append the entry" written three times. One closure. The third copy skips `same_work` de-duplication; pass a flag. -25
- `check.py:515-516` `_call`: every one of ten callers passes `event == name`; six single-call sites wrap it in `_outcome_value` the same way. Drop the parameter, add `_ask(name, fn, usage)`. -25
- `check.py:312-355`: `counted_judgements` and `pending_judgements` differ only in the status literal. One `_judgements(conn, task_id, status)` with two one-line wrappers (three files import the names). -17
- `check.py:466-478, 1621-1631, 2185-2191`: the `item_text(link, source_text=..., target_text=..., population=..., place=...)` call built three times. -15
- `check.py:1502-1555`: `toc_select_scope` is a pass-through to `_select_links(only=None)`. Fold. -12
- `check.py:2656-2709` `_pick_critical`: the unmark loop is written twice. -10
- `check.py:2414`, `draft.py:435`, `importing.py:251`: three identical `_norm` helpers. Keep one. Do not touch `graph.py:210` (`item_hash` depends on its regex form). -4
- `check.py:1754, 1767, 1773`, `report.py:472`: DOI normalisation hand-written four times while `acquire._normalize_doi` is the repo's identity key. Make it public and call it. Small change: it also strips `http://` and `dx.doi.org/`. -4
- `check.py:682`, `draft.py:473`, `importing.py:275`, `test_proposals.py:25`: four places build an `EditOpWire` with every field `None`. One `EditOpWire.of(...)` classmethod. -6
- `proposals.py:317-325, 354-362`: `_merge` and `_add_pathway` write out `store.record(..., step=USER_EDIT, ...)` that `edits._record` already wraps. -12
- `proposals.py:221-266`: the box-revision lookup and the if/then/because `fields` comprehension are each written twice. -6
- `edits.py:90-95, 123-129, 471`: the stale-revision refusal built twice, once via the trick `_stale(row, -1)`. -4
- `edits.py:551-555, 605-609`: accept/reject decision values built twice. -3
- `review.py:125-133` and `routers/toc.py:200-207`: the same "latest `toc_report` payload" query. One `latest_report(conn, task_id)` in `review.py`. -8
- `contract/toc.py:488-495` vs `:33-40`: `TocCriteriaIn` equals `TocResultCriteriaOut`. One model. -9
- `contract/toc.py:58, 483, 505-508` + `proposals.py:60-63`: the six-value layer Literal written four times. One `Layer` alias; `edits.LAYERS` derives from it. -8
- `routers/toc.py:149` vs `contract/toc.py:30`: `CheckStatus` defined twice. -1
- `routers/toc.py:993-1001, 1076-1084`: "these link ids belong to this task" query twice. -4
- `routers/toc.py:1164, 1301`: `backends.toc if ... else StubTocBackend()` twice. -1
- `api/toc_start.py:577-587` repeats `walk_context` (`:249-267`); `:315-323` calls `walk_kind` then `walk_context` for the same walk in two connections; `:543-547` repeats the check-context dict from `routers/runs.py`. -18
- `importing.py:160-161` vs `:101-102`: `joined` refs set computed twice. -3
- `store.py:321-334` `one_change` rebuilds the payload layout `record()` builds. -5
- `draft.py:260-270` vs `:413-428`: the pathway-kind-and-label rule twice. -4
- `runtime/option_search.py:683-786`: `dispatch_toc_item_searches` is a near line-for-line copy of `dispatch_option_searches` (`:599-675`). One private `_fan_out(stage, requests, extra_payload)` for both. -45
- `runtime/option_search.py:789-801`: `join_option_searches` is now a wrapper around its renamed copy `join_children`. Add `stage=` to the original. -10
- `runtime/runner.py:1176-1274`: the two ToC barriers repeat the `plan_row` dict and the "failed join → skipped outcome and flag" block. -22
- `runtime/task_agent_toc.py:312-317, 264-269`: the `DEFAULT_PUBLISHED_AFTER` default written twice; `toc_scope_constraints` already applies it. -6
- `runtime/capability_registry.py:193-197`: `importlib.import_module` + `cast` because "the profile module lands in step 1.3". It landed. Use a local import like its two siblings. -3
- `evidence_search/sourcing/search_loop.py:1633-1686`: `_acquire_user_dois` builds `ExecutedCall` twice with six identical fields. -9
- `cost.py:25-53` and `scripts/evals/theory_of_change/harness.py:78, 191`: two price tables and two copies of the formula. The harness should import `cost`. -12 (in the harness)

Frontend:

- `workspace/usePanelWidth.ts:15-46` duplicates dev's `useRail` in `workspace/rail.tsx:52-101` (pointer-capture drag, arrow-key step, clamp 280–640, separatorProps). Build `useRail` on `usePanelWidth`. -30 (in dev's file; touch with care)
- `workspace/PlanDocument.tsx:964-1037`: `TocYearsSection` re-implements `TocEditSection` (`:878-954`): same editing/drafts/error state, same `patchPlan.mutate`. One section component with a field renderer. -35
- Three copies of "blob → `blobUrl` → PDF link or `<img>` thumbnail" (`NewTaskView.tsx:248`, `PlanDocument.tsx:1041`, `TaskAgentPane.tsx:354`). One `UploadPreview`. -20
- Two paperclip file inputs with different SVG paths (`NewTaskView.tsx:262`, `TaskAgentPane.tsx:292`). One `AttachFileButton`. -15
- `views/toc/Documents.tsx:185-231`: `DocumentItem` takes seven fields one by one and all four call sites copy them from a `TocDocument`. Pass `doc` plus overrides. -20
- `views/toc/Documents.tsx:46-97`: `EvidenceBalance` is generic with optional `detail`/`onOpen` and a non-button branch; its one caller passes everything. Its `caption` duplicates `SUPPORT_LABEL` in `tocModel.ts:35`. -12
- `views/toc/TocCanvas.tsx:294-325`: `WholeFitter` and `Focuser` are the same component. -12
- `views/toc/TocCanvas.tsx:447-496`: four label nodes repeat the same props; `DECOR` already exists. -22
- `views/toc/TocCanvas.tsx:165-173` duplicates the `HANDLES` list at `:252`. -5
- `views/toc/TocResult.tsx:150-188`: the "Check the evidence" button is written twice (drafted and failed banners). -12
- `views/toc/TocResult.tsx:68-91`: the `?focus=` block re-implements `select()` and the code lookup in `codeTargets`. -5
- `views/toc/Editing.tsx:60-69`: `isQueued` + `checkWords` are always used together at three sites. One `CheckButton`. -10
- `views/toc/Editing.tsx:71, 270` + `EditForms.tsx:8, 75`: `LAYERS` declared twice (equals `Object.keys(LAYER_LABEL)`); the layer `<select>` rendered twice. -8
- `views/toc/DetailPanel.tsx:90-97, 135-142` and `DetailedInformation.tsx:56-65, 256`: the same citation object built twice in each file. -10
- `views/toc/DetailPanel.tsx:195, 304, 342` vs `Documents.tsx:294-320`: two `opened` states and two `CitationSheet`s for one panel. -8
- `views/toc/Suggestions.tsx:159-186, 115-152`: two identical Accept/Reject pairs; two hover-preview mechanisms. -10
- `views/toc/codeLinks.tsx:11-29` vs `DetailedInformation.tsx:77-95`: two "split text on box or connection codes" splitters. -6
- `workspace/TocTrace.tsx:16-91`: `doneLine` and `nowLine` are two switches over the same step names. One table. -15
- `workspace/TocTrace.tsx:251-261`: `useElapsed` duplicates `RunningCard.tsx:25-37` and `runProgress.elapsedSeconds`. -3
- `workspace/runProgress.ts:174-186` vs `TocTrace.tsx:57-91`: two label vocabularies for the same ToC steps, with different wording ("Picking documents" vs "Reading titles and abstracts"). A copy decision for the owner. -10 if one wording wins
- `workspace/chat/ChatSidePanel.tsx:51-68`: `readClosed`/`writeClosed` repeat `ConversationSidebar.tsx:14-33`'s localStorage pair. -10
- `views/toc/exports.ts:155-164`: anchor-click download written here and in `artefactPresentation.ts:555` and `SourcesView.tsx:515`. -5
- `views/toc/tocModel.ts:280-287, 331`: column-by-layer table written twice. -3
- `api/queries.ts:737-740` vs `:697-700`: the "drafting or checking" polling rule twice. -3
- `views/NewTaskView.tsx:300-325`: `drawYourself` and `submit` build nearly the same payload. -4
- `views/finishAlerts.ts:15-31`: `CheckStatus` hand-copied from `views/toc/types.ts:24`; the switch is a lookup table. -9

### 2.3 Abstractions with one implementation (yagni, about -60; some optional)

- `theory_of_change/backend.py:124-250`: the `TocBackend` Protocol repeats every signature of `OpenAITocBackend` one for one, and its docstrings are stale (`toc_judge_v4`; the prompt is v8). A union of the two real classes would save 120 lines. **Optional.** The repo's other seams (`RankingBackend`, `EmbeddingBackend`) are Protocols, so this breaks the house convention. At minimum fix the docstrings.
- `api/toc_start.py:83-109, 168-223`: `admit_and_mint` + `AdmittedToc` + `TocRefused` have one caller; `links` is never passed; the `not_toc` branch cannot fire. **Optional.** It mirrors `longlist_start.admit_and_mint` on purpose and a branch-site test tracks the pattern. Keep the shape, delete the dead `links` parameter and the `not_toc` branch. -10
- `routers/toc.py:746-755` + 11 `_edit(...)` sites: `_edit` hand-converts `EditRefused` to API errors. `app.py:461` already installs exception handlers; register one for `EditRefused` and call `edits.x()` directly. -13
- `routers/toc.py:1002-1012, 1093-1104, 1251-1261, 1421-1431`: four handlers repeat the same ten-line `start_toc_check(...)` call and `TocCheckOut(...)`. One `_start_check` helper with the three runner dependencies in one `Depends` bundle. -20
- `theory_of_change/edits.py:71-75` + 19 sites: `Actor` wraps one `user_id: str`. Pass the string. -6
- `views/toc/Editing.tsx:135-171` / `TocResult.tsx:191-211`: `CanvasBar` takes `graph` and `editor` yet the caller precomputes `pathways`, `reviewLabel`, `reviewDisabled` from the same graph, and always passes `suggestions=0`, `suggestionsOpen=false`. Derive inside; make props required. -8
- `views/toc/TocCanvas.tsx:344-347`, `DetailPanel.tsx:368, 377`, `tocModel.ts:453`: `= null` defaults and `?` props that the only caller always passes; `tocTitle(fallback?)` never passed. -5
- `ui/radix/portal.ts:6`: `typeof document === "undefined"` guard in a browser-only Vite app. -1
- `views/finishAlerts.ts:65-72`: an extra `GET /toc` per finished ToC task exists only to pick one of four sentences. **Optional**: one sentence. -12

### 2.4 Stdlib or platform does it (about -40)

- `views/toc/Editing.tsx:93-128`: `MoreMenu` is a hand-rolled `<details>` with a document click listener. The Radix Popover already does outside-click and Esc, as `DownloadMenu` shows. Popover first needs `container={portalContainer()}` (see § 4). -8
- `views/toc/EditForms.tsx:42-47, 120-125`: twelve `useState`s that only feed `onSubmit`. Uncontrolled inputs plus `FormData`. Keep `text` controlled (the warning depends on it). -12
- `api/mutations.ts:465-467`: hand-written 32 KB chunked base64 loop. `FileReader.readAsDataURL` and strip the prefix. -2
- `api/mutations.ts:236-254`: the `{...mutation, mutate: wrapper}` around `useStartRun` is one `onMutate: askForFinishAlerts` option, and stops the object changing identity every render. -7
- `check.py:1496, 2616`: `X(**{**obj.__dict__, "field": v})` is `dataclasses.replace(obj, field=v)`. 0, clearer
- `routers/toc.py:387-391`: `_source_type` is a three-entry dict `.get`. -3
- `draft.py`, `report.py`, `check.py`: about eleven function-local imports with no import cycle (the modules are already imported at the top of the same files). Move up. -14
- `search_loop.py:127-131`: four single-use `LINK_*_RESULTS` constants. Inline; keep `LINK_PLACE_SUFFIX` (tests use it). -5
- `views/toc/exports.ts:45-48`: `theoryJson` wraps `JSON.stringify(graph, null, 2)`. Inline. -3
- `views/toc/ReadingGuide.tsx:26-40`: six `verdict === … && line(...)` conditionals; one table. -5

## 3. Checked and kept

- `fixture.ts` (374 lines): the mock API uses it, not only tests.
- `portal.ts`, `blobUrl.ts`, `usePanelWidth` (apart from the `useRail` overlap): each has two or three callers and a stated reason.
- `DetailPanel.tsx` vs `DetailedInformation.tsx`: side panel vs report under the canvas; no overlap.
- `DownloadMenu.tsx` vs `ArtefactDownload.tsx`: the latter is now a 20-line item list over the former.
- Query keys and mutation hooks: every one has a reader or a caller.
- Legacy report fields (`weakest_links`, `whole_programme`, v4-era optionals): the models use `extra="forbid"`, so stored reports need them.
- The pathway `broken` check in the router is not the same as `review.py`'s (the router also flags a gap at position 0 or the end); merging would change behaviour.
- `task_agent_toc.py` and `toc_plan.py` are a profile and a plan model, not copies of the generic loop.
- All 13 `*_prompt.py` modules are imported. One stale `evidence/__pycache__/crossref.cpython-312.pyc` has no source file.

## 4. Out of scope here, for the adversarial review

Bugs and costs the reviews noticed while reading. Not fixed, not verified beyond the quoted lines.

- **Download menu in full screen**: `ui/radix/Popover.tsx` portals to the page body without `container={portalContainer()}`, unlike Tooltip and Sheet. The Download menu sits inside the full-screen `#toc-canvas`, so it is probably invisible there.
- **Copies that already disagree**: `_flag_values` (`check.py:487`) treats only origin `user` as user work, while `_user_written` (`check.py:1016`) treats `user` and `imported`. Pathways or links that merge or choose change on imported rows are not flagged. The canvas and the review model can also disagree on whether a pathway is broken (§ 3).
- **Bedrock steps likely unpriced**: `cost.PRICES` keys are OpenAI ids; the Bedrock routes use `global.openai.gpt-6-luna` (`model_routes.toml:171, 228`). `walk_cost` would report every step as unpriced on that route.
- **Consolidate billed to discover**: `backend.py:358` routes `consolidate` as step `toc_merge`, but its tokens land in `toc_discover`'s component and get discover's price.
- **N+1 in the judge**: `toc_judge` runs a "judged" query inside the per-link loop (`check.py:2192-2199`), up to 80 queries per walk.
- **`_pending_found` cost**: calls the private `review._theory`, which computes every link's verdict, just to label a few links.
- **`_acquire_user_dois`**: acquires from no backends and reports nothing when OpenAlex is not configured.
- **Upload read access**: `core/uploads.py:13-14` says a route checks edit rights before sending a file back; `GET /uploads` and `GET /uploads/{id}` use the read grade (`routers/toc.py:1201, 1221`). Docstring or check is wrong.
- **Silent stale skips**: `edits.reset_layout` (L485) and `edits.keep_evidence` (L645) ignore `store.update`'s stale result but still count the row.
- **finishAlerts gap**: `before === null` is skipped, so a task that starts and finishes between two 15 s polls never alerts.
- **TaskAgentPane hand-off effect** (about L979) has no dependency array; it runs every render, guarded only by a ref.
- **Layout recomputed** several times per canvas render (`layoutToc` in TocCanvas, `imageBounds`, `tocTitle`; `visibleLinkIds` twice); the Escape-key effect re-attaches every render because `editing` is a new object each time.
- **`hasToc` means two things**: "is a ToC task" in `useTabOptions` and "has boxes and a check" in `useChatsEnabled` (`taskResult.ts:24, 42`); the doc at `lifecycle.ts:59` is stale.
- `tests/core/test_embeddings.py:131`: the comment's table counts do not match the assert (52). `tests/helpers.py`: the ToC cleanup list has no `toc_figure`; fine only if it cascades.
- `toc_after_approve` (`task_agent_toc.py:232`) imports the private `search_loop._semantic_filter_parts`.
- `ChatSidePanel.tsx:51` inserted `CLOSED_KEY` between the component's JSDoc and the component, so the doc now describes the constant.

## 5. Suggested order

1. Decide § 1 (the seven frontend and four backend behaviour changes). These are product calls, not code calls.
2. Delete § 2.1 in one commit. Mechanical, no behaviour change, about -110 lines, and it removes the "increment 2/4/7" scaffolding before a reviewer reads it.
3. The shared-helper batch from § 2.2: `snapshot_meta`, `_judgements(status)`, `_ask`, `_link_item_text`, `latest_report`, `Layer`, `EditOpWire.of`, `route_ops`, `_fan_out`, the report numbering closure. About -300 lines and the main drift risk.
4. The frontend batch from § 2.2 and § 2.4: `DocumentItem(doc)`, one citation sheet, `CheckButton`, `FitTo`, label helper, `TocYearsSection` on `TocEditSection`, `UploadPreview`, `AttachFileButton`, the `TocGet` cast. About -250 lines.
5. Leave § 2.3's optional items (the Protocol, `admit_and_mint`) unless the owner wants them.

`make verify` after each step; the function-level tests in `backend/tests/theory_of_change/` cover the edits and proposals paths, and `TocResult.test.tsx` covers the canvas flows.
