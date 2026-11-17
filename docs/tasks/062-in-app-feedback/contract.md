# Task contract: 062-in-app-feedback

One feature, delivered as seven small pull requests. Boundaries are in
[AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status: approved.** Contract approved (before any code): 2026-11-17 · Rosie Oxbury ·
> Hard gates in § Constraints approved: 2026-11-17 · Rosie Oxbury ·
> ADR: [0045](../../adr/0045-in-app-feedback-events-and-trace-join.md).
>
> **Process ruling (Rosie Oxbury, 2026-11-17):** this feature uses a reduced cycle. One contract
> and one ADR cover the whole feature. Each pull request then follows the brief's sequence, with
> tests and a short description, and has no rubric or plan of its own. This is a deviation from
> the task-cycle for a Tier 4 change. The hard gates in § Constraints still need recorded approval.

Sources: the brief ([policy-atlas-in-app-feedback-brief.md](../../../policy-atlas-in-app-feedback-brief.md))
and the Phase 0 report (`policy-atlas-in-app-feedback-phase0-report.md`, repository root, not
committed). Where this contract and the brief differ, § Changes to the brief gives the reason.

## Goal

A signed-in user can give feedback on a report without leaving the page. Each feedback record
joins to two things:

1. **The pipeline artefact and its Langfuse trace**, so that the record can drive error analysis
   and calibrate the grounding judge.
2. **The user's department and primary job**, so that user research can cut the records.

## Deliverable

Seven pull requests into `dev`, in this order. Each element has its own feature flag, and each
flag is off by default.

| PR | Content | Hard gates it meets |
|---|---|---|
| 1 | Tables, the event envelope, the Langfuse score mirror, feature flags, `runs.trace_id`, `pa_version` | Schema, production config |
| 2 | OP: onboarding profile | Public interface, personal data |
| 3 | CF: citation flag. RAP: report a problem. Adds `source_id` to `ReferenceOut`. | Public interface |
| 4 | MP: missing paper and "should have been kept", with the resolver | Public interface, egress (OpenAlex, existing client) |
| 5 | UIQ: use-intent question | Public interface |
| 6 | CLF: claim flag. Adds `data-claim-id` to `ClaimSpan`. | Public interface |
| 7 | PostHog: the dependency, the events, and the profile mirror to person properties | Dependency, egress, personal data |

All PostHog work is in PR 7. PRs 1 to 6 do not depend on it.

## Terms

| Term | Meaning |
|---|---|
| **CF** | Citation flag: "Useful" / "Not relevant" on each row of the References list and of Sources › All sources. Element A in the brief. |
| **MP** | Missing paper: "A paper I expected is missing" (References foot, Sources toolbar) and "Should have been kept" (each screened-out row). Element B in the brief. |
| **UIQ** | Use-intent question, "Would you use this report in your work?", below the Key findings section. Element C in the brief. |
| **CLF** | Claim flag, at the foot of the "Evidence for this claim" sidebar. Element D in the brief. |
| **RAP** | Report a problem: a button in the app header on every page. Element E in the brief. |
| **OP** | Onboarding profile: a full-screen card at first login. Element F in the brief. |
| **Run** | A `capability_run` row: what the user sees as one run. It has up to 11 component runs. |
| **Component run** | A `runs` row: one pipeline step. Each has one Langfuse trace. |
| **Envelope** | The columns that every `feedback_event` row has, whatever its kind. |
| **Mirror** | A Langfuse score written after the Postgres row commits. Postgres is the record. |
| **Toggle kind** | A kind where a second submit changes or retracts the first: `citation_flag`, `screening_override`, `claim_flag`, `use_intent`. |
| **Retraction** | Setting `retracted_at`. Rows are never deleted. |
| **Document** | A `task_source_snapshot` row. Its ID is scoped to one task. |

## Read first

- The brief and the Phase 0 report (above).
- [data-model.md](../../specs/system/data-model.md), for document identity.
- [ADR 0038](../../adr/0038-langfuse-observability-boundaries.md), for what may go to Langfuse.
- [ADR 0033](../../adr/0033-organisation-tenancy-and-global-admin-read.md), for the ruling on legal copy.
- `docs/knowledge/effective-screen-row-read-rule.md` and `docs/knowledge/new-table-bumps-count-asserts.md`.
- [DESIGN.md](../../../DESIGN.md), before any frontend work.

## Proposed schema

Three new tables and one new column. The repository uses SQLAlchemy Core `Table` objects in
`backend/src/policy_atlas/core/schema.py`, and `Text` plus `CheckConstraint` for closed
vocabularies. This contract follows that.

**`feedback_event`**

| Column | Type | Notes |
|---|---|---|
| `feedback_event_id` | UUID, primary key | Also the Langfuse `score_id`, so the two records reconcile. |
| `user_id` | Text, FK → `app_user` | From the token of the person who gives the feedback. |
| `capability_run_id` | UUID, nullable | Null only for a problem report made before a run exists. |
| `trace_id` | Text, nullable | Copied from the relevant component run. Null for old runs. |
| `surface`, `kind`, `target_type` | Text + check constraint | |
| `target_id` | Text, nullable | An internal UUID as text. See § Changes to the brief. |
| `payload` | JSONB + `jsonb_typeof = 'object'` check | Validated per kind by Pydantic. |
| `pa_version` | Text, nullable | |
| `created_at`, `retracted_at` | timestamptz | `retracted_at` nullable. |

Indexes: `(capability_run_id)`, `(user_id)`, `(kind, created_at)`, `(target_type, target_id)`.

Idempotency: one unique partial index on
`(user_id, capability_run_id, target_type, target_id, kind)` where `retracted_at IS NULL` and
`kind` is a toggle kind. `capability_run_id` is in the index because a document ID is the same
for every run of a task, and the brief requires one flag "per user per run". Non-toggle kinds
are not in the index, because a user can report many missing papers or problems for one run.

**`missing_paper_resolution`**: `feedback_event_id` (FK, primary key), `resolved_id`,
`failure_stage` (Text + check), `resolver_confidence`, `resolved_at`.

**`user_profile`**: `user_id` (FK → `app_user`, primary key), `department`, `team_type`,
`primary_job`, `secondary_job`, `panel_opt_in`, `completed_at`, `skipped_once_at`.

**`runs.trace_id`**: Text, nullable. Written when the component span opens
(`backend/src/policy_atlas/runtime/runner.py:6077`). Settled (Rosie, 2026-11-17). The value is
null for runs made before this change and for runs made with tracing off. For such a run, the
feedback row is saved and the Langfuse score is skipped.

How a feedback event finds its component run: the `runs` table does not record which step a row
is. For `citation_flag`, `claim_flag`, `use_intent` and `missing_paper`, the path is
`synthesis_result.run_id` → `runs.trace_id`. For `screening_override`, no result table holds the
screen step's run ID, so the lookup reads the `component.started` event in `event_log`.

Each new table needs the `len(metadata.tables) == 52` assertions changed to 55.

## Changes to the brief

| Brief | This contract | Reason |
|---|---|---|
| `target_id = <OpenAlex ID>` | `target_id` is `task_source_snapshot_id`. OpenAlex ID and DOI go in `payload` when they exist. | OpenAlex ID is an optional JSONB key. Overton documents do not have one. |
| "Each run has a Langfuse trace" | Each feedback kind names its component: synthesise for `citation_flag`, `claim_flag`, `use_intent`, `missing_paper`; the screen step for `screening_override`; the latest component run for `problem_report`. | A run has several traces. |
| Postgres enums | `Text` + `CheckConstraint` | Repository convention. A check constraint can be dropped and re-created when the job labels change. An enum value cannot be removed. |
| `dismissed` as a score with value null | A categorical score with value `dismissed` | `create_score` in SDK 4.15.4 requires `value: float | str`. |
| Reason chips on a report card or sheet | Existing `Checkbox` and radio controls | `DESIGN.md` § "Where chips are not". Ruling: Rosie, 2026-11-17. |
| 44px buttons | The 32px shared icon button with a 44px hit area | Same ruling. Meets the touch-target aim. |
| `section_id` | `block_id` | Sections have no ID. |
| Judge verdict per claim–span pair | Per-claim verdict only | The judge gives one verdict per claim. |
| Sidebar "Where this comes from" | "Evidence for this claim" | Renamed in the code. It is a modal sheet. CLF sits in it. |
| "Profile settings" | A new entry in the account popover | No settings page exists. |
| Alert channel | One routing function with stubbed destinations | No Slack, SNS or Sentry exists. The brief permits a stub. |
| Twelve flag variables | One list variable per side: `POLICY_ATLAS_FEEDBACK=cf,mp,rap` and `VITE_FEEDBACK=cf,mp,rap` | Same independence, two variables. Follows the existing env-var pattern. |

## Scope / Out of scope

- **In:** the tables above; one `feedback` router; the score mirror in `core/tracing.py`; the
  resolver for MP; the six UI elements; the flag plumbing through `infra/pa_config.json`,
  `policy_atlas_stack.py`, `api/settings.py`, `frontend/src/lib/capabilities.ts` and
  `scripts/deploy.sh`.
- **Out:**
  - The privacy notice text (`PrivacyView.tsx`). ADR 0033: slices do not edit legal copy.
  - Feedback on public pages (`PublicTaskShell`). No signed-in user exists there.
  - Feedback on live (streaming) claims with a `live:` ID.
  - A backfill of `trace_id` for old runs.
  - A retry queue for failed mirrors. See § Constraints.
  - The old branch `origin/feat/in-app-feedback` (PR #52). Not revived.
  - A real alert channel.

## Constraints & approval gates

**Needs recorded approval before the PR that meets it:** schema (PR 1) · production config
(PR 1: `pa_version`, flags) · public interface (PRs 2 to 6) · dependency and egress (PR 7).

- **Privacy.** The notice says that email is the only user identifier stored and that no device
  data is collected. Department, job, browser details and PostHog conflict with it. Ruling
  (Rosie, 2026-11-17): approval from the notice owner exists or is in progress. The flags for
  RAP and OP and for PostHog stay off in every deployed environment until the notice
  changes. The PR description for each must say so.
- **Free text.** Free text goes to Postgres and to the Langfuse score comment only. No query
  text or free text goes to PostHog.
- **Mirror failure.** The Postgres row commits first. The Langfuse write happens after the
  commit, and a failure is logged and does not fail the request. Because the score ID is the
  row ID, a later re-sync script can repair gaps. That script is deferred.
- **Tracing off.** When the Langfuse keys are unset, the mirror is a no-op. Tests pass a fake
  client to assert the score call.
- **`app_user` row.** It is created only by `GET /me`. The feedback write path must not assume
  that it exists.
- **Generated files.** `frontend/openapi.json` and `frontend/src/api/gen/types.ts` change only
  through `make openapi-sync`.
- **Tooling.** `CLAUDE.md` names `black`, `base.yaml` and `load_geodata.py`, which do not exist
  here. Where `CLAUDE.md` and the repository differ, the repository applies (`ruff`,
  `api/settings.py`).

## Public / private boundary

Feedback notes, problem descriptions and query text are private. They stay in Postgres and
Langfuse. Test fixtures use invented text only.

## Design annex

None yet. The frontend elements reuse `Button`, `iconButtonClass`, `Checkbox`, `Select` and
`Sheet`. Frontend work goes to the `frontend-designer` agent, as `AGENTS.md` requires.

## Model route

n/a. No inference. The resolver calls OpenAlex through the existing `OpenAlexLiveBackend`.

## Stop conditions

Stop and ask when: a hard gate has no recorded approval; a join (user → profile, event → trace
→ artefact) cannot be kept; a PR must touch legal copy; scope grows past the element of that PR.

## Acceptance checks

- `make verify` is green for each PR.
- One integration test per kind: post an event, then assert the Postgres row and the score call
  on a fake Langfuse client.
- Unit tests: every branch of the resolver (MP), the show-once rules (UIQ), the profile gating (OP).
- A migration round trip (upgrade, downgrade, upgrade) for PR 1.
- With every flag off, the UI and the API surface are the same as before. One test asserts this.
- Manual check on staging for PR 1: write a score by trace ID to a finished trace, read it in
  the Langfuse UI, then delete it.

## Verification evidence expected

In each PR description: command results, the assumptions that the PR relies on, the flag state
per environment, and known gaps.

## Open decisions

| # | Question | Status |
|---|---|---|
| 1 | Trace join: a stored `runs.trace_id` column, a trace ID derived from the run ID (`create_trace_id(seed=...)`), or a lookup in Langfuse by `run_id` metadata? | Settled: the stored column (Rosie, 2026-11-17). The derived ID hides the gap for old runs. The lookup adds a network read to each submit. |
| 2 | Who records approval for the hard gates: Rosie, or the repository owner? | ❓ Open |
| 3 | `user_profile.source` (signup, migration, waitlist): nothing stores this signal. This contract leaves the column out until a source of the value exists. | ❓ Open |
| 4 | `pa_version`: a deploy-script change that passes the git SHA into the container as an env var. | 🟡 Leaning yes |
| 5 | Close PR #52? | ❓ Open |
| 6 | Branch name. | Settled: `task/062-in-app-feedback` (Rosie, 2026-11-17). The task number was 059 in the first draft. |

## Not yet verified

1. That the self-hosted Langfuse v3 server accepts `create_score` by trace ID from SDK 4.15.4.
   The SDK signature is checked. The server is not. The staging check in PR 1 covers it.
2. That a second run on a task reuses the evidence scope of the first. This decides the meaning
   of "screened out in this run" for MP. Resolve before PR 4.
3. That every old `component.completed` event holds `acquired_tss_by_verb`. Resolve before PR 4.
4. That accounts are not shared in practice.

## Risk tier & review focus

**Tier 4** (migration, public API change, production config), under the reduced cycle that the
status block records. Review focus: the two joins, the idempotency index, personal data behind
flags, and no free text in PostHog.
