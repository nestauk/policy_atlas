# Plan: 054-toc-integration

Deliverables 1–9, decisions C1–C17, ruling T1, findings A1–A10, the schema and every term are
defined in [contract.md](contract.md). This plan cites them, fixes the seams the contract leaves
to the build (S1–S14), routes each task to an executor and sets the verify gates. It adds
nothing to scope.

> **Status:** drafted 2026-10-23 · lead. Plan-stage adversarial review: _pending_. Plan
> approved (before implementation): _pending_. ADR 0042 is drafted after plan approval and
> before Phase 1, as task 044 did.

Executor marks follow AGENTS.md § Agent-side model routing. **Owner ruling 2026-09-04 (038)
stands:** judgment-bearing phases go to `deep-reasoner`, not `codex`; the family flip happens at
step 7 when Codex reviews each deliverable's diff. Prompt-bearing work is `lead` only.
Taste-bearing frontend surfaces (the canvas, the key, the cards, the panel) get a `lead` polish
pass after the delegate lands the structure (owner ruling 2026-09-05). Every `lead` mark carries
its reason.

**Verify gates.** Full `make verify` at Phase 0 (build-open baseline), at the schema phase (1.2),
at the exit of every deliverable (each one is a PR into `feat/theory-of-change`, C15), and at
Phase 10 (step-6 exit). Sub-phases inside a deliverable commit on `make verify-fast` **plus
`make prompt-guard` and `make drift-check`** wherever a prompt or a contract model changed, plus
`make frontend-verify` where the frontend changed and `pnpm e2e` where a route changed. One green
commit per sub-phase. Memory rule: stage by explicit path, never `git add -A`; check `git log`
before reporting, because another session may share this checkout.

## Seams fixed here (lead design)

S1. **Registry entry** (C3, C12). `THEORY_OF_CHANGE = "theory_of_change"`; `AnyPlan = TaskPlan |
ScopingPlan | TocPlan`; `CAPABILITIES[THEORY_OF_CHANGE] = CapabilitySpec(plan_model=TocPlan,
compose=compose_toc, lattice={}, load_task_agent=_toc_task_agent)`; `expect_toc_plan` beside the
other two. `test_capability_registry.py:105` widens to three keys; the AST guard (:205) stays and
covers the new module.

S2. **`TocPlan`** (`runtime/toc_plan.py`). Fields: `title`, `question`, `entry_point`
(`outcome_first · intervention_first · existing_theory`), `intended_change`, `target_population`,
`intervention | None`, `dosage | None`, `existing_theory_text | None`, `upload_id | None`,
`where | None`, `time_horizon | None`, `context | None`, `evidence_restriction` (the OS shape,
reused), `from_option | None` (source task, option, pinned run), `steering_mode =
"unattended"` (C12: never asked; the runner reads the field on every plan), `steer_point_defaults
= {}`, `source_turn_index | None`. Readiness rules per entry point as the spec § Plan slots states.

S3. **Walk kinds, one purpose** (C3). Every ToC intent record carries `purpose = 'toc'` and
`context.toc_walk ∈ {draft, check, recheck}`; recheck adds `context.items` (a list of
`{kind, id}`). `compose_toc(plan, purpose, context)`:
- `toc` + `draft`: `inherit` (only when `from_option` is set) → `toc_draft` (or `toc_import` when
  the entry point is `existing_theory`).
- `toc` + `check`: `toc_item_searches` → `screen_abstract` → `classify` → `appraise` →
  `toc_judge` → `toc_discover` → `toc_consolidate` → `toc_summarise`.
- `toc` + `recheck`: `toc_item_searches` → `screen_abstract` → `classify` → `appraise` →
  `toc_judge` (only the named items).
- `targeted` + `acquire_only` (the item search child): `acquire` → `toc_web` (`toc_web` only when
  the route's web search is enabled, C7).
`toc_item_searches` is a runner-level stage like the OS dispatch: it dispatches one child per
item (S5) and joins before `screen_abstract`, in a `purpose == 'toc'` branch beside the existing
`LONGLIST_PURPOSE` branch at `runner.py:1078-1140`. Each new step gets a `COMPONENT_REGISTRY`
entry (`run_spec.py:13`), a `TOC_STEPS` tuple in `task_plan._validate_registry`, and a harness
node.

S4. **Follow-on walks** (C3, C10). The draft walk's outcome carries `follow_on = "toc_check"`; the
check walk's outcome carries `follow_on = "toc_recheck"` with the item list when any item's
current hash has no judgement from that walk (the derived follow-up of C10). The recheck never
sets a follow-on, so there is no loop. `_dispatch_run` (`api/routers/runs.py:153`) gains one
branch that mints the next ToC intent record and runs it inline, on the `_run_follow_on_longlist`
pattern (:170-209). "Check again" is `POST /toc/recheck` with the same minting.

S5. **Child search move** (C2, A6). New `runtime/child_search.py` holds `ChildSearchRequest`,
`run_child_search`, `_run_child`, `_end_child`, `_forget`, `child_walks`, `dispatched_children(…,
stage)`, `join_children`, `_ended`, `_interrupt_children`, `abandon_children`,
`end_if_abandoned`, `JoinOutcome`, and the `_futures` / `_abandoned` / `_handles_lock`
registry. `option_search.py` **re-exports the same objects** (`from …child_search import _futures,
_handles_lock, _abandoned, _ended, _end_child, …`), keeps `run_option_search` as a thin wrapper
whose module global `dispatch_option_searches` still calls, and keeps every OS-specific function.
The child resolves its plan through the registry by the task's capability (replacing the direct
`unattended_plan` → `ScopingPlan` use only inside `_run_child`; `unattended_plan` stays for its
other callers). Proof: every test listed in the inventory (`test_option_search.py`,
`test_acquire_only_walk.py`, `test_compose_by_purpose.py`, `test_longlist_routes.py`,
`test_longlist_start.py`, `test_longlist_turns.py`, `test_scoping_existence.py`) passes with no
edit.

S6. **OS-only branches that must learn ToC** (inventory § 4, 6, 7): `_finish_run`'s abandon branch
(`runner.py:5536`) also for `toc`; `_latest_run_row`'s parentless, non-targeted filter
(`_common.py:111`) also for ToC; `persist_approved_plan` (`agent.py:959`) writes `purpose='toc'`
and `context.toc_walk='draft'` for a `TocPlan`; `get_plan` and `patch_plan`
(`task_agent.py:1236, 1534`) get a ToC branch; `plan_slot` and `PlanOut` / `TaskAgentTurnOut`
gain a `toc` slot (additive); `NewTaskView` `FORM_COPY` gains a ToC entry; `ArtefactView` and
`taskResult.ts` gain `isToc`. A grep test lists every `== OPTIONS_SCOPING` / `=== "options_scoping"`
site and fails if a new one appears without a reviewed ToC decision (a one-line allow-list).

S7. **The Task Agent thread stays open** (inventory § 4). `_finish_run` closes the Task Agent
conversation when a parentless walk succeeds (`runner.py:5593`). For ToC that would end the
thread where change requests and the plan-change choice (C11) happen. ToC walks skip the close.
The thread then carries: plan turns, run progress, change requests (S9), the C11 choice.

S8. **Graph module** (`theory_of_change/graph.py`). Pydantic read and write models for the eight
tables, the validator (E1 checks, the *broken* pathway rule), `item_text(item) -> str` and
`item_hash(text) -> str` (sha256 of the normalised text), the assumption type from layers, and
the compare-and-apply writer `apply_changes(conn, task_id, changes, observed_revisions) ->
ApplyReport(applied, skipped)` used by consolidate, Undo and Keep mine (C9, C10). Edits use
`edit_row(conn, …, expected_revision)` raising `StaleRevision` → 409 `toc_stale_revision`.

S9. **Change requests through the Task Agent** (spec § Product surface). After the draft, a Task
Agent turn on a ToC task may return `graph_edits` (a closed list: add, edit, delete, connect,
mark load-bearing) in its wire. The route applies them through `edit_row` with the revisions the
turn read, as the user's edits (origin `user`, `user_edited = true`). A plan-slot change in a
turn triggers the C11 choice instead. One prompt (`task_agent_toc_v1`) covers both jobs.

S10. **Grade** (C4). `theory_of_change/evidence/grade.py`: `grade(judgements: list[Judgement],
current_hash: str) -> GradeResult(grade, flags, counts, status)`; constants for the score
thresholds (4, 3) and the web cap; `rule_text() -> list[str]` for the key. Table test covers
every rule row and boundary.

S11. **Web call** (C7). `core/openai_client.py` gains `resolve_web_search_client()` (reads
`route().web_search`) and `traced_web_search(client, langfuse, *, model, prompt, …) ->
WebSearchResult(text, citations[url, title], usage)`, wrapped in `traced_call`, reserving the
`CallBudget`; `core/usage.py` gains `token_usage_from_responses` for `input_tokens` /
`output_tokens`. `evidence_search/sourcing/web_pages.py`: `freeze_pages(conn, *, task_id,
run_id, citations, fetcher) -> counts`, using `LiveDocumentFetcher`, trafilatura, the 200,000
character cap, URL de-duplication inside the task, and one `search.executed` event per web call.

S12. **Uploads storage** (C8). `theory_of_change/importer/storage.py`: `UploadStore` protocol
(`put`, `get`, `delete`), `S3UploadStore` (boto3, already a dependency since task 053) and
`LocalUploadStore` (a directory, for development and tests); chosen by
`POLICY_ATLAS_TOC_UPLOAD_BUCKET` being set.

S13. **Frontend structure.** `views/toc/`: `TocResult.tsx` (header, Test this first, view
switch), `TocCanvas.tsx` (React Flow; deterministic column layout by layer, rows by order;
bands as React Flow group nodes), `TocKey.tsx` (rule text from the API), `AssumptionBand.tsx`
(cards under their link, numbered markers, hover link), `DetailPanel.tsx`, `PathwayList.tsx`
(kept, then "Considered and set aside", Restore), `OriginalView.tsx`, `StressTestPane.tsx`,
`exports.ts` (PNG and SVG with `html-to-image@1.11.11`; CSV, JSON, draw.io and PowerPoint
downloads from the API). Hooks in `api/queries.ts` (`useToc`, `useTocEvidence`) and
`api/mutations.ts` (`useTocEdit`, `useTocRecheck`, `useTocUndo`, `useTocRestore`, `useTocKeepMine`,
`useTocUpload`). Polling while a ToC walk runs uses the existing run SSE stream.

S14. **API shape** (`api/routers/toc.py`, prefix `/api/v1/tasks/{task_id}/toc`, no router-level
auth so reads can use the public leg, C17). Reads (public leg): `GET /` (graph with grades,
flags, statuses, revisions, rule text), `GET /items/{kind}/{id}/evidence`, `GET /pathways`,
`GET /summary`, `GET /export/{csv|json|drawio|pptx}`. Writes and private reads
(`get_current_user`, write grade): `PATCH /boxes/{id}`, `/links/{id}`, `/assumptions/{id}`,
`/pathways/{id}`, `/band-items/{id}`; `POST` to add each; `DELETE` each; `POST /recheck`, `POST
/consolidations/{event_id}/undo`, `POST /pathways/{id}/restore`, `POST /{kind}/{id}/keep-mine`,
`POST /uploads`, `GET /uploads/{id}` (authenticated only, C8 headers). Every write carries
`expected_revision`. Each new public GET goes into `_CONDITIONALLY_PUBLIC_GETS` in
`test_api_conformance.py`; upload GETs stay out.

## Phase 0 — Build-open baseline — `lead` (inline)

PR #84 merged to `dev` (stop condition otherwise). Create `feat/theory-of-change` from `dev`;
rebase the task 054 docs onto it. Full `make verify`. Never build on a red base.

## Deliverable 1 — Shell and draft

1.1 **Prompts first — `lead`.** Reason: prompt-bearing, lead-only. `task_agent_toc_prompt.py`
(`task_agent_toc_v1`: plan slots, entry-point inference, dosage question, the C11 choice
sentence, the S9 `graph_edits` wire) and `theory_of_change/draft/draft_prompt.py`
(`toc_draft_v1`: Magenta Book layers, up to 6 success and 3 failure pathways, mechanisms,
assumptions on links, result criteria and indicators, load-bearing assumption, origin
`drafted`). Stub backends for both. Refine-replay per `prompting.md` on three topics. Re-pin.
Gate: `verify-fast` + `prompt-guard`. Commit.

1.2 **Schema and registry — `deep-reasoner`.** The revision exactly as contract § Schema (from
head `f1b6d3a8c2e5`, pattern `b5e1d7a4c026` and `c7e2a9f4b1d8`), mirrored in `core/schema.py`;
`tests/core/test_migration_054_slice.py` (round trip, downgrade refusal); the six
`len(metadata.tables)` asserts move from 43 to 51; S1; S2; `compose_toc` (S3, draft branch only
yet); S6's backend sites; S7; the C15 server setting (`api/settings.py`) with the create guard;
`scripts/ops_remove_toc_tasks.py` on the `ops_remove_scoping_tasks.py` pattern, deleting upload
objects first (C8). Done when the round trip, registry, settings-guard and S6 grep tests pass.
Gate: **full `make verify`**. Commit.

1.3 **Task Agent profile and draft walk — `deep-reasoner`.** `runtime/task_agent_toc.py`
(profile per inventory § 6); `theory_of_change/graph.py` (S8, validator, item text, hash);
`theory_of_change/draft/` (the `toc_draft` component writing the tables); harness nodes; the
`toc` slot in the plan contract; `make openapi-sync`. Tests: plan validation per entry point; an
ES or OS payload rejected on a ToC task and the reverse; the draft writes a graph that passes the
validator (stub); the thread stays open after the draft walk (S7). Gate: `verify-fast` +
`prompt-guard` + `drift-check`. Commit.

1.4 **Read API and canvas — `fast-worker` for structure, then `lead` polish.** Reason for the
lead pass: the canvas, the bands and the key are taste-bearing. `GET /toc` (S14) with the public
leg and the conformance entry; `@xyflow/react` added through the dependency gate; `views/toc/`
read-only: `TocResult`, `TocCanvas`, `AssumptionBand`, `TocKey`, `PathwayList`; `capabilities.ts`
flag; `NewTaskView` copy. Vitest from fixtures. Gate: `verify-fast` + `frontend-verify` +
`pnpm e2e`. Commit.

1.5 **E1 and the E6 harness — `fast-worker` for harness code, `lead` for the rubric.** Reason:
the E6 judge rubric is prompt-bearing. `scripts/evals/toc/` with `e1_structure.py` (the
validator over drafts from ~30 descriptions in `datasets/descriptions.jsonl`) and
`e6_rebuild.py` (soft node matching, edge F1 with direction, impact and outcome recall, Mayne
rubric judge, 5-run stability). The lead picks the first 20 published theories (Youth
Endowment Fund, GOV.UK, Campbell; 2025–26 first), writes their labels as JSON with source URLs
and licences, and runs both once. Numbers into `verification.md`.

Exit: **full `make verify`**; live check (1); PR into `feat/theory-of-change`; step-7 review stack.

## Deliverable 2 — Evidence check

2.1 **Prompts — `lead`.** `toc_item_judge_v1` (stance, quote, condition, case study and indicator
for boxes; untrusted-text fencing), `toc_summary_v1`, and the item-search guidance (support and
challenge queries). Re-pin.

2.2 **Child search move — `deep-reasoner`.** S5 exactly, before any ToC use. Done when every OS
test listed in S5 passes **unedited** and full `make verify` is green. Gate: **full `make
verify`**. Commit. (Own review pass before 2.3, like task 044's rename.)

2.3 **Check walk — `deep-reasoner`.** S3 check branch; the runner's `toc` dispatch and join
branch; `toc_item_searches`; `toc_judge` (C5: rerank top 8, the quote matcher, drop and count);
`theory_of_change/evidence/grade.py` (S10); `toc_summarise`; S4 follow-on from draft to check;
the 80-item cap rule. Tests per contract acceptance 2. Gate: **full `make verify`** (runner and
schema-adjacent). Commit.

2.4 **Detail panel and Sources — `fast-worker`, then `lead` polish.** Evidence read route;
`DetailPanel` with the three groups, case studies, indicators, quality chips; grade colours and
line styles on links and box bars; the header counts; Sources tab unchanged except the source
type split. Gate: `verify-fast` + `frontend-verify`. Commit.

2.5 **E2 and E2b — `fast-worker` for harnesses, `lead` for the label mapping and the Consensus
run.** Reason: the label mapping decides what the numbers mean. Datasets with licences recorded;
the ablation arm; E2b on 50 fixed claims, Consensus calls only after the owner approves the run
(about $2.50), results cached in `scripts/evals/toc/results/` (aggregates only committed). Check
the E2 stop condition before Deliverable 3.

Exit: **full `make verify`**; live check (2); PR; review stack.

## Deliverable 3 — Discover and consolidate

3.1 **Prompts — `lead`.** `toc_discover_v1`, `toc_consolidate_v1` (two stages; distinct and
relevant aggregate, promising and evidence choose; one-line reasons; flag every change to user
work). Re-pin.

3.2 **Components — `deep-reasoner`.** `toc_discover` (insert-only, FK failures dropped and
counted); `toc_consolidate` through `apply_changes` (S8) with the before-state event; Undo,
Restore and Keep mine routes (C9); the limits check. Tests per contract acceptance 3. Gate:
**full `make verify`**. Commit.

3.3 **Screens — `fast-worker`, then `lead` polish.** The *changed by Policy Atlas* mark, the
side-by-side panel with Keep mine, "Considered and set aside" with Restore, the thread's summary
line with Undo. Gate: `verify-fast` + `frontend-verify`. Commit.

3.4 **E6 rerun — `lead`** on the consolidated theories; numbers into `verification.md`.

Exit: **full `make verify`**; live check (3); PR; review stack.

## Deliverable 4 — Editing during the check

4.1 **Edit routes and revisions — `deep-reasoner`.** S14 write routes through `edit_row`; one
event per edit; S4's recheck follow-on and `POST /recheck`; S9 `graph_edits` applied from the
Task Agent; the C11 Redraft and Keep choice (Redraft = a new draft walk; user elements carried as
flagged where they still fit). Race tests per contract acceptance 4, written with explicit
barriers, not sleeps. Gate: **full `make verify`**. Commit.

4.2 **Canvas editing — `fast-worker`, then `lead` polish.** Add, edit, delete, connect, move
assumptions, mark load-bearing; *out of date* and "Check again"; 409 handling that reloads and
says what changed. Gate: `verify-fast` + `frontend-verify` + `pnpm e2e`. Commit.

Exit: **full `make verify`**; live check (4); PR; review stack.

## Deliverable 5 — Web search

5.1 **Route config — `deep-reasoner`.** `WebSearchRoute` and its parser (inventory § 8): the
allowed-address tuple, `api_key_env` in `API_KEY_ENVS`, every route declaring the table, the
three route tables in `model_routes.toml`, fixture TOMLs in `test_model_routes.py` updated, a test
that non-web calls keep `openai_base_url`.

5.2 **Call, pages, step — `deep-reasoner`.** S11; the `toc_web` child step; the "web not
searched" coverage line; the grade's web cap is already in S10 and is tested here end to end.
One manual smoke call per route, recorded: `openai-direct`, and `bedrock-local` against Mantle in
us-east-1 (stop condition if the key or identity is refused).

5.3 **ADR 0042 web section** already written at design time; this phase adds the measured cost
per check. Gate: **full `make verify`**. Commit.

Exit: live check (5); PR; review stack with the security lane on egress.

## Deliverable 6 — Stress test and discuss

6.1 **Prompt — `lead`.** `toc_stress_v1` (four angles, one at a time, tied to an element, two to
four sentences, no invented evidence). Re-pin.

6.2 **Chat kind and discuss context — `deep-reasoner`.** `stress_test` conversation kind wired
through the chat backend; the four questions stored on the conversation; discuss gets the graph
and evidence as context through `answer_core`; neither chat writes the graph (test).

6.3 **Pane — `fast-worker`, then `lead` polish.** `StressTestPane`, canvas highlight of the tied
element. Gate: `verify-fast` + `prompt-guard` + `frontend-verify`. Commit.

Exit: **full `make verify`**; live check (6); PR; review stack.

## Deliverable 7 — Bring your own theory

7.1 **Prompt — `lead`.** `toc_import_v1` (keep the user's words; map to layers; label additions
`imported` vs `drafted`; say what could not be read). Re-pin.

7.2 **Storage and route — `deep-reasoner`.** S12; `POST /uploads` (base64, 10 MB, type and magic
bytes, PDF to at most 10 page images with pymupdf); `GET /uploads/{id}` authenticated only with
the C8 headers; audit event and trace span; the `toc_import` component through
`chat.completions.parse` with image parts. Tests per contract acceptance 7, including the access
matrix.

7.3 **Infrastructure — `deep-reasoner`, `lead` review.** Reason for the review: production
config. The bucket (`BLOCK_ALL`, `S3_MANAGED` encryption, `enforce_ssl`, `RETAIN`), the task-role
grant (read, write, delete on the bucket only), `POLICY_ATLAS_TOC_UPLOAD_BUCKET` and
`POLICY_ATLAS_THEORY_OF_CHANGE=0` in the container environment; `infra/tests/unit/
test_service_wiring.py` `API_ENVIRONMENT_NAMES` updated; `test_synth.py` asserts the bucket
properties.

7.4 **Screens — `fast-worker`, then `lead` polish.** Upload in the Task Agent pane; "Your
original" beside the canvas. Gate: **full `make verify`** + infra tests. Commit.

Exit: live check (7); PR; review stack with the security lane on uploads.

## Deliverable 8 — Export

8.1 **Backend exports — `fast-worker`.** CSV, JSON, draw.io XML (standard library), PowerPoint
(`python-pptx` through the dependency gate; connectors attached to boxes; arrowheads by the
`a:tailEnd` XML addition). Tests per contract acceptance 8.

8.2 **Frontend exports — `fast-worker`.** PNG and SVG with `html-to-image` pinned to 1.11.11
(dependency gate); download buttons; a binary-download helper beside `triggerTextDownload`.

8.3 **Manual import checks — `lead`.** Open each file in PowerPoint, diagrams.net and a Miro
import, and the PowerPoint file in Google Slides; record results and screenshots; apply A9.
Gate: `verify-fast` + `frontend-verify`. Commit.

Exit: **full `make verify`**; PR; review stack.

## Deliverable 9 — Design from an option

9.1 **Create path — `deep-reasoner`.** C13: `from_option` on `TaskCreate` with its validators and
error codes; `_write_task_links` widened for ToC targets only (and the latest-walk check reading
the parentless walk for an OS source); `source_option_id` written; `TaskLinkOut.source_option_id`;
the C14 option direction in `runtime/inherit.py` (membership rows to the same snapshots,
labels through `labels_for_snapshots`); slot seeding in the ToC profile's `load_inputs`; the
newer-run flag. Tests per contract acceptance 9.

9.2 **Option page — `fast-worker`, then `lead` polish.** "Design a theory of change" between
`OptionCard.tsx:524` and `:525`, hidden for non-writers; the back-list of ToC tasks from this
option; `useCreateTask` sends `from_option`. Gate: `verify-fast` + `frontend-verify` + `pnpm
e2e`. Commit.

Exit: **full `make verify`**; live check (9); PR; review stack.

## Phase 10 — Close the build — `lead`

Spec changes 1–5 applied with quotes and logged; `docs/deferred.md` delta (rubric 19);
`verification.md` complete; ADR 0042 evidence and sign-off; the feature branch's merge request
to `dev` raised only on the owner's word (C15).

## Out-of-plan reminders

- The Consensus API bills every call: no E2b run without the owner's approval of that run.
- The local Bedrock key lasts at most 12 hours: get a fresh one before the Mantle smoke call.
- Two checkouts share the test database and Playwright port 5199: run the full gate serially.
- Never open a second PR for task 053; PR #84 is the only one.
