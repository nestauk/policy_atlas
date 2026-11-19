# Policy Atlas in-app feedback: Phase 0 report and handover

Date: 2026-11-16. Branch: `task/in-app-feedback`. Author: Claude, for Rosie.

## How to use this file

You are a new Claude session. Rosie will ask you to continue this work.

1. Read `CLAUDE.md`, then `DS_GUIDELINES.md`, then `policy-atlas-in-app-feedback-brief.md` (the brief). All three are at the repository root.
2. Read this file. It is the Phase 0 deliverable that the brief asks for.
3. **Do not start Phase 1.** The brief says that Phase 0 ends with a stop. Rosie has not yet confirmed. She must first answer the five decisions in the last section.

State of the work:

- Phase 0 (discovery) is complete. No code was written. No files were changed, except this one.
- This file is not committed. The brief says the report is "in chat, not committed". Ask Rosie before you commit it.
- All paths are relative to the repository root.

How the facts were collected: three read-only search agents explored the frontend, the backend data model, and the integrations. Claude then checked the most important claims against the code. Each fact below has one of two marks:

- **[checked]**: Claude read the code line directly.
- **[agent]**: a search agent reported it with a citation. Claude did not re-read it. Check it again before you build on it.

## Summary

The user-to-event join is sound. The event-to-trace join and the event-to-document join do not work as the brief assumes:

- A run has several Langfuse traces, and no trace ID is stored for a run.
- A document is not identified by an OpenAlex ID. A References row has no document ID at all.

PostHog, feature flags for feedback, a version string, and an alert channel do not exist yet. The work also meets hard gates in the repository's own process (schema, egress, dependencies) and conflicts with the published privacy notice.

## The ten discovery items

### 1. Frontend stack and component structure

Stack [agent], from `frontend/package.json`:

- React 19, TypeScript 6, Vite 8, pnpm.
- React Router 7 (`createBrowserRouter` in `frontend/src/routes.tsx:61` and `:86`).
- TanStack Query v5. The API client is `openapi-fetch`, with types generated into `frontend/src/api/gen/types.ts`.
- Live run state comes from a server-sent event stream (`frontend/src/store/useRunStream.tsx:54`).
- Tailwind 4. Radix primitives wrapped in `frontend/src/ui/radix/`. Brand components in `frontend/src/ui/brand/`.
- Unit tests: Vitest, Testing Library, jsdom. End-to-end tests: Playwright against a mock API.

Components [agent]:

| Surface | Component | Location |
|---|---|---|
| Task tabs | Agent, Result, Sources, Share, History | `frontend/src/lib/vocabulary.ts:39-45` |
| Report view | `ArtefactView` → `ArtefactReport` → `ReportPage` → `SectionBody` → `AnnotatedProse` → `ClaimSpan` | `frontend/src/views/ArtefactView.tsx:3346`, `:3451`, `:1336`, `:1047` |
| References list | `ReferencesSection` → `ReferenceEntry` | `frontend/src/views/ArtefactView.tsx:4012`, `:4079` |
| All sources table | `SourcesView` → `SourceRow` | `frontend/src/views/SourcesView.tsx:90`, `:618` |
| Screening switch | `All` / `Relevant` / `Screened out`, driven by `?status=` | `frontend/src/views/SourcesView.tsx:72-78`, `:327` |
| Planner | `WorkspaceView` → `TaskAgentPane` → `PlanCard`, `CheckInCard`, `RunTrace` | `frontend/src/views/WorkspaceView.tsx:32`, `frontend/src/views/workspace/TaskAgentPane.tsx:821` |
| App header | `AppShell`, global `NavBar` | `frontend/src/views/AppShell.tsx:299`, `:422` |
| Key findings | Section with `role: "key_findings"` | `frontend/src/api/gen/types.ts:6124`, `frontend/src/views/ArtefactView.tsx:236` |
| Claim sidebar | `ProvenanceSheet` → `ClaimPanel` | `frontend/src/views/ArtefactView.tsx:804`, `:868` |

Notes:

- The brief's "screened-in" view is labelled "Relevant" in the UI. Its API value is `Included`.
- No control is labelled "Approve". The "Start the search" button in `PlanCard` is the approval (`frontend/src/views/workspace/PlanCard.tsx:25`).
- `AppShell` wraps every signed-in page, including `/new` and runs in progress (`frontend/src/routes.tsx:91`). Public pages use `PublicTaskShell` and have no signed-in user. Feedback controls must not show there.
- The Key findings DOM id is a slug built from the title, not the role (`frontend/src/views/ArtefactOutline.tsx:50-51`).
- Shared controls: `Button` (`frontend/src/ui/brand/Button.tsx`), `iconButtonClass` (32px or 28px, `frontend/src/ui/brand/icons.tsx:27`), `Chip` (`frontend/src/ui/brand/Chip.tsx`), `Checkbox`, `Select`, `Sheet` (`frontend/src/ui/radix/Sheet.tsx`). There is no Modal component. `Sheet` is the only Dialog-based overlay.

### 2. Per-user identity

Yes, one stable ID per account.

- `app_user.user_id` is a `Text` primary key that holds the Cognito token `sub` (`backend/src/policy_atlas/core/schema.py:111-120`) [checked].
- Authentication is RS256 OIDC bearer tokens. Ops create accounts per email with `user create --email` (`backend/src/policy_atlas/ops/commands.py:451-530`) [agent].
- Server side: `get_current_user` returns `AuthenticatedUser(user_id=sub)` (`backend/src/policy_atlas/api/auth.py:185-208`) [agent].
- Client side: `useAuth().user.sub` (`frontend/src/auth/types.ts:14-17`) and `useMe()` → `GET /api/v1/me` → `MeOut { user_id, display_name, email?, is_admin, organisation? }` (`frontend/src/api/queries.ts:168-179`) [agent].

Gaps:

- The `app_user` row is created only by `GET /me` (`backend/src/policy_atlas/api/routers/me.py:60-68`) [agent]. A feedback row with a foreign key to `app_user` needs that row to exist.
- `app_user.email` is nullable and "ops- and admin-facing only" (`schema.py:117`) [checked]. `/me` never writes it.
- `capability_run` and `runs` have no user column. A run is attributed only through `task.owner_user_id` [agent]. Feedback takes its `user_id` from the token of the person who gives it, so this is not a blocker. Note that this person is not always the run owner.
- No column records how a user arrived (signup, migration, waitlist). `waitlist_entry` has no foreign key to `app_user` [agent].
- No profile or settings table exists [agent].

### 3. Claims

Claims are addressable in the data, but not in the DOM.

- `ClaimOut` has `claim_id` (UUID), `citations[]`, `claim_type`, `grounding_tier`, `grounding_rationale`, `weakly_grounded` (`frontend/src/api/gen/types.ts:2867-2896`) [checked].
- `CitationOut` has `citation_id` (UUID), `n`, `quote`, `source_id?`, `source_title` (`types.ts:2795-2813`) [agent].
- `claim_id` is `addressable_unit.unit_id`, a random UUID made at write time (`backend/src/policy_atlas/api/read_models/repository.py:2278-2279`) [agent]. It survives reloads. A new synthesis run makes new IDs.
- Tier values: `tier_1`, `tier_2`, `tier_3`, `tier_4`, `unsupported_mis_cited` (`backend/src/policy_atlas/evidence_search/synthesis/grounding_judge.py:52`) [agent].
- `ClaimSpan` renders a plain `<span>` with no id or data attribute (`ArtefactView.tsx:1144-1153`) [agent].
- Live (streaming) claims can carry a fake id `live:<key>` (`ArtefactView.tsx:2268`) [agent]. Do not accept a flag on a live claim.

Cheapest path to addressable claims: add one `data-claim-id` attribute to `ClaimSpan`. The URL parameter `?claim=<claim_id>` already opens the sidebar (`ArtefactView.tsx:3533`).

The grounding judge:

- It gives one verdict per claim, not per claim–citation pair (`grounding_judge.py:55-63`) [agent].
- The verdict is stored in `annotation.payload` under `verdict`, `weakly_grounded`, `rationale`, `judge_model`, `judge_prompt_version` (`backend/src/policy_atlas/evidence_search/synthesis/synthesise.py:4491-4502`) [agent].

Sections:

- A section has no ID. It is a JSONB entry in `synthesis_result.blocks`. Blocks have `block_id` (`schema.py:1396-1398`) [agent].

### 4. Citations and references

- A References row has no document identifier. `ReferenceOut` holds only `n`, `title`, `url`, `venue`, `year`, `authorships` (`types.ts:5440-5453`) [checked].
- The list key is `reference.n`, and a click opens the source by title match (`ArtefactView.tsx:4049`, `:4056`) [checked].
- All sources rows are keyed by `source_id` (`SourcesView.tsx:503-504`) [agent]. This is `task_source_snapshot_id`, an internal UUID that is scoped to one task (`schema.py:393-396`) [checked].
- OpenAlex ID and DOI are not columns. They are keys in `source_snapshot.metadata` (JSONB): `backend_record_id` and `doi` (`backend/src/policy_atlas/evidence_search/sourcing/acquire.py:335-338`, `:411-414`) [checked].
- For Overton documents, `backend_record_id` is Overton's `policy_document_id`, not an OpenAlex ID (`acquire.py:414`) [checked].
- There is no cross-task document identity (`docs/specs/system/data-model.md:124-131`) [agent].
- The API does not expose the OpenAlex ID. `SourceDossierOut` exposes `doi` only [agent].

### 5. Stage membership for a run and a document

Possible, but not one cheap lookup. All [agent], except the table name.

| Fact | Where | Index |
|---|---|---|
| Acquired | `task_source_snapshot.run_id` (first acquiring component run only) | None on `run_id` |
| Screened out, stage 1 | `source_screening_result`, `screen_stage = 1`, status `not_relevant` or `excluded_retracted` | `uq_ssr_scope_source_stage`, `ix_ssr_scope_status` |
| Screened out, stage 2 | Same table, `screen_stage = 2` | Same |
| Selected | `selection_result.selected`, a JSONB array of `{tss_id, …}` | None into the JSON |
| Cited | `citation` → `annotation` → `block` → `artefact.capability_run_id`, plus `chunk` → `task_source_snapshot` | None on the join columns |

There is one screening table with a `screen_stage` column (`schema.py:542`, `:556`, `:607`) [checked]. No `screening_result` table exists.

Complications:

- Screening is keyed by evidence scope and document, not by run. Stage 1 skips documents that already have a row in the same scope (`backend/src/policy_atlas/evidence_search/assess/screen.py:491-505`).
- You must read the "effective" row: highest generation, then highest stage (`docs/knowledge/effective-screen-row-read-rule.md`).
- A document is linked once per task. Later runs do not write a new acquire row.
- Existing read-model code already answers "selected" and "cited" (`repository.py:747-774`). Reuse it for the resolver in element B.

An OpenAlex client exists for the resolver [agent]: `OpenAlexLiveBackend` in `backend/src/policy_atlas/evidence_search/sourcing/search_live.py:317`, with `lookup_dois` (`:519`), `lookup_title` (`:505`), `fetch_by_id` (`:475`). A user-pasted DOI flow already exists in `backend/src/policy_atlas/api/routers/toc.py:1075-1110`.

### 6. Langfuse

- SDK: `langfuse>=4.13,<5` (OpenTelemetry-based). The self-hosted server is v3 (`docs/adr/0038-langfuse-observability-boundaries.md`) [agent].
- Unit of a trace: one per component run (one `runs` row) and one per chat turn (`backend/src/policy_atlas/runtime/runner.py:6075-6082`) [agent].
- A user-facing run is a `capability_run` that has many `runs` rows. It therefore has many traces. They share a session ID, which is the task ID.
- No trace ID is stored for a run. `trace_id` appears in only one backend file, the chat path (`backend/src/policy_atlas/api/answer_core.py:387-392`) [checked]. The `runs` table has no trace column (`schema.py:316-340`) [checked].
- The SDK generates the trace ID. It is not derived from the run ID [agent].
- Trace `user_id` is the Cognito `sub`. Root metadata is `{task_id, run_id}` (`backend/src/policy_atlas/core/tracing.py:617-620`) [agent].
- Tracing is a no-op when the keys are unset. Tests remove the keys (`backend/tests/conftest.py:25-38`) [agent].
- No score wrapper exists. All writes are `client.score_current_trace(...)` inside a live span (`tracing.py:676-680`) [agent]. Nothing writes a score to a finished trace, and nothing writes a score comment.

### 7. PostHog

Not integrated [agent, and checked for `frontend/package.json`]. No dependency, no code, no infra. It appears only in documents as a later item (`docs/tasks/058-perceived-latency/contract.md:256`, `docs/deferred.md:3537`). There is no `identify()` call and no person properties.

### 8. Existing feedback code

- None on this branch. `frontend/src/ui/feedback/` holds error and empty-state components only [agent].
- An unmerged branch exists: `origin/feat/in-app-feedback`, last commit `a799dd0e` on 2026-08-17 [checked]. It is PR #52 [agent]. It has:
  - a `user_feedback` table with `kind IN ('source_not_relevant', 'issue_report')` and a unique partial index for the source flag,
  - `backend/src/policy_atlas/api/routers/feedback.py` with two routes,
  - `frontend/src/ui/feedback/ReportIssueButton.tsx`.
- That branch predates the project-to-task rename (task 038) and will not apply cleanly.

Proposal: do not revive the old branch. Reuse one idea from it, the unique partial index for toggle idempotency. Rosie decides if PR #52 is closed.

Planned items in documents [agent]: "Thumbs-feedback → Langfuse scores" in `docs/deferred.md:2239-2240` and `docs/tasks/029-copilot-chat/contract.md:85`.

### 9. Migrations and tests

Migrations [agent]:

- Alembic. `backend/alembic/env.py` targets `core.schema.metadata`. Run with `uv run alembic upgrade head`.
- Tables are SQLAlchemy Core `Table` objects in `backend/src/policy_atlas/core/schema.py`. There are no ORM model classes.
- No Postgres enums exist [checked: no `Enum(` in `schema.py`]. Closed vocabularies are `Text` columns with a `CheckConstraint` (example at `schema.py:1559-1563`).
- JSONB columns carry a `jsonb_typeof(...) = 'object'` check (example at `schema.py:1453`, `:1474`).
- Migrations use `SET LOCAL lock_timeout`.
- Each new table requires a change to the `len(metadata.tables) == 52` assertions (`backend/tests/core/test_embeddings.py:134` and others) [checked]. See `docs/knowledge/new-table-bumps-count-asserts.md`.

Tests [agent]:

- pytest with xdist and pytest-socket. The suite makes no network calls.
- Real local Postgres with pgvector, one database per worker. Each test rolls back (`backend/tests/conftest.py:54-156`).
- API tests use the `api_client` helper with real dev-issuer tokens (`backend/tests/api/resource_support.py:39-72`). A short example is `backend/tests/api/test_waitlist.py:17-34`.
- Because Langfuse is off in tests, "assert the Langfuse score call" needs a fake client passed in.

### 10. Feature flags

Environment variables only [agent]. No flags table, no library, no per-user or per-organisation toggle.

The existing pattern, end to end:

1. `infra/pa_config.json` sets a boolean per environment.
2. `infra/infra/policy_atlas_stack.py:103` turns it into an env var such as `POLICY_ATLAS_THEORY_OF_CHANGE`.
3. `backend/src/policy_atlas/api/settings.py:53` and `:106` read it into a frozen dataclass.
4. The frontend reads a separate build-time variable, for example `VITE_THEORY_OF_CHANGE` (`frontend/src/lib/capabilities.ts:31`), set in `scripts/deploy.sh:613-616`.

The backend does not tell the frontend about flags.

## Brief assumptions that are wrong

| Brief says | Code says | Effect on the plan |
|---|---|---|
| Each run has a Langfuse trace | Several traces per run, none stored | Store a trace ID on each `runs` row. Old runs will have none. |
| `target_id = <OpenAlex ID>` | Identity is `task_source_snapshot_id`. OpenAlex ID and DOI are optional JSONB keys. Overton documents have no OpenAlex ID. | Use the internal UUID as `target_id`. Copy OpenAlex ID and DOI into the payload for cross-run joins. |
| References rows carry a document ID | They do not | Add `source_id` to `ReferenceOut` before element A. This changes the public API. |
| Steps 1–12, with a `report` step | At most 11 steps: acquire, screen_abstract, classify, appraise, ingest_full_text, screen_full, characterise, select, extract, group, synthesise. Some depend on depth. Synthesise writes the report. (`backend/src/policy_atlas/runtime/task_plan.py:100-107`, `:1157-1174`) | Affects labels in element E only. |
| `source_screening_result` and `screening_result` | One table, with `screen_stage` | Simplifies element B. |
| Screen is LLM ×3 | Adaptive, 1–2 calls | None. |
| Sections have IDs | Sections are JSONB entries. Blocks have `block_id`. | Use `block_id` for `section_id`. |
| Judge verdict per claim–span pair | Per claim only | Store the per-claim verdict. |
| Use enums | The repo uses `Text` plus `CheckConstraint` | Follow the repo. |
| `pa_version` exists | No version reaches the running app. `pyproject.toml` says `0.1.0` and nothing reads it. Releases are git tags that never reach the container. | Needs a deploy change (an env var set from the release tag or SHA). |
| Sidebar is "Where this comes from" | Renamed "Evidence for this claim" (`ArtefactView.tsx:794`) [checked]. It is a Radix Dialog sheet, so it is modal. | Element D sits inside a modal, against the "no modal" rule. |
| "Profile settings" exists | Only an account popover (`AppShell.tsx:186-227`) | Element F needs a new page or a popover entry. |
| `source = signup / migration / waitlist` | No such signal is stored | Ops must supply it, or drop the field. |
| An alert channel exists | No Slack, SNS, SES, or Sentry. CloudWatch alarms have no action. | Stub the routing, as the brief permits. |
| The planner produces a TaskPlan | The planner is the "Task Agent". The table is `plan`. | Names only. |

Correct as stated: select prioritises and does not remove documents. Stage 2 can remove documents.

## Proposed schema

Three tables, as the brief intends, with these changes:

- `feedback_event`: the brief's envelope. `user_id` is `Text` with a foreign key to `app_user`. The run column is `capability_run_id` (the user-facing run). `trace_id` and `pa_version` are nullable.
- `kind`, `surface`, and `target_type` are `Text` columns with check constraints. `payload` is JSONB with a `jsonb_typeof` check, validated per kind by Pydantic in application code.
- A unique partial index on `(user_id, target_type, target_id, kind) WHERE retracted_at IS NULL` gives toggle idempotency.
- Indexes as the brief lists: `(capability_run_id)`, `(user_id)`, `(kind, created_at)`, `(target_type, target_id)`.
- One new nullable `trace_id` column on `runs`, written when the component span opens.
- `missing_paper_resolution` and `user_profile` as in the brief, with `Text` plus check constraints in place of enums.

Why `Text` plus `CheckConstraint` and not an enum: a Postgres enum is a type in the database. A new value needs `ALTER TYPE`, and you cannot remove a value. A check constraint is a rule on one column that a migration can drop and re-create. The J1–J7 job labels will change after user testing, so the repo convention is also the better fit.

## Constraints from the repository's own process

All [agent]. Read the sources before you rely on them.

- The repository has a task-cycle (`.claude/skills/task-cycle/SKILL.md`): contract → rubric → plan → ADR → implement → verify → review → PR. Each phase runs in its own conversation. Artefacts go in `docs/tasks/NNN-slug/`.
- Risk tiers 0 to 4. Schema, auth, runtime egress, dependencies, CI, production config, and public interface changes are "never below Tier 3" and need recorded sign-off first (`AGENTS.md:25-26`).
- This feature meets several hard gates: new tables, new endpoints, new egress to Langfuse and PostHog, a new dependency.
- The highest task number is 058. The next free number is 059. The highest ADR is 0044.
- Task-cycle branch naming is `task/NNN-slug`. `DS_GUIDELINES.md` asks for `{issue number}_{tinyLowerCamelDescription}`. The current branch `task/in-app-feedback` matches neither.
- `AGENTS.md:15-21` says which agent writes which code. Frontend work goes to `frontend-designer`.
- `CLAUDE.md` refers to `base.yaml`, `load_geodata.py`, CRS getters, and `black`. None exist here. The repo uses `ruff`, env-var settings in `backend/src/policy_atlas/api/settings.py`, and `backend/src/policy_atlas/model_routes.toml`.
- `DESIGN.md` rules that conflict with the brief: no chips on a report card or a sheet (`:421`), zero corner radius (`:357`), and the shared icon button is 32px, not 44px.

Privacy:

- The privacy notice says "Email Address: This is the only user-specific identifier we store" and that no device information is collected (`frontend/src/views/legal/PrivacyView.tsx:46-52`).
- `docs/adr/0033-organisation-tenancy-and-global-admin-read.md:80-85` records a ruling that slices do not edit legal copy.
- There is a DPIA precedent: `docs/specs/system/data-flow-queued-ingest.md:11-14`.
- Department, job, browser details, and PostHog conflict with the notice as written.

## Could not verify

1. That SDK v4 can write a score by trace ID, with a comment, to the self-hosted v3 Langfuse server. No existing code does this. Check the Langfuse documentation and test against staging.
2. That Langfuse accepts a score with a null value (the brief's `dismissed` case). Claude expects that it does not. A categorical score is the likely alternative.
3. That a second run on a task reuses the first run's evidence scope. This decides if "screened out in this run" has a clear meaning. Start at `backend/src/policy_atlas/api/routers/runs.py:135-141`.
4. That the Cognito token carries an email claim. Without it, the department prefill works only for users whose email ops have set.
5. That accounts are not shared in practice. The code does not prevent it.
6. That a DPIA or retention policy exists outside the repository.
7. That `frontend/openapi.json` is in sync with the backend routers.
8. That the "Evidence for this claim" sheet scrolls internally, so that a flag block at its foot is reachable.
9. That every historical `component.completed` event holds `acquired_tss_by_verb`.

## Decisions needed from Rosie before Phase 1

1. **Privacy.** The feature conflicts with the privacy notice, and slices do not edit legal copy. Who approves this, and is a DPIA addendum needed?
2. **Process.** Does the task-cycle apply (contract, rubric, plan, ADR, task number 059, hard-gate sign-off), or the brief's simpler PR sequence?
3. **CLAUDE.md.** It describes a different codebase in places. Claude proposes to follow the repository where the two conflict.
4. **Trace join.** Is a stored trace ID per component run acceptable, with each feedback kind tied to the relevant component (synthesise for claims, citations, and use-intent; screen for overrides)?
5. **Design rules.** `DESIGN.md` forbids chips on a report card or a sheet and uses 32px icon buttons. The brief requires chips and 44px targets. Which one applies?

Smaller questions that can wait for Phase 1 planning:

- Feature flags: twelve variables (one backend and one frontend per element), or one list variable per side such as `POLICY_ATLAS_FEEDBACK=a,b,e`?
- `pa_version`: is a deploy-script change acceptable to pass the release tag or SHA into the container?
- Onboarding `source`: who supplies it?
- PR #52: close it?
