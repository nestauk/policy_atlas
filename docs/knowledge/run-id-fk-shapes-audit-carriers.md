---
type: Convention
title: Run-less audit events carry no run id; some tables reach their run only through another table
description: event_log.run_id is nullable, so task lifecycle events outside any run are appended with run_id None, while the composite foreign key still stops a run of one task from writing into another task's log. Annotation has no run_id and reaches its run through block and artefact.
tags: [event-log, persistence, audit]
generated:
  by: claude-opus/5.5
  at: 2026-11-20
sources:
  - id: schema
    resource: backend/src/policy_atlas/core/schema.py
    title: event_log, annotation
  - id: lifecycle
    resource: backend/src/policy_atlas/api/lifecycle.py
---

# Rule

- `event_log.run_id` is nullable. Task lifecycle events that happen outside a run (for example
  rename and archive in `api/lifecycle.py`) are appended with `run_id=None`.
- When a run id is present, the composite foreign key `fk_event_log_run_task`
  (`run_id`, `task_id`) → `runs` stops a run of one task from writing into another task's log.
- Plan lifecycle state lives in `plan` version rows, not in events.
- `annotation` has no `run_id` column. It reaches its run only through `block` → `artefact`.
  A run-scoped annotation query joins that path; when it wants one specific write it orders
  newest first and filters on the payload shape (for example
  `a.payload ? 'cited_finding_ids'`).

See also [event-log-sequence](event-log-sequence.md).
