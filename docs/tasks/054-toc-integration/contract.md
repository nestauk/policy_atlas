# Task contract: 054-toc-integration

One programme contract for the third capability, **Theory of change**, in nine numbered build
steps (owner memory: one contract per programme, numbered steps, no gate per step). It lands a
new task kind whose Result is a Magenta Book canvas: a drafted causal chain, every link,
assumption and result box graded against evidence in the background, pathways consolidated,
and a stress-test chat, with import, export and one entry point from Options scoping.

> **Status:** drafted 2026-10-23 · awaiting owner approval. Contract approved (before planning):
> _pending_ · Plan approved (before implementation): _pending_ · ADR: **0042** (to be written
> at step 4 of the design phase; § ADR scope).
>
> **Design source.** The capability spec
> [`docs/specs/capabilities/theory-of-change/`](../../specs/capabilities/theory-of-change/capability.md)
> ([components](../../specs/capabilities/theory-of-change/components.md)) holds the product
> intent and every owner ruling. This contract fixes the build: schema, interfaces, tests,
> sequence. Where the two differ, the contract's § Decisions is the newer word and the spec is
> updated with it (§ Spec changes).
>
> **Prior decisions this contract builds on** (context, not targets): the three owner rounds of
> 2026-10-23, recorded in the spec § Rulings as R1–R16, S1–S11 and the third round, plus one
> later ruling the same day (T1 below). Research behind them:
> [research-notes.md](research-notes.md). Owner-facing explainer:
> [theory-of-change.html](theory-of-change.html).
>
> **Branching.** `task/054-integrate-toc` sits on `aws-bedrock-integration` (task 053, PR #84,
> awaiting review), because it needs the model route file (`model_routes.toml`, ADR 0041).
> The build starts only after PR #84 merges to `dev` (§ Stop conditions; decision C15).

## Goal

A user can start a **Theory of change** task, agree a short plan with the Task Agent, and get
a canvas in the Magenta Book layout that they can edit at once while Policy Atlas grades the
evidence for each part in the background. Afterwards they can stress-test it, discuss it and
export it. A user in Options scoping can start one from an option's page.

Nine numbered deliverables, one per build step. The rubric, the plan and the ADR use the same
numbers. Each step is usable on its own (owner, R13: "sequence and compartmentalise").

1. **Shell and draft.** The task kind, its plan, its Task Agent, the draft, a read-only
   canvas with its bands, assumption cards and key, the list view, the build flag.
2. **Evidence check.** One search per item over OpenAlex and Overton, the reused Evidence
   search spine, the per-document judge, grades and flags, case studies and indicators, the
   detail panel, the Sources tab, the summary with evaluation questions.
3. **Discover and consolidate.** Pathways found in the evidence; merging, setting aside and
   choosing; flagged changes to user work; Restore, Keep mine and Undo.
4. **Editing during the check.** Canvas editing, the edit queue and follow-up check,
   *out of date*, Check again, History events, change requests through the Task Agent, the
   plan-change choice (C11).
5. **Web search.** OpenAI's web search tool as a third source on both routes, pages frozen as
   untrusted text.
6. **Stress test and discuss.** The `stress_test` chat kind; discuss with the theory as
   context.
7. **Bring your own theory.** Pasted text, image and PDF import; the uploads bucket; the
   "Your original" view.
8. **Export.** PNG, SVG, CSV, JSON, draw.io, then PowerPoint.
9. **Design from an option.** The button on the Options scoping option page, the option
   direction of `inherit`, the shared documents, the back-list, the newer-run flag.

## Deliverable

Code, migrations, prompts, infrastructure and tests for deliverables 1–9 on a feature branch
(C15), behind the build flag `VITE_THEORY_OF_CHANGE`; ADR 0042; the spec changes in § Spec
changes; the three first evals (E1, E2 with E2b, E6) built and run once with their numbers
recorded; `verification.md`. Removing the build flag is **not** in this contract (§ Scope).

## Terms

| Term | Meaning |
|---|---|
| **ToC** | Theory of change. The capability (`theory_of_change`) and its task kind. |
| **Layer** | One of the four Magenta Book columns: Inputs · Outputs · Outcomes · Impact (owner, S1). Spec § Vocabulary. |
| **Box** | One element in a layer (`toc_box`). A failure outcome is a box with layer `failure_outcome`. |
| **Link** | A causal step between two boxes (`toc_link`), with if / for / then / because / unless text. |
| **Assumption** | A condition on one link (`toc_assumption`). Its **type** (delivery · take-up · behaviour change · benefits and unintended effects) is computed from the link's two layers, never stored. |
| **Band item** | A line in the context band or the supporting-activities band (`toc_band_item`). |
| **Pathway** | An ordered route of links from an input to an impact or a failure outcome (`toc_pathway`), kind success or failure, status kept or set aside, with a one-line reason. |
| **Item** | Anything the evidence check tests: a link, an assumption, or an output, outcome or impact box. Inputs boxes are not items (owner, S3). |
| **Item text** | The fixed sentence code builds for an item (spec components § Items). Its hash is the **item hash**. |
| **Item search** | One acquire-only child walk for one item, built on the Options scoping option-search machinery (`runtime/option_search.py`). C2. |
| **Judgement** | One row of `toc_item_evidence`: one item, one document, a stance (supports · supports under conditions · challenges · not about this item), a verified quote, and for boxes any case study and indicator. |
| **Grade** | strong · medium · weak · no evidence found, computed on read from an item's judgements by one function (C4). **Flags:** *evidence against (N)*, *holds under conditions*. **Status:** *checking*, *out of date*. |
| **Origin** | Who made a graph element: `drafted` · `found_in_evidence` · `imported` · `user` · `options_scoping`. |
| **Changed-by-Policy-Atlas flag** | Set when discover or consolidate changes or sets aside something the user made or edited (T1). Stored with the reason and the user's prior version. |
| **Draft walk** | The walk that drafts or imports the graph. **Check walk** | the walk that searches, judges, discovers, consolidates and summarises. C3. |
| **E1, E2, E2b, E6** | The first evals (spec § Evaluation): structure checks; judge on public stance datasets; grades against Consensus and System; rebuilding published theories. |
| **Mantle** | Amazon Bedrock's second endpoint (`bedrock-mantle`), the only Bedrock endpoint with hosted web search, in us-east-1 and us-east-2 only. |
| **OS** · **ES** | Options scoping · Evidence search. |

## Read first

- The ToC spec: [capability.md](../../specs/capabilities/theory-of-change/capability.md),
  [components.md](../../specs/capabilities/theory-of-change/components.md). Both in full.
- [OS components § 0 inherit, § Interface rulings](../../specs/capabilities/options-scoping/components.md),
  [OS trust.md](../../specs/capabilities/options-scoping/trust.md): the reuse and trust rules ToC inherits.
- System contracts: [data-model.md § Links between tasks](../../specs/system/data-model.md),
  [execution-orchestration.md](../../specs/system/execution-orchestration.md) (the `search`
  verb, the open-web seam), [provenance-grounding.md](../../specs/system/provenance-grounding.md)
  (tier 4 reasoning label), [prompting.md](../../specs/system/prompting.md) (every prompt
  surface), [web-api.md](../../specs/system/web-api.md) (additive-only evolution).
- ADRs: [0037](../../adr/0037-options-scoping-task-kind-links-and-baseline-gate.md) (task kind,
  links, registry: the pattern this follows), [0039](../../adr/0039-options-scoping-longlist-option-searches-and-option-records.md)
  (option searches as child walks), [0041](../../adr/0041-bedrock-inference-route-and-model-route-file.md)
  (model route file).
- Knowledge notes: `capability-registry-one-plan-reader.md`, `task-link-grants-no-read.md`,
  `alembic-roundtrip-explicit-revisions.md`, `new-table-bumps-count-asserts.md`,
  `structured-output-prompts-pin-key-vocabulary.md`.
- Precedent contract: [044](../044-scoping-shell-baseline/contract.md) (a new task kind end to end).

## Decisions

Owner rulings are quoted in the spec § Rulings. One more ruling came after the spec rounds:

- **T1** (owner, 2026-10-23): "we should still allow Policy Atlas to consolidate or edit the
  ToCs that users touched, just it should be flagged." Applied in the spec § Editing during the
  check.

The decisions below are the contract's own. They fix what the spec leaves to the build. Each is
open to the owner at the contract 🛑.

- **C1. One theory per task; edits in place.** The graph tables are keyed by `task_id`. There
  are no graph versions: every change writes an event to `event_log` (History). Undo of a
  consolidate step replays the before-state carried in that step's event (C9).
- **C2. Item searches reuse the option-search child walk.** The child-walk machinery in
  `runtime/option_search.py` (intent record with `purpose='targeted'`, `acquire_only`,
  `walk_pool.option_search_pool()`, join, abandon) is today typed to `OptionDesign` and
  `ScopingPlan`. The plan decides between generalising it to take an intent text and a context
  reference, or a thin ToC sibling over the same pool and join; either way no second pool, join
  or abandon path is written. The intent record's `context` names the item (`toc_item_kind`,
  `toc_item_id`, `item_hash`).
- **C3. Two walks.** A **draft walk** (draft or import) and a **check walk** (item searches →
  join → screen → classify → appraise → judge → discover → consolidate → summarise →
  follow-up check). The check walk starts automatically when the draft walk succeeds (R5). A
  re-check is a check walk restricted to named items, without discover and consolidate. The
  main ToC intent record uses a new `purpose` value, `toc`.
- **C4. The grade is one pure function, computed on read.** `grade(judgements, appraisals) ->
  Grade` in `theory_of_change/evidence/grade.py`, with the rule from the spec § Trust rules,
  table-tested. Never stored. Web judgements count toward flags and *weak*, never toward
  *medium* or *strong*. The rule text in the canvas key is generated from the same constants.
- **C5. Judge scope.** Per item: the item search's screened-in documents plus inherited ones,
  reranked against the item text with the existing rerank backend, top *K* = 8. One call per
  item and document. The existing quote matcher (`evidence_search/extract/quote_verify.py`)
  checks every quote against the abstract or the frozen page text; an unverified judgement is
  dropped and counted. At most 80 items per check walk; above that, the check covers the items
  on kept pathways first and says how many were left out.
- **C6. Discover and consolidate.** Discover reads the screened-in documents in batches and
  proposes pathways labelled `found_in_evidence`; their new links are judged against the
  existing pool only. Consolidate runs in two stages (spec § Pipeline 5): aggregate by distinct
  and relevant, then choose by promising and evidence (owner, S5), within 6 success and 3
  failure pathways. It may merge, reword or set aside user-made or user-edited elements, and
  then sets the changed-by-Policy-Atlas flag with the reason and the user's prior version (T1).
- **C7. Web search.** A Responses API call with the hosted `web_search` tool, beside the
  existing `chat.completions.parse` wrapper in `core/openai_client.py`, with the same tracing,
  usage records and call budget. A new `[routes.<name>.web_search]` table in
  `model_routes.toml` holds the address and model: OpenAI on `openai-direct`;
  `https://bedrock-mantle.us-east-1.api.aws/openai/v1` with `openai.gpt-5.6-terra` on
  `bedrock-local` (owner, 2026-10-23: "Send only the web search calls to Bedrock's US
  endpoint"). Each cited URL is fetched once with the existing full-text fetcher
  (`ingest_full_text.py`), and stored as a `source_snapshot` whose metadata names the backend
  `web`, the URL and the retrieval time. Page text enters prompts only through the existing
  untrusted-text rule (`sanitize_prompt_field` in `core/prompt_fields.py`) and inside a fenced
  data block, as the scoping prompts' `_fence_safe` does. Every web call emits the existing `search.executed` governance event.
- **C8. Uploads.** The file travels as base64 in a JSON body (no `python-multipart`), PNG, JPG
  or PDF, at most 10 MB, checked by content type and magic bytes. The backend writes it to a
  new private, encrypted S3 bucket (`RemovalPolicy.RETAIN`, block all public access, TLS only)
  under `tasks/<task_id>/<upload_id>`; reads go through a task-scoped route with the task's
  ordinary read check. PDF pages are rasterised with `pymupdf` (already a dependency), at most
  10 pages. Each upload writes an audit event and a trace span (closes the
  `docs/deferred.md` "Upload audit-event seam" for this surface). Deleting a task deletes its
  objects. Local development uses a directory in place of the bucket, behind one small storage
  protocol.
- **C9. Undo, Restore, Keep mine.** Consolidate writes one event whose payload carries the
  before-state of every row it changed. **Undo** applies it back and writes its own event; it
  is offered until the next edit to an affected row. **Restore** moves one set-aside pathway to
  kept (above the limits is allowed when the user does it). **Keep mine** puts the user's prior
  version back on one flagged element and clears the flag.
- **C10. Editing during the check.** As the spec § Editing during the check states. An edit
  during a running check queues the item; the check walk's last step runs one follow-up pass
  over queued items. Edits never block on the walk: the edit route takes a row lock, not a walk
  lock.
- **C11. A plan change after the draft** offers two choices in the Task Agent thread, as task
  044 did for the baseline: **Redraft** (a new draft walk replaces the graph; the old graph is
  recorded in the History event; user elements are carried over as flagged items where they
  still fit) or **Keep the graph** (the plan changes; the graph does not).
- **C12. Steering.** The ToC lattice is empty: no pause points, and the Task Agent does not ask
  for a steering mode. The check walk reports progress through the existing run events only.
- **C13. Links.** `task_link` gains `source_option_id UUID NULL` with a composite foreign key to
  `option(option_id, task_id)` on `(source_option_id, source_task_id)` (owner: "yes fine"). The
  task-create link rules widen in one place (`api/routers/tasks.py` `_write_task_links`): a ToC
  target accepts exactly one Options scoping source, which must name `source_option_id` of an
  option that is not merged. Every other existing rule stands. No link after creation.
- **C14. Shared documents.** The ToC `inherit` direction gives the ToC task one
  `task_source_snapshot` row per option document, pointing at the same `source_snapshot`
  (shared, not copied; owner, 2026-10-23), runs before the item searches so `acquire`'s
  per-task duplicate check sees them, and reads classification and appraisal from the scoping
  task's pinned run through the existing resolver (`labels_for_snapshots` in
  `options_scoping/labels.py`). The cross-task duplicate gap stays as it is
  (spec § Connections to other tasks).
- **C15. Branch and merge.** A feature branch `feat/theory-of-change` from `dev` after PR #84
  merges. Each deliverable lands as a PR into it. It merges to `dev` when deliverables 1–5
  pass review and the owner says so; until then production cannot create a ToC task. The
  backend refuses `capability = 'theory_of_change'` on task create unless the setting
  `POLICY_ATLAS_THEORY_OF_CHANGE=1` is on, so a merge to `dev` exposes nothing by API alone.
- **C16. New dependencies** (owner, R12): `@xyflow/react` (canvas, MIT), `html-to-image`
  pinned to `1.11.11` (PNG and SVG export), `python-pptx` (PowerPoint). Nothing else.

## ADR scope

ADR 0042, "A third task kind: theory of change", records C1–C16 that are consequential: the
task kind and its walks (C3), the grade rule as a deliberate difference from Options scoping's
no-banding rule (C4), web search opening the open-web seam, with the Mantle US endpoint for
the Bedrock route (C7), the uploads bucket (C8), flagged changes to user work (T1, C6), the
`source_option_id` link (C13), the server-side capability setting (C15), and the rollback.

## Surface map

| Surface | What changes | File(s) | Must not change |
|---|---|---|---|
| New task page | "Theory of change" available behind the build flag | `frontend/src/lib/capabilities.ts` | ES and OS entries |
| Capability registry | `THEORY_OF_CHANGE` entry, `TocPlan` in `AnyPlan` | `runtime/capability_registry.py` | ES and OS profiles, compose and lattice |
| Plan and Task Agent | `TocPlan`, `compose_toc`, profile, prompt | `runtime/toc_plan.py`, `runtime/task_agent_toc*.py` (new) | `planner_v11`, `task_agent_scoping_v5` text and hashes |
| Harness | ToC steps as data, like `_SCOPING_STEPS` | `runtime/harness.py` | ES and OS graphs and edges |
| Child walks | Item searches (C2) | `runtime/option_search.py` or a sibling | OS option-search behaviour and tests |
| Inherit | The option direction (C14) | `runtime/inherit.py` | ES and OS directions |
| Web search | Responses call, route table, web backend | `core/openai_client.py`, `core/model_routes.py`, `model_routes.toml`, `evidence_search/sourcing/search_live.py` | Every existing step's model on both routes |
| Links | `source_option_id`, the widened rule | `core/schema.py`, `api/routers/tasks.py`, `api/contract/tasks.py` | Existing link rules for ES and OS targets |
| ToC package | Graph, draft, import, evidence, discover, consolidate, stress, summary, export | `theory_of_change/` (new) | — |
| API | `api/routers/toc.py` (new); create accepts the new kind | `api/app.py`, `frontend/openapi.json` via `make openapi-sync` | Existing routes: additive only |
| Result tab | Canvas, bands, cards, key, detail panel, list view, original view, stress-test pane | `frontend/src/views/toc/` (new), `views/taskResult.ts` | ES report, OS longlist |
| Option page | "Design a theory of change" and the back-list | `frontend/src/views/longlist/` option page | Every other OS surface |
| Infrastructure | Uploads bucket and the backend's grant | `infra/infra/policy_atlas_stack.py` | Other buckets, network, database |
| Evals | E1, E2, E2b, E6 harnesses | `scripts/evals/toc/` (new) | Existing eval suites |

## Spec changes

Applied with this contract, after approval, logged in `docs/specs/log.md`:

1. ToC components § Data: the walk names (C3), the `toc` purpose, the flag columns (T1), no
   undo table (C9).
2. ToC capability § Product surface: the server-side capability setting (C15) beside the build
   flag; the plan-change choice (C11); the empty lattice (C12).
3. OS capability § Artefact & scope: "start a theory of change" moves from ⏸ to the one
   button this contract builds, citing the owner's ruling (spec § Connections to other tasks).
4. `docs/specs/system/execution-orchestration.md`: the open-web backend is no longer deferred
   for the ToC check walk; the seam stays deferred for every other capability.
5. `docs/specs/product.md` in/out table: Theory of change moves from out of scope to in scope.

## Scope / Out of scope

- **In:** deliverables 1–9; ADR 0042; the spec changes; E1, E2 (with E2b on a fixed, cached
  claim set) and E6 built and run once.
- **Out:** removing the build flag or the server setting; E3, E4, E5, E7, E8 (planned, later);
  full-text reading of evidence and the "check in depth" action; links to ES tasks or links
  after creation; reusing ES findings; a Miro API integration (draw.io covers Miro); Google
  Slides API; anchored comments on boxes; real-time collaboration; an overall theory score;
  complexity features (feedback loops, system maps); the cross-task duplicate fix; any change
  to ES or OS behaviour beyond the named touch points.

## Constraints & approval gates

Every one of these is an approval gate, and this contract asks for all of them at once:

- **Schema.** One Alembic revision: widen `ck_task_capability`, `ck_capr_capability`,
  `ck_scope_purpose` (`toc`), `ck_conversation_kind` (`stress_test`); add
  `task_link.source_option_id` and its foreign key; add `toc_box`, `toc_link`,
  `toc_assumption`, `toc_band_item`, `toc_pathway`, `toc_item_evidence`, `toc_upload`, with the
  changed-by-Policy-Atlas columns (flag, reason, prior version as JSONB) on boxes, links,
  assumptions and pathways. Reversible (§ Risk tier).
- **Runtime egress.** New: web search (OpenAI, or Mantle in us-east-1 on the Bedrock route);
  page fetches of cited URLs; vision calls carrying user-uploaded files. Existing: OpenAlex,
  Overton, model calls.
- **Dependencies.** C16 only.
- **Infrastructure / production config.** The uploads bucket, the backend task role's grant on
  it, one environment value naming it; `POLICY_ATLAS_THEORY_OF_CHANGE` off in both
  environments.
- **Public interfaces.** New routes under `/api/v1/tasks/{task_id}/toc/**`; `TaskCreate`
  accepts the new capability and `source_option_id` on a link. Additive only.
- **Prompts.** New, lead-written, hash-pinned: `task_agent_toc_v1`, `toc_draft_v1`,
  `toc_import_v1`, `toc_item_judge_v1`, `toc_discover_v1`, `toc_consolidate_v1`,
  `toc_summary_v1`, `toc_stress_v1`, the item-search guidance. No existing prompt changes.
- **Generated files.** `frontend/openapi.json` and `types.ts` only through `make openapi-sync`.

## Public / private boundary

Public-safe: code, specs, ADR, eval harnesses, aggregate eval numbers, the labels we write for
E6. Private: uploaded files (bucket only, never the repo), fetched web page text and source
text, Langfuse traces, any Consensus API output beyond aggregate agreement, the E6 report PDFs
and figures (cite by URL; do not commit them). Public datasets keep their licences: SciFact is
CC-BY 4.0; each other dataset's licence is checked and recorded in `verification.md` before
use.

## Model route

All through `model_routes.toml` (ADR 0041). New steps: `task_agent_toc`, `toc_draft`,
`toc_import`, `toc_consolidate` on **frontier**; `toc_item_judge`, `toc_discover`,
`toc_summary`, `toc_stress` on **standard**; `toc_web_search` through the new `web_search`
table (C7). Item queries use the existing `search_queries` step. Every prompt surface is
prompt-bearing and **lead-only** (AGENTS.md); each follows `prompting.md` and its refine-replay
loop.

## Disciplines binding this slice

- **Don't flatten status.** Spec markers stay as they are until a ruling moves them.
- **Model only what behaves.** No column, label or flag that changes nothing on screen or in a
  rule. The assumption type is computed, not stored; the grade is computed, not stored.
- **Flag, don't drop.** Unverified quotes are dropped from evidence but counted and shown as a
  count; changes to user work are flagged (T1).
- **Honest absence.** *No evidence found* says what was searched. "Web not searched" appears
  whenever the web leg did not run.
- **Leave seams as seams** in `docs/deferred.md`: full-text depth, ES links, the cross-task
  duplicate gap, Miro API, the later evals.

## Stop conditions

Halt and report when: PR #84 has not merged when the build opens; an approval gate is hit that
this contract does not name; the Mantle endpoint refuses the Bedrock key or identity from our
account (the web leg then ships on `openai-direct` only, and the owner decides); Google Slides
drops PowerPoint connectors (PowerPoint ships, the Slides claim does not); E2 shows the judge
calls challenge evidence "supports" more than one time in five (the owner decides before step
3); a step's work would change ES or OS behaviour beyond the surface map.

## Acceptance checks

- `make verify` green at the exit of every deliverable (okf-validate · test · typecheck · lint
  · build · drift-check · prompt-guard), with intermediate commits on `make verify-fast` as the
  plan marks.
- **Deterministic tests** (backend unless stated), by deliverable:
  1. Migration round-trip (upgrade, downgrade, upgrade); the downgrade refuses while any `task`
     or `capability_run` row carries `theory_of_change`. Registry: `spec_for`, `validate_plan`,
     `compose_plan` and `lattice_for` accept `theory_of_change`; the AST test still bans bare
     plan validation; an ES or OS plan is rejected on a ToC task and the reverse. Create refuses
     the new kind while the server setting is off. The graph validator (the E1 checks): layers
     in order, no orphan boxes, every assumption on a link, at least one failure pathway, every
     pathway a connected route; assumption type computed from layers. Frontend (vitest): the
     canvas renders boxes, links, markers, bands and key from a fixture; the list view; the
     build flag hides the entry.
  2. Item text built deterministically from fixtures; item hash stable. The grade function's
     table test covers every row of the rule, the web cap and both flags. Item searches open
     child walks with the right intent record and join; an unverified quote drops the
     judgement and counts it; *K* and the 80-item cap hold. Detail panel renders the three
     groups (vitest).
  3. Consolidate keeps at most 6 success and 3 failure; a change to a user element sets the flag
     with reason and prior version; Undo restores the before-state exactly; Restore and Keep
     mine behave; discover's links are judged without a new search.
  4. An edit during a check queues the item and the follow-up pass checks it; a changed item
     reads *out of date* and its old judgements stop counting; a deleted item's pending results
     are dropped; every edit writes one event; the plan-change choice (C11) for both branches.
  5. The route table parses on all routes; the Bedrock route sends web calls to the Mantle
     address and nothing else there; pages are stored once with backend `web`; page text reaches every prompt that reads it only through `sanitize_prompt_field` and a
     fence; web judgements never raise a grade
     above *weak*; "web not searched" appears when the leg is off.
  6. `stress_test` conversations: four questions, each tied to an element; the chat route
     refuses edits to the graph from either chat.
  7. Upload: type and size checks (including a renamed non-image), the 10-page PDF cap, the
     storage protocol on a local directory, the task-scoped read check, deletion with the task,
     the audit event. Import of a text fixture keeps the user's words and labels additions.
  8. Exports: CSV columns, JSON round-trip through the graph models, draw.io XML that parses
     and has one vertex per box and one edge per link, a `.pptx` that python-pptx re-opens with
     one connector per link attached to its two boxes.
  9. Create with an OS source requires `source_option_id` of a non-merged option in that task;
     the foreign key holds; the slots are seeded and labelled; option documents get membership
     rows pointing at the same snapshots, before any item search; the per-task duplicate check
     stops a re-store; the newer-run flag appears when the source has a later finished walk; the
     option page lists every ToC started from it.
- **Evals (recorded, not pass/fail, except the stop condition above):** E1 on about 30 drafts
  (pass rate per check); E2 on SciFact, Check-COVID, PubMedQA and the Evidence Inference
  abstract subset with the ablation arm (macro-F1, the challenge-called-support rate); E2b on a
  fixed set of about 50 claims, Consensus calls approved by the owner before the run and cached
  (about $2.50 at $0.05 a call), System only if access is granted; E6 on 20 published
  theories with recall of impacts and outcomes, soft link F1, direction accuracy and run-to-run
  stability over 5 runs.
- **Live check (pinned scope, about 60 minutes in total, split by deliverable):** local app,
  real egress, on `openai-direct`, one topic ("mentoring to keep young care leavers in
  education, employment or training"):
  (1) plan and draft, canvas renders; (2) the check fills grades, one link's panel read against
  its sources; (3) consolidate's summary line and one flagged change, Undo; (4) an edit during
  the check, then its follow-up result; (5) web leg on `openai-direct`, and one web call on
  `bedrock-local` against Mantle; (6) one stress-test round; (7) one image import of a
  published GOV.UK theory figure; (8) every export opened in its target tool (PowerPoint,
  Google Slides, diagrams.net, Miro import); (9) "Design a theory of change" from an existing
  OS task's option page. No full live e2e of ES or OS.

## Verification evidence expected

Command tails per deliverable; the migration round-trip output; the OpenAPI diff (additive);
the prompt-hash diff (new entries only); the eval numbers with their data sources and licences;
live-check notes and screenshots for (1)–(9); the export import results by tool; the spec diffs
with quoted rulings; the `docs/deferred.md` delta; known gaps.

## Risk tier & review focus

**Tier 4.** A migration, a public API, new runtime egress including a US endpoint, user file
uploads, a new S3 bucket and three new dependencies. ADR 0042 with the rollback; human-approved
plan; adversarial review at contract, plan and code (`codex-rescue`, read-only briefs); the
step-7 stack per deliverable PR (contract verifier · `/code-review` · a security lane on uploads,
web egress and the link rule · `/simplify` · human deep review).

**Rollback.** Turn the server setting off (no new ToC tasks). The revision's downgrade refuses
while any `task` or `capability_run` row carries `theory_of_change`; the remedy is an operator
script that hard-deletes those tasks, their walks and their bucket objects, after which the
downgrade drops the seven tables and `task_link.source_option_id` and narrows the four
constraints. The bucket is retained by policy and emptied by the same script; deleting it is a
separate infrastructure change. Deploy the previous image.

**Review focus:** ES and OS behaviour, prompts and hashes unchanged; the grade function is the
only place a grade is decided; no web text reaches a prompt outside the fence; uploads cannot be
read across tasks; a flagged change always keeps the user's prior version; the link rule widens
only for ToC targets; the server setting really blocks creation; no element is lost by Undo.
