---
type: Convention
title: A bulk loop over a one-item route inherits that route's side powers and error classes
description: "When a page runs many items through a route built for one deliberate action, check what the route does beyond the plain case (here: it reactivated deactivated people) and how it classes failures (here: a throttle answered 409, which the loop treated as final). Both were invisible in a one-person form and wrong in a 500-person file."
tags: [ops, bulk, api, review]
generated:
  by: agent:task-cycle-review
  at: 2026-11-26
---

# Rule

Add many creates people one at a time through `POST /api/v1/ops/people`, so each person keeps an audit row and an outcome. The one-person route was written for an operator who types one address on purpose. Two of its behaviours were wrong for a file:

- **A side power.** The route turned a deactivated person back on, and the one-person form says so in its toast. A file run did it silently for every deactivated person in an old list. The route now takes `reactivate` (default true); a file run sends false and lists the person as not added.
- **An error class.** Every Cognito error answered 409. The loop retries only "no answer or a server error", so a throttle in the middle of a file was final. Passing Cognito failures now answer 503, from the one list the sweep also uses.

Before a loop reuses a one-item route, list what the route does beyond the plain case and which status each failure gets. Then decide each for the loop.

# Evidence

- `backend/src/policy_atlas/api/routers/ops.py` (`create_person`, `_cognito_failure`), `backend/src/policy_atlas/ops/errors.py` (`TRANSIENT_COGNITO_CODES`).
- `backend/tests/api/test_ops_router.py::test_create_person_without_reactivate_refuses_a_deactivated_person`, `::test_create_person_answers_a_passing_cognito_failure_with_a_retryable_503`.
- `frontend/src/ops/views/AddManyForm.test.tsx`: "never turns a deactivated person back on: counts and lists them, and Try again leaves them out".
