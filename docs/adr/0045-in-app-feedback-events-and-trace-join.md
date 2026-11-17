# ADR 0045 — In-app feedback: one event table, a stored trace ID per component run, and a Langfuse score mirror

- **Status:** Accepted — 2026-11-17 (Rosie Oxbury, task 062 contract gate).
- **Date:** 2026-11-17
- **Task:** [062-in-app-feedback](../tasks/062-in-app-feedback/contract.md) (contract approved
  2026-11-17). The contract defines the element names CF, MP, UIQ, CLF, RAP and OP.
- **Builds on:** [ADR 0038](0038-langfuse-observability-boundaries.md) (what goes to Langfuse,
  and that tracing is a no-op without keys) ·
  [ADR 0033](0033-organisation-tenancy-and-global-admin-read.md) (slices do not edit legal copy).

## Context

Feedback has two consumers. Evals need each record to join to a pipeline artefact and to its
Langfuse trace. User research needs each record to join to the user's department and job.

Three facts in the code shaped the decisions:

- One run that the user sees (`capability_run`) has up to 11 component runs (`runs` rows). Each
  component run has its own trace. The Langfuse SDK makes the trace ID, and no code stored it.
- A document has no stable ID across tasks. Its identity is `task_source_snapshot_id`. OpenAlex
  ID and DOI are optional keys in a JSONB column, and Overton documents have no OpenAlex ID.
- The published privacy notice says that email is the only user identifier stored.

## Decisions

1. **One `feedback_event` table for every kind of feedback.** The envelope columns are the same
   for every kind. `payload` is JSONB, validated per kind by Pydantic. Two more tables hold what
   is not an event: `missing_paper_resolution` and `user_profile`.
2. **Closed vocabularies are `Text` with a `CheckConstraint`, not Postgres enums.** This is the
   repository convention. A migration can drop and re-create a check. An enum value cannot be
   removed. Vocabularies that will change after user testing (jobs, team types, reasons) have no
   database check; the application validates them.
3. **Postgres is the record. A Langfuse score is a mirror.** The row commits first. The score is
   written after the commit with `create_score(trace_id=...)`. The score ID is the row ID, so the
   two records reconcile. A mirror failure is logged and does not fail the request.
4. **The trace ID is stored on each component run: `runs.trace_id`, nullable.** The runner writes
   it when the component span opens. A null value means "no trace to join to" (an old run, or
   tracing off). Rejected: an ID derived from the run ID, because it hides the gap for old runs;
   a lookup in Langfuse at feedback time, because it adds a network read to each submit.
5. **Each feedback event names its component run.** The caller passes the component run, and the
   event copies that run's `trace_id`. Feedback on a report uses the synthesise run. A screening
   override uses the screen run.
6. **Retraction, not deletion.** A retraction sets `retracted_at` and deletes the mirrored score.
   A change to a toggle retracts the active row and inserts a new one in one transaction.
7. **One active row per user, run, target and kind, for toggle kinds only.** A unique partial
   index enforces it. The run is in the key because a document ID is the same for every run of a
   task. Missing-paper reports and problem reports are not in the index, because a user can make
   many for one run.
8. **`target_id` is the internal ID.** For a document it is `task_source_snapshot_id`. OpenAlex ID
   and DOI go in `payload` when they exist.
9. **Feature flags are one list per side.** `POLICY_ATLAS_FEEDBACK` (backend) and `VITE_FEEDBACK`
   (frontend build) each hold a comma-separated list of element names. The default is empty.
10. **`pa_version` is the git commit of the deploy**, passed to the container as
    `POLICY_ATLAS_VERSION`. It is null in local development.

## Consequences

- Feedback on a run made before this change is saved, but it has no Langfuse score. No backfill
  is planned.
- With tracing off (local development, tests), `runs.trace_id` is null and the mirror does
  nothing. Tests assert the score call on a fake client.
- No retry queue exists for a failed mirror. Because the score ID is the row ID, a re-sync
  script can repair gaps later. That script is deferred.
- A second synthesis of a task makes new claim IDs. A claim flag stays with the claim it was
  made on.
- The flags for RAP, OP and PostHog stay off in every deployed environment until the owner of
  the privacy notice changes it.
- Each new table changes the `len(metadata.tables)` assertions in the test suite (52 to 55).
- Rollback of PR 1: the migration downgrade drops the three tables and the column. No other code
  reads them.

## Not yet verified

- That the self-hosted Langfuse v3 server accepts a score by trace ID, and a score delete, from
  SDK 4.15.4. The SDK functions exist. A manual check on staging covers the server.
