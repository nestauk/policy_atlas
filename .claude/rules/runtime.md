---
paths:
  - "backend/src/policy_atlas/runtime/**"
  - "backend/src/policy_atlas/options_scoping/**"
  - "backend/src/policy_atlas/theory_of_change/**"
---

# Runtime and capabilities: facts the code does not show

Each line is a fact about this repository that is easy to miss when you read one file.
Use your own judgement for everything else. Remove a line when a test enforces it.

- A `task_link` is a pointer, not a grant: the owner may have lost access to the source
  task since the link was made. Code that reads a linked task's rows filters the links by
  what the owner can read now (`_sources_owner_reads` in `runtime/inherit.py`), or a
  private task's material reaches a shared or public one with no error.
- `ScopeConstraints` (`runtime/task_plan.py`) has hand-kept copies that do not derive from
  it: the flattened fields of `PlanDraftWire` (`runtime/task_agent_prompt.py`) and
  `ScopeConstraintsDraft` (`api/contract/task_agent.py`). A field left out of a copy is
  dropped without an error.
