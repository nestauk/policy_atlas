---
type: Capability spec
title: Theory of change — component skeleton
description: The ToC components, which ones are Evidence search or Options scoping components reused as they are, the new ones and why, the web search seam, the data, the model steps, and the build order.
tags: [capability, theory-of-change, components, draft]
timestamp: 2026-10-23
---

# Theory of change — component skeleton

**Status: draft (task 054).** Product intent and rulings are in [capability.md](capability.md).
This file says how the capability sits on the existing infrastructure. Python paths are under
`backend/src/policy_atlas/` (the top-level `src/policy_atlas/` holds only stale `__pycache__`
folders).

**Reuse rule** (from [Options scoping components](../options-scoping/components.md)). Each
component is **reused** (an existing component, maybe with new parameters), **modified** (an
existing engine with new input or output) or **new**. Each "new" has a reason.

## Skeleton

```
[0 inherit, from an option] ─▶ 1 plan ══approve══▶ 2 draft (or 2b import) ─▶
   item searches (child walks, acquire only; one per link;
                  OpenAlex · Overton · web) ─▶ join
   ─▶ 3 screen ─▶ 4 classify ─▶ 5 appraise ─▶ 7 discover ─▶ 8 merge ─▶ 6 judge ─▶ 9 choose ─▶ 10 summarise

check again   = same-meaning call ─▶ 6 judge on the documents already judged for those links ─▶ 10
search more   = item searches for the named links ─▶ 3 ─▶ 4 ─▶ 5 ─▶ 6 ─▶ 10 (those links only)
edits         = flag links *Edited · check pending*; nothing reruns on its own
chats         = stress test · discuss; no walk
export        = read endpoints and frontend rendering; no walk
```

The contract for task 054 (`docs/tasks/054-toc-integration/contract.md`, C3 and C19) is the
build-level word on the chains and their step names.

## Components

| # | Component | Origin | What ToC uses it for | Realisation |
|---|---|---|---|---|
| 0 | inherit | **modified**: shared by ES and OS; gains one direction, from an OS option | Seeds the plan slots from the option and the scoping plan; gives the ToC task a membership row for each of the option's documents (the document itself is shared, not copied), flagged *inherited* and re-screened, with classification and appraisal read from the scoping run. Runs **before** the item searches, so `acquire` does not store those documents again (capability.md § Connections to other tasks). | procedure |
| 1 | plan | **modified**: the Task Agent profile pattern with ToC slots | The plan conversation and `TocPlan` (capability.md § Plan slots). | agent, lead-authored prompt |
| 2 | draft | **new**: nothing in the repo writes a causal graph | Candidate success and failure pathways through Inputs, Outputs, Outcomes and Impact; links with mechanisms and conditions; context; supporting activities; result criteria and indicators; the critical connection. Code then checks the graph (the E1 checks). | one call (judgment model) + code checks |
| 2b | import | **new**: no vision call exists | Reads pasted text, an image or a PDF of an existing theory into the same graph shape, keeping the user's words and labelling what it adds. The file is stored in S3 (§ Uploads). PDF pages become images with `pymupdf` (already a dependency) and go through the existing `chat.completions.parse` path as image parts. | one vision call + the same code checks |
| — | item search | **reused**: the option-search child walk (`runtime/option_search.py`) | One acquire-only walk per item (§ Items). Intent = the item text. The search guidance asks for queries on the step and on each of its conditions that would find support **and** challenge. 🟡 At most 80 links per check. | procedure |
| — | web leg | **new backend** behind the existing `search` verb | OpenAI's web search tool (§ Web search). | procedure |
| 3 | screen | **reused**, unchanged | Title-and-abstract screen once over the joined pool; intent = the theory. Web pages are screened on their title and opening text. | per-doc fan-out |
| 4 | classify | **reused** | Evidence type per document. Non-evidence never counts toward a grade. | per-doc fan-out |
| 5 | appraise | **reused** | Appraisal score per document under the existing rubric (1 to 5). Feeds the grade. | code |
| 6 | judge | **new**: nothing judges a document against one causal claim | Per link: the screened-in documents its own search found plus inherited ones (a link with no search of its own, from discover or Search for more, uses the whole screened-in pool), reranked against the item with the existing rerank backend, top *K* kept (🟡 *K* = 8). One call per link and document returns two stances, each *supports* · *challenges* · *not about this*, with its own quote: one for *worked elsewhere* (did the change follow where it was tried) and one for *holds here* (does it work, or do its conditions hold, for the plan's population and place); a support may record a condition; for a modelling study, the call also says whether it is robust (capability § Trust rules). For a link, the same call also returns any **case study** (programme, place) and any **indicator** the document gives for the link's source or target box; for an input source box, the case study records where it was put in place and what it took. The existing quote verifier checks each quote; unverified items are dropped. | per-pair fan-out + quote check |
| — | grade | **new**, code only | Grade, flags and status per item, computed on read from its evidence rows (capability.md § Trust rules). Not stored, so it cannot drift. One function, so the rule can be tuned from the evals. | code |
| 7 | discover | **new**: the OS intervention profile finds interventions, not mechanisms or failure modes | Batched calls over the screened-in abstracts and pages: mechanisms, outcomes and failure modes the graph does not have, each with its document and quote. They become candidate pathways labelled *found in the evidence*; their links get no search and are judged with the rest. Insert-only. | batched calls |
| 8 | merge | **new**: nothing in the repo selects among causal routes | Before judging. Merges pathways by *distinct* (shared mechanism) and sets aside by *relevant* (does not reach the intended change for the plan's population and place). A one-line reason per pathway; flags changes to user work (T1); the before-state goes in its event. | one call + code checks |
| 9 | choose | **new** | After grading, only above the limits (6 success, 3 failure): keeps by *promising* and *evidence* (grade counts per pathway). Adds conditions that supports recorded and a link does not name. Re-picks the critical connection. Same reasons, flags and event. | one call + code checks |
| 10 | summarise | **modified**: a small template call, not the full ES synthesise | The header paragraphs, the evaluation questions, two evidence sentences per link (worked elsewhere, holds here, without repeating a finding) and a two-sentence description per box, from the graph, the grades and the judged documents; each sentence cites only its own item's documents (capability § Trust rules). Sentences about evidence cite evidence items; the rest is labelled reasoning. 🟡 ES `synthesise` grounded blocks or one call with citation checks: a contract decision. | one call + citation check |
| — | stress test | **new**: a chat kind with its own prompt | Four questions, one at a time, each tied to a box or link. Conversation only. | chat turns |
| — | discuss | **reused**: the existing chat and grounded-answer path | The graph and its evidence enter the chat context. | chat turns |
| — | export | **new**, small | PNG and SVG from the canvas in the browser (`html-to-image`). CSV references, JSON graph, draw.io XML (standard library) and PowerPoint (`python-pptx`) from backend read endpoints. | code |

**Not reused, on purpose:** the ES deep chain (ingest, select, extract, group, full synthesise),
because this task reads abstracts only; the OS longlist, constrain, theme and shortlist, which
work at option grain; the prototype's judge-then-filter double pass and score clamps, which a
single judge, a verified quote and a fixed grade rule replace.

## Items

🟡 An **item** is something the evidence check tests: a link. Boxes are not items (owner,
2026-10-26). Code builds the item text, so the same graph always gives the same text:

- **Item text:** the link's sentence, "If <if>, for <for>, then <then>, because <because>", the
  source and target box texts, and the link's conditions, with the question "did this work where
  it was tried, and does it hold for <population> in <where> now?".
- **Item hash:** sha256 over the normalised link fields, both box texts and the conditions.
  Plan-scope fields (population, place) are in the item text but **not** in the hash, so a plan
  change does not flag every link (C11).
- A link whose hash differs from the one its evidence counts for reads *Edited · check pending*;
  its evidence stays until the user keeps it or checks again (contract C19).

## Web search

✅ OpenAI's own web search tool (owner, S7). 🟡 Design:

- **Call path.** The tool needs the OpenAI Responses API, a new call path beside the existing
  `chat.completions.parse` wrapper in `core/openai_client.py`, with the same tracing and usage
  records. About $10 per 1,000 tool calls plus tokens (research § 3); up to 80 calls per check.
- **Route.** On the OpenAI route, the call goes to OpenAI as usual. Bedrock's global routing does
  not offer the tool: only the `bedrock-mantle` endpoint has hosted web search, in us-east-1 and
  us-east-2 only. ✅ On the Bedrock route, web search calls alone go to `bedrock-mantle` in
  us-east-1 (owner, 2026-10-23). 🟡 A `web_search` table on each route in `model_routes.toml`, like
  the existing `search_queries` one, holds the address and the model name (`openai.gpt-5.6-terra`
  on Mantle, which takes in-region names, not `global.` ones). The contract checks that the Bedrock
  key and identity also work in us-east-1.
- **Frozen, untrusted text.** Each page the tool cites is fetched with the existing full-text
  fetcher and stored as a source snapshot with source type *web*, its URL, its retrieval time and
  its text. Page text enters prompts only as quoted data, following
  [../../system/prompting.md](../../system/prompting.md). No component reads a live page at answer
  time.
- **Same funnel.** Web pages are screened, classified and appraised like any document. They count
  toward flags and *weak*, never toward *medium* or *strong*.
- **Governance.** Every web call emits the existing search governance event.
- **ADR.** This opens the open-web seam that
  [../../system/execution-orchestration.md](../../system/execution-orchestration.md) and
  `docs/deferred.md` defer. The task ADR records the provider, the injection posture and the cost.

## Uploads

✅ Kept in S3 (owner, S8). 🟡 The file travels as base64 in a JSON request (no multipart dependency),
size-capped (🟡 10 MB). The backend writes it to a new private, encrypted bucket under the task's
key. Tasks are archived, never deleted, so the file stays while the task row exists; only the
operator script that hard-deletes tasks removes it (contract C8). Reads go through a task-scoped route with the task's own access
check. This is the first user-data bucket (today's buckets hold the frontend and fonts), so it is
an infrastructure change and closes the "Upload audit-event seam" in `docs/deferred.md`: each
upload writes an audit event and a trace span.

## Data

🟡 New tables, following the OS precedent; one theory per task. Columns, keys and the three
revisions are in contract § Schema: `toc_box`, `toc_link`, `toc_band_item`, `toc_pathway`,
`toc_pathway_link`, `toc_item_evidence` (revision 1); `toc_upload` (revision 2); and
`task_link.source_option_id` (revision 3). Boxes, links and pathways carry a *changed by Policy
Atlas* flag with its reason and the user's prior version.

Shared tables, reused: `task`, `plan`, `task_agent_transcript`, `task_link`, `evidence_scope`,
`capability_run`, `source_snapshot` and the screening, classification and appraisal results,
`conversation`, `event_log`, `artefact`.

**Links.** Two changes to the existing link rules, in the task-create route and its contract:

- Today a link's source must be an Evidence search task. A ToC target also accepts an Options
  scoping source, and only with an option named.
- Today `task_link.option_id` points to an option in the **target** task. A ToC started from an
  option needs an option in the **source** task. 🟡 Add `source_option_id` with its own composite
  foreign key to `(option_id, task_id)` on the source side (owner, 2026-10-23).

**Migrations:** three revisions, as contract § Schema states. Item searches reuse the `targeted`
scope with `acquire_only`; the main ToC walk uses the new `toc` purpose. Web pages are stored as
`source_snapshot` rows with `text_basis = 'full_text'` and metadata `backend = 'web'`, so no new
source type is needed.

## Runtime and code

| Touch point | Change |
|---|---|
| `runtime/capability_registry.py` | `THEORY_OF_CHANGE` key, a `CapabilitySpec`, a `TaskAgentProfile`; `AnyPlan` gains `TocPlan`. |
| `runtime/toc_plan.py` (new) | `TocPlan` and `compose_toc`, like `scoping_plan.py`. |
| `runtime/task_agent_toc.py`, `task_agent_toc_prompt.py` (new) | Task Agent profile and prompt. |
| `runtime/harness.py` | ToC steps registered as data, like `_SCOPING_STEPS`, and their edges. |
| `runtime/inherit.py` | The option direction. |
| `core/openai_client.py` | A Responses API call for the web search tool. |
| `model_routes.toml`, `core/model_routes.py` | A `web_search` table per route (address and model); on `bedrock-local`, Mantle in us-east-1. |
| `evidence_search/sourcing/web_pages.py` (new) | Freezes cited web pages (contract C7). |
| `theory_of_change/` (new package) | `graph.py` (models, read, write, checks), `draft/`, `importer/`, `evidence/` (items, judge, grade), `discover/`, `merge/`, `choose/`, `stress/`, `summary/`, `export/`, `model_calls.py`. Prompts sit beside their phase as `*_prompt.py`. |
| `model_routes.toml` `[steps]` | As in contract § Prompts and model routes: `task_agent_toc`, `toc_draft`, `toc_import`, `toc_merge`, `toc_choose` (frontier); `toc_discover`, `toc_judge`, `toc_summarise`, `toc_same_meaning`, `toc_stress`, `toc_web` (standard). Queries use the existing `search_queries` step. |
| `scripts/prompt_hashes.json` | New prompt files pinned. |
| `api/routers/toc.py` (new) | Routes as in the task 054 plan § S14: read the graph with grades and link states; edit; keep the evidence; check again; search for more; undo a change; restore a pathway; keep mine; accept a change; upload; exports. Registered in `api/app.py`; `make openapi-sync`. |
| `api/routers/tasks.py` | The two link-rule changes. |
| `tests/runtime/test_capability_registry.py` | The "unknown capability" assertion for `theory_of_change` is reversed. |
| Infrastructure | The uploads bucket and the backend's access to it. |
| Frontend | `lib/capabilities.ts` flag; `views/toc/` (canvas, reading guide, detail panel, Detailed information, original-file view, stress-test pane); a ToC branch in `views/taskResult.ts`; "Design a theory of change" at the end of the option page. |
| New dependencies (R12) | `@xyflow/react` (canvas; MIT licence), `html-to-image` pinned to 1.11.11 (PNG and SVG), `python-pptx` (PowerPoint). Each goes through the dependency gate. |

## Build order

✅ One programme contract, built iteratively (owner, 2026-10-26: "implement a simple version …
then iterate a bit, and then build from there"). Tier **4**, with the owner-approved lighter
review stack (contract C18) and ADR 0042.

| Increment | Delivers | Evals |
|---|---|---|
| 1. Core, then iteration | Registry entry, revision 1, `TocPlan`, Task Agent, draft, the check (OpenAlex, Overton), grades, sentences, read-only Result page | E1, E2, E6 during iteration; E2b only with the owner's cost approval |
| 2. Editing and changes | Canvas editing, *check pending* with Keep and Check again, Task Agent edits, change list with Undo, Keep mine, Restore, plan-change choice | E1 on edited graphs |
| 3. Web search | Responses call, web pages, Mantle on the Bedrock route | spot checks |
| 4. Stress test and discuss | `stress_test` chat kind; discuss with ToC context | spot checks |
| 5. Bring your own theory | Revision 2, uploads bucket, text, image and PDF import | E3, E4 later |
| 6. Export | PDF report, PNG, SVG, CSV, JSON, draw.io, PowerPoint | manual import checks |
| 7. Design from an option | Revision 3, the option-page button and back-list, shared documents, the newer-run flag | spot checks |

E7 (back-test against reviews) and E8 (expert panel) run once steps 1 to 5 are stable, before the
build flag is removed.
