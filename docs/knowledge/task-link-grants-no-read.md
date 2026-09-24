---
type: Security rule
title: A task link grants no read — every cross-task copy or read re-checks the grade, every time
description: A scoping task links an Evidence search task and inherits its screened-in documents and report. The link is a pointer, not a permission, so a copy step that trusts it can leak a private task's uploads into a public one. As built, inherit and the linked-report read keep only the links whose source the scoping task's owner can read right now (re-checked each build; unreadable links skipped, named, walk degraded), and a read that crosses via a membership row must also find a task_link between the two tasks.
tags: [security, tenancy, task-link, inherit, options-scoping, task-045]
timestamp: 2026-09-24
---

# Rule

- **Re-check at every build.** `inherit._sources_owner_reads` returns the linked source tasks the
  scoping task's **owner** can read now (`readable_task_leg(owner)`). `inherit_documents` and
  `linked_reports` both filter by it; a link outside it is skipped, logged and named, and the
  walk ends `degraded`. Access checked when the link was made is not access now — the source may
  have gone private, or the owner may have left the org.
- **Cross-task reads need the link, not a stored task id.** The option card's linked-finding read
  joins `finding_reference_union` rows only where a `task_link` targets this task from the row's
  task (`EXISTS`), instead of trusting `option_membership.unit_task_id`.
- Uploads still inherit when readable (owner's choice at the 045 review stack: "Recheck access
  only").

# Why

045 security lane S1 (major): inherit copied a linked task's documents — uploads included — with
no re-check, so a scoping task shared with colleagues could expose a linked task's private
uploads. S2 (minor) was the same shape on the read side. The contract tests already asserted "a
link grants no read to a task it does not target"; the copy step was the gap.

# Watch out

- Any future step that copies or reads across `task_link` (task 5 export, sources) takes the same
  filter; see [tenancy-predicates-in-sql](tenancy-predicates-in-sql.md) for pinning the compiled
  predicate.
- Grade is checked for the **owner**, because the walk writes into the owner's task. The
  inherited rows then read under the scoping task's own visibility, so a readable source's
  uploads reach whoever can read the scoping task, public readers included — the open gap in
  [deferred.md](../deferred.md) ("Linked uploads reach the scoping task's readers").

# Citations

- `backend/src/policy_atlas/runtime/inherit.py` (`_sources_owner_reads`, `inherit_documents`, `linked_reports`)
- `backend/src/policy_atlas/api/readmodels/repository.py` (option card linked findings, the `task_link` `EXISTS`)
- [045 verification.md](../tasks/045-scoping-longlist/verification.md) § Review findings (S1, S2)
