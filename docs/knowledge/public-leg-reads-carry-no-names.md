---
type: Invariant
title: A read served on the anonymous public leg carries no person's name
description: Task 037 D5 nulls owner_display on the public shape and the longlist read models reduce actors to the words user and agent; every new read model that readable_or_public_task admits must skip its names_of lookup when access.via_public is set, and its access test asserts the anonymous body has null name fields.
tags: [auth, public-leg, pii, read-models, task-054]
timestamp: 2026-11-05
---

# Rule

- `readable_or_public_task` admits an anonymous caller when the task is public and returns
  `Access(via_public=True)`. A route that uses it must carry that flag into its read model.
- The read model resolves user ids to display names only when the caller is not on the public
  leg (`names = {} if public else names_of(...)`); the name fields are `None` otherwise.
  Timestamps may stay.
- The access-matrix test for the route has a case that reads the body anonymously after an
  owner's edit and asserts every name field is `None`.
- Lists that exist to name people (History: "who changed what") stay editors-only.

# Why

The theory-of-change graph and evidence reads were served on the public leg and returned the
owner's display name on every edited box, link and scored document, against task 037 D5. The
security lane and `/code-review` found it independently (2026-11-05). The write grade is
owner-only, so the leak was one name per task, but the rule has no size threshold.

# Citations

- `backend/src/policy_atlas/api/routers/common.py` (task 037 D5: the redacted shape)
- `backend/src/policy_atlas/api/routers/toc.py` (`_readable_toc`, `toc_graph_out(public=...)`)
- `backend/tests/api/test_toc_routes.py::test_the_public_leg_carries_no_editor_names`
- Related: [auth-boundary-widening-needs-both-caller-sweeps](auth-boundary-widening-needs-both-caller-sweeps.md)
