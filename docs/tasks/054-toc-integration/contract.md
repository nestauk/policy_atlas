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
  rules, once for *worked elsewhere* and once for *holds here*. Never stored. Web judgements count
  toward *weak* and the evidence-against flag, never *medium* or *strong*. A modelling study the
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
     setting is off. The graph validator (E1 checks): layers in order, no orphan boxes, every link
     with at least one condition, at least one failure pathway, every pathway connected, every
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
