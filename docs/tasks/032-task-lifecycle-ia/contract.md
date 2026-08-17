# Task contract: 032-task-lifecycle-ia

One implementation slice. Keep it reviewable. The boundaries are in
[AGENTS.md](../../../AGENTS.md). The specs are in [docs/specs/](../../specs/index.md).

> **Status:** drafted 2026-08-17. Contract approved (before planning):
> 2026-08-17 · owner · Plan approved (before implementation): _date · who_ ·
> ADR: 0031 expected (the portfolio layer, G13 — a new entity above the existing
> project row).
>
> **Branching:** `task/032-task-lifecycle-ia` branches from `dev`.
> Task 031 is **already merged** into `dev` (PR #51, `23b3dfa`), so there is no
> stacking and no conflict on the count-display files it touched. AGENTS.md said
> "PR open" for 031; this slice corrects that pointer.
>
> **Source of the design:** a clickable prototype the owner supplied 2026-08-17,
> committed as a frozen design source at
> [docs/specs/sources/task-lifecycle-ux/](../../specs/sources/task-lifecycle-ux/README.md).
> It is a bundled artifact; its readable source is a single component of about
> 1,600 lines. Read § Reading the prototype before using it.

## Goal

Reshape the app around **one task, one lifecycle**, and put a named grouping
above tasks.

Today the app has one shape: a project is one research question, and its six
pages sit flat next to each other in the top navigation. The prototype has two
shapes. At the top, a person picks what kind of work to start, sees all their
tasks, and sees their tasks grouped into projects. Inside one task, a fixed set
of stages runs in order — plan it, read the results, inspect the sources, see
what happened — and the stages that cannot work yet are visibly unavailable
rather than empty.

After this slice:

- A person starts work by choosing a **capability** and then typing a question.
  Only Evidence search works; the other three are visibly marked as coming soon.
- Inside a task, navigation is **Plan · Results · Sources · Share · History**,
  and a stage that cannot work yet is locked, not empty.
- The plan can be **opened as a document** and each of its parts can be sent
  back to the chat to be changed.
- The report leads with a **prominent answer**, states its own metadata, and
  says which sources matter most.
- **Sources is one page** with four views: Themes, Landscape, All sources and
  Findings.
- There is a **list of every task** and a way to search it by name.
- Tasks can belong to a **project**, and a project page lists its tasks.
- A **planning conversation appears in the chats overlay** once it is no longer
  the live surface, so a past plan lineage can still be read.
- Reading surfaces are **set at the app's own type floor** instead of below it.

The planning conversation's own behaviour does not change. The chat stays the
main place where a person interacts with the system and where run progress is
reported.

## Deliverable

One PR on `task/032-task-lifecycle-ia` containing:

- The reshaped frontend: new routes, the task lifecycle bar, the new-task entry,
  the plan document panel, the report additions, the merged Sources page, the
  History page, the Share notice, the tasks list, the projects list, and
  planning conversations listed in the chats overlay.
- One type-scale and layout pass, in its own commit, applying the mapping in
  § Type scale and layout — plus one new `text-display` token, registered with
  tailwind-merge in the same commit.
- One new backend table (`portfolio`) with its migration, its endpoints, and a
  nullable link column on `project`.
- One additive field on the project list row (`source_count`).
- One additive field on the section-proposal prompt and schema (`nav_label`).
- Tests for every behaviour rule below, and `verification.md`.

## Terms

The naming problem is the first thing to understand. The words differ between
the code and the screen, deliberately, and the mapping is fixed here.

| Term | Meaning |
|---|---|
| **Task** (screen word) | One research question with its own plan, run and report. It is **the existing `project` table row** — nothing is re-parented. Owner decision, 2026-08-17. |
| **Project** (screen word) | A named body of related tasks. It is **the new `portfolio` table row**. It holds no plan, no run and no evidence of its own. |
| **`project`** (code word) | The existing table and every existing route under `/api/v1/projects/{id}`. It is what the screen calls a Task. Unchanged by this slice apart from one new nullable column and one new list field. |
| **`portfolio`** (code word) | The new table introduced by this slice. It is what the screen calls a Project. |
| **Capability** | A kind of work the system can do. Only `evidence_base` runs. `scoping_policy_options`, `theory_of_change` and `map_stakeholders` are listed and disabled. |
| **Lifecycle bar** | The five task-level tabs: Plan · Results · Sources · Share · History. |
| **Locked tab** | A lifecycle tab that is visible but cannot be opened, because the task has not reached the state that would give it content. |
| **Plan document** | The whole approved or draft plan, shown as a document in a panel opened on request. It renders the `OrchestrationPlan` fields — see [plan-as-object.md](../../specs/system/plan-as-object.md). |
| **Answer callout** | The report's opening statement, taken from the existing artefact-level summary (`ArtefactOut.summary`). Not new prose. |
| **Nav label** | A short scannable name for a report section, at most 28 characters, used only in the contents list. New optional field on the section proposal. |
| **Planning conversation** | The negotiation that produced a plan. One per plan lineage; it closes when its run reaches its terminal transaction (ADR 0029). Its turns live in `planning_transcript` and are read through `/planning-turns`, never `/conversations/{cid}/turns`. |
| **Chat** | A follow-up thread that reads across a task's artefacts and never mutates anything (task 029). This is the "ask" conversation. |
| **Chats overlay** | The conversation library, `ChatsLibrary.tsx`. Today it lists chats only; G14 makes it list both kinds. |
| **Type floor** | 16px, `--text-body` in `index.css`, declared there as "running prose — the floor". A sentence meant to be read never renders below it. |
| **Prototype** | The owner's supplied HTML, frozen at [docs/specs/sources/task-lifecycle-ux/](../../specs/sources/task-lifecycle-ux/README.md). A design reference, never a source of behaviour the backend does not have. |

## Reading the prototype

The file is a bundled artifact: a base64 gzip payload inside `<script
type="__bundler/manifest">`, plus the page itself inside `<script
type="__bundler/template">`. The readable component source is in the
`data-dc-script` block of that template. Unpack before reading; do not try to
read the raw file. The step-by-step recipe is in the source's own
[README](../../specs/sources/task-lifecycle-ux/README.md).

**The prototype is a picture, not a contract.** It carries invented content the
backend does not produce. Owner instruction, 2026-08-17: *where the prototype
shows an output the backend does not have, do not build a new backend process
for it.* Two named consequences:

1. **Case studies are out of scope** — see § Out of scope.
2. The prototype's report shows an "authors" line. The backend has no author
   concept for an artefact. The metadata strip omits it rather than invents one.

## The gaps this slice closes

Every step in the plan, and every rubric item, cites one of these numbers.

| # | Gap today | Where it lives now |
|---|---|---|
| **G1** | Work cannot be started by choosing a kind of work. There is only "New project". | `LandingView.tsx` |
| **G2** | A task is created by typing a *name*, not a *question*. The question-first entry page does not exist. | `LandingView.tsx` `NewProjectForm` |
| **G3** | Navigation is six flat project tabs. There is no task lifecycle bar, and no tab is ever locked. | `AppShell.tsx`, `routes.tsx` |
| **G4** | The plan is readable only as a collapsible card inside the chat thread. It cannot be opened as a document, and its parts cannot be edited from it. | `workspace/PlanCard.tsx` |
| **G5** | The report has no prominent answer statement and no metadata strip. The artefact summary is present but not given weight. | `ArtefactView.tsx` |
| **G6** | The contents list uses full section titles, which are too long to scan. | `ArtefactOutline.tsx` |
| **G7** | The report never says which of its sources matter most. | `ArtefactView.tsx` |
| **G8** | Sources, Landscape and Findings are three separate top-level pages. There is no single corpus view. | `SourcesView.tsx`, `LandscapeView.tsx`, `FindingsView.tsx` |
| **G9** | Themes are reachable only through a claim's theme reference. There is no reader-facing themes view, although the prose descriptions exist. | `groups` and `landscape` read models |
| **G10** | The audit trail is called "Decision log" and starts at plan approval. It omits the question and the plan drafting that came before. | `DecisionsView.tsx` |
| **G11** | Share does not exist and is not named as missing. | — |
| **G12** | There is no list of every task, and no way to find one by name. | `LandingView.tsx` shows project cards only |
| **G13** | There is no structure above a task. Related tasks cannot be grouped or named. | no such table |
| **G14** | The planning conversation is reachable from one place only. Every conversation surface hard-filters to `kind: "chat"`, and the planning thread is a hard-coded tab on the workspace. Once a run starts, planning goes read-only; when the run ends, the conversation closes. After that its thread is reachable only from Plan, and an earlier plan lineage is reachable from nowhere. | `chat/ChatsLibrary.tsx`, `chat/ChatSidePanel.tsx`, `chat/ConversationTabs.tsx` |
| **G15** | The app is built below its own type floor, so reading surfaces are cramped. `index.css` declares 16px as "running prose — the floor", and the frontend then uses 12px 250 times and 14px 83 times against 16 uses of the body token. In the report and evidence views alone that is 122 uses below the floor against 6 at it. | `index.css` type scale, and nearly every view |

## Read first

Read the source sections, not the headings.

- [product.md](../../specs/product.md) — the journey this slice reshapes, and the
  progressive-disclosure commitment the locked tabs enact.
- [web-api.md](../../specs/system/web-api.md) § Projects, § Planning turns,
  § Read models — the endpoints and read models every new view reads. G13 adds
  to § Projects; nothing existing changes shape.
- [plan-as-object.md](../../specs/system/plan-as-object.md) § What a plan
  contains — the plan document (G4) renders these fields and adds none.
- [data-model.md](../../specs/system/data-model.md) § Entity hierarchy — read
  before designing the portfolio table (G13). Note the rule this slice must not
  break: *whole-item organisation is just columns, tags and scoping — no special
  container between project and artefact.* A portfolio sits **above** the
  project, so it does not breach that rule; say so in the ADR.
- [components.md](../../specs/capabilities/evidence-base/components.md) § 9 —
  synthesise, for the section proposal that gains `nav_label` (G6).
- [provenance-grounding.md](../../specs/system/provenance-grounding.md)
  § Summaries — why the answer callout (G5) may reuse the artefact summary and
  must keep its drill-down affordance.
- [deferred.md](../../deferred.md) § Web app, § Frontend uplift, § UX
  refinement — the recorded workspace-cluster and multi-question seams. This
  slice discharges part of the IA seam and must record what it leaves.
- [ADR 0029](../../adr/0029-unified-conversation-model-copilot-chat.md) — the
  conversation model G14 builds on: one planning conversation per plan lineage,
  closing with its run; chats are read-only and never mutate a plan.
- [custom-text-tokens-need-tailwind-merge-registration](../../knowledge/custom-text-tokens-need-tailwind-merge-registration.md)
  — read before touching the type scale (G15). It records a production failure
  that every automated gate missed.

## Scope

**In — frontend, no backend needed:**

- G1, G2 — new-task capability list and question page; submitting creates the
  project then posts the question as the first planning turn.
- G3 — lifecycle bar with locking; route map and redirects from the six old
  paths.
- G4 — plan document panel, opened on request, with per-part "Change this"
  actions that seed the chat composer.
- G5 — answer callout and metadata strip, from `ArtefactOut.summary` and
  `coverage_snapshot` plus the funnel.
- G7 — most relevant sources, derived in the client by counting how many report
  claims cite each source.
- G8 — one Sources route with four views, the fourth shown only when the run
  extracted findings.
- G9 — Themes view built from the existing `groups` and `landscape.themes`
  prose descriptions.
- G10 — History page: the existing decision log merged with the planning turns,
  ordered by time.
- G11 — Share notice.
- G12 — tasks list and the find-a-task overlay.
- G14 — the chats overlay and the chat side panel list planning conversations
  alongside chats. No backend work: `GET /projects/{id}/conversations` already
  returns both kinds, and each row already carries `kind`, `status`, `closed_at`
  and a preview read from whichever turn table its kind uses.
- G15 — the type-scale and layout pass, per § Type scale and layout.

**In — backend, each gated (see § Constraints):**

- G6 — `nav_label` on the section-proposal schema and prompt; optional
  `SectionOut.nav_label`.
- G12 — additive `source_count` on the project list row.
- G13 — `portfolio` table, nullable `project.portfolio_id`, and the portfolio
  endpoints.

**The planning conversation is untouched.** `PlanningPane`, `ChatPane`,
`JourneyPane`, `CheckInCard` and the conversation rail keep their current
behaviour. There is no Plan/Run toggle and no second run monitor: the journey
pane stays where it is, and the chat thread's existing run block stays the place
run progress is reported. Owner decision, 2026-08-17.

## Out of scope

- **Case studies.** Parked by the owner, 2026-08-17: producing them needs a new
  synthesis pass. The report gains no case-study section. Record the shape of
  the parked design in `docs/deferred.md` so it is a seam, not an omission.
- **Any other new synthesis pass or new prompt surface** beyond the one
  `nav_label` field.
- **Mobile and narrow-viewport work.** Owner: later. Existing responsive
  behaviour must not regress, but no new mobile navigation is built.
- **Re-parenting plan, run or artefact** onto a new task entity. That is the
  workspace-cluster slice and stays deferred.
- **The other three capabilities.** They are list entries with a "coming soon"
  marker and no route.
- **Share behaviour.** The tab states that sharing is coming soon and does
  nothing else.
- **Download and export beyond what exists.** The evidence-base print
  stylesheet already ships; the download control uses it. Any other format says
  coming soon. The share/export product seam stays deferred.
- **A full briefing page.** Owner: one page for the report is enough.
- **Chat behaviour.** Report chat shipped in task 029 and is not re-opened.

## Constraints & approval gates

**Needs human approval before proceeding.** Three gates fire.

| Gate | What changes | Why it is gated |
|---|---|---|
| **Schema** | New `portfolio` table; new nullable `project.portfolio_id` column; one Alembic revision. | Schema change (G13). Never below Tier 3. |
| **Public interface** | New `/api/v1/portfolios` routes; `portfolio_id` accepted on `PATCH /projects/{id}`; additive `source_count` on the project list row; additive optional `nav_label` on `SectionOut`. | Public API surface (G12, G13). |
| **Prompt surface** | `nav_label` added to the section-proposal schema and prompt; prompt version bumped from `synthesise_sections_v2`. | Prompt-bearing work. Lead-authored only, never delegated. |

Further constraints:

- **Additive only.** No existing response field changes type, meaning or
  presence. Every new field is optional. A project with no portfolio reads
  `portfolio_id: null` and appears in the tasks list normally.
- **No backfill.** Artefacts produced before this slice have no `nav_label`; the
  contents list falls back to a shortened title. Projects created before this
  slice have no portfolio. Both are normal states, not errors.
- **No new dependency.** The report, charts, tables and panels use what is
  already installed (Radix primitives, recharts, Tailwind brand layer).
- **No generated file edited by hand.** `frontend/src/api/gen/types.ts` is
  regenerated from the OpenAPI export.
- **Fallbacks if a gate is refused.** G6 falls back to shortening the section
  title in the client. G12 falls back to a tasks list without a source count.
  G13 has no fallback — refusing it removes the Projects view from the slice.
  Name the fallback taken in `verification.md`.

## Behaviour rules

These are the rules the tests assert. They use the gap numbers.

**Locking (G3).** A lifecycle tab's availability is computed from task state,
never from whether its page would be empty.

| State of the task | Plan | Results | Sources | Share | History |
|---|---|---|---|---|---|
| No run yet | open | locked | locked | locked | locked |
| Run executing or paused | open | locked | locked | locked | open |
| Run succeeded or degraded | open | open | open | open | open |
| Run failed, interrupted or aborted | open | locked | open | locked | open |

A locked tab is rendered, is visibly unavailable, and is not focusable as a
link. Sources stays open after a failed run because the corpus that was gathered
is real and readable — that is the flag-don't-drop discipline, not a special
case.

**Routing by state (G12).** A task row in the tasks list routes by lifecycle
state: a succeeded task opens Results, any other state opens Plan. One
destination per state, never a generic detail page.

**Status vocabulary (G12).** The tasks list reuses the existing
`runPresentation` mapping in `landingPresentation`. It is not re-invented. The
prototype's "Stale" is a **derived** state: succeeded, and the run ended more
than twelve months ago.

**Plan document (G4).** Every part of the plan renders. A part with no value yet
says so — "Not decided yet" — and is never hidden. "Change this" on a part
places a seed sentence in the chat composer and focuses it; it never edits the
plan directly.

**Answer callout (G5).** The callout renders `ArtefactOut.summary` only when
`summary_status` is `verified`. A `pending` or `failed` summary renders the
honest state and the report starts at Key findings. The callout never renders
detached from the report beneath it.

**Most relevant sources (G7).** Ranked by the number of report claims citing
each source, ties broken by appraisal tier then title. At most three. Each card
states what is true — appraisal tier, evidence type, and which sections cite it
— and never asserts why the study matters.

**Findings view (G8).** Shown only when `funnel.findings` is a number greater
than zero. Otherwise the fourth tab is absent, not empty.

**Cited sources (G8).** In All sources, a cited row is visibly distinct from a
reviewed row.

**History (G10).** One list ordered by time, merging the decision log with the
planning turns. Each row carries a time, a category badge, a plain sentence and
a status accent. Language stays readable by someone auditing the research — no
event type names, no component identifiers.

**Nav labels (G6).** The contents list uses `nav_label` when present, otherwise
a shortened title. A `nav_label` longer than 28 characters is a validation
failure at the proposal boundary, not something the client truncates.

**Planning in the chats overlay (G14).** The overlay and the side-panel list show
both kinds of conversation, newest first. A planning row is badged as planning
and shows whether it is open or closed.

A planning row is a **record, not a live thread**, and the rules follow from
that:

- **It opens at its home.** Selecting a planning row goes to that task's Plan
  tab, where the thread already renders beside the plan it produced. It does not
  open inside the chat panel. This is not a shortcut: posting a planning turn is
  409-fenced while a run executes or parks, and the conversation is closed once
  the run reaches its terminal transaction, so there is no live thread for the
  panel to host. Rebuilding a read-only planning reader inside the panel would
  duplicate the Plan tab and give the user a second, worse copy.
- **No rename, no archive.** The API rejects both on a planning conversation
  (422). The controls must not be rendered on a planning row — offering a button
  that can only fail is the defect this rule prevents.
- **Chats are unchanged.** They still open in the panel, and still rename and
  archive.

Several closed planning rows over a task's life is the expected state, not a
bug: there is one planning conversation per plan lineage, each closing with its
run. Listing them is how a reader answers "which plan did we agree for the
second run".

## Type scale and layout (G15)

The prototype is not a different design language. It is the **same font
(Archivo) and nearly the same scale**, used at the right rungs. Its whole type
census is five sizes — 14, 16, 19, 24 and 36px — and its workhorses are 16px
(160 uses) and 19px (142 uses). Nothing carries body copy below 14px.

The app already declares that scale, and then does not use it:

| Token | Size | Uses in the frontend today |
|---|---|---|
| `text-caption` | 12px | **250** |
| `text-meta` | 14px | 83 |
| `text-body` | 16px — the declared floor for running prose | 16 |
| `text-lead` | 19px | 4 |
| `text-heading` | 24px | 13 |
| `text-title` | 30px | 12 |

So 333 of 378 type declarations sit below the app's own stated floor. That, not
the scale, is why the prototype reads better. **This step is a re-mapping, not a
redesign.** The mapping:

| Surface | Today | Becomes |
|---|---|---|
| Answer callout, section ledes | caption / meta | `text-lead` (19px) |
| All other running prose in the report — block prose, key findings, section bodies, gap and theme detail | caption / meta | `text-body` (16px) |
| Report title | `text-title` (30px) | `text-display` (36px) — one new token |
| The new-task question heading | — | `text-display` (36px) |
| Contents list, metadata strip, source cards, evidence table cells, theme blocks | caption (12px) | `text-body` (16px) inside the reading column; `text-meta` (14px) at minimum elsewhere |
| Chat and planning messages | meta (14px) | `text-body` (16px) |
| Eyebrows, chips, badges, status pills, timestamps, table column headers | caption (12px) | **unchanged** — this is what caption is for |
| Page container width | a mix of `max-w-4xl`, `5xl`, `6xl` | one page width, 1180px, matching the prototype |
| Report reading measure | `--container-prose-measure: 72ch` | retuned to the prototype's 44em |
| Uppercase label tracking | `tracking-wide` / `tracking-wider` | 0.06em, matching the prototype |

Two rules bind this step:

1. **No running prose below 16px.** `text-caption` is for labels, chips, badges
   and fine print only. A sentence a person is meant to read is never 12px.
2. **The new token must be registered with tailwind-merge in the same commit that
   adds it to `@theme`.** This is a recorded production failure, not a
   hypothetical: in task 028 an unregistered scale token was classified as a text
   *colour*, silently stripping `text-white` from every primary button, with
   typecheck, lint, 185 tests and the mock e2e all green. See
   [custom-text-tokens-need-tailwind-merge-registration](../../knowledge/custom-text-tokens-need-tailwind-merge-registration.md)
   and the `Button.test.tsx` guard.

**Honest limit on verification.** Rule 2 and the token/registration sync are
mechanically testable, and they will be tested. Whether each surface landed on
the *right* rung is a judgement, checked by eye at the live check and at review.
A test asserting class names per surface would be brittle and would not measure
readability, so none is written. Say this plainly in `verification.md` rather
than implying the mapping is test-covered.

## Public / private boundary

Public-safe and committable: the task documents, the migration, the API
contract, the prompt change, tests and fixtures using synthetic content.

Private: any acquired or uploaded source text, real run traces, live model
output, and any screenshot of a real project. Manual-check notes name projects
by id, never by pasting evidence content.

## Model route

OpenAI under the approved controls, behind the routing seam — unchanged.

One prompt-bearing change: `nav_label` on the section proposal
(`synthesise_sections_v2` → `v3`). It is **lead-authored**, never delegated. It
adds one field and one instruction line to an existing call; it adds no call, so
run cost does not change materially.

No other step in this slice makes an inference call.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — the portfolio row exists because it changes
  navigation and grouping behaviour. It carries no status, no lifecycle and no
  run state, because none of those would do anything.
- **Flag, don't drop** — a failed summary, a missing `nav_label`, an
  unclassified source and a failed run all render their real state.
- **Honest absence** — a locked tab says it is locked; an absent Findings view
  is absent; a task with no portfolio says so.
- **Progressive disclosure** — the plan opens on request, the report leads with
  the answer and drills down, the evidence sits behind the claims.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md), not
  silent omissions. This slice must record at least: case studies, the prose
  "why this source matters", mobile navigation, the full briefing page, and
  what remains of the workspace-cluster IA.

## Stop conditions

Halt and escalate when: one of the three gates above is unapproved; the
portfolio design would need to re-parent plan, run or artefact; a step needs a
second new table or a second prompt change; scope would grow past this contract;
or the turn or token budget is spent. Report the blocker; do not push through.

## Acceptance checks

- `make verify` (okf-validate · test · typecheck · lint · build) — green.
- **Deterministic tests** cover: the locking table, state-based routing, the
  stale derivation, the plan document's "Not decided yet" behaviour, the
  callout's three summary states, the most-relevant-sources ranking, the
  Findings view's availability rule, the History merge order, the `nav_label`
  validation boundary and its client fallback, the portfolio endpoints
  including the not-found and cross-owner cases, the additive-only shape of
  every changed response, the chats overlay listing both conversation kinds with
  no rename or archive control on a planning row, and the type-scale tokens in
  `index.css` staying in sync with the tailwind-merge registration in `cn.ts`.
- **Migration round-trip** — up and down, against a scratch database.
- **No AI eval applies.** The one prompt change adds a short label field; its
  quality is a judgement call at the live check, not a scored eval.
- **Live manual check — scoped.** The changed surfaces on one real project, plus
  one cheap full-chain smoke. Named at contract time so it is not inherited:
  1. New task → capability list → question → the question appears as the first
     planning message.
  2. Locking: the bar with no run, then during a run, then after it completes.
  3. Plan document: open it, read every part, use "Change this" once.
  4. Results: callout, metadata strip, contents list with short labels, most
     relevant sources, one citation opening the source drawer.
  5. Sources: all four views, including a cited row reading as cited.
  6. History: the question and the plan drafting appear above the run events.
  7. Tasks list and find-a-task; one task assigned to a project; the projects
     list showing the right count.
  8. The chats overlay on a task whose run has finished: the planning
     conversation is listed and badged, selecting it lands on Plan, and it offers
     no rename or archive control.
  9. **Read the app by eye** on the report, Sources and the chat, at a normal
     window size, and confirm no sentence renders at 12px. Confirm a primary
     button still shows white text — the 028 tailwind-merge failure was invisible
     to every automated gate and was caught this way.
  A full live end-to-end run is **not** in scope for this check. If the staging
  model route is unavailable (the OpenAI quota was recorded exhausted
  2026-07-28), say so plainly in `verification.md` and name which checks could
  not run. Do not claim them.

## Verification evidence expected

In [verification.md](verification.md): the `make verify` output; the migration
round-trip output; the manual-check notes for all nine checks above, each either
passed with what was observed or explicitly not run with the reason; a diff
summary by step; which fallback was taken if a gate was refused; the plain
statement that the type mapping is eye-verified rather than test-covered
(§ Type scale and layout); the new `docs/deferred.md` entries; and a
public-safety confirmation.

## Risk tier & review focus

**Tier 3.** A new table and new public routes are a hard gate, and a hard gate is
never below Tier 3. The review stack therefore includes the security lane,
adversarial review at the contract stage and the plan stage and on the code, and
a human deep review.

Review focus, in order:

1. **Did the naming mapping hold?** The screen says Task where the code says
   project. A place that leaks the code word to the user, or vice versa, is a
   defect.
2. **Tenancy on the new routes.** Portfolios are owner-scoped. An unknown or
   cross-owner portfolio is 404, matching the existing project rule.
3. **Additive only.** Any existing response field that changed shape is a
   defect.
4. **Locking correctness** against the table above, especially the failed-run
   row.
5. **Scope creep** — a second prompt change, a second table, or case studies
   creeping back in.
6. **Over-abstraction** — the portfolio row must stay a name, a description and
   an owner. No status, no lifecycle, no cached counts.
7. **The type pass reviewed on its own.** It lands as its own commit precisely so
   it can be read separately from the structural work — a large mechanical diff
   mixed into a large structural diff is how a real defect hides. Check the
   tailwind-merge registration first, then whether any sentence is still 12px,
   then whether caption survived where caption belongs.
8. **Planning rows offer nothing that 422s.** No rename or archive control on a
   planning conversation, anywhere.
