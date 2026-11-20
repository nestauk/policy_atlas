---
paths:
  - "backend/src/policy_atlas/api/**"
---

# API: facts the code does not show

Each line is a fact about this repository that is easy to miss when you read one file.
Use your own judgement for everything else. Remove a line when a test enforces it.

- In-memory locks and sets in the API (`_turn_locks`, `_dispatching_tasks`) hold only
  inside one process, and tests run one process. A guard that must hold across processes
  is a row's status read under a row lock (`api/locks.py`); one kept only in memory passes
  every test and fails once the API runs more than one process.
- `access.via_public` (from `readable_or_public_task` in `api/routers/access.py`) means an
  anonymous reader. Each route leaves out people's names itself when it is set; nothing
  later in the response path removes them.
- Group and theme ids (`intervention:g01`) are positional and repeat in every run. A read
  model joins a companion result through the run id its row records (for example
  `synthesis_result.grouping_run_id`), not "latest for the task", or an older report shows
  a newer run's labels.
