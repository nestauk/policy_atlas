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
   item searches (child walks, acquire only; one per link, assumption and output/outcome/impact box;
                  OpenAlex · Overton · web) ─▶ join
   ─▶ 3 screen ─▶ 4 classify ─▶ 5 appraise ─▶ 6 item_evidence ─▶ 7 discover ─▶ 8 consolidate ─▶ 9 summarise
   ─▶ follow-up check on items queued by edits during the run

re-check   = item searches for the chosen items ─▶ 3 ─▶ 4 ─▶ 5 ─▶ 6 (those items only)
chats      = stress test · discuss; no walk
export     = read endpoints and frontend rendering; no walk
```

## Components

| # | Component | Origin | What ToC uses it for | Realisation |
|---|---|---|---|---|
| 0 | inherit | **modified**: shared by ES and OS; gains one direction, from an OS option | Seeds the plan slots from the option and the scoping plan; gives the ToC task a membership row for each of the option's documents (the document itself is shared, not copied), flagged *inherited* and re-screened, with classification and appraisal read from the scoping run. Runs **before** the item searches, so `acquire` does not store those documents again (capability.md § Connections to other tasks). | procedure |
| 1 | plan | **modified**: the Task Agent profile pattern with ToC slots | The plan conversation and `TocPlan` (capability.md § Plan slots). | agent, lead-authored prompt |
| 2 | draft | **new**: nothing in the repo writes a causal graph | Candidate success and failure pathways through Inputs, Outputs, Outcomes and Impact; links with mechanisms; assumptions; context; supporting activities; result criteria and indicators; load-bearing assumption. Code then checks the graph (the E1 checks) and sets each assumption's type from its link's layers. | one call (judgment model) + code checks |
| 2b | import | **new**: no vision call exists | Reads pasted text, an image or a PDF of an existing theory into the same graph shape, keeping the user's words and labelling what it adds. The file is stored in S3 (§ Uploads). PDF pages become images with `pymupdf` (already a dependency) and go through the existing `chat.completions.parse` path as image parts. | one vision call + the same code checks |
| — | item search | **reused**: the option-search child walk (`runtime/option_search.py`) | One acquire-only walk per item (§ Items). Intent = the item text. The search guidance asks for queries that would find support **and** challenge; for a box, also case studies and measures. 🟡 At most 80 items per check. | procedure |
| — | web leg | **new backend** behind the existing `search` verb | OpenAI's web search tool (§ Web search). | procedure |
| 3 | screen | **reused**, unchanged | Title-and-abstract screen once over the joined pool; intent = the theory. Web pages are screened on their title and opening text. | per-doc fan-out |
| 4 | classify | **reused** | Evidence type per document. Non-evidence never counts toward a grade. | per-doc fan-out |
| 5 | appraise | **reused** | Appraisal score per document under the existing rubric (1 to 5). Feeds the grade. | code |
| 6 | item_evidence | **new**: nothing judges a document against one causal claim or one result | Per item: the screened-in documents its own search found plus inherited ones, reranked against the item with the existing rerank backend, top *K* kept (🟡 *K* = 8). One call per item and document: *supports* · *supports under conditions* · *challenges* · *not about this item*, with a quote and, for conditions, the condition. For a box, the same call also returns any **case study** (programme, place) and any **indicator** the document uses. The existing quote verifier checks each quote; unverified items are dropped. | per-pair fan-out + quote check |
| — | grade | **new**, code only | Grade, flags and status per item, computed on read from its evidence rows (capability.md § Trust rules). Not stored, so it cannot drift. One function, so the rule can be tuned from the evals. | code |
| 7 | discover | **new**: the OS intervention profile finds interventions, not mechanisms or failure modes | Batched calls over the screened-in abstracts and pages: mechanisms, outcomes and failure modes the graph does not have, each with its document and quote. They become candidate pathways labelled *found in the evidence*; their new links are judged by `item_evidence` against the existing pool, with no new search. | batched calls + item_evidence |
| 8 | consolidate | **new**: nothing in the repo selects among causal routes | Stage 1 merges by *distinct* (shared mechanism) and sets aside by *relevant* (does not reach the intended change for the plan's population and place). Stage 2, only above the limits (6 success, 3 failure), keeps by *promising* and *evidence* (grade counts per pathway, given as input). A one-line reason per pathway. Code enforces the limits, records a flag and the user's prior version for every change to a user-made or user-edited item, and writes one undo record. | one call (judgment model) + code checks |
| 9 | summarise | **modified**: a small template call, not the full ES synthesise | The summary and the evaluation questions, from the graph and the grades. Sentences about evidence cite evidence items; the rest is labelled reasoning. 🟡 ES `synthesise` grounded blocks or one call with citation checks: a contract decision. | one call + citation check |
| — | stress test | **new**: a chat kind with its own prompt | Four questions, one at a time, each tied to a box, link or assumption. Conversation only. | chat turns |
| — | discuss | **reused**: the existing chat and grounded-answer path | The graph and its evidence enter the chat context. | chat turns |
| — | export | **new**, small | PNG and SVG from the canvas in the browser (`html-to-image`). CSV references, JSON graph, draw.io XML (standard library) and PowerPoint (`python-pptx`) from backend read endpoints. | code |

**Not reused, on purpose:** the ES deep chain (ingest, select, extract, group, full synthesise),
because this task reads abstracts only; the OS longlist, constrain, theme and shortlist, which
work at option grain; the prototype's judge-then-filter double pass and score clamps, which a
single judge, a verified quote and a fixed grade rule replace.

## Items

🟡 An **item** is something the evidence check tests. Code builds its text, so the same graph
always gives the same text:

- **Link:** "If <if>, for <for>, then <then>, because <because>." With empty fields: "<source
  box> leads to <target box>."
- **Assumption:** its text, plus the text of its link for context.
- **Output, outcome or impact box:** "<box text>, for <population>, from interventions such as
  <intervention>." Inputs boxes are not searched.
- Every item carries the theory scope: intervention, intended change, population, where.

A hash of the item text is stored with each evidence row. A changed text no longer matches, and
the item reads *out of date*.

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
key, and deletes it with the task. Reads go through a task-scoped route with the task's own access
check. This is the first user-data bucket (today's buckets hold the frontend and fonts), so it is
an infrastructure change and closes the "Upload audit-event seam" in `docs/deferred.md`: each
upload writes an audit event and a trace span.

## Data

🟡 New tables, following the OS precedent. Final columns are a contract decision. One theory per
task.

| Table | Holds |
|---|---|
| `toc_box` | task, layer (input · output · outcome · impact · failure_outcome), text, dosage, result criteria, indicator, origin, user-edited flag, position override. |
| `toc_link` | task, source box, target box, if / for / then / because / unless, origin, user-edited flag. |
| `toc_assumption` | task, link, text, load-bearing flag, origin, user-edited flag. The type is computed from the link. |
| `toc_band_item` | task, band (context · supporting activities), text, origin. |
| `toc_pathway` | task, kind (success · failure), status (kept · set aside), reason, label, origin, ordered links. Boxes, links, assumptions and pathways also carry a *changed by Policy Atlas* flag, its reason and the user's prior version. |
| `toc_item_evidence` | item (box, link or assumption), source snapshot, stance, quote, condition, case study, indicator, item hash, capability run. |
| `toc_upload` | task, S3 key, file name, size, hash, uploaded by, uploaded at. |

Shared tables, reused: `task`, `plan`, `task_agent_transcript`, `task_link`, `evidence_scope`,
`capability_run`, `source_snapshot` and the screening, classification and appraisal results,
`conversation`, `event_log`, `artefact`.

**Links.** Two changes to the existing link rules, in the task-create route and its contract:

- Today a link's source must be an Evidence search task. A ToC target also accepts an Options
  scoping source, and only with an option named.
- Today `task_link.option_id` points to an option in the **target** task. A ToC started from an
  option needs an option in the **source** task. 🟡 Add `source_option_id` with its own composite
  foreign key to `(option_id, task_id)` on the source side (owner, 2026-10-23).

**Migration (one Alembic revision):** widen `ck_task_capability` and `ck_capr_capability` with
`theory_of_change`; widen `ck_scope_purpose` with one value for the main ToC walk (item searches
reuse `targeted` with `acquire_only`); widen `ck_conversation_kind` with `stress_test`; allow a
*web* source type on `source_snapshot` if its check needs it; add `task_link.source_option_id`; add
the seven tables.

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
| `evidence_search/sourcing/search_live.py` | The web backend. |
| `theory_of_change/` (new package) | `graph.py` (models, read, write, checks), `draft/`, `importer/`, `evidence/` (items, judge, grade), `discover/`, `consolidate/`, `stress/`, `summary/`, `export/`, `model_calls.py`. Prompts sit beside their phase as `*_prompt.py`. |
| `model_routes.toml` `[steps]` | 🟡 `task_agent_toc`, `toc_draft`, `toc_import`, `toc_consolidate` (frontier); `toc_item_judge`, `toc_discover`, `toc_summary`, `toc_stress`, `toc_web_search` (standard). Queries use the existing `search_queries` step. |
| `scripts/prompt_hashes.json` | New prompt files pinned. |
| `api/routers/toc.py` (new) | Read the graph with grades; edit; upload and import; start a check; re-check; restore a pathway; undo consolidate; exports. Registered in `api/app.py`; `make openapi-sync`. |
| `api/routers/tasks.py` | The two link-rule changes. |
| `tests/runtime/test_capability_registry.py` | The "unknown capability" assertion for `theory_of_change` is reversed. |
| Infrastructure | The uploads bucket and the backend's access to it. |
| Frontend | `lib/capabilities.ts` flag; `views/toc/` (canvas, bands, assumption cards, key, detail panel, pathways list, original-file view, stress-test pane); a ToC branch in `views/taskResult.ts`; "Design a theory of change" at the end of the option page. |
| New dependencies (R12) | `@xyflow/react` (canvas; MIT licence), `html-to-image` pinned to 1.11.11 (PNG and SVG), `python-pptx` (PowerPoint). Each goes through the dependency gate. |

## Build order

✅ One programme contract with numbered steps. Sequenced so each step is usable on its own and the
risky parts sit apart (R13). It touches schema, a public API, new dependencies, infrastructure and
new runtime egress, so the task-cycle tier is **4** (a migration, a public API and infrastructure each put a task at
tier 4),
with an ADR ("a third task kind: theory of change", following ADR 0037) covering the web seam, the
uploads bucket and the grade rule.

| Step | Delivers | Evals that gate it |
|---|---|---|
| 1. Shell and draft | Registry entry, migration, `TocPlan`, Task Agent, `draft`, graph read API, read-only canvas with bands, assumption cards, key, pathways list, build flag | E1; E6 harness built and run once |
| 2. Evidence check | Item searches on OpenAlex and Overton, the reused spine, `item_evidence`, grades, case studies and indicators, detail panel, Sources tab, `summarise` | E2, E2b, then E5 |
| 3. Discover and consolidate | `discover`, `consolidate`, set-aside pathways with Restore, the undo record | E6 |
| 4. Editing during the check | Canvas editing, the edit queue, follow-up check, *out of date*, "Check again", History events, change requests through the Task Agent | E1 on edited graphs |
| 5. Web search | The Responses API call, the web backend, page freezing, the ADR, cost logging | E5 rerun with web items |
| 6. Stress test and discuss | `stress_test` chat kind and prompt; discuss with ToC context | spot checks |
| 7. Import an existing theory | Uploads bucket, pasted text, image and PDF import, "Your original" view | E3, then E4 |
| 8. Export | PNG, SVG, CSV, JSON, draw.io, then PowerPoint after a manual Google Slides import test | manual import checks in Miro, diagrams.net, PowerPoint, Google Slides |
| 9. Design from an option | The button on the option page, the option direction of `inherit`, the link changes, the back-list on the option page, the newer-run flag | spot checks on three scoping tasks |

E7 (back-test against reviews) and E8 (expert panel) run once steps 1 to 5 are stable, before the
build flag is removed.
