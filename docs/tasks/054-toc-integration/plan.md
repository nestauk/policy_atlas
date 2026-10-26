# Plan: 054-toc-integration

Deliverables 1–9, decisions C1–C17, ruling T1, findings A1–A10, the schema and every term are
defined in [contract.md](contract.md). This plan cites them, fixes the seams the contract leaves
to the build (S1–S14), routes each task to an executor and sets the verify gates. It adds
nothing to scope.

> **Status:** drafted 2026-10-23 · lead. Plan-stage adversarial review ran the same day in two
> read-only lanes (Codex; `deep-reasoner` on what Codex left out): 26 findings, all folded
> (§ Plan-review folds). Two folds amend the contract (X7, R1) and are flagged for the owner. Plan
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
**Steering floor (X6).** With an empty lattice and `unattended`, nothing pauses, but the generic
floor triggers of the reused spine steps (`FLOOR_BOUNDARY_FOR_COMPONENT`, `runner.py:2167-2215`)
still flow to the end-of-run collation (`runner.py:1874-1879`). ToC keeps that behaviour: the
flags are recorded in History like any unattended walk's. Tests: a ToC walk never pauses; a fired
floor trigger is recorded.

S3. **Walk kinds and chains** (C3; X1, R1, R10). Every ToC intent record carries
`purpose = 'toc'` and `context.toc_walk ∈ {draft, check, recheck}`; recheck adds
`context.items` (a list of `{kind, id}`). `compose_toc(plan, purpose, context)`:
- `toc` + `draft`: `inherit` (only when `from_option` is set) → `toc_draft` (or `toc_import` for
  `existing_theory`).
- `toc` + `check`: `screen_abstract` → `classify` → `appraise` → `toc_discover` → `toc_merge`
  → `toc_judge` → `toc_choose` → `toc_summarise` (W16). **Discover and merge run before judge**
  (R1, W16), so one judge pass covers the merged drafted and discovered links against the same
  pool, with no new search (C6), and choose can use the grades.
- `toc` + `recheck` (user-started only, W17): `toc_same_meaning` → `toc_judge` on the documents
  already judged for the named links, with no search; *Search for more* starts a named-link
  check walk with item searches.
- `targeted` + `acquire_only` (the item search child): `acquire` → `toc_web` (`toc_web` only
  when the route's web search is enabled, C7).
**Item searches are not a chain step** (X1). As for the OS longlist, the runner dispatches the
children in a `purpose == 'toc'` branch beside `LONGLIST_PURPOSE` (`runner.py:1078-1140`):
dispatch before the first chain step of a check or recheck walk, join before `screen_abstract`,
and emit the stage `toc_item_searches` as an event only. The new chain steps (`toc_draft`,
`toc_import`, `toc_discover`, `toc_judge`, `toc_consolidate`, `toc_summarise`, `toc_web`) each get
a `COMPONENT_REGISTRY` entry (`run_spec.py:13`), a `TOC_STEPS` tuple in
`task_plan._validate_registry`, and a harness node, with `build_graph`'s edge map built from the
step dictionaries instead of more literals.
**Directives (R10).** Item search: the item text as intent; search guidance asking for support
and for challenge (lead-written text, 2.1; for a box also case studies and measures); a record
cap of 🟡 20 per item; the plan's evidence restriction as filters; no ingest. Screen: the theory
(intervention, intended change, population) as the screening intent, with the place carried as
the user's place and never a criterion, as in the OS longlist (task 045 D20). Each walk screens
only the documents its own children acquired plus inherited ones not yet screened in the task;
a document already screened in the task keeps its result. The deep-reasoner confirms in 2.3 how
`screen_sources` selects documents per scope and makes this hold.

S4. **Follow-on driver and dispatch** (C3, C10; X2, R2, R7). A ToC sequence driver
`run_toc_sequence(engine, *, task_id, first_outcome)` in `api/toc_start.py` consumes each inline
walk's returned outcome until `follow_on` is `None`, with the transition map `draft → check` only (W17 removed the automatic re-check hop), a hard
maximum of one hop, and a duplicate guard (`active_parentless_walk` refusal is logged, not
raised). `_dispatch_run` (`runs.py:125-162`) calls it for ToC outcomes. **Every minted walk
validates through the registry**: `_dispatch_run` and the follow-on use
`validate_plan(capability, …)` and force `steering_mode = "unattended"` by capability, replacing
the `unattended_plan` → `ScopingPlan` call for any capability other than OS. A ToC
`admit_and_mint(engine, task_id, *, toc_walk, items=None)` mints the `toc` intent record and the
walk on the `longlist_start.admit_and_mint` pattern (`:113-224`), without its OS reads. Every ToC
launch path (approve then Start through `POST /runs`, the follow-on, `POST /toc/recheck`,
Redraft) goes through `_dispatch_run` and so through the driver. **Restart (R7):** "Check again"
on a task whose latest check walk did not succeed mints a full `check`, not a `recheck`, so an
interrupted check or a crash between draft and check always has a way forward. Tests: a minted
ToC walk dispatches through `_dispatch_run`; the driver stops after two hops; an interrupted
check restarts in full.

S5. **Child search, kept in `option_search.py`** (C2; X7, R3). Simpler than a new module: the
neutral entry point is added **inside** `runtime/option_search.py`, so every private name that
callers and tests import or patch (`_futures`, `_handles_lock`, `_abandoned`, `_ended`,
`_end_child`, `run_option_search`, the lazy `runner.run_plan` lookup) keeps its identity and its
patch site. Changes: `ChildSearchRequest(intent, context, plan_id, stage, pool)` and
`run_child_search(engine, *, task_id, request, parent_capability_run_id, backends, user_id)`,
which `run_option_search` now calls with the option's values; `dispatched_children(…, stage)` and
`join_children(…, stage, timeout)` parameterised by stage; `_run_child` resolving its plan
through the registry by the task's capability. **Pool and timeout (R3):** ToC children run on
their own pool, `walk_pool.toc_item_pool()` at 🟡 width 8, so an OS longlist's option searches
never queue behind them; the join timeout is `max(1800, ceil(n / width) × 300)` seconds.
Compatibility criterion (replaces "no edit"): the seven OS test files pass unedited, and a new
test runs an OS longlist's option searches beside a ToC check and asserts both join. This
amends contract C2's "moves into a new `runtime/child_search.py`"; the decision's intent (one
capability-neutral interface, no second pool, join or abandon code path for OS, OS behaviour
unchanged) holds. Flagged at the plan gate.

S6. **OS-only branches that must learn ToC** (inventory § 4, 6, 7): `_finish_run`'s abandon branch
(`runner.py:5536`) also for `toc`; `_latest_run_row`'s parentless, non-targeted filter
(`_common.py:111`) also for ToC; `persist_approved_plan` (`agent.py:959`) writes `purpose='toc'`
and `context.toc_walk='draft'` for a `TocPlan`; `get_plan` and `patch_plan`
(`task_agent.py:1236, 1534`) get a ToC branch; `plan_slot` and `PlanOut` / `TaskAgentTurnOut`
gain a `toc` slot (additive); `NewTaskView` `FORM_COPY` gains a ToC entry; `ArtefactView` and
`taskResult.ts` gain `isToc`. A grep test lists every `== OPTIONS_SCOPING` / `=== "options_scoping"`
site and fails if a new one appears without a reviewed ToC decision (a one-line allow-list).

S7. **The Task Agent thread stays open, and admits turns during a check** (X3). `_finish_run`
closes the Task Agent conversation when a parentless walk succeeds (`runner.py:5593`); ToC walks
skip the close. `_phase_one_turn` refuses every turn while a parentless walk is active
(`task_agent.py:541-557`). For a ToC task whose active walk is a `check` or `recheck`, the turn
is admitted: it may answer a question or carry graph edits (S9), applied through `edit_row` with
the revisions the turn read; it may not approve or change the plan, and a turn that asks to
returns "after the evidence check finishes". A running `draft` walk keeps today's refusal: there
is no graph to edit yet.

S8. **Graph module** (`theory_of_change/graph.py`). Pydantic read and write models for the eight
tables, the validator (E1 checks, the *broken* pathway rule), `item_text(item) -> str` and
`item_hash(text) -> str` (sha256 of the normalised text), the assumption type from layers, and
the compare-and-apply writer `apply_changes(conn, task_id, changes, observed_revisions) ->
ApplyReport(applied, skipped)` used by consolidate, Undo and Keep mine (C9, C10). Edits use
`edit_row(conn, …, expected_revision)` raising `StaleRevision` → 409 `toc_stale_revision`.

S9. **Change requests through the Task Agent** (spec § Product surface; R11). From
Deliverable 4, a Task Agent turn on a ToC task may return `graph_edits` (a closed list: add,
edit, delete, connect, mark load-bearing). The route applies them through `edit_row`, as the
user's edits (origin `user`, `user_edited = true`); a stale revision returns the S8 conflict to
the thread in words. A plan-slot change triggers the C11 choice instead. `task_agent_toc_v1`
(Deliverable 1) has no `graph_edits` and says edits are made on the canvas; `task_agent_toc_v2`
(4.1) adds them, so the Task Agent never claims a change it cannot make.

S10. **Grade** (C4). `theory_of_change/evidence/grade.py`: `grade(judgements: list[Judgement],
current_hash: str) -> GradeResult(grade, flags, counts, status)`; constants for the score
thresholds (4, 3) and the web cap; `rule_text() -> list[str]` for the key. Table test covers
every rule row and boundary.

S11. **Web call** (C7; R4, R17, R18). `core/openai_client.py` gains
`resolve_web_search_client()` (reads `route().web_search`) and `traced_web_search(client,
langfuse, *, model, prompt, …) -> WebSearchResult(text, citations[url, title], usage,
tool_calls)`, wrapped in `traced_call`, reserving the `CallBudget`, and recording the number of
hosted web-search tool calls in the span (the tool is billed per call, not by tokens).
`core/usage.py` gains `token_usage_from_responses` for `input_tokens` / `output_tokens`.
`evidence_search/sourcing/web_pages.py`: `freeze_pages(conn, *, task_id, run_id, citations,
fetcher) -> counts`, using `LiveDocumentFetcher`, trafilatura, the 200,000-character cap, URL
de-duplication inside the task, one chunk per page (as acquire writes one chunk per abstract),
and one `search.executed` event per web call. **Key and address (R4).** One key per route, as C7
states. The Mantle base path is checked with one call before 5.1 fixes the allowed address
(the GPT-5.6 Sol model card gives `/openai/v1`; another AWS page gives `/v1`). A short-term
Bedrock key works only in the region it was made in, so a developer on `bedrock-local` with a
London short-term key gets "web not searched", honestly, and no crash; deployed environments use
the long-term key from the app secret, and 5.2's smoke call proves it works in us-east-1 (stop
condition if not). The README and `.env.example` gain the `web_search` table for overlay route
files.

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

S14. **API shape** (C17; X4, X5, R5, R6, R8, R9, R19). `api/routers/toc.py`, prefix
`/api/v1/tasks/{task_id}/toc`, no router-level auth so reads can use the public leg.
- **Public reads:** `GET ""` (the graph with grades, flags, statuses, revisions and rule text;
  this body is also the JSON export), `GET /boxes/{box_id}/evidence`,
  `GET /links/{link_id}/evidence`, `GET /assumptions/{assumption_id}/evidence`,
  `GET /pathways`, `GET /summary`. No enum path segments, so the conformance sweep's UUID fill
  gets a 404, not a 422. On a public task that is not a ToC task each returns 404
  `toc_not_found`, so all go into `_CONDITIONALLY_PUBLIC_GETS`, none into the structural set.
- **Authenticated reads:** `GET /export/csv`, `GET /export/drawio`, `GET /export/pptx` (server
  work stays off the anonymous leg, C17 lists no exports), `GET /uploads/{upload_id}` (C8
  headers).
- **Writes** (`get_current_user`, write grade, each carrying `expected_revision`): `POST` and
  `PATCH` for boxes, links, assumptions, pathways and band items; `DELETE` for each;
  `POST /recheck`; `POST /consolidations/{event_id}/undo`; `POST /pathways/{id}/restore`;
  `POST /boxes/{id}/keep-mine` (and for links, assumptions, pathways); `POST /uploads`.
- **CORS (X4):** `DELETE` joins `allow_methods` in `api/app.py:136`, a public-interface change
  recorded in ADR 0042; a preflight test covers a ToC delete route.
- **Registration (X5):** the public and authenticated routers are imported and included in
  `api/app.py` (public before authenticated, as `tasks.py` does), with a route-table test that
  every ToC path is mounted and appears in the OpenAPI document.
- **Back-list (R9):** `GET /api/v1/tasks/{task_id}/options/{option_id}/theories` (authenticated,
  like the option page), listing ToC tasks whose link names this option and that the caller can
  read.
- **Access matrix (R8):** one parametrised test from 1.4, extended by each deliverable, runs
  anonymous, same-organisation, owner and cross-organisation callers against every ToC route.

## Phase 0 — Build-open baseline — `lead` (inline)

PR #84 merged to `dev` (stop condition otherwise). Create `feat/theory-of-change` from `dev`;
rebase the task 054 docs onto it. Full `make verify`. Never build on a red base.

Every `lead` mark below carries its reason. "Lead polish" always means: the delegate lands
structure and tests; the lead then adjusts layout, spacing, copy and visual weight, because those
surfaces are taste-bearing (owner ruling 2026-09-05). Every live check is `lead`: it is the
evidence the owner reads.

## Deliverable 1 — Shell and draft

1.1 **Prompts — `lead`** (prompt-bearing). `task_agent_toc_v1` (plan slots, entry-point
inference, dosage question, the C11 choice sentence; no `graph_edits`, S9) and `toc_draft_v1`
(Magenta Book layers, up to 6 success and 3 failure pathways, mechanisms, assumptions on links,
result criteria and indicators, load-bearing assumption). Stub backends. Refine-replay per
`prompting.md` on three topics. Re-pin. Gate: `verify-fast` + `prompt-guard`. Commit.

1.2 **Schema and registry — `deep-reasoner`.** The revision exactly as contract § Schema (from
head `f1b6d3a8c2e5`, patterns `b5e1d7a4c026` and `c7e2a9f4b1d8`), mirrored in `core/schema.py`;
`tests/core/test_migration_054_slice.py` (round trip, downgrade refusal); the six
`len(metadata.tables)` asserts from 43 to 51; S1; S2; `compose_toc` draft branch (S3); S6's
backend sites and grep test; S7's close skip; the C15 server setting with the create guard;
`scripts/ops_remove_toc_tasks.py` (database rows only; object deletion arrives in 7.2, R13).
Gate: **full `make verify`** (schema). Commit.

1.3 **Task Agent profile and draft walk — `deep-reasoner`.** `runtime/task_agent_toc.py`;
`theory_of_change/graph.py` (S8: models, validator, item text and hash, `edit_row`,
`apply_changes`); `theory_of_change/draft/` (`toc_draft`); harness nodes; the `toc` plan slot;
`make openapi-sync`. Tests: plan validation per entry point; ES or OS payloads rejected on a ToC
task and the reverse; a stub draft passes the validator; the thread stays open after the draft
walk. Gate: `verify-fast` + `prompt-guard` + `drift-check` + `frontend-verify`. Commit.

1.4 **Read API and canvas — `fast-worker`, then lead polish.** S14 public reads that exist now
(`GET ""`, `GET /pathways`); router registration and the route-table test (X5); the conformance
entries; the parametrised access-matrix test (R8); `@xyflow/react` through the dependency gate;
`views/toc/` read-only (`TocResult`, `TocCanvas`, `AssumptionBand`, `TocKey`, `PathwayList`);
`capabilities.ts` flag; `NewTaskView` copy; vitest from fixtures. Gate: `verify-fast` +
`drift-check` + `frontend-verify` + `pnpm e2e`. Commit.

1.5 **E1 and the E6 harness — `fast-worker` for harness code; `lead` for the E6 rubric, the
soft-match threshold and the reference set** (eval criteria are lead-only, R16).
`scripts/evals/toc/`: `e1_structure.py` over drafts from ~30 descriptions; `e6_rebuild.py` (soft
node matching, edge F1 with direction, impact and outcome recall, the Mayne rubric judge,
5-run stability). The lead picks the first 20 published theories (2025–26 first), writes their
labels with source URLs and licences, and runs both once. Gate: `verify-fast`. Commit.

Exit: **full `make verify`**; live check (1) — `lead`; PR into `feat/theory-of-change`; step-7
review stack.

## Deliverable 2 — Evidence check

2.1 **Prompts — `lead`** (prompt-bearing). `toc_item_judge_v1` (stance, quote, condition, case
study and indicator for boxes; fenced untrusted text), `toc_discover_v1` (it runs in this
deliverable's chain, S3), `toc_summary_v1`, and the item-search guidance text. Re-pin. Gate:
`verify-fast` + `prompt-guard`. Commit.

2.2 **Child search and dispatch — `deep-reasoner`.** S5 in `option_search.py`; the ToC pool and
the scaled join timeout; S4's driver, the registry-based validation in `_dispatch_run` and the
follow-on, and the ToC `admit_and_mint`. Done when the seven OS test files pass unedited and the
OS-beside-ToC join test passes. Gate: **full `make verify`** (runner). Commit. Own review pass
(`/code-review`) before 2.3, as task 044 did for its rename.

2.3 **Check walk — `deep-reasoner`.** S3 check and recheck branches and directives (confirming
the per-scope screening rule); the runner's `toc` dispatch and join; `toc_discover`;
`toc_judge` (C5); `theory_of_change/evidence/grade.py` (S10); `toc_summarise`; the 80-item cap;
"Check again" with the restart rule (R7); `POST /toc/recheck`; evidence and summary reads (S14).
Tests per contract acceptance 2 plus discover-then-judge order. `toc_consolidate` is a
pass-through until 3.2. Gate: **full `make verify`** (runner, `task_source_snapshot` writes).
Commit.

2.4 **Detail panel and Sources — `fast-worker`, then lead polish.** `DetailPanel` with the three
groups, case studies, indicators and quality chips; grade colours and line styles; box bars;
header counts; the Sources tab source-type split. Gate: `verify-fast` + `frontend-verify` +
`pnpm e2e`. Commit.

2.5 **E2 and E2b — `fast-worker` for harnesses; `lead` for the label mapping and the Consensus
run** (the mapping decides what the numbers mean; the Consensus run spends money). Licences
recorded; the ablation arm; E2b on 50 fixed claims after the owner approves the run (about
$2.50), cached, aggregates only committed. Check the E2 stop condition before Deliverable 3.
Gate: `verify-fast`. Commit.

Exit: **full `make verify`**; live check (2) — `lead`; PR; review stack.

## Deliverable 3 — Discover and consolidate

3.1 **Prompt — `lead`** (prompt-bearing). `toc_consolidate_v1` (two stages; one-line reasons;
flag every change to user work). Re-pin. Gate: `verify-fast` + `prompt-guard`. Commit.

3.2 **Consolidate, Undo, Restore, Keep mine — `deep-reasoner`.** `toc_consolidate` through
`apply_changes` with the before-state event; the routes (C9); the limits check. Tests per
contract acceptance 3. Gate: `verify-fast` + `drift-check` (no schema or ingest contact, R14).
Commit.

3.3 **Screens — `fast-worker`, then lead polish.** The *changed by Policy Atlas* mark, the
side-by-side panel with Keep mine, "Considered and set aside" with Restore, the thread's summary
line with Undo. Gate: `verify-fast` + `frontend-verify` + `pnpm e2e`. Commit.

3.4 **E6 rerun — `lead`** (eval reading). On consolidated theories; numbers into
`verification.md`.

Exit: **full `make verify`**; live check (3) — `lead`; PR; review stack.

## Deliverable 4 — Editing during the check

4.1 **Prompt — `lead`** (prompt-bearing). `task_agent_toc_v2` adds `graph_edits` (S9). Re-pin.
Gate: `verify-fast` + `prompt-guard`. Commit.

4.2 **Edit routes, admission, C11 — `deep-reasoner`.** S14 writes through `edit_row`; one event
per edit; `DELETE` in CORS with the preflight test (X4); S7's admission of Task Agent turns
during a check; S9 applied; the C11 Redraft and Keep choice. Race tests per contract acceptance
4, with explicit barriers, not sleeps. Gate: `verify-fast` + `prompt-guard` + `drift-check`
(R14). Commit.

4.3 **Canvas editing — `fast-worker`, then lead polish.** Add, edit, delete, connect, move
conditions, mark the critical connection; *Edited · check pending*, Keep the evidence and
"Check again" (W17); the 409 reload with what
changed. Gate: `verify-fast` + `frontend-verify` + `pnpm e2e`. Commit.

Exit: **full `make verify`**; live check (4) — `lead`; PR; review stack.

## Deliverable 5 — Web search

5.0 **Mantle check — `lead`** (an egress fact the code will pin). One call against Mantle in
us-east-1 with the long-term key: confirm the base path and that the hosted `web_search` tool is
accepted. Record it. Stop condition if refused.

5.1 **Route config — `deep-reasoner`.** `WebSearchRoute` and its parser with the address checked
in 5.0; the three route tables; fixture TOMLs; the non-web address test; README and
`.env.example` (R18). Gate: `verify-fast`. Commit.

5.2 **Call, pages, step — `deep-reasoner`.** S11; the `toc_web` child step; "web not searched";
the web cap end to end; one smoke call per route, recorded. Gate: **full `make verify`**
(egress, `task_source_snapshot` writes). Commit.

Exit: live check (5) — `lead`; PR; review stack with the security lane on egress.
**Merge point (C15, R15):** after Deliverable 5's review, the lead asks the owner whether
`feat/theory-of-change` merges to `dev` now (server setting off) or after Deliverable 9.

## Deliverable 6 — Stress test and discuss

6.1 **Prompt and discuss template — `lead`** (prompt-bearing). `toc_stress_v1`, and the template
that renders the graph and its evidence into the discuss context, with every quote and page
excerpt through `sanitize_prompt_field` and a fence (R12). Re-pin. Gate: `verify-fast` +
`prompt-guard`. Commit.

6.2 **Chat kind and discuss wiring — `deep-reasoner`.** `stress_test` kind; the four questions
stored on the conversation; discuss uses 6.1's template through `answer_core`; neither chat
writes the graph (test); a fence test on a web-page quote. Gate: `verify-fast` + `drift-check`.
Commit.

6.3 **Pane — `fast-worker`, then lead polish.** `StressTestPane`, canvas highlight of the tied
element. Gate: `verify-fast` + `frontend-verify` + `pnpm e2e`. Commit.

Exit: **full `make verify`**; live check (6) — `lead`; PR; review stack.

## Deliverable 7 — Bring your own theory

7.1 **Prompt — `lead`** (prompt-bearing). `toc_import_v1`. Re-pin. Gate: `verify-fast` +
`prompt-guard`. Commit.

7.2 **Storage and route — `deep-reasoner`.** S12; `POST /uploads` and `GET /uploads/{id}` with
C8's checks and headers; the audit event and span; `toc_import`; object deletion added to
`ops_remove_toc_tasks.py` (R13); the access matrix extended. Gate: `verify-fast` +
`drift-check`. Commit.

7.3 **Infrastructure — `deep-reasoner`; `lead` review** (production config). The bucket, the
task-role grant, the two environment values, `test_service_wiring.py` and `test_synth.py`.
Gate: infra unit tests. Commit.

7.4 **Screens — `fast-worker`, then lead polish.** Upload in the Task Agent pane; "Your
original". Gate: `verify-fast` + `frontend-verify` + `pnpm e2e`. Commit.

Exit: **full `make verify`** + infra tests; live check (7) — `lead`; PR; review stack with the
security lane on uploads.

## Deliverable 8 — Export

8.1 **Backend exports — `fast-worker`.** CSV, draw.io XML, PowerPoint (`python-pptx` through the
dependency gate; attached connectors; arrowheads). Authenticated routes (S14). Gate:
`verify-fast` + `drift-check`. Commit.

8.2 **Frontend exports — `fast-worker`.** PNG and SVG with `html-to-image@1.11.11` (dependency
gate); JSON from the graph read; download buttons; a binary-download helper. Gate: `verify-fast`
+ `frontend-verify` + `pnpm e2e`. Commit.

8.3 **Manual import checks — `lead`** (evidence the owner reads). PowerPoint, diagrams.net, Miro
import, and Google Slides per A9. Recorded with screenshots.

Exit: **full `make verify`**; PR; review stack.

## Deliverable 9 — Design from an option

9.1 **Create path and back-list — `deep-reasoner`.** C13 `from_option` with validators and
error codes; `_write_task_links` widened for ToC targets only, reading the parentless walk of an
OS source; `source_option_id`; `TaskLinkOut.source_option_id`; the C14 option direction in
`runtime/inherit.py`; slot seeding; the newer-run flag; the back-list read (S14, R9). Gate:
**full `make verify`** (`task_link`, `task_source_snapshot` writes; R14). Commit.

9.2 **Option page — `fast-worker`, then lead polish.** The button between `OptionCard.tsx:524`
and `:525`, hidden for non-writers; the back-list; `useCreateTask` sends `from_option`. Gate:
`verify-fast` + `frontend-verify` + `pnpm e2e`. Commit.

Exit: **full `make verify`**; live check (9) — `lead`; PR; review stack.

## Phase 10 — Close the build — `lead`

`docs/deferred.md` delta (rubric 19); `verification.md` complete; ADR 0042 evidence and sign-off;
the merge to `dev` on the owner's word if not already done at the Deliverable 5 merge point.
The contract's spec changes 1–5 are applied at the design phase's close, with the ADR, not here:
the plan folds above amend two of them (the child-search location, the chain order), so they wait
for the approved plan, not for the build (R15).

## Plan-review folds (2026-10-23)

Two read-only lanes on the first draft (`28eb13c2`): Codex (`codex-rescue`), seven findings, and
`deep-reasoner` on the areas Codex did not cover, nineteen findings. All adopted.

| # | Finding | Fold |
|---|---|---|
| X1 | `toc_item_searches` was both a chain step and a runner stage | S3: runner stage only |
| X2 | The follow-on pattern handles one hop | S4: the sequence driver |
| X3 | Task Agent turns are refused while a walk runs | S7: admission during a check |
| X4 | CORS has no `DELETE` | S14 and 4.2 |
| X5 | No router registration work | S14 and 1.4 |
| X6 | Unattended still collects floor triggers | S2: kept, recorded, tested |
| X7 | Moving private names breaks patch sites | S5: stays in `option_search.py` (amends C2's location) |
| R1 | Discovered links were never judged | S3: discover before judge |
| R2 | Minted walks validate as `ScopingPlan` | S4: registry validation, ToC mint |
| R3 | 80 children on the 4-wide OS pool and a fixed join timeout | S5: own pool, scaled timeout, coexistence test |
| R4 | Short-term Bedrock keys are region-bound; Mantle path unclear | S11 and 5.0 |
| R5 | Enum path segments break the conformance sweep | S14 |
| R6 | Exports were made public beyond C17 | S14: authenticated |
| R7 | No restart after an interrupted check | S4: "Check again" runs a full check |
| R8 | Access matrix only in D7 | S14 and 1.4 |
| R9 | No back-list read | S14 and 9.1 |
| R10 | Check-walk directives unspecified | S3 directives |
| R11 | `graph_edits` in the prompt before it is applied | S9: v1 without, v2 at 4.1 |
| R12 | Web text in discuss without the fence | 6.1 and 6.2 |
| R13 | Ops script deletes objects before storage exists | 1.2 and 7.2 |
| R14 | Gates missing or inconsistent | every sub-phase gated |
| R15 | Merge point and spec-change timing | D5 merge point; Phase 10 note |
| R16 | Prompt- or eval-bearing work delegated | 1.5 and 6.1 to `lead` |
| R17 | Web cost not captured | S11 tool-call count |
| R18 | Mandatory route table breaks overlay files | 5.1 |
| R19 | `GET /` path; contract says seven tables | S14 `GET ""`; contract slip fixed |

Two folds change the approved contract and are flagged at the plan gate: **X7** keeps the child
search in `option_search.py` instead of a new module (C2's location, not its intent), and **R1**
orders discover before judge (consistent with C6's "judged against the existing pool only").

## Out-of-plan reminders

- The Consensus API bills every call: no E2b run without the owner's approval of that run.
- The local Bedrock key lasts at most 12 hours and works in one region: the Mantle check uses the
  long-term key.
- Two checkouts share the test database and Playwright port 5199: run the full gate serially.
- Never open a second PR for task 053; PR #84 is the only one.
