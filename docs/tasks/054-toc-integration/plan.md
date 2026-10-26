# Plan: 054-toc-integration

Increments 1–7, decisions C1–C21, rulings T1 and W1–W18, the schema and every term are defined in
[contract.md](contract.md). This plan fixes the seams the contract leaves to the build (S1–S14),
routes each step to an executor and sets the gates. It adds nothing to scope.

> **Status:** first drafted 2026-10-23 and reviewed in two read-only lanes (26 findings, folded;
> § Plan-review folds). **Re-planned 2026-10-26** after the owner's wireframe and journey review
> and the ruling on an iterative build (contract C18): a simple core first, an iteration phase,
> then six increments. Plan and contract approved (before implementation): _pending_. ADR 0042 is
> written after approval and before the build opens.

**How this build runs (C18).** Build the narrowest core that runs end to end, try it on real
topics, tune it, then add one increment at a time. The owner uses each increment in the app before
the next starts.

- **Inner loop.** Small commits. Each runs the tests for the modules it touches plus `make
  verify-fast`; add `make prompt-guard` for a prompt change, `make drift-check` for a contract-model
  change, `make frontend-verify` for a frontend change. No full gate per step.
- **Full `make verify`** at build open (P0), when a migration lands (1.2, 5.2, 7.1), and at the
  end of each increment before its PR. The two checkouts share the test database and Playwright
  port 5199: run full gates serially.
- **Reviews.** `/code-review` and the security lane on each increment's PR, focused as C18 lists.
  The contract verifier, a Codex adversarial pass on the code and `/simplify` run once, at P8,
  before the merge to `dev`.
- **Executors.** Judgment-bearing work goes to `deep-reasoner` (owner ruling 2026-09-04);
  mechanical work to `fast-worker`; prompts, eval criteria and the try-it sessions are `lead`
  (AGENTS.md); taste-bearing screens get a `lead` polish pass after the delegate lands structure
  and tests (owner ruling 2026-09-05). Every `lead` mark carries its reason.
- **Housekeeping.** Stage by explicit path, never `git add -A`; check `git log` before reporting,
  because another session may share this checkout.

## Seams fixed here (lead design)

S1. **Registry entry** (C3, C12). `THEORY_OF_CHANGE = "theory_of_change"`; `AnyPlan = TaskPlan |
ScopingPlan | TocPlan`; `CAPABILITIES[THEORY_OF_CHANGE] = CapabilitySpec(plan_model=TocPlan,
compose=compose_toc, lattice={}, load_task_agent=_toc_task_agent)`; `expect_toc_plan`.
`test_capability_registry.py` widens to three keys; the AST guard covers the new module.

S2. **`TocPlan`** (`runtime/toc_plan.py`). `title`, `question`, `entry_point` (`outcome_first ·
intervention_first · existing_theory`), `intended_change`, `target_population`, `intervention |
None`, `dosage | None`, `existing_theory_text | None`, `upload_id | None`, `where | None`,
`time_horizon | None`, `context | None`, `evidence_restriction` (the OS shape, reused),
`from_option | None`, `steering_mode = "unattended"`, `steer_point_defaults = {}`,
`source_turn_index | None`. Ready when `intended_change` and `target_population` are set, plus the
entry point's own slot (spec § Plan slots). The Task Agent asks at most two questions before
drafting (J2): the measurable change, and whether a theory exists; it suggests every other slot.
Floor triggers of the reused spine steps are recorded in History (C12); a ToC walk never pauses
(test).

S3. **Walk kinds and chains** (C3). Every main ToC walk's intent record carries `purpose = 'toc'` and
`context.toc_walk ∈ {draft, check, recheck}`; recheck and named-link checks add `context.links`.
`compose_toc(plan, purpose, context)`:
- `draft`: `inherit` (only with `from_option`) → `toc_draft` (or `toc_import`).
- `check`: `screen_abstract` → `classify` → `appraise` → `toc_discover` → `toc_merge` →
  `toc_judge` → `toc_choose` → `toc_summarise`. With `context.links` (Search for more), the same
  chain without discover, merge and choose.
- `recheck` (C19, user-started): `toc_same_meaning` → `toc_judge` over the documents already
  judged for the named links, no search → `toc_summarise` for those links. A discovered link, or
  one after Search for more, is judged against the whole screened-in pool (C5).
- The item-search child (`targeted`, `acquire_only`): `acquire` → `toc_web` (`toc_web` only when
  the route's web search is enabled, increment 3).
**Item searches are a runner stage, not a chain step**: the runner dispatches the children in a
`purpose == 'toc'` branch beside `LONGLIST_PURPOSE`, before the first chain step of a check walk,
and joins them before `screen_abstract`, emitting `toc_item_searches` as an event. Each new step
gets a `COMPONENT_REGISTRY` entry, a `TOC_STEPS` tuple in `task_plan._validate_registry`, and a
harness node; `build_graph`'s edge map is built from the step dictionaries.
**Directives.** Item search: the item text as intent; guidance asking for evidence on the step and
on each of its conditions, for and against; a record cap of 🟡 20 per link; the plan's evidence
restriction as filters; no ingest. Screen: the theory (intervention, intended change, population)
as the screening intent, the place carried as the user's place and never a criterion. Each walk
screens only documents its own children acquired plus inherited ones not yet screened in the task.

S4. **Sequence driver and dispatch** (C3, C19). `run_toc_sequence(engine, *, task_id,
first_outcome)` in `api/toc_start.py` follows `draft → check` (one hop) with a duplicate guard.
`_dispatch_run` calls it for ToC outcomes and validates every minted walk through
`validate_plan(capability, …)`, forcing `steering_mode = "unattended"` by capability. A ToC
`admit_and_mint(engine, task_id, *, toc_walk, links=None)` on the `longlist_start` pattern,
without its OS reads. Every launch path (Start, the follow-on, Check again, Search for more,
Redraft) goes through `_dispatch_run`. **Restart:** Check again on a task whose latest check walk
did not succeed mints a full `check`, so an interrupted check always has a way forward.

S5. **Child search inside `option_search.py`** (C2). `ChildSearchRequest(intent, context, plan_id,
stage, pool)`; `run_child_search(…)`, which `run_option_search` calls with the option's values;
`dispatched_children(…, stage)` and `join_children(…, stage, timeout)`; `_run_child` resolves its
plan through the registry. `walk_pool.toc_item_pool()` at 🟡 width 8; join timeout `max(1800,
ceil(n / width) × 300)` s.

S6. **OS-only branches that must learn ToC.** `_finish_run`'s abandon branch also for `toc`;
`_latest_run_row`'s parentless filter (`_common.py`) also for ToC; `persist_approved_plan` writes
`purpose='toc'` and `context.toc_walk='draft'`; `get_plan` and `patch_plan` get a ToC branch;
`plan_slot`, `PlanOut` and `TaskAgentTurnOut` gain a `toc` slot (additive); `NewTaskView`
`FORM_COPY` gains a ToC entry; `ArtefactView` and `taskResult.ts` gain `isToc`. A grep test lists
every `== OPTIONS_SCOPING` / `=== "options_scoping"` site and fails on a new one without a
reviewed ToC decision.

S7. **The Task Agent thread stays open and admits turns during a check.** ToC walks skip
`_finish_run`'s conversation close. During a `check` or `recheck`, a ToC turn is admitted: it may
answer a question or, from increment 2, carry graph edits (S9); it may not change the plan (it
says "after the evidence check finishes"). A running `draft` keeps today's refusal. The agent
posts a message when the draft lands (J3) and, after the check, the change list (increment 2 adds
Undo), the pending count, and the stress-test suggestion (increment 4 adds the button) (J5, J7).

S8. **Graph module** (`theory_of_change/graph.py`). Pydantic read and write models for the graph
tables; the validator (E1 checks, the *broken* pathway rule); `item_text(link) -> str` (sentence, if, for, then, because, both box texts, conditions, and the
place and population for the search) and `assumption_type(link)` from the two layers (spec § Vocabulary); `item_hash(link)` over the link fields, both box texts and
the conditions, **not** the plan-scope fields (C19); `link_state(link, active_walk) -> checking ·
checked · pending · kept · no_change` by the C19 transition table; `edit_row(conn, …, expected_revision)`
raising `StaleRevision` → 409 `toc_stale_revision`; `apply_changes(conn, task_id, changes,
observed_revisions) -> ApplyReport(applied, skipped)` for merge, choose, Undo and Keep mine (C10).

S9. **Change requests through the Task Agent** (increment 2). `task_agent_toc_v2` may return
`graph_edits` (closed list: add, edit, delete, connect, set conditions, mark critical). Applied
through `edit_row` as the user's edits; a stale revision returns the conflict in words; a
plan-slot change triggers C11 instead. `task_agent_toc_v1` has no `graph_edits` and says edits are
made on the canvas.

S10. **Grade** (C4). `theory_of_change/evidence/grade.py`: `grade(judgements, appraisals,
question) -> GradeResult(grade, against, counts)`, called with the judgements whose `item_hash`
equals the link's `counted_hash`; constants for the score thresholds (4, 3),
the web cap and the robust-model score (3); `lower(a, b)` for the canvas colour; `rule_text()` for
the reading guide. Table test over every row and boundary for both questions.

S11. **Sentences and their check** (C20). `theory_of_change/summary/`: one summarise call returns
the header paragraphs, evaluation questions, `elsewhere_sentence` and `here_sentence` per link,
and `description` per box, each with a list of cited document ids. `check_citations(sentence,
allowed_ids) -> ok | replaced` runs before anything is written; the no-repeat rule is in the
prompt and checked by a test that a *holds here* sentence does not repeat a quote the *worked
elsewhere* sentence used; `merged = all documents answer both questions the same way` decides the
merged paragraph.

S12. **Web call** (increment 3; C7). `resolve_web_search_client()`, `traced_web_search(…) ->
WebSearchResult(text, citations, usage, tool_calls)` in `core/openai_client.py`;
`token_usage_from_responses` in `core/usage.py`; `evidence_search/sourcing/web_pages.py`
`freeze_pages(…)` with the C7 fetch limits (🟡 5 per call, 🟡 100 per walk) and the skipped URLs recorded. A short-term Bedrock key works in one region only, so a developer on
`bedrock-local` with a London key gets "web not searched", not a crash. README and `.env.example`
gain the `web_search` table for overlay route files.

S13. **Frontend structure** (C21; the wireframes are the reference). `views/toc/`:
`TocResult.tsx` (header paragraphs, toolbar, reading guide toggle), `TocCanvas.tsx` (React Flow;
columns by layer, rows by order; neutral rounded nodes; curved edges coloured by `lower`; the
critical dot; blue dots for edited, pending and changed items; hover summaries),
`ReadingGuide.tsx`, `DetailPanel.tsx` (box: measured, seen, case studies; link: reading, how it
works and what it needs, then both questions with their documents, a shared document once; the
pending block; changed-by-Policy-Atlas block), `DetailedInformation.tsx` (expand and collapse
sections; boxes as label, title, description; links as three paragraphs or one merged; the "+"
document lists; the Assumptions section grouped by `assumption_type(link)` from S8 (W18); pending label and buttons; print styles for the PDF), `OriginalView.tsx`,
`StressTestPane.tsx`, `exports.ts`. The ToC sections of the navy plan panel in
`PlanDocument.tsx`. Hooks in `api/queries.ts` (`useToc`, `useTocEvidence`) and `api/mutations.ts`
(`useTocEdit`, `useTocKeep`, `useTocRecheck`, `useTocUndo`, `useTocRestore`, `useTocKeepMine`,
`useTocUpload`). Updates through the existing run SSE stream.

S14. **API shape** (C17). `api/routers/toc.py`, prefix `/api/v1/tasks/{task_id}/toc`, no
router-level auth so reads can use the public leg.
- **Public reads:** `GET ""` (graph with both grades, link states, revisions, rule text; also the
  JSON export), `GET /links/{link_id}/evidence`, `GET /boxes/{box_id}/case-studies`,
  `GET /pathways`, `GET /summary`. No enum path segments. On a public non-ToC task each returns 404
  `toc_not_found`, so all go into `_CONDITIONALLY_PUBLIC_GETS`.
- **Authenticated reads:** `GET /export/csv`, `/export/drawio`, `/export/pptx`,
  `GET /uploads/{upload_id}`.
- **Writes** (write grade, each carrying `expected_revision`): `POST`, `PATCH` and `DELETE` for
  boxes, links, pathways and band items; `POST /links/keep` and `POST /links/recheck` (body: link
  ids, or all pending); `POST /links/search-more`; `POST /events/{event_id}/undo` (one change or
  the whole step); `POST /pathways/{id}/restore`; `POST /boxes/{id}/keep-mine`,
  `/links/{id}/keep-mine`, `/pathways/{id}/keep-mine`; `POST /boxes/{id}/accept`,
  `/links/{id}/accept`, `/pathways/{id}/accept` (C9); `POST /uploads`.
- **CORS:** `DELETE` joins `allow_methods` in `api/app.py`, with a preflight test.
- **Registration:** public and authenticated routers included in `api/app.py`, public first, with
  a route-table test that every ToC path is mounted and in the OpenAPI document.
- **Back-list:** `GET /api/v1/tasks/{task_id}/options/{option_id}/theories` (authenticated).
- **Access matrix:** one parametrised test, started in increment 1 and extended by each increment,
  runs the four caller kinds against every ToC route.

## D1 — Design close — `lead`

After the owner approves the contract and this plan: write ADR 0042 (Accepted, with sign-off
date; contract § ADR scope); apply contract spec changes 2–5 (the ToC product surface, the OS
artefact and scope, the execution spec's open-web seam, the product in/out table), each quoting
its ruling, and log them; record the approval in both documents' status lines. Commit by explicit
path. Then stop: the build runs in a fresh session with `task-cycle-build`.

## P0 — Build open — `lead` (inline)

PR #84 merged to `dev` (stop condition otherwise). Create `feat/theory-of-change` from `dev`; bring
the task 054 docs onto it. Full `make verify`. Never build on a red base.

## Increment 1 — Core

The narrowest version that runs end to end on a real topic: no editing, no web, no import, no
export, no option link, no stress test.

1.1 **Prompts — `lead`** (prompt-bearing). `task_agent_toc_v1`, `toc_draft_v1`, `toc_discover_v1`,
`toc_merge_v1`, `toc_judge_v1`, `toc_choose_v1`, `toc_summary_v1`, the item-search guidance.
Stub backends for each. Replay on three fixed topics, the obesity option of the wireframes first.
Pin. Commit.

1.2 **Schema and registry — `deep-reasoner`.** Revision 1 exactly as contract § Schema (from the
head at build open), mirrored in `core/schema.py`; `tests/core/test_migration_054_core.py` (round
trip, downgrade refusal); the `len(metadata.tables)` asserts from 43 to 49; S1; S2; S6's backend
sites and grep test; the C15 server setting with the create guard; `scripts/ops_remove_toc_tasks.py`
(database rows; object deletion arrives in 5.2). Gate: **full `make verify`** (migration). Commit.

1.3 **Draft walk and Task Agent — `deep-reasoner`.** `runtime/task_agent_toc.py`; S8 without
`edit_row` and `apply_changes` callers yet; `theory_of_change/draft/`; harness nodes; S3 draft
branch; S4 driver; S7 (thread open, draft message); the `toc` plan slot; `make openapi-sync`.
Commit.

1.4 **Check walk — `deep-reasoner`.** S5 child search and pool, with the seven OS test files
unedited and the side-by-side join test; S3 check branch and directives; the runner's `toc`
dispatch and join; `toc_discover`, `toc_merge`, `toc_judge` (C5), `toc_choose`, `toc_summarise`
with S11; S10 grade; the 80-link cap. Commit after each step lands with its tests; `/code-review`
on the S5 change before the rest builds on it.

1.5 **Read API and Result page — `fast-worker`, then lead polish** (taste-bearing). S14 public
reads; router registration and route-table test; the access matrix; `@xyflow/react` through the
dependency gate; **only** the five read-only core components of S13 (`TocResult`, `TocCanvas`,
`ReadingGuide`, `DetailPanel`, `DetailedInformation`) and the plan panel's ToC sections; the
editing, original, stress-test and export parts of S13 belong to increments 2, 5, 4 and 6; `capabilities.ts` flag; `NewTaskView`
copy; vitest from fixtures. The lead's polish matches the wireframes. Commit.

1.6 **First try — `lead`** (evidence the owner reads). Full `make verify`. One live topic end to
end on `openai-direct`; notes and screenshots in `verification.md`. The owner tries it.

### Iteration phase (part of increment 1)

Short loops until the owner says the core is good enough to build on. Each loop: run one or two
real topics, read the Result page against its sources, change one thing, commit with the inner-loop
gate, try again. Expected targets, in rough order: the draft's shape and wording; the judge's
stances and quotes; the grade constants; the sentences and the no-repeat rule; the canvas layout
and the panel. The lead keeps a short log in `verification.md` (what changed, why, what improved).

1.7 **E1, E2, E6 — `fast-worker` for harness code; `lead` for the E6 reference set, its labels, the
soft-match threshold and the E2 label mapping** (eval criteria are lead-only). `scripts/evals/toc/`:
`e1_structure.py`, `e2_judge.py` (SciFact, Check-COVID, PubMedQA, Evidence Inference abstract
subset; the ablation arm), `e6_rebuild.py` (20 published theories, 2025–26 first). Run during the
iteration; numbers recorded. E2b only after the owner approves its cost. Check the E2 stop
condition before increment 2.

Exit: the owner's word; full `make verify`; PR into `feat/theory-of-change`; `/code-review` and the
security lane on the public read API and the server setting.

## Increment 2 — Editing and changes

2.1 **Prompts — `lead`.** `task_agent_toc_v2` (`graph_edits`, S9), `toc_same_meaning_v1`. Pin.
Commit.

2.2 **Writes, states and Undo — `deep-reasoner`.** S14 writes through `edit_row`, one event per
edit; `DELETE` in CORS with the preflight test; C19 states, Keep the evidence, the minimal Check
again (`recheck` walk), Search for more; box edits marking their links pending; merge and choose
through `apply_changes` with before-state events; Undo per change and Undo all; Restore; Keep
mine; S7's admission of turns with edits during a check; S9 applied; C11's Redraft and Keep the
canvas. Race tests with explicit barriers. Commit per piece.

2.3 **Screens — `fast-worker`, then lead polish.** Canvas editing (add, edit, delete, connect,
conditions, mark critical); the blue dots; the pending block in the panel; the pending label and
buttons in Detailed information; the changed-by-Policy-Atlas block with Keep mine; the Task
Agent's change list with Undo, and Check all and Keep all; Restore in *Considered and set aside*;
the 409 reload. Commit.

Exit: try it (2) — `lead`, then the owner; full `make verify`; PR; `/code-review` and the security
lane on writes, Undo and the 409 path.

## Increment 3 — Web search

3.1 **Mantle check — `lead`** (an egress fact the code pins). One call to Mantle in us-east-1 with
the long-term key: confirm the base path and that the hosted `web_search` tool is accepted.
Record it. Stop condition if refused.

3.2 **Route config, call, pages — `deep-reasoner`.** `WebSearchRoute` and its parser; the three
route tables; fixture TOMLs; the non-web address test; S12; the `toc_web` child step; "web not
searched"; the fetch limits with a test; the web cap end to end; one smoke call per route. Commit per piece.

Exit: try it (3); full `make verify`; PR; `/code-review` and the security lane on egress and page
text.
**Merge point (C15):** the lead asks the owner whether the branch merges to `dev` now (server
setting off) or later.

## Increment 4 — Stress test and discuss

4.1 **Prompt and discuss template — `lead`.** `toc_stress_v1`; the template that renders the graph
and its evidence into the discuss context, every quote and page excerpt through
`sanitize_prompt_field` and a fence. Pin. Commit.

4.2 **Chat kind, wiring and pane — `deep-reasoner`, then `fast-worker` for the pane, then lead
polish.** `stress_test` kind; four questions tied to a box or link, starting with the critical
connection; discuss through `answer_core`; neither chat writes the graph; the fence test; the Task
Agent's "Start the stress test" button; `StressTestPane` with canvas focus. Commit.

Exit: try it (4); full `make verify`; PR; `/code-review` and the security lane on the chat context
fence.

## Increment 5 — Bring your own theory

5.1 **Prompt — `lead`.** `toc_import_v1`. Pin. Commit.

5.2 **Storage, route, revision 2 — `deep-reasoner`.** Revision 2 (`toc_upload`), the count assert
to 50; `UploadStore` (`S3UploadStore`, `LocalUploadStore`, chosen by
`POLICY_ATLAS_TOC_UPLOAD_BUCKET`); `POST /uploads` and `GET /uploads/{id}` with C8's checks and
headers; the audit event and span; `toc_import`; object deletion in `ops_remove_toc_tasks.py`; the
access matrix extended. Gate: **full `make verify`** (migration). Commit.

5.3 **Infrastructure — `deep-reasoner`; `lead` review** (production config). The bucket, the task
role grant, the environment values, `test_service_wiring.py`, `test_synth.py`. Commit.

5.4 **Screens — `fast-worker`, then lead polish.** Upload in the Task Agent composer; the original
under *Starting point* in the plan panel; "Your original" in the toolbar. Commit.

Exit: try it (5); full `make verify` and the infra tests; PR; `/code-review` and the security lane
on uploads.

## Increment 6 — Export

6.1 **Exports — `fast-worker`.** CSV, draw.io XML and PowerPoint (`python-pptx` through the
dependency gate; attached connectors) as authenticated routes; PNG and SVG with
`html-to-image@1.11.11` (dependency gate); JSON from the graph read; the Download menu; the PDF
report as the print of the Result page with Detailed information expanded. Commit.

6.2 **Manual checks — `lead`** (evidence the owner reads). PowerPoint, diagrams.net, Miro import,
Google Slides, the PDF. Recorded with screenshots.

Exit: full `make verify`; PR; `/code-review` and the security lane on the authenticated exports.

## Increment 7 — Design from an option

7.1 **Create path, revision 3, back-list — `deep-reasoner`.** Revision 3; C13 `from_option`,
validators and error codes; `_write_task_links` widened for ToC targets only; `TaskLinkOut`;
the C14 option direction in `runtime/inherit.py`; slot seeding; the newer-run flag; the back-list
read. Gate: **full `make verify`** (migration). Commit.

7.2 **Option page — `fast-worker`, then lead polish.** "How would this option work?" with the
button, hidden for non-writers, and the back-list, at the end of the expanded option card;
`useCreateTask` sends `from_option`. Commit.

Exit: try it (7); full `make verify`; PR; `/code-review` and the security lane on the link rule.
If this increment would disturb Options scoping, the owner may release the capability without it
first (W12).

## P8 — Close and merge — `lead`

The contract verifier; a Codex adversarial pass on the branch diff (`/codex:adversarial-review`,
typed by the owner); `/simplify`; findings adjudicated into `verification.md`. `docs/deferred.md`
delta; ADR 0042 evidence and sign-off; the merge to `dev` on the owner's word, server setting off.

## Plan-review folds (2026-10-23, first draft)

Two read-only lanes (Codex; `deep-reasoner`), 26 findings, all adopted. They hold in this
re-plan; where a later ruling replaced one, the fold says so.

| # | Finding | Where it lives now |
|---|---|---|
| X1 | Item searches were both a chain step and a runner stage | S3: runner stage only |
| X2 | The follow-on pattern handles one hop | S4: the sequence driver (now one hop, C19) |
| X3 | Task Agent turns refused while a walk runs | S7 |
| X4 | CORS has no `DELETE` | S14, 2.2 |
| X5 | No router registration | S14, 1.5 |
| X6 | Unattended walks still collect floor triggers | S2, C12 |
| X7 | Moving private names breaks patch sites | S5, C2 |
| R1 | Discovered links were never judged | S3; now discover, merge, judge, choose (W16) |
| R2 | Minted walks validate as `ScopingPlan` | S4 |
| R3 | 80 children on the OS pool, fixed timeout | S5 |
| R4 | Region-bound Bedrock keys; Mantle path unclear | S12, 3.1 |
| R5 | Enum path segments break the conformance sweep | S14 |
| R6 | Exports public beyond C17 | S14: authenticated |
| R7 | No restart after an interrupted check | S4 |
| R8 | Access matrix only late | S14, 1.5 |
| R9 | No back-list read | S14, 7.1 |
| R10 | Check-walk directives unspecified | S3 |
| R11 | `graph_edits` before they are applied | S9: v1 without, v2 in increment 2 |
| R12 | Web text in discuss without a fence | 4.1, 4.2 |
| R13 | Ops script deleting objects before storage exists | 1.2, 5.2 |
| R14 | Gates missing or inconsistent | Replaced by C18's gates |
| R15 | Merge point and spec-change timing | Increment 3 merge point; spec changes at design close |
| R16 | Prompt- or eval-bearing work delegated | 1.1, 1.7, 4.1 to `lead` |
| R17 | Web cost not captured | S12: tool-call count |
| R18 | Mandatory route table breaks overlay files | S12 |
| R19 | `GET /` path; table count | S14 `GET ""`; § Schema counts |

## Out-of-plan reminders

- The Consensus API bills every call: no E2b run without the owner's approval of that run.
- The local Bedrock key lasts at most 12 hours and works in one region: the Mantle check uses the
  long-term key.
- Two checkouts share the test database and Playwright port 5199: run full gates serially.
- Never open a second PR for task 053; PR #84 is the only one.
