# Task contract: 054-toc-integration

One programme contract for the third capability, **Theory of change**, in nine numbered build
steps (owner memory: one contract per programme, numbered steps, no gate per step). It lands a
new task kind whose Result is a Magenta Book canvas: a drafted causal chain, every link graded
against evidence in the background, both where it was tried and here (boxes described, not
graded; § Wireframe review amendments), pathways consolidated,
and a stress-test chat, with import, export and one entry point from Options scoping.

> **Status:** **approved 2026-10-23 · owner** ("approve, let's go"). The contract-stage adversarial
> review ran before approval, at the lead's choice, so the owner approves a reviewed contract:
> ten findings, all adopted (§ Adversarial findings). Contract approved (before planning):
> 2026-10-23 · owner · Plan approved (before implementation): _pending_ · ADR: **0042** (to be written
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
   canvas in the reviewed layout (W1–W3), the reading guide, Detailed information without
   evidence, the build flag. E1 and the
   E6 harness are built here and run once on the draft (spec build order).
2. **Evidence check.** One search per item over OpenAlex and Overton, the reused Evidence
   search spine, the per-document judge, grades and flags, case studies and indicators, the
   detail panel, the Sources tab, the summary with evaluation questions.
3. **Discover and consolidate.** Pathways found in the evidence; merging, setting aside and
   choosing; flagged changes to user work; Restore, Keep mine and Undo. E6 runs again on the
   consolidated theory.
4. **Editing during the check.** Canvas editing, *Edited · check pending*, Keep the evidence,
   the minimal Check again and Search for more (W17), History events, change requests through the Task Agent, the
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
| **Conditions** | What must hold for a link to work in the user's setting, stored on the link (`toc_link.conditions`). They hold the Magenta Book's assumptions; there is no assumption table (W14). |
| **Band item** | A line in the context band or the supporting-activities band (`toc_band_item`). |
| **Pathway** | An ordered route of links from an input to an impact or a failure outcome (`toc_pathway`), kind success or failure, status kept or set aside, with a one-line reason. |
| **Item** | Anything the evidence check tests: a link. Boxes are not items (W4); assumptions are a link's conditions (W14). Each link has two grades, *worked elsewhere* and *holds here*. |
| **Item text** | The fixed sentence code builds for an item (spec components § Items). Its hash is the **item hash**. |
| **Item search** | One acquire-only child walk for one item, built on the Options scoping option-search machinery (`runtime/option_search.py`). C2. |
| **Judgement** | One row of `toc_item_evidence`: one item, one document, a stance (supports · challenges · not about this item), a verified quote, an optional condition on a support, and any case study and indicator the document gives, each tagged with the box it describes (W4). |
| **Grade** | strong · medium · weak · no evidence found, computed on read from an item's judgements by one function (C4). **Flags:** *evidence against (N)*. (Amended 2026-10-26 by the owner during the wireframe review: no *supports under conditions* stance and no *holds under conditions* flag; conditions are covered by assumptions. Schema unchanged: `condition NULL` stays.) **Status:** *checking*, *Edited · check pending*, *evidence kept by you*, *checked: no change* (W17). |
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
- **C2. Item searches use one capability-neutral child search** (A6). The child-walk machinery
  in `runtime/option_search.py` moves into a new `runtime/child_search.py`:
  `ChildSearchRequest(intent: str, context: dict, plan_id, purpose="targeted")` and
  `run_child_search(engine, *, task_id, request, parent_capability_run_id, backends, user_id)
  -> uuid`, plus the existing join, interrupt and abandon functions over the same
  `walk_pool.option_search_pool()`. The child resolves its plan through the capability registry
  by the task's capability (today it validates `ScopingPlan` directly, `option_search.py:211`).
  `run_option_search` becomes a thin caller that passes `design.as_intent()` and the option
  context, so its signature and behaviour stay as they are; the existing OS option-search tests
  are the compatibility check and must pass unchanged. The ToC item search passes the item text
  and `context = {toc_item_kind, toc_item_id, item_hash, acquire_only: true}`. Abandon
  semantics are unchanged: a parent that ends abandons its children.
- **C3. Two walks.** A **draft walk** (draft or import) and a **check walk** (item searches →
  join → screen → classify → appraise → discover → merge → judge → choose → summarise; W16,
  W17). The check walk starts automatically when the draft walk succeeds (R5). A
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
  proposes pathways labelled `found_in_evidence`; their new links get no search and are judged
  with the rest against the existing pool. Consolidate is two steps around the judge (W16, spec
  § Pipeline 5): **merge** by distinct and relevant before judging, then **choose** by promising
  and evidence after grading (owner, S5), within 6 success and 3 failure pathways. It may merge, reword or set aside user-made or user-edited elements, and
  then sets the changed-by-Policy-Atlas flag with the reason and the user's prior version (T1).
- **C7. Web search** (A3, A7). A Responses API call with the hosted `web_search` tool, beside
  the existing `chat.completions.parse` wrapper in `core/openai_client.py`, with the same
  tracing, usage records and call budget.
  - **Route config.** A typed `WebSearchRoute(enabled: bool, base_url: str | None, model: str |
    None, api_key_env: str | None)` parsed from `[routes.<name>.web_search]` in
    `model_routes.toml` by `core/model_routes.py`. Every route must declare the table; a
    missing table fails loud at start-up. `base_url` must be one of two allowed addresses,
    `https://api.openai.com/v1` or `https://bedrock-mantle.us-east-1.api.aws/openai/v1`;
    anything else fails loud. `openai-direct`: enabled, OpenAI's address, the standard model.
    `bedrock-local`: enabled, the Mantle address, `openai.gpt-5.6-terra` (Mantle takes in-region
    names, not `global.` ones), key `AWS_BEARER_TOKEN_BEDROCK` (owner, 2026-10-23: "Send only
    the web search calls to Bedrock's US endpoint"). `bedrock-local-claude`: disabled. No
    fallback: if the web call fails, the leg records the failure and "web not searched"; it
    never retries on another address. Non-web calls keep the route's own `openai_base_url`,
    which a test asserts.
  - **Pages.** Each cited URL is fetched with the existing hardened `LiveDocumentFetcher`
    (`evidence_search/sourcing/fetch_live.py`: private-address blocking, 5 redirect hops, 25 MB
    and 30 s caps), through its `DocumentFetcher` protocol, **not** through the full-text ingest
    pipeline, whose eligibility rules only take stored search results. A new writer
    `evidence_search/sourcing/web_pages.py` turns HTML into text with `trafilatura` (already a
    dependency), caps the text at 200,000 characters, and writes one `source_snapshot`
    (`text_basis = 'full_text'`, metadata `backend = 'web'`, the URL, the retrieval time) plus a
    `task_source_snapshot` with `origin = 'acquired'`. Duplicates are checked by URL inside the
    task. Only http and https URLs are fetched.
  - **Untrusted text.** Page text enters prompts only through `sanitize_prompt_field`
    (`core/prompt_fields.py`) and inside a fenced data block, as the scoping prompts'
    `_fence_safe` does. Quotes are checked against the stored page text. Every web call emits
    the existing `search.executed` governance event.
- **C8. Uploads** (A4, A8). The file travels as base64 in a JSON body (no
  `python-multipart`): PNG, JPG or PDF, at most 10 MB, checked by declared type **and** magic
  bytes. The backend writes it to a new private, encrypted S3 bucket (`RemovalPolicy.RETAIN`,
  block all public access, TLS only) under `tasks/<task_id>/<upload_id>`. PDF pages are
  rasterised with `pymupdf` (already a dependency), at most 10 pages. Each upload writes an
  audit event and a trace span (closes the `docs/deferred.md` "Upload audit-event seam" for this
  surface). Local development uses a directory in place of the bucket, behind one small storage
  protocol.
  - **Lifecycle.** Tasks are archived, never deleted, by the product (`api/lifecycle.py`
    `archive_task`), so uploads stay while their task row exists, archived or not. Objects are
    removed only by the operator script that hard-deletes tasks (§ Risk tier), which deletes
    the object first, records an event, and is safe to run twice. A retention rule for uploads
    is a deferred seam in `docs/deferred.md`.
  - **Access.** Upload bytes and the "Your original" view are **never** on the public read leg:
    authenticated full access only, same rules as editing the task. Served by the backend
    (no presigned URLs) with `Content-Disposition: inline`, `X-Content-Type-Options: nosniff` and
    the stored content type.
- **C9. Undo, Restore, Keep mine.** Consolidate writes one event whose payload carries the
  before-state of every row it changed. **Undo** applies it back row by row with the revision check
  of C10, skips rows the user changed since, says which, and writes its own event. **Restore** moves one set-aside pathway to
  kept (above the limits is allowed when the user does it). **Keep mine** puts the user's prior
  version back on one flagged element and clears the flag.
- **C10. Editing during the check** (A5). Every graph row carries an integer `revision`,
  raised by one on every write.
  - **Edits.** Each edit request carries the revision the client saw; the route locks the row
    (`SELECT … FOR UPDATE`), refuses with 409 `toc_stale_revision` on a mismatch, writes, raises
    the revision and records one event, in one transaction. Edits never wait on a walk.
  - **Judge.** Judgements are insert-only and keyed by item hash, so they never overwrite. A
    judgement for an old hash is kept; it counts while the link is pending or kept (W17). A judgement for a deleted item is
    removed with it by the foreign key's cascade.
  - **Discover.** Insert-only. A proposal that refers to a box deleted meanwhile fails its
    foreign key and is dropped and counted.
  - **Consolidate.** Reads the graph with every row's revision, then applies each change in one
    transaction with `WHERE revision = <observed>`. A row the user changed meanwhile is skipped,
    and the summary line says how many changes were skipped and why. User edits always win.
  - **Undo** uses the same compare-and-apply against the revisions consolidate wrote.
  - **Summary.** Stamped with the time it read the graph; the panel says "the theory changed
    since this summary" when any row is newer.
  - **Follow-up pass.** Removed by W17: an edit flags the link, and the user chooses Check again
    or Keep the evidence.
- **C11. A plan change after the draft** offers two choices in the Task Agent thread, as task
  044 did for the baseline: **Redraft** (a new draft walk replaces the graph; the old graph is
  recorded in the History event; user elements are carried over as flagged items where they
  still fit) or **Keep the graph** (the plan changes; the graph does not).
- **C12. Steering.** The ToC lattice is empty: no pause points, and the Task Agent does not ask
  for a steering mode. The check walk reports progress through the existing run events only.
- **C13. Links** (A2). `task_link` gains `source_option_id UUID NULL` with a composite foreign
  key `fk_task_link_source_option` on `(source_option_id, source_task_id)` to
  `option(option_id, task_id)`, MATCH SIMPLE (owner: "yes fine"). The create request keeps
  `from_task_ids` as it is for ES and OS, and gains one optional field,
  `from_option: {source_task_id: UUID, source_option_id: UUID} | null`. Rules: `from_option`
  is accepted only with `capability = 'theory_of_change'` (else 422 `from_option_capability`);
  a ToC create takes `from_option` or nothing, never `from_task_ids` (422
  `toc_links_option_only`); the source must be an OS task that passes the existing four checks
  in `_write_task_links` (readable, same project, finished walk); the option must belong to it
  and not be merged (409 `link_option_invalid`). `TaskLinkOut` gains `source_option_id`. No
  link after creation.
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
- **C17. Public read** (A8). The graph, grades, evidence, pathways and summary follow the
  existing public read leg exactly as the Result and Sources tabs do. Uploads and the original
  view are authenticated only (C8). Tests cover anonymous, same-organisation, owner and
  cross-organisation access for each new route.

## ADR scope

ADR 0042, "A third task kind: theory of change", records the consequential decisions among C1–C17: the
task kind and its walks (C3), the grade rule as a deliberate difference from Options scoping's
no-banding rule (C4), web search opening the open-web seam, with the Mantle US endpoint for
the Bedrock route (C7), the uploads bucket (C8), flagged changes to user work (T1, C6), the
`source_option_id` link (C13), the server-side capability setting (C15), and the rollback.

## Schema

One Alembic revision (A1). Every new table follows the repo's cross-task guard: a
`UNIQUE (<id>, task_id)` and composite foreign keys that include `task_id`, so no row can point
into another task. Every graph table has `created_at`, `updated_at` and `revision INTEGER NOT
NULL DEFAULT 1` (C10). "Flag columns" means `pa_changed BOOLEAN NOT NULL DEFAULT false`,
`pa_change_reason TEXT NULL`, `prior_version JSONB NULL` (T1) and `user_edited BOOLEAN NOT NULL
DEFAULT false`. `origin` is checked against `drafted · found_in_evidence · imported · user ·
options_scoping`.

| Table | Columns (besides the common ones) | Keys and checks |
|---|---|---|
| `toc_box` | `box_id`, `task_id`, `layer`, `text`, `dosage NULL`, `result_criteria JSONB`, `indicator NULL`, `description NULL` (W7), `origin`, flag columns, `position JSONB NULL` | PK `box_id`; `uq_toc_box_id_task`; `ck_toc_box_layer` (`input · output · outcome · impact · failure_outcome`); FK `task_id` → `task` |
| `toc_link` | `link_id`, `task_id`, `source_box_id`, `target_box_id`, `if_text`, `for_text`, `then_text`, `because_text`, `conditions JSONB` (W14), `sentence NULL` (W8), `elsewhere_sentence NULL`, `here_sentence NULL` (W7), `critical BOOL DEFAULT false`, `origin`, flag columns | PK; `uq_toc_link_id_task`; partial unique index: at most one `critical` per task; `fk_toc_link_source` and `fk_toc_link_target` on `(box_id, task_id)` ON DELETE CASCADE; `ck_toc_link_distinct`; unique `(task_id, source_box_id, target_box_id)` |
| `toc_band_item` | `item_id`, `task_id`, `band`, `text`, `sort_order`, `origin` | PK; `ck_toc_band` (`context · supporting`) |
| `toc_pathway` | `pathway_id`, `task_id`, `kind`, `status`, `reason`, `label`, `origin`, flag columns | PK; `uq_toc_pathway_id_task`; `ck_toc_pathway_kind` (`success · failure`); `ck_toc_pathway_status` (`kept · set_aside`) |
| `toc_pathway_link` | `pathway_id`, `task_id`, `position`, `link_id` | PK `(pathway_id, position)`; FKs on `(pathway_id, task_id)` and `(link_id, task_id)` ON DELETE CASCADE. A join table, not JSONB, so a deleted link cannot leave a dangling member. A pathway with a gap after a deletion reads *broken*; the canvas shows it and the graph validator reports it. |
| `toc_item_evidence` | `evidence_id`, `task_id`, `link_id`, `case_box_id NULL` (the box a case study or indicator describes, W4), `task_source_snapshot_id`, `capability_run_id`, `stance_elsewhere`, `quote_elsewhere NULL`, `stance_here`, `quote_here NULL`, `condition NULL`, `case_study JSONB NULL`, `indicator NULL`, `item_hash` | PK; composite FK `(link_id, task_id)` → `uq_toc_link_id_task` ON DELETE CASCADE; composite FK `(case_box_id, task_id)` → `uq_toc_box_id_task` ON DELETE SET NULL; FK `(task_source_snapshot_id, task_id)` → `uq_tss_id_task`; FK `(capability_run_id, task_id)` → `uq_capr_id_task`; `ck_toc_evidence_stances` (each `supports · challenges · not_about`, W6, W14); a quote is required when its stance is not `not_about`; unique `(link_id, task_source_snapshot_id, item_hash)` |
| `toc_upload` | `upload_id`, `task_id`, `object_key`, `file_name`, `content_type`, `size_bytes`, `sha256`, `uploaded_by`, `uploaded_at` | PK; `ck_toc_upload_type` (`image/png · image/jpeg · application/pdf`); `ck_toc_upload_size` (at most 10 MB) |

Changes to existing tables: `ck_task_capability` and `ck_capr_capability` gain
`theory_of_change`; `ck_scope_purpose` gains `toc`; `ck_conversation_kind` gains `stress_test`;
`task_link.source_option_id` with `fk_task_link_source_option` (C13).

**Downgrade order:** refuse while any `task` or `capability_run` row carries
`theory_of_change`; then drop `toc_item_evidence`, `toc_pathway_link`, `toc_pathway`,
`toc_link`, `toc_box`, `toc_band_item`, `toc_upload`; drop
`fk_task_link_source_option` and its column; narrow the four constraints.

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

## Wireframe review amendments (2026-10-26)

The owner reviewed `wireframes.html` (versions 1–9) and ruled as below. Each ruling is applied in
the spec and logged in `docs/specs/log.md`; this section overrides any older wording in this
contract and in `plan.md`, which is re-touched before plan approval.

- **W1 Visual rules.** One font, the app's own, in the app's sizes; colour means evidence grade
  only; blue means actions and review; no counts, badges or captions on the canvas; detail on
  hover, on click, and in Detailed information. Header: title plus *About this theory* and *What
  the evidence says*. Context and supporting activities move off the canvas into the header and
  the reading guide (`toc_band_item` stays; only its display moves).
- **W2 Canvas.** Rounded neutral boxes; connections as smooth curves coloured by grade, dashed for
  weak and none; the critical connection marked by one navy dot (W14); failure
  pathways below *If it goes wrong*; one pathway menu; *How to read this* opens the guide.
- **W3 Detailed information** replaces the list view and the pathways list: the report's expand
  and collapse sections, one per pathway, then *Considered and set aside* and *Questions for an
  evaluation*; *Download as PDF* on the right. This section is the PDF report (a new export
  beside C16's six).
- **W4 Boxes are described, not graded.** Only links are searched and graded (W14).
  Boxes show result criteria, case studies and indicators, pulled from the documents judged for
  their links (inputs: where put in place and what it took). Schema: `toc_item_evidence` drops
  `box_id`, adds `case_box_id`; one row per link (W14). Fewer item searches.
- **W5 (superseded by W14) A link and its assumption answer different questions** (did the change follow where it
  was tried; does the condition hold), each with its own judge question and grade; they never
  share judgements; the panel shows the link's evidence first, then its assumption.
- **W6 No conditions stance or flag.** Stances: supports, challenges, not about. A support may
  record a condition; uncovered conditions go to consolidate, which adds them to the link's conditions (W14).
- **W7 Evidence sentences.** Summarise writes two sentences per link (worked elsewhere, holds here; W14), and a
  two-sentence description per box, each citing only that item's judged documents or case studies;
  code checks every citation. Storage: a nullable
  `elsewhere_sentence` and `here_sentence` on `toc_link`, and `description` on `toc_box` (W14) (lead recommendation, for the owner
  at plan approval).
- **W8 Connection sentence.** Each link has one sentence naming both boxes and the mechanism,
  written by the draft with the link's fields; code falls back to "<source> leads to <target>,
  because <because>". It is redrafted when either box's text changes.
- **W9 Plan panel.** The navy plan panel of the other task types, with the uploaded original
  inside it under *Starting point*.
- **W10 Naming.** "Critical connection · test this first" replaces "load-bearing" in the product (W14).
- **W11 (superseded by W14) Assumptions are about here.** A link's evidence answers "did it work elsewhere"; an
  assumption's answers "will this condition hold here" (population, place, now), with the item
  text and judge question saying so. An assumption never restates its link's mechanism; some links
  have none. E1 adds a check for restatement (text close to the link's *because*, or the same
  documents). A document never gives the same quote to a link and its assumption.
- **W12 Journey (spec § Rulings J1–J9).** The Task Agent asks at most two questions before
  drafting; the draft posts a sidebar message; the run notification fires when the check ends;
  the Task Agent then lists each consolidate change with its own **Undo** and **Undo all**
  (amends C9: the stored before-state is applied per row as well as for the whole step) and always
  suggests a stress test. Deliverable 9 (design from an option) may ship after a standalone
  release if it would disturb Options scoping; the owner prefers it in.
- **W14 No separate assumptions** (owner, later on 2026-10-26: "the evidence for each connection is
  in fact the Assumption"). Supersedes W2's assumption circles, W5, W10's "critical assumption"
  and W11. Every link answers two questions, *worked elsewhere* and *holds here* (transferability:
  do its conditions hold for this population and place, now; Cartwright and Hardie 2012). One
  judge call per link and document returns a stance and quote for each. The canvas colours a link
  by the lower grade; the critical connection carries one navy dot. Detailed information shows
  a link as three paragraphs (sentence, worked elsewhere, holds here) and never repeats a finding:
  a shared document is listed once, the *holds here* sentence refers back to it, and the two
  paragraphs merge when every document answers both the same way. Schema: no `toc_assumption`;
  `toc_link.unless_text` becomes `conditions JSONB`, plus `critical`; `toc_item_evidence` is per
  link with two stances. Seven tables, not eight.
- **W15 Robust modelling** (owner, 2026-10-26). For a "Modelling & Simulation" document only, the
  judge returns `robust_model` (built on or calibrated against outcome data, with sensitivity
  analysis, or validated). The grade function (C4) treats a robust model as score 3: it can
  support *medium*, never *strong*. The shared `appraise` rubric is unchanged. Schema:
  `toc_item_evidence.robust_model BOOL NULL`. The grade table test gains rows for it.
- **W16 Order of the check** (owner, 2026-10-26: "first elucidate missing pathways, consolidate
  them and then judge them all together"). The `check` chain is `screen_abstract` → `classify` →
  `appraise` → `toc_discover` → `toc_merge` → `toc_judge` → `toc_choose` → `toc_summarise`.
  Consolidate splits into `toc_merge` (needs no evidence) and `toc_choose` (needs grades); each
  writes its own event with the before-state for Undo (W12). Prompt list: `toc_consolidate_v1`
  becomes `toc_merge_v1` and `toc_choose_v1`.
- **W17 Edits flag; the user decides** (owner, 2026-10-26). An edit to a link, or to a box at
  either end, marks the link *Edited · check pending*; its evidence and grades stay, labelled for
  the previous wording. The user picks **Keep the evidence** or **Check again**. Check again is
  minimal: a same-meaning call first (no change → *Checked: no change*); if the claim changed,
  only the documents already found are re-judged, with no new search; with fewer than two left,
  **Search for more** is offered. Replaces C10's derived follow-up pass and C3's follow-up step;
  the plan's `run_toc_sequence` driver loses its automatic re-check hop (draft → check only), and
  a re-check is a user-started walk. Schema: `toc_link.counted_hash` (the wording whose
  judgements count) and `kept_hash NULL` with `kept_by` (`user · check`); the state is computed:
  checked when the text hash equals `counted_hash`, kept when it equals `kept_hash`, else pending.
  New step `toc_same_meaning` (one standard-tier call, prompt `toc_same_meaning_v1`). Where it
  shows (spec § Output structure): a blue dot on the link and the edited box; a block at the top
  of the link's panel with old and new wording, Check again, Keep the evidence, and the grades
  marked *for the previous wording*; the same label and buttons in Detailed information; a Task
  Agent message with Check all and Keep all. Frontend tests cover each of the four.
- **W13 Connection sentence storage.** W8's sentence is a nullable `sentence` column on
  `toc_link`, beside W7's `evidence_sentence`.

## Adversarial findings (contract stage, 2026-10-23)

Reviewer: Codex (`codex-rescue`, read-only brief), one pass over the contract and rubric against
the spec and the code, before the owner's approval. Ten findings; all adopted.

| # | Severity | Finding | Adopted remedy |
|---|---|---|---|
| A1 | Blocker | The schema named tables but no keys, cross-task guards, cascades or downgrade order. | § Schema. |
| A2 | Blocker | The create request has only `from_task_ids`; there was no shape for naming an option. | C13: a separate `from_option` field, its rules and error codes. |
| A3 | Blocker | The full-text ingest pipeline only takes stored search results, so it cannot fetch cited web pages. | C7: reuse the hardened `LiveDocumentFetcher` through its protocol, plus a new page writer. |
| A4 | Blocker | Tasks are archived, never deleted, so "delete uploads with the task" had no trigger. | C8: uploads live as long as the task row; only the operator script removes them; retention deferred. |
| A5 | Blocker | Nothing stopped a background step from overwriting a newer user edit. | C10: row revisions, compare-and-apply for every writer, a derived follow-up pass, race tests. |
| A6 | Blocker | Whether to generalise option search or write a sibling was left to the plan. | C2: one capability-neutral child search; the OS tests as the compatibility check. |
| A7 | Should fix | The web search route table had no typed shape, address allow-list or failure rule. | C7: `WebSearchRoute`, two allowed addresses, no fallback. |
| A8 | Should fix | Public access to new routes, especially uploads, was unstated. | C17 and C8 § Access. |
| A9 | Should fix | Google Slides was both a requirement and a possible non-claim. | Live check (8) and rubric 8 made conditional. |
| A10 | Should fix | The spec runs E6 at step 1; the contract ran it at step 3. | E6 built and run at deliverable 1, and again at 3. |

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
  `toc_band_item`, `toc_pathway`, `toc_pathway_link`, `toc_item_evidence`,
  `toc_upload`, with the
  changed-by-Policy-Atlas columns (flag, reason, prior version as JSONB) on boxes, links
  and pathways, and `toc_pathway_link`. Exactly § Schema. Reversible (§ Risk tier).
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
  rule. The two grades are computed, not stored.
- **Flag, don't drop.** Unverified quotes are dropped from evidence but counted and shown as a
  count; changes to user work are flagged (T1).
- **Honest absence.** *No evidence found* says what was searched. "Web not searched" appears
  whenever the web leg did not run.
- **Leave seams as seams** in `docs/deferred.md`: full-text depth, ES links, the cross-task
  duplicate gap, Miro API, the later evals, an upload retention rule.

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
     in order, no orphan boxes, every link with at least one condition, at least one failure pathway,
     every pathway a connected route. Frontend (vitest): the
     canvas renders neutral boxes, connections coloured by the lower of their two grades, and the critical-connection dot, from a fixture; the
     reading guide opens and closes; Detailed information renders and expands; the build flag
     hides the entry.
  2. OS option-search tests pass unchanged on the moved child-search code (C2). Item text built deterministically from fixtures; item hash stable. The grade function's
     table test covers every row of the rule, the web cap and the evidence-against flag. Item searches open
     child walks with the right intent record and join; an unverified quote drops the
     judgement and counts it; *K* and the 80-item cap hold. Detail panel renders *worked elsewhere* and *holds here*, each with its two
     groups; a document shared by both is listed once; each evidence sentence cites only its own
     link's judged documents (W7) (vitest).
  3. Consolidate keeps at most 6 success and 3 failure; a change to a user element sets the flag
     with reason and prior version; Undo restores the before-state exactly; Restore and Keep
     mine behave; discover's links are judged without a new search.
  4. Race tests: an edit racing the judge, discover, consolidate and Undo each leaves the
     user's edit in place and the skipped change reported; a stale edit gets 409
     `toc_stale_revision`; an edited link reads *Edited · check pending* and keeps its evidence; Keep the evidence and a
     no-change Check again both leave its judgements counting; a meaning change re-judges only the
     documents already found (W17); a deleted item's pending results
     are dropped; every edit writes one event; the plan-change choice (C11) for both branches.
  5. `WebSearchRoute` parsing: a missing table, an address outside the two allowed, and a
     disabled route each behave as C7 states; non-web calls keep the route's own address; the
     route table parses on all routes; the Bedrock route sends web calls to the Mantle
     address and nothing else there; pages are stored once with backend `web`; page text reaches every prompt that reads it only through `sanitize_prompt_field` and a
     fence; web judgements never raise a grade
     above *weak*; "web not searched" appears when the leg is off.
  6. `stress_test` conversations: four questions, each tied to an element; the chat route
     refuses edits to the graph from either chat.
  7. Upload: type and size checks (including a renamed non-image), the 10-page PDF cap, the
     storage protocol on a local directory, the audit event; access for anonymous, same-
     organisation, owner and cross-organisation callers on every new route (C17), with the
     upload routes refusing the public leg; the response headers of C8. Import of a text fixture keeps the user's words and labels additions.
  8. Exports: CSV columns, JSON round-trip through the graph models, draw.io XML that parses
     and has one vertex per box and one edge per link, a `.pptx` that python-pptx re-opens with
     one connector per link attached to its two boxes.
  9. `from_option` on a non-ToC create is 422; a ToC create with `from_task_ids` is 422; an
     option from another task or a merged option is 409; ES and OS create requests behave as
     before;
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
  the check, then Keep the evidence on one link and Check again on another; (5) web leg on `openai-direct`, and one web call on
  `bedrock-local` against Mantle; (6) one stress-test round; (7) one image import of a
  published GOV.UK theory figure; (8) every export opened in its target tool (PowerPoint,
  diagrams.net, Miro import), and the PowerPoint file opened in Google Slides: if the arrows stay
  attached, Slides is a supported claim; if not, the owner rules and Slides is listed as a
  non-claim in `docs/deferred.md`; (9) "Design a theory of change" from an existing
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
