# Implementation plan: 032-task-lifecycle-ia

> **Status:** drafted 2026-08-17. Contract approved 2026-08-17 · owner. Plan
> approved: _date · who_. ADR: 0031 expected (the portfolio layer).
>
> Terms, the G1–G15 gap numbers, the locking table and the type mapping are in
> [contract.md](contract.md). This plan cites them and does not restate them.

## Context

The app has one shape today: a backend `project` is one research question, and
its six pages sit flat in the top navigation. The target has two shapes — a
workspace level above tasks, and a fixed five-stage lifecycle inside one task.

The naming decision keeps the backend still. The screen word **Task** is the
existing `project` row; the screen word **Project** is a new `portfolio` row.
Nothing is re-parented, so no existing route, read model or migration changes
meaning.

| Gap | Closed in |
|---|---|
| G13 portfolio layer | Phase 1 (backend) · Phase 10 (views) |
| G6 short nav labels · G12 source count | Phase 2 |
| G3 lifecycle bar, locking, routes · naming | Phase 3 |
| G1, G2 new-task entry | Phase 4 |
| G4 plan document | Phase 5 |
| G8, G9 Sources subviews and Themes | Phase 6 |
| G5, G7 answer callout, metadata, top sources | Phase 7 |
| G10, G11 History and Share | Phase 8 |
| G14 planning in the chats overlay | Phase 9 |
| G12 tasks list and finder | Phase 10 |
| G15 type scale and layout | Phase 11 |

## Decisions

Locked here so the build does not re-decide them. Each was checked against the
code, not assumed.

| # | Decision | Choice and why |
|---|---|---|
| **D1** | Route shape for the Sources subviews | **Nested routes, not a query parameter.** `routes.tsx` states the repo rule: "views are routes, the dossier and filters are search params". Four subviews are views. This is also the *smaller* diff: a layout route renders the tab strip plus `<Outlet/>`, and `LandscapeView` and `FindingsView` mount unchanged underneath it. Merging them into one component would be more work and would lose their existing tests. |
| **D2** | Where the locking input comes from | `useProject(projectId).data.latest_run.status`. `ProjectOut` carries `latest_run` on the detail GET as well as the list, so `AppShell` already has it. |
| **D3** | Keeping locking fresh during a run | `useProject` gains a `refetchInterval` while `latest_run.status` is `running` or `paused`. **Do not** mount `useRunStream` in `AppShell`: the stream is already mounted in `WorkspaceView` and `ArtefactView`, and a third connection in the shell would double-connect on those pages. The run stream *does* invalidate the project detail query (its predicate matches `["projects", projectId, …]`, and `queryKeys.project` is `["projects", projectId, "detail"]`), so on the two pages that mount it, locking updates with no polling. Polling covers only the pages that do not — the same pattern `AppShell` already uses for the pending check-in badge. |
| **D4** | Creating a task | `POST /projects {name, question}` then `POST /projects/{id}/planning-turns {message, client_turn_id}` with the same question. Two calls, no backend change. |
| **D5** | The task's name at creation | Derived client-side from the question (trimmed, question mark dropped, truncated). The planner's own `plan.title` is **not** written back to the project name — that would need a new behaviour. A task therefore displays its derived name until renamed. Record this as a known gap, not a defect. |
| **D6** | Assigning a task to a project | `PATCH /projects/{id} {portfolio_id}` after creation, and from the project detail page. **`POST /projects` is left alone** — keeping `portfolio_id` off the create call keeps the gated public-interface surface smaller. |
| **D7** | Executor family | Codex is **not available** — `codex` is not on PATH. Every phase routes inside the Claude family. See § Executor summary and § Tier 3 shortfall. |

## Phases

Each phase ends in a commit on `task/032-task-lifecycle-ia`.

### Phase 0 — Baseline

**Executor:** `lead`, inline — one command, and delegating it costs more than it saves.

1. `make verify` on the branch. Never build on a red base.
2. Record the baseline test count in `verification.md`, so the type pass in
   Phase 11 can be checked for silent test loss.

**Gate:** full `make verify` green (the build-open baseline class — mandatory).

### Phase 1 — The portfolio table and its endpoints (G13)

🛑 **The schema gate must be signed off before this phase starts.**

**Executor:** `lead` designs the table and the route semantics — seam design, and
seam design stays with the lead regardless of budget. `fast-worker` writes the
tests from the list below, which is an exact spec.

1. `portfolio` table: `portfolio_id`, `owner`, `name`, `description`,
   `created_at`, `archived_at`. **Nothing else** — no status, no lifecycle, no
   cached task count (rubric 36). The count is derived at read time.
2. Nullable `project.portfolio_id`, foreign key to `portfolio`. Nullable is the
   whole compatibility story: every existing project reads `null` and behaves
   exactly as before.
3. One Alembic revision with explicit revision ids (see
   `docs/knowledge/alembic-roundtrip-explicit-revisions.md`).
4. Routes, owner-scoped under the existing BOLA rule — unknown and cross-owner
   are both 404, matching projects:
   - `GET /api/v1/portfolios` — list with a derived `task_count` per row.
   - `POST /api/v1/portfolios` `{name, description?}`.
   - `GET /api/v1/portfolios/{id}`.
   - `PATCH /api/v1/portfolios/{id}` `{name?, description?}`.
   - `PATCH /api/v1/projects/{id}` additively accepts `portfolio_id`, including
     an explicit `null` to unassign.
5. `ProjectOut` gains optional `portfolio_id`.
6. Tests: create, list with counts, get, patch, unassign, unknown id 404,
   cross-owner 404, a project with no portfolio unaffected, and the migration
   round-trip up and down against a scratch database.

**Done when:** rubric items 34, 35, 36 and 38 hold.

**Gate:** full `make verify` — mandatory, schema class.

### Phase 2 — Two additive fields (G6, G12)

🛑 **The public-interface and prompt-surface gates must be signed off before this
phase starts.** If either is refused, take the fallback named in the contract and
say so in `verification.md`.

**Executor:** `lead` for the `nav_label` prompt line and schema — prompt-bearing
work is lead-only and is never delegated. `fast-worker` for `source_count` and
the OpenAPI regeneration, which is mechanical.

1. `nav_label` on the section-proposal schema: optional, at most 28 characters,
   **rejected at the proposal boundary** when longer — never truncated
   downstream. One instruction line in `SECTIONS_SYSTEM_PROMPT` asking for a
   short scannable name in the vocabulary of the title. Bump
   `synthesise_sections_v2` → `v3`. No new call, so run cost does not move.
2. `SectionOut.nav_label` optional. **No backfill** — artefacts predating this
   read `null` and the client falls back to a shortened title.
3. `source_count` on the project list row, derived at read time from the same
   population the funnel's `found` uses. Optional, so a project with no run reads
   `null`.
4. Regenerate `frontend/src/api/gen/types.ts` from the OpenAPI export. Never hand-edit it.
5. Tests: the over-28-character rejection, an artefact with no `nav_label`
   rendering a usable contents list, `source_count` on a project with and without
   a run, and a diff of the OpenAPI export showing every change is additive.

**Done when:** rubric items 21, 30 (the count half) and 37 hold.

**Gate:** full `make verify` — mandatory, schema-adjacent (OpenAPI contract plus
a pinned prompt version).

### Phase 3 — Vocabulary, routes and the lifecycle bar (G3, naming)

**Executor:** `lead` — this is the taste-bearing surface the whole slice hangs
off, and the locking rules are the contract's core invariant.

1. One vocabulary module owning every user-visible label, so no view hard-codes
   "Task" or "Project" (rubric 9).
2. Route map. New paths, and a redirect from every old path so no bookmark 404s:

   | Path | View | Replaces |
   |---|---|---|
   | `/` | Tasks list | the project-card grid |
   | `/new` | New task | `NewProjectForm` |
   | `/projects/:id` | Plan (`WorkspaceView`, internals untouched) | same path |
   | `/projects/:id/results` | `ArtefactView` | `/evidence-base` |
   | `/projects/:id/sources` | Sources layout → Themes | same path |
   | `/projects/:id/sources/landscape` | `LandscapeView` unchanged | `/landscape` |
   | `/projects/:id/sources/all` | `SourcesView` table | part of `/sources` |
   | `/projects/:id/sources/findings` | `FindingsView` unchanged | `/findings` |
   | `/projects/:id/share` | Share notice | — |
   | `/projects/:id/history` | History | `/decisions` |
   | `/portfolios` | Projects list | — |
   | `/portfolios/:id` | Project detail | — |

3. Replace the six `NavItem`s in `AppShell` with the lifecycle bar. Availability
   comes from the contract's locking table via D2 and D3.
4. A locked tab is rendered, visibly unavailable, and **not focusable**. A locked
   route typed directly redirects to Plan — a locked tab must not be reachable by
   URL either (rubric 14).
5. Tests: every row of the locking table, including the failed-run row where
   Sources stays open; each redirect; a locked route redirecting.

**Done when:** rubric items 9, 13, 14 and 15 hold.

**Gate:** `make verify-fast`.

### Phase 4 — New task entry (G1, G2)

**Executor:** `lead` for the capability list copy and the question page, which are
taste-bearing entry surfaces. `fast-worker` for the tests from the rules below.

1. Capability list: Evidence search actionable; Scoping policy options, Theory of
   change and Map stakeholders visibly marked coming soon, **not focusable as
   links**, and with no route (rubric 11).
2. Question page per the contract: small context label, large heading, short
   explanation, large multi-line input, compact send attached to the input,
   Enter/Shift+Enter hint, one example question that populates the box. Nothing
   else competing with the question.
3. Send disabled while the box is empty. Submit runs D4 and lands on Plan, with
   the question as the **first planning message**.
4. Optional project selector, applying D6 after creation.
5. Tests: disabled-while-empty, Enter submits, Shift+Enter does not, the question
   arrives as turn one, the three disabled capabilities are inert.

**Done when:** rubric items 11 and 12 hold.

**Gate:** `make verify-fast`.

### Phase 5 — The plan document (G4)

**Executor:** `lead` — the plan document is the trust surface of the product, and
"Change this" touches the steering boundary.

1. A panel opened on request from the Plan tab, closable, rendering every
   `OrchestrationPlan` field: question, scope, screening rules, thoroughness,
   settings, agreed steps, assumptions.
2. A field with no value yet says "Not decided yet" and is **never hidden**.
3. "Change this" seeds the chat composer with the part's sentence and focuses it.
   It **never** writes to the plan — editing stays conversational.
4. `PlanCard`, `PlanningPane`, `ChatPane`, `JourneyPane`, `CheckInCard` and the
   conversation rail keep their behaviour, and their existing tests pass
   untouched. No Plan/Run toggle. No second run monitor.
5. Tests: every field renders; an empty field says "Not decided yet"; "Change
   this" seeds the composer and does not mutate the plan.

**Done when:** rubric items 16, 17 and 18 hold.

**Gate:** full `make verify` — the shared gate for Phases 3–5. Argued: all three
add or rewire frontend files with no schema and no read-model contact, so three
separate full runs would carry the same signal. Consolidating here still leaves
the route wiring and the untouched-planning claim checked by the whole suite
before the next group starts.

### Phase 6 — Sources subviews and Themes (G8, G9)

**Executor:** `fast-worker` — a layout route plus one presentational view, against
the exact rules below. `lead` reviews the Themes copy.

1. Layout route with the tab strip and `<Outlet/>` per D1. `LandscapeView` and
   `FindingsView` mount unchanged.
2. Themes: theme name, size and the **existing** prose description from `groups`
   and `landscape.themes`. No new text is generated (rubric 25).
3. Findings tab present only when `funnel.findings` is a number greater than
   zero; otherwise **absent**, not empty (rubric 24).
4. In All sources, a cited row is visibly distinct from a reviewed row.
5. Tests: the Findings tab's presence and absence; Themes rendering description
   text; a cited row distinguishable; the existing Landscape and Findings tests
   still pass under the new paths.

**Done when:** rubric items 24, 25 and 26 hold.

**Gate:** `make verify-fast`.

### Phase 7 — Results additions (G5, G6 client, G7)

**Executor:** `lead` — the report is the product's most taste-bearing surface, and
the three summary states are an honesty rule.

1. Answer callout from `ArtefactOut.summary`, rendered **only** when
   `summary_status` is `verified`. `pending` and `failed` each render their honest
   state and the report still opens correctly (rubric 19).
2. Metadata strip: last updated, sources found, sources cited, publication-year
   range. **No author line** — the backend has no author for an artefact, and the
   prototype's is invented.
3. Contents list uses `nav_label` when present, else a shortened title.
4. Most relevant sources: rank by how many report claims cite each source, ties
   by appraisal tier then title, at most three. Each card states facts only —
   tier, evidence type, which sections cite it — and asserts nothing about why
   the study matters (rubric 22).
5. The download control uses the print stylesheet that already ships. Any other
   format says coming soon.
6. Citations still open the source drawer; existing artefact tests unchanged.
7. Tests: all three summary states; the ranking including a tie; the metadata
   strip with a missing year range; the `nav_label` fallback.

**Done when:** rubric items 19, 20, 21, 22 and 23 hold.

**Gate:** `make verify-fast`.

### Phase 8 — History and Share (G10, G11)

**Executor:** `fast-worker` — merging two lists by time is mechanical. `lead`
reviews the row copy, because "readable by someone auditing the research" is a
judgement.

1. History merges `useDecisions` with `usePlanningTurns` into one time-ordered
   list. The question and the plan drafting appear before the run events.
2. Each row: time, category badge, plain sentence, status accent. **No event type
   name, no component identifier, no pipeline vocabulary** reaches the screen
   (rubric 28).
3. Share: sharing is coming soon, and nothing else.
4. Tests: merge order with turns interleaved among decisions; no raw event type
   in the rendered output.

**Done when:** rubric items 27, 28 and 29 hold.

**Gate:** full `make verify` — the shared gate for Phases 6–8. Same argument as
Phase 5: presentational work, no schema contact.

### Phase 9 — Planning in the chats overlay (G14)

**Executor:** `fast-worker` — dropping a filter and adding a row variant, against
exact rules. No backend work.

1. Drop the `kind: "chat"` filter in `ChatsLibrary` and `ChatSidePanel` so both
   kinds list, newest first. Badge planning rows and show open or closed.
2. **No rename and no archive control on a planning row** — the API 422s on both,
   so the control must not exist (rubric 41).
3. Selecting a planning row navigates to that task's Plan tab. It never opens in
   the chat panel, and **no read-only planning reader is built** — the contract's
   reasoning is that it would duplicate the Plan tab.
4. Chats keep opening in the panel, and keep rename and archive.
5. Tests: both kinds listed; a planning row has neither control; selecting one
   navigates to Plan; several closed planning rows render; chat behaviour
   unchanged.

**Done when:** rubric items 40–44 hold.

**Gate:** `make verify-fast`.

### Phase 10 — Tasks list, finder, and the projects views (G12, G13 frontend)

**Executor:** `fast-worker` for the three views against the rules below. `lead`
decides the list's column set and the empty-state copy.

1. Tasks list at `/`: every task with status, date, its project when it has one,
   and its source count. Status wording **reuses** `runPresentation` from
   `landingPresentation` — not a second vocabulary (rubric 30). "Stale" is
   derived: succeeded, and ended more than twelve months ago.
2. A row routes by state: succeeded opens Results, every other state opens Plan.
3. Find-a-task filters by name and opens the chosen task at its state-correct
   destination.
4. Projects list: name and task count. Project detail: that project's tasks.
   **Nothing else on either page** (rubric 33).
5. Tests: the routing table; the stale derivation at the twelve-month boundary;
   the finder; project counts; a task with no project appearing normally.

**Done when:** rubric items 30, 31, 32, 33 and 35 hold.

**Gate:** full `make verify` — the shared gate for Phases 9–10.

### Phase 11 — Type scale and layout (G15)

**Executor:** `lead` decides the mapping — which rung each surface lands on is
taste-bearing and the contract's mapping table is the brief. `fast-worker`
applies the sweep, because ~250 class-site edits against a fixed table is exactly
mechanical volume.

**This is its own commit** (rubric 49), so review can read it apart from the
structural diff.

1. Add `--text-display: 36px` to the `@theme` block in `index.css` **and** to the
   tailwind-merge registration in `ui/brand/cn.ts` — **in this same commit**. Not
   optional hygiene: the identical omission in task 028 shipped ink-on-blue
   primary buttons with typecheck, lint, 185 tests and the mock e2e all green.
2. Apply the contract's mapping table. No sentence a person is meant to read
   renders below 16px; `text-caption` survives only on labels, chips, badges,
   status pills, timestamps and table column headers.
3. One page width (1180px). Retune `--container-prose-measure` from 72ch to 44em.
   Uppercase label tracking to 0.06em.
4. Tests: a guard asserting the `index.css` token list and the `cn.ts`
   registration are in sync, so the next token cannot repeat the 028 failure. The
   existing `Button.test.tsx` colour-plus-size guard must still pass.
5. Compare the test count against the Phase 0 baseline — a mechanical sweep this
   wide must not silently delete a test.

**Done when:** rubric items 45–50 hold.

**Gate:** full `make verify`. Not consolidated: this phase touches shared brand
components, which is the exact failure class the 028 note records.

### Phase 12 — ADR, deferred seams, docs and verification

**Executor:** `lead` — the ADR is a design decision and the evidence narrative
needs judgement. `fast-worker` writes the `docs/deferred.md` entries from the
list below.

1. **ADR 0031 — the portfolio layer.** Why a container above the project rather
   than re-parenting plan, run and artefact; the screen-word/code-word mapping
   and why it is accepted; and why this does not breach
   [data-model.md](../../specs/system/data-model.md)'s "no special container
   between project and artefact" rule — a portfolio sits *above* the project, not
   between project and artefact.
2. `docs/deferred.md` entries, at minimum: case studies (with the parked design —
   deterministic IOF shortlist plus a prose pass modelled on the key-findings
   pass); the prose "why this source matters"; mobile navigation; the full
   briefing page; writing `plan.title` back to the task name (D5); and what
   remains of the workspace-cluster IA after this slice.
3. Check whether any living spec now misstates the IA, and flow the correction
   back per `docs/specs/README`. `web-api.md` § Projects gains the portfolio
   routes.
4. `verification.md`, including the plain statement that the type mapping is
   eye-verified, not test-covered.
5. Update the AGENTS.md phase pointer at review time.

**Done when:** rubric items 6, 7 and 10 hold.

**Gate:** full `make verify` — the step-6 exit class.

## Executor summary

| Phase | Executor | Why |
|---|---|---|
| 0 | `lead` inline | One command; delegation costs more than it saves |
| 1 design | `lead` | Seam design — table shape and route semantics |
| 1 tests | `fast-worker` | Exact test list in the phase |
| 2 `nav_label` | `lead` | **Prompt-bearing — never delegated** |
| 2 `source_count`, OpenAPI regen | `fast-worker` | Mechanical |
| 3 | `lead` | The slice's core invariant (locking) and the vocabulary seam |
| 4 | `lead` copy, `fast-worker` tests | Entry-surface copy is taste-bearing |
| 5 | `lead` | The plan document is the product's trust surface |
| 6 | `fast-worker`, `lead` reviews copy | Layout route plus one presentational view |
| 7 | `lead` | The report is the most taste-bearing surface; three honesty states |
| 8 | `fast-worker`, `lead` reviews copy | A time-ordered merge is mechanical |
| 9 | `fast-worker` | Drop a filter, add a row variant, exact rules |
| 10 | `fast-worker`, `lead` picks columns | Three views against fixed rules |
| 11 mapping | `lead` | Which rung each surface gets is taste |
| 11 sweep | `fast-worker` | ~250 sites against a fixed table |
| 12 ADR, verification | `lead` | Design decision; evidence needs judgement |
| 12 deferred sweep | `fast-worker` | Mechanical, against the list above |

**No phase routes to `codex`.** It is not installed — `codex` is not on PATH.
Marking it and rerouting mid-build is precisely the rationalisation the executor
column exists to prevent (failure log, 2026-07-05).

## 🛑 Tier 3 shortfall — needs an owner decision before the build starts

This is Tier 3, so the cycle requires adversarial review at the contract stage,
the plan stage **and** on the code, and the mechanism is the other model family
through `codex-rescue`. The Codex CLI is **not installed in this environment**, so
none of those three lanes can run as specified. The same gap was escalated on
task 031 and is still open.

Three ways forward. The owner picks one, and `verification.md` records it:

1. **Install the Codex CLI before the build.** The only option that satisfies
   Tier 3 as written. Recommended — this slice adds a table and public routes,
   which is exactly what a second family is good at attacking.
2. **Same-family adversarial lanes.** A fresh `deep-reasoner` briefed read-only to
   attack the contract, the plan and the diff. Weaker than a family flip, because
   it shares the author's blind spots, but not nothing.
3. **Accept the gap.** Record it in `verification.md` and in the PR, as 031 did.

Do not silently proceed with the lanes missing.

## Out of plan (do not do)

- Case studies, or any second synthesis pass or prompt surface.
- A read-only planning reader inside the chat panel.
- Re-parenting plan, run or artefact onto a new task entity.
- Routes or behaviour for the three disabled capabilities.
- Any share or export behaviour beyond the existing print path.
- A full briefing page.
- Mobile navigation.
- Writing `plan.title` back to the task name (D5 — deferred, recorded).
- Caching a task count on the portfolio row.
- Mounting `useRunStream` in `AppShell` (D3).

## Risks

| Risk | Mitigation |
|---|---|
| A gate is refused mid-slice | Phases 1 and 2 come **first** precisely so a refusal surfaces before any frontend is built against the field. Fallbacks are named in the contract. |
| Locking reads a stale `latest_run` on pages with no stream | D3: poll only where no stream is mounted, matching the existing check-in badge pattern. Tested at the boundary. |
| The type sweep silently deletes or weakens tests | Phase 0 records the baseline count; Phase 11 compares it. Rubric 5 covers the rest. |
| The type sweep repeats the 028 tailwind-merge failure | Registration in the same commit, a sync guard test, the existing `Button.test.tsx` guard, and an explicit eye-check for white-on-blue buttons in the live check. |
| Planning rows offer a control that 422s | Rubric 41 asserts the controls do not exist, not merely that they are disabled. |
| The structural and type diffs get reviewed as one blur | Phase 11 is a separate commit, and review focus item 7 says to read it alone. |
| Tier 3 adversarial lanes cannot run | Escalated above as a decision, not absorbed. |

## Live check (pinned by the contract)

The nine checks in [contract.md](contract.md) § Acceptance checks, on one real
project plus one cheap full-chain smoke. **A full live end-to-end run is not in
scope.** If the staging model route is unavailable — staging's OpenAI quota is
recorded exhausted since 2026-07-28 — name in `verification.md` exactly which
checks could not run. Do not claim them.
