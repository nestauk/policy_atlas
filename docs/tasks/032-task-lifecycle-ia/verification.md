# Verification: 032-task-lifecycle-ia

Evidence for one slice. Public-safe: no secrets, raw source text, credentials or
unredacted traces. Filled at step 6; **Review findings** and **Rubric status** are
added after the review stack (step 7), which runs in a fresh conversation.

> **Adversarial review did not run.** The owner waived it on 2026-08-17 (plan § Review
> stack, D8). The slice **stays Tier 3** regardless — a new table and new public routes
> are a hard gate. What is given up is the fresh-context attack on the *design*: the lane
> that finds an unstated assumption or a missed requirement rather than a local bug. The
> two places that would most have benefited are the portfolio table's tenancy rules and
> the additive-only claim; `/security-review` covers the first and the OpenAPI diff
> covers the second, so the exposure is narrower than a blanket waiver suggests but is
> not zero. It was also unavailable as specified: the mechanism is the other model family
> via `codex-rescue`, and the Codex CLI is not installed in this environment — the same
> gap escalated on task 031, so **no non-Claude reviewer read this slice either**.

## Approval gates

All three fired and all three were approved by the owner on 2026-08-17, in the build
conversation, before the phase that needed them started:

| Gate | What changed | Approved |
|---|---|---|
| Schema | `portfolio` table; nullable `project.portfolio_id`; one Alembic revision | yes |
| Public interface | `/api/v1/portfolios` routes; `portfolio_id` on `PATCH /projects/{id}`; additive `ProjectOut.portfolio_id` + `source_count`; additive `SectionOut.nav_label` | yes |
| Prompt surface | `nav_label` on the section-proposal schema and prompt; version bump | yes |

The first ask returned the schema gate only. Rather than build a table nothing could
reach, the build stopped and re-asked; the owner confirmed all three were intended. No
fallback was taken, so the full G6/G12/G13 scope shipped.

## Commands run

| Command | Result | Notes |
|---|---|---|
| `make verify` (Phase 0 baseline) | pass | infra 44 · frontend 243 tests / 43 files · audit-paths 104 files 0 violations · prompt-guard 12 modules · drift-check OK |
| `make verify-fast` (Phase 1) | pass | 2153 passed · mypy 266 files clean · ruff clean |
| `make verify` (Phase 2, attempt 1) | **fail** | 2 prompt-version pin tests — see § Incidents |
| `make verify` (Phase 2, attempt 2) | pass | `EXIT=0` · frontend 265 tests / 45 files |
| `make frontend-verify` (Phase 4) | pass | 278 tests / 47 files |
| `make frontend-verify` (Phase 5) | pass | 285 tests / 48 files |
| `make frontend-verify` (Phase 6) | pass | 294 tests / 50 files |
| `make verify` (step-6 exit, first run) | pass | `EXIT=0` · backend 2160 passed · mypy 266 files · ruff clean · frontend 330 tests / 54 files |
| `pnpm exec playwright test` (mock journey) | pass | 11 tests, after the rewrite for the new IA |
| `make verify` (step-6 exit, after the four defect fixes) | pass | `EXIT=0` · backend 2160 passed · mypy 266 files · ruff clean · frontend 330 tests / 54 files |
| `pnpm exec playwright test` (mock journey + eye-check) | pass | 11 tests, `EXIT=0` |

**Gate-map deviation, at the owner's direction.** The plan's gate map puts a
`make frontend-verify` at every frontend phase boundary. From Phase 7 onward the owner
directed that the code be written first and "the tests and verifications after". Phases
7–11 therefore carry per-phase `tsc` + `eslint` only, with the test-writing and the full
gate consolidated at the exit. Commits stayed per phase. The cost is attribution: a
regression introduced in Phase 7 is not localised by a gate until the exit run.

**A second gate-map deviation, mine and not directed.** Phase 3's edits were started
while the Phase 2 full-verify gate was still running, so that gate covered work it was
not scoped to. The two phases are still separate commits and both are covered by a green
full run, but Phase 2's gate was not isolated as the plan intends. Recorded rather than
absorbed.

## Checks beyond the build

- **Deterministic tests** — the portfolio routes (11 cases: create, list with derived
  counts, owner scoping, get, partial update, assign, unassign, unknown-vs-cross-owner
  404 equality, assigning an unowned portfolio, a project with no portfolio); the
  migration round-trip; `nav_label` validation at the proposal boundary (accept, 28-char
  boundary, 29-char rejection without truncation, omitted, blank); `source_count`
  null-vs-zero; the locking table row by row; locked-route redirects; retired-path
  redirects; the plan document's every-field and "Not decided yet" behaviour; "Change
  this" seeding without mutating; the new-task entry rules; the Sources Findings-tab
  availability rule; Themes rendering existing descriptions; both conversation kinds
  listing with no rename/archive on a planning row; the type-scale token/registration
  sync guard. Results in the table above and in § End-to-end.
- **AI evals** — none apply. The one prompt change adds a short optional label field;
  its quality is a judgement at the live check, not a scored eval (contract
  § Acceptance checks).
- **Manual / browser** — see § Live check.

## Migration round-trip

`test_migration_roundtrip_portfolio_layer` targets revision `b3c7d914e0a2` **by id**
rather than the `-1` form the neighbouring round-trip test uses. `-1` silently retargets
whichever migration is newest, so the existing test has been exercising a different
migration than its name claims ever since the conversation-model revision landed. The
new test asserts the table and column are absent after `downgrade` and present with
exactly the five expected columns after `upgrade head`.

## End-to-end command

```
cd backend && make reset-test-db && \
  DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test" \
  uv run pytest tests/api/test_portfolios_router.py tests/core/test_schema.py -q
cd frontend && pnpm exec vitest run
```

## Diff summary

By phase, each its own commit on `task/032-task-lifecycle-ia`:

1. **Phase 1 — portfolio table and endpoints (G13).** `portfolio` table; nullable
   `project.portfolio_id`; Alembic `b3c7d914e0a2`; owner-scoped list/create/get/patch;
   `owned_portfolio` raising the same indistinguishable 404 as projects; `PATCH
   /projects/{id}` accepting `portfolio_id` including explicit null.
2. **Phase 2 — two additive fields (G6, G12).** `nav_label` through wire → validation →
   spec → rollup → `SectionOut`; `source_count` on the project row; OpenAPI regenerated.
3. **Phase 3 — vocabulary, routes, lifecycle bar (G3).** `lib/vocabulary.ts`;
   `views/lifecycle.ts`; `LifecycleRoute`; four retired-path redirects; `useProject`
   opt-in polling.
4. **Phase 4 — new task entry (G1, G2).** Capability list; question page; two-call
   create (D4); derived name (D5); optional project selector (D6).
5. **Phase 5 — plan document (G4).** Panel rendering every plan field; "Not decided yet";
   "Change this" seeding the composer via a DOM `CustomEvent`.
6. **Phase 6 — Sources subviews and Themes (G8, G9).** Layout route with `<Outlet/>`;
   Themes from existing read models; conditional Findings tab.
7. **Phase 7 — results additions (G5, G6 client, G7).** Answer callout with three
   summary states; Last updated; Most cited sources; nav-label contents list.
8. **Phases 8 and 10 — History, tasks list, projects (G10–G13).** Time-ordered merge;
   tasks list with one status vocabulary and derived staleness; projects list and detail.
9. **Phase 9 — planning in the chats overlay (G14).** Both kinds listed; no rename or
   archive on a planning row; planning rows open at Plan.
10. **Phase 11 — type scale and layout (G15).** Its own commit (rubric 49).

### Flagged deviations

1. **`archived_at` omitted from the `portfolio` row.** plan.md § Phase 1 step 1 lists it
   while citing rubric 36 ("no status, no lifecycle"). Nothing in the slice writes it —
   there is no archive route — so the column would have had no writer and no reader.
   Resolved toward rubric 36, the binding completion criterion. Recorded as a seam in
   `docs/deferred.md`.
2. **Prompt version bump is v3 → v4, not v2 → v3.** The contract and plan both say
   "bump `synthesise_sections_v2` → v3", written against a stale reading: the code
   already pinned `synthesise_sections_v3`. The owner confirmed v3 → v4 on 2026-08-17.
   The contract's intent (bump the version with the prompt change) holds; only its stated
   numbers were stale.
3. **Six internal deep links repointed, beyond the phase's literal scope.** Making bare
   `/sources` the Themes index broke six live links that relied on it being the
   All-sources table — `?theme=`, `?source=`, `?cited=true`, `?status=screened_out` were
   landing on the wrong tab with the filter silently dropped. They now address
   `/sources/all`. Four further links still pointed at retired paths and went through a
   redirect hop; they now address their real homes. Fixing a regression this slice
   introduced is in scope even though the files were not on the phase's list.
4. **`LandingView.tsx` and `DecisionsView.tsx` deleted.** Both fully superseded and no
   longer routed or imported. Neither had a test file, so no test was lost. The two
   behaviours `DecisionsView` had that History initially dropped — grouped search rows
   and the friendly-detail allowlist — were restored before deletion.
5. **`ChatSidePanel`'s query now returns both conversation kinds**, because the brief
   said to drop the `kind` filter there too. That needed a client-side chat-only filter
   for the panel's launcher and title lookup: a planning conversation keeps
   `status: "active"` even once `closed_at` is set, so without the filter the launcher
   could have picked a planning row as "the latest chat" and opened it in the panel —
   exactly what rubric 42 forbids. Worth a specific look at review.

## Type scale and layout — the honest limit

**The mapping is verified by eye and at review, not by tests.** No test asserts which
rung a given surface landed on. A test asserting class names per surface would be brittle
and would not measure readability, so none was written. Do not read the green suite as
coverage of the mapping.

What **is** mechanically guarded is the failure that actually shipped in 028:
`src/ui/brand/typeScale.test.ts` asserts the `index.css` `--text-*` token list and the
tailwind-merge registration in `cn.ts` are the same set. The guard was confirmed to fail
when `display` is removed from `cn.ts` — a guard that cannot fail is not a guard. The
existing `Button.test.tsx` colour-plus-size assertion still passes.

## Incidents (build-time, for the review conversation)

- **A piped `make verify | tail -N` reports `tail`'s exit code, not `make`'s.** The first
  Phase 2 gate looked green (exit 0) while the backend suite had two failures. It was
  caught by reading the captured output, not by trusting the exit code. Every later gate
  redirects to a log and echoes `EXIT=$?`. This is the most transferable lesson of the
  build.
- **Six hard-coded `len(metadata.tables) == 32` assertions** across five unrelated test
  files. One new table breaks all six; bumped to 33.
- **Two prompt-version pin tests** must move with any bump —
  `test_prompt_versions_are_distinct_constants` and the `synthesis_provenance` assertion
  in `test_characterisation_only_stub_writes_substrate_and_rollup`.
- **`prompt-guard` does not cover `synthesis_backend.py`.** `scripts/prompt_hash_guard.py`
  globs only files whose *name* contains "prompt", and `SECTIONS_SYSTEM_PROMPT` lives in
  `synthesis_backend.py`. Editing the largest prompt surface in the codebase does not
  fail `prompt-guard`. This is a real gap in a guard the project relies on.
- **`RunStatus` is not a named schema in `gen/types.ts`** — openapi-typescript inlines
  the union. Derive it as `components["schemas"]["LatestRun"]["status"]`.
- **The type-scale guard could not use Vite's `?raw` for CSS** (vitest runs with CSS
  processing off, so it resolves to an empty string) and could not use `node:fs` types
  (`tsconfig.app.json` restricts `types` to `vite/client`). Resolved with a file-local
  `/// <reference types="node" />` rather than widening the app config.
- **The mock Playwright journey is not in `make verify` but IS in CI.** `make verify`
  runs `frontend-verify` (typecheck · lint · vitest · build); the journey runs as a
  separate `mock-journey` job. So a reshape can leave `make verify` fully green while the
  PR's CI is red. It was found only by running the journey by hand.
- **A delegated agent parked two regressions as `test.fail()`** rather than reporting them
  as blocking. `test.fail()` on a defect the current slice caused converts a red test into
  a green suite with a comment — the opposite of flag-don't-drop. Briefs should say
  explicitly: report and stop, never park.

## Public safety

Everything committed is public-safe: task documents, the migration, the API contract, the
prompt change, tests and fixtures using synthetic content. No acquired or uploaded source
text, no real run traces, no live model output, no screenshots of real projects. The
manual-check notes below name projects by id only.

## Review findings

_Added at step 7, in a fresh conversation — the adjudicator must not be the chat that
wrote the code._

- **Contract verifier (fresh context):**
- **`/code-review`:**
- **`/security-review`:**
- **`/simplify`:**
- **Adversarial review:** not run — waived by the owner 2026-08-17, and unavailable as
  specified (no Codex CLI on PATH). See the note at the top of this file.

## Rubric status

_Added at step 7. Every item in [rubric.md](rubric.md) checked, or explicitly listed as
not satisfied with the reason._

## Review handoff (step-7/8 inputs)

**Adjudication items** — the five flagged deviations above, in particular (1) the
plan/rubric conflict on `archived_at`, (3) the out-of-phase link fixes, and (5) the
`ChatSidePanel` filter consequence.

**Executor provenance** — no family flip happened. The Codex CLI is not on PATH, so every
phase ran inside the Claude family per plan D7. Lead wrote: the schema and route design,
the `nav_label` prompt line and its validation, `lib/vocabulary.ts`, `views/lifecycle.ts`
and the locking transcription, `LifecycleRoute`, the new-task entry, the plan document
and the composer seam, the results additions and `artefactPresentation`, the History
merge, the tasks/projects views, ADR 0031, the type token and its sync guard.
`fast-worker` wrote: the portfolio route tests, the Phase 2 field tests, the NewTaskView
and PlanDocument tests, the Sources layout and Themes, the chats overlay, the type-scale
sweep (three partitions), and the phase 7/8/10 pure-function tests. **Every delegated
change was reviewed by the lead before it landed**, and two lead-authored defects were
caught by a delegated agent running the gates properly (a typecheck error in the guard
test, a lint error in the History merge).

**Knowledge candidates** (step-8 input):

- **A piped `make verify | tail` masks the real exit code.** A gate that reported green
  was red. Any gate invocation must capture `$?` from `make`, not from the last pipe
  stage. This is the single most likely lesson to recur.
- **Starting the next phase's edits while the current phase's gate runs destroys
  attribution.** The gate then covers work it was not scoped to, and a failure cannot be
  localised. Wait, or branch.
- **A table-count assertion duplicated across six test files is a schema-slice tax** that
  nobody sees until they add a table. Worth collapsing into one shared assertion.
- **`prompt-guard`'s name-glob leaves the largest prompt surface unguarded.** The guard's
  file selection is by filename, not by content, so `synthesis_backend.py` — which holds
  `SECTIONS_SYSTEM_PROMPT` — is invisible to it.
- **A migration round-trip test targeting `-1` silently retargets** whichever revision is
  newest. Target the revision id explicitly or the test's name stops describing what it
  tests.
- **Renaming what a route *means* breaks deep links that still resolve.** Bare `/sources`
  kept returning 200 after it became Themes, so nothing 404'd and nothing failed — the
  filters were just silently dropped. A redirect test would not have caught it; only
  grepping for in-app links to the changed path did.
- **An unregistered `text-*` token is a colour, not a size** (the 028 failure). The
  sync-guard test is cheap and was verified to actually fail; every project with a
  tailwind-merge config and a custom scale wants one.
- **A green `make verify` does not mean green CI.** The mock Playwright journey is a
  separate CI job. Any slice that changes navigation must run it by hand before claiming
  the build is clean.
- **The eye-check is not ceremony — it found two defects nothing else could.** 330 unit
  tests, typecheck and lint were all green while the plan document printed
  `[object Object]` and showed raw enum keys. Both are invisible to a test that does not
  know what the string should say. This is the second slice running (after 028) where
  looking at the rendered page caught something every automated gate missed.
- **Reinventing a rendering helper that already exists is how vocabulary drifts.**
  `planVocabulary.ts` already had `scopeChips` and `vocabLabel`; the plan document
  reimplemented both worse, and the two surfaces disagreed on screen until it was caught
  by eye. Look for the existing presenter before writing a new one.
- **`test.fail()` is not a way to record a regression you introduced.** It turns a red
  suite green and reads as "known issue" rather than "blocker".

## Deferred work

Seams recorded in [docs/deferred.md](../../deferred.md) § Task lifecycle IA: case studies
(with the parked design), the prose "why this source matters", mobile navigation, the full
briefing page, writing `plan.title` back to the task name (D5), portfolio soft-delete,
portfolio membership beyond one, what remains of the workspace-cluster IA, sharing and
export, the three unbuilt capabilities, and per-surface type assertions.

## Live check

**Scope, as the contract pinned it:** the changed surfaces plus one cheap
full-chain smoke. A full live end-to-end run is **not** in scope, and none was run.

**How it was driven.** The staging model route is unavailable — staging's OpenAI quota
is recorded exhausted since 2026-07-28 — so no check was driven against a real project
with a live model. Instead the app was driven in **mock mode** (`VITE_MOCK=1`, the
existing `src/mock/` fixture project and scripted SSE narrative), which renders the real
frontend end to end with no backend. That is a genuine exercise of every changed surface
and of the full plan → run → check-in → report chain, but it is **not** a live check
against real model output, and it is not claimed as one.

| # | Contract check | Result |
|---|---|---|
| 1 | New task → capability list → question → question is the first planning message | **Partly.** The capability list and the question page were driven and read by eye; the four capabilities render and the three unavailable ones are inert. The two-call create (D4) and the question arriving as turn one are covered by unit test only — the mock API does not implement `POST /planning-turns` against a newly created project. **Not confirmed live.** |
| 2 | Locking with no run, during a run, after it completes | **Pass.** Driven in the mock journey and asserted: with no run only Plan is a link; while paused Plan and History are links and Results/Sources/Share render as non-link text; after success all five are links. |
| 3 | Plan document: open it, read every part, use "Change this" | **Pass**, and it caught two defects — `[object Object]` for the country group, and raw enum keys where the plan card showed proper labels. Both fixed. |
| 4 | Results: callout, metadata strip, contents list, top sources, citation → drawer | **Pass** for the report body, the contents list and the citation drawer (mock journey). The answer callout's `pending`/`failed` states are unit-tested, not driven — the fixture carries a verified summary only. |
| 5 | Sources: all four views, a cited row reading as cited | **Pass.** Themes index, Landscape, All sources and Findings all reached through the new subnav; the cited chip renders. |
| 6 | History: the question and plan drafting above the run events | **Pass** (mock journey). |
| 7 | Tasks list and find-a-task; a task in a project; the projects count | **Partly.** The tasks list and its row routing were driven and read by eye. **Find-a-task, the projects list and the projects count were not driven** — the mock API has no `/api/v1/portfolios` implementation, so there is nothing to render. Covered by backend tests (11 route cases incl. derived counts) and by unit tests, but **not exercised in a browser**. |
| 8 | Chats overlay on a finished task: planning listed, badged, opens at Plan, no rename/archive | **Pass** (mock journey and unit tests). |
| 9 | **Read the app by eye**; no sentence at 12px; a primary button is white on blue | **Pass.** Screenshots read at 1440px on the tasks list, the new-task page, the question page and the plan document. The "New task" and "Start the analysis" buttons render white on Nesta blue. Additionally made mechanical in `e2e/eye-check.spec.ts`: a primary button's computed colour is asserted white-on-blue, and no rendered sentence falls below 16px. |

**What could not be checked, plainly:** no live model route (checks 1 and 4's honest-state
paths), and no portfolio surfaces in the browser (check 7's projects half) because the
mock API does not serve the new routes. Neither is claimed as passed above. Extending the
mock API to cover `/portfolios` would close the second gap and is the obvious next step
if the owner wants check 7 driven before merge.

### Mock end-to-end journey

`frontend/e2e/journey.spec.ts` was **rewritten for the new IA** and is green at 11 tests.
This suite runs in CI (`.github/workflows/verify.yml`, job `mock-journey`), so the reshape
would have failed CI had it been left asserting the old navigation.

Rewriting it surfaced three real regressions this slice had introduced, all since fixed
(see the commit "fix four defects found by the live check and the mock journey"):
`RedirectToPath` dropping `location.search`; one internal link still addressing the
retired `/findings`; and the "Open the plan" button overlapping the rail toggle below
`lg`, which made the toggle unclickable at narrow widths. The delegated agent had parked
the last two as `test.fail()` cases; that was the wrong resolution for regressions this
slice caused, so they were fixed and the strict assertions restored. **No `test.fail`
remains in the suite.**
