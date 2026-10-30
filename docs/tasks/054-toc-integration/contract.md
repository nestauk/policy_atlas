# Task contract: 054-toc-integration

One programme contract for the third capability, **Theory of change**, built as a simple core
first, then iterated, then extended in six increments (owner memory: one contract per programme,
numbered steps, no gate per step; owner, 2026-10-26: "implement a simple version of what we've
discussed and then iterate a bit, and then build from there"). It lands a new task kind whose
Result is a Magenta Book canvas: a drafted causal chain whose links are checked in the
background against research, policy documents and the web, each graded on *worked elsewhere*
and *holds here*, with pathways found in the evidence, a stress-test chat, import, export and one
entry point from Options scoping.

> **Status:** approved 2026-10-23 · owner ("approve, let's go"). **Amended 2026-10-26** after the
> owner's wireframe and journey review (§ Rulings from the wireframe review, W1–W18) and the
> owner's ruling on an iterative build (C18). The amendments change the schema, the deliverables
> and the review stack, so the contract is **re-approved with the plan**: **approved 2026-10-26 ·
> owner** ("Approve!"), after a read-only Codex review of the revised contract and plan (five
> fixes folded, one finding kept on the owner's word). ADR
> [0042](../../adr/0042-theory-of-change-task-kind.md): Accepted 2026-10-26.
>
> **Increment 2 (editing) drafted 2026-10-30** (§ Increment 2: editing, C40 to C51), for the
> owner's design review with `wireframes-editing.html`.
>
> **Design sources.** Product intent and every owner ruling: the capability spec
> [`docs/specs/capabilities/theory-of-change/`](../../specs/capabilities/theory-of-change/capability.md)
> ([components](../../specs/capabilities/theory-of-change/components.md)). Screens:
> [wireframes.html](wireframes.html) (version 21), which § Output structure of the spec describes
> in words. Owner-facing explainer: [theory-of-change.html](theory-of-change.html). This contract
> fixes the build: schema, interfaces, tests, sequence. Where it and the spec differ, the
> contract's § Decisions is the newer word and the spec is updated with it.
>
> **Branching.** `task/054-integrate-toc` sits on `aws-bedrock-integration` (task 053, PR #84),
> because it needs the model route file (`model_routes.toml`, ADR 0041). The build starts only
> after PR #84 merges to `dev` (§ Stop conditions; C15).

## Goal

A user can start a **Theory of change** task, agree a short plan with the Task Agent, and see a
drafted canvas at once. Policy Atlas then checks every link against the evidence in the
background and reports, in plain sentences that cite their sources, whether each step worked
where it was tried and whether it is likely to hold here. The user can read the result on the
canvas or as Detailed information, edit it, stress-test it, export it, and start one from an
option in Options scoping.

**Seven increments**, built in order (C18). The rubric, the plan and the ADR use the same
numbers. Increment 1 is the simple core; the iteration phase after it is part of increment 1.

1. **Core.** The task kind, its plan and Task Agent, the draft, the check (OpenAlex and Overton
   only), the grades and sentences, and a read-only Result page: header, canvas, reading guide,
   detail panel, Detailed information, Sources tab. Then **iteration**: real topics run in the
   app, prompts, grade constants and layout tuned, E1, E2 and E6 built and run. The increment
   ends when the owner says the core is good enough to build on.
2. **Editing and changes.** Canvas editing, *Edited · check pending* with Keep the evidence and
   the minimal Check again, change requests through the Task Agent, the change list with Undo
   per change, Keep mine, Restore, and the plan-change choice.
3. **Web search.** OpenAI's web search tool as a third source on both routes, pages frozen as
   untrusted text.
4. **Stress test and discuss.**
5. **Bring your own theory.** Pasted text, image and PDF import; the uploads bucket; "Your
   original" in the plan.
6. **Export.** The PDF report, PNG, SVG, CSV, JSON, draw.io and PowerPoint.
7. **Design from an option.** The option-page button and back-list, the option direction of
   `inherit`, the shared documents. It may follow a standalone release if it would disturb
   Options scoping (owner: "my preference of course is to make that connection").

## Deliverable

Code, migrations, prompts, infrastructure and tests for increments 1–7 on a feature branch (C15),
behind the build flag `VITE_THEORY_OF_CHANGE` and the server setting; ADR 0042; the spec changes
in § Spec changes; E1, E2 (with E2b if the owner approves its cost) and E6 built and run in the
iteration phase, their numbers recorded; `verification.md`. Removing the build flag is **not** in
this contract.

## Terms

| Term | Meaning |
|---|---|
| **ToC** | Theory of change. The capability (`theory_of_change`) and its task kind. |
| **Layer** | One of the four Magenta Book columns: Inputs · Outputs · Outcomes · Impact (owner, S1). |
| **Box** | One element in a layer (`toc_box`). A failure outcome is a box with layer `failure_outcome`. Boxes are **described, not graded** (W4): each has a two-sentence description, result criteria, case studies and indicators. |
| **Link** | A causal step between two boxes (`toc_link`), also called a **connection** in the product. It has if / for / then / because text, its **conditions**, a one-sentence reading (W8), and two grades. |
| **Conditions** | What must hold for a link to work in the user's setting, stored on the link (`toc_link.conditions`, a list of plain statements). They hold the Magenta Book's assumptions; there is no assumption table (W14). Detailed information lists them all in an **Assumptions** section, grouped by assumption type (W18). |
| **Assumption type** | *delivery* · *take-up* · *behaviour change* · *benefits and side effects*, computed from the layers a link joins (spec § Vocabulary); *if it goes wrong* for failure pathways. Not stored. |
| **Worked elsewhere · Holds here** | The two evidence questions on every link: did it work where it was tried, and will it work for this population, in this place, now (transferability; Cartwright and Hardie 2012). Each has its own grade. |
| **Critical connection** | The link whose failure here would break the most of the theory, marked with one navy dot and "Critical connection · test this first" (W10, W14). At most one per task. |
| **Band item** | A context or supporting-activities line (`toc_band_item`). Shown in the header paragraph and the reading guide, not on the canvas (W1). |
| **Pathway** | An ordered route of links from an input to an impact or a failure outcome (`toc_pathway`), kind success or failure, status kept or set aside, with a one-line reason. |
| **Item** | What the evidence check tests: a link. Boxes are not items (W4). |
| **Item text** · **item hash** | The fixed text code builds for a link (spec components § Items), and its sha256 over the normalised text. |
| **Item search** | One acquire-only child walk for one link, on the Options scoping option-search machinery (C2). |
| **Judgement** | One row of `toc_item_evidence`: one link, one document, a stance and quote for *worked elsewhere* and a stance and quote for *holds here* (each supports · challenges · not about), an optional condition on a support, any case study or indicator with the box it describes, and for a modelling study whether it is robust (W6, W14, W15). |
| **Grade** | strong · medium · weak · no evidence found, computed on read by one function (C4), once per question. The canvas colours a link by the lower of its two grades. Flag: *evidence against (N)*. |
| **Link state** | *checking* · *checked* · *Edited · check pending* · *evidence kept by you* · *checked: no change* (W17). Computed, not stored (C19). |
| **Evidence sentence** · **box description** | Generated text that names and dates sources: two sentences per link (one per question), two per box (W7). Every citation is checked by code (C20). |
| **Origin** | Who made a graph element: `drafted` · `found_in_evidence` · `imported` · `user` · `options_scoping`. |
| **Changed-by-Policy-Atlas flag** | Set when merge or choose changes or sets aside something the user made or edited (T1), with the reason and the user's prior version. Cleared by Accept, Keep mine or Undo (C9). |
| **Draft walk** · **check walk** · **re-check** | The walk that drafts or imports the graph; the walk that searches, screens, discovers, merges, judges, chooses and summarises (C3); a user-started walk that re-judges named links (C19). |
| **Detailed information** | The section under the canvas: one expandable section per pathway, then *Considered and set aside* and *Questions for an evaluation*. It is also the PDF report (W3). |
| **E1, E2, E2b, E6** | Structure checks; the judge on public stance datasets; grades against Consensus and System; rebuilding published theories (spec § Evaluation). |
| **Mantle** | Amazon Bedrock's `bedrock-mantle` endpoint, the only Bedrock endpoint with hosted web search, in us-east-1 and us-east-2 only. |
| **OS** · **ES** | Options scoping · Evidence search. |

## Read first

- The ToC spec: [capability.md](../../specs/capabilities/theory-of-change/capability.md) and
  [components.md](../../specs/capabilities/theory-of-change/components.md), in full; the
  [wireframes](wireframes.html).
- [OS components § 0 inherit, § Interface rulings](../../specs/capabilities/options-scoping/components.md),
  [OS trust.md](../../specs/capabilities/options-scoping/trust.md).
- System contracts: [data-model.md § Links between tasks](../../specs/system/data-model.md),
  [execution-orchestration.md](../../specs/system/execution-orchestration.md),
  [provenance-grounding.md](../../specs/system/provenance-grounding.md),
  [prompting.md](../../specs/system/prompting.md), [web-api.md](../../specs/system/web-api.md).
- ADRs [0037](../../adr/0037-options-scoping-task-kind-links-and-baseline-gate.md),
  [0039](../../adr/0039-options-scoping-longlist-option-searches-and-option-records.md),
  [0041](../../adr/0041-bedrock-inference-route-and-model-route-file.md).
- Knowledge notes: `capability-registry-one-plan-reader.md`, `task-link-grants-no-read.md`,
  `alembic-roundtrip-explicit-revisions.md`, `new-table-bumps-count-asserts.md`,
  `structured-output-prompts-pin-key-vocabulary.md`, `rubric-domain-defines-appraisability.md`.
- Precedent contract: [044](../044-scoping-shell-baseline/contract.md).

## Decisions

Owner rulings are quoted in the spec § Rulings. **T1** (2026-10-23): "we should still allow
Policy Atlas to consolidate or edit the ToCs that users touched, just it should be flagged."
**W1–W18** (2026-10-26) are listed in § Rulings from the wireframe review and folded into the
decisions below. The decisions fix what the spec leaves to the build.

- **C1. One theory per task; edits in place.** The graph tables are keyed by `task_id`. No graph
  versions: every change writes an event to `event_log` (History). Undo replays the
  before-state carried in a step's event (C9).
- **C2. Item searches use one capability-neutral child search.** Added **inside**
  `runtime/option_search.py`, so every private name callers and tests patch keeps its identity
  (plan X7): `ChildSearchRequest(intent, context, plan_id, stage, pool)` and
  `run_child_search(…)`, which `run_option_search` calls with the option's values. The child
  resolves its plan through the registry by the task's capability. ToC children run on their own
  pool (`walk_pool.toc_item_pool()`, width 🟡 8); the join timeout is `max(1800, ceil(n / width) ×
  300)` seconds. The seven OS option-search test files pass **unedited**, and a new test runs an
  OS longlist's option searches beside a ToC check and asserts both join.
- **C3. Two walks and their chains** (W16). A **draft walk**: `inherit` (only from an option) →
  `toc_draft` or `toc_import`. A **check walk**: item searches (a runner stage, not a chain step)
  → join → `screen_abstract` → `classify` → `appraise` → `toc_discover` → `toc_merge` →
  `toc_judge` → `toc_choose` → `toc_summarise`. The check walk starts automatically when the
  draft walk succeeds (R5). Merge needs no evidence and runs before judging, so nothing is judged
  twice; choose needs grades and runs after. Discovered links get no search of their own and are
  judged with the rest against the pool. The main ToC intent record uses `purpose = 'toc'`.
- **C4. The grade is one pure function, computed on read.** `grade(judgements, appraisals,
  question) -> Grade` in `theory_of_change/evidence/grade.py`. The caller passes only the link's
  judgements whose `item_hash` equals its `counted_hash` (C19); `appraisals` maps each document to
  its appraisal score and evidence type; `robust_model` is read from the judgement. The rule is with the rule from the spec § Trust
  rules, once for *worked elsewhere* and once for *holds here*. Never stored. A web page from a
  trusted publisher counts by its appraisal score like a paper; any other web page counts toward
  *weak* and the evidence-against flag only, never *medium* or *strong* (C23). A modelling study the
  judge marks robust counts as score 3, so it can support *medium*, never *strong* (W15); the
  shared `appraise` rubric is unchanged. The reading guide's rule text is generated from the same
  constants. The canvas colour is the lower of the two grades.
- **C5. Judge.** Per link: the documents its own search screened in, plus inherited ones; a link
  with no search of its own (discovered, or after Search for more before its search returns) uses
  the whole screened-in pool of the task. Reranked against the item text with the existing rerank backend, top *K* = 8. **One call per
  link and document** returns both stances with their own quotes, an optional condition on a
  support, any case study or indicator with the box it describes (either end of the link), and
  `robust_model` for a modelling study (W14, W15). The existing quote matcher
  (`evidence_search/extract/quote_verify.py`) checks every quote against the abstract or the
  frozen page text; an unverified stance is dropped and counted. At most 80 links per check
  walk; above that, links on kept pathways go first and the thread says how many were left out.
- **C6. Discover, merge, choose.** Discover reads the screened-in documents in batches and
  proposes pathways labelled `found_in_evidence`. **Merge** (before judging) joins pathways that
  share a mechanism and sets aside those that do not reach the intended change. **Choose** (after
  grading) keeps at most 6 success and 3 failure pathways, the most promising and best evidenced,
  read as counts, never a score. It also adds conditions that supports recorded and a link does
  not yet name; such an addition does not make the link pending (C19), because the evidence it
  came from is already judged. Choose then re-picks the **critical connection**: among links on
  kept success pathways whose *worked elsewhere* grade is medium or strong and whose *holds here*
  grade is weak or none, the one on the most kept pathways (ties: the earlier one in pathway 1);
  if none qualifies, the link with the lowest *holds here* grade on the most kept pathways. The
  draft's proposal is only a starting point; a critical connection the user marked is kept. Both may merge, reword or set aside user work, and then set the
  changed-by-Policy-Atlas flag with the reason and the user's prior version (T1). Each writes its
  own event with the before-state of every row it changed.
- **C7. Web search** (increment 3). A Responses API call with the hosted `web_search` tool,
  beside the existing `chat.completions.parse` wrapper in `core/openai_client.py`, with the same
  tracing, usage records and call budget, and the hosted tool-call count in the span.
  - **Route config.** A typed `WebSearchRoute(enabled, base_url, model, api_key_env)` parsed
    from `[routes.<name>.web_search]` in `model_routes.toml`. Every route declares the table; a
    missing table fails loud at start-up. `base_url` must be `https://api.openai.com/v1` or the
    Mantle address confirmed by the first step of increment 3 (us-east-1); anything else fails
    loud. `openai-direct`: enabled. `bedrock-local`: enabled, the Mantle address,
    `openai.gpt-5.6-terra`, key `AWS_BEARER_TOKEN_BEDROCK` (owner: "Send only the web search
    calls to Bedrock's US endpoint"). `bedrock-local-claude`: disabled. No fallback: a failed web
    call records "web not searched"; non-web calls keep the route's own address (tested).
  - **Pages.** Each cited URL is fetched with the hardened `LiveDocumentFetcher`
    (`evidence_search/sourcing/fetch_live.py`) through its `DocumentFetcher` protocol, not the
    full-text ingest pipeline. A new writer `evidence_search/sourcing/web_pages.py` turns HTML
    into text with `trafilatura`, caps it at 200,000 characters, and writes one `source_snapshot`
    (`text_basis = 'full_text'`, metadata `backend = 'web'`, URL, retrieval time) and a
    `task_source_snapshot` with `origin = 'acquired'`. Duplicates checked by URL inside the task;
    http and https only.
  - **Fetch limits.** At most 🟡 5 cited URLs fetched per web call and 🟡 100 per check walk, in
    citation order. URLs over a limit are not fetched; their count and addresses are recorded in
    the walk's event and shown as "N cited pages not fetched" in the Sources tab.
  - **Untrusted text.** Page text enters prompts only through `sanitize_prompt_field` and a fenced
    data block (`_fence_safe`). Quotes are checked against the stored page text. Every web call
    emits `search.executed`.
- **C8. Uploads** (increment 5). Base64 in a JSON body; PNG, JPG or PDF; at most 10 MB; checked by
  declared type **and** magic bytes. A new private, encrypted S3 bucket (`RemovalPolicy.RETAIN`,
  public access blocked, TLS only) under `tasks/<task_id>/<upload_id>`; a local directory behind
  the same `UploadStore` protocol in development. PDF pages rasterised with `pymupdf`, at most 10.
  Each upload writes an audit event and a span. Uploads live as long as their task row; only the
  operator script that hard-deletes tasks removes objects; a retention rule is a deferred seam.
  **Access:** never on the public read leg; served by the backend with `Content-Disposition:
  inline`, `X-Content-Type-Options: nosniff` and the stored content type. The original is shown
  inside the plan under *Starting point* and from the toolbar (W9).
- **C9. Undo, Restore, Keep mine** (increment 2; W12). Each merge and choose event carries the
  before-state of every row it changed. The Task Agent lists each change with its own **Undo**
  and offers **Undo all**; both apply the before-state with C10's revision check, skip rows the
  user changed since, say which, and write their own event. **Restore** moves one set-aside
  pathway to kept (above the limits when the user does it). **Accept** keeps Policy Atlas's change
  and clears the flag. **Keep mine** puts the user's prior version back on one flagged element,
  clears the flag, and leaves the link *check pending* (C19). The blue dot clears with the flag.
- **C10. Concurrency.** Every graph row carries an integer `revision`, raised on every write.
  Edits carry the revision the client saw; the route locks the row, refuses a mismatch with 409
  `toc_stale_revision`, writes, raises the revision and records one event in one transaction.
  Judgements are insert-only and keyed by item hash. Discover is insert-only. Merge, choose and
  Undo apply each change with `WHERE revision = <observed>`; a row the user changed meanwhile is
  skipped and reported. User edits always win. The summary is stamped with the time it read the
  graph.
- **C11. A plan change after the draft** offers two choices in the Task Agent thread:
  **Redraft** (a new draft walk replaces the graph; the old one is kept in the History event;
  user elements are carried over as flagged items where they fit) or **Keep the canvas**: the
  graph and its evidence stay as they are, and the Task Agent offers **Check all again** as an
  optional next step. Plan-scope fields are not in the item hash, so a plan change flags no link
  by itself (C19).
- **C12. Steering.** Empty lattice: no pause points, no steering-mode question. The check walk
  reports progress through the existing run events. Floor triggers of the reused spine steps are
  recorded in History, as for any unattended walk.
- **C13. Links** (increment 7). `task_link` gains `source_option_id UUID NULL` with
  `fk_task_link_source_option` on `(source_option_id, source_task_id)` → `option(option_id,
  task_id)`. The create request keeps `from_task_ids` for ES and OS and gains `from_option:
  {source_task_id, source_option_id} | null`, accepted only with `capability =
  'theory_of_change'` (else 422 `from_option_capability`); a ToC create never takes
  `from_task_ids` (422 `toc_links_option_only`); the source must pass the existing four checks
  in `_write_task_links`; the option must belong to it and not be merged (409
  `link_option_invalid`). `TaskLinkOut` gains `source_option_id`. No link after creation.
- **C14. Shared documents** (increment 7). The ToC `inherit` direction gives the ToC task one
  `task_source_snapshot` per option document, pointing at the same `source_snapshot`, before the
  item searches, and reads classification and appraisal from the scoping task's pinned run
  through `labels_for_snapshots`. The cross-task duplicate gap stays as it is.
- **C15. Branch, merge and the server setting.** A feature branch `feat/theory-of-change` from
  `dev` after PR #84 merges; each increment lands as a PR into it. The backend refuses
  `capability = 'theory_of_change'` on create unless `POLICY_ATLAS_THEORY_OF_CHANGE=1`. The
  branch merges to `dev` on the owner's word, at the earliest after increment 3 (server setting
  off in both environments).
- **C16. New dependencies** (owner, R12): `@xyflow/react` (increment 1), `html-to-image` pinned to
  `1.11.11` and `python-pptx` (increment 6). The PDF report uses the browser's own print of the
  report page, as the ES report does, so it needs no new dependency. Nothing else.
- **C17. Public read.** The graph, grades, evidence, pathways and summary follow the existing
  public read leg as the Result and Sources tabs do. Uploads, the original view and exports are
  authenticated only. Each new route is tested for anonymous, same-organisation, owner and
  cross-organisation callers.
- **C18. Iterative build** (owner, 2026-10-26: "implement a simple version … then iterate a bit,
  and then build from there - rather than one perfect build session and review session with many
  long make verify inbetween. We want to test and iterate during the build process"). This
  departs from the Tier 4 default and needs the owner's approval at the plan gate.
  - **Inner loop.** Small commits. Each commit runs the tests for the modules it touches plus
    `make verify-fast`; a prompt change adds `make prompt-guard`; a contract-model change adds
    `make drift-check`; a frontend change adds `make frontend-verify`.
  - **Full `make verify`** only at build open, when a migration lands, and at the end of each
    increment before its PR.
  - **Try it in the app.** Every increment ends with the owner using it on a real topic; during
    the iteration phase, at least one live topic per working session.
  - **Reviews.** Each increment's PR gets `/code-review` and the security lane (AGENTS.md: one
    security lane, always at Tier 3 and above), focused on what the increment exposes: the public
    read API and the server setting (1); writes, Undo and the 409 path (2); web egress and page
    text (3); the chat context fence (4); uploads (5); authenticated exports (6); the link rule
    (7). The contract verifier, a Codex
    adversarial pass on the code and `/simplify` run **once**, before the branch merges to `dev`,
    not per increment.
  - **Schema.** Increment 1 adds one revision with the core tables; increments 5 and 7 add their
    own. A revision may be edited while it lives only on the feature branch, with the round-trip
    test rerun; once merged to `dev` it is append-only.
  - **Prompts.** During the iteration phase, prompt versions may move quickly (`_v1`, `_v2`, …);
    each change still re-pins its hash and replays on the fixed topic set (`prompting.md`).
- **C19. Edits flag; the user decides** (increment 2; W17). An edit to a link, or to a box at
  either end of it, marks the link *Edited · check pending*; its evidence and grades stay,
  labelled for the previous wording. Nothing reruns on its own. The user picks **Keep the
  evidence** or **Check again**, per link or for all pending links. Check again is minimal: a
  same-meaning call first (`toc_same_meaning`; no change → *checked: no change*); if the claim
  changed, only the documents already judged for the link are re-judged, reranked for the new
  wording, with no new search; with fewer than two left speaking to it, **Search for more** starts
  a named-link check walk with item searches. A link edited before the check reaches it is simply
  judged on its new wording.
  - **Hash.** The item hash covers the link's own fields, both box texts and the conditions; not
    plan-scope fields (C11). So a box edit flags both its links, and a plan change flags none.
  - **Columns and transitions.** `counted_hash` (the hash whose judgements count),
    `kept_hash NULL`, `kept_by NULL` (`user · check · choose`):

    | Action | Writes | State shown |
    |---|---|---|
    | Check walk judges the link | judgements with the current hash; `counted_hash` := current; `kept_*` := NULL | checked |
    | User edits the link or a box at either end | nothing on the link | pending (current hash ≠ `counted_hash` and ≠ `kept_hash`) |
    | Keep the evidence | `kept_hash` := current; `kept_by` := `user` | evidence kept by you |
    | Check again, same meaning | `kept_hash` := current; `kept_by` := `check` | checked: no change |
    | Check again, meaning changed | re-judged rows with the current hash; `counted_hash` := current; `kept_*` := NULL | checked |
    | Choose adds a condition | `kept_hash` := new hash; `kept_by` := `choose` | checked |

    *Checking* comes from walk state (the link is named in an active walk and has no judgement
    from it yet), not from the hashes. After a re-judge, "fewer than two left" means fewer than
    two documents with a stance other than *not about* on either question. Where it shows: a blue
  dot on the link and the edited box; a block at the top of the link's panel; the same label and
  buttons in Detailed information; a Task Agent message with **Check all** and **Keep all**.
- **C20. Generated sentences and their check** (W7, W8). The draft writes each link's one-sentence
  reading (`toc_link.sentence`); code falls back to "<source> leads to <target>, because
  <because>". Summarise writes the header paragraphs, the evaluation questions, two evidence
  sentences per link (`elsewhere_sentence`, `here_sentence`) and a two-sentence description per box
  (`toc_box.description`). A *holds here* sentence never repeats a finding the *worked elsewhere*
  sentence gave; when every document answers both questions the same way, the two merge into
  one ("Medium evidence, including in England"). Code checks every citation: a sentence may cite
  only its own link's judged documents with verified quotes, or for a box its case studies; a
  sentence that fails is replaced by a fixed one. An item with no evidence gets a fixed sentence.
- **C21. Result page** (W1–W3, W9, W10, W12). Built to the spec § Output structure and the
  wireframes: one font in the app's sizes; colour means evidence grade only, blue means actions
  and review; neutral rounded boxes; curved connections coloured by the lower grade, dashed for
  weak and none; one navy dot on the critical connection; failure pathways below *If it goes
  wrong*; a pathway menu; *How to read this* opens the guide; the header keeps *About this
  theory* and *What the evidence says*; the detail panel shows a link's reading, how it works and
  what it needs, then *worked elsewhere* and *holds here*, each with its sentence and documents
  (a document shared by both listed once); Detailed information in the report's expand and
  collapse sections, with *Download as PDF* on the right, including the **Assumptions** section:
  every condition grouped by assumption type, with its *holds here* grade, its connection and the
  critical label (W18). The plan uses the navy plan panel of
  the other task types. The Task Agent posts a message when the draft appears, lists each change
  after the check, and always suggests a stress test (J3, J5, J7).
- **C22. Iteration loop 2** (owner, 2026-10-27). Case studies: at most 5 per box, distinct by
  programme and place, ranked by appraisal score, then supporting first. Conditions: 0 to 2 per
  link, only those most likely to fail here, never repeated across links (prompt `toc_draft_v2`,
  enforced in code when the draft is stored). The judge sees the neighbouring steps and treats a
  document about a neighbouring step as *not about* this one; a condition that does not depend on
  place can be shown by good evidence from anywhere (`toc_judge_v3`). Evidence items show authors,
  and a document title opens the report's citation sidebar with the quote in its passage
  (`GET /toc/evidence/{evidence_id}/context`). The Result page sits on a white card with the ES
  report's type styles; the canvas opens at a readable zoom, fits a chosen pathway, and has a
  working fit-view control and a full-screen view.

- **C23. Web pages by publisher** (owner, 2026-10-27: "If it comes from Eval Task Force, for
  example, it could be quite strong"). Every fetched page is classified and appraised. A page whose
  domain is on the **trusted publisher list** (configuration, not code: gov.uk and subdomains, the
  Evaluation Task Force, nao.org.uk, ons.gov.uk, NHS, Ofcom, ASA, NICE, What Works Centres, WHO,
  OECD, .ac.uk, journal landing pages of works that resolve in OpenAlex) counts by its appraisal
  score. Any other page keeps the web cap. The grade function takes the publisher verdict as an
  input; the grade table test gains rows for both. Replaces the blanket web cap in C4 and C7.

- **C24. Item searches and the check screen follow arm B** (owner approved, 2026-10-27; offline
  search eval, [agentic-search.md](agentic-search.md)). Each item search's record cap is 40, not
  20. The check walk's screen judges each document against the steps it covers, not the whole
  theory: it passes when it reports evidence (a study, a review, a model, or official monitoring
  or evaluation) on at least one covered link's sentence, in any setting and whatever the
  intervention. The criterion lists the theory's boxes (the changes) in `links_to_check` order,
  under the screen's 1,000-character limit for one criterion (2026-10-27: a list of link sentences
  was too long and the live check failed). It is built when the check walk's intent record is
  minted (the graph is read there) and stored in its context; walks without it fall back to the
  theory-wide criterion. The draft walk's criterion is unchanged, and the place still never
  excludes.
- **C25. Judge v4** (owner approved, 2026-10-27). `toc_judge_v4` adds "the test" (the step's
  source and target), counts a study of a close proxy, treats a document with no data of its own
  as not about the step, and decides whether the step depends on place before it answers "holds
  here". Measured on 34 labelled documents, 3 repeats: 97 of 102 right against 92 for v3. The whole
  theory is not sent: it made results worse.
- **C26. Discovery consolidates before it writes** (owner, 2026-10-27: "53 boxes is way too much
  … do the merges first before evidence checks"). Discover's batches run in parallel and cannot
  see each other's new boxes, so the second live run wrote the same change up to 10 times (53
  boxes, 80 links). Now the batches' checked proposals are held back, and one
  `toc_consolidate_v1` call (merge tier) joins repeats, reuses the theory's boxes, shares a new
  box between pathways, and returns at most 3 new success and 2 new failure pathways, within the
  6 + 3 kept-pathway limit. Only what it returns is written; code checks every route as before
  and drops a pathway that joins no checked proposal. Merge, judge and choose then run as before.
- **C27. Light link check** (owner approved, 2026-10-27). Each link asks one narrow question, but
  each link ran a full Evidence search (about 50 calls, 40 records), then a model screen, and the
  judge reranked up to 493 documents per link (about 65 minutes in the last live run). On the live
  runs, OpenAlex search by meaning found 9 to 10 of the gold key studies and 31 of the 40
  documents the judge used; keyword queries and citation chasing added little. Now, in the check
  walk only: (1) each item search runs the Evidence search's new `link` depth: no query-generation
  call, OpenAlex search by meaning on the link sentence (20 results) and on the sentence plus
  " in the United Kingdom" (10), and Overton on the sentence (10); every distinct result is kept
  (record cap 40), with its list and rank on its `source.acquired` event. The sentence is the
  first line of the item text, the child's intent. The plan's filters still apply. (2) No model
  screen: a code step, `toc_select`, picks each link's documents with `select_for_link` (for now:
  10, in turn from the three lists in rank order, documents with an abstract first) and writes the
  screen's own rows: picked ones screened in ("selected by the link search"), the rest screened
  out ("not selected by the link search"). The pick rule lives in that one function and is
  expected to change after the pick-rule experiment. (3) The judge reads up to *K* = 10 documents
  per link, so a link with its own search skips the rerank. (4) A link with no search of its own
  (added by discovery) reads the 10 screened-in documents closest by meaning to its item text,
  using the embeddings acquire stores (a document with none ranks last), not a rerank of the
  whole pool. Replaces C24's record cap of 40 per search and its box-list screen; the steps
  criterion is deleted. The draft walk, the Evidence search's other depths and Options scoping
  are unchanged.
- **C28. One pick call per link** (owner approved, 2026-10-27: "use the best performing option, L
  + one pick call"). In the eval, round-robin put 3 of 38 key studies in front of the judge; one
  small pick call put 6. `toc_select` now makes one `toc_pick_v1` call per link on the fast tier
  (links in parallel), over all the link's documents (short ids `d1`...; title and the start of
  the abstract). It returns ids only; code drops unknown ids, tops up a short answer with
  C27's round-robin, and uses round-robin alone when the call fails. A link with 10 or fewer
  documents makes no call. The pick usage is in `toc_select`'s summary. Two fixes from the lead
  land with it: ToC calls now send the route's reasoning setting (`c7c9a5b4`; without it Terra
  ran at its default and the judge called a decisive trial "not about" its step 3 to 5 times in
  5), and the draft and discover schemas no longer write "If IF" (`7a72f1c1`; prompts
  `toc_draft_v3`, `toc_discover_v3`, `toc_consolidate_v2`).
- **C29. Merge folds repeated boxes; only kept-pathway links are checked** (owner approved,
  2026-10-27). `toc_merge_v2` also returns `box_merges` (box, into), applied before the pathway
  decisions. Code checks each: both boxes exist, same layer, not the same box, and never a box
  the user wrote (user-edited, or from their own theory) into one they did not. A fold re-points
  every link from the folded box to the kept one; two links that then join the same pair become
  one (the user-edited one, else the older, with pathway steps re-pointed to it); a link from a
  box to itself is dropped from its pathways; then the box is deleted. All of one fold, or none
  when a row changed meanwhile. The thread lists "Merged box X into Y". `links_to_check` leaves
  out links that sit only on set-aside pathways (a link the user names in Search for more is
  still checked).
- **C30. C23 implemented; Crossref abstracts; a cost line** (owner approved, 2026-10-27). (1) A web
  page (`backend = web`) whose address's host is on `trusted_publishers.toml` (gov.uk and its
  subdomains including the Evaluation Task Force and ONS, NAO, NHS, Ofcom, ASA, NICE, What Works
  Centres, WHO, OECD, .ac.uk) counts by its appraisal score like a paper; other web pages and
  unscored documents count only toward weak. Papers and Overton policy documents are not web
  pages. C23's "journal landing pages of works that resolve in OpenAlex" is not built. (2) Before
  the pick, a document with a DOI and no abstract gets one Crossref lookup (parallel, 5-second
  timeout, a mailto in the User-Agent); a found abstract is stored on the snapshot with
  `abstract_source = crossref`, so the pick, classify, appraise and the judge read it. Only when
  the ToC backend is live. (3) Every ToC model call runs under the task's Langfuse session: the
  discover, pick and judge thread pools now carry the run's tracing context. Each ToC walk's
  `run.finished` event carries `cost` (tokens per step, model, a USD estimate from a small price
  table; a model not in the table is listed as unpriced, never $0), also logged as
  `toc_check.cost`.
- **C31. Study-design search, shared pick pool, classify after the judge** (owner approved,
  2026-10-27, after the fourth live run: about 5 minutes and $0.36 for the whole theory; calorie
  intake to obesity weak; 5 links with no evidence; most Crossref lookups failed). (1) Crossref
  runs 3 lookups at a time (its polite-pool limit); a 429 waits for Retry-After (or 1 second) and
  retries once; one summary line per walk counts found, no abstract and failed. (2) The `link`
  depth adds one query-generation call (the existing writer and prompt; only its first OpenAlex
  query is used) and runs that query on OpenAlex keyword search with the existing
  systematic-review and trial clauses, 10 results each. A link now makes 5 search calls (4
  OpenAlex, 1 Overton) and 1 generation call; the record cap is 60. The lists are named by origin
  (`semantic`, `semantic_place`, `verbatim` for Overton, `variant_sr`, `variant_rct`), so select
  and the pick see them. If generation fails, the link still searches by meaning. (3) In
  `toc_select`, each link chooses from its own search's documents plus the 10 documents of the
  whole walk's searches closest by meaning to its item text; the picks are written per link in a
  `toc_select.picked` event, which the judge reads. Discovered links still use the nearest
  documents of the screened-in pool. (4) The check chain is `toc_select → toc_discover →
  toc_merge → toc_judge → classify → appraise → toc_choose → toc_summarise`. After judging, every
  screened-in document no link found supports or challenges (either question) is screened out
  ("judged not about any step", at the next screen generation), so classify and appraise read
  only what is left. Grades, case-study ranking and the critical connection read appraisals at
  grade time, so they still work; the Sources tab shows judged "not about" documents without an
  evidence type or score. The judge no longer gets a modelling flag (`toc_judge_v5` tells a
  modelling study from the text) and stores `robust_model` as it said it; a robust model counts as
  one only when classify also calls it a modelling study, and choose logs the documents where the
  two disagree.
- **C32. Links discovery adds get their own search** (owner approved, 2026-10-27: "implement if
  it adds"; in the second-round experiment a no-evidence discovered link found 4 relevant studies
  with its own light search). After `toc_merge`, the runner dispatches and joins one link-depth
  item search per kept link with no search of its own in this walk (stage
  `toc_new_link_searches`, the same fan-out and join as the first). A new code step,
  `toc_search_new` (not a spine step), then picks for those links exactly as `toc_select` does:
  own documents plus the 10 nearest from the whole walk, one pick call, round-robin fallback. A
  picked document already screened out is screened in again at the next screen generation, and
  the picks are merged into the picks event the judge reads, so the judge treats these links like
  any other. A link whose search fails or finds nothing keeps the nearest-pool fallback.
  Named-link checks (Search for more) are unchanged.

### Iteration 3: ground truth, shape, BEAM, numbers, narrative (draft, 2026-10-28)

Owner, 2026-10-28: five builds on the light link check, in this order, designed once, then built
straight through with no full verify between steps; the ground-truth eval runs after step 1
(baseline) and after step 5. Source material: `scripts/evals/theory_of_change/datasets/
ground_truth_v1/` (ground-truth pack, evaluation protocol, simplified BEAM). **Draft for the
owner's design review.** **Approved 2026-10-28** (owner: "the design concepts are good … the
evidence balance looks very good … the narrative summary is PERFECT"), with two conditions: the
canvas keeps its established look (arrows, curves, boxes), and only the line style carries the
verdict; and the wireframe's narrative (`wireframes-iteration3.html`, frame 4) is the target for
brevity and tone, used as the worked example in `toc_report_v1`. Short codes in box corners are
kept.

- **C33. Ground-truth eval (step 1).** A script drives the real app through the API: creates a
  task from a case's brief (verbatim), runs draft and check, exports the theory to the pack's
  schema (§8), and scores it. Version 1 scope: the 4 cases with link-level ground truth (EPPS,
  Changing Futures individual, service, system), intervention-first brief, 1 repeat, about $2
  a round. **Headline result is qualitative** (owner: some published theories list what a
  programme did and then evaluate it, so overlap is a direction, not a pass mark): per case, an
  LLM drafts a side-by-side read on five questions (main routes covered; layers sensible; major
  mechanism or failure mode missed; weak links plausibly the right ones; anything spurious), the
  lead reviews it, and gives a verdict of right direction / partly / off. Supporting numbers,
  read with care: box recall by layer (outcomes and impact matter most; activities are handed to
  us in the intervention-first brief), soft link recall, shape score, weak-link recall and the
  confidence gradient, using the protocol's judge prompt verbatim.
- **C34. Magenta Book layers (step 2).** Layers become *inputs and activities* (one layer:
  owner, "inputs = activities"), outputs, short-term outcomes, long-term outcomes, impact, and
  failure outcomes. The draft aims for 15 to 25 boxes and 1 to 2 impacts. Draft, discover,
  consolidate and merge prompts follow; stored `outcome` boxes migrate to short-term outcomes.
  Containers, a simplified view, multi-level maps and a vision box are later increments.
- **C35. Short IDs and the accountability ceiling (step 2).** Every box and link gets a short,
  stable code assigned by code when it is written and never reused (boxes by layer: `A1` inputs
  and activities, `P1` outputs, `S1` short-term, `L1` long-term, `I1` impact, `F1` failure;
  links `#1`). The canvas shows a box's code small and grey in its corner, only if the
  wireframe shows it unobtrusive; the narrative uses codes to point at the canvas. The
  accountability ceiling is a dashed divider after the outputs layer, labelled "Directly
  influenced" and "Contributes to"; moving it is an increment 2 edit. Context is described in
  the narrative's Summary, not shown as chips (owner).
- **C36. One evidence verdict per link: simplified BEAM (step 3).** Replaces the two grades
  (*worked elsewhere*, *holds here*; C4) with one verdict per link, computed by code (owner:
  "let's have one verdict"). Per judged document: the judge gives *support* (`strong` /
  `weak` / `mixed` / `refutes` / `not_about`, with its quote) and *relevance* R 0–3 with BEAM's
  anchors (3: same kind of intervention, population and a UK-comparable setting; 2: a few small
  extra assumptions; 1: several small or a few large leaps; 0: not applicable), so "does it
  hold here" lives in relevance and in one panel sentence. Quality Q 0–3 comes from appraise
  (score 5–4 → 3, 3 → 2, 2–1 → 1, unscored → 1; untrusted web → 1). Weight = Q × R ÷ 9; the
  verdict follows the pack's rules (`03_beam_evidence_scheme.md` §3.2, thresholds to calibrate):
  *Confident*, *Not sure: mixed*, *Not sure: too little evidence*, *Not confident: evidence
  against*, with a near-threshold flag. Canvas line: solid, two-tone, dashed, dotted in a warning
  colour. The theory's confidence is the lowest verdict among critical links. A systematic
  review replacing its own included studies (deduplication) is deferred. ADR 0042 amendment.
- **C37. Size of change (step 4).** A step after the judge extracts up to 3 figures per document
  that supports or refutes, on the link's cause or effect: value, low, high, unit, what it
  measures, population, place, year, direction, effect type and the exact quote. The Evidence
  search's IOF extractor (`extract_iof_v7`) cannot be called as is: it extracts every finding,
  takes no intent, and writes its own tables. So a small ToC prompt, `toc_figures_v1` (fast
  tier, as `extract`), reads the same title and abstract the judge read and reuses IOF's parts:
  the `IOFStatisticsWire` shape (effect size and type, CI, n), `_parse_numeric` and the bounds
  checks in `quote_verify`, and `QuoteMatcher`. Code keeps a figure only when its quote is in the
  text and its number is in the quote (a new check of a few lines). Figures come from abstracts;
  the panel says so. The link panel shows "Size of change":
  figures with the same measure and unit grouped as "Evidence suggests A to B <unit> (n
  studies)", never pooled, each with its quote and source line (policy_builder's pattern); box
  panels show baseline and indicator figures.
- **C38. Detailed information becomes a short narrative report (step 5).** It replaces the
  canvas-repeating content with the pack's five sections (§2.2), 400 to 800 words plus two
  tables: Summary (goal, one If–then–because sentence, scope, context, the 2–3 weakest critical
  links); How change happens (a paragraph per pathway, pointing at box and link codes);
  Assumptions and evidence (table: code, statement, link, kind, verdict, why, sources); What to
  test and measure (table: weak link, question, indicator and data, test-and-learn idea);
  Sources and method (numbered sources; AI use, search scope, models, date). One frontier call,
  `toc_report_v1`, writes the prose and the one-line reasons; code builds the tables and the
  sources list, and checks every code and citation. It takes over the summary's header
  paragraphs and evaluation questions; the per-link sentences stay. It uses the report's four
  text styles only (`docs/knowledge/report-typography.md`). The PDF prints it.

- **C39. Container view (next build; designed, owner-reviewed 2026-10-28).** Wireframe frame 5.
  Boxes that share their incoming or outgoing links are grouped, 2 to 6 per container in one
  layer, under a short causal claim the draft writes; a box on its own stays a plain box. Lines
  run between containers; a bundled line shows the **strongest** verdict among the links it
  stands for (owner), with a small count; opening a container shows its boxes and each link's
  own verdict. Evidence stays on box-to-box links; nothing is graded at container level.
  **Containers are the default canvas view** (owner); "All boxes" shows the full canvas. Not in
  this round's build.

### Increment 2: editing (draft, 2026-10-30)

Owner, 2026-10-30: build editing before the broad review and refactor. Every user edit applies
at once, with Undo; everything Policy Atlas finds or proposes after the first check waits for the
user's **Accept** (owner agreed, 2026-10-30). Design first (`wireframes-editing.html`), then
four slices (A to D), each tried in the app, committed and pushed. **Draft for the owner's
design review.** This section replaces the increment 2 parts of C9, C19 and S9 where they differ;
C10 (revisions and 409) stands as written.

- **C40. Checking part of the theory (the seam, slice A).** One function runs the evidence check
  on named links only: item search (C27 depth "link") → pick (C28) → judge (`toc_judge_v8`) →
  figures → classify and appraise → summarise for the named links and their boxes. No draft,
  discover, merge or choose. It runs as a **check walk named on links** (`toc_walk: "check_links"`
  with `link_ids`), so progress, cost lines, Langfuse and the run stream work as for a full check.
  Every later feature that "finds evidence" calls it: Check again (C43), Find more evidence (C44),
  checking new boxes and links (C41), and judging a study the user adds (C42, judge only). It is
  built first, as a refactor of `check.py`'s step list, and the full check uses the same pieces.
- **C41. Direct edits (slice A).** On the canvas and in the sidebar the user can:
  - **Edit a box:** its text, layer, description, and Definition, Indicator and Timing.
  - **Edit a link:** its title, if, for, then and because, and its conditions.
  - **Add a box** (choose the layer) and **connect** two boxes (pick the source, then the
    target, as in the prototype). A new box or link is marked *Needs evidence*. The sidebar
    offers **Find evidence** for it, and the Task Agent offers **Find evidence for all new
    items** once there are two or more (C40, one walk).
  - **Delete** a box (its links go with it) or a link. A pathway that loses a link is shown as
    *broken* in the pathway list; the review (C45) proposes how to repair it.
  - **Mark a link critical.** A user-marked critical link is kept by the rule (C6).
  - **Pathways:** links the user adds join no pathway. "All pathways" shows every link that is
    not set aside, so they are visible; the review (C45) proposes which pathways they belong to.
  - **Who edited what.** Every write records the user (`edited_by`, the user's display name and
    id) and the time on the row, and one `toc.changed` event with the before-state. The sidebar
    shows "Edited by Karlis · 30 Oct, 11:20" under the title, and a **History** list (who, what,
    when) at the bottom of the Result page. **Undo** is offered right after each edit (a small
    toast) and per entry in History; it applies the before-state with C10's revision check.
- **C42. Editing the evidence (slice B).** In a link's document list each document gets:
  - **Remove from this link:** the document leaves the balance and the verdict is recomputed on
    read (no rerun). It stays listed, greyed, under "Removed by you", with **Restore**.
  - **Change the judge's scores:** support (strong, weak, mixed, refutes) and relevance (0 to 3).
    The verdict uses the user's scores; the judge's scores stay visible ("Judge: weak · 2").
    Clearing the override returns to the judge's scores.
  - **Add a study:** paste a DOI or a web address. Policy Atlas fetches the record (OpenAlex for a
    DOI, the page fetch for a URL), judges it for this link, extracts its figures and adds it,
    marked *Added by you*. A study the judge finds not about the step is listed with that answer
    and the user can override it. Added studies count at once: the user asked for them.
- **C43. An edit marks evidence for review (slice B; C19 simplified).** Editing a link, or a box
  at either end of it, marks the link *Edited · evidence from the earlier wording*. Its evidence
  and verdict stay. The block at the top of its sidebar offers **Keep the evidence** (the
  evidence still fits) or **Check again** (C40 on that link: the documents already judged are
  judged again for the new wording, plus a fresh search; the results are pending, C44). The Task
  Agent lists all such links with **Keep all** and **Check all**. The same-meaning call
  (`toc_same_meaning`) is dropped: Keep and Check again cover it.
- **C44. Find more evidence; pending results (slice C).** A **Find more evidence** button at the
  bottom of the link and box sidebars (for a box: its incoming and outgoing links) runs C40 with
  a wider search (both study-design clauses, an analogue query, and the plan's place). New
  judgements arrive **pending**: they do not count until accepted. The link's sidebar shows a
  *New evidence found* block at the top: each new document with its support and relevance, the
  verdict now and the verdict if accepted ("Not enough evidence → Leaning supports"), and
  **Accept**, **Reject** per document and **Accept all**. The canvas shows a small blue dot on a
  link with pending evidence; the Task Agent posts one message per finished search with the
  same counts and buttons.
- **C45. Review after edits (slice D).** A **Review the theory** button in the toolbar, and a Task
  Agent suggestion after five or more edits since the last review. One frontier call
  (`toc_review_v1`) reads the plan, the theory with verdicts, the edits since the last review and
  the report, and returns: (1) **shape findings**, each with a reason and a proposed edit from
  the C41 list (orphan box, a layer jump, two boxes that say the same thing, a route with no
  failure pathway, a new link's pathway, a broken pathway); (2) **report findings**: which report
  sections no longer match the theory. Posted in the Task Agent as one card: each proposed edit
  with **Accept** and **Reject**, **Accept all**, and **Update the report** (reruns summarise for
  changed items and `toc_report`). Accepted edits are recorded as "Proposed by Policy Atlas,
  accepted by Karlis".
- **C46. Edits from the chat (slice D; S9 revised).** `task_agent_toc_v2` gets three tools:
  `propose_edits` (the C41 operations, as a proposal card like C45's; nothing applies until
  accepted), `find_evidence` (C44 on named links or boxes) and `review_theory` (C45). The agent
  says what it proposed and why; the user accepts in the card.
- **C47. Moving boxes (slice A).** Boxes can be dragged. On drop the position saves to
  `toc_box.position` with the row revision (C10); boxes never moved keep the computed layout.
  Connections re-route as boxes move: between boxes still in their computed places the current
  right-angled routes stay; a connection with a moved box at either end runs as a smooth curve
  between the facing sides of the two boxes (the prototype's rule). **Reset layout** clears every
  position. Positions are per task, shared by everyone who can edit it.
- **C48. Run control and progress (slice C; parked items).** A **Stop** button on a running check
  (a stopped walk keeps what it finished; links not judged stay *Needs evidence*). **Check the
  rest** restarts an interrupted or stopped check on the links with no judgements (C40). The Task
  Agent shows one progress line per stage with counts ("Searching for 11 links", "Judging: 12 of
  20 links"). Pause is Stop plus Check the rest, so it gets no button of its own.
- **C49. Clarifications to the plan (slice D; parked item).** In the Task Agent the user can add a
  clarification ("only England, not the UK") while a check runs or after it. It is stored on the
  plan as a note; the next check, Find more evidence and the review read it. A clarification
  that changes a plan field (place, population, horizon) goes through C11 instead.
- **C50. Who can edit.** Editing uses the existing write grade: the task's owner and its
  editors. Public readers and viewers see the page read-only, with no edit controls.
- **C51. Slices and what each is tried with.**
  - **A: the seam and direct edits** (C40, C41, C47, Undo and History). Try it: edit, add,
    connect, delete, drag, reset, undo; find evidence for one new link.
  - **B: evidence edits** (C42, C43). Try it: remove a study, override a score, add a DOI,
    edit a link and Keep or Check again.
  - **C: finding more** (C44, C48). Try it: Find more evidence on a weak link, accept part of it;
    stop and restart a check.
  - **D: review and chat** (C45, C46, C49). Try it: five edits, review, accept two findings,
    update the report; ask the Task Agent for an edit.
  - Each slice: lead-written prompts, tests with the slice, `make verify-fast` between pieces,
    full `make verify` at the end of each slice, commit and push. A live run at the end of B
    and of D.

**Schema (one migration per slice).**
- A: `toc_box` and `toc_link` gain `edited_by JSONB NULL` (`{id, name}`) and `edited_at`;
  `toc_link.needs_evidence` is derived (no judgements), not stored.
- B: `toc_item_evidence` gains `excluded_by JSONB NULL`, `excluded_at`, `support_override`,
  `relevance_override`, `override_by JSONB NULL`, `added_by JSONB NULL`.
- C: `toc_item_evidence` gains `status` (`counted` · `pending` · `rejected`, default `counted`),
  `decided_by JSONB NULL`, `decided_at`. The verdict reads `counted` rows only.
- D: `toc_proposal` (`proposal_id`, `task_id`, `source` (`review` · `chat`), `edits JSONB`,
  `report_findings JSONB`, `status`, `created_at`, `decided_by`); the plan gains `notes JSONB`.

**Endpoints** (prefix `/api/v1/tasks/{task_id}/toc`, write grade, each write carrying
`expected_revision`, 409 `toc_stale_revision` on a mismatch): `POST/PATCH/DELETE /boxes`,
`/links`; `PATCH /boxes/{id}/position`, `POST /layout/reset`; `POST /events/{event_id}/undo`;
`GET /history`; `PATCH /evidence/{evidence_id}` (exclude, restore, override, accept, reject);
`POST /links/{id}/studies` (DOI or URL); `POST /links/keep`, `POST /check` (body: link ids and
mode `check_again` · `find_more` · `new_items` · `rest`); `POST /check/stop`; `POST /review`;
`POST /proposals/{id}/decide` (accept or reject per edit, or all); `POST /report/update`.
`DELETE` joins CORS with a preflight test.

## ADR scope

ADR 0042, "A third task kind: theory of change", records: the task kind and its walks (C3); the
two-question grade rule as a deliberate difference from Options scoping's no-banding rule, with
the robust-model rule (C4); web search opening the open-web seam, with the Mantle US endpoint
(C7); the uploads bucket (C8); flagged changes to user work and per-change Undo (T1, C6, C9); the
edit-flag model (C19); the `source_option_id` link (C13); the server setting (C15); `DELETE` in
CORS; the iterative build (C18); and the rollback.

## Schema

Every new table follows the cross-task guard: `UNIQUE (<id>, task_id)` and composite foreign keys
that include `task_id`. Every graph table has `created_at`, `updated_at` and `revision INTEGER NOT
NULL DEFAULT 1` (C10). "Flag columns" means `pa_changed BOOLEAN NOT NULL DEFAULT false`,
`pa_change_reason TEXT NULL`, `prior_version JSONB NULL` and `user_edited BOOLEAN NOT NULL DEFAULT
false`. `origin` is checked against `drafted · found_in_evidence · imported · user ·
options_scoping`.

**Revision 1 (increment 1).**

| Table | Columns (besides the common ones) | Keys and checks |
|---|---|---|
| `toc_box` | `box_id`, `task_id`, `layer`, `text`, `dosage NULL`, `result_criteria JSONB`, `indicator NULL`, `description NULL`, `origin`, flag columns, `position JSONB NULL` | PK; `uq_toc_box_id_task`; `ck_toc_box_layer` (`input · output · outcome · impact · failure_outcome`); FK `task_id` → `task` |
| `toc_link` | `link_id`, `task_id`, `source_box_id`, `target_box_id`, `if_text`, `for_text`, `then_text`, `because_text`, `conditions JSONB NOT NULL DEFAULT '[]'`, `sentence NULL`, `elsewhere_sentence NULL`, `here_sentence NULL`, `critical BOOLEAN NOT NULL DEFAULT false`, `counted_hash NULL`, `kept_hash NULL`, `kept_by NULL`, `origin`, flag columns | PK; `uq_toc_link_id_task`; partial unique index on `task_id` where `critical`; `fk_toc_link_source` and `fk_toc_link_target` on `(box_id, task_id)` ON DELETE CASCADE; `ck_toc_link_distinct`; `ck_toc_link_kept_by` (`user · check · choose`); unique `(task_id, source_box_id, target_box_id)` |
| `toc_band_item` | `item_id`, `task_id`, `band`, `text`, `sort_order`, `origin` | PK; `ck_toc_band` (`context · supporting`) |
| `toc_pathway` | `pathway_id`, `task_id`, `kind`, `status`, `reason`, `label`, `origin`, flag columns | PK; `uq_toc_pathway_id_task`; `ck_toc_pathway_kind` (`success · failure`); `ck_toc_pathway_status` (`kept · set_aside`) |
| `toc_pathway_link` | `pathway_id`, `task_id`, `position`, `link_id` | PK `(pathway_id, position)`; FKs on `(pathway_id, task_id)` and `(link_id, task_id)` ON DELETE CASCADE. A pathway with a gap after a deletion reads *broken*. |
| `toc_item_evidence` | `evidence_id`, `task_id`, `link_id`, `case_box_id NULL`, `task_source_snapshot_id`, `capability_run_id`, `stance_elsewhere`, `quote_elsewhere NULL`, `stance_here`, `quote_here NULL`, `condition NULL`, `case_study JSONB NULL`, `indicator NULL`, `robust_model BOOLEAN NULL`, `item_hash` | PK; composite FK `(link_id, task_id)` ON DELETE CASCADE; composite FK `(case_box_id, task_id)` → `uq_toc_box_id_task` ON DELETE SET NULL; FK `(task_source_snapshot_id, task_id)` → `uq_tss_id_task`; FK `(capability_run_id, task_id)` → `uq_capr_id_task`; `ck_toc_evidence_stances` (each `supports · challenges · not_about`); a quote is required for a stance that is not `not_about`; unique `(link_id, task_source_snapshot_id, item_hash)` |

Changes to existing tables in revision 1: `ck_task_capability` and `ck_capr_capability` gain
`theory_of_change`; `ck_scope_purpose` gains `toc`; `ck_conversation_kind` gains `stress_test` (added now, used in
increment 4: one widening is cheaper than a fourth revision).
`len(metadata.tables)` asserts move from 43 to 49.

**Revision 2 (increment 5):** `toc_upload` (`upload_id`, `task_id`, `object_key`, `file_name`,
`content_type`, `size_bytes`, `sha256`, `uploaded_by`, `uploaded_at`; PK; `ck_toc_upload_type`;
`ck_toc_upload_size` at most 10 MB). Table count 50.

**Revision 3 (increment 7):** `task_link.source_option_id` with `fk_task_link_source_option` (C13).

**Downgrade order:** each revision refuses only while its own data exists, so a later increment
can be rolled back without deleting every theory. Revision 3 refuses while any
`task_link.source_option_id` is set, then drops the foreign key and column. Revision 2 refuses
while any `toc_upload` row exists, then drops the table. Revision 1 refuses while any `task` or
`capability_run` row carries `theory_of_change`, then drops `toc_item_evidence`, `toc_pathway_link`, `toc_pathway`, `toc_link`, `toc_box`,
`toc_band_item` and narrows the four constraints.

## Surface map

| Surface | What changes | File(s) | Must not change |
|---|---|---|---|
| New task page | "Theory of change" behind the build flag; ToC form copy | `frontend/src/lib/capabilities.ts`, `views/NewTaskView.tsx` | ES and OS entries |
| Capability registry | `THEORY_OF_CHANGE`, `TocPlan` in `AnyPlan` | `runtime/capability_registry.py` | ES and OS profiles, compose and lattice |
| Plan and Task Agent | `TocPlan`, `compose_toc`, profile, prompt; the navy plan panel's ToC sections | `runtime/toc_plan.py`, `runtime/task_agent_toc*.py`, `views/workspace/PlanDocument.tsx` | `planner_v11`, `task_agent_scoping_v5` text and hashes; ES and OS plan sections |
| Harness and runner | ToC steps as data; the `toc` dispatch and join beside `LONGLIST_PURPOSE` | `runtime/harness.py`, `runtime/runner.py` | ES and OS graphs, edges and chains |
| Child walks | Item searches (C2) | `runtime/option_search.py`, `runtime/walk_pool.py` | OS option-search behaviour and tests |
| Inherit | The option direction (C14) | `runtime/inherit.py` | ES and OS directions |
| Web search | Responses call, route table, web backend | `core/openai_client.py`, `core/model_routes.py`, `model_routes.toml`, `evidence_search/sourcing/` | Every existing step's model on both routes |
| Links | `source_option_id`, the widened rule | `core/schema.py`, `api/routers/tasks.py`, `api/contract/tasks.py` | Link rules for ES and OS targets |
| ToC package | Graph, draft, import, evidence, discover, merge, choose, summary, stress, export | `theory_of_change/` (new) | — |
| API | `api/routers/toc.py` (new); create accepts the new kind; `DELETE` in CORS | `api/app.py`, `frontend/openapi.json` via `make openapi-sync` | Existing routes: additive only |
| Result tab | Header, canvas, reading guide, detail panel, Detailed information, pending states, change list | `frontend/src/views/toc/` (new), `views/taskResult.ts` | ES report, OS longlist |
| Option page | Button and back-list | `frontend/src/views/longlist/` | Every other OS surface |
| Infrastructure | Uploads bucket and the backend's grant | `infra/infra/policy_atlas_stack.py` | Other buckets, network, database |
| Evals | E1, E2, E2b, E6 harnesses | `scripts/evals/toc/` (new) | Existing eval suites |

## Prompts and model routes

All prompts are new, lead-written and hash-pinned (AGENTS.md: prompt-bearing work is lead-only);
none existing changes. Each follows `prompting.md` and its refine-replay loop.

| Prompt | Step | Tier | Increment |
|---|---|---|---|
| `task_agent_toc_v1` (no graph edits) · `_v2` (adds `graph_edits`) | `task_agent_toc` | frontier | 1 · 2 |
| `toc_draft_v1` (pathways, links with sentence, if/for/then/because, conditions; result criteria; critical connection) | `toc_draft` | frontier | 1 |
| `toc_discover_v1` | `toc_discover` | standard | 1 |
| `toc_merge_v1` · `toc_choose_v1` | `toc_merge` · `toc_choose` | frontier | 1 |
| `toc_judge_v1` (two stances, quotes, condition, case study, indicator, robust model; fenced text) | `toc_judge` | standard | 1 |
| `toc_web_v1` (the web search instruction for one link: the step and its conditions, for and against) | `toc_web` | web search table | 3 |
| `toc_summary_v1` (header paragraphs, evaluation questions, evidence sentences, box descriptions) | `toc_summarise` | standard | 1 |
| Item-search guidance (the step and its conditions) | `search_queries` (existing step) | — | 1 |
| `toc_same_meaning_v1` | `toc_same_meaning` | standard | 2 |
| `toc_stress_v1` and the discuss context template | `toc_stress` | standard | 4 |
| `toc_import_v1` | `toc_import` | frontier | 5 |

Every step reads its model from `model_routes.toml` (ADR 0041). Web search uses the route's
`web_search` table (C7).

## Spec changes

Applied at the close of the design phase by plan step **D1**, with the ADR, and logged in
`docs/specs/log.md` (the W1–W18 spec edits are already applied and logged, 2026-10-26):

1. ToC components throughout (skeleton, items, components table, data, migrations, runtime and
   code, build order) to match this contract. **Applied 2026-10-26** with the review fixes.
2. ToC capability § Product surface: the server setting (C15) beside the build flag; the
   plan-change choice (C11); the empty lattice (C12).
3. OS capability § Artefact & scope: "start a theory of change" moves from ⏸ to the one button
   increment 7 builds.
4. `docs/specs/system/execution-orchestration.md`: the open-web backend is no longer deferred for
   the ToC check walk; deferred for every other capability.
5. `docs/specs/product.md` in/out table: Theory of change moves in scope.

## Rulings from the wireframe review (2026-10-26)

The owner reviewed `wireframes.html` (versions 1–21) and the user journey. Each ruling is applied
in the spec and logged in `docs/specs/log.md`, and folded into § Decisions above.

| # | Ruling | Folded into |
|---|---|---|
| W1 | One font in the app's sizes; colour means grade only; no counts, badges or captions; header paragraphs; context off the canvas | C21 |
| W2 | Neutral rounded boxes, curved graded connections, failure pathways below a line, one pathway menu, reading guide | C21 |
| W3 | Detailed information replaces the list view and pathways list; it is the PDF report | C21, C16 |
| W4 | Boxes described, not graded; case studies and indicators come from their links' documents | C5, Schema |
| W5 | (superseded by W14) | — |
| W6 | No conditions stance or flag; a support may record a condition | C5, C6 |
| W7 | Evidence sentences and box descriptions, citations checked by code | C20 |
| W8 | One-sentence reading per link | C20 |
| W9 | Navy plan panel, uploaded original inside it | C8, C21 |
| W10 | "Critical connection · test this first" | Terms, C21 |
| W11 | (superseded by W14) | — |
| W12 | Journey: two questions at most, draft message, run notification, change list with Undo per change, stress test always suggested, option link may follow a standalone release | C9, C21, increment 7 |
| W13 | Sentence storage on the link | Schema |
| W14 | No separate assumptions; every link answers *worked elsewhere* and *holds here*; lower grade colours the canvas; no repeated evidence | Terms, C4, C5, C20, Schema |
| W15 | A robust modelling study can support *medium* | C4, C5 |
| W16 | Check order: discover, merge, judge, choose | C3, C6 |
| W17 | Edits flag; the user decides; minimal Check again | C19 |
| W18 | An Assumptions section in Detailed information lists every condition, grouped by the Magenta Book's types, so the PDF shows all assumptions in one place | Terms, C21 |

Journey rulings J1–J9 are in the spec § Rulings. J9 (how an older theory signals it may be out of
date) is postponed.

## Adversarial findings (contract stage, 2026-10-23)

Codex (`codex-rescue`, read-only), before the first approval. All adopted; the remedies are now
in the decisions above.

| # | Finding | Remedy |
|---|---|---|
| A1 | Schema had no keys, guards, cascades or downgrade order | § Schema |
| A2 | No shape for naming an option on create | C13 |
| A3 | The full-text ingest cannot fetch cited web pages | C7 pages |
| A4 | Tasks are archived, not deleted | C8 lifecycle |
| A5 | Background steps could overwrite user edits | C10, C19 |
| A6 | Generalise option search or write a sibling | C2 |
| A7 | Web route table untyped | C7 route config |
| A8 | Public access to new routes unstated | C17, C8 |
| A9 | Google Slides both required and a possible non-claim | Live check, increment 6 |
| A10 | E6 timing | E6 in the iteration phase |

## Scope / Out of scope

- **In:** increments 1–7; ADR 0042; the spec changes; E1, E2 and E6 built and run (E2b if the
  owner approves its cost).
- **Out:** removing the build flag or the server setting; E3, E4, E5, E7, E8; full-text reading
  and "check in depth"; links to ES tasks or links after creation; reusing ES findings; a Miro
  API integration; the Google Slides API; anchored comments; real-time collaboration; an overall
  theory score; system maps and feedback loops; the cross-task duplicate fix; how an older theory
  signals it may be out of date (J9); any change to ES or OS behaviour beyond the surface map.

## Constraints & approval gates

Asked for together, at the plan gate:

- **Schema.** The three revisions in § Schema, each reversible.
- **Runtime egress.** New: web search (OpenAI, or Mantle in us-east-1 on the Bedrock route); page
  fetches of cited URLs; vision calls with user uploads. Existing: OpenAlex, Overton, model calls.
- **Dependencies.** C16 only, each through the dependency gate.
- **Infrastructure and production config.** The uploads bucket, the backend task role's grant,
  one environment value naming it; `POLICY_ATLAS_THEORY_OF_CHANGE` off in both environments.
- **Public interfaces.** New routes under `/api/v1/tasks/{task_id}/toc/**`; `TaskCreate` accepts
  the new capability and `from_option`; `DELETE` in CORS. Additive only.
- **Prompts.** § Prompts and model routes only.
- **Review stack.** C18's lighter stack in place of the Tier 4 default.
- **Generated files.** `frontend/openapi.json` and `types.ts` only through `make openapi-sync`.

## Public / private boundary

Public-safe: code, specs, ADR, eval harnesses, aggregate eval numbers, the labels we write for E6.
Private: uploaded files, fetched web page text and source text, Langfuse traces, Consensus API
output beyond aggregates, the E6 report PDFs and figures (cite by URL). Dataset licences are
checked and recorded in `verification.md` before use.

## Disciplines binding this slice

- **Simple first.** Increment 1 builds the narrowest version that runs end to end; anything not
  needed to try the core on a real topic waits for its increment.
- **Model only what behaves.** No column, label or flag that changes nothing on screen or in a
  rule. Grades and link states are computed, not stored.
- **Flag, don't drop.** Unverified quotes are dropped from evidence but counted; changes to user
  work are flagged (T1); edits are flagged, never silently re-checked (C19).
- **Honest absence.** *No evidence found* says what was searched; "web not searched" appears
  whenever the web leg did not run.
- **Leave seams as seams** in `docs/deferred.md`: full-text depth, ES links and links after
  creation, ES findings reuse, the cross-task duplicate gap, the Miro API, E3, E4, E5, E7, E8,
  removing the build flag, an upload retention rule, J9.

## Stop conditions

Halt and report when: PR #84 has not merged when the build opens; an approval gate is hit that
this contract does not name; Mantle refuses the long-term Bedrock key (the web leg then ships on
`openai-direct` only, and the owner decides); Google Slides drops PowerPoint connectors (PowerPoint
ships, the Slides claim does not); E2 shows the judge calls a challenge "supports" more than one
time in five (the owner decides before increment 2); a change would alter ES or OS behaviour
beyond the surface map.

## Acceptance checks

- **Gates** as C18 sets them: full `make verify` at build open, at each migration and at the end
  of each increment; `make verify-fast` plus the touched suites on every commit in between.
- **Deterministic tests** (backend unless stated), by increment:
  1. Migration round-trip; the downgrade refuses while ToC rows exist. Registry: `spec_for`,
     `validate_plan`, `compose_plan`, `lattice_for` accept the kind; the AST guard holds; ES or OS
     plans are rejected on a ToC task and the reverse. Create refuses the kind while the server
     setting is off. The graph validator (E1 checks): layers in order, no orphan boxes, at most two conditions per link and
     none repeated across links, at least one failure pathway, every pathway connected, every
     evidence item on a stored document. The seven OS option-search test files pass
     unedited; OS and ToC searches join side by side (C2). Item text and hash stable. The grade
     table test covers every rule row, both questions, the web cap, the robust-model row and the
     evidence-against flag. An unverified stance is dropped and counted; *K* and the 80-link cap
     hold. Discovered links are judged against the whole screened-in pool without a search; a
     condition added by choose does not make a link pending; the critical connection follows the
     C6 rule; merge runs before judge and choose
     after; choose keeps at most 6 and 3. Citation check: a sentence citing a document its link
     did not judge is replaced (C20). Frontend (vitest): the canvas renders neutral boxes,
     connections in the lower grade and the critical dot from a fixture; the reading guide opens
     and closes; the panel shows both questions with a shared document listed once; Detailed
     information expands, merges the two paragraphs when the documents agree, opens a document list
     from "+", and lists every condition under Assumptions in its computed type; the build flag hides the entry. The access matrix for every read
     route (C17).
  2. Race tests with explicit barriers: an edit racing judge, discover, merge, choose and Undo
     leaves the user's edit in place and reports the skipped change; a stale edit gets 409
     `toc_stale_revision`; an edited link reads pending and keeps its evidence; Keep the evidence
     and a no-change Check again both leave its judgements counting; a meaning change re-judges
     only the documents already judged; Search for more starts item searches; a box edit marks
     both its links pending; a plan change marks none; every row of the C19 transition table;
     Accept and Keep mine clear the flag; Undo per change and Undo all restore the before-state; Restore and
     Keep mine behave; every edit writes one event; the plan-change choice for both branches;
     `DELETE` passes CORS preflight. Frontend: the pending block in the panel, the label and
     buttons in Detailed information, the blue dots, the Task Agent's Check all and Keep all.
  3. `WebSearchRoute` parsing: a missing table, a disallowed address and a disabled route each
     behave as C7 states; non-web calls keep the route's address; the Bedrock route sends only web
     calls to Mantle; pages stored once with backend `web`; page text reaches prompts only through
     `sanitize_prompt_field` and a fence; web judgements never raise a grade above *weak*; "web
     not searched" appears when the leg is off; the per-call and per-walk fetch limits hold and the
     skipped URLs are recorded.
  4. `stress_test` conversations: four questions, each tied to a box or link; neither chat writes
     the graph; a fence test on a web-page quote.
  5. Upload: type and size checks including a renamed non-image; the 10-page cap; the storage
     protocol on a local directory; the audit event; access for the four caller kinds, with
     upload routes refusing the public leg; the C8 headers; a text import keeps the user's words
     and labels additions.
  6. Exports: CSV columns; JSON round-trip through the graph models; draw.io XML with one vertex
     per box and one edge per link; a `.pptx` that python-pptx re-opens with one connector per
     link attached to its two boxes; the PDF report prints Detailed information expanded.
  7. `from_option` on a non-ToC create is 422; a ToC create with `from_task_ids` is 422; another
     task's or a merged option is 409; ES and OS create behave as before; the foreign key holds;
     slots are seeded; option documents get membership rows pointing at the same snapshots before
     any item search; the duplicate check stops a re-store; the newer-run flag; the back-list.
- **Evals (recorded, not pass/fail, except the E2 stop condition),** in the iteration phase: E1 on
  about 30 drafts; E2 on SciFact, Check-COVID, PubMedQA and the Evidence Inference abstract subset,
  with the ablation arm and the challenge-called-support rate; E2b on about 50 fixed claims only if
  the owner approves the Consensus cost (about $2.50) before the run; E6 on 20 published theories.
- **Try it in the app** (C18), on `openai-direct`, local app, real egress, starting with the
  obesity option used in the wireframes and one other topic: (1) plan, draft, check, Result page
  read against its sources, Detailed information; then the iteration sessions; (2) an edit, Keep
  the evidence on one link and Check again on another, one Undo; (3) the web leg on
  `openai-direct`, and one web call on `bedrock-local` against Mantle; (4) one stress-test round;
  (5) one image import of a published GOV.UK theory figure; (6) every export opened in its target
  tool, and the PowerPoint in Google Slides: if the arrows stay attached, Slides is a supported
  claim, otherwise a recorded non-claim; (7) "Design a theory of change" from an OS option page.

## Verification evidence expected

Command tails at each full gate; the migration round-trip outputs; the OpenAPI diff (additive);
the prompt-hash diff (new entries only); eval numbers with their data sources and licences; notes
and screenshots from each try-it session; export results by tool; the `docs/deferred.md` delta;
known gaps. All in `verification.md`.

## Risk tier & review focus

**Tier 4**, with the owner-approved lighter review stack of C18. A migration, a public API, new
runtime egress including a US endpoint, user file uploads, a new S3 bucket and three new
dependencies.

**Rollback.** Turn the server setting off (no new ToC tasks). Each revision's downgrade refuses
while ToC rows exist; the remedy is an operator script that hard-deletes those tasks, their walks
and their bucket objects, after which the downgrades drop the new tables and column and narrow the
four constraints. The bucket is retained by policy and emptied by the same script. Deploy the
previous image.

**Review focus:** ES and OS behaviour, prompts and hashes unchanged; the grade function is the only
place a grade is decided; every generated citation is checked; no web text reaches a prompt
outside the fence; uploads cannot be read across tasks; a flagged change always keeps the user's
prior version; an edit never triggers a check by itself; the link rule widens only for ToC
targets; the server setting blocks creation; Undo loses nothing.
