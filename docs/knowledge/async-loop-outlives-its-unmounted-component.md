---
type: Frontend rule
title: An async loop in a component keeps running after the component unmounts
description: A for-await loop started in an event handler does not stop when React unmounts the component. It keeps sending requests while its results go nowhere. Stop it with a ref set on unmount, block the ways out of the page while it runs, and ignore answers that are not the latest.
tags: [react, async, frontend, ops]
generated:
  by: agent:task-cycle-review
  at: 2026-11-26
---

# Rule

React unmounting a component cancels nothing that the component started. Two faults came from this in the file run of Add many:

- A switch above the form unmounted it during a run. The loop went on creating people (12 more writes in 1.5 seconds, measured), but the count, the outcomes and Try again were gone.
- A second file chosen while the first check was still out: the first answer arrived last and replaced the second file's rows, so Create would add the wrong file's people.

What the code does now:

- A ref is set when the component unmounts and the loop reads it before each call. The call in flight may still finish.
- While a run is in progress the switch is disabled, react-router's `useBlocker` asks before a move inside the app, and `beforeunload` asks before the browser leaves.
- Each check takes a number from a counter ref; only the latest may set the result.

`beforeunload` alone guards the browser tab, not a link or a switch inside the app.

# Evidence

- `frontend/src/ops/views/AddManyForm.tsx`, `frontend/src/ops/views/AddPersonView.tsx`.
- `frontend/src/ops/views/AddManyForm.test.tsx`: "asks before moving to another page during a run, and a confirmed move adds no one else"; "shows the file chosen last, even when an earlier file's check answers after it".
