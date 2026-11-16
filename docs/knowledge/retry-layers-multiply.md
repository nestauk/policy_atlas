---
type: Pitfall
title: A step that retries inside a component the runner also retries makes up to four model calls
description: The theory-of-change draft step retries its call once, and the runner retries a failed component once, so one draft can cost four frontier calls; count both layers before sizing a budget or a timeout, and pin the count in a test.
tags: [runtime, retries, cost, theory-of-change, task-054]
timestamp: 2026-11-05
---

# Rule

- Retry layers compose: a step-level retry (one more call on a bad response) inside a runner
  component retry (one more attempt of the component) gives `(1 + step) × (1 + runner)` calls.
- Size the step's budget and the per-step timeout for the product, not for one call.
- Pin the count in a test so a new retry layer shows up as a changed number.

# Why

Task 054's draft walk: the step retries once, the runner retries a failed component once; the
worst case is four draft calls. A test pins it (`calls["draft"] == 4`).

# Citations

- `backend/src/policy_atlas/theory_of_change/draft.py`; `backend/src/policy_atlas/runtime/runner.py`
- `backend/tests/theory_of_change/test_walks.py` (the four-call pin)
- [054 verification § Review handoff](../tasks/054-toc-integration/verification.md)
